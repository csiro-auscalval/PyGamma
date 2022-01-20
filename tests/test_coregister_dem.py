from pathlib import Path
import pytest
import insar.constant as const

from tests.fixtures import *

from tests.test_workflow import do_ard_workflow_validation

#import insar.coregister_dem
from insar.project import ARDWorkflow
from insar.coregister_dem import CoregisterDem, CoregisterDemException
from insar.paths.coregistration import CoregisteredPrimaryPaths
from insar.paths.dem import DEMPaths
from insar.stack import load_stack_config
from insar.workflow.luigi.utils import read_rlks_alks
from insar.coreg_utils import rm_file
from insar.logs import logging_directory


def get_coreg_args(stack_dir: Path):
    # Load stack info
    proc_config = load_stack_config(stack_dir)
    # TODO: this isn't really acceptable having to dig into implementation-specific workflow details to get rlks/alks
    ml_file = Path(proc_config.job_path) / 'tasks' / f"{proc_config.stack_id}_createmultilook_status_logs.out"
    rlks, alks = (2, 2)
    if ml_file.exists():
        rlks, alks = read_rlks_alks(ml_file)

    paths = CoregisteredPrimaryPaths(proc_config)
    dem_paths = DEMPaths(proc_config)

    return (rlks, alks), paths, dem_paths


@pytest.fixture
def coreg(pgp, pgmock, s1_proc, s1_test_data_zips):
    """The test harness used for running coregistration tests shared by all tests in this file"""
    # Run a normal backscatter workflow
    source_data = [str(i) for i in s1_test_data_zips]
    pols = ["VV", "VH"]

    out_dir, job_dir, _ = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Backscatter,
        source_data,
        pols,
        s1_proc
    )

    # Load stack info
    (rlks, alks), paths, dem_paths = get_coreg_args(out_dir)

    # Delete all the coregistered products
    rm_file(paths.dem_primary_mli)
    rm_file(paths.dem_primary_mli_par)
    rm_file(paths.r_dem_primary_slc)
    rm_file(paths.r_dem_primary_slc_par)
    rm_file(paths.r_dem_primary_mli)
    rm_file(paths.r_dem_primary_mli_par)

    # Manually re-run coregistration against the SLC data
    pgp.reset_proxy()

    with logging_directory(job_dir):
        coreg = CoregisterDem(
            rlks,
            alks,
            dem_paths.dem,
            paths.dem_primary_slc,
            dem_paths.dem_par,
            paths.dem_primary_slc_par,
            multi_look=2
        )

        yield coreg


def test_valid_data(pgp, coreg):
    coreg.main()

    # coreg fixture should've had 0 errors
    assert pgp.error_count == 0

    paths = coreg.dem_paths

    assert paths.dem_pix_gam.exists()
    assert paths.dem_diff.exists()
    assert paths.dem_lt_fine.exists()
    assert paths.seamask.exists()

    assert paths.dem_lv_theta.exists()
    assert paths.dem_lv_phi.exists()

    assert paths.rdc_dem.exists()
    assert paths.rdc_dem.with_suffix(".png").exists()
    assert paths.dem_rdc_sim_sar.exists()
    assert paths.dem_rdc_inc.exists()

    assert coreg.dem_primary_gamma0.exists()
    assert coreg.dem_primary_gamma0_bmp.exists()
    assert coreg.dem_primary_gamma0_geo.exists()
    assert coreg.dem_primary_gamma0_geo_bmp.exists()
    assert coreg.dem_primary_gamma0_geo_bmp.with_suffix(".png").exists()
    assert coreg.dem_primary_gamma0_geo_bmp.with_suffix(".kml").exists()
    assert coreg.dem_primary_gamma0_geo_tif.exists()
    assert coreg.dem_primary_sigma0_geo.exists()
    assert coreg.dem_primary_sigma0_geo_tif.exists()


