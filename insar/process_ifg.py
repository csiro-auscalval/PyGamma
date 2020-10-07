import socket
import pathlib
import subprocess

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


# TODO: add type hinting


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


def get_ifg_width(r_master_mli_par):
    """
    Return range/sample width from dem diff file.
    :param r_master_mli_par: open file-like obj
    :return: width as integer
    """
    for line in r_master_mli_par.readlines():
        if const.MatchStrings.SLC_RANGE_SAMPLES.value in line:
            _, value = line.split()
            return int(value)

    msg = 'Cannot locate "{}" value in resampled master MLI'
    raise ProcessIfgException(msg.format(const.MatchStrings.SLC_RANGE_SAMPLES.value))


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
                ic.r_master_slc,  # single-look complex image 1 (reference)
                ic.r_slave_slc,  # single-look complex image 2
                ic.r_master_slc_par,  # SLC-1 ISP image parameter file
                ic.r_slave_slc_par,  # SLC-2 ISP image parameter file
                ic.ifg_off,  # ISP offset/interferogram parameter file
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
    pc: ProcConfig, ic: IfgFileNames, dc: DEMFileNames, ifg_width, clean_up
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

    width10 = get_width10(ic.ifg_off10)

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

    # calculate coherence of flattened interferogram
    # WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING COHERENCE OPTIMISATION
    pg.cc_wave(
        ic.ifg_flat,  # normalised complex interferogram
        ic.r_master_mli,  # multi-look intensity image of the first scene (float)
        ic.r_slave_mli,  # multi-look intensity image of the second scene (float)
        ic.ifg_flat_cc,  # interferometric correlation coefficient (float)
        ifg_width,  # number of samples/line
        pc.ifg_coherence_window,  # estimation window size in columns
        pc.ifg_coherence_window,  # estimation window size in lines
        const.ESTIMATION_WINDOW_TRIANGULAR,  # estimation window "shape/style"
    )


def get_width10(ifg_off10_path):
    """
    Return range/sample width from ifg_off10
    :param ifg_off10_path: Path type obj
    :return: width as integer
    """
    with ifg_off10_path.open() as f:
        for line in f.readlines():
            if const.MatchStrings.IFG_AZIMUTH_LINES.value in line:
                _, value = line.split()
                return int(value)

    msg = 'Cannot locate "{}" value in ifg offsets10 file'
    raise ProcessIfgException(msg.format(const.MatchStrings.IFG_AZIMUTH_LINES.value))


def calc_filt(pc: ProcConfig, ic: IfgFileNames, ifg_width: int):
    """
    TODO docs
    :param pc:
    :param ic:
    :param ifg_width:
    :return:
    """
    if not ic.ifg_flat.exists():
        msg = "cannot locate (*.flat) flattened interferogram: {}. Was FLAT executed?".format(
            ic.ifg_flat
        )
        _LOG.error(msg, missing_file=ic.ifg_flat)
        raise ProcessIfgException(msg)

    # Smooth the phase by Goldstein-Werner filter
    pg.adf(
        ic.ifg_flat,
        ic.ifg_filt,
        ic.ifg_filt_cc,
        ifg_width,
        pc.ifg_exponent,
        pc.ifg_filtering_window,
        pc.ifg_coherence_window,
        const.NOT_PROVIDED,  # step
        const.NOT_PROVIDED,  # loff
        const.NOT_PROVIDED,  # nlines
        const.NOT_PROVIDED,  # minimum fraction of points required to be non-zero in the filter window (default=0.700)
    )


