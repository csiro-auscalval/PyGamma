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

# generic Gamma interface
COUT = "cout"
CERR = "cerr"

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

ESTIMATION_WINDOW_RECTANGULAR = 0  # default
ESTIMATION_WINDOW_TRIANGULAR = 1
ESTIMATION_WINDOW_GAUSSIAN = 2
ESTIMATION_WINDOW_NORMALIZED_VECTOR = 3

RASCC_MASK_DEFAULT_COHERENCE_STARTING_LINE = 1
RASCC_MASK_DEFAULT_INTENSITY_STARTING_LINE = 1
RASCC_TO_EOF = 0
N_PIXELS_DEFAULT_RANGE_AVERAGE = 1
N_PIXELS_DEFAULT_AZIMUTH_AVERAGE = 1
RASCC_DEFAULT_INTENSITY_THRESHOLD = 0

RASCC_THINNING_THRESHOLD = 4

LEFT_RIGHT_FLIPPING_NORMAL = 1
LEFT_RIGHT_FLIPPING_MIRROR = -1

INT_MODE_SINGLE_PASS = 0
INT_MODE_REPEAT_PASS = 1

PHASE_OFFSET_MODE_ABSOLUTE = 0
PHASE_OFFSET_MODE_SUBTRACT_PHASE = 1

RANGE_SPECTRAL_SHIFT_FLAG_APPLY_FILTER = 1
RANGE_SPECTRAL_SHIFT_FLAG_NO_FILTER = 0
AZIMUTH_COMMON_BAND_APPLY_FILTER = 1
AZIMUTH_COMMON_BAND_NO_FILTER = 0

DEFAULT_MINIMUM_RANGE_BANDWIDTH_FRACTION = 0.25

SLC_1_RANGE_PHASE_MODE_NEAREST = 0  # aka 'rp1_flag' arg
SLC_1_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE = 1
SLC_2_RANGE_PHASE_MODE_NEAREST = 0  # aka 'rp2_flag' arg
SLC_2_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE = 1

NUM_RANGE_LOOKS = 10
NUM_AZIMUTH_LOOKS = 10

BX = 7
BY = 7

MASKING_COHERENCE_THRESHOLD = 0.7

RANGE_LOOKS_MAGNIFICATION = -10
AZIMUTH_LOOKS_MAGNIFICATION = -10

NUM_GCP_POINTS_RANGE = 100
NUM_GCP_POINTS_AZIMUTH = 100

GCP_PHASE_WINDOW_SIZE = 3

TRIANGULATION_MODE_FILLED_TRIANGULAR_MESH = 0
TRIANGULATION_MODE_DELAUNAY = 1

INIT_FLAG_INIT_POINT_PHASE_VALUE = 0  # the default
INIT_FLAG_SET_PHASE_0_AT_INITIAL = 1  # set phase to 0.0 at initial point

BASE_INIT_METHOD_4 = 4

BASE_ADD_MODE_ADD = 1
BASE_ADD_MODE_SUBTRACT = -1

NUM_RANGE_PATCHES = 1
NUM_AZIMUTH_PATCHES = 1

SUB_PHASE_SUBTRACT_MODE = 0
SUB_PHASE_ADD_PHASE_MODE = 1


# Phase sim constants
PH_FLAG_SIMULATED_UNFLATTENED_INTERFEROGRAM = 0
PH_FLAG_SIMULATED_FLATTENED_INTERFEROGRAM = 1
B_FLAG_INIT_BASELINE = 0
B_FLAG_PRECISION_BASELINE = 1
PH_MODE_ABSOLUTE_PHASE = 0
PH_MODE_SUBTRACT_PHASE_OFFSET = 1

# interp_ad weighting mode:
# 0:constant
# 1: 1-(r/r_max)   default(-): 1-(r/r_max)
# 2: 1-(r/r_max)**2
# 3: exp(-2.*SQR(r/r_max))
# TODO: get good names for these from InSAR team
WEIGHTING_MODE_CONSTANT = 0
WEIGHTING_MODE_1 = 1
WEIGHTING_MODE_2 = 2
WEIGHTING_MODE_3 = 3

MAX_INTERP_WINDOW_RADIUS = 32
NPOINTS_MIN_FOR_INTERP = 8
NPOINT_MAX_FOR_INTERP = 16

# UNW model constants
REF_POINT_PHASE = 0.0

# Geocoding constants
# interpolation mode (enter - for default)
INTERPOLATION_MODE_NEAREST_NEIGHBOR = 0
INTERPOLATION_MODE_BICUBIC_SPLINE = 1  # (default)
INTERPOLATION_MODE_BICUBIC_SPLINE_INTERP_LOG = 2  # bicubic-spline, interpolate log(data)
INTERPOLATION_MODE_BICUBIC_SPLINE_INTERP_SQRT = (
    3  # bicubic-spline, interpolate sqrt(data)
)
#   4: B-spline interpolation (default B-spline degree: 5)
#   5: B-spline interpolation sqrt(x) (default B-spline degree: 5)
#   6: Lanczos interpolation (default Lanczos function order: 5)
#   7: Lanczos interpolation sqrt(x) (default Lanczos function order: 5)

# Data types
DTYPE_FLOAT = 0  # (default)
DTYPE_FCOMPLEX = 1
#    2: SUN raster/BMP/TIFF format
DTYPE_UNSIGNED_CHAR = 3
DTYPE_SHORT = 4
DTYPE_DOUBLE = 5

# GEOCODE constants
DEFAULT_STARTING_LINE = 1
DISPLAY_TO_EOF = 0

DTYPE_GEOTIFF_FLOAT = 2

# file patterns to delete after geocoding step
TEMP_FILE_GLOBS = [
    "*flat0*",
    "*flat1*",
    "*sim0*",
    "*sim1*",
    "*int1*",
    "*.ras",
    "*.unw",
    "*eqa.int",
    "*filt.int",
    "*.cc",
]


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
