import io
from insar import project

from unittest.mock import Mock
import pytest


def test_create_config():
    config = project.Config()
    assert config.proc_variables is None
    assert config.final_file_loc is None
    assert config.dem_master_names is None
    assert config.dem_file_names is None
    assert config.ifg_file_names is None


# tests for ProcConfig
def test_read_proc_file():
    file_obj = io.StringIO(FULL_PROC_VARIABLES_FILE)
    assert file_obj.closed is False

    pv = project.ProcConfig.from_file(file_obj)
    assert pv.nci_path == "<user-defined>"
    assert pv.slc_dir == "SLC"
    assert pv.ifg_list == "ifgs.list"
    assert pv.master_dem_image

    # check secondary variables derived from the proc file
    assert pv.dem_img == "{}/GAMMA_DEM_SRTM_1as_mosaic.img".format(pv.master_dem_image)
    assert pv.proj_dir == "{}/{}/{}/GAMMA".format(pv.nci_path, pv.project, pv.sensor)
    assert pv.raw_data_track_dir == "{}/{}".format(pv.raw_data_dir, pv.track)
    assert pv.gamma_dem_dir == "{}/gamma_dem".format(pv.proj_dir)
    assert pv.results_dir == "{}/{}/results".format(pv.proj_dir, pv.track)
    assert pv.dem_noff1 == '0'
    assert pv.dem_noff2 == '0'
    assert pv.ifg_rpos == pv.dem_rpos
    assert pv.ifg_azpos == pv.dem_azpos


def test_read_incomplete_proc_file_fails():
    """Ensure partial proc files can still be read."""
    file_obj = io.StringIO(FULL_PROC_VARIABLES_FILE[:207])

    with pytest.raises(AttributeError):
        project.ProcConfig.from_file(file_obj)


def test_read_unknown_settings():
    """Fail fast if unrecognised settings are found"""
    content = "FAKE_SETTING=foo\n"
    file_obj = io.StringIO(content)

    with pytest.raises(AttributeError):
        project.ProcConfig.from_file(file_obj)


# tests for the PBS job dirs section
BATCH_BASE = 'tmp/pbs'
MANUAL_BASE = 'tmp/manual'


@pytest.fixture
def mock_proc():
    mproc = Mock()
    mproc.batch_job_dir = BATCH_BASE
    mproc.manual_job_dir = MANUAL_BASE
    return mproc


def test_pbs_job_dirs(mock_proc):
    pbs_dirs = project.get_default_pbs_job_dirs(mock_proc)
    assert len([x for x in dir(pbs_dirs) if x.endswith('_dir')]) == 14

    # check subset of batch vars
    assert pbs_dirs.extract_raw_batch_dir == BATCH_BASE + "/extract_raw_jobs"
    assert pbs_dirs.dem_batch_dir == BATCH_BASE + "/dem_jobs"
    assert pbs_dirs.ifg_batch_dir == BATCH_BASE + "/ifg_jobs"

    # check subset of manual vars
    assert pbs_dirs.extract_raw_manual_dir == MANUAL_BASE + '/extract_raw_jobs'
    assert pbs_dirs.base_manual_dir == MANUAL_BASE + '/baseline_jobs'
    assert pbs_dirs.ifg_manual_dir == MANUAL_BASE + '/ifg_jobs'


def test_pbs_job_dirs_none_setting(mock_proc):
    """Ensure failure if the proc settings aren't initialised properly"""
    mock_proc.batch_job_dir = None

    with pytest.raises(Exception):
        project.get_default_pbs_job_dirs(mock_proc)


def test_sentinel1_pbs_job_dirs(mock_proc):
    s1_pbs_dirs = project.get_default_sentinel1_pbs_job_dirs(mock_proc)
    assert s1_pbs_dirs.resize_batch_dir == BATCH_BASE + "/resize_S1_slc_jobs"
    assert s1_pbs_dirs.resize_manual_dir == MANUAL_BASE + "/resize_S1_slc_jobs"
    assert s1_pbs_dirs.subset_batch_dir == BATCH_BASE + "/subset_S1_slc_jobs"
    assert s1_pbs_dirs.subset_manual_dir == MANUAL_BASE + "/subset_S1_slc_jobs"


