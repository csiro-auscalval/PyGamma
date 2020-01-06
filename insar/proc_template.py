PROC_FILE_TEMPLATE = """
##### GAMMA CONFIGURATION FILE #####


-----NCI SOFTWARE CONFIGURATION FILE--------------------------------------------------------------------

GAMMA_CONFIG=/g/data/u46/users/pd1813/INSAR/INSAR_DEV_BULK_PROCESS/gamma_insar/configs/GAMMA_CONFIG


-----NCI FILE PATHS-------------------------------------------------------------------------------------

# NCI_PATH=/g/data1/u46/users/pd1813/INSAR/test_a

NCI_PATH={outdir}
ENVISAT_ORBITS=/g/data1/dg9/SAR_ORBITS/ENVISAT
ERS_ORBITS=/g/data1/dg9/SAR_ORBITS/ERS_ODR_UPDATED
S1_ORBITS=/g/data/fj7/Copernicus/Sentinel-1
S1_PATH=/g/data1/fj7/Copernicus/Sentinel-1/C-SAR/SLC
MASTER_DEM_IMAGE=/g/data1/dg9/MASTER_DEM


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
S1_FILE_LIST={s1_file_list}
SCENE_LIST=scenes.list
SLAVE_LIST=slaves.list
IFG_LIST=ifgs.list
FRAME_LIST=frame.list
    # list for removing scene/s from lists (ie. for SLCs that don't work)
REMOVE_SCENE_LIST=remove_scenes.list


-----PROJECT DIRECTORY & TRACK--------------------------------------------------------------------------

PROJECT={project}
TRACK={track}
FRAME={frame}

-----RAW DATA & DEM LOCATION ON MDSS--------------------------------------------------------------------

    # Sentinel-1 - if AOI within Australia, GAMMA DEM will be produced automatically.
                 - if AOI elsewhere,a  manual GAMMA DEM will need to first be created and MDSS_DEM_tar
                   details required.
                 - data downloaded directly from S1_PATH and S1_ORBITS.

    # Options: aust (within Australia) or other (outside Australia)
DEM_AREA=aust
    # if using DEM from MDSS, enter file name (exc. tar.gz). If auto generated, enter track name
DEM_NAME={track}_{frame}
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
POLARISATION={polarization}
    # Options: ASAR, CSK, ERS, JERS1, PALSAR1, PALSAR2, RSAT1, RSAT2, S1, TSX
SENSOR=S1
    # Sensor mode options:
        # ASAR: I4 or - for other image modes
        # CSK: HI or SP (HIMAGE or Spotlight)
        # PALSAR2: WD or SM (Wide-swath/Stripmap)
        # RSAT2: W or MF (Wide/Multi-look Fine)
        # S1: IWS or SM (Interferometic Wide Swath/Stripmap)
SENSOR_MODE=IWS
    # If ERS, specify which one (ERS1 or ERS2)
ERS_SENSOR=
    # If PALSAR2, specify which raw data level (raw or slc)
PALSAR2_TYPE=


-----MULTI-LOOK VALUES----------------------------------------------------------------------------------

    # For full resolution (with square pixels), set to 1
MULTI-LOOK={multi_look}
    # Leave as 'auto' if not pre-selecting, it will then be auto calculated and updated
RANGE_LOOKS=auto
AZIMUTH_LOOKS=auto


-----INTERFEROGRAM PROCESSING METHOD--------------------------------------------------------------------

    # Options: chain (use daisy-chain), sbas (use reference master) or single (use single master)
PROCESS_METHOD=sbas
    # Leave as 'auto' if not pre-selecting a scene, it will then be calculated and updated
REF_MASTER_SCENE=auto
    # thresholds for minimum and maximum number of SBAS connections
MIN_CONNECT=4
    # default is 7 for S1, 10 for other sensors (e.g. RSAT2)
MAX_CONNECT=7


-----POST PROCESSING PROCESSING METHOD------------------------------------------------------------------

   # Options: pymode, pyrate or stamps
POST_PROCESS_METHOD=pyrate


-----PROCESSING STEPS-----------------------------------------------------------------------------------

    # yes / no options
EXTRACT_RAW_DATA={extract_raw_data}
DO_SLC={do_slc}

    -----SENTINEL-1 SLC ONLY-----
    # Subset all SLCs by specific burst numbers
DO_S1_BURST_SUBSET=no
    # start and end bursts for each swath (e.g. 4-7)
SWATH1=
SWATH2=
SWATH3=

COREGISTER_DEM={coregister_dem}
    # External image is required to assist in DEM coregistration?
USE_EXT_IMAGE=no

COREGISTER_SLAVES={coregister_slaves}
PROCESS_IFGS={process_ifgs}
IFG_GEOTIFF={process_geotiff}

-----CLEAN UP-------------------------------------------------------------------------------------------

    # Clean up intermediate processing files
CLEAN_UP={clean_up}


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
    # Coherence threshold used (default: 0.8)
COREG_S1_CC_THRESH=0.8
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
CREATE_DEM_WALLTIME=01:00:00
CREATE_DEM_MEM=16GB
CREATE_DEM_NCPUS=1

   -----FULL SLC CREATION-----  # parameters for one SLC only
SLC_WALLTIME=01:00:00
SLC_MEM=16GB
SLC_NCPUS=4

   -----CALCULATE MULTI-LOOK VALUES, SENTINEL-1 REF RESIZING SCENE-----
CALC_WALLTIME=00:15:00
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
RESIZE_MEM=16GB
RESIZE_NCPUS=1

   -----DEM COREGISTRATION-----
DEM_WALLTIME=02:30:00
DEM_MEM=16GB
DEM_NCPUS=4

   -----CALCULATE LATITUDE-LONGITUDE FOR EACH PIXEL (STAMPS ONLY)-----
PIX_WALLTIME=04:00:00
PIX_MEM=100MB
PIX_NCPUS=1

   -----SLAVE COREGISTRATION-----  # parameters for one SLC only
COREG_WALLTIME=02:00:00
COREG_MEM=16GB
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