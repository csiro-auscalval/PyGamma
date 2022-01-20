from pathlib import Path
from typing import Generator, List, Tuple, Optional
import tempfile
from dataclasses import dataclass
from luigi.date_interval import Custom as LuigiDate
import itertools
from shutil import rmtree

from tests.fixtures import *
from unittest import mock

from insar.scripts.process_gamma import run_ard_inline
from insar.project import ARDWorkflow, ProcConfig
from insar.paths.slc import SlcPaths
from insar.paths.interferogram import InterferogramPaths
from insar.stack import load_stack_scene_dates, load_stack_ifg_pairs
from insar.paths.stack import StackPaths
import insar.workflow.luigi.coregistration

test_data = Path(__file__).parent.absolute() / 'data'
rs2_pols = ["HH"]

def print_dir_tree(dir: Path, depth=0):
    print("  " * depth + dir.name + "/")

    depth += 1

    for i in dir.iterdir():
        if i.is_dir():
            print_dir_tree(i, depth)
        else:
            print("  " * depth + i.name)

def dir_tree(dir: Path, include_dirs: bool = True) -> Generator[Path, None, None]:
    for i in dir.iterdir():
        yield i

        if i.is_dir():
            yield from dir_tree(i, include_dirs)

def count_dir_tree(dir: Path, include_dirs: bool = True) -> int:
    if not dir.exists():
        return 0

    return len(list(dir_tree(dir, include_dirs)))

# Note: these tests run on fake source data products, so...
# 1) This doesn't test any of the DB query side of things
# 2) This, like all of our unit test, doesn't test the
#    correctness of any of the GAMMA data processing, only
#    the high level API checking that py_gamma_test_proxy.py does.


# TODO: in the future... we could detect if we're on the NCI and truly
# run these tests "without" the mock fixtures, and real data (not the
# tests/data/* stuff) and these should also run/pass.
#
# These tests are basically end-to-end workflow integration tests, and
# the ONLY two differences between this and a real processing job are
# the GAMMA mocks and fake testing data.
#
# These tests legitimately run the real-deal ARD luigi workflow directly,
# albeit slowly (single-threaded in the calling thread).

@dataclass
class GeospatialQuery:
    database_path: Path
    shapefile: Path
    include_dates: List[Tuple[datetime, datetime]]
    exclude_dates: List[Tuple[datetime, datetime]]

