"""
Constants
---------
"""

from pathlib import Path
from typing import List, Tuple
from enum import Enum

SAFE_FMT : str = "{s}.SAFE"
S1_SOURCE_DIR_FMT : str = "{y}/{y}-{m}/{g}/{f}"
DATE_FMT : str = "*{dt}*"
SCENE_DATE_FMT : str = "%Y%m%d"
COREG_JOB_FILE_FMT : str = "{primary}_{secondary}.bash"
COREG_JOB_ERROR_FILE_FMT : str = "{primary}_{secondary}.error"

# generic Gamma interface
COUT : str = "cout"
CERR : str = "cerr"

# constants for process_ifg
YES : str = "yes"
NO : str = "no"

OFFSET_ESTIMATION_INTENSITY_CROSS_CORRELATION : int = 1
OFFSET_ESTIMATION_FRINGE_VISIBILITY : int = 2

OFFSET_PWR_OVERSAMPLING_FACTOR : int = 2

BASE_LS_DERIVE_FROM_ORBIT : int = 0
BASE_LS_ESTIMATE_FROM_DATA : int = 1

RANGE_PATCH_SIZE : int = 64
AZIMUTH_PATCH_SIZE : int = 64
NUM_OFFSET_ESTIMATES_RANGE : int = 64
NUM_OFFSET_ESTIMATES_AZIMUTH : int = 256
CROSS_CORRELATION_THRESHOLD : float = 0.1

NON_INTERACTIVE : int = 0
NOT_PROVIDED = None

DIFF_PAR_OFFSET : int = 0  # ISP offset and interferogram parameters
DIFF_PAR_SLC_MLI : int = 1  # ISP SLC/MLI parameters (default)
DIFF_PAR_DEM : int = 2

ESTIMATION_WINDOW_RECTANGULAR : int = 0  # default
ESTIMATION_WINDOW_TRIANGULAR : int = 1
ESTIMATION_WINDOW_GAUSSIAN : int = 2
ESTIMATION_WINDOW_NORMALIZED_VECTOR : int = 3

# rasrmg & rascc constants
RASCC_MASK_DEFAULT_COHERENCE_STARTING_LINE : int = 1
RASCC_MASK_DEFAULT_INTENSITY_STARTING_LINE : int = 1
RASCC_TO_EOF : int = 0
N_PIXELS_DEFAULT_RANGE_AVERAGE : int = 1
N_PIXELS_DEFAULT_AZIMUTH_AVERAGE : int = 1
RASCC_DEFAULT_INTENSITY_THRESHOLD : int = 0

RASCC_MIN_THINNING_THRESHOLD : int = 1
RASCC_THINNING_THRESHOLD : int = 4
RASCC_THRESHOLD_INCREMENT : float = 0.2

RASCC_MIN_CORRELATION : int = 0
RASCC_MAX_CORRELATION : int = 1

# Parameters for `rasSLC` when generating quicklook bmp/png's
RAS_PIXEL_AVERAGE_RANGE : int = 20 # resampling
RAS_PIXEL_AVERAGE_AZIMUTH : int = 20 # resampling
RAS_PH_SCALE : int = 1
RAS_SCALE : int = 1
RAS_EXP : float = 0.35
RAS_PH_OFFSET : int = 0

LEFT_RIGHT_FLIPPING_NORMAL : int = 1
LEFT_RIGHT_FLIPPING_MIRROR : int = -1

INT_MODE_SINGLE_PASS : int = 0
INT_MODE_REPEAT_PASS : int = 1

PHASE_OFFSET_MODE_ABSOLUTE : int = 0
PHASE_OFFSET_MODE_SUBTRACT_PHASE : int = 1

RANGE_SPECTRAL_SHIFT_FLAG_APPLY_FILTER : int = 1
RANGE_SPECTRAL_SHIFT_FLAG_NO_FILTER : int = 0
AZIMUTH_COMMON_BAND_APPLY_FILTER : int = 1
AZIMUTH_COMMON_BAND_NO_FILTER : int = 0

DEFAULT_MINIMUM_RANGE_BANDWIDTH_FRACTION : int = 0.25

SLC_1_RANGE_PHASE_MODE_NEAREST : int = 0  # aka 'rp1_flag' arg
SLC_1_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE : int = 1
SLC_2_RANGE_PHASE_MODE_NEAREST : int = 0  # aka 'rp2_flag' arg
SLC_2_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE : int = 1

NUM_RANGE_LOOKS : int = 10
NUM_AZIMUTH_LOOKS : int = 10

BX : int = 7
BY : int = 7

MASKING_COHERENCE_THRESHOLD : float = 0.7

RANGE_LOOKS_MAGNIFICATION : int = -10
AZIMUTH_LOOKS_MAGNIFICATION : int = -10

NUM_GCP_POINTS_RANGE : int = 100
NUM_GCP_POINTS_AZIMUTH : int = 100

GCP_PHASE_WINDOW_SIZE : int = 3

TRIANGULATION_MODE_FILLED_TRIANGULAR_MESH : int = 0
TRIANGULATION_MODE_DELAUNAY : int = 1

INIT_FLAG_INIT_POINT_PHASE_VALUE : int = 0  # the default
INIT_FLAG_SET_PHASE_0_AT_INITIAL : int = 1  # set phase to 0.0 at initial point

BASE_INIT_METHOD_4 : int = 4

BASE_ADD_MODE_ADD : int = 1
BASE_ADD_MODE_SUBTRACT : int = -1

