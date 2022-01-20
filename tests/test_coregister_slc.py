from pathlib import Path
import itertools

from tests.fixtures import *

from tests.test_workflow import do_ard_workflow_validation

from insar.coregister_slc import CoregisterSlc
from insar.paths.coregistration import CoregisteredSlcPaths
from insar.paths.dem import DEMPaths

from insar.process_backscatter import generate_normalised_backscatter
from insar.project import ARDWorkflow
from insar.path_util import append_suffix
from insar.stack import load_stack_config, load_stack_scene_dates
from insar.workflow.luigi.utils import read_rlks_alks
from insar.coreg_utils import rm_file
from insar.logs import logging_directory


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
        s1_proc,
        debug=True
    )

    # Load stack info
    proc_config = load_stack_config(out_dir)
    scene_dates = list(itertools.chain(*load_stack_scene_dates(proc_config)))
    secondary_dates = list(set(scene_dates) - set([proc_config.ref_primary_scene]))
    # TODO: this isn't really acceptable having to dig into implementation-specific workflow details to get rlks/alks
    ml_file = Path(proc_config.job_path) / 'tasks' / f"{proc_config.stack_id}_createmultilook_status_logs.out"
    rlks, alks = read_rlks_alks(ml_file)

    paths = CoregisteredSlcPaths(out_dir, proc_config.ref_primary_scene, secondary_dates[0], pols[0], int(proc_config.range_looks))

    # Delete all the coregistered products
    rm_file(paths.secondary_lt)
    rm_file(paths.secondary_off)
    rm_file(paths.r_secondary_slc)
    rm_file(paths.r_secondary_slc_par)
    rm_file(paths.r_secondary_mli)
    rm_file(paths.r_secondary_mli_par)

    # Manually re-run coregistration against the SLC data
    pgp.reset_proxy()

    dem_paths = DEMPaths(proc_config)

    with logging_directory(job_dir):
        coreg = CoregisterSlc(
            proc_config,
            "-",
            paths.primary.slc,
            paths.secondary.slc,
            rlks,
            alks,
            dem_paths.rdc_dem
        )

        assert(coreg.out_dir == paths.secondary.dir)

        yield coreg


def test_valid_data(pgp, coreg):
    paths = coreg.ctx.paths

    # Run the full coregistration process
    coreg.main()

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


# TODO: This test is pretty pointless, and soon set_tab_files will be a private implementation detail that won't even exist
# - this will likely be removed when coregistration refactor is complete.
def test_set_tab_files(coreg):
    paths = coreg.ctx.paths

    coreg.set_tab_files(paths)

    # Assert the required tab files are produced...
    assert(paths.primary.slc_tab.exists())
    assert(paths.secondary.slc_tab.exists())
    assert(paths.r_secondary_slc_tab.exists())

# TODO: As other tests above, largely pointless / an implementation detail that won't exist soon
def test_get_lookup(coreg):
    paths = coreg.ctx.paths

    # Create dummy inputs that are expected
    paths.r_dem_primary_mli_par.touch()
    coreg.rdc_dem.touch()
    paths.secondary.mli_par.touch()

    # Run function
    coreg.get_lookup(paths.secondary_lt, coreg.rdc_dem)

    # Ensure the output is produced
    assert(paths.secondary_lt.exists())

# TODO: As other tests above, largely pointless / an implementation detail that won't exist soon
def test_resample_full(coreg):
    paths = coreg.ctx.paths

    # Pre-work before resample (coarse coreg is enough)
    coreg.set_tab_files(paths)
    coreg.get_lookup(paths.secondary_lt, coreg.rdc_dem)
    coreg.reduce_offset()
    coreg.coarse_registration()

    coreg.resample_full(paths.secondary_lt, paths.secondary_off)

    assert(paths.r_secondary_slc_tab.exists())
    assert(paths.r_secondary_slc.exists())
    assert(paths.r_secondary_slc_par.exists())

# TODO: As other tests above, largely pointless / an implementation detail that won't exist soon
# - also... multi-look has it's own independent functions (that this ultimately calls) which should
# - instead be tested directly...
def test_multi_look(coreg):
    paths = coreg.ctx.paths

    # Pre-work before multi_look (coarse coreg is enough)
    coreg.set_tab_files(paths)
    coreg.get_lookup(paths.secondary_lt, coreg.rdc_dem)
    coreg.reduce_offset()
    coreg.coarse_registration()
    coreg.resample_full(paths.secondary_lt, paths.secondary_off)

    coreg.multi_look()

    assert(paths.r_secondary_mli.exists())
    assert(paths.r_secondary_mli_par.exists())


# TODO: Should be it's own separate test/s - backscatter isn't necessarily tied to coreg
def test_generate_normalised_backscatter(coreg, temp_out_dir):
    paths = coreg.ctx.paths

    # Run the full coregistration process
    coreg.main()

    test_output = temp_out_dir / "test_output"

    proc_config = load_stack_config(paths.secondary.dir.parent.parent)
    dem_paths = DEMPaths(proc_config)

    generate_normalised_backscatter(
        test_output.parent,
        paths.secondary.slc,
        dem_paths.ellip_pix_sigma0,
        dem_paths.dem_pix_gam,
        dem_paths.dem_lt_fine,
        dem_paths.geo_dem_par,
        test_output
    )

    secondary_gamma0 = append_suffix(test_output, "_gamma0")
    secondary_gamma0_geo = append_suffix(test_output, "_geo_gamma0")
    secondary_sigma0_geo = append_suffix(test_output, "_geo_sigma0")

    assert(secondary_gamma0.exists())

    assert(secondary_gamma0_geo.exists())
    assert(append_suffix(secondary_gamma0_geo, ".tif").exists())
    assert(append_suffix(secondary_gamma0_geo, ".png").exists())

    assert(secondary_sigma0_geo.exists())
    assert(append_suffix(secondary_sigma0_geo, ".tif").exists())


# TODO: Test more specific corner cases (what are they?)