# TODO unw == unwrapped?
def calc_unw(pc: ProcConfig, ic: IfgFileNames, ifg_width, clean_up):
    """
    TODO: docs
    :param pc:
    :param ic:
    :param ifg_width:
    :param clean_up: bool, True to clean up temporary files during run
    :return:
    """

    if not ic.ifg_filt.exists():
        msg = "cannot locate (*.filt) filtered interferogram: {}. Was FILT executed?".format(
            ic.ifg_filt
        )
        _LOG.error(msg, missing_file=ic.ifg_filt)
        raise ProcessIfgException(msg)

    pg.rascc_mask(
        ic.ifg_filt_cc,  # <cc> coherence image (float)
        const.NOT_PROVIDED,  # <pwr> intensity image (float)
        ifg_width,  # number of samples/row
        const.RASCC_MASK_DEFAULT_COHERENCE_STARTING_LINE,
        const.RASCC_MASK_DEFAULT_INTENSITY_STARTING_LINE,
        const.RASCC_TO_EOF,  # [nlines] number of lines to display
        const.N_PIXELS_DEFAULT_RANGE_AVERAGE,  # number of pixels to average in range
        const.N_PIXELS_DEFAULT_AZIMUTH_AVERAGE,  # number of pixels to average in azimuth
        pc.ifg_coherence_threshold,  # masking threshold
        const.RASCC_DEFAULT_INTENSITY_THRESHOLD,  # intensity threshold
        const.NOT_PROVIDED,  # [cc_min] minimum coherence value for color display
        const.NOT_PROVIDED,  # [cc_max] maximum coherence value for color display
        const.NOT_PROVIDED,  # [scale] intensity image display scale factor
        const.NOT_PROVIDED,  # [exp] intensity display exponent
        const.LEFT_RIGHT_FLIPPING_NORMAL,  # [LR] left/right flipping flag
        ic.ifg_mask,  # [rasf] (output) validity mask
    )

    if (
        const.RASCC_MIN_THINNING_THRESHOLD
        <= pc.multi_look
        <= const.RASCC_THINNING_THRESHOLD
    ):
        unwrapped_tmp = calc_unw_thinning(pc, ic, ifg_width, clean_up=clean_up)
    else:
        msg = (
            "Processing for unwrapping the full interferogram without masking not implemented. "
            "GA's InSAR team use multilooks=2 for Sentinel-1 ARD product generation."
        )
        raise NotImplementedError(msg)

    if pc.ifg_unw_mask.lower() == "yes":
        # Mask unwrapped interferogram for low coherence areas below threshold
        pg.mask_data(
            unwrapped_tmp,  # input file
            ifg_width,
            ic.ifg_unw,  # output file
            ic.ifg_mask,
            const.DTYPE_FLOAT,
        )
        remove_files(unwrapped_tmp)
    else:
        unwrapped_tmp.rename(ic.ifg_unw)