def test_sentinel1_pbs_job_dirs_none_setting(mock_proc):
    mock_proc.batch_job_dir = None

    with pytest.raises(Exception):
        project.get_default_sentinel1_pbs_job_dirs(mock_proc)


def test_default_dem_master_paths(mock_proc):
    slc_dir = "slc-dir"
    ref_master_scene = "master-scene"
    polarisation = "polarisation"
    range_looks = "range-looks"

    mock_proc.slc_dir = slc_dir
    mock_proc.ref_master_scene = ref_master_scene
    mock_proc.polarisation = polarisation
    mock_proc.range_looks = range_looks

    cfg = project.DEMMasterNames(mock_proc)
    assert len([x for x in dir(cfg) if x.startswith("dem_")]) == 12
    assert len([x for x in dir(cfg) if x.startswith("r_dem_")]) == 7

    assert cfg.dem_master_dir == "{}/{}".format(slc_dir, ref_master_scene)
    assert cfg.dem_master_slc_name == "{}/{}_{}".format(cfg.dem_master_dir, ref_master_scene, polarisation)
    assert cfg.dem_master_slc == cfg.dem_master_slc_name + ".slc"
    assert cfg.dem_master_slc_par == cfg.dem_master_slc + ".par"

    assert cfg.dem_master_mli_name == "{}/{}_{}_{}rlks".format(cfg.dem_master_dir, ref_master_scene,
                                                               polarisation, range_looks)
    assert cfg.dem_master_mli == cfg.dem_master_mli_name + ".mli"
    assert cfg.dem_master_mli_par == cfg.dem_master_mli + ".par"

    assert cfg.dem_master_gamma0 == cfg.dem_master_mli_name + ".gamma0"
    assert cfg.dem_master_gamma0_bmp == cfg.dem_master_gamma0 + ".bmp"
    assert cfg.dem_master_gamma0_eqa == cfg.dem_master_mli_name + "_eqa.gamma0"
    assert cfg.dem_master_gamma0_eqa_bmp == cfg.dem_master_gamma0_eqa + ".bmp"
    assert cfg.dem_master_gamma0_eqa_geo == cfg.dem_master_gamma0_eqa + ".tif"

    assert cfg.r_dem_master_slc_name == "{}/r{}_{}".format(cfg.dem_master_dir, ref_master_scene, polarisation)
    assert cfg.r_dem_master_slc == cfg.r_dem_master_slc_name + ".slc"
    assert cfg.r_dem_master_slc_par == cfg.r_dem_master_slc + ".par"
    assert cfg.r_dem_master_mli_name == "{}/r{}_{}_{}rlks".format(cfg.dem_master_dir, ref_master_scene,
                                                                  polarisation, range_looks)

    assert cfg.r_dem_master_mli == cfg.r_dem_master_mli_name + ".mli"
    assert cfg.r_dem_master_mli_par == cfg.r_dem_master_mli + ".par"
    assert cfg.r_dem_master_mli_bmp == cfg.r_dem_master_mli + ".bmp"


def test_default_dem_master_paths_none_setting(mock_proc):
    """Ensure incomplete proc settings prevent DEM config from being initialised."""
    mock_proc.slc_dir = None

    with pytest.raises(Exception):
        project.DEMMasterNames(mock_proc)


