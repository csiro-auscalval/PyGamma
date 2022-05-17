import re
from typing import List, Optional
import tarfile
from pathlib import Path
from datetime import datetime

import structlog
import xml.etree.ElementTree as etree
from insar.sensors.types import SensorMetadata


# Example: 20170320_TSX_T041D.tar.gz
ANY_DATA_PATTERN = (
    r"^(?P<product_date>[0-9]{8})"
    r"_(?P<sensor_id>T[SD]X)"
    r"_T(?P<track>[0-9]+D)"
    r"(?P<extension>.tar.gz)?$"
)

SOURCE_DATA_PATTERN = ANY_DATA_PATTERN
POLARISATIONS = ["HH", "VV", "HV", "VH"]  # TODO: anything else?
SUPPORTS_GEOSPATIAL_DB = False


_LOG = structlog.get_logger("insar")

# name: str
# constellation_name: str
# constellation_members: List[str]
# mean_altitude_km: float
# center_frequency_ghz: float
# polarisations: List[str]

# Data from:
# https://www.geoimage.com.au/satellites-sensors/terrasar-x-and-tandem-x/

# From https://www.n2yo.com/satellite/?s=31698 (referenced by https://en.wikipedia.org/wiki/TerraSAR-X)

# TODO: verify constellation_name
METADATA = SensorMetadata(
    "TerraSAR-X",  # sensor name/also the mission name
    "TSX",  #  TSX refers to TSX and TDX/TanDEM-X satellite pair
    ["TSX1", "TDX1"],
    514.8,  # average altitude, source: https://eoportal.org/web/eoportal/satellite-missions/t/terrasar-x
    9.65,
    POLARISATIONS
)


# Terminology:
# Single Look Slant Range Complex (SSC)
# Multi Look Ground Range Detected (MGD)
# Geocoded Ellipsoid Corrected (GEC)
# Enhanced Ellipsoid Corrected (EEC)
XML_METADATA_BASE = (
    r"(?P<sensor>T[SD]X1)_SAR_"  # handle both satellite names just in case
    r"_(?P<product_variant>SSC|MGD|GEC|EEC)"
    r"_(?P<resolution_variant>[SRE_]{4})"
    r"_(?P<imaging_mode>SM|SC|SL|HS)"
    r"_(?P<polarisation_mode>[SDTQ])"
    r"_(?P<antenna_receive_config>(SRA|DRA))"
    r"_(?P<start_date>[0-9]{8})"
    r"T(?P<start_time>[0-9]{6})"
    r"_(?P<end_date>[0-9]{8})"
    r"T(?P<end_time>[0-9]{6})"
    r"(?P<extension>.xml)"
)


def _find_xml_meta_member(names):
    """Searches list of tarfile entries and returns the TSX/TDX XML metadata match obj."""

    # TSX/TDX .tar.gz data files have several data subdirs
    # the XML metadata file has the same name as its parent dir, note *duplicated* names in this example path:
    # 20170411/TDX1_SAR__SSC______SM_S_SRA_20170411T192821_20170411T192829/TDX1_SAR__SSC______SM_S_SRA_20170411T192821_20170411T192829.xml
    #
    # XML_METADATA_BASE can't simply be concatenated as this duplicates regex match group names...
    res = [re.search(XML_METADATA_BASE, n) for n in names]
    res = [r for r in res if r is not None]

    if len(res) > 1:
        msg = f"TSX/TDX found more XML metadata files than expected:\n{res}"
        raise RuntimeError(msg)

    match = res[0]
    return match


def _find_swath_extent(scene_corner_coords):
    """
    Returns 4 tuple of scene extent lat/longs.
    :param scene_corner_coords: XML Element tree nodes to process
    """

    assert len(scene_corner_coords) == 4, "4 coordinate blocks are required to provide extents"

    latitudes = [float(cnr_coord.find("lat").text) for cnr_coord in scene_corner_coords]
    longitudes = [float(cnr_coord.find("lon").text) for cnr_coord in scene_corner_coords]
    assert len(latitudes) == len(longitudes) == 4

    swath_extent = (
        (min(longitudes), min(latitudes)),
        (max(longitudes), max(latitudes))
    )

    return swath_extent


