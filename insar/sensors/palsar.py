from pathlib import Path
from datetime import datetime
from typing import List, Optional
import re
import tarfile
import shutil
import tempfile
import structlog
import os.path

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper

from insar.sensors.types import SensorMetadata
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

_LOG = structlog.get_logger("insar")
pg = GammaInterface(
    subprocess_func=auto_logging_decorator(subprocess_wrapper, Exception, _LOG)
)

def get_data_swath_info(
    data_path: Path,
    raw_data_path: Optional[Path]
):
    match = re.match(ANY_DATA_PATTERN, data_path.name)
    if not match:
        raise RuntimeError("Invalid data path, does not match an ALOS PALSAR data path")

    if not raw_data_path or not raw_data_path.is_dir():
        raise RuntimeError("Cannot get swath info from ALOS archive, only from directory")

    with tempfile.TemporaryDirectory() as temp_dir:
        # Inentify ALOS 1 or 2... (this function supports both as they share logic)
        alos1_acquisitions = list(raw_data_path.glob("*/IMG-*-ALP*"))
        alos2_acquisitions = list(raw_data_path.glob("*/IMG-*-ALOS*"))

        if not alos1_acquisitions and not alos2_acquisitions:
            raise Exception(f"Provided product does not contain any ALOS data")

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
        if alos1_acquisitions:
            sar_par_path = "sar.par"
            proc_par_path = "proc.par"

            pg.PALSAR_proc(
                led_file,
                sar_par_path,
                proc_par_path,
                raw_file,
                const.NOT_PROVIDED,
                const.NOT_PROVIDED,
                const.NOT_PROVIDED
            )

            #sar_par = pg.ParFile(sar_par_path)
            proc_par = pg.ParFile(proc_par_path)

            scene_lat = proc_par.get_value("scene_center_latitude", dtype=float, index=0)
            scene_lon = proc_par.get_value("scene_center_longitude", dtype=float, index=0)

        else:
            slc_par_path = "slc.par"

            pg.par_EORC_PALSAR(
                led_file,
                slc_par_path,
                raw_file,
                const.NOT_PROVIDED
            )

            # Parse SLC par
            slc_par = pg.ParFile(slc_par_path)

            scene_lat = slc_par.get_value("center_latitude", dtype=float, index=0)
            scene_lon = slc_par.get_value("center_longitude", dtype=float, index=0)

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
    # We only support local paths currently
    source_path = Path(source_path)
    if not source_path.exists():
        raise FileNotFoundError("The source data path does not exist!")

    # The end result is a subdir in dst_dir identical to source_path (including it's name)
    # - a.k.a. `cp -r source_path dst_dir/source_path`
    if source_path.is_dir():
        def ignore_filter(dir, names):
            included_imagery = [f"imagery_{p}" for p in pols]
            return [i for i in names if "imagery" in i and Path(i).stem not in included_imagery]

        if pols:
            shutil.copytree(source_path, dst_dir / source_path.stem, ignore=ignore_filter)
        else:
            shutil.copytree(source_path, dst_dir / source_path.stem)

        return dst_dir / source_path.stem

    # This extracts the contents of the archive directly into dst_dir, JAXA ALOS
    # products contain a {scene_date}/... top level directory, thus we should end up
    # with a dst_dir/{scene_date} dir of the archive contents.
    elif source_path.name.endswith(".tar.gz"):
        with tarfile.open(source_path) as archive:
            filtered_list = None

            # Only extract imagery for pols we care about
            if pols:
                filtered_list = archive.getmembers()
                included_imagery = [f"IMG-{p}" for p in pols]
                filtered_list = [i for i in filtered_list if "IMG-" not in i.name or Path(i.name).name[:6] in included_imagery]

            archive.extractall(dst_dir, filtered_list)

            return dst_dir / os.path.commonpath(i.name for i in archive.getmembers())

    else:
        raise RuntimeError(f"Unsupported source data path: {source_path}")
