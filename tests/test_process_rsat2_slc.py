import pytest
import tempfile
import shutil
import tarfile
from pathlib import Path
from unittest import mock

from tests.py_gamma_test_proxy import PyGammaTestProxy

import insar.process_rsat2_slc
from insar.process_rsat2_slc import process_rsat2_slc, ProcessSlcException

TEST_DATA_BASE = Path(__file__).parent / "data"
TEST_DATA_ID = "RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_HH_SLC"

TEST_DATA_PATH = TEST_DATA_BASE / f"{TEST_DATA_ID}.tar.gz"

@pytest.fixture
def pgp():
    return PyGammaTestProxy(exception_type=ProcessSlcException)

@pytest.fixture
def pgmock(monkeypatch, pgp):
    pgmock = mock.Mock(spec=PyGammaTestProxy, wraps=pgp)
    monkeypatch.setattr(insar.process_rsat2_slc, 'pg', pgmock)
    return pgmock

@pytest.fixture(scope="module")
def test_data():
    temp_dir = tempfile.TemporaryDirectory()

    # Extract test data
    with tarfile.open(TEST_DATA_PATH) as tar:
        tar.extractall(path=Path(temp_dir.name))

    with temp_dir as temp_path:
        yield Path(temp_path)


def test_rsat2_slc_processing(pgp, pgmock, test_data):
    # Run the SLC processing in a temp dir
    data_path = test_data / TEST_DATA_ID
    out_path = test_data / "test_output.slc"
    out_par_path = test_data / "test_output.slc.par"

    process_rsat2_slc(data_path, "HH", out_path)

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(out_path.exists())

    # Clean up output for subsequent tests (as we share test_data for the whole module to reduce IO)
    out_path.unlink()
    out_par_path.unlink()


def test_rsat2_slc_fails_with_missing_input(pgp, pgmock, test_data):
    # Run the SLC processing in a temp dir
    data_path = test_data / f"{TEST_DATA_ID}_does_not_exist"
    out_path = test_data / "test_output.slc"

    with pytest.raises(RuntimeError):
        process_rsat2_slc(data_path, "HH", out_path)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_rsat2_slc_fails_with_bad_polarisation(pgp, pgmock, test_data):
    # Run the SLC processing in a temp dir
    data_path = test_data / TEST_DATA_ID
    out_path = test_data / "test_output.slc"

    # Run w/ intentional typo
    with pytest.raises(RuntimeError):
        process_rsat2_slc(data_path, "CH", out_path)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_rsat2_slc_fails_with_missing_polarisation(pgp, pgmock, test_data):
    # Run the SLC processing in a temp dir
    data_path = test_data / TEST_DATA_ID
    out_path = test_data / "test_output.slc"

    # Run w/ VV even though the test data only has HH
    with pytest.raises(RuntimeError):
        process_rsat2_slc(data_path, "VV", out_path)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())


def test_rsat2_slc_fails_with_incomplete_data(pgp, pgmock, test_data):
    # Run the SLC processing in a temp dir
    data_path = test_data / TEST_DATA_ID
    out_path = test_data / "test_output.slc"

    # Delete an important file from the data set to make it incomplete
    (data_path / "product.xml").unlink()

    with pytest.raises(RuntimeError):
        process_rsat2_slc(data_path, "HH", out_path)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not out_path.exists())