def do_ard_workflow_validation(
    pgp,
    workflow: ARDWorkflow,
    source_data: List[Path],
    pols: List[str],
    proc_file_path: Path,
    expected_errors: int = 0,
    min_gamma_calls: int = 10,
    validate_slc: bool = True,
    validate_ifg: bool = True,
    cleanup: bool = True,
    debug: bool = False,
    expected_scenes: Optional[int] = None,
    geospatial_query: Optional[GeospatialQuery] = None,
    temp_dir: Optional[tempfile.TemporaryDirectory] = None,
    append: bool = False,
    resume: bool = False,
    reprocess_failed: bool = False,
    require_poeorb: bool = False
) -> Tuple[Path, Path, tempfile.TemporaryDirectory]:
    # Reset pygamma proxy/mock stats
    pgp.reset_proxy()

    # Setup temporary dirs to run the workflow in
    if temp_dir is None:
        temp_dir = tempfile.TemporaryDirectory()

    job_dir = Path(temp_dir.name) / "job"
    out_dir = Path(temp_dir.name) / "out"

    job_dir.mkdir(exist_ok=True)
    out_dir.mkdir(exist_ok=True)

    # Record starting dir, and move into temp dir
    orig_cwd = safe_get_cwd()
    os.chdir(temp_dir.name)

    # Setup test workflow arguments
    args = {
        "proc_file": str(proc_file_path),
        "source_data": [str(i) for i in source_data],
        "workdir": str(job_dir),
        "outdir": str(out_dir),
        "polarization": pols,
        "cleanup": cleanup,
        "workflow": workflow,
        "append": append,
        "resume": resume,
        "reprocess_failed": reprocess_failed,
        "require_precise_orbit": require_poeorb
    }

    if geospatial_query:
        args["database_path"] = geospatial_query.database_path
        args["shape_file"] = geospatial_query.shapefile
        args["include_dates"] = geospatial_query.include_dates
        args["exclude_dates"] = geospatial_query.exclude_dates

    # Run the workflow
    try:
        run_ard_inline(args)

    # Go back to the processes original work
    finally:
        os.chdir(orig_cwd)

    # Load final .proc config
    finalised_proc_path = out_dir / "config.proc"
    with finalised_proc_path.open('r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    paths = StackPaths(proc_config)
    is_nrt = workflow == ARDWorkflow.BackscatterNRT
    is_coregistered = workflow != ARDWorkflow.BackscatterNRT
    rlks = int(proc_config.range_looks)

    # DEBUG for visualising output in tempdir
    if debug:
        print("===== DEBUG =====")
        print_dir_tree(out_dir)
        print("==="*5)
        print((job_dir / "insar-log.jsonl").read_text())
        print((job_dir / "status-log.jsonl").read_text())
    # END DEBUG

    # Assert there were no GAMMA errors
    assert(pgp.error_count == expected_errors)

    # Assert we did call some GAMMA functions
    if min_gamma_calls == 0:
        assert(len(pgp.call_sequence) == 0)
    else:
        assert(len(pgp.call_sequence) >= min_gamma_calls)

    # Assert raw data was extracted from source data
    if not cleanup and source_data:
        raw_data_dir = out_dir / proc_config.raw_data_dir
        assert(raw_data_dir.exists())
        # There should be dozens of raw files in any source data
        assert(count_dir_tree(raw_data_dir) > 10)

    # Assert we have a csv of source data
    assert(paths.acquisition_csv.exists())

    # Assert our scene lists make sense
    ifgs_list = load_stack_ifg_pairs(proc_config)
    ifgs_list = list(itertools.chain(*ifgs_list))

    scenes_list = load_stack_scene_dates(proc_config)
    scenes_list = list(itertools.chain(*scenes_list))

    if expected_scenes is not None:
        if expected_scenes == 0:
            assert(not scenes_list)
        else:
            assert(len(scenes_list) == expected_scenes)

    if scenes_list:
        primary_ref_scene = out_dir / proc_config.list_dir / "primary_ref_scene"
        primary_ref_scene = primary_ref_scene.read_text().strip()

        assert(primary_ref_scene == proc_config.ref_primary_scene)

    ifg_dir = out_dir / proc_config.int_dir

    if len(scenes_list) < 2:
        assert(len(ifgs_list) == 0)
    elif workflow == ARDWorkflow.Interferogram:
        assert(len(ifgs_list) > 0)

    # Assert each scene has an SLC (coregistered if not NRT)
    #
    # TBD: It might be better to use the `required_files` variable in the
    # ARD luigi task?  as that is the expected pattern of files we expect
    # to exist (and are thus saved from being cleaned up).
    #
    # Might want to do this 'in addition' to this explicit code-based approach
    # as this current approach validates our SlcPaths/etc constants are
    # being respected.  Where as the glob patterns are more of a higher level
    # encoding/representation of a business requirement.
    if validate_slc:
        for scene in scenes_list:
            scene_dir = out_dir / proc_config.slc_dir / scene
            assert(scene_dir.exists())

            for pol in pols:
                slc_paths = SlcPaths(proc_config, scene, pol, rlks)

                # If we haven't cleaned up, SLC data should exist
                if not cleanup:
                    assert(slc_paths.slc.exists())
                    assert(slc_paths.slc_par.exists())
                    assert(slc_paths.mli.exists())
                    assert(slc_paths.mli_par.exists())

                    def resampled(path: Path):
                        return path.parent / f"r{path.name}"

                    if is_coregistered and scene != primary_ref_scene:
                        # FIXME: CoregisteredSlcPaths has these?
                        assert(resampled(slc_paths.slc).exists())
                        assert(resampled(slc_paths.slc_par).exists())
                        assert(resampled(slc_paths.mli).exists())
                        assert(resampled(slc_paths.mli_par).exists())

                # Assert each scene has backscatter products
                if is_nrt:
                    gamma0_path = scene_dir / f"nrt_{scene}_{pol}_{rlks}rlks_gamma0_geo"
                    gamma0_tif_path = scene_dir / f"nrt_{scene}_{pol}_{rlks}rlks_gamma0_geo.tif"
                else:
                    gamma0_path = scene_dir / f"{scene}_{pol}_{rlks}rlks_geo_gamma0"
                    gamma0_tif_path = scene_dir / f"{scene}_{pol}_{rlks}rlks_geo_gamma0.tif"

                # Raw data only kept if not cleanup
                if not cleanup:
                    assert(gamma0_path.exists())

                # But we should always have a geotiff no matter what
                assert(gamma0_tif_path.exists())

    # Assert each IFG date pair has phase unwrapped geolocated data
    if validate_ifg and workflow == ARDWorkflow.Interferogram and len(scenes_list) > 1:
        assert(len(list(ifg_dir.iterdir())) == len(ifgs_list))

        for primary_date, secondary_date in ifgs_list:
            ic = InterferogramPaths(proc_config, primary_date, secondary_date)

            # Make sure the main geo flat & unwrapped file exists
            assert((ic.ifg_dir / ic.ifg_unw_geocode_out_tiff).exists())
            assert((ic.ifg_dir / ic.ifg_flat_geocode_out_tiff).exists())
            assert((ic.ifg_dir / ic.ifg_flat).exists())

            # Ensure filt/flat products exist
            assert((ic.ifg_dir / ic.ifg_filt_geocode_out_tiff).exists())
            assert((ic.ifg_dir / ic.ifg_filt_coh_geocode_out_tiff).exists())
            assert((ic.ifg_dir / ic.ifg_flat_geocode_out_tiff).exists())
            assert((ic.ifg_dir / ic.ifg_flat_coh_geocode_out_tiff).exists())

    return out_dir, job_dir, temp_dir

def test_ard_workflow_ifg_single_s1_scene(pgp, pgmock, s1_proc, s1_test_data_zips):
    # Take just first 2 source data files (which is a single date, each date has 2 acquisitions in a frame)
    source_data = [str(i) for i in s1_test_data_zips[:2]]
    pols = ["VV", "VH"]

    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        s1_proc
    )


