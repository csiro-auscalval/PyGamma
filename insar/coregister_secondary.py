from pathlib import Path
import structlog

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.path_util import append_suffix
import insar.constant as const
from insar.project import ProcConfig
from insar.coreg_utils import create_diff_par, grep_stdout
from insar.path_util import par_file

class CoregisterSlcException(Exception):
    pass


_LOG = structlog.get_logger("insar")
pg = GammaInterface(
    subprocess_func=auto_logging_decorator(
        subprocess_wrapper, CoregisterSlcException, _LOG
    )
)

def coregister_secondary(
    proc_config: ProcConfig,
    primary_slc_path: Path,
    primary_mli_path: Path,
    rdc_dem_path: Path,
    secondary_slc_path: Path,
    secondary_mli_path: Path,
    r_secondary_slc_path: Path,
    r_secondary_mli_path: Path,
    rlks: int,
    alks: int
):
    """
    Coregisters the provided secondary scene to a primary scene.

    This implies the secondary scene will be both geocoded and then an offset
    model will be produced which correlates every pixel in the secondary scene
    to a pixel in the primary scene.

    Coregistration is done at the resolution of MLIs (which is why the function
    takes both full-res and multi-looked primary SLC data).

    Like all coregistration functions, this also multi-looks the final products.

    :param proc_config:
        The configuration settings to be used for processing.
    :param primary_slc_path:
        The path to the primary scene's SLC file.
    :param primary_mli_path:
        The path to the primary scene's MLI file.
    :param rdc_dem_path:
        The DEM to use for coregistration in radar coordinates.

        RDC = "radar coordinates" = "same coordinates as the source SLC data"
        (eg: RDC is slant range geometry for S1 SLC products)
    :param secondary_slc_path:
        The path to the secondary scene's SLC file.
    :param secondary_mli_path:
        The path to the secondary scene's MLI file.
    :param r_secondary_slc_path:
        The output path where the coregistered secondary
        SLC file should be written.
    :param r_secondary_mli_path:
        The output path where the coregistered secondary
        multi-looked file should be written.
    :param rlks:
        The range (x-axis) multi-look factor
    :param alks:
        The aximuth (y-axis) multi-look factor
    """

    primary_slc_par_path = par_file(primary_slc_path)
    primary_mli_par_path = par_file(primary_mli_path)
    secondary_slc_par_path = par_file(secondary_slc_path)
    secondary_mli_par_path = par_file(secondary_mli_path)
    r_secondary_slc_par_path = par_file(r_secondary_slc_path)
    r_secondary_mli_par_path = par_file(r_secondary_mli_path)
    diff_par_path = append_suffix(secondary_slc_path, ".diff.par")

    # Check inputs exist
    input_paths = [
        primary_slc_path,
        primary_slc_par_path,
        primary_mli_path,
        primary_mli_par_path,
        secondary_slc_path,
        secondary_slc_par_path,
        secondary_mli_path,
        secondary_mli_par_path,
    ]

    for p in input_paths:
        if not p.exists():
            raise FileNotFoundError(f"Input path does not exist: {p}")

    # Check outputs do NOT exist (don't want to implicitly overwrite data)
    output_paths = [
        r_secondary_slc_path,
        r_secondary_slc_par_path,
        r_secondary_mli_path,
        r_secondary_mli_par_path,
    ]

    for p in output_paths:
        if p.exists():
            raise FileExistsError(f"Output path already has data at it's location: {p}")

    # Read input sizes
    primary_mli_par = pg.ParFile(str(primary_mli_par_path))
    primary_mli_width = primary_mli_par.get_value("range_samples", dtype=int, index=0)
    priamry_mli_height = primary_mli_par.get_value("azimuth_lines", dtype=int, index=0)

    secondary_mli_par = pg.ParFile(str(secondary_mli_par_path))
    secondary_mli_width = secondary_mli_par.get_value("range_samples", dtype=int, index=0)
    secondary_mli_height = secondary_mli_par.get_value("azimuth_lines", dtype=int, index=0)

    lt_path = r_secondary_slc_path.with_suffix(".lt")
    off_path = r_secondary_slc_path.with_suffix(".off")
    offs_path = r_secondary_slc_path.with_suffix(".offs")
    ccp_path = r_secondary_slc_path.with_suffix(".ccp")
    lt0_path = r_secondary_slc_path.with_suffix(".lt0")
    off0_path = r_secondary_slc_path.with_suffix(".off0")
    offsets_path = r_secondary_slc_path.with_suffix(".offsets")
    # Note: Bash wrote a bunch of stats/info to this file... we don't currently.
    #ovr_path = r_secondary_slc_path.with_suffix(".ovr_results")
    coffs_path = r_secondary_slc_path.with_suffix(".coffs")
    coffsets_path = r_secondary_slc_path.with_suffix(".coffsets")

    # Generate initial lookup table between primary and secondary MLI considering terrain heights from DEM coregistered to primary
    pg.rdc_trans(
        primary_mli_par_path,
        rdc_dem_path,
        secondary_mli_par_path,
        lt0_path
    )

    pg.geocode(
        lt0_path,
        primary_mli_path,
        primary_mli_width,
        r_secondary_mli_path,
        secondary_mli_width,
        secondary_mli_height,
        2,
        0
    )

    # Measure offset and estimate offset polynomials between slave MLI and resampled slave MLI
    num_measurements = proc_config.secondary_offset_measure.split(" ")
    window_sizes = proc_config.coreg_window_size.split(" ")
    cc_thresh = proc_config.secondary_cc_thresh

    create_diff_par(
        secondary_mli_par_path,
        secondary_mli_par_path,
        diff_par_path,
        None,
        num_measurements,
        window_sizes,
        cc_thresh
    )

    # Measure offset between slave MLI and resampled slave MLI
    pg.init_offsetm(
        r_secondary_mli_path,
        secondary_mli_path,
        diff_par_path,
        1,
        1,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        proc_config.secondary_cc_thresh,
        const.NOT_PROVIDED,
        1
    )

    pg.offset_pwrm(
        r_secondary_mli_path,
        secondary_mli_path,
        diff_par_path,
        off0_path,
        ccp_path,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        2
    )

    # Fit the offset using the given number of polynomial coefficients
    pg.offset_fitm(
        off0_path,
        ccp_path,
        diff_par_path,
        coffs_path,
        const.NOT_PROVIDED,
        proc_config.secondary_cc_thresh,
        proc_config.coreg_model_params
    )

    off0_path.unlink()

    # Refinement of initial geocoding look up table
    pg.gc_map_fine(
        lt0_path,
        primary_mli_width,
        diff_par_path,
        lt_path,
    )

    # Resample slave SLC into geometry of primary SLC using lookup table
    pg.SLC_interp_lt(
        secondary_slc_path,
        primary_slc_par_path,
        secondary_slc_par_path,
        lt_path,
        primary_mli_par_path,
        secondary_mli_par_path,
        const.NOT_PROVIDED,
        r_secondary_slc_path,
        r_secondary_slc_par_path
    )

    # set up iterable loop
    num_iters = int(proc_config.coreg_num_iterations)

    for i in range(1, num_iters+1):

        ioff = Path(str(off_path) + str(i))

        # Measure offsets for refinement of lookup table using initially resampled slave SLC
        pg.create_offset(
            primary_slc_par_path,
            r_secondary_slc_par_path,
            ioff,
            1,
            rlks,
            alks,
            0
        )

        pg.offset_pwr(
            primary_slc_path,
            r_secondary_slc_path,
            primary_slc_par_path,
            r_secondary_slc_par_path,
            ioff,
            offs_path,
            ccp_path,
            window_sizes[0],
            window_sizes[1],
            offsets_path,
            proc_config.coreg_oversampling,
            proc_config.coreg_num_windows,
            proc_config.coreg_num_windows,
            proc_config.secondary_cc_thresh
        )

        # Fit polynomial model to offsets
        _, offset_fit_cout, _ = pg.offset_fit(
            offs_path,
            ccp_path,
            ioff,
            const.NOT_PROVIDED,
            coffsets_path,
            proc_config.secondary_cc_thresh,
            proc_config.coreg_model_params,
            0
        )

        # Create blank offset file for first iteration and calculate the total estimated offset
        if i == 1:
            pg.create_offset(
                primary_slc_par_path,
                r_secondary_slc_par_path,
                off0_path,
                1,
                rlks,
                alks,
                0
            )

            pg.offset_add(
                off0_path,
                ioff,
                off_path
            )

        # Calculate the cumulative total estimated offset after first iteration
        else:
            pg.offset_add(
                off_path,
                ioff,
                off_path
            )

        # Perform resampling of slave SLC using lookup table and offset model
        pg.SLC_interp_lt(
            secondary_slc_path,
            primary_slc_par_path,
            secondary_slc_par_path,
            lt_path,
            primary_mli_par_path,
            secondary_mli_par_path,
            off_path,
            r_secondary_slc_path,
            r_secondary_slc_par_path
        )

        # Example: "final range offset poly. coeff.:             -0.00408   5.88056e-07   3.95634e-08  -1.75528e-11"
        azoff = float(grep_stdout(offset_fit_cout, "final azimuth offset poly. coeff.:").split()[5])
        rgoff = float(grep_stdout(offset_fit_cout, "final range offset poly. coeff.:").split()[5])

        _LOG.info(
            "SLC coreg iteration",
            iter=i,
            azoff=azoff,
            rgoff=rgoff
        )

        # If estimated offsets are less than 0.2 of a pixel then break iterable loop
        if abs(azoff) < 0.2 and abs(rgoff) < 0.2:
            break

    # Finally, multi-look our coregistered SLC.
    pg.multi_look(
        r_secondary_slc_path,
        r_secondary_slc_par_path,
        r_secondary_mli_path,
        r_secondary_mli_par_path,
        rlks,
        alks
    )


