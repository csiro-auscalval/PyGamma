import re
import datetime
from pathlib import Path
from typing import List, Optional

from . import s1
from . import rsat2

_sensors = {
    s1.METADATA.constellation_name: s1,
    rsat2.METADATA.constellation_name: rsat2,
}

def identify_data_source(name: str):
    """
    Identify the constellation/satellite name a source data path is for.

    :param name:
        The source data path name to be identified.
    :returns:
        A tuple of (constellation, satellite) names identified.
    """
    # Note: In the future we may want to return a product type as well...
    # (eg: Level 0/1 products we may be interested in, like SLC and GRD)

    # Turn absolute paths into just the filenames
    name = Path(name).name

    # Check Sentinel-1
    s1_match = re.match(s1.SOURCE_DATA_PATTERN, name)
    if s1_match:
        return s1.METADATA.constellation_name, s1_match.group("sensor")

    # Check RADARSAT-2
    rsat2_match = re.match(rsat2.SOURCE_DATA_PATTERN, name)
    if rsat2_match:
        # There is only a single satellite in RSAT2 constellation,
        # so it has a hard-coded sensor name.
        return rsat2.METADATA.constellation_name, rsat2.METADATA.name

    raise Exception(f"Unrecognised data source file: {name}")

def _dispatch(constellation_or_pathname: str):
    if constellation_or_pathname in _sensors:
        return _sensors[constellation_or_pathname]

    id_constellation, id_sensor = identify_data_source(constellation_or_pathname)
    if id_constellation not in _sensors:
        raise RuntimeError("Unsupported data source: " + constellation_or_pathname)

    return _sensors[id_constellation]

def get_data_swath_info(data_path: str):
    try:
        local_path = Path(data_path)

        return _dispatch(local_path.name).get_data_swath_info(local_path)
    except Exception as e:
        raise RuntimeError("Unsupported path!\n" + str(e))

# Note: source_path is explicitly a str... it's possible we may need
# to support non-local-file paths in the future (eg: S3 buckets or NCI MDSS paths)
def acquire_source_data(
    source_path: str,
    dst_dir: Path,
    pols: Optional[List[str]] = None,
    **kwargs
):
    """
    Acquires the data products for processing from a source data product.

    An example of a source data product is S1 .SAFE or RS2 multi-file structures.

    This function simply lets us treat source data as a path, from which we can
    simply extract data for polarisations we are interested in processing.

    :param source_path:
        The source data path to extract polarised data from.
    :param dst_dir:
        The directory to extract the acquired data into.
    :param pols:
        An optional list of polarisations we are interested in acquiring data for,
        if not provided all possible to be processed will be acquired.
    """
    try:
        local_path = Path(source_path)

        return _dispatch(local_path.name).acquire_source_data(source_path, dst_dir, pols, **kwargs)
    except Exception as e:
        raise RuntimeError("Unsupported path!\n" + str(e))