def test_ard_workflow_ifg_smoketest_two_date_s1_stack(pgp, pgmock, s1_proc, s1_test_data_zips):
    source_data = [str(i) for i in s1_test_data_zips]
    pols = ["VV", "VH"]

    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        s1_proc
    )


def test_ard_workflow_ifg_smoketest_single_rs2_scene(pgp, pgmock, rs2_test_data, rs2_proc):
    # Setup test workflow arguments, taking just a single RS2 acquisition
    source_data = [str(rs2_test_data[0])]
    pols = ["HH"]

    # Run standard ifg workflow validation test for this data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        rs2_proc
    )

def test_ard_workflow_ifg_smoketest_two_date_rs2_stack(pgp, pgmock, rs2_test_data, rs2_proc):
    # Setup test workflow arguments
    source_data = [str(i) for i in rs2_test_data]
    pols = ["HH"]

    # Run standard ifg workflow validation test for this data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        rs2_proc
    )


def test_ard_workflow_ifg_smoketest_single_alos1_scene(pgp, pgmock, test_data_dir, alos1_test_zips, alos1_proc_config_path):
    # Setup test workflow arguments, taking just a single RS2 acquisition
    source_data = [str(alos1_test_zips[0])]
    pols = ["HH"]

    # Run standard ifg workflow validation test for this data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        alos1_proc_config_path
    )


def test_ard_workflow_ifg_smoketest_single_alos2_scene(pgp, pgmock, test_data_dir, alos2_test_zips, alos2_proc_config_path):
    # Setup test workflow arguments, taking just a single RS2 acquisition
    source_data = [str(alos2_test_zips[0])]
    pols = ["HH"]

    # Run standard ifg workflow validation test for this data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        alos2_proc_config_path
    )


#
# Note: The tests below don't differ inside of the workflow between sensors,
# as such to avoid duplicating tests for no reason we just have one version
# of each based on RS2 data.  This 'might' change in the future, at which
# point test coverage may drop (and this may need to be revised).
#

def test_ard_workflow_smoketest_nrt(pgp, pgmock, rs2_test_data, rs2_proc):
    # Setup test workflow arguments
    source_data = [str(i) for i in rs2_test_data]
    pols = ["HH"]

    # Run standard ifg workflow validation test for this data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.BackscatterNRT,
        source_data,
        pols,
        rs2_proc
    )