def calc_unw_thinning(
    pc: ProcConfig,
    ic: IfgFileNames,
    ifg_width,
    num_sampling_reduction_runs=3,
    clean_up=False,
):
    """
    TODO docs
    :param pc:
    :param ic:
    :param ifg_width:
    :param num_sampling_reduction_runs:
    :param clean_up:
    :return: dest TODO unwrapped ifg
    """
    # Use rascc_mask_thinning to weed the validity mask for large scenes. this can unwrap a sparser
    # network which can be interpolated and used as a model for unwrapping the full interferogram
    thresh_1st = pc.ifg_coherence_threshold + const.RASCC_THRESHOLD_INCREMENT
    thresh_max = thresh_1st + const.RASCC_THRESHOLD_INCREMENT

    # TODO: can the output file ic.ifg_mask_thin exist?
    pg.rascc_mask_thinning(
        ic.ifg_mask,  # validity mask
        ic.ifg_filt_cc,  # file for adaptive sampling reduction, e.g. coherence (float)
        ifg_width,
        ic.ifg_mask_thin,  # (output) validity mask with reduced sampling
        num_sampling_reduction_runs,
        pc.ifg_coherence_threshold,
        thresh_1st,
        thresh_max,
    )

    # Unwrapping with validity mask (Phase unwrapping using Minimum Cost Flow (MCF) triangulation)
    pg.mcf(
        ic.ifg_filt,  # interferogram
        ic.ifg_filt_cc,  # weight factors file (float)
        ic.ifg_mask_thin,  # validity mask file
        ic.ifg_unw_thin,  # (output) unwrapped phase image (*.unw) (float)
        ifg_width,  # number of samples per row
        const.TRIANGULATION_MODE_DELAUNAY,
        const.NOT_PROVIDED,  # r offset
        const.NOT_PROVIDED,  # l offset
        const.NOT_PROVIDED,  # num of range samples
        const.NOT_PROVIDED,  # nlines
        pc.ifg_patches_range,  # number of patches (tiles?) in range
        pc.ifg_patches_azimuth,  # num of lines of section to unwrap
        const.NOT_PROVIDED,  # overlap between patches in pixels
        pc.ifg_ref_point_range,  # phase reference range offset
        pc.ifg_ref_point_azimuth,  # phase reference azimuth offset
        const.INIT_FLAG_SET_PHASE_0_AT_INITIAL,
    )

    # Interpolate sparse unwrapped points to give unwrapping model
    # Weighted interpolation of gaps in 2D data using adaptive interpolation
    pg.interp_ad(
        ic.ifg_unw_thin,
        ic.ifg_unw_model,
        ifg_width,
        const.MAX_INTERP_WINDOW_RADIUS,  # maximum interpolation window radius
        const.NPOINTS_MIN_FOR_INTERP,  # minimum number of points used for interpolation
        const.NPOINT_MAX_FOR_INTERP,  # maximum number of points used for interpolation
        const.WEIGHTING_MODE_2,
    )

    # Use model to unwrap filtered interferogram
    dest = pathlib.Path(
        "temp-unwapped-filtered-ifg"
    )  # TODO: handle paths in temp file struct or use tempfile module?

    pg.unw_model(
        ic.ifg_filt,  # complex interferogram
        ic.ifg_unw_model,  # approximate unwrapped phase model (float)
        dest,  # output file
        ifg_width,
        pc.ifg_ref_point_range,  # xinit
        pc.ifg_ref_point_azimuth,  # # yinit
        const.REF_POINT_PHASE,  # reference point phase (radians)
    )

    if clean_up:
        remove_files(ic.ifg_unw_thin, ic.ifg_unw_model)

    return dest


def do_geocode(
    pc: ProcConfig,
    ic: IfgFileNames,
    dc: DEMFileNames,
    dtype_out=const.DTYPE_GEOTIFF_FLOAT,
):
    """
    TODO
    :param pc: ProcConfig obj
    :param ic: IfgFileNames obj
    :param dc: DEMFileNames obj
    :param dtype_out:
    """
    # TODO: figure out how to fix the "buried" I/O here
    width_in = get_width_in(dc.dem_diff.open())
    width_out = get_width_out(dc.eqa_dem_par.open())

    geocode_unwrapped_ifg(ic, dc, width_in, width_out)
    geocode_flattened_ifg(ic, dc, width_in, width_out)
    geocode_filtered_ifg(ic, dc, width_in, width_out)
    geocode_flat_coherence_file(ic, dc, width_in, width_out)
    geocode_filtered_coherence_file(ic, dc, width_in, width_out)

    # Geotiff geocoded outputs
    if pc.ifg_geotiff.lower() == "yes":
        # unw
        pg.data2geotiff(
            dc.eqa_dem_par,
            ic.ifg_unw_geocode_out,
            dtype_out,
            ic.ifg_unw_geocode_out_tiff,
        )
        # flat ifg
        pg.data2geotiff(
            dc.eqa_dem_par,
            ic.ifg_flat_geocode_out,
            dtype_out,
            ic.ifg_flat_geocode_out_tiff,
        )
        # filt ifg
        pg.data2geotiff(
            dc.eqa_dem_par,
            ic.ifg_filt_geocode_out,
            dtype_out,
            ic.ifg_filt_geocode_out_tiff,
        )
        # flat cc
        pg.data2geotiff(
            dc.eqa_dem_par,
            ic.ifg_flat_cc_geocode_out,
            dtype_out,
            ic.ifg_flat_cc_geocode_out_tiff,
        )
        # filt cc
        pg.data2geotiff(
            dc.eqa_dem_par,
            ic.ifg_filt_cc_geocode_out,
            dtype_out,
            ic.ifg_filt_cc_geocode_out_tiff,
        )

    # TF: also remove all binaries and .ras files to save disc space
    #     keep flat.int since this is currently used as input for stamps processing
    # TODO: move paths to dedicated mgmt class
    current = pathlib.Path(".")
    all_paths = [tuple(current.glob(pattern)) for pattern in const.TEMP_FILE_GLOBS]

    for path in all_paths:
        remove_files(*path)


