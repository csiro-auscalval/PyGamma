import socket
import structlog
from insar.project import ProcConfig, IfgFileNames
import insar.constant as const

try:
    import py_gamma as pg
except ImportError as iex:
    pg = None
    hostname = socket.gethostname()

    if hostname.startswith("gadi"):
        # something odd here if can't find py_gamma path on NCI
        raise iex


_LOG = structlog.get_logger("insar")


def calc_int(pc: ProcConfig, ic: IfgFileNames, clean_up):
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
        stat = pg.create_offset(
            ic.r_master_slc_par,
            ic.r_slave_slc_par,
            ic.ifg_off,
            const.OFFSET_ESTIMATION_INTENSITY_CROSS_CORRELATION,
            pc.range_looks,
            pc.azimuth_looks,
            const.NON_INTERACTIVE,
            cout=cout,
            cerr=cerr,
        )

        if stat:
            msg = "failed to execute pg.create_offset"
            _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
            raise ProcessIfgException(msg)

        # 2-pass differential interferometry without phase unwrapping (CSK spotlight)
        if pc.sensor == "CSK" and pc.sensor_mode == "SP":
            raise NotImplementedError("Not required for Sentinel 1 processing")
        else:
            cout = []
            cerr = []

            # TODO: do any outputs need to be processed?
            stat = pg.offset_pwr(
                ic.r_master_slc,  # (input) single-look complex image 1 (reference)
                ic.r_slave_slc,  # (input) single-look complex image 2
                ic.r_master_slc_par,  # (input) SLC-1 ISP image parameter file
                ic.r_slave_slc_par,  # (input) SLC-2 ISP image parameter file
                ic.ifg_off,  # (input) ISP offset/interferogram parameter file
                ic.ifg_offs,  # (output) offset estimates in range and azimuth (fcomplex)
                ic.ifg_ccp,  # (output) cross-correlation of each patch (0.0->1.0) (float)
                const.RANGE_PATCH_SIZE,
                const.AZIMUTH_PATCH_SIZE,
                const.NOT_PROVIDED,  # (output) range and azimuth offsets and cross-correlation data
                const.NOT_PROVIDED,
                const.NUM_OFFSET_ESTIMATES_RANGE,
                const.NUM_OFFSET_ESTIMATES_AZIMUTH,
                const.CROSS_CORRELATION_THRESHOLD,
                cout=cout,
                cerr=cerr,
            )
            if stat:
                msg = "failed to execute pg.offset_pwr"
                _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
                raise ProcessIfgException(msg)

            cout = []
            cerr = []
            stat = pg.offset_fit(
                ic.ifg_offs,
                ic.ifg_ccp,
                ic.ifg_off,
                ic.ifg_coffs,
                ic.ifg_coffsets,
                cout=cout,
                cerr=cerr,
            )

            if stat:
                msg = "failed to execute pg.offset_fit"
                _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
                raise ProcessIfgException(msg)

    if clean_up:
        remove_files(ic.ifg_offs, ic.ifg_ccp, ic.ifg_coffs, ic.ifg_coffsets)

    cout = []
    cerr = []

    # Create differential interferogram parameter file
    stat = pg.create_diff_par(
        ic.ifg_off,
        const.NOT_PROVIDED,
        ic.ifg_diff_par,
        const.DIFF_PAR_OFFSET,
        const.NON_INTERACTIVE,
        cout=cout,
        cerr=cerr,
    )
    if stat:
        msg = "failed to execute pg.create_diff_par"
        _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
        raise ProcessIfgException(msg)


def remove_files(*args):
    """
    Attempts to remove the given files, logging any failures
    :param args: pathlib.Path like objects
    """
    for path in args:
        try:
            if path:
                path.unlink()
        except FileNotFoundError:
            _LOG.error("Could not delete {}".format(path))

        # TODO: add more exception handlers?


class ProcessIfgException(Exception):
    pass
