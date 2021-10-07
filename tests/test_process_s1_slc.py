from tests.fixtures import *

from insar.constant import SlcFilenames
from insar.process_s1_slc import SlcProcess

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
def process_s1_slc(test_data_dir, temp_out_dir, s1_proc, s1_test_data_csv, pol):
    Path(temp_out_dir / S1_TEST_DATA_DATE).mkdir(exist_ok=True, parents=True)

    processor = SlcProcess(
        test_data_dir,
        temp_out_dir,
        pol,
        S1_TEST_DATA_DATE,
        s1_test_data_csv
    )

    processor.main()

    return processor

def test_s1_slc_processing(pgp, pgmock, temp_out_dir, s1_proc, s1_test_data, s1_test_data_csv):
    # Unfortunately SlcProcess has assumptions on sub-dirs within the dir you provide it, as it
    # has it's own opinions on structure (unlike other modules which get it's structure from
    # the caller and .proc settings) - so for now, we have to hard-code this here too...
    out_dir = temp_out_dir / S1_TEST_DATA_DATE
    test_out_slc = out_dir / SlcFilenames.SLC_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    test_out_slc_par = out_dir / SlcFilenames.SLC_PAR_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    # Note: .parent.parent is hacky implementation detail that's hard-coded into SlcProcess...
    # - this will almost certainly be fixed when it's refactored to follow the same standards as
    # - the other processing modules.
    test_data_dir = s1_test_data[0].parent.parent

    process_s1_slc(
        test_data_dir,
        temp_out_dir,
        s1_proc,
        s1_test_data_csv,
        "VV"
    )

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(test_out_slc.exists())

    # Clean up output for subsequent tests (as we share test_data for the whole module to reduce IO)
    test_out_slc.unlink()
    test_out_slc_par.unlink()


def test_s1_slc_fails_with_missing_input(pgp, pgmock, temp_out_dir, s1_proc, s1_test_data, s1_test_data_csv):
    missing_data_dir = temp_out_dir / "does_not_exist"

    # Run w/ intentional typo
    with pytest.raises(Exception):
        process_s1_slc(
            missing_data_dir,
            temp_out_dir,
            s1_proc,
            s1_test_data_csv,
            "VV"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)


def test_s1_slc_fails_with_bad_polarisation(pgp, pgmock, temp_out_dir, s1_proc, s1_test_data, s1_test_data_csv):
    out_dir = temp_out_dir / S1_TEST_DATA_DATE
    test_out_slc = out_dir / SlcFilenames.SLC_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    test_out_slc_par = out_dir / SlcFilenames.SLC_PAR_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    test_data_dir = s1_test_data[0].parent.parent

    # Run w/ intentional typo
    with pytest.raises(Exception):
        process_s1_slc(
            test_data_dir,
            temp_out_dir,
            s1_proc,
            s1_test_data_csv,
            "BAD"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)
    assert(not test_out_slc.exists())
    assert(not test_out_slc_par.exists())


def test_s1_slc_fails_with_missing_polarisation(pgp, pgmock, temp_out_dir, s1_proc, s1_test_data, s1_test_data_csv):
    out_dir = temp_out_dir / S1_TEST_DATA_DATE
    test_out_slc = out_dir / SlcFilenames.SLC_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    test_out_slc_par = out_dir / SlcFilenames.SLC_PAR_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    test_data_dir = s1_test_data[0].parent.parent

    # Run w/ valid pol that doesn't exist
    with pytest.raises(Exception):
        process_s1_slc(
            test_data_dir,
            temp_out_dir,
            s1_proc,
            s1_test_data_csv,
            "HH"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)
    assert(not test_out_slc.exists())
    assert(not test_out_slc_par.exists())


def test_s1_slc_fails_with_incomplete_data(pgp, pgmock, temp_out_dir, s1_proc, s1_test_data, s1_test_data_csv):
    out_dir = temp_out_dir / S1_TEST_DATA_DATE
    test_out_slc = out_dir / SlcFilenames.SLC_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    test_out_slc_par = out_dir / SlcFilenames.SLC_PAR_FILENAME.value.format(S1_TEST_DATA_DATE, "VV")
    test_data_dir = s1_test_data[0].parent.parent

    # Delete important source data files to make it incomplete
    for xml in s1_test_data[0].glob("*annotation/*.xml"):
        xml.unlink()

    with pytest.raises(Exception):
        process_s1_slc(
            test_data_dir,
            temp_out_dir,
            s1_proc,
            s1_test_data_csv,
            "VV"
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(count_post_query_gamma_calls(pgp.call_sequence) == 0)
    assert(not test_out_slc.exists())
    assert(not test_out_slc_par.exists())