def test_default_dem_file_names(mock_proc):
    mock_proc.gamma_dem_dir = "gamma-dem-dir"
    mock_proc.dem_name = "dem-name"
    mock_proc.dem_dir = "dem-dir"
    mock_proc.ref_master_scene = "ref_master_scene"
    mock_proc.polarisation = "polarisation"
    mock_proc.range_looks = "range_looks"
    mock_proc.results_dir = "results-dir"
    mock_proc.track = "track"

    cfg = project.DEMFileNames(mock_proc)

    assert cfg.dem == "{}/{}.dem".format(mock_proc.gamma_dem_dir, mock_proc.dem_name)
    assert cfg.dem_par == "{}.par".format(cfg.dem)
    assert cfg.dem_master_name == "{}/{}_{}_{}rlks".format(mock_proc.dem_dir,
                                                           mock_proc.ref_master_scene,
                                                           mock_proc.polarisation,
                                                           mock_proc.range_looks)

    assert cfg.dem_diff == "{}/diff_{}_{}_{}rlks.par".format(mock_proc.dem_dir,
                                                             mock_proc.ref_master_scene,
                                                             mock_proc.polarisation,
                                                             mock_proc.range_looks)

    assert cfg.rdc_dem == cfg.dem_master_name + "_rdc.dem"

    # NB: rest of these are only string concatenation, so probably not worth testing!
    dem_master_name = cfg.dem_master_name
    assert cfg.eqa_dem == dem_master_name + "_eqa.dem"
    # assert cfg.eqa_dem_par == eqa_dem.par
    assert cfg.seamask == dem_master_name + "_eqa_seamask.tif"
    assert cfg.dem_lt_rough == dem_master_name + "_rough_eqa_to_rdc.lt"
    assert cfg.dem_lt_fine == dem_master_name + "_eqa_to_rdc.lt"
    assert cfg.dem_eqa_sim_sar == dem_master_name + "_eqa.sim"
    assert cfg.dem_rdc_sim_sar == dem_master_name + "_rdc.sim"
    assert cfg.dem_loc_inc == dem_master_name + "_eqa.linc"
    assert cfg.dem_rdc_inc == dem_master_name + "_rdc.linc"
    assert cfg.dem_lsmap == dem_master_name + "_eqa.lsmap"
    assert cfg.ellip_pix_sigma0 == dem_master_name + "_ellip_pix_sigma0"
    assert cfg.dem_pix_gam == dem_master_name + "_rdc_pix_gamma0"
    # assert cfg.dem_pix_gam_bmp == dem_pix_gam".bmp"
    assert cfg.dem_off == dem_master_name + ".off"
    assert cfg.dem_offs == dem_master_name + ".offs"
    assert cfg.dem_ccp == dem_master_name + ".ccp"
    assert cfg.dem_offsets == dem_master_name + ".offsets"
    assert cfg.dem_coffs == dem_master_name + ".coffs"
    assert cfg.dem_coffsets == dem_master_name + ".coffsets"
    assert cfg.dem_lv_theta == dem_master_name + "_eqa.lv_theta"
    assert cfg.dem_lv_phi == dem_master_name + "_eqa.lv_phi"
    assert cfg.ext_image_flt == dem_master_name + "_ext_img_sar.flt"
    assert cfg.ext_image_init_sar == dem_master_name + "_ext_img_init.sar"
    assert cfg.ext_image_sar == dem_master_name + "_ext_img.sar"

    assert cfg.dem_check_file == "results-dir/track_DEM_coreg_results"
    assert cfg.lat_lon_pix == "dem-dir/track_range_looksrlks_sar_latlon.txt"


