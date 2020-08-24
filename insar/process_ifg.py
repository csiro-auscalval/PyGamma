import socket
import structlog
from insar.project import ProcConfig, IfgFileNames, DEMFileNames
import insar.constant as const

from insar.py_gamma_ga import GammaInterface, subprocess_wrapper

try:
    import py_gamma
except ImportError as iex:
    hostname = socket.gethostname()

    if hostname.startswith("gadi"):
        # something odd here if can't find py_gamma path on NCI
        raise iex


_LOG = structlog.get_logger("insar")


# customise the py_gamma calling interface to automate repetitive tasks
def decorator(func):
    """
    Decorate & expand 'func' with default logging & error handling for Ifg processing.

    The automatic adding of logging & error handling simplifies Gamma calls considerably, in addition
    to reducing a large amount of code duplication.

    :param func: function to decorate (e.g. py_gamma_ga.subprocess_wrapper)
    :return: a decorated function
    """

    def error_handler(cmd, *args, **kwargs):
        if const.COUT not in kwargs:
            kwargs[const.COUT] = []
        if const.CERR not in kwargs:
            kwargs[const.CERR] = []

        stat = func(cmd, *args, **kwargs)
        cout = str(kwargs[const.COUT])
        cerr = str(kwargs[const.CERR])

        if stat:
            msg = "failed to execute pg.{}".format(cmd)
            _LOG.error(msg, args=args, **kwargs)  # NB: cout/cerr already in kwargs
            raise ProcessIfgException(msg)

        return stat, cout, cerr

    return error_handler


# Customise Gamma shim to automatically handle basic error checking and logging
pg = GammaInterface(subprocess_func=decorator(subprocess_wrapper))


def calc_int(pc: ProcConfig, ic: IfgFileNames, clean_up):
    """
    Perform InSAR INT processing step.
    :param pc: ProcConfig settings obj
    :param ic: IfgFileNames settings obj
    :param clean_up: bool, True to delete working files after processing
    """

    # Calculate and refine offset between interferometric SLC pair
    if not ic.ifg_off.exists():
        pg.create_offset(
            ic.r_master_slc_par,
            ic.r_slave_slc_par,
            ic.ifg_off,
            const.OFFSET_ESTIMATION_INTENSITY_CROSS_CORRELATION,
            pc.range_looks,
            pc.azimuth_looks,
            const.NON_INTERACTIVE,
        )

        # 2-pass differential interferometry without phase unwrapping (CSK spotlight)
        if pc.sensor == "CSK" and pc.sensor_mode == "SP":
            raise NotImplementedError("Not required for Sentinel 1 processing")
        else:
            pg.offset_pwr(
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
            )

            pg.offset_fit(
                ic.ifg_offs,
                ic.ifg_ccp,
                ic.ifg_off,  # TODO: should ifg_off be renamed ifg_off_par in settings?
                ic.ifg_coffs,
                ic.ifg_coffsets,
            )

    if clean_up:
        remove_files(ic.ifg_offs, ic.ifg_ccp, ic.ifg_coffs, ic.ifg_coffsets)

    # Create differential interferogram parameter file
    pg.create_diff_par(
        ic.ifg_off,
        const.NOT_PROVIDED,
        ic.ifg_diff_par,
        const.DIFF_PAR_OFFSET,
        const.NON_INTERACTIVE,
    )


