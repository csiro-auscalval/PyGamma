"""
Constants
---------
"""

from __future__ import absolute_import, print_function
from enum import Enum


SAFE_FMT = "{s}.SAFE"
S1_SOURCE_DIR_FMT = "{y}/{y}-{m}/{g}/{f}"
DATE_FMT = "*{dt}*"
SCENE_DATE_FMT = "%Y%m%d"
COREG_JOB_FILE_FMT = "{master}_{slave}.bash"
COREG_JOB_ERROR_FILE_FMT = "{master}_{slave}.error"

# constants for process_ifg
OFFSET_ESTIMATION_INTENSITY_CROSS_CORRELATION = 1
OFFSET_ESTIMATION_FRINGE_VISIBILITY = 2

RANGE_PATCH_SIZE = 64
AZIMUTH_PATCH_SIZE = 64
NUM_OFFSET_ESTIMATES_RANGE = 64
NUM_OFFSET_ESTIMATES_AZIMUTH = 256
CROSS_CORRELATION_THRESHOLD = 0.1

NON_INTERACTIVE = 0
NOT_PROVIDED = "-"

DIFF_PAR_OFFSET = 0  # ISP offset and interferogram parameters
DIFF_PAR_SLC_MLI = 1  # ISP SLC/MLI parameters (default)
DIFF_PAR_DEM = 2


class SlcFilenames(Enum):
    """SLC filenames """

    SLC_FILENAME = "{}_{}.slc"
    SLC_PAR_FILENAME = "{}_{}.slc.par"
    SLC_TOPS_PAR_FILENAME = "{}_{}.slc.TOPS_par"
    SLC_TAB_FILENAME = "{}_{}_tab"

    SLC_IW_FILENAME = "{}_{}_iw{}.slc"
    SLC_IW_PAR_FILENAME = "{}_{}_iw{}.slc.par"
    SLC_IW_TOPS_PAR_FILENAME = "{}_{}_iw{}.slc.TOPS_par"


class MliFilenames(Enum):
    """ MLI filenames """

    MLI_FILENAME = "{scene_date}_{pol}_{rlks}rlks.mli"
    MLI_PAR_FILENAME = "{scene_date}_{pol}_{rlks}rlks.mli.par"


class Wildcards(Enum):
    """
    Defines the wildcard patterns which are used in finding files with
    specific pattern match
    """

    # slc directory
    SCENE_CONNECTION_TYPE = "*-*"
    RADAR_CODED_TYPE = "r*"
    SWATH_TYPE = "*IW*"
    SLC_ERROR_LOG_TYPE = "error.log"
    RADAR_CODED_MLI_TYPE = "r*.mli"
    RADAR_CODED_MLI_PAR_TYPE = "r*.mli.par"
    MLI_PAR_TYPE = "*.mli.par"
    MLI_TYPE = "*.mli"
    GAMMA0_TYPE = "*gamma0*"
    SIGMA0_TYPE = "*sigma0*"
    # ifg directory
    FLT_TYPE = "*.flt"
    MODEL_UNW_TYPE = "*_model.unw"
    SIM_UNW_TYPE = "*_sim.unw"
    THIN_UNW_TYPE = "*_thin.unw"
    EQA_UNW_TYPE = "*eqa.unw"
    INT_FLAT_TYPE = "*_flat.int"
    OFF_PAR_TYPE = "*off.par"

    # gamma dem directory
    TRACK_DEM_TYPE = "{track_frame}.dem"
    TRACK_DEM_PAR_TYPE = "{track_frame}.dem.par"
    TRACK_DEM_PNG_TYPE = "*.png"
    # dem directory
    CCP_TYPE = "*.ccp"
    SIM_TYPE = "*.sim"
    PIX_TYPE = "*_pix*"
    RDC_TYPE = "*_rdc*"
    RDC_SIM_TYPE = "*_rdc.sim"
    DEM_ERROR_LOG_TYPE = "error.log"

    # raw data directory
    TIFF_TYPE = "*.tiff"
    ALL_TYPE = "*"
    POL_TYPE = ""


class FolderNames(Enum):
    """
    Defines the name of folders used throughout the insar processing workflow
    """

    # raw data directpry
    MEASUREMENT = "measurement"
    ANNOTATION = "annotation"
    CALIBRATION = "calibration"
    PREVIEW = "preview"


class MatchStrings(Enum):
    """
    Defines the string (or characters) which are used in finding
    characters with specific match in a file
    """

    # slc directory
    SLC_RANGE_SAMPLES = "range_samples"
    SLC_AZIMUTH_LINES = "azimuth_lines"

    # ifg directory
    IFG_RANGE_SAMPLES = "interferogram_azimuth_lines:"
    IFG_AZIMUTH_LINES = "interferogram_width:"

    # dem directory
    DEM_USAGE_NOTE = "USAGE NOTE:"
    DEM_SCENE_TITLE = "scene title:"
    DEM_WARNING = "WARNING:"
    DEM_ISP = "Using ISP SLC/MLI"


class ErrorMessages(Enum):
    """
    Defines the error messages
    """

    # raw Data file size error
    RAW_FILE_SIZE_ERROR_MSGS = (
        "{f}: File size is {s}B at the source and {d}B at the destination}"
    )

    # error log file size
    ERROR_LOG_MSGS = "{f}: File size is {s}B, the expected file size is {d}B"

    # multi-look file size error
    MLI_FILE_SIZE_ERROR_MSGS = (
        "{f}: File size {s}B, the expected file size is greater than {s}B"
    )

    # error log content
    ERROR_CONTENT_MSGS = "{f}: contains following errors: {s}"
