from tests.fixtures import *

from insar.paths.slc import SlcPaths
from insar.process_s1_slc import process_s1_slc

S1_TEST_DATA_DATE = S1_TEST_DATA_DATES[0]

def count_post_query_gamma_calls(gamma_calls):
    """
    This is a simple len() sort of function which filters out S1_burstloc calls
    which are used to parse input/source data information before processing.

    The reason we filter this out in these tests is because even with some invalid
    settings or outputs... inputs may still need to be parsed using GAMMA.
    """

    filtered_calls = [i for i in gamma_calls if i.program != 'S1_burstloc']
    return len(filtered_calls)

# Note: This is not a fixture, as it's just a wrapper around what S1 SLC processing
# may eventually look like (a function, not a class)
def do_processing(s1_test_data, temp_out_dir, s1_test_data_csv, pol):
    test_date = s1_test_data[0].parent.name
    test_data_dir = s1_test_data[0].parent.parent

    slc_paths = SlcPaths(temp_out_dir, test_date, pol)
    slc_paths.dir.mkdir(exist_ok=True, parents=True)

    process_s1_slc(
        slc_paths,
        pol,
        test_data_dir,
        s1_test_data_csv
    )

def test_s1_slc_processing(pgp, pgmock, temp_out_dir, s1_temp_job_proc, s1_test_data, s1_test_data_csv):
    paths = SlcPaths(s1_temp_job_proc, S1_TEST_DATA_DATE, "VV")

    assert(not paths.slc.exists())

    do_processing(
        s1_test_data,
        temp_out_dir,
        s1_test_data_csv,
        "VV"
    )

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(paths.slc.exists())


def test_s1_slc_fails_with_missing_input(pgp, pgmock, temp_out_dir, s1_temp_job_proc, s1_test_data_csv):
    paths = SlcPaths(s1_temp_job_proc, S1_TEST_DATA_DATE, "VV")

    assert(not paths.slc.exists())

    missing_data_dir = temp_out_dir / "does_not_exist"

    # Run w/ intentional typo
    with pytest.raises(Exception):
        do_processing(
            missing_data_dir,
            temp_out_dir,
            s1_test_data_csv,
            "VV"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)


def test_s1_slc_fails_with_bad_polarisation(pgp, pgmock, temp_out_dir, s1_temp_job_proc, s1_test_data, s1_test_data_csv):
    paths = SlcPaths(s1_temp_job_proc, S1_TEST_DATA_DATE, "VV")

    assert(not paths.slc.exists())

    # Run w/ intentional typo
    with pytest.raises(Exception):
        do_processing(
            s1_test_data,
            temp_out_dir,
            s1_test_data_csv,
            "BAD"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)
    assert(not paths.slc.exists())
    assert(not paths.slc_par.exists())


def test_s1_slc_fails_with_missing_polarisation(pgp, pgmock, temp_out_dir, s1_temp_job_proc, s1_test_data, s1_test_data_csv):
    paths = SlcPaths(s1_temp_job_proc, S1_TEST_DATA_DATE, "VV")

    assert(not paths.slc.exists())

    # Run w/ valid pol that doesn't exist
    with pytest.raises(Exception):
        do_processing(
            s1_test_data,
            temp_out_dir,
            s1_test_data_csv,
            "HH"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)
    assert(not paths.slc.exists())
    assert(not paths.slc_par.exists())


def test_s1_slc_fails_with_incomplete_data(pgp, pgmock, temp_out_dir, s1_temp_job_proc, s1_mutable_test_data, s1_test_data_csv):
    paths = SlcPaths(s1_temp_job_proc, S1_TEST_DATA_DATE, "VV")

    assert(not paths.slc.exists())

    # Delete important source data files to make it incomplete
    for test_data in s1_mutable_test_data:
        for xml in test_data.glob("*annotation/*.xml"):
            xml.unlink()

    with pytest.raises(FileNotFoundError):
        process_s1_slc(
            s1_mutable_test_data,
            temp_out_dir,
            s1_test_data_csv,
            "VV"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)
    assert(not paths.slc.exists())
    assert(not paths.slc_par.exists())
