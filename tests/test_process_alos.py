import pytest

from tests.fixtures import *

from insar.process_alos_slc import process_alos_slc, ProcessSlcException

def test_alos1_slc_processing(pgp, pgmock, temp_out_dir, alos1_proc_config, alos1_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"
    out_par_path = temp_out_dir / "test_output.slc.par"

    process_alos_slc(
        alos1_proc_config,
        alos1_test_data[0],
        alos1_test_data[0].name[:8],
        "PALSAR1",
        "HH",
        out_path
    )

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(out_path.exists())

    # Clean up output for subsequent tests (as we share test_data for the whole module to reduce IO)
    out_path.unlink()
    out_par_path.unlink()


def test_alos1_slc_fails_with_missing_input(pgp, pgmock, temp_out_dir, alos1_proc_config, alos1_test_data):
    # Run the SLC processing in a temp dir
    data_path = temp_out_dir / "does_not_exist"
    out_path = temp_out_dir / "test_output.slc"

    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos1_proc_config,
            data_path,
            "20200101",
            "PALSAR1",
            "HH",
            out_path
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_alos1_slc_fails_with_bad_polarisation(pgp, pgmock, temp_out_dir, alos1_proc_config, alos1_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"

    # Run w/ intentional typo
    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos1_proc_config,
            alos1_test_data[0],
            alos1_test_data[0].name[:8],
            "PALSAR1",
            "CH",
            out_path
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_alos1_slc_fails_with_missing_polarisation(pgp, pgmock, temp_out_dir, alos1_proc_config, alos1_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"

    # Run w/ VV even though the test data only has HH
    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos1_proc_config,
            alos1_test_data[0],
            alos1_test_data[0].name[:8],
            "PALSAR1",
            "VV",
            out_path
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_alos1_slc_fails_with_incomplete_data(pgp, pgmock, temp_out_dir, alos1_proc_config, alos1_test_data):
    # Run the SLC processing in a temp dir
    data_path = temp_out_dir / alos1_test_data[0]
    out_path = temp_out_dir / "test_output.slc"

    # Delete an important file from the data set to make it incomplete
    prod_img = list(data_path.glob("IMG*HH*"))[0]
    prod_img.rename(data_path / "oops")

    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos1_proc_config,
            alos1_test_data[0],
            alos1_test_data[0].name[:8],
            "PALSAR1",
            "HH",
            out_path
        )

    # Restore file (for future tests)
    (data_path / "oops").rename(prod_img)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


# The ALOS 2 tests below should mirror the ALOS 1 ones above


def test_alos2_slc_processing(pgp, pgmock, temp_out_dir, alos2_proc_config, alos2_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"
    out_par_path = temp_out_dir / "test_output.slc.par"

    process_alos_slc(
        alos2_proc_config,
        alos2_test_data[0],
        alos2_test_data[0].name[:8],
        "PALSAR2",
        "HH",
        out_path
    )

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(out_path.exists())

    # Clean up output for subsequent tests (as we share test_data for the whole module to reduce IO)
    out_path.unlink()
    out_par_path.unlink()


def test_alos2_slc_fails_with_missing_input(pgp, pgmock, temp_out_dir, alos2_proc_config, alos2_test_data):
    # Run the SLC processing in a temp dir
    data_path = temp_out_dir / "does_not_exist"
    out_path = temp_out_dir / "test_output.slc"

    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos2_proc_config,
            data_path,
            "20200101",
            "PALSAR2",
            "HH",
            out_path
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_alos2_slc_fails_with_bad_polarisation(pgp, pgmock, temp_out_dir, alos2_proc_config, alos2_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"

    # Run w/ intentional typo
    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos2_proc_config,
            alos2_test_data[0],
            alos2_test_data[0].name[:8],
            "PALSAR2",
            "CH",
            out_path
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_alos2_slc_fails_with_missing_polarisation(pgp, pgmock, temp_out_dir, alos2_proc_config, alos2_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"

    # Run w/ VV even though the test data only has HH
    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos2_proc_config,
            alos2_test_data[0],
            alos2_test_data[0].name[:8],
            "PALSAR2",
            "VV",
            out_path
        )

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_alos2_slc_fails_with_incomplete_data(pgp, pgmock, temp_out_dir, alos2_proc_config, alos2_test_data):
    # Run the SLC processing in a temp dir
    data_path = temp_out_dir / alos2_test_data[0]
    out_path = temp_out_dir / "test_output.slc"

    # Delete an important file from the data set to make it incomplete
    prod_img = list(data_path.glob("IMG*HH*"))[0]
    prod_img.rename(data_path / "oops")

    with pytest.raises(ProcessSlcException):
        process_alos_slc(
            alos2_proc_config,
            alos2_test_data[0],
            alos2_test_data[0].name[:8],
            "PALSAR2",
            "HH",
            out_path
        )

    # Restore file (for future tests)
    (data_path / "oops").rename(prod_img)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())