def test_ard_workflow_pol_mismatch_produces_no_data(pgp, pgmock, rs2_test_data, rs2_proc):
    # Setup test workflow arguments
    source_data = [str(i) for i in rs2_test_data]
    # But with a mismatching pols! (rs2 test data is HH, not VV)
    pols = ["VV"]

    # Run standard ifg workflow validation test for this data
    # expected calls == 0!
    out_dir, _, _ = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        rs2_proc,
        min_gamma_calls=0
    )

    assert(not (out_dir / 'lists' / 'scenes.list').read_text().strip())


def test_ard_workflow_excepts_on_dag_errors(monkeypatch, pgp, pgmock, rs2_test_data, rs2_proc):
    # We inject an error in this test, to the get_scenes function - which most
    # non-processing tasks (eg: the Create* tasks which create processing tasks)
    # use to determine what the input scenes are... so this will cause errors pretty
    # early on in a Luigi task (eg: CreateCoregisterSecondaries)
    test_message = "No backscatter for you! >:|"

    def get_exception(*args, **kwargs):
        raise Exception(test_message)

    monkeypatch.setattr(insar.workflow.luigi.coregistration, "get_scenes", get_exception)

    # Setup test workflow arguments
    source_data = [str(i) for i in rs2_test_data]
    pols = ["HH"]

    # Run standard ifg workflow validation test, which should raise our exception!
    # - as the tasks that get it will 'not' be processing tasks, but other tasks
    # - in the DAG which should NOT be allowed to fail / can not soldier on.
    with pytest.raises(Exception) as ex_info:
        _, job_dir, _ = do_ard_workflow_validation(
            pgp,
            ARDWorkflow.Backscatter,
            source_data,
            pols,
            rs2_proc,
            # Don't validate outputs, as they won't exist from our error
            validate_slc=False
        )

        assert(ex_info.value.message == test_message)


def test_ard_workflow_processing_errors_do_not_except(pgp, pgmock, rs2_test_data, rs2_proc):
    # We inject a processing error into the backscatter code which should not cause any
    # exception, as it should not flow out of the workflow (they should be captured and
    # the workflow should soldier on when raised within a processing module).
    #
    # float_math is only done for gamma0 calcs, this was chosen to cause backscatter
    # to fail in this unit test.
    def raise_error(*args, **kwargs):
        raise Exception("Test error!")

    pgmock.float_math.side_effect = raise_error

    # Setup test workflow arguments
    source_data = [str(rs2_test_data[0])]
    pols = ["HH"]

    # Run standard ifg workflow validation test, it should NOT except in this case
    # despite us raising an exception above.  As the tasks that get the error are
    # data processing tasks which should be allowed to fail / soldier on.
    _, job_dir, _ = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Backscatter,
        source_data,
        pols,
        rs2_proc,
        # Don't validate outputs, as they won't exist from our error
        validate_slc=False,
        validate_ifg=False
    )

    # Assert our exception was thrown (despite it not making it outside of luigi)
    assert(pgmock.float_math.call_count > 0)

    # Assert the DAG output file has a failed status
    nbr_status_text = (job_dir / "tasks" / "20170430_HH_2rlks_nbr_logs.out").read_text()
    assert(nbr_status_text == "FAILED")


def test_ard_workflow_excepts_on_invalid_proc(pgp, pgmock, rs2_test_data, rs2_proc):
    # Setup test workflow arguments
    source_data = [str(i) for i in rs2_test_data]
    pols = ["HH"]

    # Create invalid .proc file
    proc_txt = rs2_proc.read_text()[2000:]

    bad_proc = rs2_proc.parent / "invalid_rs2_proc.config"
    with bad_proc.open("w") as file:
        file.write(proc_txt)

    # Run standard ifg workflow validation test, which should except
    with pytest.raises(Exception):
        do_ard_workflow_validation(
            pgp,
            ARDWorkflow.Interferogram,
            source_data,
            pols,
            bad_proc,
            min_gamma_calls=0
        )

    # Assert no GAMMA calls were ever made
    assert(len(pgp.call_sequence) == 0)


