from pathlib import Path
from typing import Optional, Tuple
import pytest
import insar.constant as const

from tests.fixtures import *

from tests.test_workflow import do_ard_workflow_validation

from insar.project import ARDWorkflow
from insar.coregister_dem import coregister_primary, CoregisterDemException
from insar.paths.backscatter import BackscatterPaths
from insar.paths.coregistration import CoregisteredPrimaryPaths
from insar.paths.dem import DEMPaths
from insar.paths.slc import SlcPaths
from insar.stack import load_stack_config
from insar.workflow.luigi.utils import read_rlks_alks
from insar.coreg_utils import rm_file
from insar.logs import logging_directory

_LOG = structlog.get_logger("insar")

class CoregTestRunner:
    proc_config: ProcConfig
    dem_paths: DEMPaths
    coreg_paths: CoregisteredPrimaryPaths
    rlks: int
    alks: int
    land_center: Optional[Tuple[float, float]]

    def __init__(self, stack_or_proc, land_center = None):
        if not isinstance(stack_or_proc, ProcConfig):
            proc_config = load_stack_config(stack_or_proc)
        else:
            proc_config = stack_or_proc

        # TODO: this isn't really acceptable having to dig into implementation-specific workflow details to get rlks/alks
        ml_file = Path(proc_config.job_path) / 'tasks' / f"{proc_config.stack_id}_createmultilook_status_logs.out"
        self.rlks, self.alks = (2, 2)
        if ml_file.exists():
            self.rlks, self.alks = read_rlks_alks(ml_file)

        self.proc_config = proc_config
        self.dem_paths = DEMPaths(proc_config)
        primary_slc_paths = SlcPaths(
            proc_config,
            proc_config.ref_primary_scene,
            proc_config.polarisation,
            self.rlks
        )
        self.coreg_paths = CoregisteredPrimaryPaths(primary_slc_paths)

        self.land_center = land_center

    def run(
        self,
        log: structlog.BoundLogger = None,
        multi_look=None,
        dem_patch_window: Optional[int] = 1024,
        dem_window: Optional[Tuple[int, int]] = (256, 256),
    ):
        coregister_primary(
            log or _LOG,
            self.proc_config,
            self.rlks,
            self.alks,
            multi_look or int(self.proc_config.multi_look),
            land_center=self.land_center,
            dem_patch_window=dem_patch_window,
            dem_window=dem_window
        )


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

    # Create runner for the test stack
    runner = CoregTestRunner(out_dir)
    paths = runner.coreg_paths

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
        yield runner


def test_valid_data(pgp, coreg):
    coreg.run()

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

    nrb_paths = BackscatterPaths(coreg.coreg_paths.primary)

    assert nrb_paths.gamma0.exists()
    assert nrb_paths.gamma0_geo.exists()
    assert nrb_paths.gamma0_geo_tif.exists()
    assert nrb_paths.gamma0_geo_tif.with_suffix(".png").exists()
    assert nrb_paths.gamma0_geo_tif.with_suffix(".kml").exists()
    assert nrb_paths.sigma0_geo.exists()
    assert nrb_paths.sigma0_geo_tif.exists()


def test_missing_par_files_cause_errors(pgp, coreg):
    par_file_patterns = [
        "*.slc",
        "*.dem",
        "*.slc.par",
    ]

    wrong_dir = coreg.proc_config.output_path

    for pattern in par_file_patterns:
        slc_dir = coreg.coreg_paths.dem_primary_slc.parent

        # Move matched files into wrong dir
        important_files = slc_dir.glob(pattern)
        for file in important_files:
            file.rename(wrong_dir / file.name)

        try:
            # Reset mock error stats
            pgp.reset_proxy()

            with pytest.raises(CoregisterDemException):
                coreg.run()

            # Assert that we have no GAMMA errors as DEM coreg sanity checks inputs before running anything that could fail
            assert pgp.error_count == 0

        # Restore file for next iteration
        finally:
            for file in important_files:
                (wrong_dir / file.name).rename(file)


def test_small_settings_get_fixed_up(pgp, pgmock, coreg):
    """
    This test asserts that small patch window sizes are automatically bumped up
    to the minimum supported window size we support w/o error (with logging)
    """
    mock_log = mock.MagicMock()
    mock_log.info = mock.MagicMock()

    # try settings that are smaller than acceptable values
    # - this shouldn't raise an exception
    small_patch_window = 64

    coreg.run(
        log = mock_log,
        multi_look = 2,
        dem_window = (18, 66),
        dem_patch_window = small_patch_window
    )

    # Instead it should automatically correct the values, logging
    # the details of why...
    mock_log.info.assert_any_call(
        "increasing DEM patch window",
        old_patch_window=small_patch_window // 2,
        new_patch_window=min(const.INIT_OFFSETM_CORRELATION_PATCH_SIZES),
    )


def test_adjust_dem_parameter(pgp, pgmock, monkeypatch, coreg):
    """
    This test asserts that multi_look is being applied to the provided patch/window
    arguments inside of coregistration (eg: they should all be divided by multi_look)
    """
    import insar.coregister_dem

    # Mock offset_calc
    mock_offset_fn = mock.MagicMock()
    mock_offset_fn.side_effect = insar.coregister_dem.offset_calc

    mock_diff_fn = mock.MagicMock()
    mock_diff_fn.side_effect = insar.coregister_dem.create_diff_par

    monkeypatch.setattr(insar.coregister_dem, "offset_calc", mock_offset_fn)
    monkeypatch.setattr(insar.coregister_dem, "create_diff_par", mock_diff_fn)

    coreg.run(
        multi_look = 2,
        dem_window = (16, 32)
    )

    # Note: Sadly python's mocking lib is a bit lacking, there's no easy way
    # to assert that a function was called with a specific argument being a value
    # while ignoring all other args...  nor is there a way to index call_args with
    # the name of the parameter (forced to use indices) - hence the hard-coded
    # call_args.args[N] code below :(

    # DEM windows should be halved because multi-look is 2

    # args[5] == "dem_window"
    assert mock_diff_fn.call_args.args[5] == [8,16]
    # args[7] == "dem_patch_window"
    assert mock_offset_fn.call_args.args[7] == 512


def test_failure_on_invalid_multilook(pgp, pgmock, coreg):
    with pytest.raises(ValueError):
        coreg.run(multi_look=-123)


def test_failure_on_invalid_dem_window_setting(pgp, pgmock, coreg):
    # try settings that are smaller than acceptable values
    for dw in [(8, 8), (7, 5), (1, 2), (3, 0)]:
        with pytest.raises(ValueError):
            coreg.run(
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