def generate_init_flattened_ifg(
    pc: ProcConfig, ic: IfgFileNames, dc: DEMFileNames, clean_up
):
    """
    TODO: docs
    :param pc:
    :param ic:
    :param dc:
    :param clean_up:
    """

    # calculate initial baseline of interferogram (i.e. the spatial distance between the two
    # satellite positions at the time of acquisition of first and second image).
    pg.base_orbit(
        ic.r_master_slc_par, ic.r_slave_slc_par, ic.ifg_base_init,
    )

    # Simulate phase from the DEM & linear baseline model
    # linear baseline model may be inadequate for longer scenes, in which case use phase_sim_orb
    pg.phase_sim_orb(
        ic.r_master_slc_par,
        ic.r_slave_slc_par,
        ic.ifg_off,
        dc.rdc_dem,
        ic.ifg_sim_unw0,
        ic.r_master_slc_par,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.INT_MODE_REPEAT_PASS,
        const.PHASE_OFFSET_MODE_SUBTRACT_PHASE,
    )

    # Calculate initial flattened interferogram (baselines from orbit)
    # Multi-look complex interferogram generation from co-registered SLC data and a simulated
    # interferogram derived from a DEM.
    pg.SLC_diff_intf(
        ic.r_master_slc,
        ic.r_slave_slc,
        ic.r_master_slc_par,
        ic.r_slave_slc_par,
        ic.ifg_off,
        ic.ifg_sim_unw0,
        ic.ifg_flat0,
        pc.range_looks,
        pc.azimuth_looks,
        const.RANGE_SPECTRAL_SHIFT_FLAG_APPLY_FILTER,
        const.AZIMUTH_COMMON_BAND_NO_FILTER,
        const.DEFAULT_MINIMUM_RANGE_BANDWIDTH_FRACTION,
        const.SLC_1_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE,
        const.SLC_2_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE,
    )

    # Estimate residual baseline using fringe rate of differential interferogram
    pg.base_init(
        ic.r_master_slc_par,
        const.NOT_PROVIDED,
        ic.ifg_off,
        ic.ifg_flat0,
        ic.ifg_base_res,
        const.BASE_INIT_METHOD_4,
    )

    # Add residual baseline estimate to initial estimate
    pg.base_add(
        ic.ifg_base_init, ic.ifg_base_res, ic.ifg_base, const.BASE_ADD_MODE_ADD,
    )

    # Simulate the phase from the DEM and refined baseline model
    # simulate unwrapped interferometric phase using DEM height, linear baseline model, and linear
    # deformation rate for single or repeat-pass interferograms
    pg.phase_sim(
        ic.r_master_slc_par,
        ic.ifg_off,
        ic.ifg_base,
        dc.rdc_dem,
        ic.ifg_sim_unw1,
        const.PH_FLAG_SIMULATED_UNFLATTENED_INTERFEROGRAM,
        const.B_FLAG_INIT_BASELINE,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.INT_MODE_REPEAT_PASS,
        const.NOT_PROVIDED,
        const.PH_MODE_ABSOLUTE_PHASE,
    )

    # Calculate second flattened interferogram (baselines refined using fringe rate)
    pg.SLC_diff_intf(
        ic.r_master_slc,
        ic.r_slave_slc,
        ic.r_master_slc_par,
        ic.r_slave_slc_par,
        ic.ifg_off,
        ic.ifg_sim_unw1,
        ic.ifg_flat1,
        pc.range_looks,
        pc.azimuth_looks,
        const.RANGE_SPECTRAL_SHIFT_FLAG_APPLY_FILTER,
        const.AZIMUTH_COMMON_BAND_NO_FILTER,
        const.DEFAULT_MINIMUM_RANGE_BANDWIDTH_FRACTION,
        const.SLC_1_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE,
        const.SLC_2_RANGE_PHASE_MODE_REF_FUNCTION_CENTRE,
    )

    if clean_up:
        remove_files(
            ic.ifg_base_temp,
            ic.ifg_base_res,
            ic.ifg_base_init,
            ic.ifg_flat_temp,
            ic.ifg_sim_unw0,
            ic.ifg_flat0,
        )


