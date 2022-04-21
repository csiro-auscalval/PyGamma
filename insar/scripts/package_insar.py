#!/usr/bin/env python

import os
import shutil
import yaml
import attr
import click
import datetime
import structlog
import pandas as pd
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union, Tuple
import json

from insar.py_gamma_ga import pg
from eodatasets3 import DatasetAssembler
from insar.meta_data.s1_gridding_utils import generate_slc_metadata

from insar.project import ProcConfig
from insar.workflow.luigi.utils import load_settings

_LOG = structlog.get_logger("insar")


ALIAS_FMT = {"gamma0": "nrb_{}", "sigma0": "rb_{}"}
PRODUCTS = ("sar", "insar")


def map_product(product: str) -> Dict:
    """Returns product names mapped to a product filename suffix."""
    _map_dict = {
        "sar": {
            "suffixs": ("geo_gamma0.tif", "geo_sigma0.tif"),
            "angles": ("geo_lv_phi.tif", "geo_lv_theta.tif"),
            "product_base": "SLC",
            "dem_base": "DEM",
            "product_family": "nrb",
            "thumbnail_bands": ["gamma0_vv"]
        },
        "insar": {
            # Note: Suffixes here are wrong / need revising
            "suffixs": ("unw.tif", "int.tif", "coh.tif"),
            "angles": ("lv_phi.tif", "lv_theta.tif"),
            "product_base": "INT",
            "dem_base": "DEM",
            "product_family": "insar",
            # Note: These are wrong / placeholders
            "thumbnail_bands": ["2pi", "2pi", "2pi"]
        },
    }

    return _map_dict[product]


def get_s1_files(
    burst_data: Union[Path, str, pd.DataFrame], acquisition_date: datetime.date,
) -> List:
    """
    Returns a list of Sentinel-1 files used in forming
    Single-Look-Composite image.

    Parameters
    ----------

    burst_data: Path, str, or pd.DataFrame
        A burst information data of a whole SLC stack. Either pandas
        DataFrame or csv file.

    acquisition_date: datetime.date
        A date of the acquisition.

    Returns
    -------
        A list containing the S1 zip paths
    """
    if not isinstance(burst_data, pd.DataFrame):
        burst_data = pd.read_csv(Path(burst_data).as_posix())

    burst_data["acquisition_datetime"] = pd.to_datetime(burst_data["acquisition_datetime"])
    burst_data["date"] = burst_data["acquisition_datetime"].apply(
        lambda x: pd.Timestamp(x).date()
    )
    _subset_burst_data = burst_data[burst_data["date"] == acquisition_date]

    return [s1_zip for s1_zip in _subset_burst_data.url.unique()]


def get_slc_metadata_dict(
    s1_zip_list: list, yaml_base_dir: Union[Path, str, None],
) -> Dict:
    """
    Returns a multi-layered dictionary containing SLC metadata
    for each s1 zip in the given list

    Parameters
    ----------

    s1_zip_list: list
        A list of s1 zip files

    yaml_base_dir: Path, str or None
        the path to the yaml base directory

    Returns
    -------
    A multi-layered dictionary containing SLC metadata.
    """
    if yaml_base_dir:
        yaml_metadata = dict()
        for s1_zip in s1_zip_list:
            # create the filename of the yaml from the s1 zip
            yaml_file = Path(
                os.path.splitext(
                    os.path.join(yaml_base_dir, *list(Path(s1_zip).parts[-4:]))  # parts[-4:] returns the CopHub directory structure we then replicate. e.g (yyyy, yyyy-mm, xy-region, zip name)
                )[0]
                + ".yaml"
            )
            if yaml_file.is_file:
                # check that yaml file exists & load as a dictionary
                with open(yaml_file, "r") as in_fid:
                    slc_metadata = yaml.load(in_fid, Loader=yaml.FullLoader)

            else:
                # yaml file doesn't exist. Generate slc metadata
                slc_metadata = generate_slc_metadata(Path(s1_zip))

            yaml_metadata[Path(s1_zip).stem] = slc_metadata
    else:
        # if yaml_base_dir is None
        yaml_metadata = {
            Path(s1_zip).stem: generate_slc_metadata(Path(s1_zip))
            for s1_zip in s1_zip_list
        }

    return yaml_metadata