def _find_polarisation(pols):
    # NB: treats pols as a sequence, in the event multiple polarisations are possible
    if len(pols) > 1:
        msg = "Multiple polarisation values found in XML data"
        raise RuntimeError(msg)

    return pols[0]


def _parse_raw_time(raw_time):
    """Return datetime obj from parsing "2017-04-11T19:28:21.237341Z" format timestamps."""
    return datetime.strptime(raw_time, "%Y-%m-%dT%H:%M:%S.%fZ")


def get_data_swath_info(
    data_path: Path,
    raw_data_path: Optional[Path]
):
    if data_path.is_dir():
        # TODO: does previously decompressed data ever need to be handled?
        msg = "TSX sensor: get_data_swath_info() with a directory is not yet implemented"
        raise NotImplementedError(msg)

    # try matching the tar file patterns
    match = re.match(ANY_DATA_PATTERN, data_path.name)

    if not match:
        raise RuntimeError("Invalid data path, does not match a TSX data path")

    elif data_path.suffixes == [".tar", ".gz"]:
        # extract metadata from the XML metadata file

        with tarfile.open(data_path, "r") as tf:
            names = tf.getnames()
            xml_match = _find_xml_meta_member(names)
            start_date = xml_match.group("start_date")
            start_time = xml_match.group("start_time")
            _date = datetime.strptime(start_date + start_time, "%Y%m%d%H%M%S")

            xml_path = xml_match.string
            f = tf.extractfile(xml_path)
            xml_meta = etree.fromstring(f.read())

    else:
        raise RuntimeError("Unsupported TSX/TDX source data file!")

    # extract data from XML
    raw_time = xml_meta.find('productInfo//sceneInfo//start//timeUTC')
    raw_cnr_coords = xml_meta.findall('productInfo//sceneInfo//sceneCornerCoord')
    raw_polarisation = [e.text for e in xml_meta.findall('productInfo//acquisitionInfo//polarisationList//polLayer')]

    res = {'date': _date.date(),
           'swath_extent': _find_swath_extent(raw_cnr_coords),
           'sensor': METADATA.constellation_name,
           'url': str(data_path),
           'polarization': _find_polarisation(raw_polarisation),
           'acquisition_datetime': _parse_raw_time(raw_time.text),
           'swath': "N/A",
           'burst_number': [0],
           'total_bursts': 1,
           'missing_primary_bursts': [],
    }

    return [res]


def acquire_source_data(source_path: str, dst_dir: Path, pols: Optional[List[str]] = None, **kwargs):
    # We only support local paths currently
    # if pols is not None:
    #     raise NotImplementedError("acquiring source data for different polarisations is not implemented")

    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError("The source data path does not exist!")

    if source_path.is_dir():
        # TODO: is this functionality ever required for TSX?
        raise NotImplementedError("TSX Sensor: currently only .tar.gz files are handled")

    # This extracts the contents of the archive directly into dst_dir, TSX/TDX products contain a
    # scene_date top level dir, and we should have a dst_dir/{scene_date} dir of the tar archive contents.
    elif source_path.name.endswith(".tar.gz"):
        with tarfile.open(source_path) as archive:
            archive.extractall(dst_dir)
            members = archive.getmembers()

            if len(members) < 1:
                raise IOError("No files found in TSX tar archive")

            found = False
            for m in members:
                if m.name.endswith("IMAGEDATA"):
                    found = True
                    break

            if not found:
                msg = "Data archive is invalid, could not find IMAGEDATA dir"
                raise RuntimeError(msg)

            img_path = Path(m.name)

            # returned product_dir needs to be: dst_dir / scene_date (from the .tar.gz) / long TSX dir
            img_parent = img_path.parent.name
            if "TDX" not in img_parent and "TSX" not in img_parent:
                msg = f"parent path may not be a T[SD]X dir, img_path={img_parent}"
                raise RuntimeError(msg)

            product_dir = dst_dir / img_path.parent  # need to return the big ugly TSX dir
            return product_dir  # pushes out to DataDownload task, raw_data/date/date/TSX...

    else:
        raise RuntimeError(f"Unsupported TSX source data path: {source_path}")