# NB: this function is a bit long and ugly due to the volume of chained calls for the workflow
def generate_final_flattened_ifg(
    pc: ProcConfig, ic: IfgFileNames, dc: DEMFileNames, width10, ifg_width, clean_up
):
    """
    Perform refinement of baseline model using ground control points
    :param pc:
    :param ic:
    :param dc:
    :param width10:
    :param ifg_width:
    :param clean_up:
    """
    # multi-look the flattened interferogram 10 times
    pg.multi_cpx(
        ic.ifg_flat1,
        ic.ifg_off,
        ic.ifg_flat10,
        ic.ifg_off10,
        const.NUM_RANGE_LOOKS,
        const.NUM_AZIMUTH_LOOKS,
        const.NOT_PROVIDED,  # line offset
        const.DISPLAY_TO_EOF,
    )

    # Generate coherence image
    pg.cc_wave(
        ic.ifg_flat10,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        ic.ifg_flat_cc10,
        width10,
        const.BX,
        const.BY,
        const.ESTIMATION_WINDOW_TRIANGULAR,
    )

    # Generate validity mask with high coherence threshold for unwrapping
    pg.rascc_mask(
        ic.ifg_flat_cc10,
        const.NOT_PROVIDED,
        width10,
        const.NOT_PROVIDED,  # start_cc
        const.NOT_PROVIDED,  # start_pwr
        const.DISPLAY_TO_EOF,
        const.NOT_PROVIDED,  # pixavr
        const.NOT_PROVIDED,  # pixavaz
        const.MASKING_COHERENCE_THRESHOLD,
        const.NOT_PROVIDED,  # pwr_thresh
        const.NOT_PROVIDED,  # cc_min
        const.MASKING_COHERENCE_THRESHOLD,  # cc_max
        const.NOT_PROVIDED,  # scale
        const.NOT_PROVIDED,  # exp
        const.NOT_PROVIDED,  # left_right_flipping
        ic.ifg_flat_cc10_mask,
    )

    # Perform unwrapping
    pg.mcf(
        ic.ifg_flat10,
        ic.ifg_flat_cc10,
        ic.ifg_flat_cc10_mask,
        ic.ifg_flat10.unw,
        width10,
        const.TRIANGULATION_MODE_DELAUNAY,
        const.NOT_PROVIDED,  # roff: offset to starting range of section to unwrap
        const.NOT_PROVIDED,  # loff: offset to starting line of section to unwrap
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NUM_RANGE_PATCHES,
        const.NUM_AZIMUTH_PATCHES,
    )

    # Oversample unwrapped interferogram to original resolution
    pg.multi_real(
        ic.ifg_flat10.unw,
        ic.ifg_off10,
        ic.ifg_flat1.unw,
        ic.ifg_off,
        const.RANGE_LOOKS_MAGNIFICATION,
        const.AZIMUTH_LOOKS_MAGNIFICATION,
        const.NOT_PROVIDED,  # line offset
        const.DISPLAY_TO_EOF,
    )

    # Add full-res unwrapped phase to simulated phase
    # FIXME: create temp file names container to avoid path manipulation in processing code
    ifg_flat_int1 = ic.ifg_flat.with_suffix(".int1.unw")

    pg.sub_phase(
        ic.ifg_flat1.unw,
        ic.ifg_sim_unw1,
        ic.ifg_diff_par,
        ifg_flat_int1,
        const.DTYPE_FLOAT,
        const.SUB_PHASE_ADD_PHASE_MODE,
    )

    # calculate coherence of original flattened interferogram
    # MG: WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING
    # COHERENCE OPTIMISATION
    pg.cc_wave(
        ic.ifg_flat1,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        ic.ifg_flat_cc0,
        ifg_width,
        pc.ifg_coherence_window,
        pc.ifg_coherence_window,
        const.ESTIMATION_WINDOW_TRIANGULAR,
    )

    # generate validity mask for GCP selection
    pg.rascc_mask(
        ic.ifg_flat_cc0,
        const.NOT_PROVIDED,
        ifg_width,
        const.NOT_PROVIDED,  # start_cc
        const.NOT_PROVIDED,  # start_pwr
        const.DISPLAY_TO_EOF,
        const.NOT_PROVIDED,  # num pixels to average in range
        const.NOT_PROVIDED,  # num pixels to average in azimuth
        const.MASKING_COHERENCE_THRESHOLD,  # NB: reuse threshold from other pg.rascc_mask() call
        const.NOT_PROVIDED,  # pwr_threshold
        const.NOT_PROVIDED,  # cc_min
        const.NOT_PROVIDED,  # cc_max
        const.NOT_PROVIDED,  # scale
        const.NOT_PROVIDED,  # exp
        const.NOT_PROVIDED,  # left_right_flipping flag
        ic.ifg_flat_cc0_mask,
    )

    # select GCPs from high coherence areas
    pg.extract_gcp(
        dc.rdc_dem,
        ic.ifg_off,
        ic.ifg_gcp,
        const.NUM_GCP_POINTS_RANGE,
        const.NUM_GCP_POINTS_AZIMUTH,
        ic.ifg_flat_cc0_mask,
    )

    # extract phase at GCPs
    ifg_flat1_unw = ic.ifg_flat.with_suffix(
        ".int1.unw"
    )  # TODO: move to temp file container

    pg.gcp_phase(
        ifg_flat1_unw, ic.ifg_off, ic.ifg_gcp, ic.ifg_gcp_ph, const.GCP_PHASE_WINDOW_SIZE,
    )

    # Calculate precision baseline from GCP phase data
    pg.base_ls(
        ic.r_master_slc_par,
        ic.ifg_off,
        ic.ifg_gcp_ph,
        ic.ifg_base,
        const.NOT_PROVIDED,  # ph_flag
        const.NOT_PROVIDED,  # bc_flag
        const.NOT_PROVIDED,  # bn_flag
        const.NOT_PROVIDED,  # bcdot_flag
        const.NOT_PROVIDED,  # bndot_flag
        const.NOT_PROVIDED,  # bperp_min
    )

    # USE OLD CODE FOR NOW
    # Simulate the phase from the DEM and precision baseline model.
    pg.phase_sim(
        ic.r_master_slc_par,
        ic.ifg_off,
        ic.ifg_base,
        dc.rdc_dem,
        ic.ifg_sim_unw,
        const.NOT_PROVIDED,  # ph_flag
        const.B_FLAG_PRECISION_BASELINE,
    )

    # subtract simulated phase ('ifg_flat1' was originally 'ifg', but this file is no longer created)
    pg.sub_phase(
        ic.ifg_flat1,
        ic.ifg_sim_unw,
        ic.ifg_diff_par,
        ic.ifg_flat,
        const.DTYPE_FCOMPLEX,
        const.SUB_PHASE_SUBTRACT_MODE,
    )

    if clean_up:
        remove_files(
            ic.ifg_flat1,
            ifg_flat1_unw,
            ic.ifg_sim_unw1,
            ic.ifg_flat1.unw,
            ic.ifg_flat_cc0,
            ic.ifg_flat_cc0_mask,
            ic.ifg_flat10.unw,
            ic.ifg_off10,
            ic.ifg_flat10,
            ic.ifg_flat_cc10,
            ic.ifg_flat_cc10_mask,
            ic.ifg_gcp,
            ic.ifg_gcp_ph,
        )

    # Calculate final flattened interferogram with common band filtering (diff ifg generation from
    # co-registered SLCs and a simulated interferogram)
    pg.SLC_diff_intf(
        ic.r_master_slc,
        ic.r_slave_slc,
        ic.r_master_slc_par,
        ic.r_slave_slc_par,
        ic.ifg_off,
        ic.ifg_sim_unw,
        ic.ifg_flat,
        pc.range_looks,
        pc.azimuth_looks,
        const.NOT_PROVIDED,  # sps_flag
        const.AZIMUTH_COMMON_BAND_NO_FILTER,
        const.NOT_PROVIDED,  # rbw_min
        const.NOT_PROVIDED,  # rp1 flag
        const.NOT_PROVIDED,  # rp2 flag
    )

    # Calculate perpendicular baselines
    _, cout, _ = pg.base_perp(ic.ifg_base, ic.r_master_slc_par, ic.ifg_off,)

    # copy content to bperp file instead of rerunning EXE (like the old Bash code)
    try:
        with ic.ifg_bperp.open("w") as f:
            f.writelines(cout)
    except IOError as ex:
        msg = "Failed to write ifg_bperp"
        _LOG.error(msg, exception=ex)
        raise ex


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
