#!/usr/bin/env python

import os
import yaml
import attr
import click
import datetime
import structlog
import pandas as pd
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union
import json

from insar.py_gamma_ga import pg
from eodatasets3 import DatasetAssembler
from insar.meta_data.s1_gridding_utils import generate_slc_metadata
from insar.logs import COMMON_PROCESSORS

structlog.configure(processors=COMMON_PROCESSORS)
_LOG = structlog.get_logger("insar")


ALIAS_FMT = {"gamma0": "nrb_{}", "sigma0": "rb_{}"}
PRODUCTS = ("sar", "insar")


def map_product(product: str) -> Dict:
    """Returns product names mapped to a product filename suffix."""
    _map_dict = {
        "sar": {
            "suffixs": ("gamma0.tif", "sigma0.tif"),
            "angles": ("lv_phi.tif", "lv_theta.tif"),
            "product_base": "SLC",
            "dem_base": "DEM",
            "product_family": "nbr",
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


def get_image_metadata_dict(par_file: Union[Path, str]) -> Dict:
    """
    Returns metadata used in backscatter product generation.

    Parameters
    ----------
    par_file: Path or str
        A full path to the image parameter file (*.mli.par)
        used in generating the backscatter product.

    Returns
    -------
        A dict with parameters used in generating a backscatter product.
    """

    par_file = Path(par_file)

    if not par_file.exists():
        _LOG.error("missing par file", par_file=str(par_file))
        raise FileNotFoundError(f"{par_file} does not exists")

    _metadata = dict()

    params = pg.ParFile(par_file.as_posix())

    year, month, day = params.get_value("date")
    _metadata["date"] = datetime.date(int(year), int(month), int(day))
    _dt = datetime.datetime(int(year), int(month), int(day))
    _metadata["center_time"] = _dt + datetime.timedelta(
        seconds=params.get_value("center_time", dtype=float, index=0)
    )
    _metadata["start_time"] = _dt + datetime.timedelta(
        seconds=params.get_value("start_time", dtype=float, index=0)
    )
    _metadata["end_time"] = _dt + datetime.timedelta(
        seconds=params.get_value("end_time", dtype=float, index=0)
    )
    _metadata["incidence_angle"] = params.get_value(
        "incidence_angle", dtype=float, index=0
    )

    azimuth_angle = params.get_value("azimuth_angle", dtype=float, index=0)
    _metadata["azimuth_angle"] = azimuth_angle
    _metadata["looks_range"] = params.get_value("range_looks", dtype=int, index=0)
    _metadata["looks_azimuth"] = params.get_value("azimuth_looks", dtype=int, index=0)
    _metadata["pixel_spacing_range"] = params.get_value(
        "range_pixel_spacing", dtype=float, index=0
    )
    _metadata["pixel_spacing_azimuth"] = params.get_value(
        "azimuth_pixel_spacing", dtype=float, index=0
    )
    _metadata["radar_frequency"] = params.get_value(
        "radar_frequency", dtype=float, index=0
    )
    _metadata["heading"] = params.get_value("heading", dtype=float, index=0)
    _metadata["chirp_bandwidth"] = params.get_value(
        "chirp_bandwidth", dtype=float, index=0
    )
    _metadata["doppler_polynomial"] = params.get_value("doppler_polynomial", dtype=float)[
        0:4
    ]
    _metadata["prf"] = params.get_value("prf", dtype=float, index=0)
    _metadata["azimuth_proc_bandwidth"] = params.get_value(
        "azimuth_proc_bandwidth", dtype=float, index=0
    )
    _metadata["receiver_gain"] = params.get_value("receiver_gain", dtype=float, index=0)
    _metadata["calibration_gain"] = params.get_value(
        "calibration_gain", dtype=float, index=0
    )
    _metadata["sar_to_earth_center"] = params.get_value(
        "sar_to_earth_center", dtype=float, index=0
    )
    _metadata["earth_radius_below_sensor"] = params.get_value(
        "earth_radius_below_sensor", dtype=float, index=0
    )
    _metadata["earth_semi_major_axis"] = params.get_value(
        "earth_semi_major_axis", dtype=float, index=0
    )
    _metadata["earth_semi_minor_axis"] = params.get_value(
        "earth_semi_minor_axis", dtype=float, index=0
    )
    _metadata["near_range_slc"] = params.get_value("near_range_slc", dtype=float, index=0)
    _metadata["center_range_slc"] = params.get_value(
        "center_range_slc", dtype=float, index=0
    )
    _metadata["far_range_slc"] = params.get_value("far_range_slc", dtype=float, index=0)
    _metadata["center_latitude"] = params.get_value(
        "center_latitude", dtype=float, index=0
    )
    _metadata["center_longitude"] = params.get_value(
        "center_longitude", dtype=float, index=0
    )

    if float(azimuth_angle) > 0:
        p.properties["observation_direction"] = "right"
    else:
        p.properties["observation_direction"] = "left"

    # Hard-coded assumptions based on our processing pipeline / data we use
    p.properties["frequency_band"] = "C"
    p.properties["instrument_mode"] = "IW"

    return _metadata


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

    burst_data["acquisition_datetime"] = pd.to_datetime(burst_data["acquistion_datetime"])
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
        # r'^[0-9]{8}_[VV|VH]_*_*.tif'
        try:
            _, pol, _, _suffix = product.stem.split("_")
        except:
            _LOG.error("filename pattern not recognized", product_name=product.name)
            raise ValueError(f"{product.name} not recognized filename pattern")

        p.write_measurement(
            f"{_suffix.split('.')[1]}_{pol.lower()}", product, overviews=None
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
            _, _name = product.stem.split(".")
        except:
            _LOG.error("filename pattern not recognized", product_name=product.name)
            raise ValueError(f"{product.name} not recognized filename pattern")

        p.write_measurement(f"{_name}", product, overviews=None)


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

        if product == "sar":
            # currently, map_product("sar")["product_base"] = "SLC"
            for slc_scene_path in (
                Path(stack_base_path)
                .joinpath(map_product(product)["product_base"])
                .iterdir()
            ):
                package_status = True
                dem_path = Path(stack_base_path).joinpath(
                    map_product(product)["dem_base"]
                )
                burst_data = Path(stack_base_path).joinpath(
                    f"{_track}_{_frame}_burst_data.csv"
                )

                if not burst_data.exists():
                    package_status = False
                    _LOG.info("burst does not exist", burst_data=burst_data)

                # try to find any slc parameter for any polarizations to extract the metadata
                par_files = [
                    item
                    for _pol in _pols
                    for item in slc_scene_path.glob(
                        f"r{slc_scene_path.name}_{_pol}_*rlks.mli.par"
                    )
                ]

                # Ensure we have data for all polarisations requested to be packaged
                if len(par_files) != len(_pols):
                    package_status = False
                    msg = f"{slc_scene_path} missing one or more polarised products, expected {_pols}"
                    _LOG.info(msg, scene=slc_scene_path)
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
    sensor_attrs = {"orbit": doc["orbit"], "relative_orbit": doc["orbitNumber_rel"]}

    sensor = doc["sensor"]
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


def package(
    track: str,
    frame: str,
    track_frame_base: Union[Path, str],
    out_directory: Union[Path, str],
    yaml_base_dir: Union[Path, str, None],
    product: Optional[str] = PRODUCTS[0],
    polarizations: Optional[Iterable[str]] = ("VV", "VH"),
    common_attrs: Optional[Dict] = None,
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

    # Both the VV and VH polarizations has have identical SLC and burst informations.
    # Only properties from one polarization is gathered for packaging.
    for slc in SLC.for_path(
        track, frame, polarizations, track_frame_base, product, yaml_base_dir
    ):
        # skip packaging for missing parameters files needed to extract metadata
        if not slc.status:
            _LOG.info("skipping slc scene", slc_scene=str(slc.slc_path))
            continue

        _LOG.info("processing slc scene", slc_scene=str(slc.slc_path))

        with DatasetAssembler(Path(out_directory), naming_conventions="dea") as p:
            # Metadata extracted verbatim from ESA's acquisition xml files
            esa_slc_metadata = slc.esa_slc_metadata
            esa_s1_raw_data_ids = esa_slc_metadata.keys()
            # Metadata extracted/generated by gamma
            ard_slc_metadata = get_image_metadata_dict(slc.par_file)
            # Extra metadata generated by our own processing workflow
            our_slc_metadata = slc.our_slc_metadata

            # extract the common slc attributes from ESA SLC files
            # subsequent slc all have the same common SLC attributes
            if common_attrs is None:
                for _, _meta in esa_slc_metadata.items():
                    common_attrs = get_slc_attrs(_meta["properties"])
                    break

            # Query our SLCs for orbit file used
            orbit_file = Path(our_slc_metadata["slc"]["orbit_url"]).name

            if "RESORB" in orbit_file:
                orbit_source = "RESORB"
                is_orbit_precise = False
            elif "POEORB" in orbit_file:
                orbit_source = "POEORB"
                is_orbit_precise = True
            else:
                raise Exception(f"Unsupported orbit file: {orbit_file}")

            product_attrs = map_product(product)
            p.instrument = common_attrs["instrument"]
            p.platform = common_attrs["platform"]
            p.product_family = product_attrs["product_family"]

            # TBD: When we support NRT backscatter, we need to differentiate
            # between non-coregistered backscatter (not necessarily interim) &
            # coregistered backscatter (which would be final).
            #
            # currently we only produce coregistered data (and SLC.for_path
            # only looks for coregistered data), so this is fine for now...
            if is_orbit_precise:
                p.maturity = "interim"
            else:
                p.maturity = "final"

            p.region_code = f"{int(common_attrs['relative_orbit']):03}{frame}"
            p.producer = "ga.gov.au"
            p.properties["eo:orbit"] = common_attrs["orbit"]
            p.properties["eo:relative_orbit"] = common_attrs["relative_orbit"]

            p.properties["constellation"] = "sentinel-1"
            p.properties["instruments"] = ["c-sar"]

            # NEEDS REVISION
            # TBD: what should this prefix be called?
            # or do we just throw them into the user metadata instead?
            prefix = "tbd"

            p.properties[f"card4l:orbit_data_source"] = orbit_source
            p.properties[f"{prefix}:orbit_data_file"] = orbit_file  # TBD: Apparently this should be a "link"

            p.properties["sar:polarizations"] = polarizations

            p.properties[f"{prefix}:platform_heading"] = ard_slc_metadata["heading"]

            # These are hard-coded assuptions, based on either our satellite/s (S1) or the data from it we support.
            p.properties["card4l:beam_id"] = "TOPS"
            p.properties["card4l:orbit_mean_altitude"] = 693
            p.properties[f"{prefix}:dem"] = workflow_metadata["dem_path"]
            # END NEEDS REVISION

            # processed time is determined from the maketime of slc.par_file
            # TODO better mechanism to infer the processed time of files
            p.processed = datetime.datetime.fromtimestamp(slc.par_file.stat().st_mtime)
            p.datetime = ard_slc_metadata["center_time"]

            # TODO need better logical mechanism to determine dataset_version
            p.dataset_version = "1.0.0"

            # note the software versions used
            p.note_software_version("gamma", "http://www/gamma-rs.ch", workflow_metadata["gamma_version"])
            p.note_software_version("GDAL", "https://gdal.org/", workflow_metadata["gdal_version"])
            p.note_software_version("gamma_insar", "https://github.com/GeoscienceAustralia/gamma_insar", workflow_metadata["gamma_insar_version"])

            for _key, _val in ard_slc_metadata.items():
                p.properties[f"{product}:{_key}"] = _val

            # store level-1 SLC metadata as extended user metadata
            for key, val in esa_slc_metadata.items():
                p.extend_user_metadata(key, val)

            # find backscatter files and write
            _write_measurements(p, find_products(slc.slc_path, product_attrs["suffixs"]))

            # find angles files and write
            _write_angles_measurements(
                p, find_products(slc.dem_path, product_attrs["angles"])
            )

            # Note lineage
            # TODO: we currently don't index the source data, thus can't implement this yet
            # - they'll be uuid v5's for each acquisition's ESA assigned ID

            # Write thumbnail
            thumbnail_bands = product_attrs["thumbnail_bands"]
            if len(thumbnail_bands) == 1:
                p.write_thumbnail(thumbnail_bands[0], thumbnail_bands[0], thumbnail_bands[0])
            else:
                p.write_thumbnail(**thumbnail_bands)

            p.done()


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
    "--polarization",
    default=["VV", "VH"],
    multiple=True,
    help="Polarizations to be processed VV or VH, arg can be specified multiple times",
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to contain the logging events.",
    default="packaging-insar-data.jsonl",
)
def main(
    track, frame, input_dir, pkgdir, yaml_dir, product, polarization, log_pathname,
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
            polarizations=polarization,
        )
        package(
            track=track,
            frame=frame,
            track_frame_base=input_dir,
            out_directory=pkgdir,
            yaml_base_dir=yaml_dir,
            product=product,
            polarizations=polarization,
        )
