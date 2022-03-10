from pathlib import Path
import itertools

from tests.fixtures import *

from tests.test_workflow import do_ard_workflow_validation

from insar.coregister_slc import coregister_s1_secondary
from insar.paths.backscatter import BackscatterPaths
from insar.paths.coregistration import CoregisteredSlcPaths
from insar.paths.dem import DEMPaths

from insar.process_backscatter import generate_normalised_backscatter
from insar.project import ARDWorkflow
from insar.stack import load_stack_config, load_stack_scene_dates
from insar.workflow.luigi.utils import read_rlks_alks
from insar.coreg_utils import rm_file
from insar.logs import logging_directory

class CoregTestRunner:
    proc_config: ProcConfig
    dem_paths: DEMPaths
    coreg_paths: CoregisteredSlcPaths
    rlks: int
    alks: int

    def __init__(self, stack_or_proc, scene_date, pol):
        if not isinstance(stack_or_proc, ProcConfig):
            proc_config = load_stack_config(stack_or_proc)
        else:
            proc_config = stack_or_proc

        self.proc_config = proc_config
        self.dem_paths = DEMPaths(proc_config)

        # TODO: this isn't really acceptable having to dig into implementation-specific workflow details to get rlks/alks
        ml_file = Path(proc_config.job_path) / 'tasks' / f"{proc_config.stack_id}_createmultilook_status_logs.out"
        self.rlks, self.alks = (2, 2)
        if ml_file.exists():
            self.rlks, self.alks = read_rlks_alks(ml_file)

        self.coreg_paths = CoregisteredSlcPaths(
            proc_config,
            proc_config.ref_primary_scene,
            scene_date,
            pol,
            self.rlks
        )

    def run(self):
        coregister_s1_secondary(
            self.proc_config,
            "-",
            self.coreg_paths.primary.slc,
            self.coreg_paths.secondary.slc,
            self.rlks,
            self.alks,
            self.dem_paths.rdc_dem
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

    # Load stack info
    proc_config = load_stack_config(out_dir)
    scene_dates = list(itertools.chain(*load_stack_scene_dates(proc_config)))
    secondary_dates = list(set(scene_dates) - set([proc_config.ref_primary_scene]))
    # TODO: this isn't really acceptable having to dig into implementation-specific workflow details to get rlks/alks
    ml_file = Path(proc_config.job_path) / 'tasks' / f"{proc_config.stack_id}_createmultilook_status_logs.out"
    rlks, alks = read_rlks_alks(ml_file)

    runner = CoregTestRunner(proc_config, secondary_dates[0], pols[0])
    paths = runner.coreg_paths

    # Delete all the coregistered products
    rm_file(paths.secondary_lt)
    rm_file(paths.secondary_off)
    rm_file(paths.r_secondary_slc)
    rm_file(paths.r_secondary_slc_par)
    rm_file(paths.r_secondary_mli)
    rm_file(paths.r_secondary_mli_par)

    # Manually re-run coregistration against the SLC data
    pgp.reset_proxy()

    with logging_directory(job_dir):
        yield runner


def test_valid_data(pgp, coreg):
    paths = coreg.coreg_paths

    # Run the full coregistration process
    coreg.run()

    # Assert no failure status for any gamma call
    assert(pgp.error_count == 0)

    # Assert coregistration LUTs exist
    assert(paths.secondary_lt.exists())
    assert(paths.secondary_off.exists())

    # Assert coregistered SLC outputs exist
    assert(paths.r_secondary_slc.exists())
    assert(paths.r_secondary_slc_par.exists())
    assert(paths.r_secondary_mli.exists())
    assert(paths.r_secondary_mli_par.exists())


# TODO: Should be it's own separate test/s - backscatter isn't necessarily tied to coreg
def test_generate_normalised_backscatter(coreg, temp_out_dir):
    paths = coreg.coreg_paths

    # Run the full coregistration process
    coreg.run()

    test_output = temp_out_dir / "test_output"

    proc_config = load_stack_config(paths.secondary.dir.parent.parent)
    dem_paths = DEMPaths(proc_config)
    nrb_paths = BackscatterPaths(paths.secondary)

    generate_normalised_backscatter(
        test_output.parent,
        paths.secondary.slc,
        dem_paths.ellip_pix_sigma0,
        dem_paths.dem_pix_gam,
        dem_paths.dem_lt_fine,
        dem_paths.geo_dem_par,
        test_output
    )

    print("????", nrb_paths.gamma0)
    assert(nrb_paths.gamma0.exists())

    assert(nrb_paths.gamma0_geo.exists())
    assert(nrb_paths.gamma0_geo_tif.exists())
    assert(nrb_paths.gamma0_geo_tif.with_suffix(".png").exists())

    # We don't keep raw sigma0, only the geo transformed version
    #assert(nrb_paths.sigma0.exists())
    assert(nrb_paths.sigma0_geo.exists())
    assert(nrb_paths.sigma0_geo_tif.exists())


# TODO: Test more specific corner cases (what are they?)
