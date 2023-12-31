from pathlib import Path
from datetime import datetime
from typing import List, Optional
import re
import tarfile
import shutil
import os.path

import insar.constant as const

from insar.gamma.proxy import create_gamma_proxy
from insar.parfile import GammaParFile as ParFile
from insar.sensors.types import SensorMetadata
from insar.utils import TemporaryDirectory

import insar.constant as const

# Example: 20151215_PALSAR2_T124A_F6660.tar.gz
# Example: 20100117_PALSAR1_T433A_F6530.tar.gz
# Parts: {date}_PALSAR{sensor index}_T{track}_F{frame}
ANY_DATA_PATTERN = (
    r"^(?P<product_date>[0-9]{8})"
    r"_(?P<sensor_id>PALSAR[12])"
    r"_T(?P<track>[0-9]+)(?P<rel_orbit>[AD])"
    r"_F(?P<frame>[0-9]+)"
    r"(?P<extension>.tar.gz)?$"
)

SOURCE_DATA_PATTERN = ANY_DATA_PATTERN
POLARISATIONS = ["HH", "HV", "VV", "VH"]
SUPPORTS_GEOSPATIAL_DB = False

METADATA = SensorMetadata(
    "ALOS PALSAR",
    "ALOS",
    ["ALOS-1", "ALOS-2"],
    [691.65, 628.0],
    1.270,
    POLARISATIONS
)

pg = create_gamma_proxy(Exception)

def parse_product_summary(summary_text: str) -> dict:
    """
    Parses the ALOS `summary.txt` files that come with the JAXA products into a dict.
    """
    # Convert from key="value", into [ (key, value) ]
    summary = [ [ i.strip('"') for i in line.split('=') ] for line in summary_text.splitlines() ]
    # Convert from [ (key, value) ] into { key: value }
    summary = { key: val for key, val in summary }

    return summary