def find_products(
    base_dir: Union[Path, str], product_suffixs: Iterable[str],
) -> List[Path]:
    """Returns List of matched suffix files from base_dir."""
    matched_files = []
    for item in Path(base_dir).iterdir():
        for _suffix in product_suffixs:
            if item.name.endswith(_suffix):
                matched_files.append(item)
    return matched_files


def _write_measurements(
    p: DatasetAssembler, product_list: Iterable[Union[Path, str]],
) -> None:
    """
    Unpack and package the sar and insar products
    """
    for product in product_list:
        product = Path(product)

        # TODO currently assumes that filename is of
        # r'^[0-9]{8}_[VV|VH]_*_{projection}_{product_type}.tif'
        try:
            file_parts = product.stem.split("_")
            pol = file_parts[1]
            prod_type = "_".join(file_parts[4:])
        except:
            _LOG.error("filename pattern not recognized", product_name=product.name)
            raise ValueError(f"{product.name} not recognized filename pattern")

        p.write_measurement(
            f"{prod_type}_{pol.lower()}", product, overviews=None
        )


def _write_angles_measurements(
    p: DatasetAssembler, product_list: Iterable[Union[Path, str]],
) -> None:
    """
    Unpack and package the sar and insar products
    """
    for product in product_list:
        product = Path(product)

        # TODO currently assumes that filename is of
        # r'^[0-9]{8}_[VV|VH]_*_*_*.tif'
        try:
            file_parts = product.stem.split("_")
            pol = file_parts[1]
            prod_type = "_".join(file_parts[4:])
        except:
            _LOG.error("filename pattern not recognized", product_name=product.name)
            raise ValueError(f"{product.name} not recognized filename pattern")

        p.write_measurement(f"{prod_type}", product, overviews=None)


@attr.s(auto_attribs=True)
class SLC:
    """
    A single SLC scene in a stack processing
    """

    track: str
    frame: str
    par_file: Path
    slc_path: Path
    dem_path: Path
    esa_slc_metadata: Dict
    our_slc_metadata: Dict
    status: bool

    @classmethod
    def for_path(
        cls,
        _track: str,
        _frame: str,
        _pols: Iterable[str],
        stack_base_path: Union[Path, str],
        product: str,
        yaml_base_dir: Union[Path, str, None],
    ):
        proc_config, metadata = load_settings(stack_base_path / "config.proc")

        stack_base_path = Path(stack_base_path)
        prod_base = (stack_base_path / map_product(product)["product_base"])

        if product == "sar":
            # currently, map_product("sar")["product_base"] = "SLC"
            for slc_scene_path in prod_base.iterdir():
                package_status = True
                dem_path = stack_base_path / map_product(product)["dem_base"]
                burst_data = Path(metadata["burst_data"])

                if not burst_data.exists():
                    package_status = False
                    _LOG.info("burst does not exist", burst_data=burst_data)

                # try to find any slc parameter for any polarisations to extract the metadata
                par_files = [
                    item
                    for _pol in _pols
                    for item in slc_scene_path.glob(
                        f"r{slc_scene_path.name}_{_pol}_*rlks.mli.par"
                    )
                ]

                backscatter_files = [
                    item
                    for _pol in _pols
                    for item in slc_scene_path.glob(
                        f"{slc_scene_path.name}_{_pol}*_geo.gamma0.tif"
                    )
                ]

                # Ensure we have data for all polarisations requested to be packaged
                require_all_pols = False  # TBD: Not sure where we stand on this yet (maybe make it a flag)

                if len(backscatter_files) != len(_pols):
                    msg = f"{slc_scene_path} missing one or more polarised products, expected {_pols}"
                    _LOG.warning(msg, scene=slc_scene_path)

                    if require_all_pols:
                        package_status = False
                        raise Exception(msg)

                scene_date = datetime.datetime.strptime(
                    slc_scene_path.name, "%Y%m%d"
                ).date()

                # get a list of the S1*zip files. These will be used
                # to find the respective yaml files. If these yamls
                # do not exist or if the user did not provide a
                # yaml directory, then the S1 zips are used to
                # extract metadata (this requires pygamma)
                s1_zip_list = get_s1_files(burst_data, scene_date)

                # get multi-layered slc ESA metadata dict
                slc_metadata_dict = get_slc_metadata_dict(s1_zip_list, yaml_base_dir)

                # get our workflow processing metadata dict
                # Note: we take this from the first polarisation's metadata, they should
                # share common values for all the properties we care about for packaging.
                with (slc_scene_path / f"metadata_{_pols[0]}.json").open("r") as file:
                    our_metadata_dict = json.load(file)

                yield cls(
                    track=_track,
                    frame=_frame,
                    par_file=par_files[0],
                    slc_path=slc_scene_path,
                    dem_path=dem_path,
                    esa_slc_metadata=slc_metadata_dict,
                    our_slc_metadata=our_metadata_dict,
                    status=package_status,
                )
        else:
            raise NotImplementedError(f"packaging of {product} is not implemented")