def get_width_in(dem_diff):
    """
    Return range/sample width from dem diff file.
    :param dem_diff: open file-like obj
    :return: width as integer
    """
    for line in dem_diff.readlines():
        if "range_samp_1:" in line:
            _, value = line.split()
            return int(value)

    msg = 'Cannot locate "range_samp_1" value in DEM diff file'
    raise ProcessIfgException(msg)


def get_width_out(dem_eqa_par):
    """
    Return range field from eqa_dem_par file
    :param dem_eqa_par: open file like obj
    :return: width as integer
    """
    for line in dem_eqa_par.readlines():
        if "width:" in line:
            _, value = line.split()
            return int(value)

    msg = 'Cannot locate "width" value in DEM eqa param file'
    raise ProcessIfgException(msg)


def geocode_unwrapped_ifg(ic: IfgFileNames, dc: DEMFileNames, width_in, width_out):
    """
    TODO
    :param ic:
    :param dc:
    :param width_in:
    :param width_out:
    """
    dest = pathlib.Path("temp-geocode_unwrapped_ifg")

    # Use bicubic spline interpolation for geocoded unwrapped interferogram
    pg.geocode_back(ic.ifg_unw, width_in, dc.dem_lt_fine, dest, width_out)
    pg.mask_data(dest, width_out, ic.ifg_unw_geocode_out, dc.seamask)

    # make quick-look png image
    rasrmg_wrapper(ic.ifg_unw_geocode_out, width_out, ic.ifg_unw_geocode_bmp)
    convert(ic.ifg_unw_geocode_bmp)
    kml_map(ic.ifg_unw_geocode_png, dc.eqa_dem_par)
    remove_files(ic.ifg_unw_geocode_bmp, dest)


def geocode_flattened_ifg(
    ic: IfgFileNames, dc: DEMFileNames, width_in, width_out,
):
    """
    TODO
    :param ic:
    :param dc:
    :param width_in:
    :param width_out:
    """
    # # Use bicubic spline interpolation for geocoded flattened interferogram
    # convert to float and extract phase
    pg.cpx_to_real(
        ic.ifg_flat, ic.ifg_flat_float, width_in, const.CPX_TO_REAL_OUTPUT_TYPE_PHASE
    )

    dest = pathlib.Path("temp-ifg_flat_float-resampled")
    pg.geocode_back(ic.ifg_flat_float, width_in, dc.dem_lt_fine, dest, width_out)

    # apply sea mask to phase data
    pg.mask_data(dest, width_out, ic.ifg_flat_geocode_out, dc.seamask)

    # make quick-look png image
    rasrmg_wrapper(ic.ifg_flat_geocode_out, width_out, ic.ifg_flat_geocode_bmp)
    convert(ic.ifg_flat_geocode_bmp)
    kml_map(ic.ifg_flat_geocode_png, dc.eqa_dem_par)
    remove_files(ic.ifg_flat_geocode_bmp, dest, ic.ifg_flat_float)


