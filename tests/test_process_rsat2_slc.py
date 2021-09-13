import pytest

from tests.fixtures import *

from insar.process_rsat2_slc import process_rsat2_slc

def test_rsat2_slc_processing(pgp, pgmock, temp_out_dir, rs2_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"
    out_par_path = temp_out_dir / "test_output.slc.par"

    process_rsat2_slc(rs2_test_data[0], "HH", out_path)

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(out_path.exists())

    # Clean up output for subsequent tests (as we share test_data for the whole module to reduce IO)
    out_path.unlink()
    out_par_path.unlink()


def test_rsat2_slc_fails_with_missing_input(pgp, pgmock, temp_out_dir, rs2_test_data):
    # Run the SLC processing in a temp dir
    data_path = temp_out_dir / "does_not_exist"
    out_path = temp_out_dir / "test_output.slc"

    with pytest.raises(RuntimeError):
        process_rsat2_slc(data_path, "HH", out_path)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_rsat2_slc_fails_with_bad_polarisation(pgp, pgmock, temp_out_dir, rs2_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"

    # Run w/ intentional typo
    with pytest.raises(RuntimeError):
        process_rsat2_slc(rs2_test_data[0], "CH", out_path)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_rsat2_slc_fails_with_missing_polarisation(pgp, pgmock, temp_out_dir, rs2_test_data):
    # Run the SLC processing in a temp dir
    out_path = temp_out_dir / "test_output.slc"

    # Run w/ VV even though the test data only has HH
    with pytest.raises(RuntimeError):
        process_rsat2_slc(rs2_test_data[0], "VV", out_path)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_rsat2_slc_fails_with_incomplete_data(pgp, pgmock, temp_out_dir, rs2_test_data):
    # Run the SLC processing in a temp dir
    data_path = temp_out_dir / rs2_test_data[0]
    out_path = temp_out_dir / "test_output.slc"

    # Delete an important file from the data set to make it incomplete
    prod_xml = data_path / "product.xml"
    prod_xml = prod_xml.rename(data_path / "oops")

    with pytest.raises(RuntimeError):
        process_rsat2_slc(data_path, "HH", out_path)

    # Restore file (for future tests)
    prod_xml.rename(data_path / "product.xml")

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())