def get_slc_attrs(doc: Dict) -> Dict:
    """
    Returns a properties common to a esa s1_slc from a doc.
    """
    sensor = doc["sensor"]

    sensor_attrs = {
        "sensor": sensor,
        "orbit": doc["orbit"],
        "relative_orbit": doc["orbitNumber_rel"],
        "absolute_orbit": doc["orbitNumber_abs"]
    }

    if sensor == "S1A":
        sensor_attrs["platform"] = "Sentinel-1A"
    elif sensor == "S1B":
        sensor_attrs["platform"] = "Sentinel-1B"
    else:
        raise NotImplementedError(
            f"Unexpected sensor: {sensor}, only supports S1A and S1B"
        )

    sensor_attrs["instrument"] = "C-SAR"

    return sensor_attrs


def get_src_metadata() -> Dict:
    params = pg.ParFile("TODO")

    # Note: this is just a stub, w/ some logic from the _prod_ version that incorrectly had src metadata
    # moved into here (we will flesh this out fully once we actually index/link the source data)

    azimuth_angle = 0 # TODO

    usr = {}

    usr["pixel_spacing_range"] = params.get_value(
        "range_pixel_spacing", dtype=float, index=0
    )
    usr["pixel_spacing_azimuth"] = params.get_value(
        "azimuth_pixel_spacing", dtype=float, index=0
    )

    # TODO: implement CARD4L src metadata here, probably need to dispatch this to sensor-specific impls.
    usr["center_frequency"] = 5.405

    # TBD: src only?
    if float(azimuth_angle) > 0:
        usr["observation_direction"] = "right"
    else:
        usr["observation_direction"] = "left"

    card4l = {
        "orbit_mean_altitude": 693,
    }

    return {
        "card4l": card4l,
        "user": usr,
    }


