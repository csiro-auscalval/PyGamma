import socket
import structlog
from insar.project import ProcConfig, IfgFileNames, DEMFileNames
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


# TODO: do any pg.<function_name> outputs need to be kept or processed?
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
            _LOG.error(
                msg,
                stat=stat,
                slc1_par=ic.r_master_slc_par,
                slc2_par=ic.r_slave_slc_par,
                gamma_stdout=cout,
                gamma_stderr=cerr,
            )

            raise ProcessIfgException(msg)

        # 2-pass differential interferometry without phase unwrapping (CSK spotlight)
        if pc.sensor == "CSK" and pc.sensor_mode == "SP":
            raise NotImplementedError("Not required for Sentinel 1 processing")
        else:
            cout = []
            cerr = []

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
                _LOG.error(
                    msg,
                    stat=stat,
                    slc1=ic.r_master_slc,
                    slc2=ic.r_slave_slc,
                    slc1_par=ic.r_master_slc_par,
                    slc2_par=ic.r_slave_slc_par,
                    gamma_stdout=cout,
                    gamma_stderr=cerr,
                )

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
                _LOG.error(
                    msg,
                    stat=stat,
                    offs=ic.ifg_offs,
                    ccp=ic.ifg_ccp,
                    off_par=ic.ifg_off,  # TODO: should ifg_off be renamed ifg_off_par in settings?
                    gamma_stdout=cout,
                    gamma_stderr=cerr,
                )

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
        _LOG.error(
            msg,
            stat=stat,
            par1=ic.ifg_off,
            diff_par=ic.ifg_diff_par,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )
        raise ProcessIfgException(msg)