def geocode_filtered_ifg(ic: IfgFileNames, dc: DEMFileNames, width_in, width_out):
    """
    TODO:
    :param ic:
    :param dc:
    :param width_in:
    :param width_out:
    :return:
    """
    pg.cpx_to_real(
        ic.ifg_filt, ic.ifg_filt_float, width_in, const.CPX_TO_REAL_OUTPUT_TYPE_PHASE
    )

    dest = pathlib.Path("temp-geocode_filtered_ifg-resampled")
    pg.geocode_back(ic.ifg_filt_float, width_in, dc.dem_lt_fine, dest, width_out)

    # apply sea mask to phase data
    pg.mask_data(dest, width_out, ic.ifg_filt_geocode_out, dc.seamask)

    # make quick-look png image
    rasrmg_wrapper(ic.ifg_filt_geocode_out, width_out, ic.ifg_filt_geocode_bmp)
    convert(ic.ifg_filt_geocode_bmp)
    kml_map(ic.ifg_filt_geocode_png, dc.eqa_dem_par)
    remove_files(ic.ifg_filt_geocode_bmp, dest, ic.ifg_filt_float)


def geocode_flat_coherence_file(
    ic: IfgFileNames, dc: DEMFileNames, width_in, width_out,
):
    """
    TODO
    :param ic:
    :param dc:
    :param width_in:
    :param width_out:
    """
    pg.geocode_back(
        ic.ifg_flat_cc, width_in, dc.dem_lt_fine, ic.ifg_flat_cc_geocode_out, width_out
    )

    # make quick-look png image
    dest = pathlib.Path("temp-geocode_flat_coherence_file.bmp")
    rascc_wrapper(ic.ifg_flat_cc_geocode_out, width_out, dest)
    pg.ras2ras(dest, ic.ifg_flat_cc_geocode_bmp, const.RAS2RAS_GREY_COLOUR_MAP)
    convert(ic.ifg_flat_cc_geocode_bmp)
    kml_map(ic.ifg_flat_cc_geocode_png, dc.eqa_dem_par)
    remove_files(ic.ifg_flat_cc_geocode_bmp, dest)


def geocode_filtered_coherence_file(
    ic: IfgFileNames, dc: DEMFileNames, width_in, width_out,
):
    """
    TODO:
    :param ic:
    :param dc:
    :param width_in:
    :param width_out:
    """
    pg.geocode_back(
        ic.ifg_filt_cc, width_in, dc.dem_lt_fine, ic.ifg_filt_cc_geocode_out, width_out
    )

    # make quick-look png image
    dest = pathlib.Path("temp-geocode_geocoded_filter_coherence_file.bmp")
    rascc_wrapper(ic.ifg_filt_cc_geocode_out, width_out, dest)
    pg.ras2ras(dest, ic.ifg_filt_cc_geocode_bmp, const.RAS2RAS_GREY_COLOUR_MAP)
    convert(ic.ifg_filt_cc_geocode_bmp)
    kml_map(ic.ifg_filt_cc_geocode_png, dc.eqa_dem_par)
    remove_files(ic.ifg_filt_cc_geocode_bmp, dest)