def get_prod_metadata(workflow_metadata: Dict, slc: SLC) -> Dict:
    """
    Returns metadata used in backscatter product generation.

    Parameters
    ----------
    workflow_metadata: dict
        A dictionary of high level workflow metadata that applies to all SLCs,
        contains information about the product query and processing workfloy
        settings.
    slc: Path or str
        The SLC object representing the product for which we want to extract
        production metadata from.

    Returns
    -------
        A dict of dicts with parameters used in generating a backscatter product.
        { "STAC_extension_or_user": { "metadata_name": "metadata_value" } }
    """

    pols = workflow_metadata["polarisations"]

    # Extract the first ES A"properties" metadata field (common across all SLCs)
    for _, _meta in slc.esa_slc_metadata.items():
        common_attrs = get_slc_attrs(_meta["properties"])
        break

    par_file = Path(slc.par_file)

    if not par_file.exists():
        raise FileNotFoundError(f"{par_file} does not exists")

    params = pg.ParFile(par_file.as_posix())
    year, month, day = params.get_value("date")

    usr = {}
    usr["date"] = datetime.date(int(year), int(month), int(day))
    _dt = datetime.datetime(int(year), int(month), int(day))
    usr["center_time"] = _dt + datetime.timedelta(
        seconds=params.get_value("center_time", dtype=float, index=0)
    )
    usr["start_time"] = _dt + datetime.timedelta(
        seconds=params.get_value("start_time", dtype=float, index=0)
    )
    usr["end_time"] = _dt + datetime.timedelta(
        seconds=params.get_value("end_time", dtype=float, index=0)
    )
    usr["incidence_angle"] = params.get_value(
        "incidence_angle", dtype=float, index=0
    )

    azimuth_angle = params.get_value("azimuth_angle", dtype=float, index=0)
    usr["azimuth_angle"] = azimuth_angle

    usr["looks_range"] = params.get_value("range_looks", dtype=int, index=0)
    usr["looks_azimuth"] = params.get_value("azimuth_looks", dtype=int, index=0)

    usr["radar_frequency"] = params.get_value(
        "radar_frequency", dtype=float, index=0
    )
    usr["heading"] = params.get_value("heading", dtype=float, index=0)
    usr["chirp_bandwidth"] = params.get_value(
        "chirp_bandwidth", dtype=float, index=0
    )
    usr["doppler_polynomial"] = params.get_value("doppler_polynomial", dtype=float)[
        0:4
    ]
    usr["prf"] = params.get_value("prf", dtype=float, index=0)
    usr["azimuth_proc_bandwidth"] = params.get_value(
        "azimuth_proc_bandwidth", dtype=float, index=0
    )
    usr["receiver_gain"] = params.get_value("receiver_gain", dtype=float, index=0)
    usr["calibration_gain"] = params.get_value(
        "calibration_gain", dtype=float, index=0
    )
    usr["sar_to_earth_center"] = params.get_value(
        "sar_to_earth_center", dtype=float, index=0
    )
    usr["earth_radius_below_sensor"] = params.get_value(
        "earth_radius_below_sensor", dtype=float, index=0
    )
    usr["earth_semi_major_axis"] = params.get_value(
        "earth_semi_major_axis", dtype=float, index=0
    )
    usr["earth_semi_minor_axis"] = params.get_value(
        "earth_semi_minor_axis", dtype=float, index=0
    )
    usr["near_range_slc"] = params.get_value("near_range_slc", dtype=float, index=0)
    usr["center_range_slc"] = params.get_value(
        "center_range_slc", dtype=float, index=0
    )
    usr["far_range_slc"] = params.get_value("far_range_slc", dtype=float, index=0)
    usr["center_latitude"] = params.get_value(
        "center_latitude", dtype=float, index=0
    )
    usr["center_longitude"] = params.get_value(
        "center_longitude", dtype=float, index=0
    )

    # Query our SLCs for orbit file used
    orbit_file = Path(slc.our_slc_metadata["slc"]["orbit_url"]).name

    if "RESORB" in orbit_file:
        orbit_source = "predicted"
    elif "POEORB" in orbit_file:
        orbit_source = "definitive"
    else:
        raise Exception(f"Unsupported orbit file: {orbit_file}")

    # TBD: Apparently this should be a "link" - eod3 doesn't seem to have anything about links?
    usr["orbit_data_file"] = orbit_file
    usr["elevation_model"] = workflow_metadata["dem_path"]

    card4l = {
        "specification": "NRB",
        "specification_version": "5.0",
        "noise_removal_applied": False,
        # ?? is this true for gamma? "pixel_coordinate_convention": "center",
        "measurement_type": "gamma0",
        "orbit_data_source": orbit_source,
        # measurement related metadata fields disabled until we go for CARD4L compliance
        #"measurement_convention": "",
    }

    sar = {
        # Hard-coded assumptions based on our processing pipeline / data we use / S1A+S1B sensors
        "instrument_mode": "IW",
        "frequency_band": "C",
        "product_type": "RTC",
        "polarizations": pols,
    }

    sat = {
        "orbit_state": "descending",  # Hard-coded for now (we don't support ascending)
        "absolute_orbit": common_attrs["absolute_orbit"],
        "relative_orbit": common_attrs["relative_orbit"],
    }

    eo = {
        "bands": [
            {
                "name": "SAR",
                "description": "SENTINEL-1 carries a single C-band synthetic aperture radar instrument operating at a centre frequency of 5.405 GHz.",
                "center_wavelength": 55465.76,  # wavelength (um) of 5.405 Ghz / S1 C-band
                # Note: I don't think we can do "full_width_half_max" - bandwidth is programmable, and I'm not sure if we have the metadata for it?
                # Info here if anyone comes back to this:
                # https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-1-sar/sar-instrument
            }
        ]
    }

    return {
        "card4l": card4l,
        "sar": sar,
        "sat": sat,
        "eo": eo,
        "user": usr
    }