# FIXME: would be nice to add a func to automatically handle the cout/cerr & pg stat to log and raise
#        errors as needed. Maybe with a decorator?
# NB: this function is long and a bit ugly as there's a lot of chained calls in the workflow. This
#     means there's a lot of local variables on the stack with some risk of conflated variable names
#     accidental use of reused cout/cerr variables.
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
    cout = []
    cerr = []

    stat = pg.base_orbit(
        ic.r_master_slc_par, ic.r_slave_slc_par, ic.ifg_base_init, cout=cout, cerr=cerr
    )

    if stat:
        msg = "failed to execute pg.base_orbit"
        _LOG.error(
            msg,
            stat=stat,
            slc1_par=ic.r_master_slc_par,
            slc2_par=ic.r_slave_slc_par,
            baseline_file=ic.ifg_base_init,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Simulate phase from the DEM & linear baseline model
    # linear baseline model may be inadequate for longer scenes, in which case use phase_sim_orb
    cout = []
    cerr = []

    stat = pg.phase_sim_orb(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.phase_sim_orb"
        _LOG.error(
            msg,
            stat=stat,
            slc1_par=ic.r_master_slc_par,
            slc2r_par=ic.r_slave_slc_par,
            off_par=ic.ifg_off,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Calculate initial flattened interferogram (baselines from orbit)
    # Multi-look complex interferogram generation from co-registered SLC data and a simulated
    # interferogram derived from a DEM.
    cout = []
    cerr = []

    stat = pg.SLC_diff_intf(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.SLC_diff_intf"
        _LOG.error(
            msg,
            stat=stat,
            slc1=ic.r_master_slc,
            slc2r=ic.r_slave_slc,
            slc1_par=ic.r_master_slc_par,
            slc2r_par=ic.r_slave_slc_par,
            off_par=ic.ifg_off,
            sim_unw=ic.ifg_sim_unw0,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Estimate residual baseline using fringe rate of differential interferogram
    cout = []
    cerr = []

    stat = pg.base_init(
        ic.r_master_slc_par,
        const.NOT_PROVIDED,
        ic.ifg_off,
        ic.ifg_flat0,
        ic.ifg_base_res,
        const.BASE_INIT_METHOD_4,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.base_init"
        _LOG.error(
            msg,
            stat=stat,
            slc1_par=ic.r_master_slc_par,
            off_par=ic.ifg_off,
            int=ic.ifg_flat0,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Add residual baseline estimate to initial estimate
    cout = []
    cerr = []

    stat = pg.base_add(
        ic.ifg_base_init,
        ic.ifg_base_res,
        ic.ifg_base,
        const.BASE_ADD_MODE_ADD,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.base_add"
        _LOG.error(
            msg,
            stat=stat,
            base1=ic.ifg_base_init,
            base2=ic.ifg_base_res,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Simulate the phase from the DEM and refined baseline model
    # simulate unwrapped interferometric phase using DEM height, linear baseline model, and linear
    # deformation rate for single or repeat-pass interferograms
    cout = []
    cerr = []

    stat = pg.phase_sim(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.phase_sim"
        _LOG.error(
            msg,
            stat=stat,
            slc1_par=ic.r_master_slc_par,
            off_par=ic.ifg_off,
            baseline=ic.ifg_base,
            hgt_map=dc.rdc_dem,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Calculate second flattened interferogram (baselines refined using fringe rate)
    cout = []
    cerr = []

    stat = pg.SLC_diff_intf(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.SLC_diff_intf"
        _LOG.error(
            msg,
            stat=stat,
            slc1=ic.r_master_slc,
            slc2r=ic.r_slave_slc,
            slc1_par=ic.r_master_slc_par,
            slc2r_par=ic.r_slave_slc_par,
            off_par=ic.ifg_off,
            sim_unw=ic.ifg_sim_unw0,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    if clean_up:
        remove_files(
            ic.ifg_base_temp,
            ic.ifg_base_res,
            ic.ifg_base_init,
            ic.ifg_flat_temp,
            ic.ifg_sim_unw0,
            ic.ifg_flat0,
        )


# NB: this segment is also large and ugly due to the chained calls in the workflow
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
    cout = []
    cerr = []

    stat = pg.multi_cpx(
        ic.ifg_flat1,
        ic.ifg_off,
        ic.ifg_flat10,
        ic.ifg_off10,
        const.NUM_RANGE_LOOKS,
        const.NUM_AZIMUTH_LOOKS,
        const.NOT_PROVIDED,  # line offset
        const.DISPLAY_TO_EOF,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.multi_cpx"
        _LOG.error(
            msg,
            stat=stat,
            slc1=ic.r_master_slc,
            cpx_input=ic.ifg_flat1,
            off_par_in=ic.ifg_off,
            cpx_output=ic.ifg_flat10,
            off_par_out=ic.ifg_off10,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Generate coherence image
    cout = []
    cerr = []

    stat = pg.cc_wave(
        ic.ifg_flat10,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        ic.ifg_flat_cc10,
        width10,
        const.BX,
        const.BY,
        const.ESTIMATION_WINDOW_TRIANGULAR,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.cc_wave"
        _LOG.error(
            msg,
            stat=stat,
            ifg=ic.ifg_flat10,
            cc=ic.ifg_flat_cc10,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Generate validity mask with high coherence threshold for unwrapping
    cout = []
    cerr = []

    stat = pg.rascc_mask(
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
        cout=cout,
        cerr=cerr,
    )
    if stat:
        msg = "failed to execute pg.rascc_mask"
        _LOG.error(
            msg,
            stat=stat,
            cc=ic.ifg_flat_cc10,
            rasf=ic.ifg_flat_cc10_mask,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Perform unwrapping
    cout = []
    cerr = []

    stat = pg.mcf(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.mcf"
        _LOG.error(
            msg,
            stat=stat,
            cc=ic.ifg_flat_cc10,
            rasf=ic.ifg_flat_cc10_mask,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Oversample unwrapped interferogram to original resolution
    cout = []
    cerr = []

    stat = pg.multi_real(
        ic.ifg_flat10.unw,
        ic.ifg_off10,
        ic.ifg_flat1.unw,
        ic.ifg_off,
        const.RANGE_LOOKS_MAGNIFICATION,
        const.AZIMUTH_LOOKS_MAGNIFICATION,
        const.NOT_PROVIDED,  # line offset
        const.DISPLAY_TO_EOF,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.multi_real"
        _LOG.error(
            msg,
            stat=stat,
            real_input=ic.ifg_flat10.unw,
            off_par_in=ic.ifg_off10,
            real_output=ic.ifg_flat1.unw,
            off_par_out=ic.ifg_off,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Add full-res unwrapped phase to simulated phase
    cout = []
    cerr = []

    # FIXME: create temp file names container to avoid path manipulation in processing code
    ifg_flat_int1 = ic.ifg_flat.with_suffix(".int1.unw")

    stat = pg.sub_phase(
        ic.ifg_flat1.unw,
        ic.ifg_sim_unw1,
        ic.ifg_diff_par,
        ifg_flat_int1,
        const.DTYPE_FLOAT,
        const.SUB_PHASE_ADD_PHASE_MODE,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.sub_phase"
        _LOG.error(
            msg,
            stat=stat,
            int1=ic.ifg_flat1.unw,
            unw2=ic.ifg_sim_unw1,
            diff_par=ic.ifg_diff_par,
            diff_int=ifg_flat_int1,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # calculate coherence of original flattened interferogram
    # MG: WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING
    # COHERENCE OPTIMISATION
    cout = []
    cerr = []

    stat = pg.cc_wave(
        ic.ifg_flat1,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        ic.ifg_flat_cc0,
        ifg_width,
        pc.ifg_coherence_window,
        pc.ifg_coherence_window,
        const.ESTIMATION_WINDOW_TRIANGULAR,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.cc_wave"
        _LOG.error(
            msg,
            stat=stat,
            iterf=ic.ifg_flat1,
            cc=ic.ifg_flat_cc0,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # generate validity mask for GCP selection
    cout = []
    cerr = []

    stat = pg.rascc_mask(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.rascc_mask"
        _LOG.error(
            msg,
            stat=stat,
            cc=ic.ifg_flat_cc0,
            raster_validity_mask=ic.ifg_flat_cc0_mask,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # select GCPs from high coherence areas
    cout = []
    cerr = []

    stat = pg.extract_gcp(
        dc.rdc_dem,
        ic.ifg_off,
        ic.ifg_gcp,
        const.NUM_GCP_POINTS_RANGE,
        const.NUM_GCP_POINTS_AZIMUTH,
        ic.ifg_flat_cc0_mask,
    )

    if stat:
        msg = "failed to execute pg.extract_gcp"
        _LOG.error(
            msg,
            stat=stat,
            DEM_rdc=dc.rdc_dem,
            OFF_par=ic.ifg_off,
            GCP=ic.ifg_gcp,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # extract phase at GCPs
    cout = []
    cerr = []

    ifg_flat1_unw = ic.ifg_flat.with_suffix(
        ".int1.unw"
    )  # TODO: move to temp file container

    stat = pg.gcp_phase(
        ifg_flat1_unw,
        ic.ifg_off,
        ic.ifg_gcp,
        ic.ifg_gcp_ph,
        const.GCP_PHASE_WINDOW_SIZE,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.gcp_phase"
        _LOG.error(
            msg,
            stat=stat,
            unw=ifg_flat1_unw,
            off_par=ic.ifg_off,
            gcp=ic.ifg_gcp,
            gcp_ph=ic.ifg_gcp_ph,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Calculate precision baseline from GCP phase data
    cout = []
    cerr = []

    stat = pg.base_ls(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.base_ls"
        _LOG.error(
            msg,
            stat=stat,
            slc_par=ic.r_master_slc_par,
            off_par=ic.ifg_off,
            gcp_ph=ic.ifg_gcp_ph,
            baseline=ic.ifg_base,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # USE OLD CODE FOR NOW
    # Simulate the phase from the DEM and precision baseline model.
    cout = []
    cerr = []

    stat = pg.phase_sim(
        ic.r_master_slc_par,
        ic.ifg_off,
        ic.ifg_base,
        dc.rdc_dem,
        ic.ifg_sim_unw,
        const.NOT_PROVIDED,  # ph_flag
        const.B_FLAG_PRECISION_BASELINE,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.phase_sim"
        _LOG.error(
            msg,
            stat=stat,
            slc1_par=ic.r_master_slc_par,
            off_par=ic.ifg_off,
            baseline=ic.ifg_base,
            hgt_map=dc.rdc_dem,
            sim_unw=ic.ifg_sim_unw,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # subtract simulated phase ('ifg_flat1' was originally 'ifg', but this file is no longer created)
    cout = []
    cerr = []

    stat = pg.sub_phase(
        ic.ifg_flat1,
        ic.ifg_sim_unw,
        ic.ifg_diff_par,
        ic.ifg_flat,
        const.DTYPE_FCOMPLEX,
        const.SUB_PHASE_SUBTRACT_MODE,
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.sub_phase"
        _LOG.error(
            msg,
            stat=stat,
            int1=ic.ifg_flat1,
            unw2=ic.ifg_sim_unw,
            diff_par=ic.ifg_diff_par,
            diff_int=ic.ifg_flat,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

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
    cout = []
    cerr = []

    stat = pg.SLC_diff_intf(
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
        cout=cout,
        cerr=cerr,
    )

    if stat:
        msg = "failed to execute pg.SLC_diff_intf"
        _LOG.error(
            msg,
            stat=stat,
            slc1=ic.r_master_slc,
            slc2r=ic.r_slave_slc,
            slc1_par=ic.r_master_slc_par,
            slc2r_par=ic.r_slave_slc_par,
            off_par=ic.ifg_off,
            sim_unw=ic.ifg_sim_unw,
            diff_int=ic.ifg_flat,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

    # Calculate perpendicular baselines
    cout = []
    cerr = []

    stat = pg.base_perp(
        ic.ifg_base, ic.r_master_slc_par, ic.ifg_off, cout=cout, cerr=cerr
    )

    if stat:
        msg = "failed to execute pg.base_perp"
        _LOG.error(
            msg,
            stat=stat,
            baseline=ic.ifg_base,
            slc1_par=ic.r_master_slc_par,
            off_par=ic.ifg_off,
            gamma_stdout=cout,
            gamma_stderr=cerr,
        )

        raise ProcessIfgException(msg)

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