def test_ard_workflow_no_op_for_empty_data(pgp, pgmock, rs2_proc):
    # Setup test workflow arguments
    source_data = []
    pols = ["VV"]

    # Run standard ifg workflow validation test for this data
    # - shouldn't except
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        rs2_proc,
        # Except no GAMMA calls w/ no data inputs
        min_gamma_calls=0
    )


def test_ard_workflow_no_cleanup_keeps_raw_data(pgp, pgmock, rs2_test_data, rs2_proc):
    # Setup test workflow arguments
    source_data = [str(i) for i in rs2_test_data]
    pols = ["HH"]

    # Run standard ifg workflow validation test for this data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        rs2_proc,
        cleanup=False
    )

    # Note: do_ard_workflow_validation does all the validation we care about when cleanup == False
    # - no need to duplicate it here.


def test_ard_workflow_with_good_s1_db_query(logging_ctx, pgp, pgmock, s1_test_db, s1_proc):
    first_date = S1_TEST_DATA_DATES[0]
    last_date = S1_TEST_DATA_DATES[-1]

    first_date = f"{first_date[:4]}-{first_date[4:6]}-{first_date[6:]}"
    last_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"

    query = GeospatialQuery(
        s1_test_db,
        TEST_DATA_BASE / "T133D_F20S_S1A.shp",
        [LuigiDate.parse(f"{first_date}-{last_date}")],
        []
    )

    # Run standard ifg workflow w/ a query that covers our test data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        [],
        ["VV", "VH"],
        s1_proc,
        geospatial_query=query,
        expected_scenes=2
    )

    # Note: do_ard_workflow_validation does all the validation we care about
    # - this test should not except / should complete cleanly.


def test_ard_workflow_with_db_query_no_spatial_coverage(logging_ctx, pgp, pgmock, s1_test_db, s1_proc):
    first_date = S1_TEST_DATA_DATES[0]
    last_date = S1_TEST_DATA_DATES[-1]

    first_date = f"{first_date[:4]}-{first_date[4:6]}-{first_date[6:]}"
    last_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"

    query = GeospatialQuery(
        s1_test_db,
        # Note: using shape file which does NOT cover our standard test data
        TEST_DATA_BASE / "T147D_F28S_S1A.shp",
        [LuigiDate.parse(f"{first_date}-{last_date}")],
        []
    )

    # Run standard ifg workflow w/ our query (that doesn't spatially cover test data)
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        [],
        ["VV", "VH"],
        s1_proc,
        geospatial_query=query,
        # The stack should not process / there should be no data returned by this query.
        expected_scenes=0,
        min_gamma_calls=0
    )


def test_ard_workflow_with_db_query_no_temporal_coverage(logging_ctx, pgp, pgmock, s1_test_db, s1_proc):
    # Note: using dates which do NOT cover our test data
    first_date = f"3000-01-01"
    last_date = f"4000-12-25"

    query = GeospatialQuery(
        s1_test_db,
        TEST_DATA_BASE / "T133D_F20S_S1A.shp",
        [LuigiDate.parse(f"{first_date}-{last_date}")],
        []
    )

    # Run standard ifg workflow w/ our query (that doesn't temporally cover test data)
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        [],
        ["VV", "VH"],
        s1_proc,
        geospatial_query=query,
        # The stack should not process / there should be no data returned by this query.
        expected_scenes=0,
        min_gamma_calls=0
    )


def test_ard_workflow_with_empty_db(logging_ctx, test_data_dir, pgp, pgmock, s1_test_db, s1_proc):
    # Create an empty database
    empty_db_path = test_data_dir / "test.db"
    with Archive(empty_db_path) as archive:
        pass

    first_date = S1_TEST_DATA_DATES[0]
    last_date = S1_TEST_DATA_DATES[-1]

    first_date = f"{first_date[:4]}-{first_date[4:6]}-{first_date[6:]}"
    last_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"

    query = GeospatialQuery(
        empty_db_path,
        TEST_DATA_BASE / "T133D_F20S_S1A.shp",
        [LuigiDate.parse(f"{first_date}-{last_date}")],
        []
    )

    # Run standard ifg workflow w/ a query that covers our test data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        [],
        ["VV", "VH"],
        s1_proc,
        geospatial_query=query,
        # The stack should not process / there's no scenes in our DB...
        expected_scenes=0,
        min_gamma_calls=0
    )