def test_missing_par_files_cause_errors(pgp, coreg):
    (rlks, alks), paths, dem_paths = get_coreg_args(coreg.proc_config.output_path)

    par_file_patterns = [
        "*.slc",
        "*.dem",
        "*.slc.par",
    ]

    wrong_dir = coreg.proc_config.output_path

    for pattern in par_file_patterns:
        slc_dir = paths.dem_primary_slc.parent

        # Move matched files into wrong dir
        important_files = slc_dir.glob(pattern)
        for file in important_files:
            file.rename(wrong_dir / file.name)

        try:
            # Reset mock error stats
            pgp.reset_proxy()

            coreg = CoregisterDem(
                rlks,
                alks,
                dem_paths.dem,
                paths.dem_primary_slc,
                dem_paths.dem_par,
                paths.dem_primary_slc_par,
                multi_look=2
            )

            with pytest.raises(CoregisterDemException):
                coreg.main()

            # Assert that we have no GAMMA errors as DEM coreg sanity checks inputs before running anything that could fail
            assert pgp.error_count == 0

        # Restore file for next iteration
        finally:
            for file in important_files:
                (wrong_dir / file.name).rename(file)


def test_small_settings_get_fixed_up(pgp, pgmock, s1_temp_job_proc):
    (rlks, alks), paths, dem_paths = get_coreg_args(s1_temp_job_proc.output_path)
    dw = (18, 66)

    coreg = CoregisterDem(
        rlks,
        alks,
        dem_paths.dem,
        paths.dem_primary_slc,
        dem_paths.dem_par,
        paths.dem_primary_slc_par,
        multi_look=2,
        # try settings that are smaller than acceptable values
        dem_window = dw,
        dem_patch_window = 64
    )

    assert (
        coreg.dem_window[0] == 10
    ), "Failed to adjust dem_window with setting {}".format(dw)
    assert (
        coreg.dem_window[1] == 34
    ), "Failed to adjust dem_window with setting {}".format(dw)

    assert coreg.dem_patch_window == const.INIT_OFFSETM_CORRELATION_PATCH_SIZES[0]


def test_adjust_dem_parameter(pgp, pgmock, s1_temp_job_proc):
    (rlks, alks), paths, dem_paths = get_coreg_args(s1_temp_job_proc.output_path)

    coreg = CoregisterDem(
        rlks,
        alks,
        dem_paths.dem,
        paths.dem_primary_slc,
        dem_paths.dem_par,
        paths.dem_primary_slc_par,
        multi_look=2,
        # try settings that are smaller than acceptable values
        dem_window = (16, 32)
    )

    # DEM windows should be halved
    assert coreg.dem_window[0] == 8
    assert coreg.dem_window[1] == 16
    assert coreg.dem_patch_window == 512


def test_failure_on_invalid_multilook(pgp, pgmock, s1_temp_job_proc):
    (rlks, alks), paths, dem_paths = get_coreg_args(s1_temp_job_proc.output_path)

    with pytest.raises(ValueError):
        CoregisterDem(
            rlks,
            alks,
            dem_paths.dem,
            paths.dem_primary_slc,
            dem_paths.dem_par,
            paths.dem_primary_slc_par,
            # try settings that are smaller than acceptable values
            dem_window = (16, 32),
            multi_look=-123
        )


def test_failure_on_invalid_dem_window_setting(pgp, pgmock, s1_temp_job_proc):
    (rlks, alks), paths, dem_paths = get_coreg_args(s1_temp_job_proc.output_path)

    # try settings that are smaller than acceptable values
    for dw in [(8, 8), (7, 5), (1, 2), (3, 0)]:
        with pytest.raises(ValueError):
            coreg = CoregisterDem(
                rlks,
                alks,
                dem_paths.dem,
                paths.dem_primary_slc,
                dem_paths.dem_par,
                paths.dem_primary_slc_par,
                multi_look=2,
                # try settings that are smaller than acceptable values
                dem_window = dw,
                dem_patch_window=64
            )


def test_offset_model_bad_init_center(pgp, pgmock, coreg):
    # Fail the first 3 attempts of init_offsetm
    # - this simulates failing to initialise the offset model
    # - due to a bad land center...
    #
    # The 4th location attempt should then succeed!
    expected_fails = 3
    num_fails = expected_fails

    def init_offsetm_mock(*args, **kwargs):
        nonlocal num_fails

        if num_fails > 0:
            num_fails -= 1
            raise CoregisterDemException("simulated bad land center")

        return pgp.init_offsetm(*args, **kwargs)

    pgmock.init_offsetm.side_effect = init_offsetm_mock

    # Run our standard valid data test (it should still pass... after 3 attempts)
    test_valid_data(pgp, coreg)
