import pytest
from pathlib import Path
import tempfile
import click
from datetime import datetime, timezone

from tests.fixtures import *
from tests.test_workflow import count_dir_tree

from insar.scripts.package_insar import main as package_insar

from insar.scripts.process_gamma import run_ard_inline
from insar.project import ARDWorkflow

@pytest.fixture
def fake_stack(pgp, pgmock, s1_proc, s1_test_data_zips):
    # Setup temporary dirs to run the workflow in
    temp_dir = tempfile.TemporaryDirectory()
    job_dir = Path(temp_dir.name) / "job"
    out_dir = Path(temp_dir.name) / "out"

    out_dir.mkdir()
    job_dir.mkdir()

    # S1 test data has VV+VH
    source_data = [str(i) for i in s1_test_data_zips]
    pols = ["VV", "VH"]

    # Setup test workflow arguments
    args = {
        "proc_file": str(s1_proc),
        "include_dates": '',
        "exclude_dates": '',
        "source_data": source_data,
        "workdir": str(job_dir),
        "outdir": str(out_dir),
        "polarization": pols,
        "cleanup": True,
        "workflow": ARDWorkflow.Interferogram
    }

    # Run the workflow
    run_ard_inline(args)

    return temp_dir, out_dir

#
# Note: As these unit tests are all testing user scripts, we test the scripts
# in a similar way to how the user would use the scripts...
#
# Specifically we run the script as similarly to the CLI way as possible w/
# a click.Context, and then check the output logs and files.
#

def package_stack(temp_dir, data_dir, package_dir = None, overwrite_existing = None, error_on_existing = None):
    optional_args = {}

    if overwrite_existing is not None:
        optional_args["overwrite_existing"] = overwrite_existing

    if error_on_existing is not None:
        optional_args["error_on_existing"] = error_on_existing

    if not package_dir:
        package_dir = Path(temp_dir.name) / "packaged"

    package_dir.mkdir(parents=True, exist_ok=True)
    package_log = package_dir / 'packaging.log'

    # S1 test stack id is a track_frame string
    track, frame = S1_TEST_STACK_ID.split("_")

    # Run the packaging script
    cli_runner = click.Context(package_insar)
    cli_runner.invoke(
        package_insar,
        track=str(track),
        frame=str(frame),
        input_dir=str(data_dir),
        pkgdir=str(package_dir),
        log_pathname=str(package_log),
        **optional_args
    )
    print(package_log.read_text())

    return package_dir, package_log


def test_package_new_stack(fake_stack):
    package_dir, package_log = package_stack(*fake_stack)

    # There should be no failures in the log
    error_msg = "Packaging failed with exception"
    assert(error_msg not in package_log.read_text())

    # Assert we have a packaged product!
    assert((package_dir / "ga_s1ac_nrb").exists())
    assert(len(list((package_dir / "ga_s1ac_nrb").glob("**/*.odc-metadata.yaml"))) == len(S1_TEST_DATA_DATES))


def test_package_empty_stack_produces_error():
    temp_dir = tempfile.TemporaryDirectory()
    out_dir = Path("path/does/not/exist")

    package_dir, package_log = package_stack(temp_dir, out_dir)

    # There should be a failure in the log
    error_msg = '"level": "error"'
    assert(error_msg in package_log.read_text())

    # Assert we have no packaged files!
    assert(count_dir_tree(package_dir / "ga_s1ac_nrb", False) == 0)


def test_package_invalid_stack_produces_error(fake_stack):
    temp_dir, data_dir = fake_stack

    # Delete metadata and burst data
    # - this will invalidate the stack... and prevent packaging
    # - of it, as the packaging script requires this information.
    metadata_file = data_dir / "metadata.json"
    burst_data_file = list(data_dir.glob("*burst_data.csv"))

    assert(metadata_file.exists())
    metadata_file.unlink()

    assert(len(burst_data_file) == 1)
    burst_data_file[0].unlink()

    # Run packaging...
    package_dir, package_log = package_stack(temp_dir, data_dir)

    # There should be a failure in the log
    error_msg = '"level": "error"'
    assert(error_msg in package_log.read_text())

    # Assert we have no packaged files!
    assert(count_dir_tree(package_dir / "ga_s1ac_nrb", False) == 0)


def test_continue_package_partially_packaged_stack(fake_stack):
    track, frame = S1_TEST_STACK_ID.split("_")
    test_date = S1_TEST_DATA_DATES[0]
    year = test_date[:4]
    month = test_date[4:6]
    date = test_date[6:]

    # Pad track/frame
    track = f"{track[0]}{int(track[1:-1]):03}{track[-1]}"
    frame = f"{frame[0]}{int(frame[1:-1]):03}{frame[-1]}"

    # Package a new stack
    package_dir, package_log = package_stack(*fake_stack)

    # Record the timestamp of a packaged stack date
    packaged_date_dir = package_dir / "ga_s1ac_nrb" / track / frame / year / month / f"{date}_interim"
    first_packaged_date_timestamp = datetime.fromtimestamp(packaged_date_dir.stat().st_mtime, tz=timezone.utc)

    # Then delete that packaged date dir, run it again...
    shutil.rmtree(packaged_date_dir)
    package_dir, package_log = package_stack(*fake_stack, package_dir)

    # ... and ensure it's over-written (newer timestamps)
    second_packaged_date_timestamp = datetime.fromtimestamp(packaged_date_dir.stat().st_mtime, tz=timezone.utc)

    assert(second_packaged_date_timestamp > first_packaged_date_timestamp)


def test_package_already_packaged_stack_overwrites_if_asked(fake_stack):
    track, frame = S1_TEST_STACK_ID.split("_")

    # Package a new stack
    package_dir, package_log = package_stack(*fake_stack)

    # Record the timestamp of a packaged stack date
    packaged_metadata = list(package_dir.glob("**/*.odc-metadata.yaml"))
    first_metadata_timestamps = [datetime.fromtimestamp(i.stat().st_mtime, tz=timezone.utc) for i in packaged_metadata]

    # Then run it again...
    package_dir, package_log = package_stack(*fake_stack, package_dir, overwrite_existing=True)

    # ... and ensure it's over-written (newer timestamps)
    second_metadata_timestamps = [datetime.fromtimestamp(i.stat().st_mtime, tz=timezone.utc) for i in packaged_metadata]

    for first_timestamp, second_timestamp in zip(first_metadata_timestamps, second_metadata_timestamps):
        assert(second_timestamp > first_timestamp)


def test_package_partially_packaged_stack_errors_if_asked(fake_stack):
    # Package a new stack
    package_dir, package_log = package_stack(*fake_stack)

    # There should be no failures in the log
    error_msg = "Packaging failed with exception"
    assert(error_msg not in package_log.read_text())

    # Assert we have successfully packaged files!
    assert(len(list(package_dir.glob("**/*.odc-metadata.yaml"))) == len(S1_TEST_DATA_DATES))

    # Run the standard smoke test AGAIN with error on existing, ensuring it crashes
    package_dir, package_log = package_stack(*fake_stack, package_dir, error_on_existing=True)

    # There should now be errors in the log
    error_msg = '"level": "error"'
    assert(error_msg in package_log.read_text())