def test_ard_workflow_no_append_new_dates_raises_error(pgp, pgmock, rs2_test_data, rs2_proc):
    # Run a normal workflow with just one scene
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data[:1],
        rs2_pols,
        rs2_proc
    )

    # Assert there's only one date
    first_products = list(out_dir.glob("SLC/*/*gamma0.tif"))
    assert len(first_products) == 1
    first_mtime = first_products[0].stat().st_mtime

    # Then try and run another without append, should raise error
    with pytest.raises(RuntimeError):
        out_dir, job_dir, temp_dir = do_ard_workflow_validation(
            pgp,
            ARDWorkflow.Interferogram,
            sorted(rs2_test_data),
            rs2_pols,
            rs2_proc,
            temp_dir=temp_dir
        )

    # Assert nothing changed (still just one date, not modified)
    second_products = sorted(list(out_dir.glob("SLC/*/*gamma0.tif")))
    assert len(second_products) == 1
    second_mtime = second_products[0].stat().st_mtime

    assert first_mtime == second_mtime


def test_ard_workflow_append_new_dates(pgp, pgmock, rs2_test_data, rs2_proc):
    # Run a normal workflow with just one scene
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data[:1],
        rs2_pols,
        rs2_proc
    )

    # Assert there's only one date
    products = list(out_dir.glob("SLC/*/*gamma0.tif"))
    assert len(products) == 1
    first_mtime = products[0].stat().st_mtime

    # Then try and run another WITH append, should succeed w/o issue
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        sorted(rs2_test_data),
        rs2_pols,
        rs2_proc,
        append=True,
        temp_dir=temp_dir
    )

    # Assert there are now two dates, and the first was unchanged (eg: only new one was made)
    second_products = sorted(list(out_dir.glob("SLC/*/*gamma0.tif")))
    assert products[0] == second_products[0]
    assert len(second_products) == 2

    assert first_mtime == second_products[0].stat().st_mtime
    assert second_products[1].stat().st_mtime > second_products[0].stat().st_mtime


def test_ard_workflow_remove_dates_fails(pgp, pgmock, rs2_test_data, rs2_proc):
    # Run a normal workflow with many dates
    assert(len(rs2_test_data) > 1)

    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc
    )

    # Then run again w/o append passing in less dates, ensuring an error is raised
    with pytest.raises(RuntimeError):
        out_dir, job_dir, temp_dir = do_ard_workflow_validation(
            pgp,
            ARDWorkflow.Interferogram,
            rs2_test_data[:-1],
            rs2_pols,
            rs2_proc,
            temp_dir=temp_dir,
            min_gamma_calls=0
        )

    # Then run again WITH append passing in less dates, ensuring an error is still raised
    # (we can't remove dates even if we want to)
    with pytest.raises(RuntimeError):
        out_dir, job_dir, temp_dir = do_ard_workflow_validation(
            pgp,
            ARDWorkflow.Interferogram,
            rs2_test_data[:-1],
            rs2_pols,
            rs2_proc,
            append=True,
            temp_dir=temp_dir,
            min_gamma_calls=0
        )


def test_ard_workflow_append_no_dates_is_no_op(pgp, pgmock, rs2_test_data, rs2_proc):
    # Run a normal workflow with many dates
    assert(len(rs2_test_data) > 1)

    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc
    )

    products = list(out_dir.glob("SLC/*/*gamma0.tif"))
    first_mtimes = [i.stat().st_mtime for i in products]

    # Re-run it with append (note: data already processed above)
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc,
        append=True,
        temp_dir=temp_dir,
        # It should result in no GAMMA calls / no work to process
        min_gamma_calls=0
    )

    # Sanity check outputs to ensure nothing changed!
    assert sorted(list(out_dir.glob("SLC/*/*gamma0.tif"))) == sorted(products)

    for first_mtime, prod_url in zip(first_mtimes, products):
        assert first_mtime == prod_url.stat().st_mtime


