import socket
import structlog
from insar.project import ProcConfig, IfgFileNames

try:
    import py_gamma as pg
except ImportError as iex:
    pg = None
    hostname = socket.gethostname()

    if hostname.startswith('gadi'):
        # something odd here if can't find py_gamma path on NCI
        raise iex


_LOG = structlog.get_logger("insar")

# TODO: move these to constants.py
OFFSET_ESTIMATION_INTENSITY_CROSS_CORRELATION = 1
OFFSET_ESTIMATION_FRINGE_VISIBILITY = 2

RANGE_PATCH_SIZE = 64
AZIMUTH_PATCH_SIZE = 64
SLC_OVERSAMPLING_FACTOR_DEFAULT = 2
NUM_OFFSET_ESTIMATES_RANGE = 64
NUM_OFFSET_ESTIMATES_AZIMUTH = 256
CROSS_CORRELATION_THRESHOLD = 0.1

NON_INTERACTIVE = 0
NOT_PROVIDED = '-'
NO_OUTPUT = '-'

# PAR1 and PAR2 parameter file type
DIFF_PAR_OFFSET = 0  # ISP offset and interferogram parameters
DIFF_PAR_SLC_MLI = 1  # ISP SLC/MLI parameters (default)
DIFF_PAR_DEM = 2


def calc_int(pc: ProcConfig,
             ic: IfgFileNames,
             clean_up):
    """
    Perform InSAR INT processing step.
    :param pc: ProcConfig settings obj
    :param ic: IfgFileNames settings obj
    :param clean_up: bool, True to delete working files after processing
    """

    # Calculate and refine offset between interferometric SLC pair
    if not ic.ifg_off.exists():
        cout = []
        cerr = []
        stat = pg.create_offset(ic.r_master_slc_par,
                                ic.r_slave_slc_par,
                                ic.ifg_off,
                                OFFSET_ESTIMATION_INTENSITY_CROSS_CORRELATION,
                                pc.range_looks,
                                pc.azimuth_looks,
                                NON_INTERACTIVE,
                                cout=cout,
                                cerr=cerr)

        if stat:
            msg = "failed to execute pg.create_offset"
            _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
            raise ProcessIfgException(msg)

        # 2-pass differential interferometry without phase unwrapping (CSK spotlight)
        if pc.sensor == "CSK" and pc.sensor_mode == "SP":
            raise NotImplementedError('Not required for Sentinel 1 processing')
        else:
            cout = []
            cerr = []

            # TODO: do any outputs need to be processed?
            stat = pg.offset_pwr(ic.r_master_slc,  # (input) single-look complex image 1 (reference)
                                 ic.r_slave_slc,  # (input) single-look complex image 2
                                 ic.r_master_slc_par,  # (input) SLC-1 ISP image parameter file
                                 ic.r_slave_slc_par,  # (input) SLC-2 ISP image parameter file
                                 ic.ifg_off,  # (input) ISP offset/interferogram parameter file
                                 ic.ifg_offs,  # (output) offset estimates in range and azimuth (fcomplex)
                                 ic.ifg_ccp,  # (output) cross-correlation of each patch (0.0->1.0) (float)
                                 RANGE_PATCH_SIZE,  # (range pixels, enter - for default from offset parameter file)
                                 AZIMUTH_PATCH_SIZE, # (azimuth lines, enter - for default from offset parameter file)
                                 NO_OUTPUT,  # (output) range and azimuth offsets and cross-correlation data
                                 SLC_OVERSAMPLING_FACTOR_DEFAULT,  # (integer 2**N (1,2,4), enter - for default: 2)
                                 NUM_OFFSET_ESTIMATES_RANGE,  # or "-" for default from offset parameter file
                                 NUM_OFFSET_ESTIMATES_AZIMUTH,  # or "-" for default from offset parameter file
                                 CROSS_CORRELATION_THRESHOLD,
                                 cout=cout,
                                 cerr=cerr)
            if stat:
                msg = "failed to execute pg.offset_pwr"
                _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
                raise ProcessIfgException(msg)

            cout = []
            cerr = []
            stat = pg.offset_fit(ic.ifg_offs,
                                 ic.ifg_ccp,
                                 ic.ifg_off,
                                 ic.ifg_coffs,
                                 ic.ifg_coffsets,
                                 cout=cout,
                                 cerr=cerr)

            if stat:
                msg = "failed to execute pg.offset_fit"
                _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
                raise ProcessIfgException(msg)

    if clean_up:
        for p in (ic.ifg_offs, ic.ifg_ccp, ic.ifg_coffs, ic.ifg_coffsets):
            try:
                p.unlink()
            except FileNotFoundError:
                _LOG.error('Could not delete {}'.format(p))

    cout = []
    cerr = []

    # Create differential interferogram parameter file
    stat = pg.create_diff_par(ic.ifg_off,
                              NOT_PROVIDED,
                              ic.ifg_diff_par,
                              DIFF_PAR_OFFSET,
                              NON_INTERACTIVE,
                              cout=cout,
                              cerr=cerr)
    if stat:
        msg = "failed to execute pg.create_diff_par"
        _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
        raise ProcessIfgException(msg)


class ProcessIfgException(Exception):
    pass
