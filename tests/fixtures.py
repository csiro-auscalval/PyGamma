import pytest
import tempfile
import tarfile
import shutil
from pathlib import Path
from unittest import mock

from tests.py_gamma_test_proxy import PyGammaTestProxy

from insar.project import ProcConfig

import insar.process_rsat2_slc
import insar.coregister_secondary

TEST_DATA_BASE = Path(__file__).parent / "data"

RS2_TEST_DATA_ID = "RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_HH_SLC"
RS2_TEST_DATA_PATH = TEST_DATA_BASE / f"{RS2_TEST_DATA_ID}.tar.gz"

@pytest.fixture(scope="session")
def proc_config():
    with open(Path(__file__).parent.absolute() / 'data' / '20151127' / 'gamma.proc', 'r') as fileobj:
        return ProcConfig.from_file(fileobj)

@pytest.fixture
def pgp():
    return PyGammaTestProxy(exception_type=RuntimeError)

@pytest.fixture
def pgmock(monkeypatch, pgp):
    pgmock = mock.Mock(spec=PyGammaTestProxy, wraps=pgp)

    def create_diff_par_mock(*args, **kwargs):
        diff_par_path = Path(args[2])
        diff_par_path.touch()

    # Coreg tests need some stdout data from offset_fit to work...
    # - this fake data should meet accuracy requirements / result in just
    # - a single refinement iteration as a result (which is all we need for testing).
    pgmock.offset_fit.return_value = (
        0,
        [
            "final model fit std. dev. (samples) range:   0.3699  azimuth:   0.1943",
            "final range offset poly. coeff.:             -0.00408   5.88056e-07   3.95634e-08  -1.75528e-11",
            "final azimuth offset poly. coeff.:             -0.00408   5.88056e-07   3.95634e-08  -1.75528e-11",
        ],
        [],
    )

    monkeypatch.setattr(insar.process_rsat2_slc, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_secondary, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_secondary, 'create_diff_par', create_diff_par_mock)

    return pgmock

@pytest.fixture(scope="session")
def rs2_test_data():
    temp_dir = tempfile.TemporaryDirectory()

    # Extract test data
    with tarfile.open(RS2_TEST_DATA_PATH) as tar:
        tar.extractall(path=Path(temp_dir.name))

    with temp_dir as temp_path:
        yield Path(temp_path) / RS2_TEST_DATA_ID

@pytest.fixture
def rs2_slc(pgp, pgmock, rs2_test_data):
    from insar.process_rsat2_slc import process_rsat2_slc

    test_slc_par = TEST_DATA_BASE / (RS2_TEST_DATA_ID + ".slc.par")
    out_path = rs2_test_data.parent / "test_output.slc"
    out_par_path = rs2_test_data.parent / "test_output.slc.par"

    process_rsat2_slc(rs2_test_data, "HH", out_path)
    shutil.copyfile(test_slc_par, out_par_path)
    pgp.reset_proxy()

    return out_path