def rasrmg_wrapper(
    input_file,
    width_out,
    output_file,
    pwr=const.NOT_PROVIDED,
    start_pwr=const.DEFAULT_STARTING_LINE,
    start_unw=const.DEFAULT_STARTING_LINE,
    nlines=const.DISPLAY_TO_EOF,
    pixavr=const.RAS_PIXEL_AVERAGE_RANGE,
    pixavaz=const.RAS_PIXEL_AVERAGE_AZIMUTH,
    ph_scale=const.RAS_PH_SCALE,
    scale=const.RAS_SCALE,
    exp=const.RAS_EXP,
    ph_offset=const.RAS_PH_OFFSET,
    leftright=const.LEFT_RIGHT_FLIPPING_NORMAL,
):
    """
    Helper function to default rasrmg args to Geoscience Australia InSAR defaults.

    Generate 8-bit raster graphics image from unwrapped phase & intensity data
    TODO: skips some variables in docs (cc, start_cc & cc_min)

    :param input_file: unwrapped phase data
    :param width_out: samples per row of unwrapped phase and intensity files
    :param output_file:
    :param pwr: intensity data (float, enter - for none)
    :param start_pwr:starting line of unwrapped phase file ('-' for default: 1)
    :param start_unw: starting line of intensity file ('-' for default: 1)
    :param nlines: number of lines to display (- or 0 for default: to end of file)
    :param pixavr: number of pixels to average in range
    :param pixavaz: number of pixels to average in azimuth
    :param ph_scale: phase display scale factor (enter - for default: 0.33333)
    :param scale: pwr display scale factor (- for default: 1.0)
    :param exp: pwr display exponent (- for default: default: 0.35)
    :param ph_offset: phase offset in radians subtracted from unw ( - is default: 0.0)
    :param leftright: left/right mirror image (- is default, 1: normal (default), -1: mirror image)
    :return:
    """

    # docs from gadi "/g/data/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-20191203/DISP/bin/rasrmg -h"
    # as they do not exist as HTML in the GAMMA install
    pg.rasrmg(
        input_file,
        pwr,
        width_out,
        start_unw,
        start_pwr,
        nlines,
        pixavr,
        pixavaz,
        ph_scale,
        scale,
        exp,
        ph_offset,
        leftright,
        output_file,
    )


def rascc_wrapper(
    input_file,
    width_out,
    output_file,
    pwr=const.NOT_PROVIDED,
    start_cc=const.DEFAULT_STARTING_LINE,
    start_pwr=const.DEFAULT_STARTING_LINE,
    nlines=const.DISPLAY_TO_EOF,
    pixavr=const.RAS_PIXEL_AVERAGE_RANGE,
    pixavaz=const.RAS_PIXEL_AVERAGE_AZIMUTH,
    cmin=const.RASCC_MIN_CORRELATION,
    cmax=const.RASCC_MAX_CORRELATION,
    scale=const.RAS_SCALE,
    exp=const.RAS_EXP,
    leftright=const.LEFT_RIGHT_FLIPPING_NORMAL,
):
    """
    Helper function to default rascc args to Geoscience Australia InSAR defaults.

    Generate 8-bit raster graphics image of correlation coefficient + intensity data

    :param input_file:
    :param width_out:
    :param output_file:
    :param pwr:
    :param start_cc:
    :param start_pwr:
    :param nlines:
    :param pixavr:
    :param pixavaz:
    :param cmin:
    :param cmax:
    :param scale:
    :param exp:
    :param leftright:
    :return:
    """
    # docs from gadi "/g/data/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-20191203/DISP/bin/rascc -h"
    # as they do not exist as HTML in the GAMMA install
    pg.rascc(
        input_file,
        pwr,
        width_out,
        start_cc,
        start_pwr,
        nlines,
        pixavr,
        pixavaz,
        cmin,
        cmax,
        scale,
        exp,
        leftright,
        output_file,
    )


def convert(input_file):
    """
    Run an ImageMagick command to convert a BMP to PNG.
    :param input_file: BMP
    """
    args = [
        input_file,  # a BMP
        "-transparent black",
        input_file.with_suffix(".png"),
    ]

    try:
        subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=True,
        )
        _LOG.info("Calling ImageMagick's convert", args=args)
    except subprocess.CalledProcessError as cpe:
        msg = "failed to execute ImageMagick's convert"
        _LOG.error(msg, stat=cpe.returncode, stdout=cpe.stdout, stderr=cpe.stderr)
        raise ProcessIfgException(msg)


def kml_map(input_file, dem_par, output_file=None):
    """
    Generates KML format XML with link to an image using geometry from a dem_par.
    :param input_file:
    :param dem_par:
    :param output_file:
    :return:
    """
    if output_file is None:
        output_file = input_file.with_suffix(".kml")

    pg.kml_map(input_file, dem_par, output_file)


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