FULL_PROC_VARIABLES_FILE = """##### GAMMA CONFIGURATION FILE #####


-----NCI SOFTWARE CONFIGURATION FILE--------------------------------------------------------------------

GAMMA_CONFIG=/g/data/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_CONFIG


-----NCI FILE PATHS-------------------------------------------------------------------------------------

NCI_PATH=<user-defined>
ENVISAT_ORBITS=/g/data/dg9/SAR_ORBITS/ENVISAT
ERS_ORBITS=/g/data/dg9/SAR_ORBITS/ERS_ODR_UPDATED
S1_ORBITS=/g/data/fj7/Copernicus/Sentinel-1
S1_PATH=/g/data/fj7/Copernicus/Sentinel-1/C-SAR/SLC
MASTER_DEM_IMAGE=/g/data/dg9/MASTER_DEM

# NOTE:
# - the total path to the gamma processing directory will be made up of variables from this file.
# - so, NCI_PATH/PROJECT/SENSOR/GAMMA/TRACK
# - the path needs to exist.

-----PROCESSING OUTPUT DIRECTORIES----------------------------------------------------------------------

SLC_DIR=SLC
DEM_DIR=DEM
INT_DIR=INT
BASE_DIR=baselines
LIST_DIR=lists
ERROR_DIR=error_results
PDF_DIR=pdfs
RAW_DATA_DIR=raw_data
BATCH_JOB_DIR=batch_jobs
MANUAL_JOB_DIR=manual_jobs
PRE_PROC_DIR=pre_proc_files


-----INPUT TEXT FILES-----------------------------------------------------------------------------------

SCENE_LIST=scenes.list
SLAVE_LIST=slaves.list
IFG_LIST=ifgs.list
FRAME_LIST=frame.list
S1_BURST_LIST=subset_burst.list
S1_DOWNLOAD_LIST=s1_download.list
    # list for removing scene/s from lists (ie. for SLCs that don't work)
REMOVE_SCENE_LIST=remove_scenes.list


-----PROJECT DIRECTORY & TRACK--------------------------------------------------------------------------

PROJECT=<project>
TRACK=T<track_num><A/D>


-----RAW DATA & DEM LOCATION ON MDSS--------------------------------------------------------------------

    # Sentinel-1 - if AOI within Australia, GAMMA DEM will be produced automatically.
                 - if AOI elsewhere,a  manual GAMMA DEM will need to first be created and MDSS_DEM_tar
                   details required.
                 - data downloaded directly from S1_PATH and S1_ORBITS.

    # Options: aust (within Australia) or other (outside Australia)
DEM_AREA=aust
    # if using DEM from MDSS, enter file name (exc. tar.gz). If auto generated, enter track name
DEM_NAME=<name>
MDSS_DATA_DIR=insar/<sensor>/<project>/<track>
MDSS_DEM_TAR=insar/DEM/<project>/<tar_name>.tar.gz
    # Name of external image used for DEM coregistration (if required, eg. very flat terrain)
EXT_IMAGE=


-----SENSOR DETAILS-------------------------------------------------------------------------------------

    # Polarisation options:
        # ASAR: VV
        # CSK: HH, VV
        # ERS: VV
        # PALSAR1/2: HH, VV, HV, VH (generally HH)
        # RSAT2: HH, VV
        # S1: HH, VV, HV, VH (generally VV)
POLARISATION=<polarisation>
    # Options: ASAR, CSK, ERS, JERS1, PALSAR1, PALSAR2, RSAT1, RSAT2, S1, TSX
SENSOR=<sensor>
    # Sensor mode options:
        # ASAR: I4 or - for other image modes
        # CSK: HI or SP (HIMAGE or Spotlight)
        # PALSAR2: WD or SM (Wide-swath/Stripmap)
        # RSAT2: W or MF (Wide/Multi-look Fine)
        # S1: IWS or SM (Interferometic Wide Swath/Stripmap)
SENSOR_MODE=<mode>
    # If ERS, specify which one (ERS1 or ERS2)
ERS_SENSOR=
    # If PALSAR2, specify which raw data level (raw or slc)
PALSAR2_TYPE=


-----MULTI-LOOK VALUES----------------------------------------------------------------------------------

    # For full resolution (with square pixels), set to 1
MULTI-LOOK=<looks>
    # Leave as 'auto' if not pre-selecting, it will then be auto calculated and updated
RANGE_LOOKS=auto
AZIMUTH_LOOKS=auto


-----INTERFEROGRAM PROCESSING METHOD--------------------------------------------------------------------

    # Options: chain (use daisy-chain), sbas (use reference master) or single (use single master)
PROCESS_METHOD=<method>
    # Leave as 'auto' if not pre-selecting a scene, it will then be calculated and updated
REF_MASTER_SCENE=auto
    # thresholds for minimum and maximum number of SBAS connections
MIN_CONNECT=4
    # default is 7 for S1, 10 for other sensors (e.g. RSAT2)
MAX_CONNECT=7


-----POST PROCESSING PROCESSING METHOD------------------------------------------------------------------

   # Options: pymode, pyrate or stamps
POST_PROCESS_METHOD=<method>


-----PROCESSING STEPS-----------------------------------------------------------------------------------

    # yes / no options
EXTRACT_RAW_DATA=yes
DO_SLC=yes

    -----SENTINEL-1 SLC ONLY-----
    # Resize all SLCs to same shape and size (uses S1_RESIZE_REF_SLC), default: yes (must be same shape/size for processing)
DO_S1_RESIZE=yes
    # Leave as 'auto' if not pre-selecting a scene, it will then be calculated and updated
        # Scene can be different from the MASTER_SCENE used in Processing Method
S1_RESIZE_REF_SLC=auto
    # Subset all SLCs by burst numbers
DO_S1_BURST_SUBSET=yes

COREGISTER_DEM=yes
    # External image is required to assist in DEM coregistration?
USE_EXT_IMAGE=no

COREGISTER_SLAVES=yes
PROCESS_IFGS=yes
IFG_GEOTIFF=yes

-----CLEAN UP-------------------------------------------------------------------------------------------

    # Clean up intermediate processing files
CLEAN_UP=yes


-----DEM COREGISTRATION PARAMETERS----------------------------------------------------------------------

    -----FOR init_offsetm-----
    # Correlation patch size (128, 256, 512, 1024) (default: 1024)
        # Use larger window for large scenes and use scene centre (e.g. S1)
        # Use smaller window for windows towards edge of scene and smaller scenes (e.g. FB PALSAR)
DEM_PATCH_WINDOW=1024
    # Select centre of window for initial offset estimation (default: "-" this gives scene centre)
DEM_RPOS=-
DEM_AZPOS=-

    -----FOR create_diff_par-----
    # Range, azimuth offsets of image2 relative to image1 (samples) (default: 0 0) - for full DEM only, auto calculated for mli
DEM_OFFSET=0 0
    # Enter number of offset measurements in range, azimuth (default: 32 32)
DEM_OFFSET_MEASURE=32 32
    # Search window sizes (32, 64, 128...) in range, azimuth (default: 256 256)
DEM_WIN=256 256
    # Correlation SNR threshold (default: 0.15)
DEM_SNR=0.15
    # If full resolution processing, may need to change 'geocode' rad_max value to 8 to avoid holes in interpolation (default: 4)
DEM_RAD_MAX=4


-----SLAVE COREGISTRATION PARAMETERS--------------------------------------------------------------------

    # Cross-correlation threshold for offset rejection (default: 0.1)
COREG_CC_THRESH=0.1
    # Number of polynomial model parameters (1, 3, 4 or 6; only 1 required for S1)
COREG_MODEL_PARAMS=1
    # Size of window for intensity cross-correlation (default: 128)
COREG_WINDOW_SIZE=128
    # Number of search windows in range and azimuth directions (default: 64)
COREG_NUM_WINDOWS=64
    # SLC oversampling factor (1, 2 or 4) (default: 2)
COREG_OVERSAMPLING=2
    # Maximum number of offset estimation iterations (default: 5)
COREG_NUM_ITERATIONS=5

    -----FOR create_diff_par-----
    # Enter number of offset measurements in range, azimuth (default: 32 32)
SLAVE_OFFSET_MEASURE=32 32
    # Search window sizes (32, 64, 128...) (range, azimuth) (default: 256 256)
SLAVE_WIN=256 256
    # Cross-correlation threshold (default: 0.15)
SLAVE_CC_THRESH=0.15

    -----SENTINEL-1 ONLY-----
    # Coherence threshold used (default: 0.6)
COREG_S1_CC_THRESH=0.6
    # Minimum valid fraction of unwrapped phase values used (default: 0.01)
COREG_S1_FRAC_THRESH=0.01
    # Phase standard deviation threshold (default: 0.8)
COREG_S1_STDEV_THRESH=0.8


-----INTERFEROGRAM PARAMETERS---------------------------------------------------------------------------

    # Options: INT/FLAT/FILT/UNW/GEOCODE
IFG_BEGIN=INT
    # Options: FLAT/FILT/UNW/GEOCODE/DONE
IFG_END=DONE

    # Coherence threshold for masking
IFG_COHERENCE_THRESHOLD=0.3
    # Mask unwrapped pixels below coherence threshold
IFG_UNW_MASK=no
    # Number of unwrapping patches (default: 1, for high res data may need to be 2 or more)
IFG_PATCHES_RANGE=3
IFG_PATCHES_AZIMUTH=3
    # Location of reference pixel
IFG_REF_POINT_RANGE=-
IFG_REF_POINT_AZIMUTH=-

    # Adaptive spectral filtering (adf) parameters
        # Exponent for non-linear filtering
IFG_EXPONENT=0.5
        # Filtering FFT window size (8 - 512, default: 32)
IFG_FILTERING_WINDOW=32
        # Coherence estimation window value (must be odd numbers, default: 3)
IFG_COHERENCE_WINDOW=3
        # Baseline estimation
IFG_ITERATIVE=no

    -----CSK SPOTLIGHT ONLY-----
    # Cross-correlation threshold (default: 0.15)
IFG_THRES=0.15
    # Window for cross-correlation (larger better, default: 512)
IFG_INIT_WIN=512 512
    # Offset window (recommended to use at least 64)
IFG_OFFSET_WIN=128 128


-----POST PROCESSING PARAMETERS-------------------------------------------------------------------------

    # Amplitude Dispersion threshold for PS candidate selection (default: 0.6)
POST_IFG_DA_THRESHOLD=0.6
    # Area to crop the data to (min/max range, min/max aziumuth, full area is used by default:- -)
POST_IFG_AREA_RANGE=- -
POST_IFG_AREA_AZIMUTH=- -
    # example with values
#POST_IFG_AREA_RANGE=1234 3456
#POST_IFG_AREA_AZIMUTH=2345 4567
    # Number of patches for StaMPS processing (default: 2, for large areas more patches are recommended to save runtime)
POST_IFG_PATCHES_RANGE=2
POST_IFG_PATCHES_AZIMUTH=2
    # Number of overlapping pixels in each patch for StaMPS processing (default: 50)
POST_IFG_OVERLAP_RANGE=50
POST_IFG_OVERLAP_AZIMUTH=50


-----NCI PBS JOB PARAMETERS-----------------------------------------------------------------------------

NCI_PROJECT=dg9

    -----PBS JOB DEFAULTS FOR MULTI-JOBS-----
    # for raw data download, resize and subset Sentinel-1 SLCs, multi-look SLCs
MIN_JOBS=20
    # for SLC creation, SLC coregistration, ifg creation
MAX_JOBS=50
PBS_RUN_LOC=gdata1
QUEUE=normal
EXP_QUEUE=express
MDSS_QUEUE=copyq

    -----RAW DATA EXTRACTION FROM ARCHIVE/MDSS-----  # parameters for one scene only
RAW_WALLTIME=00:15:00
RAW_MEM=500MB
RAW_NCPUS=1

   -----CREATE GAMMA DEM -----
CREATE_DEM_WALLTIME=00:30:00
CREATE_DEM_MEM=8GB
CREATE_DEM_NCPUS=1

   -----FULL SLC CREATION-----  # parameters for one SLC only
SLC_WALLTIME=01:00:00
SLC_MEM=8GB
SLC_NCPUS=4

   -----CALCULATE MULTI-LOOK VALUES, SENTINEL-1 REF RESIZING SCENE-----
CALC_WALLTIME=00:05:00
CALC_MEM=50MB
CALC_NCPUS=1

   -----CALCULATE BASELINES-----
BASE_WALLTIME=00:15:00
BASE_MEM=500MB
BASE_NCPUS=1

   -----MULTI-LOOK FULL SLCS-----  # parameters for one SLC only
ML_WALLTIME=00:30:00
ML_MEM=4GB
ML_NCPUS=1

   -----RESIZE AND/OR SUBSET SENTINEL-1 SLC ONLY-----  # parameters for one SLC only, includes multi-looking
RESIZE_WALLTIME=01:00:00
RESIZE_MEM=8GB
RESIZE_NCPUS=1

   -----DEM COREGISTRATION-----
DEM_WALLTIME=02:00:00
DEM_MEM=8GB
DEM_NCPUS=4

   -----CALCULATE LATITUDE-LONGITUDE FOR EACH PIXEL (STAMPS ONLY)-----
PIX_WALLTIME=04:00:00
PIX_MEM=100MB
PIX_NCPUS=1

   -----SLAVE COREGISTRATION-----  # parameters for one SLC only
COREG_WALLTIME=01:00:00
COREG_MEM=8GB
COREG_NCPUS=4

   -----INTERFEROGRAM GENERATION-----  # parameters for one ifg only
IFG_WALLTIME=02:00:00
IFG_MEM=16GB
IFG_NCPUS=4

   -----POST INTERFEROGRAM PROCESSING-----
POST_WALLTIME=00:30:00
POST_MEM=500MB
POST_NCPUS=1

    -----JOB ERROR COLLATION-----
ERROR_WALLTIME=00:05:00
ERROR_MEM=50MB
ERROR_NCPUS=1

   -----PLOT PREVIEW IMAGES AS PDF-----
IMAGE_WALLTIME=0:30:00
IMAGE_MEM=500MB
IMAGE_NCPUS=1
"""