def get_data_swath_info(
    data_path: Path,
    raw_data_path: Optional[Path]
):
    match = re.match(ANY_DATA_PATTERN, data_path.name)
    if not match:
        raise RuntimeError("Invalid data path, does not match an ALOS PALSAR data path")

    if not raw_data_path or not raw_data_path.is_dir():
        raise RuntimeError("Cannot get swath info from ALOS archive, only from directory")

    with TemporaryDirectory(delete=const.DISCARD_TEMP_FILES) as temp_dir_name:
        temp_dir = Path(temp_dir_name)

        summary = list(raw_data_path.glob("*/summary.txt"))
        if len(summary) == 0:
            raise FileNotFoundError("Failed to find ALOS product, no summary.txt found!")
        elif len(summary) > 1:
            raise RuntimeError("Multiple ALOS products detected, more than one summary.txt found!")

        summary = parse_product_summary(summary[0].read_text())
        processing_level = summary["Lbi_ProcessLevel"]

        if "1.0" in processing_level:
            processing_level = 0
        elif "1.1" in processing_level:
            processing_level = 1
        else:
            raise RuntimeError(f"Unsupported ALOS 'Lbi_ProcessLevel': {processing_level}")

        # Inentify ALOS 1 or 2... (this function supports both as they share logic)
        alos1_acquisitions = list(raw_data_path.glob("*/IMG-*-ALP*"))
        alos2_acquisitions = list(raw_data_path.glob("*/IMG-*-ALOS*"))

        if not alos1_acquisitions and not alos2_acquisitions:
            raise FileNotFoundError("Provided product does not contain any ALOS data")

        if alos1_acquisitions and alos2_acquisitions:
            raise Exception("Unsupported ALOS product, has a mix of both PALSAR 1 and 2 products")

        # Identify polarisations
        acquisitions = alos1_acquisitions or alos2_acquisitions

        # We assume if multiple polarised products exist in a single acquisition they share geospatial traits
        # so we just get the scene info for the first acquisition
        raw_file = acquisitions[0]
        # raw_file.name = "IMG-??-....", LED files are identical but "LED" instead of "IMG-??"
        led_file = raw_file.parent / f"LED{raw_file.name[6:]}"

        pols = set(i.name[4:6] for i in acquisitions)
        date = datetime.strptime(match.group("product_date"), const.SCENE_DATE_FMT)

        # Parse CEOS headers to get scene center and pixel spacing
        # and use this to get a VERY crude estimate of scene extent
        if processing_level == 0:
            sar_par_path = temp_dir / "sar.par"
            proc_par_path = temp_dir / "proc.par"

            pg.PALSAR_proc(
                led_file,
                sar_par_path,
                proc_par_path,
                raw_file,
                const.NOT_PROVIDED,
                const.NOT_PROVIDED,
                const.NOT_PROVIDED
            )

            #sar_par = ParFile(sar_par_path)
            proc_par = ParFile(proc_par_path)

            scene_lat = proc_par.get_value("scene_center_latitude", dtype=float, index=0)
            scene_lon = proc_par.get_value("scene_center_longitude", dtype=float, index=0)

        elif processing_level == 1:
            slc_par_path = temp_dir / "slc.par"

            pg.par_EORC_PALSAR(
                led_file,
                slc_par_path,
                raw_file,
                const.NOT_PROVIDED
            )

            # Parse SLC par
            slc_par = ParFile(slc_par_path)

            scene_lat = slc_par.get_value("center_latitude", dtype=float, index=0)
            scene_lon = slc_par.get_value("center_longitude", dtype=float, index=0)

        else:
            raise RuntimeError(f"Unsupported ALOS processing level: {processing_level}")

        scene_center = (scene_lon, scene_lat)

        # Note: This is a super over-exaggeration - but... in reality we only need a
        # minimum extent, so over-exaggerating is safer than under-estimating.
        #
        # This is ultimately used for two things, 1) extract a ROI out of the master DEM
        # image (which is too large to use for processing) and 2) include/exclude scenes
        # for geospatial queries (PALSAR has no geospatial query DB support)
        #
        # This would need to be fixed if we ever decide to support PALSAR scenes in the
        # geospatial database querying feature (no such plans though for now).
        scene_size = (10.0, 10.0)

        scene_radius = (scene_size[0] / 2.0, scene_size[1] / 2.0)

        swath_extent = (
            (scene_center[0] - scene_radius[0], scene_center[1] - scene_radius[1]),
            (scene_center[0] + scene_radius[0], scene_center[1] + scene_radius[1])
        )

    # JAXA ALOS data only has a single frame, which we return as a single "swath"
    # for each polarisation
    swath_template = {
        "date": date.date(),
        "swath_extent": swath_extent,
        "sensor": METADATA.constellation_members[0],
        "url": str(data_path),
        # "polarization": "This is filled in below",
        "acquisition_datetime": date,
        # N/A - PALSAR has no subswaths nor bursts
        "swath": "N/A",
        "burst_number": [0],
        "total_bursts": "1",
        "missing_primary_bursts": [],
    }

    result = []

    for pol in pols:
        pol_swath = swath_template.copy()
        pol_swath["polarization"] = pol

        result.append(pol_swath)

    return result



def acquire_source_data(source_path: str, dst_dir: Path, pols: Optional[List[str]] = None, **kwargs):
    # Note: We intentionally ignore `pols` filtering, as the interpretation of HH data can depend on the
    # existence of HV data (thus we have to extract the HV even if we only care about HH to determine this)

    # We only support local paths currently
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError("The source data path does not exist!")

    # The end result is a subdir in dst_dir identical to source_path (including it's name)
    # - a.k.a. `cp -r source_path dst_dir/source_path`
    if source_path.is_dir():
        shutil.copytree(source_path, dst_dir / source_path.stem, dirs_exist_ok=True)

        return dst_dir / source_path.stem

    # This extracts the contents of the archive directly into dst_dir, JAXA ALOS
    # products contain a {scene_date}/... top level directory, thus we should end up
    # with a dst_dir/{scene_date} dir of the archive contents.
    elif source_path.name.endswith(".tar.gz"):
        with tarfile.open(source_path) as archive:
            archive.extractall(dst_dir)

            return dst_dir / os.path.commonpath(i.name for i in archive.getmembers())

    else:
        raise RuntimeError(f"Unsupported source data path: {source_path}")