def apply_coregistration(
    primary_slc_path: Path,
    primary_mli_path: Path,
    secondary_slc_path: Path,
    secondary_mli_path: Path,
    r_secondary_slc_path: Path,
    r_secondary_mli_path: Path,
    lt_path: Path,
    off_path: Path,
    rlks: int,
    alks: int
):
    """
    Applies existing coregistration LUT/offsets to a secondary image.

    This is typically used for non-primary polarised products which we have
    opted to share the coregistration of the primary polarisation (instead of
    coregistering them separately) - this saves on computational complexity.

    Like all coregistration functions, this also multi-looks the final products.

    :param primary_slc_path:
        The path to the primary scene's SLC file.
    :param primary_mli_path:
        The path to the primary scene's MLI file.
    :param secondary_slc_path:
        The path to the secondary scene's SLC file.
    :param secondary_mli_path:
        The path to the secondary scene's MLI file.
    :param r_secondary_slc_path:
        The output path where the coregistered secondary
        SLC file should be written.
    :param r_secondary_mli_path:
        The output path where the coregistered secondary
        multi-looked file should be written.
    :param lt_path:
        The geocoding LUT to be applied for coregistration.
    :param off_path:
        The primary<->secondary offset model for coregistration.
    :param rlks:
        The range (x-axis) multi-look factor
    :param alks:
        The aximuth (y-axis) multi-look factor
    """

    input_files = [
        primary_slc_path,
        primary_mli_path,
        secondary_slc_path,
        secondary_mli_path,
        lt_path,
        off_path
    ]

    for p in input_files:
        if not p.exists():
            raise FileNotFoundError(f"Missing input file: {p}")

    primary_slc_par_path = par_file(primary_slc_path)
    primary_mli_par_path = par_file(primary_mli_path)
    secondary_slc_par_path = par_file(secondary_slc_path)
    secondary_mli_par_path = par_file(secondary_mli_path)
    r_secondary_slc_par_path = par_file(r_secondary_slc_path)
    r_secondary_mli_par_path = par_file(r_secondary_mli_path)

    # Perform resampling of slave SLC using lookup table and offset model
    pg.SLC_interp_lt(
        secondary_slc_path,
        primary_slc_par_path,
        secondary_slc_par_path,
        lt_path,
        primary_mli_par_path,
        secondary_mli_par_path,
        off_path,
        r_secondary_slc_path,
        r_secondary_slc_par_path
    )

    pg.multi_look(
        r_secondary_slc_path,
        r_secondary_slc_par_path,
        r_secondary_mli_path,
        r_secondary_mli_par_path,
        rlks,
        alks
    )
