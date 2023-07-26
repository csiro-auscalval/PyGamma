import subprocess
import shutil
import math
import io

import insar.constant as const

from typing import Union, Tuple, Optional, Any
from pathlib import Path

from insar.project import ProcConfig
from insar.paths.interferogram import InterferogramPaths
from insar.paths.dem import DEMPaths
from insar.coreg_utils import latlon_to_px
from insar.path_util import append_suffix
from insar.gamma.proxy import create_gamma_proxy
from insar.subprocess_utils import working_directory
from insar.process_utils import convert
from insar.logs import STATUS_LOGGER as LOG
from insar.utils import TemporaryDirectory


class ProcessIfgException(Exception):
    pass


pg = create_gamma_proxy(ProcessIfgException)


class TempFilePaths:
    """
    Defines temp file names for process ifg.

    Keeps file naming concerns separate to the processing details.
    """

    ifg_flat10_unw: Path
    ifg_flat1_unw: Path
    ifg_flat_diff_int_unw: Path
    unwrapped_filtered_ifg: Path
    geocode_unwrapped_ifg: Path
    geocode_flat_ifg: Path
    geocode_flat_ifg_cpx: Path
    geocode_filt_ifg: Path
    geocode_filt_ifg_cpx: Path
    geocode_flat_coherence_file: Path
    geocode_filt_coherence_file: Path

    def __init__(self, ic: InterferogramPaths) -> None:
        ifg_dir = ic.ifg_dir

        # set temp file paths for flattening step
        self.ifg_flat10_unw = append_suffix(ic.ifg_flat10, "_int_unw")
        self.ifg_flat1_unw = append_suffix(ic.ifg_flat1, "_int_unw")
        self.ifg_flat_diff_int_unw = append_suffix(ic.ifg_flat, "_int1_unw")

        # unw thinning step
        self.unwrapped_filtered_ifg = ifg_dir / "unwrapped_filtered_ifg.tmp"

        # temp files from geocoding step
        self.geocode_unwrapped_ifg = ifg_dir / "geocode_unw_ifg.tmp"
        self.geocode_flat_ifg = ifg_dir / "geocode_flat_ifg.tmp"
        self.geocode_flat_ifg_cpx = ifg_dir / "geocode_flat_ifg_cpx.tmp"
        self.geocode_filt_ifg = ifg_dir / "geocode_filt_ifg.tmp"
        self.geocode_filt_ifg_cpx = ifg_dir / "geocode_filt_ifg_cpx.tmp"
        self.geocode_flat_coherence_file = ifg_dir / "geocode_flat_coherence_file.tmp.bmp"
        self.geocode_filt_coherence_file = ifg_dir / "geocode_filt_coherence_file.tmp.bmp"

    def __getattr__(self, name: str) -> Any:
        attr = self.__getattribute__(name)
        if isinstance(attr, Path):
            # Force to always return absolute paths
            return attr.absolute()
        else:
            return attr

    def __setattr__(self, name: str, value: Any) -> None:
        if isinstance(value, str):
            LOG.error(f"Trying to set {name}={value} as a 'str' instead of a 'Path' object")
        super().__setattr__(name, value)


def quicklook_real(
    srcfn: Path,
    width: int,
    dstfn: Optional[Path] = None,
    pixavx: int = 20,
    pixavy: int = 20,
    min: float = -math.pi,
    max: float = math.pi,
    cmap: str = "viridis",
) -> Path:

    if dstfn is None:
        dstfn = srcfn.with_suffix(".png").absolute()

    with TemporaryDirectory() as tmpdir:

        tmpbmp = tmpdir / "tmp.bmp"

        pg.ras_linear(srcfn, width, None, None, pixavx, pixavy, min, max, 1, Path(cmap).with_suffix(".cm"), tmpbmp, 0)

        subprocess.run(f"convert {tmpbmp} {dstfn}", shell=True)

    return dstfn


def run_workflow(
    pc: ProcConfig,
    ic: InterferogramPaths,
    dc: DEMPaths,
    tc: TempFilePaths,
    ifg_width: int,
    enable_refinement: bool = False,
    land_center_latlon: Optional[Tuple[float, float]] = None,
) -> None:

    LOG.info(f"Running IFG workflow with ifg_width={ifg_width}")

    if not ic.ifg_dir.exists():
        LOG.debug(f"Creating directory {str(ic.ifg_dir)}")
        ic.ifg_dir.mkdir(parents=True)

    with working_directory(ic.ifg_dir):

        validate_ifg_input_files(ic)

        land_center_px = None
        if land_center_latlon:
            land_center_px = latlon_to_px(pg, ic.r_secondary_mli_par, *land_center_latlon)

        LOG.info(f"Land center for IFG secondary {land_center_px} for {ic.r_secondary_mli}")

        # future version might want to allow selection of steps (skipped for simplicity Oct 2020)
        calc_int(pc, ic)
        ifg_file = initial_flattened_ifg(pc, ic, dc)

        if enable_refinement:
            LOG.debug("Performing refinement steps...")

            # Note: These are not needed for Sentinel-1 processing

            ifg_file = refined_flattened_ifg(pc, ic, dc, ifg_file)
            ifg_file = precise_flattened_ifg(pc, ic, dc, tc, ifg_file, ifg_width, land_center_px)

        else:
            LOG.debug("No refinement steps needed, just copying files")

            LOG.debug(f"Copying {ic.ifg_base_init} to {ic.ifg_base}")
            shutil.copy(ic.ifg_base_init, ic.ifg_base)

            LOG.debug(f"Copying {ifg_file} to {ic.ifg_flat}")
            shutil.copy(ifg_file, ic.ifg_flat)

        calc_bperp_coh_filt(pc, ic, ifg_file, ic.ifg_base, ifg_width)

        try:

            if pc.multi_look > 1:  # Fails if multi_look == 1, so let's skip the pain of waiting...
                LOG.debug(f"Attempting to unwinded output with width={ifg_width} and land_center={land_center_px}")
                calc_unw(pc, ic, tc, ifg_width, land_center_px)

        except ProcessIfgException:
            LOG.error("Failed to unwind the interferogram")

        do_geocode(pc, ic, dc, tc, ifg_width)


