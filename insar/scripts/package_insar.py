#!/usr/bin/env python

from typing import Dict, Iterable, List, Optional, Union
from pathlib import Path
import datetime

import structlog
import attr
import pandas as pd
import click

import py_gamma as pg
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
            "product_family": "bck",
        },
        "insar": {
            "suffixs": ("unw.tif", "int.tif", "cc.tif"),
            "angles": ("lv_phi.tif", "lv_theta.tif"),
            "product_base": "INT",
            "dem_base": "DEM",
            "product_family": "insar",
        },
    }

    return _map_dict[product]


def _get_metadata(par_file: Union[Path, str]) -> Dict:
    """
    Returns metadata used in back  product generation.

    :param par_file:
        A full path to a parameter file used in generating backscatter product.

    :returns:
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
    _metadata["azimuth_angle"] = params.get_value("azimuth_angle", dtype=float, index=0)
    _metadata["range_looks"] = params.get_value("range_looks", dtype=int, index=0)
    _metadata["azimuth_looks"] = params.get_value("azimuth_looks", dtype=int, index=0)
    _metadata["range_pixel_spacing"] = params.get_value(
        "range_pixel_spacing", dtype=float, index=0
    )
    _metadata["azimuth_pixel_spacing"] = params.get_value(
        "azimuth_pixel_spacing", dtype=float, index=0
    )
    _metadata["radar_frequency"] = params.get_value(
        "radar_frequency", dtype=float, index=0
    )
    _metadata["heading"] = params.get_value("heading", dtype=float, index=0)
    _metadata["chirp_bandwidth"] = params.get_value(
        "chirp_bandwidth", dtype=float, index=0
    )
    _metadata["doppler_polynomial"] = params.get_value(
        "doppler_polynomial", dtype=float
    )[0:4]
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
    _metadata["near_range_slc"] = params.get_value(
        "near_range_slc", dtype=float, index=0
    )
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

    return _metadata


def _slc_files(
    burst_data: Union[Path, str, pd.DataFrame],
    acquisition_date: datetime.date,
) -> Iterable[str]:
    """
    Returns the SLC files used in forming Single-Look-Composite image.

    :param burst_data:
        A burst information data of a whole SLC stack. Either pandas
        DataFrame or csv file.
    :param acquisition_date:
        A date of the acquisition.

    :returns:
        A dict with parameters used in generating SLC image file.
    """
    if not isinstance(burst_data, pd.DataFrame):
        burst_data = pd.read_csv(Path(burst_data).as_posix())

    burst_data["acquisition_datetime"] = pd.to_datetime(
        burst_data["acquistion_datetime"]
    )
    burst_data["date"] = burst_data["acquisition_datetime"].apply(
        lambda x: pd.Timestamp(x).date()
    )
    _subset_burst_data = burst_data[burst_data["date"] == acquisition_date]

    return [item for item in _subset_burst_data.url.unique()]


def _find_products(
    base_dir: Union[Path, str],
    product_suffixs: Iterable[str],
) -> List[Path]:
    """Returns List of matched suffix files from base_dir."""
    matched_files = []
    for item in Path(base_dir).iterdir():
        for _suffix in product_suffixs:
            if item.name.endswith(_suffix):
                matched_files.append(item)
    return matched_files


def _write_measurements(
    p: DatasetAssembler,
    product_list: Iterable[Union[Path, str]],
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
    p: DatasetAssembler,
    product_list: Iterable[Union[Path, str]],
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
    slc_metadata: Dict
    status: bool

    @classmethod
    def for_path(
        cls,
        _track: str,
        _frame: str,
        _pols: Iterable[str],
        stack_base_path: Union[Path, str],
        product: str,
    ):

        if product == "sar":
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
                par_files = None
                for _pol in _pols:
                    par_files = [
                        item
                        for item in slc_scene_path.glob(
                            f"r{slc_scene_path.name}_{_pol}_*rlks.mli.par"
                        )
                    ]
                    if par_files:
                        break
                if par_files is None:
                    package_status = False
                    _LOG.info(
                        f"missing required parameter needed for packaging"
                        f"for in {slc_scene_path}"
                    )
                    _LOG.info(
                        "missing parameter required for packaging",
                        slc_path=str(slc_scene_path),
                    )

                scene_date = datetime.datetime.strptime(
                    slc_scene_path.name, "%Y%m%d"
                ).date()
                slc_urls = _slc_files(burst_data, scene_date)
                yield cls(
                    track=_track,
                    frame=_frame,
                    par_file=par_files[0],
                    slc_path=slc_scene_path,
                    dem_path=dem_path,
                    slc_metadata={
                        Path(_url).stem: generate_slc_metadata(Path(_url))
                        for _url in slc_urls
                    },
                    status=package_status,
                )
        else:
            raise NotImplementedError(f"packaging of {product} is not implemented")


def _slc_attrs(doc: Dict) -> Dict:
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
    product: Optional[str] = PRODUCTS[0],
    polarizations: Optional[Iterable[str]] = ("VV", "VH"),
    common_attrs: Optional[Dict] = None,
) -> None:

    # Both the VV and VH polarizations has have identical SLC and burst informations.
    # Only properties from one polarization is gathered for packaging.
    for slc in SLC.for_path(track, frame, polarizations, track_frame_base, product):
        _LOG.info("processing slc scene", slc_scene=str(slc.slc_path))

        # skip packaging for missing parameters files needed to extract metadata
        if not slc.status:
            continue

        with DatasetAssembler(Path(out_directory), naming_conventions="dea") as p:
            esa_metadata_slc = slc.slc_metadata
            ard_slc_metadata = _get_metadata(slc.par_file)

            # extract the common slc attributes from ESA SLC files
            # subsequent slc all have the same common SLC attributes
            if common_attrs is None:
                for _, _meta in esa_metadata_slc.items():
                    common_attrs = _slc_attrs(_meta["properties"])
                    break

            product_attrs = map_product(product)
            p.instrument = common_attrs["instrument"]
            p.platform = common_attrs["platform"]
            p.product_family = product_attrs["product_family"]
            p.maturity = "interim"
            p.region_code = f"{int(common_attrs['relative_orbit']):03}{frame}"
            p.producer = "ga.gov.au"
            p.properties["eo:orbit"] = common_attrs["orbit"]
            p.properties["eo:relative_orbit"] = common_attrs["relative_orbit"]

            # processed time is determined from the maketime of slc.par_file
            # TODO better mechanism to infer the processed time of files
            p.processed = datetime.datetime.fromtimestamp(slc.par_file.stat().st_mtime)
            p.datetime = ard_slc_metadata["center_time"]

            # TODO need better logical mechanism to determine dataset_version
            p.dataset_version = "1.0.0"

            # not software version
            software_name, version = Path(pg.__file__).parent.name.split("-")
            url = "http://www/gamma-rs.ch"
            p.note_software_version(software_name, url, version)

            for _key, _val in ard_slc_metadata.items():
                p.properties[f"{product}:{_key}"] = _val

            # store level-1 SLC metadata as extended user metadata
            for key, val in esa_metadata_slc.items():
                p.extend_user_metadata(key, val)

            # find backscatter files and write
            _write_measurements(
                p, _find_products(slc.slc_path, product_attrs["suffixs"])
            )

            # find angles files and write
            _write_angles_measurements(
                p, _find_products(slc.dem_path, product_attrs["angles"])
            )
            p.done()


@click.command()
@click.option(
    "--track", type=click.STRING, help="track name of the grid definition: `T001D`"
)
@click.option(
    "--frame", type=click.STRING, help="Frame name of the grid definition: `F02S`"
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
    "--product",
    type=click.STRING,
    default="sar",
    help="The product to be packaged: sar|insar",
)
@click.option(
    "--polarization",
    type=click.Tuple([str, str]),
    default=("VV", "VH"),
    help="Polarizations used in metadata consolidations for product.",
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to contain the logging events.",
    default="packaging-insar-data.jsonl",
)

def main(
    track,
    frame,
    input_dir,
    pkgdir,
    product,
    polarization,
    log_pathname,
):

    with open(log_pathname, "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))

        _LOG.info(
            "packaging insar",
            track=track,
            frame=frame,
            track_frame_base=input_dir,
            out_directory=pkgdir,
            product=product,
            polarizations=polarization,
        )
        package(
            track=track,
            frame=frame,
            track_frame_base=input_dir,
            out_directory=pkgdir,
            product=product,
            polarizations=polarization,
        )