NUM_RANGE_PATCHES : int = 1
NUM_AZIMUTH_PATCHES : int = 1

SUB_PHASE_SUBTRACT_MODE : int = 0
SUB_PHASE_ADD_PHASE_MODE : int = 1


# Phase sim constants
PH_FLAG_SIMULATED_UNFLATTENED_INTERFEROGRAM : int = 0
PH_FLAG_SIMULATED_FLATTENED_INTERFEROGRAM : int = 1
B_FLAG_INIT_BASELINE : int = 0
B_FLAG_PRECISION_BASELINE : int = 1
PH_MODE_ABSOLUTE_PHASE : int = 0
PH_MODE_SUBTRACT_PHASE_OFFSET : int = 1

# interp_ad weighting mode:
# 0:constant
# 1: 1-(r/r_max)   default(-): 1-(r/r_max)
# 2: 1-(r/r_max)**2
# 3: exp(-2.*SQR(r/r_max))
# TODO: get good names for these from InSAR team
WEIGHTING_MODE_CONSTANT : int = 0
WEIGHTING_MODE_1 : int = 1
WEIGHTING_MODE_2 : int = 2
WEIGHTING_MODE_3 : int = 3

MAX_INTERP_WINDOW_RADIUS : int = 32
NPOINTS_MIN_FOR_INTERP : int = 8
NPOINT_MAX_FOR_INTERP : int = 16

# UNW model constants
REF_POINT_PHASE : float = 0.0

# Geocoding constants
# interpolation mode (enter - for default)
INTERPOLATION_MODE_NEAREST_NEIGHBOR : int = 0
INTERPOLATION_MODE_BICUBIC_SPLINE : int = 1  # (default)
INTERPOLATION_MODE_BICUBIC_SPLINE_INTERP_LOG : int = 2  # bicubic-spline, interpolate log(data)
INTERPOLATION_MODE_BICUBIC_SPLINE_INTERP_SQRT : int = 3 # bicubic-spline, interpolate sqrt(data)

#   4: B-spline interpolation (default B-spline degree: 5)
#   5: B-spline interpolation sqrt(x) (default B-spline degree: 5)
#   6: Lanczos interpolation (default Lanczos function order: 5)
#   7: Lanczos interpolation sqrt(x) (default Lanczos function order: 5)

CPX_TO_REAL_OUTPUT_TYPE_PHASE : int = 4

RAS2RAS_GREY_COLOUR_MAP : Path = Path("gray.cm")

# Data types NOTE: these are NOT consistent between pygamma programs!
DTYPE_FLOAT : int = 0  # (default)
DTYPE_FCOMPLEX : int = 1
#    2: SUN raster/BMP/TIFF format
DTYPE_UNSIGNED_CHAR : int = 3
DTYPE_SHORT : int = 4
DTYPE_DOUBLE : int = 5

SLC_DTYPE_FCOMPLEX : int = 0
SLC_DTYPE_SCOMPLEX : int = 1


# GEOCODE constants
DEFAULT_STARTING_LINE : int = 1
DISPLAY_TO_EOF : int = 0

DTYPE_GEOTIFF_FLOAT : int = 2
DTYPE_GEOTIFF_SCOMPLEX : int = 3

# file patterns to delete after geocoding step
TEMP_FILE_GLOBS : List[str] = [
    "*flat0*",
    "*flat1*",
    "*sim0*",
    "*sim1*",
    "*int1*",
]


INIT_OFFSETM_CORRELATION_PATCH_SIZES : Tuple[int, int, int, int] = (128, 256, 512, 1024)
MIN_DEM_WIN_AXIS : int = 8


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
    GEO_UNW_TYPE = "*geo.unw"
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


# TODO: review why this is an enum vs raw constants
class MatchStrings(Enum):
    """
    Defines the string (or characters) which are used in finding
    characters with specific match in a file
    """

    # slc directory
    SLC_RANGE_SAMPLES = "range_samples"
    SLC_AZIMUTH_LINES = "azimuth_lines"

    # ifg directory
    IFG_AZIMUTH_LINES = "interferogram_azimuth_lines:"

    # identifies with parameter name in GAMMA & keeps terminology in reference to radar geometry
    IFG_RANGE_SAMPLES = "interferogram_width:"

    # dem directory
    DEM_USAGE_NOTE = "USAGE NOTE:"
    DEM_SCENE_TITLE = "scene title:"
    DEM_WARNING = "WARNING:"
    DEM_ISP = "Using ISP SLC/MLI"


# Other match strings

# DEM diff file
RANGE_SAMPLE_1 : str = "range_samp_1:"

# DEM GEO param file
DEM_GEO_WIDTH : str = "width:"


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


DISCARD_TEMP_FILES : bool = False

# These used to be hardcoded to 8 and 2 in process_s1_slc.py for
# SLC_mosaic_S1_TOPS call. This is a test to see if those can be
# changed to obtain higher-resolution products
# These parameters are used to determine burst data window in SLC_mosaic_ScanSAR

SLC_MOSAIC_RANGE_LOOKS : int = 1
SLC_MOSAIC_AZIMUTH_LOOKS : int = 1

# This used to be hardcoded in proc config reader, it specifies where the DEM
# files will be created.

GAMMA_DEM_DIR : Path = Path("DEM")

# The DEM oversampling rate that is used in `gc_map2`.

DEM_OVERSAMPLE_RATE : int = 1

# The DEM oversampling performed on GeoTiff

DEM_GEOTIFF_OVERSAMPLE_RATE : int = 2