def validate_ifg_input_files(ic: InterferogramPaths) -> None:
    msg = "Cannot locate input files. Run SLC coregistration steps for each acquisition."
    missing_files = []

    if not ic.r_primary_slc.exists():
        missing_files.append(ic.r_primary_slc)

    if not ic.r_primary_mli.exists():
        missing_files.append(ic.r_primary_mli)

    if not ic.r_secondary_slc.exists():
        missing_files.append(ic.r_secondary_slc)

    if not ic.r_secondary_mli.exists():
        missing_files.append(ic.r_secondary_mli)

    # Raise exception with additional info on missing_files
    if missing_files:
        msg = f"Missing files: {missing_files}"
        LOG.error(msg)
        raise ProcessIfgException(msg)


def get_ifg_width(r_primary_mli_par: io.IOBase) -> int:
    """
    Return range/sample width from dem diff file.
    :param r_primary_mli_par: open file-like obj
    :return: width as integer
    """
    for line in r_primary_mli_par.readlines():
        if const.MatchStrings.SLC_RANGE_SAMPLES.value in str(line):
            _, value = line.split()
            return int(value)

    msg = 'Cannot locate "{}" value in resampled primary MLI'
    raise ProcessIfgException(msg.format(const.MatchStrings.SLC_RANGE_SAMPLES.value))


def calc_int(pc: ProcConfig, ic: InterferogramPaths) -> None:
    """
    Perform InSAR INT processing step.
    :param pc: ProcConfig settings obj
    :param ic: InterferogramPaths settings obj
    """

    # Calculate and refine offset between interferometric SLC pair
    if not ic.ifg_off.exists():
        pg.create_offset(
            ic.r_primary_slc_par,
            ic.r_secondary_slc_par,
            ic.ifg_off,
            const.OFFSET_ESTIMATION_INTENSITY_CROSS_CORRELATION,
            pc.range_looks,
            pc.azimuth_looks,
            const.NON_INTERACTIVE,
        )

        pg.offset_pwr(
            ic.r_primary_slc,  # single-look complex image 1 (reference)
            ic.r_secondary_slc,  # single-look complex image 2
            ic.r_primary_slc_par,  # SLC-1 ISP image parameter file
            ic.r_secondary_slc_par,  # SLC-2 ISP image parameter file
            ic.ifg_off,  # ISP offset/interferogram parameter file
            ic.ifg_offs,  # (output) offset estimates in range and azimuth (fcomplex)
            ic.ifg_ccp,  # (output) cross-correlation of each patch (0.0->1.0) (float)
            const.RANGE_PATCH_SIZE,
            const.AZIMUTH_PATCH_SIZE,
            const.NOT_PROVIDED,  # (output) range and azimuth offsets and cross-correlation data
            const.OFFSET_PWR_OVERSAMPLING_FACTOR,  # n_ovr (SLC oversampling factor)
            const.NUM_OFFSET_ESTIMATES_RANGE,
            const.NUM_OFFSET_ESTIMATES_AZIMUTH,
            const.CROSS_CORRELATION_THRESHOLD,
        )

        pg.offset_fit(
            ic.ifg_offs,
            ic.ifg_ccp,
            ic.ifg_off,  # TODO: should ifg_off be renamed ifg_off_par in settings? MG: good idea, it is a 'par' file
            ic.ifg_coffs,
            ic.ifg_coffsets,
        )

    # Create differential interferogram parameter file
    pg.create_diff_par(
        ic.ifg_off,
        const.NOT_PROVIDED,
        ic.ifg_diff_par,
        const.DIFF_PAR_OFFSET,
        const.NON_INTERACTIVE,
    )