def test_ard_workflow_resume_failed_processing(pgp, pgmock, rs2_test_data, rs2_proc):
    orig_side_effect = pgmock.phase_sim_orb.side_effect

    try:
        # Get the mock to raise an error in SLC processing of one scene
        pgmock.phase_sim_orb.side_effect = mock.Mock(side_effect=Exception('Not yet...'))

        # Run a normal workflow w/ 2 scenes (should produce 1 ifg if not for error)
        out_dir, job_dir, temp_dir = do_ard_workflow_validation(
            pgp,
            ARDWorkflow.Interferogram,
            rs2_test_data[:2],
            rs2_pols,
            rs2_proc,
            # Note: we still expect 0 errors (our side effect transcends our pg mock proxy w/ error counting)
            expected_errors=0,
            validate_ifg=False
        )

        # Assert the interferogram doesn't exist due to the exception
        #
        # Note: Due to intentional design decisions in our workflow, the workflow still succeeds / no exception
        # or error raised.  Instead the interferogram task has been marked as having had an exception, but the task
        # itself at the Luigi level has 'succeeded' (but no data was generated).  This is why we have/need resume!
        ifg_tifs = list(out_dir.glob("INT/*/*.tif"))
        assert(not ifg_tifs)

    finally:
        # Fix mock to not raise errors
        pgmock.phase_sim_orb.side_effect = orig_side_effect

    # Re-run the same workflow with resume, will produce 1 ifg now the error is gone
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data[:2],
        rs2_pols,
        rs2_proc,
        temp_dir=temp_dir,
        resume=True,
        reprocess_failed=True,
        expected_errors=0,
        validate_ifg=True
    )

    # Note: do_ard_worfklow_validation w/ validate_ifg=True does all our asserts we care about
    # - but we explicitly check the above tif condition is now true!  Just for consistency
    ifg_tifs = list(out_dir.glob("INT/*/*.tif"))
    assert(len(ifg_tifs) > 0)


def test_ard_workflow_resume_lost_slcs(pgp, pgmock, rs2_test_data, rs2_proc):
    orig_side_effect = pgmock.phase_sim_orb.side_effect

    # Run a normal workflow
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc
    )

    # Delete half the SLCs
    slc_dir = out_dir / "SLC"
    slcs = list(slc_dir.iterdir())
    slcs = slcs[:(len(slcs)+1) // 2]

    orig_time = slcs[0].stat().st_mtime

    for slc in slcs:
        rmtree(slc)

    # Delete the IFGs too (--resume doesn't re-create SLCs unless they're needed for an IFG just yet)
    rmtree(out_dir / "INT")

    # Re-run the same workflow with resume
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc,
        temp_dir=temp_dir,
        resume=True
    )

    # Assert the SLCs were re-created
    for slc in slcs:
        assert(slc.exists())
        assert(slc.stat().st_mtime > orig_time)


def test_ard_workflow_resume_lost_ifgs(pgp, pgmock, rs2_test_data, rs2_proc):
    orig_side_effect = pgmock.phase_sim_orb.side_effect

    # Run a normal workflow
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc
    )

    # Delete the interferogram dir entirely!
    rmtree(out_dir / "INT")

    # Re-run the same workflow with resume
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc,
        temp_dir=temp_dir,
        resume=True
    )

    # Assert the IFGs were re-created
    assert((out_dir / "INT").exists())
    # the 2pi.png quicklook images are the final product made, so if these
    # exist all the other products should as well (validated via do_ard_workflow_validation)
    assert(len(list(out_dir.glob("INT/*/*2pi.png"))) >= 1)


def test_ard_workflow_resume_complete_job(pgp, pgmock, rs2_test_data, rs2_proc):
    # Run a normal workflow
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data[:2],
        rs2_pols,
        rs2_proc,
    )

    # Re-run it with resume, ensure no work occurs (data already processed)
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data[:2],
        rs2_pols,
        rs2_proc,
        temp_dir=temp_dir,
        resume=True,
        # No errors should occur
        expected_errors=0,
        # Because no data processing should even occur! (everything already processed)
        min_gamma_calls=0
    )

    # Note: This unit test just builds on / accepts all the asserts done in do_ard_workflow_validation