def package(
    track: str,
    frame: str,
    track_frame_base: Union[Path, str],
    out_directory: Union[Path, str],
    yaml_base_dir: Union[Path, str, None],
    product: Optional[str] = PRODUCTS[0],
    polarisations: Optional[Iterable[str]] = ("VV", "VH"),
    common_attrs: Optional[Dict] = None,
    # By default we don't error or over-write
    # (eg: if it exists, we skip it / assume it's already been packaged)
    error_on_existing: bool = False,
    overwrite_existing: bool = False
) -> None:

    if not isinstance(track_frame_base, Path):
        track_frame_base = Path(track_frame_base)

    if not isinstance(out_directory, Path):
        out_directory = Path(out_directory)

    if yaml_base_dir and not isinstance(yaml_base_dir, Path):
        yaml_base_dir = Path(yaml_base_dir)

    # Load high level workflow metadata
    with (track_frame_base / "metadata.json").open("r") as file:
        workflow_metadata = json.load(file)

    # Both the VV and VH polarisations has have identical SLC and burst informations.
    # Only properties from one polarisation is gathered for packaging.
    for slc in SLC.for_path(
        track, frame, polarisations, track_frame_base, product, yaml_base_dir
    ):
        try:
            # skip packaging for missing parameters files needed to extract metadata
            if not slc.status:
                _LOG.info("skipping slc scene", slc_scene=str(slc.slc_path))
                continue

            # Metadata extracted verbatim from ESA's acquisition xml files
            esa_slc_metadata = slc.esa_slc_metadata
            # Metadata extracted/generated by gamma
            ard_metadata = get_prod_metadata(workflow_metadata, slc)

            # extract the common slc attributes from ESA SLC files
            # subsequent slc all have the same common SLC attributes
            if common_attrs is None:
                for _, _meta in esa_slc_metadata.items():
                    common_attrs = get_slc_attrs(_meta["properties"])
                    break

            product_attrs = map_product(product)

            # Determine scene date
            scene_YYYYMMDD = str(slc.slc_path.name)

            assert(scene_YYYYMMDD.isdigit() and len(scene_YYYYMMDD) == 8)
            scene_year = scene_YYYYMMDD[:4]
            scene_month = scene_YYYYMMDD[4:6]
            scene_day = scene_YYYYMMDD[6:8]

            padded_track = f"{track[0]}{int(track[1:-1]):03}{track[-1]}"
            padded_frame = f"{frame[0]}{int(frame[1:-1]):03}{frame[-1]}"

            # Example w/ out_directory="T118D_F22S_S1A":
            # T118D_F22S_S1A/ga_s1ac_nrb/T118D/F022S/2017/04/24_interim/
            scene_pkg_YYYYMMdir = out_directory / f"ga_{common_attrs['sensor'].lower()}c_nrb"
            scene_pkg_YYYYMMdir = scene_pkg_YYYYMMdir / padded_track / padded_frame / scene_year / scene_month

            # Check if the scene has already been packaged
            yaml_pattern = f"{scene_day}*/*{padded_track}{padded_frame}_{scene_year}-{scene_month}-{scene_day}*.odc-metadata.yaml"
            odc_yamls = list(scene_pkg_YYYYMMdir.glob(yaml_pattern))
            assert(len(odc_yamls) == 0 or len(odc_yamls) == 1)
            already_packaged = len(odc_yamls) == 1

            if already_packaged:
                # Raise error if desired
                if error_on_existing:
                    _LOG.error("scene is already packaged!", slc_scene=str(slc.slc_path))
                    exit(1)

                # Or skip if we're not going to over-write it
                elif overwrite_existing:
                    _LOG.info("re-packaging existing scene", slc_scene=str(slc.slc_path))
                    for dir in scene_pkg_YYYYMMdir.glob(f"{scene_day}*"):
                        _LOG.info("Deleting existing packaged scene", dir=str(dir))
                        shutil.rmtree(dir)

                # Otherwise, skip packaging this product
                # - assume it's already been packaged / it's fine.
                else:
                    _LOG.info("Skipping already packaged scene", slc_scene=str(slc.slc_path))
                    continue
            else:
                _LOG.info("packaging scene", slc_scene=str(slc.slc_path))

            with DatasetAssembler(out_directory, naming_conventions="dea") as p:
                try:
                    p.instrument = common_attrs["instrument"]
                    p.platform = common_attrs["platform"]
                    p.product_family = product_attrs["product_family"]

                    # TBD: When we support NRT backscatter, we need to differentiate
                    # between non-coregistered backscatter (not necessarily interim) &
                    # coregistered backscatter (which would be final).
                    #
                    # currently we only produce coregistered data (and SLC.for_path
                    # only looks for coregistered data), so this is fine for now...
                    #is_orbit_precise = ard_metadata["card4l"]["orbit_data_source"] == "definitive"
                    # HACK: hard-coded to inprecise / interum maturity for now, pending InSAR go-ahead
                    is_orbit_precise = False

                    if is_orbit_precise:
                        p.maturity = "final"
                    else:
                        p.maturity = "interim"

                    # orbit_data_source is ambiguous / no clear mapping, InSAR team advised to disable
                    del ard_metadata["card4l"]["orbit_data_source"]

                    assert(int(track[1:-1]) == int(common_attrs['relative_orbit']))

                    p.region_code = f"{padded_track}{padded_frame}"
                    p.producer = "ga.gov.au"

                    p.properties["constellation"] = "sentinel-1"

                    # processed time is determined from the maketime of slc.par_file
                    # TODO better mechanism to infer the processed time of files
                    p.processed = datetime.datetime.fromtimestamp(slc.par_file.stat().st_mtime)
                    p.datetime = ard_metadata["user"]["center_time"]

                    # TODO need better logical mechanism to determine dataset_version
                    p.dataset_version = "0.0.1"

                    # note the software versions used
                    p.note_software_version("gamma", "http://www/gamma-rs.ch", workflow_metadata["gamma_version"])
                    p.note_software_version("GDAL", "https://gdal.org/", workflow_metadata["gdal_version"])
                    p.note_software_version("gamma_insar", "https://github.com/GeoscienceAustralia/gamma_insar", workflow_metadata["gamma_insar_version"])

                    # Write all metadata
                    for _ext, _meta in ard_metadata.items():
                        if _ext == "user":
                            for _key, _val in _meta.items():
                                p.extend_user_metadata(_key, _val)

                        else:
                            for _key, _val in _meta.items():
                                p.properties[f"{_ext}:{_key}"] = _val

                    # find backscatter files and write
                    _write_measurements(p, find_products(slc.slc_path, product_attrs["suffixs"]))

                    # find angles files and write
                    _write_angles_measurements(
                        p, find_products(slc.dem_path, product_attrs["angles"])
                    )

                    # Write layover/shadow mask
                    for product_path in slc.dem_path.glob("*lsmap*.tif"):
                        product_name = product_path.stem[product_path.stem.index("lsmap"):].replace(".", "_")
                        p.write_measurement(product_name, product_path, overviews=None)

                    # Note lineage
                    # TODO: we currently don't index the source data, thus can't implement this yet
                    # - they'll be uuid v5's for each acquisition's ESA assigned ID

                    # Write thumbnail
                    thumbnail_bands = product_attrs["thumbnail_bands"]
                    if len(thumbnail_bands) == 1:
                        p.write_thumbnail(thumbnail_bands[0], thumbnail_bands[0], thumbnail_bands[0])
                    else:
                        p.write_thumbnail(**thumbnail_bands)

                finally:
                    p.done()

        except Exception as e:
            _LOG.error("Packaging failed with exception", slc_scene=str(slc.slc_path), exc_info=True)