def initial_flattened_ifg(pc: ProcConfig, ic: InterferogramPaths, dc: DEMPaths) -> Path:
    """
    Generate initial flattened interferogram by:
        i) calculating initial baseline model using orbit state vectors;
        ii) simulate phase due to orbital geometry and topography;
        iii) form the initial flattened interferogram.
    :param pc: ProcConfig obj
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :returns: The path to the ifg produced
    """
    LOG.info(f"Generating initial flattened interferogram")

    LOG.debug("Calculate initial baseline of interferogram using the annotated orbital state vectors")

    # the baseline is the spatial distance between the two satellite positions at the time of
    # acquisition of first and second images.

    pg.base_orbit(
        ic.r_primary_slc_par,
        ic.r_secondary_slc_par,
        ic.ifg_base_init,
    )

    LOG.debug("Simulate phase from the DEM & linear baseline model")

    # linear baseline model may be inadequate for longer scenes, in which case use phase_sim_orb

    pg.phase_sim_orb(
        ic.r_primary_slc_par,
        ic.r_secondary_slc_par,
        ic.ifg_off,
        dc.rdc_dem,
        ic.ifg_sim_unw0,
        ic.r_primary_slc_par,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.INT_MODE_REPEAT_PASS,
        const.PHASE_OFFSET_MODE_SUBTRACT_PHASE,
    )

    LOG.debug("Calculate initial flattened interferogram (baselines from orbit)")

    # Multi-look complex interferogram generation from co-registered SLC data and a simulated
    # interferogram derived from a DEM.

    pg.SLC_diff_intf(
        ic.r_primary_slc,
        ic.r_secondary_slc,
        ic.r_primary_slc_par,
        ic.r_secondary_slc_par,
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

    LOG.debug("Finished generating initial interferogram")

    return ic.ifg_flat0


def refined_flattened_ifg(pc: ProcConfig, ic: InterferogramPaths, dc: DEMPaths, ifg_file: Path) -> Path:
    """
    Generate refined flattened interferogram by:
        i) refining the initial baseline model by analysing the fringe rate in initial flattened interferogram;
        ii) simulate phase due to refined baseline and topography;
        iii) form a refined flattened interferogram.
    :param pc: ProcConfig obj
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :returns: The path to the ifg produced
    """
    LOG.debug(f"Estimate residual baseline from the fringe rate of differential interferogram (using FFT)")

    pg.base_init(
        ic.r_primary_slc_par,
        const.NOT_PROVIDED,
        ic.ifg_off,
        ifg_file,
        ic.ifg_base_res,
        const.BASE_INIT_METHOD_4,
    )

    # Add residual baseline estimate to initial estimate
    pg.base_add(
        ic.ifg_base_init,
        ic.ifg_base_res,
        ic.ifg_base,
        const.BASE_ADD_MODE_ADD,
    )

    # Simulate the phase from the DEM and refined baseline model
    pg.phase_sim(
        ic.r_primary_slc_par,
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

    # Calculate second refined flattened interferogram (baselines refined using fringe rate)
    pg.SLC_diff_intf(
        ic.r_primary_slc,
        ic.r_secondary_slc,
        ic.r_primary_slc_par,
        ic.r_secondary_slc_par,
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

    return ic.ifg_flat1


# NB: this function is a bit long and ugly due to the volume of chained calls for the workflow
def precise_flattened_ifg(
    pc: ProcConfig,
    ic: InterferogramPaths,
    dc: DEMPaths,
    tc: TempFilePaths,
    ifg_file: Path,
    ifg_width: int,
    land_center: Optional[Tuple[int, int]] = None,
) -> Path:
    """
    Generate precise flattened interferogram by:
        i) identify ground control points (GCP's) in regions of high coherence;
        ii) extract unwrapped phase at the GCP's;
        iii) calculate precision baseline from GCP phase data;
        iv) simulate phase due to precision baseline and topography;
        v) form the precise flattened interferogram.
    :param pc: ProcConfig obj
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :param tc: TempFilePaths obj
    :param ifg_width:
    :returns: The path to the ifg produced
    """
    LOG.info("** Starting precise_flattened_ifg(...)")

    LOG.debug(
        f"Multilook the flattened interferogram {ifg_file} to produce {ic.ifg_flat10} with NUM_RANGE_LOOKS={const.NUM_RANGE_LOOKS} and NUM_AZIMUTH_LOOKS={const.NUM_AZIMUTH_LOOKS}"
    )

    pg.multi_cpx(
        ifg_file,
        ic.ifg_off,
        ic.ifg_flat10,
        ic.ifg_off10,
        const.NUM_RANGE_LOOKS,
        const.NUM_AZIMUTH_LOOKS,
        const.NOT_PROVIDED,
        const.DISPLAY_TO_EOF,
    )

    width10 = get_width10(ic.ifg_off10)

    LOG.debug("Generate the coherence image {ic.ifg_flat_coh10} using cc_wave")

    pg.cc_wave(
        ic.ifg_flat10,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        ic.ifg_flat_coh10,
        width10,
        const.BX,
        const.BY,
        const.ESTIMATION_WINDOW_TRIANGULAR,
    )

    LOG.debug(
        f"Generate validity mask {ic.ifg_float_coh10_mask} with coherence threshold MASKING_COHERENCE_THRESHOLD={const.MASKING_COHERENCE_THRESHOLD}"
    )

    pg.rascc_mask(
        ic.ifg_flat_coh10,
        const.NOT_PROVIDED,
        width10,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.DISPLAY_TO_EOF,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.MASKING_COHERENCE_THRESHOLD,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.MASKING_COHERENCE_THRESHOLD,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        ic.ifg_flat_coh10_mask,
    )

    # Perform unwrapping
    r_init = const.NOT_PROVIDED
    az_init = const.NOT_PROVIDED

    if land_center is not None:
        r_init = int(land_center[0] / const.NUM_RANGE_LOOKS + 0.5)
        LOG.debug(f"land_center defined so setting r_init={r_init} in mcf")
        az_init = int(land_center[1] / const.NUM_AZIMUTH_LOOKS + 0.5)
        LOG.debug(f"land_center defined so setting az_init={az_init} in mcf")

    pg.mcf(
        ic.ifg_flat10,
        ic.ifg_flat_coh10,
        ic.ifg_flat_coh10_mask,
        tc.ifg_flat10_unw,
        width10,
        const.TRIANGULATION_MODE_DELAUNAY,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NUM_RANGE_PATCHES,
        const.NUM_AZIMUTH_PATCHES,
        const.NOT_PROVIDED,
        r_init,
        az_init,
    )

    # Oversample unwrapped interferogram to original resolution
    pg.multi_real(
        tc.ifg_flat10_unw,
        ic.ifg_off10,
        tc.ifg_flat1_unw,
        ic.ifg_off,
        const.RANGE_LOOKS_MAGNIFICATION,
        const.AZIMUTH_LOOKS_MAGNIFICATION,
        const.NOT_PROVIDED,  # line offset
        const.DISPLAY_TO_EOF,
    )

    # Add full-res unwrapped phase to simulated phase
    pg.sub_phase(
        tc.ifg_flat1_unw,
        ic.ifg_sim_unw1,
        ic.ifg_diff_par,
        tc.ifg_flat_diff_int_unw,
        const.DTYPE_FLOAT,
        const.SUB_PHASE_ADD_PHASE_MODE,
    )

    # calculate coherence of original flattened interferogram
    pg.cc_wave(
        ifg_file,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        ic.ifg_flat_coh0,
        ifg_width,
        pc.ifg_coherence_window,
        pc.ifg_coherence_window,
        const.ESTIMATION_WINDOW_TRIANGULAR,
    )

    # generate validity mask for GCP selection
    pg.rascc_mask(
        ic.ifg_flat_coh0,
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
        ic.ifg_flat_coh0_mask,
    )

    # select GCPs from high coherence areas
    pg.extract_gcp(
        dc.rdc_dem,
        ic.ifg_off,
        ic.ifg_gcp,
        const.NUM_GCP_POINTS_RANGE,
        const.NUM_GCP_POINTS_AZIMUTH,
        ic.ifg_flat_coh0_mask,
    )

    # extract phase at GCPs
    pg.gcp_phase(
        tc.ifg_flat_diff_int_unw,
        ic.ifg_off,
        ic.ifg_gcp,
        ic.ifg_gcp_ph,
        const.GCP_PHASE_WINDOW_SIZE,
    )

    # Calculate precision baseline from GCP phase data
    pg.base_ls(
        ic.r_primary_slc_par,
        ic.ifg_off,
        ic.ifg_gcp_ph,
        ic.ifg_base,
        const.NOT_PROVIDED,  # ph_flag
        const.NOT_PROVIDED,  # bc_flag
        const.NOT_PROVIDED,  # bn_flag
        const.NOT_PROVIDED,  # bcdot_flag
        const.BASE_LS_ESTIMATE_FROM_DATA,  # bndot_flag
        const.NOT_PROVIDED,  # bperp_min
    )

    # Simulate the phase from the DEM and precision baseline model.
    pg.phase_sim(
        ic.r_primary_slc_par,
        ic.ifg_off,
        ic.ifg_base,
        dc.rdc_dem,
        ic.ifg_sim_unw,
        const.NOT_PROVIDED,  # ph_flag
        const.B_FLAG_PRECISION_BASELINE,
    )

    # subtract simulated phase ('ifg_flat1' was originally 'ifg', but this file is no longer created)
    pg.sub_phase(
        ifg_file,
        ic.ifg_sim_unw,
        ic.ifg_diff_par,
        ic.ifg_flat,
        const.DTYPE_FCOMPLEX,
        const.SUB_PHASE_SUBTRACT_MODE,
    )

    # Calculate final flattened interferogram with common band filtering (diff ifg generation from
    # co-registered SLCs and a simulated interferogram)
    pg.SLC_diff_intf(
        ic.r_primary_slc,
        ic.r_secondary_slc,
        ic.r_primary_slc_par,
        ic.r_secondary_slc_par,
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

    return ic.ifg_flat


def get_width10(ifg_off10_path: Path) -> int:
    """
    Return range/sample width from ifg_off10
    :param ifg_off10_path: Path type obj
    :return: width as integer
    """

    with ifg_off10_path.open() as f:
        for line in f.readlines():
            if const.MatchStrings.IFG_RANGE_SAMPLES.value in line:
                _, value = line.split()
                LOG.debug(f"Obtaining width of {value} from {ifg_off10_path}")
                return int(value)

    msg = 'Cannot locate "{}" value in ifg offsets10 file'
    raise ProcessIfgException(msg.format(const.MatchStrings.IFG_RANGE_SAMPLES.value))


def calc_bperp_coh_filt(
    pc: ProcConfig, ic: InterferogramPaths, ifg_file: Path, ifg_baseline: Path, ifg_width: int
) -> None:
    """
    Calculate:
        i) perpendicular baselines from baseline model;
        ii) interferometric coherence of the flattened interferogram;
        iii) filtered interferogram.
    :param pc: ProcConfig obj
    :param ic: InterferogramPaths obj
    :param ifg_file: The path to the input ifg to process
    :param ifg_baseline: The path to the input baseline file
    :param ifg_width:
    :return:
    """
    LOG.debug("* Starting calc_bperp_cog_filt(...)")

    # Three flattened interferogram functions:
    # A = initial; B = refined; C = precise
    #
    # Running combinations could be:
    # i)   A only
    # ii)  A + B
    # iii) A + B + C
    #
    # ifg_file should point to the appropriate output depending on what combination was run

    if not ifg_file.exists():
        msg = f"cannot locate interferogram: {ifg_file}"
        LOG.error(msg, missing_file=ifg_file)
        raise ProcessIfgException(msg)

    LOG.debug("Calculating perpendicular baselines")

    _, cout, _ = pg.base_perp(ifg_baseline, ic.r_primary_slc_par, ic.ifg_off)

    LOG.debug(f"Copying output to bperp file {ic.ifg_bperp} instead of rerunning base_perp")

    try:
        with ic.ifg_bperp.open("w") as f:
            f.writelines(cout)
    except IOError as ex:
        msg = "Failed to write ifg_bperp"
        LOG.error(msg, exception=str(ex))
        raise ex

    LOG.debug(f"Generating coherence of flattened interferogram {ifg_file} and storing in {ic.ifg_flat_coh}")

    # MG: WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING COHERENCE OPTIMISATION

    pg.cc_wave(
        ifg_file,
        ic.r_primary_mli,
        ic.r_secondary_mli,
        ic.ifg_flat_coh,
        ifg_width,
        pc.ifg_coherence_window,
        pc.ifg_coherence_window,
        const.ESTIMATION_WINDOW_TRIANGULAR,
    )

    LOG.debug(f"Smoothing the flattened interferogram {ifg_file} using a Goldstein-Werner filter and saving in {ic.ifg_filt}")

    pg.adf(
        ifg_file,
        ic.ifg_filt,
        ic.ifg_filt_coh,
        ifg_width,
        pc.ifg_exponent,
        pc.ifg_filtering_window,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
    )


def calc_unw(
    pc: ProcConfig,
    ic: InterferogramPaths,
    tc: TempFilePaths,
    ifg_width: int,
    land_center: Optional[Tuple[int, int]] = None,
) -> None:
    """
    Generate the unwrapped outputs using the MCF algorithm.

    :param pc: ProcConfig obj
    :param ic: InterferogramPaths obj
    :param tc: TempFileConfig obj
    :param ifg_width:
    """

    if not ic.ifg_filt.exists():
        msg = "cannot locate (*.filt) filtered interferogram: {}. Was FILT executed?".format(ic.ifg_filt)
        LOG.error(msg, missing_file=ic.ifg_filt)
        raise ProcessIfgException(msg)

    pg.rascc_mask(
        ic.ifg_filt_coh,  # <cc> coherence image (float)
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

    if const.RASCC_MIN_THINNING_THRESHOLD <= int(pc.multi_look) <= const.RASCC_THINNING_THRESHOLD:
        LOG.debug(
            f"const.RASCC_MIN_THINNING_THRESHOLD ({const.RASCC_MIN_THINNING_THRESHOLD}) "
            f"<= multi_look: {int(pc.multi_look)} <= const.RASCC_THINNING_THRESHOLD "
            f"({const.RASCC_THINNING_THRESHOLD}), so calling calc_unw_thinning(...)"
        )
        unwrapped_tmp = calc_unw_thinning(pc, ic, tc, ifg_width, land_center=land_center)
    else:
        msg = (
            "Processing for unwrapping the full interferogram without masking not implemented. "
            "GA's InSAR team use multi_look=2 for Sentinel-1 ARD product generation."
        )
        LOG.error(msg)
        raise NotImplementedError(msg)

    if pc.ifg_unw_mask.lower() == const.YES:
        LOG.debug("Mask unwrapped interferogram for low coherence areas below threshold")
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
    ic: InterferogramPaths,
    tc: TempFilePaths,
    ifg_width: int,
    num_sampling_reduction_runs: int = 3,
    land_center: Optional[Tuple[int, int]] = None,
) -> Path:
    """
    TODO docs
    :param pc: ProcConfig obj
    :param ic: InterferogramPaths obj
    :param tc: TempFileConfig obj
    :param ifg_width:
    :param num_sampling_reduction_runs:
    :return: Path of unwrapped ifg (tmp file)
    """
    # Use rascc_mask_thinning to weed the validity mask for large scenes. this can unwrap a sparser
    # network which can be interpolated and used as a model for unwrapping the full interferogram
    thresh_1st = float(pc.ifg_coherence_threshold) + const.RASCC_THRESHOLD_INCREMENT
    thresh_max = thresh_1st + const.RASCC_THRESHOLD_INCREMENT

    pg.rascc_mask_thinning(
        ic.ifg_mask,  # validity mask
        ic.ifg_filt_coh,  # file for adaptive sampling reduction, e.g. coherence (float)
        ifg_width,
        ic.ifg_mask_thin,  # (output) validity mask with reduced sampling
        num_sampling_reduction_runs,
        pc.ifg_coherence_threshold,
        thresh_1st,
        thresh_max,
    )

    # Phase unwrapping using Minimum Cost Flow (MCF) and triangulation
    pg.mcf(
        ic.ifg_filt,  # interf: interferogram
        ic.ifg_filt_coh,  # wgt: weight factors file (float)
        ic.ifg_mask_thin,  # mask: validity mask file
        ic.ifg_unw_thin,  # unw: (output) unwrapped phase image (*_unw) (float)
        ifg_width,  # width: number of samples per row
        const.TRIANGULATION_MODE_DELAUNAY,  # tri_mode: triangulation mode, 0: filled triangular mesh 1: Delaunay
        const.NOT_PROVIDED,  # roff: offset to starting range of section to unwrap (default: 0)
        const.NOT_PROVIDED,  # loff: offset to starting line of section to unwrap (default: 0)
        const.NOT_PROVIDED,  # nr: number of range samples of section to unwrap (default(-): width-roff)
        const.NOT_PROVIDED,  # nlines: number of lines of section to unwrap (default(-): total number of lines -loff)
        pc.ifg_patches_range,  # npat_r: number of patches (tiles) in range
        pc.ifg_patches_azimuth,  # npat_az: number of patches (tiles) in azimuth
        pc.ifg_patches_overlap_px,  # ovrlap: overlap between patches in pixels (>= 7, default(-): 512)
        land_center[0]
        if land_center
        else pc.ifg_ref_point_range,  # r_init: phase reference range offset (default(-): roff)
        land_center[1]
        if land_center
        else pc.ifg_ref_point_azimuth,  # az_init: phase reference azimuth offset (default(-): loff)
        const.INIT_FLAG_SET_PHASE_0_AT_INITIAL,  # init_flag: flag to set phase at reference point (default 0: use initial point phase value)
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
    pg.unw_model(
        ic.ifg_filt,  # complex interferogram
        ic.ifg_unw_model,  # approximate unwrapped phase model (float)
        tc.unwrapped_filtered_ifg,  # output file
        ifg_width,
        pc.ifg_ref_point_range,  # xinit
        pc.ifg_ref_point_azimuth,  # # yinit
        const.REF_POINT_PHASE,  # reference point phase (radians)
    )

    return tc.unwrapped_filtered_ifg


def do_geocode(
    pc: ProcConfig,
    ic: InterferogramPaths,
    dc: DEMPaths,
    tc: TempFilePaths,
    ifg_width: int,
    dtype_out: int = const.DTYPE_FCOMPLEX,
) -> None:
    """
    Perform the geocoding of files.

    :param pc: ProcConfig obj
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :param tc: TempFileConfig obj
    :param ifg_width:
    :param dtype_out:
    """

    width_in = get_width_in(dc.dem_diff)

    LOG.debug(f"Obtained width_in={width_in} from {dc.dem_diff}")

    # sanity check the widths match from separate data sources
    if width_in != ifg_width:
        raise ProcessIfgException("width_in != ifg_width. Check for a processing error")

    width_out = get_width_out(dc.geo_dem_par)

    LOG.debug(f"Obtained width_out={width_out} from {dc.geo_dem_par}")

    if ic.ifg_unw.exists():
        LOG.info(f"Geocoding unwrapped ifg {ic.ifg_unw} as {ic.ifg_unw_geocode_out}")
        geocode_unwrapped_ifg(ic, dc, tc, width_in, width_out)

    if ic.ifg_flat.exists():
        LOG.info(f"Geocoding flattened ifg {ic.ifg_flat} as {ic.ifg_flat_geocode_out}")
        geocode_flattened_ifg(ic, dc, tc, width_in, width_out)

    if ic.ifg_filt.exists():
        LOG.info(f"Geocoding filtered ifg {ic.ifg_filt}")
        geocode_filtered_ifg(ic, dc, tc, width_in, width_out)

    if ic.ifg_flat_coh.exists():
        LOG.info(f"Geocoding flat coherence {ic.ifg_flat_coh} as {ic.ifg_flat_coh_geocode_out}")
        geocode_flat_coherence_file(ic, dc, tc, width_in, width_out)

    if ic.ifg_filt_coh.exists():
        LOG.info(f"Geocoding filtered coherence {ic.ifg_filt_coh} as {ic.ifg_filt_coh_geocode_out}")
        geocode_filtered_coherence_file(ic, dc, tc, width_in, width_out)

    # Geotiff geocoded outputs
    if pc.ifg_geotiff:

        # unw
        if ic.ifg_unw.exists():
            LOG.info(f"Converting {ic.ifg_unw_geocode_out} to {ic.ifg_unw_geocode_out_tiff}")
            pg.data2geotiff(
                dc.geo_dem_par,
                ic.ifg_unw_geocode_out,
                4,
                ic.ifg_unw_geocode_out_tiff,
            )

        # flat ifg
        if ic.ifg_flat.exists():
            LOG.info(f"Converting {ic.ifg_flat_geocode_out} to {ic.ifg_flat_geocode_out_tiff}")
            pg.data2geotiff(
                dc.geo_dem_par,
                ic.ifg_flat_geocode_out,
                4,
                ic.ifg_flat_geocode_out_tiff,
            )

        # filt ifg
        if ic.ifg_filt.exists():
            LOG.info(f"Converting {ic.ifg_filt_geocode_out} to {ic.ifg_filt_geocode_out_tiff}")
            pg.data2geotiff(
                dc.geo_dem_par,
                ic.ifg_filt_geocode_out,
                4,
                ic.ifg_filt_geocode_out_tiff,
            )

        # flat coh
        if ic.ifg_flat_coh.exists():
            LOG.info(f"Converting {ic.ifg_flat_coh_geocode_out} to {ic.ifg_flat_coh_geocode_out_tiff}")
            pg.data2geotiff(
                dc.geo_dem_par,
                ic.ifg_flat_coh_geocode_out,
                2,
                ic.ifg_flat_coh_geocode_out_tiff,
            )

        # filt coh
        if ic.ifg_filt_coh.exists():
            LOG.info(f"Converting {ic.ifg_filt_coh_geocode_out} to {ic.ifg_filt_coh_geocode_out_tiff}")
            pg.data2geotiff(
                dc.geo_dem_par,
                ic.ifg_filt_coh_geocode_out,
                2,
                ic.ifg_filt_coh_geocode_out_tiff,
            )

    # TF: also remove all binaries and .ras files to save disc space
    #     keep flat.int since this is currently used as input for stamps processing
    # FIXME: move paths to dedicated mgmt class

    current = Path(".")
    all_paths = [tuple(current.glob(pattern)) for pattern in const.TEMP_FILE_GLOBS]

    # for path in all_paths:
    #    remove_files(*path)


def get_width_in(fn: Path) -> int:
    """
    Return range/sample width from dem diff file.

    Obtains width from independent source to get_ifg_width(), allowing errors to be identified if
    there are problems with a particular processing step.
    """
    with open(fn, "r") as fd:
        for line in fd.readlines():
            if const.RANGE_SAMPLE_1 in line:
                _, value = line.split()
                return int(value)

    msg = 'Cannot locate "{}" value in DEM diff file'.format(const.RANGE_SAMPLE_1)
    raise ProcessIfgException(msg)


def get_width_out(fn: Path) -> int:
    """
    Return range field from geo_dem_par file
    """
    with open(fn, "r") as fd:
        for line in fd.readlines():
            if const.DEM_GEO_WIDTH in line:
                _, value = line.split()
                return int(value)

    msg = 'Cannot locate "{}" value in DEM geo param file'.format(const.DEM_GEO_WIDTH)
    raise ProcessIfgException(msg)


def geocode_unwrapped_ifg(
    ic: InterferogramPaths, dc: DEMPaths, tc: TempFilePaths, width_in: int, width_out: int
) -> None:
    """
    TODO docs
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :param tc: TempFileConfig obj
    :param width_in:
    :param width_out:
    """
    # Use bicubic spline interpolation for geocoded unwrapped interferogram
    pg.geocode_back(ic.ifg_unw, width_in, dc.dem_lt_fine, tc.geocode_unwrapped_ifg, width_out)
    pg.mask_data(tc.geocode_unwrapped_ifg, width_out, ic.ifg_unw_geocode_out, dc.seamask)

    ## make quick-look png image
    # rasrmg_wrapper(ic.ifg_unw_geocode_out, width_out, ic.ifg_unw_geocode_2pi_bmp, pixavr=5, pixavaz=5, ph_scale=1.0)
    # rasrmg_wrapper(ic.ifg_unw_geocode_out, width_out, ic.ifg_unw_geocode_6pi_bmp, pixavr=5, pixavaz=5, ph_scale=0.33333)
    # convert(ic.ifg_unw_geocode_2pi_bmp)
    # convert(ic.ifg_unw_geocode_6pi_bmp)
    # kml_map(ic.ifg_unw_geocode_2pi_png, dc.geo_dem_par)
    # remove_files(ic.ifg_unw_geocode_2pi_bmp, ic.ifg_unw_geocode_6pi_bmp, tc.geocode_unwrapped_ifg)


def geocode_flattened_ifg(
    ic: InterferogramPaths,
    dc: DEMPaths,
    tc: TempFilePaths,
    width_in: int,
    width_out: int,
) -> None:
    """
    TODO docs
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :param tc: TempFileConfig obj
    :param width_in:
    :param width_out:
    """

    LOG.debug(
        f"Geocoding flat interferogram {ic.ifg_flat} using LUT {dc.dem_lt_fine}, width_in={width_in} width_out={width_out}"
    )

    pg.geocode_back(
        ic.ifg_flat,
        width_in,
        dc.dem_lt_fine,
        tc.geocode_flat_ifg_cpx,
        width_out,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        1,
    )

    LOG.debug(
        f"Converting from complex to float and extracting phase: {tc.geocode_flat_ifg_cpx} to {tc.geocode_flat_ifg}"
    )

    pg.cpx_to_real(tc.geocode_flat_ifg_cpx, tc.geocode_flat_ifg, width_out, const.CPX_TO_REAL_OUTPUT_TYPE_PHASE)

    LOG.debug(f"Applying seamask {dc.seamask} on phase {tc.geocode_flat_ifg}, writing to {ic.ifg_flat_geocode_out}")

    pg.mask_data(tc.geocode_flat_ifg, width_out, ic.ifg_flat_geocode_out, dc.seamask)

    fn = quicklook_real(ic.ifg_flat_geocode_out, width_out)

    LOG.debug(f"Made quicklook .png image {fn}")

    # rasrmg_wrapper(ic.ifg_flat_geocode_out, width_out, ic.ifg_flat_geocode_bmp, pixavr=5, pixavaz=5)
    # convert(ic.ifg_flat_geocode_bmp)
    # kml_map(ic.ifg_flat_geocode_png, dc.geo_dem_par)
    # remove_files(ic.ifg_flat_geocode_bmp, tc.geocode_flat_ifg, ic.ifg_flat_float)


def geocode_filtered_ifg(
    ic: InterferogramPaths, dc: DEMPaths, tc: TempFilePaths, width_in: int, width_out: int
) -> None:
    """
    TODO docs
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :param tc: TempFileConfig obj
    :param width_in:
    :param width_out:
    :return:
    """

    LOG.debug(
        f"Geocoding filtered interferogram {ic.ifg_filt} as {tc.geocode_filt_ifg_cpx}, width_in={width_in} width_out={width_out} dtype={1}"
    )

    pg.geocode_back(
        ic.ifg_filt,
        width_in,
        dc.dem_lt_fine,
        tc.geocode_filt_ifg_cpx,
        width_out,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        1,
    )

    LOG.debug(f"Converting complex data to real data (phase), {tc.geocode_filt_ifg_cpx} to {tc.geocode_filt_ifg}")

    pg.cpx_to_real(tc.geocode_filt_ifg_cpx, tc.geocode_filt_ifg, width_out, const.CPX_TO_REAL_OUTPUT_TYPE_PHASE)

    LOG.debug(f"Applying seamask to phase data, {tc.geocode_filt_ifg} to {ic.ifg_filt_geocode_out}")

    pg.mask_data(tc.geocode_filt_ifg, width_out, ic.ifg_filt_geocode_out, dc.seamask)

    fn = quicklook_real(ic.ifg_filt_geocode_out, width_out)

    LOG.debug(f"Made quicklook .png image {fn}")


def geocode_flat_coherence_file(
    ic: InterferogramPaths,
    dc: DEMPaths,
    tc: TempFilePaths,
    width_in: int,
    width_out: int,
) -> None:
    """
    TODO docs
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :param tc: TempFileConfig obj
    :param width_in:
    :param width_out:
    """

    pg.geocode_back(
        ic.ifg_flat_coh,
        width_in,
        dc.dem_lt_fine,
        ic.ifg_flat_coh_geocode_out,
        width_out,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        0,
    )

    fn = quicklook_real(ic.ifg_flat_coh_geocode_out, width_out, min=0., max=1.0)

    LOG.debug(f"Made quicklook .png image {fn}")


def geocode_filtered_coherence_file(
    ic: InterferogramPaths,
    dc: DEMPaths,
    tc: TempFilePaths,
    width_in: int,
    width_out: int,
) -> None:
    """
    TODO: docs
    :param ic: InterferogramPaths obj
    :param dc: DEMPaths obj
    :param tc: TempFileConfig obj
    :param width_in:
    :param width_out:
    """
    LOG.debug(f"Geocoding filtered coherence {ic.ifg_filt_coh} to {ic.ifg_filt_coh_geocode_out}")

    pg.geocode_back(
        ic.ifg_filt_coh,
        width_in,
        dc.dem_lt_fine,
        ic.ifg_filt_coh_geocode_out,
        width_out,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        0,
    )

    LOG.debug(f"Applying seamask to filtered coherence {ic.ifg_filt_coh_geocode_out}")

    with TemporaryDirectory() as tmpdir:
        srcfn = tmpdir / "coh_premasked"
        ic.ifg_filt_coh_geocode_out.rename(srcfn)
        pg.mask_data(srcfn, width_out, ic.ifg_filt_coh_geocode_out, dc.seamask)

    fn = quicklook_real(ic.ifg_filt_coh_geocode_out, width_out, min=0, max=1.0)

    LOG.debug(f"Made quicklook .png image {fn}")


# def rasrmg_wrapper(
#    input_file: Union[Path, str],
#    width_out: int,
#    output_file: Union[Path, str],
#    pwr=const.NOT_PROVIDED,
#    start_pwr=const.DEFAULT_STARTING_LINE,
#    start_unw=const.DEFAULT_STARTING_LINE,
#    nlines=const.DISPLAY_TO_EOF,
#    pixavr=const.RAS_PIXEL_AVERAGE_RANGE,
#    pixavaz=const.RAS_PIXEL_AVERAGE_AZIMUTH,
#    ph_scale=const.RAS_PH_SCALE,
#    scale=const.RAS_SCALE,
#    exp=const.RAS_EXP,
#    ph_offset=const.RAS_PH_OFFSET,
#    leftright=const.LEFT_RIGHT_FLIPPING_NORMAL,
# ) -> None:
#    """
#    Helper function to default rasrmg args to Geoscience Australia InSAR defaults.
#
#    Generate 8-bit raster graphics image from unwrapped phase & intensity data
#    TODO: skips some variables in docs (cc, start_cc & cc_min)
#
#    :param input_file: unwrapped phase data
#    :param width_out: samples per row of unwrapped phase and intensity files
#    :param output_file:
#    :param pwr: intensity data (float, enter - for none)
#    :param start_pwr:starting line of unwrapped phase file ('-' for default: 1)
#    :param start_unw: starting line of intensity file ('-' for default: 1)
#    :param nlines: number of lines to display (- or 0 for default: to end of file)
#    :param pixavr: number of pixels to average in range
#    :param pixavaz: number of pixels to average in azimuth
#    :param ph_scale: phase display scale factor (enter - for default: 0.33333)
#    :param scale: pwr display scale factor (- for default: 1.0)
#    :param exp: pwr display exponent (- for default: default: 0.35)
#    :param ph_offset: phase offset in radians subtracted from unw ( - is default: 0.0)
#    :param leftright: left/right mirror image (- is default, 1: normal (default), -1: mirror image)
#    :return:
#    """
#
#    # docs from gadi "/g/data/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-20191203/DISP/bin/rasrmg -h"
#    # as they do not exist as HTML in the GAMMA install
#    pg.rasrmg(
#        input_file,
#        pwr,
#        width_out,
#        start_unw,
#        start_pwr,
#        nlines,
#        pixavr,
#        pixavaz,
#        ph_scale,
#        scale,
#        exp,
#        ph_offset,
#        leftright,
#        output_file,
#    )
#
#
# def rascc_wrapper(
#    input_file: Union[Path, str],
#    width_out: int,
#    output_file: Union[Path, str],
#    pwr=const.NOT_PROVIDED,
#    start_cc=const.DEFAULT_STARTING_LINE,
#    start_pwr=const.DEFAULT_STARTING_LINE,
#    nlines=const.DISPLAY_TO_EOF,
#    pixavr=const.RAS_PIXEL_AVERAGE_RANGE,
#    pixavaz=const.RAS_PIXEL_AVERAGE_AZIMUTH,
#    cmin=const.RASCC_MIN_CORRELATION,
#    cmax=const.RASCC_MAX_CORRELATION,
#    scale=const.RAS_SCALE,
#    exp=const.RAS_EXP,
#    leftright=const.LEFT_RIGHT_FLIPPING_NORMAL,
# ):
#    """
#    Helper function to default rascc args to Geoscience Australia InSAR defaults.
#
#    Generate 8-bit raster graphics image of correlation coefficient + intensity data
#
#    :param input_file:
#    :param width_out:
#    :param output_file:
#    :param pwr:
#    :param start_cc:
#    :param start_pwr:
#    :param nlines:
#    :param pixavr:
#    :param pixavaz:
#    :param cmin:
#    :param cmax:
#    :param scale:
#    :param exp:
#    :param leftright:
#    :return:
#    """
#    # docs from gadi "/g/data/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-20191203/DISP/bin/rascc -h"
#    # as they do not exist as HTML in the GAMMA install
#    pg.rascc(
#        input_file,
#        pwr,
#        width_out,
#        start_cc,
#        start_pwr,
#        nlines,
#        pixavr,
#        pixavaz,
#        cmin,
#        cmax,
#        scale,
#        exp,
#        leftright,
#        output_file,
#    )
#
#
# def kml_map(input_file: Path, dem_par: Union[Path, str], output_file=None) -> None:
#    """
#    Generates KML format XML with link to an image using geometry from a dem_par.
#    :param input_file:
#    :param dem_par:
#    :param output_file:
#    :return:
#    """
#    if output_file is None:
#        output_file = append_suffix(input_file, ".kml")
#
#    pg.kml_map(input_file, dem_par, output_file)
#
#
# def remove_files(*args) -> None:
#    """
#    Attempts to remove the given files, logging any failures
#    :param args: Path like objects
#    """
#    for path in args:
#        try:
#            if path:
#                path.unlink()
#        except FileNotFoundError:
#            LOG.error("Could not delete {}".format(path))
#
#        # TODO: add more exception handlers?
