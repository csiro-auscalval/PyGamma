import pytest
from pathlib import Path
import tempfile
from datetime import datetime, timezone
import json
from typing import Optional

from tests.fixtures import *

from insar.scripts.process_nci_report import main as process_nci_report
from insar.project import ARDWorkflow

from tests.test_workflow import do_ard_workflow_validation, print_dir_tree


#
# Note: As these unit tests are all testing user scripts, we test the scripts
# in a similar way to how the user would use the scripts...
#
# Specifically we run the script as similarly to the CLI way as possible w/
# a click.Context, and then check the output logs and files.
#


fake_job_stdout = """this is a fake stdout file similar to what NCI would produce

... there would usually be lots of Luigi stuff here ...

This progress looks :) because there were failed tasks but they all succeeded in a retry

===== Luigi Execution Summary =====


======================================================================================
                  Resource Usage on 2022-01-20 10:53:46:
   Job Id:             34018944.gadi-pbs
   Project:            dg9
   Exit Status:        0
   Service Units:      48.05
   NCPUs Requested:    48                     NCPUs Used: 48
                                           CPU Time Used: 03:28:43
   Memory Requested:   192.0GB               Memory Used: 121.12GB
   Walltime requested: 02:00:00            Walltime Used: 00:30:02
   JobFS requested:    400.0GB                JobFS used: 23.41GB
======================================================================================
"""


def validate_report_json_product_summary(
    report: dict,
    expected_num_scenes: int,
    expected_num_interferograms: int,
    expected_missing_nrb: Optional[int] = None,
    expected_failed_nrb: Optional[int] = None,
    expected_missing_ifg: Optional[int] = None,
    expected_failed_ifg: Optional[int] = None
):
    """
    This function asserts the rough structure of the report JSON, and that the headline
    summary on product numbers match our expectations.

    This function does NOT dig into the job/output queries, product errors, or run information.
    """

    # Sanity check the high level structure of JSON
    assert "metadata" in report
    assert "job_query" in report
    assert "out_query" in report

    metadata = report["metadata"]
    pols = metadata["polarisations"]
    stack_id = metadata["stack_id"]
    job_query = report["job_query"]
    out_query = report["out_query"]

    assert "stack_id" in metadata

    # Note: We don't sanity check the metadata (it's a copy of our standard metadata.json file)
    # (outside the scope of this test which is on the reporting data)

    # Sanity check job query structure
    if job_query:
        assert "job_runs" in job_query
        assert "total_walltime" in job_query
        assert "total_service_units" in job_query
        assert "started_backscatter" in job_query
        assert "started_ifgs" in job_query
        assert "failed_backscatter" in job_query
        assert "failed_ifgs" in job_query
        assert "completed_backscatter" in job_query
        assert "completed_ifgs" in job_query
        assert "walltime_slc" in job_query
        assert "walltime_coregistration" in job_query
        assert "walltime_backscatter" in job_query
        assert "walltime_ifgs" in job_query

    # Sanity check out query structure
    if out_query:
        assert "all_scene_dates" in out_query
        assert "all_ifg_date_pairs" in out_query
        assert "completed_slcs" in out_query
        assert "missing_slcs" in out_query
        assert "completed_coregs" in out_query
        assert "missing_coregs" in out_query
        assert "completed_backscatter" in out_query
        assert "missing_backscatter" in out_query
        assert "completed_ifgs" in out_query
        assert "missing_ifgs" in out_query
        assert "coreg_quality_warn" in out_query
        assert "metadata" in out_query

    # Get high level stats
    num_total_slc_scenes = report["num_total_slc_scenes"]
    num_total_ifg_scenes = report["num_total_ifg_scenes"]
    num_completed_backscatter = report["num_completed_backscatter"]
    num_completed_ifgs = report["num_completed_ifgs"]
    num_failed_backscatter = report["num_failed_backscatter"]
    num_failed_ifgs = report["num_failed_ifgs"]
    num_missing_backscatter = report["num_missing_backscatter"]
    num_missing_ifgs = report["num_missing_ifgs"]

    # Assert they match our expectations
    if out_query:
        all_scene_dates = out_query["all_scene_dates"]
        all_ifg_date_pairs = out_query["all_ifg_date_pairs"]

        assert len(all_scene_dates) == expected_num_scenes
        assert len(all_ifg_date_pairs) == expected_num_interferograms

    assert num_total_slc_scenes == expected_num_scenes
    assert num_total_ifg_scenes == expected_num_interferograms

    if expected_failed_nrb is not None and num_failed_backscatter != "?":
        assert num_failed_backscatter == expected_failed_nrb

    if expected_failed_ifg is not None and num_failed_ifgs != "?":
        assert num_failed_ifgs == expected_failed_ifg

    if expected_missing_nrb is not None and num_missing_backscatter != "?":
        assert num_missing_backscatter == expected_missing_nrb

    if expected_missing_ifg is not None and num_missing_ifgs != "?":
        assert num_missing_ifgs == expected_missing_ifg

    if num_missing_backscatter != "?":
        assert num_completed_backscatter == (num_total_slc_scenes*len(pols) - num_missing_backscatter)

    if num_missing_ifgs != "?":
        assert num_completed_ifgs == (num_total_ifg_scenes - num_missing_ifgs)


