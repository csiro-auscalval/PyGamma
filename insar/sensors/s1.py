from pathlib import Path
from datetime import datetime
import re
from typing import List, Optional

from insar.sensors.types import SensorMetadata
from insar.meta_data.s1_gridding_utils import generate_slc_metadata
from insar.meta_data.s1_slc import S1DataDownload

# Example: S1A_IW_SLC__1SDV_20190918T200934_20190918T201001_029080_034CEE_270E.SAFE
ANY_S1_SAFE_PATTERN = (
    r"^(?P<sensor>S1[AB])_"
    r"(?P<beam>S1|S2|S3|S4|S5|S6|IW|EW|WV|EN|N1|N2|N3|N4|N5|N6|IM)_"
    r"(?P<product>SLC|GRD|OCN)(?:F|H|M|_)_"
    r"(?:1|2)"
    r"(?P<category>S|A)"
    r"(?P<pols>SH|SV|DH|DV|VV|HH|HV|VH)_"
    r"(?P<start>[0-9]{8}T[0-9]{6})_"
    r"(?P<stop>[0-9]{8}T[0-9]{6})_"
    r"(?P<orbitNumber>[0-9]{6})_"
    r"(?P<dataTakeID>[0-9A-F]{6})_"
    r"(?P<productIdentifier>[0-9A-F]{4})"
    r"(?P<extension>.SAFE|.zip)$"
)

SOURCE_DATA_PATTERN = ANY_S1_SAFE_PATTERN
POLARISATIONS = ["HH", "HV", "VV", "VH"]
SUPPORTS_GEOSPATIAL_DB = True

METADATA = SensorMetadata(
    "Sentinel-1",
    "Sentinel-1",
    ["S1A", "S1B"],
    693.0,
    5.4,
    POLARISATIONS
)

def get_data_swath_info(
    data_path: Path,
    raw_data_path: Optional[Path]
):
    s1_match = re.match(ANY_S1_SAFE_PATTERN, data_path.name)
    if not s1_match:
        raise RuntimeError("Invalid data path, does not match a SAFE path")

    slc_metadata = generate_slc_metadata(data_path)

    date = datetime.strptime(s1_match.group("start"), "%Y%m%dT%H%M%S")

    # Parse polarisation identifier
    pols = s1_match.group("pols")
    if pols[0] == "D":
        pols = [pols[1] + "V", pols[1] + "H"]
    elif pols[0] == "S":
        pols = [pols[1] * 2]
    else:
        pols = [pols]

    # Parse ESA metadata for burst and extent information for each swath
    result = []

    all_bursts = set()

    for data_id, data in slc_metadata["measurements"].items():
        sensor, swath_id, _, pol, starts, ends = data_id.split("-")[:6]
        swath_id = swath_id.upper()
        pol = pol.upper()

        # Track burst numbers
        burst_numbers = [v["burst_num"] for k,v in data.items() if k.startswith("burst ")]

        all_bursts = all_bursts | set(burst_numbers)

        # Measure swath extent
        swath_extent = None

        for k,v in data.items():
            if not k.startswith("burst "):
                continue

            minx = min(x for x,y in v["coordinate"])
            miny = min(y for x,y in v["coordinate"])

            maxx = max(x for x,y in v["coordinate"])
            maxy = max(y for x,y in v["coordinate"])

            if swath_extent:
                swath_min, swath_max = swath_extent
                swath_extent = (
                    (min(minx, swath_min[0]), min(miny, swath_min[1])),
                    (max(maxx, swath_max[0]), max(maxy, swath_max[1]))
                )
            else:
                swath_extent = ((minx, miny), (maxx, maxy))

        swath_data = {
            "date": date.date(),
            "swath": swath_id,
            "burst_number": burst_numbers,
            "swath_extent": swath_extent,
            "sensor": sensor.upper(),
            "url": str(data_path),
            "total_bursts": "?",  # Filled in below
            "polarization": pol,
            "acquisition_datetime": date,
            "missing_primary_bursts": []  # N/A at this stage (only applies to queries)
        }

        result.append(swath_data)

    for r in result:
        r["total_bursts"] = len(all_bursts)

    return result


def acquire_source_data(source_path: str, dst_dir: Path, pols: Optional[List[str]] = None, **kwargs):
    poeorb_path = kwargs["poeorb_path"]
    resorb_path = kwargs["resorb_path"]

    download_obj = S1DataDownload(
        Path(source_path),
        pols or POLARISATIONS,
        Path(poeorb_path) if poeorb_path else None,
        Path(resorb_path) if resorb_path else None,
    )

    download_obj.slc_download(dst_dir)