@click.command()
@click.option(
    "--track", type=click.STRING, help='track name of the grid definition: "T001D"'
)
@click.option(
    "--frame", type=click.STRING, help='Frame name of the grid definition: "F02"'
)
@click.option(
    "--input-dir",
    type=click.Path(exists=True, readable=True),
    help="The base directory of InSAR datasets",
)
@click.option(
    "--pkgdir",
    type=click.Path(exists=True, writable=True),
    help="The base output packaged directory.",
)
@click.option(
    "--yaml-dir",
    type=click.Path(dir_okay=True, file_okay=False),
    default=None,
    help="The base directory containing yaml files",
)
@click.option(
    "--product",
    type=click.STRING,
    default="sar",
    help="The product to be packaged: sar|insar",
)
@click.option(
    "--polarisation",
    default=["VV", "VH"],
    multiple=True,
    help="Polarisations to be processed VV or VH, arg can be specified multiple times",
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to contain the logging events.",
    default="packaging-insar-data.jsonl",
)
@click.option(
    "--overwrite-existing",
    type=click.BOOL, default=False, is_flag=True,
    help="Ensures already packaged products in the pkgdir will be over-written with new packaged products.",
)
@click.option(
    "--error-on-existing",
    type=click.BOOL, default=False, is_flag=True,
    help="Will cause any product that's requested to be packaged, which has already been packaged in pkgdir, to raise an error.",
)
def main(
    track: str,
    frame: str,
    input_dir: str,
    pkgdir: str,
    yaml_dir: str,
    product: str,
    polarisation: Tuple[str],
    log_pathname: str,
    overwrite_existing: bool,
    error_on_existing: bool
):
    with open(log_pathname, "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))

        _LOG.info(
            "packaging insar",
            track=track,
            frame=frame,
            track_frame_base=input_dir,
            out_directory=pkgdir,
            yaml_base_dir=yaml_dir,
            product=product,
            polarisations=polarisation,
            overwrite_existing=bool(overwrite_existing),
            error_on_existing=bool(error_on_existing)
        )

        try:
            package(
                track=track,
                frame=frame,
                track_frame_base=input_dir,
                out_directory=pkgdir,
                yaml_base_dir=yaml_dir,
                product=product,
                polarisations=polarisation,
                error_on_existing=error_on_existing,
                overwrite_existing=overwrite_existing
            )
        except:
            _LOG.error("Unhandled exception while packaging", exc_info=True)
