from pathlib import Path
from datetime import datetime
from typing import List, Optional
import re
from zipfile import ZipFile
import shutil
import xml.etree.ElementTree as etree
import os.path

from insar.sensors.types import SensorMetadata

# Example: RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_HH_SLC
# Parts: RS2_OK{order key}_PK{product key}_DK{delivery key}_{beam mode}_{acquisition date}_{start time}_{polarisation}_{product type}
ANY_DATA_PATTERN = (
    r"^RS2_"
    r"OK(?P<order_key>[0-9]+)_"
    r"PK(?P<product_key>[0-9]+)_"
    r"DK(?P<delivery_key>[0-9]+)_"
    r"(?P<beam_mode>[^_]+)_"
    r"(?P<start_date>[0-9]{8})_"
    r"(?P<start_time>[0-9]{6})_"
    r"(?P<polarisation>VV|HH|HV|VH)_"
    r"(?P<product>SLC)"
    r"(?P<extension>.zip)?$"
)

SOURCE_DATA_PATTERN = ANY_DATA_PATTERN
POLARISATIONS = ["HH", "HV", "VV", "VH"]
SUPPORTS_GEOSPATIAL_DB = False

METADATA = SensorMetadata(
    "RADARSAT-2",
    "RADARSAT",
    ["RS2"],
    798.0,
    5.405,
    POLARISATIONS
)


def get_data_swath_info(
    data_path: Path,
    raw_data_path: Optional[Path]
):
    match = re.match(ANY_DATA_PATTERN, data_path.name)
    if not match:
        raise RuntimeError("Invalid data path, does not match an RSAT2 data path")

    start_date = match.group("start_date")
    start_time = match.group("start_time")
    date = datetime.strptime(start_date+start_time, "%Y%m%d%H%M%S")
    pol = match.group("polarisation").upper()

    # Load product XML
    if data_path.is_dir():
        with (data_path / f"product.xml").open("r") as fileobj:
            prod_xml = etree.fromstring(fileobj.read())

    elif data_path.suffix == ".zip":
        with ZipFile(data_path, "r") as archive:
            listing = archive.namelist()

            prod_xml_list = [i for i in listing if i.endswith("product.xml")]
            if not prod_xml_list:
                raise FileNotFoundError("RS2 .zip file does not contain a product.xml!")

            if len(prod_xml_list) > 1:
                raise RuntimeError("Unsupported RS2 .zip file, contains more than one product!")

            # Expecting multi-file structure defined here:
            # https://www.pcigeomatics.com/geomatica-help/references/gdb_r/RADARSAT-2.html
            #
            # Living within a top-level directory w/ the same RS2 name as the .zip itself
            prod_xml = prod_xml_list[0]
            if len(prod_xml.split('/')) != 2:
                raise RuntimeError("Unsupported RS2 .zip file structure, expected multi-file RS2 structure in a top-level dir")

            if prod_xml.split('/')[0] != data_path.stem:
                raise RuntimeError("Unsupported RS2 .zip file structure, top-level dir does not match RS2 product name!")

            prod_xml = archive.read(prod_xml).decode("utf-8")
            prod_xml = etree.fromstring(prod_xml)

    else:
        raise RuntimeError("Unsupported RS2 source data file!")

    p = "{http://www.rsi.ca/rs2/prod/xml/schemas}"

    # Ensure we're WGS84 (east, north) coords like the rest of our code...
    # if this ever fails, we may need to add a transform here.
    # currently all RSAT2 data is EPSG 4326.
    geo_xml = prod_xml.find(f"./{p}imageAttributes/{p}geographicInformation")
    if geo_xml.find(f"./{p}referenceEllipsoidParameters/{p}ellipsoidName").text != "WGS 1984":
        raise RuntimeError("Unexpected CRS encountered, expected WGS84!")

    # Extract lat/lon coords of GCPs
    lats = []
    lons = []

    for gcp_coord in geo_xml.findall(f".//{p}geodeticCoordinate"):
        lat = gcp_coord.find(f"{p}latitude")
        lon = gcp_coord.find(f"{p}longitude")

        lats.append(float(lat.text))
        lons.append(float(lon.text))

    swath_extent = (
        (min(lons), min(lats)),
        (max(lons), max(lats))
    )

    # RSAT2 data only has a single frame, which we return as a single "swath"
    # - as opposed to S1, where we return 3 subswaths.
    result = {
        "date": date.date(),
        "swath_extent": swath_extent,
        "sensor": METADATA.constellation_members[0],
        "url": str(data_path),
        "polarization": pol,
        "acquisition_datetime": date,
        # N/A - RSAT2 has no subswaths nor bursts
        "swath": "N/A",
        "burst_number": [0],
        "total_bursts": "1",
        "missing_primary_bursts": [],
    }

    return [result]


def acquire_source_data(source_path: str, dst_dir: Path, pols: Optional[List[str]] = None, **kwargs):
    # We only support local paths currently
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError("The source data path does not exist!")

    # The end result is a subdir in dst_dir w/ the same name as the source data
    if source_path.is_dir():
        def ignore_filter(dir, names):
            included_imagery = [f"imagery_{p}" for p in pols]
            return [i for i in names if "imagery" in i and Path(i).stem not in included_imagery]

        if pols:
            shutil.copytree(source_path, dst_dir / source_path.stem, ignore=ignore_filter, dirs_exist_ok=True)
        else:
            shutil.copytree(source_path, dst_dir / source_path.stem, dirs_exist_ok=True)

        return dst_dir / source_path.stem

    elif source_path.suffix == ".zip":
        with ZipFile(source_path, "r") as zip:
            filtered_list = None

            # Only extract imagery for pols we care about
            if pols:
                filtered_list = zip.namelist()
                included_imagery = [f"imagery_{p}" for p in pols]
                filtered_list = [i for i in filtered_list if "imagery" not in i or Path(i).stem in included_imagery]

            zip.extractall(dst_dir, filtered_list)

        return dst_dir / os.path.commonpath(zip.namelist())

    else:
        raise RuntimeError("Unsupported source data path...")