def test_report_good_stack(pgp, pgmock, s1_proc, s1_test_data_zips):
    # Run a normal workflow w/ good data
    source_data = [str(i) for i in s1_test_data_zips]
    pols = ["VV", "VH"]

    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        s1_proc
    )

    # Write a fake NCI summary report
    nci_report_path = job_dir / "testing.o1234"
    nci_report_path.write_text(fake_job_stdout)

    # Run reporting script
    report_json_path = job_dir / "report.json"
    report_csv_path = job_dir / "report_summary.csv"

    cli_args = [
        str(job_dir),
        # Print to stdout, just for the code coverage / smoke test (we don't parse the stdout)
        "--print",
        # Write JSON report (we test this)
        "--json", str(report_json_path),
        # Write CSV summary (we test this)
        "--csv", str(report_csv_path)
    ]

    process_nci_report(cli_args)

    # Validate output
    report = json.loads(report_json_path.read_text())
    report = report["testing"]  # our test jobs have the stack id "testing"

    validate_report_json_product_summary(
        report,
        # Expect 2 scene dates, with 1 interferogram
        2,
        1,
        # Expect no failures or missing products of any kind
        0,
        0,
        0,
        0
    )

    # Validate CSV summary
    summary_csv = report_csv_path.read_text().splitlines()

    # should only have 2 lines, header + our 1 frame
    assert len(summary_csv) == 2

    summary = summary_csv[1].split(",")
    frame, completed, expected, errors, remaining, eta, info = summary

    assert frame == "testing"
    assert int(completed) == 1
    assert int(expected) == 1
    assert int(errors) == 0
    assert int(remaining) == 0


def test_report_incomplete_stack(pgp, pgmock, s1_proc, s1_test_data_zips):
    # Run a normal workflow w/ good data
    source_data = [str(i) for i in s1_test_data_zips]
    pols = ["VV", "VH"]

    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        s1_proc
    )

    # Remove some products to make the report indicate they're "missing"
    shutil.rmtree(out_dir / "INT")

    # Remove the job directory completely in this test (just to cover some more code paths)
    # - as there's backup paths for if "only" one of the job 'or' out dir exists (plus the main path of both)
    # - for missing data, the out dir is enough for accurate reporting of missing products
    shutil.rmtree(job_dir)

    # Run reporting script
    report_json_path = out_dir / "report.json"
    report_csv_path = out_dir / "report_summary.csv"

    cli_args = [
        str(out_dir),
        # Print to stdout, just for the code coverage / smoke test (we don't parse the stdout)
        "--print",
        # Write JSON report (we test this)
        "--json", str(report_json_path),
        # Write CSV summary (we test this)
        "--csv", str(report_csv_path)
    ]

    process_nci_report(cli_args)

    # Validate output
    report = json.loads(report_json_path.read_text())
    report = report["testing"]  # our test jobs have the stack id "testing"

    validate_report_json_product_summary(
        report,
        # Expect 2 scene dates, with 1 interferogram
        2,
        1,
        # But the interferogram should be missing...
        0,
        0,
        1,
        0
    )

    # Validate CSV summary
    summary_csv = report_csv_path.read_text().splitlines()

    # should only have 2 lines, header + our 1 frame
    assert len(summary_csv) == 2

    summary = summary_csv[1].split(",")
    frame, completed, expected, errors, remaining, eta, info = summary

    assert frame == "testing"
    assert int(completed) == 0
    assert int(expected) == 1
    assert errors == "?"
    assert int(remaining) == 1


def test_report_partially_fail_stack(pgp, pgmock, s1_proc, s1_test_data_zips):
    # Inject an error into IFG processing to cause a product failure
    def raise_error(*args, **kwargs):
        raise Exception("Test error!")

    pgmock.unw_model.side_effect = raise_error

    # Run a normal workflow w/ good data
    source_data = [str(i) for i in s1_test_data_zips]
    pols = ["VV", "VH"]

    out_dir, job_dir, temp_dir = do_ard_workflow_validation(
        pgp,
        ARDWorkflow.Interferogram,
        source_data,
        pols,
        s1_proc,
        validate_ifg=False
    )

    # Remove the output directory completely in this test (just to cover some more code paths)
    # - as there's backup paths for if "only" one of the job 'or' out dir exists (plus the main path of both)
    # - for missing data, the job dir is enough for accurate reporting of product failures
    shutil.rmtree(out_dir)

    # Run reporting script
    report_json_path = job_dir / "report.json"
    report_csv_path = job_dir / "report_summary.csv"

    cli_args = [
        str(job_dir),
        # Print to stdout, just for the code coverage / smoke test (we don't parse the stdout)
        "--print",
        # Write JSON report (we test this)
        "--json", str(report_json_path),
        # Write CSV summary (we test this)
        "--csv", str(report_csv_path)
    ]

    process_nci_report(cli_args)

    # Validate output
    report = json.loads(report_json_path.read_text())
    report = report["testing"]  # our test jobs have the stack id "testing"

    validate_report_json_product_summary(
        report,
        # Expect 2 scene dates, with 1 interferogram
        2,
        1,
        # But the interferogram should have failed...
        0,
        0,
        0,
        1
    )

    # Validate CSV summary
    summary_csv = report_csv_path.read_text().splitlines()

    # should only have 2 lines, header + our 1 frame
    assert len(summary_csv) == 2

    summary = summary_csv[1].split(",")
    frame, completed, expected, errors, remaining, eta, info = summary

    assert frame == "testing"
    assert int(completed) == 0
    assert int(expected) == 1
    assert int(errors) == 1
    assert remaining == "?"


def test_report_missing_stack(temp_out_dir):
    # Run reporting script on an empty dir (not a stack dir at all)
    report_json_path = temp_out_dir / "report.json"
    report_csv_path = temp_out_dir / "report_summary.csv"

    cli_args = [
        str(temp_out_dir),
        # Print to stdout, just for the code coverage / smoke test (we don't parse the stdout)
        "--print",
        # Write JSON report (we test this)
        "--json", str(report_json_path),
        # Write CSV summary (we test this)
        "--csv", str(report_csv_path)
    ]

    with pytest.raises(SystemExit):
        process_nci_report(cli_args)

    assert not report_json_path.exists()
    assert not report_csv_path.exists()
