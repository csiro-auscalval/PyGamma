import structlog
import py_gamma as pg

_LOG = structlog.get_logger("insar")

RANGE_PATCH_SIZE = 64
AZIMUTH_PATCH_SIZE = 64
SLC_OVERSAMPLING_FACTOR_DEFAULT = 2
NUM_OFFSET_ESTIMATES_RANGE = 64
NUM_OFFSET_ESTIMATES_AZIMUTH = 256
CROSS_CORRELATION_THRESHOLD = 0.1

NON_INTERACTIVE = 0


def calc_int(ifg_off, r_master_slc, r_slave_slc,
             r_master_slc_par, r_slave_slc_par,
             range_looks, azimuth_looks,
             ifg_offs, ifg_coffs, ifg_coffsets, ifg_ccp, ifg_diff_par,
             sensor, sensor_mode, clean_up):
    """
    TODO
    :param ifg_off:
    :param r_master_slc:
    :param r_slave_slc:
    :param r_master_slc_par:
    :param r_slave_slc_par:
    :param range_looks:
    :param azimuth_looks:
    :param ifg_offs:
    :param ifg_coffs:
    :param ifg_coffsets:
    :param ifg_ccp:
    :param ifg_diff_par:
    :param sensor:
    :param sensor_mode:
    :param clean_up:
    """

    # Calculate and refine offset between interferometric SLC pair
    if not ifg_off.exists():
        stat = pg.create_offset(r_master_slc_par,
                                r_slave_slc_par,
                                ifg_off,
                                1,  # offset estimation algorithm:, 1=intensity cross-correlation (default)
                                range_looks,
                                azimuth_looks,
                                0)  # 0=non interactive mode
        assert stat == 0, str(stat)
        if stat != 0:
            print('\npg =', pg)
            print('stat =', stat)
            raise NotImplementedError('Handle error / stat={}'.format(stat))

        # 2-pass differential interferometry without phase unwrapping (CSK spotlight)
        if sensor == "CSK" and sensor_mode == "SP":
            raise NotImplementedError('Not required for sentinel 1 processing')
        else:
            cout = []
            cerr = []

            # TODO: do any outputs need to be processed?
            stat = pg.offset_pwr(r_master_slc,  # (input) single-look complex image 1 (reference)
                                 r_slave_slc,  # (input) single-look complex image 2
                                 r_master_slc_par,  # (input) SLC-1 ISP image parameter file
                                 r_slave_slc_par,  # (input) SLC-2 ISP image parameter file
                                 ifg_off,  # (input) ISP offset/interferogram parameter file
                                 ifg_offs,  # (output) offset estimates in range and azimuth (fcomplex)
                                 ifg_ccp,  # (output) cross-correlation of each patch (0.0->1.0) (float)
                                 RANGE_PATCH_SIZE,  # (range pixels, enter - for default from offset parameter file)
                                 AZIMUTH_PATCH_SIZE, # (azimuth lines, enter - for default from offset parameter file)
                                 "-",  # (output) range and azimuth offsets and cross-correlation data in text format, enter - for no output
                                 SLC_OVERSAMPLING_FACTOR_DEFAULT,  # (integer 2**N (1,2,4), enter - for default: 2)
                                 NUM_OFFSET_ESTIMATES_RANGE,  # or "-" for default from offset parameter file
                                 NUM_OFFSET_ESTIMATES_AZIMUTH,  # or "-" for default from offset parameter file
                                 CROSS_CORRELATION_THRESHOLD,  # (0.0->1.0) (or "-" for default from offset parameter file)
                                 cout=cout,
                                 cerr=cerr)
            if stat:
                msg = "failed to execute pg.offset_pwr"
                _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
                raise ProcessIfgException(msg)

            cout = []
            cerr = []
            stat = pg.offset_fit(ifg_offs, ifg_ccp, ifg_off, ifg_coffs, ifg_coffsets, cout=cout, cerr=cerr)

            if stat:
                msg = "failed to execute pg.offset_fit"
                _LOG.error(msg, stat=stat, gamma_stdout=cout, gamma_stderr=cerr)
                raise ProcessIfgException(msg)

    if clean_up:
        for p in (ifg_offs, ifg_ccp, ifg_coffs, ifg_coffsets):
            try:
                p.unlink()
            except FileNotFoundError:
                _LOG.error('Could not delete {}'.format(p))

    # Create differential interferogram parameter file
    pg.create_diff_par(ifg_off,
                       "-",
                       ifg_diff_par,
                       0,  # PAR type 0=OFF_par, ISP offset and interferogram parameters
                       NON_INTERACTIVE)


class ProcessIfgException(Exception):
    pass
