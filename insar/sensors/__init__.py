import re
import datetime
from pathlib import Path

from insar.sensors.s1 import ANY_S1_SAFE_PATTERN
from insar.meta_data.s1_gridding_utils import generate_slc_metadata

def identify_data_source(name: str):
    # TODO: Should we return a product type as well? (eg: ESA S1 provides various Level 0/1 products we may be interested in, like SLC and GRD)

    s1_match = re.match(ANY_S1_SAFE_PATTERN, name)
    if s1_match:
        return "Sentinel-1", s1_match.group("sensor")

    raise Exception(f"Unrecognised data source file: {name}")

def get_data_swath_info(data_path: str):
    data_path = Path(data_path)
    constellation, sensor = identify_data_source(data_path.name)

    if constellation == "Sentinel-1":
        s1_match = re.match(ANY_S1_SAFE_PATTERN, data_path.name)
        slc_metadata = generate_slc_metadata(data_path)

        date = datetime.datetime.strptime(s1_match.group("start"), "%Y%m%dT%H%M%S")

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
                "sensor": sensor,
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