def test_ard_workflow_resume_crashed_job(pgp, pgmock, monkeypatch, rs2_test_data, rs2_proc):
    # Create a temporary directory up-front to work in (can't use
    # a returned one, as the first function that would normally make
    # it is expected to crash in this test)
    temp_dir = tempfile.TemporaryDirectory()

    # Copy the original function so we can restore it later
    orig_function = insar.workflow.luigi.coregistration.get_coreg_kwargs

    try:
        # Get the mock to raise an error in the Luigi DAG causing it to fail AFTER
        # already processing coregistered SLC (eg: fails before IFG)
        #
        # This is similar to test_ard_workflow_resume_failed_processing, but the
        # error happens in the DAG code, 'not' in the data processing code (where
        # errors are allowed/expected and handled differently) - errors in the DAG
        # should propagate to the caller / into Luigi, causing a crash!
        monkeypatch.setattr(
            insar.workflow.luigi.coregistration,
            'get_coreg_kwargs',
            mock.Mock(side_effect=Exception("Goodbye cruel world!"))
        )

        # Run a normal workflow, but it will crash!
        with pytest.raises(Exception):
            out_dir, job_dir, temp_dir = do_ard_workflow_validation(
                pgp,
                ARDWorkflow.Interferogram,
                rs2_test_data,
                rs2_pols,
                rs2_proc,
                temp_dir=temp_dir
            )

    finally:
        # Restore original function, so we'll no longer crash...
        monkeypatch.setattr(
            insar.workflow.luigi.coregistration,
            'get_coreg_kwargs',
            orig_function
        )

    # Re-run the same workflow with resume, will produce 1 ifg now the error is gone
    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        rs2_test_data,
        rs2_pols,
        rs2_proc,
        temp_dir=temp_dir,
        resume=True,
        expected_errors=0,
        validate_ifg=True
    )

    # Note: do_ard_worfklow_validation w/ validate_ifg=True does all our asserts we care about

def test_ard_workflow_missing_orbits_still_succeeds(
    logging_ctx,
    pgp,
    pgmock,
    s1_test_db,
    s1_proc_without_poeorb
):
    """
    This tests that the workflow can still generate data w/o external orbit files - relying on the internal
    in-flight orbital state vectors that come w/ the SLC data.

    This is the default behaviour without --requires-precise-orbit being specified (defaults to false).
    """

    first_date = S1_TEST_DATA_DATES[0]
    last_date = S1_TEST_DATA_DATES[-1]

    first_date = f"{first_date[:4]}-{first_date[4:6]}-{first_date[6:]}"
    last_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"

    query = GeospatialQuery(
        s1_test_db,
        TEST_DATA_BASE / "T133D_F20S_S1A.shp",
        [LuigiDate.parse(f"{first_date}-{last_date}")],
        []
    )

    # Run standard ifg workflow w/ a query that covers our test data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        [],
        ["VV", "VH"],
        s1_proc_without_poeorb,
        geospatial_query=query
    )


def test_ard_workflow_query_requiring_missing_orbits_produces_no_scenes(
    logging_ctx,
    pgp,
    pgmock,
    s1_test_db,
    s1_proc_without_poeorb
):
    """
    This tests that the workflow using geospatial DB queries with --requires-precise-orbit
    when poeorb files are 'not' available... will NOT generate any data / produce any scenes.

    Note: This is otherwise identical to `test_ard_workflow_with_good_s1_db_query` - just
    with a different .proc file whose source data has no orbit files, thus we expect the
    different outcome to the original test.
    """

    first_date = S1_TEST_DATA_DATES[0]
    last_date = S1_TEST_DATA_DATES[-1]

    first_date = f"{first_date[:4]}-{first_date[4:6]}-{first_date[6:]}"
    last_date = f"{last_date[:4]}-{last_date[4:6]}-{last_date[6:]}"

    query = GeospatialQuery(
        s1_test_db,
        TEST_DATA_BASE / "T133D_F20S_S1A.shp",
        [LuigiDate.parse(f"{first_date}-{last_date}")],
        []
    )

    # Run standard ifg workflow w/ a query that covers our test data
    do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        [],
        ["VV", "VH"],
        # Given no poeorb, but requiring scenes w/ precise orbits...
        s1_proc_without_poeorb,
        require_poeorb=True,
        geospatial_query=query,
        # ... we expect 0 scenes to be processed.
        expected_scenes=0,
        min_gamma_calls=0
    )
