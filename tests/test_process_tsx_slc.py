import shutil

from insar.process_tsx_slc import process_tsx_slc, ProcessSlcException
from tests.fixtures import pgp, pgmock, temp_out_dir, test_data_dir, tsx_test_data  # noqa
from tests.fixtures import TSX_TEST_DATA_SUBDIRS
import pytest

default_pol = "HH"


@pytest.fixture
def output_slc(temp_out_dir):
    return temp_out_dir / "20170411_HH.slc"


@pytest.fixture
def dummy_output_slc(temp_out_dir):
    return temp_out_dir / "dummy.slc"


def test_tsx_slc_processing(pgp, pgmock, temp_out_dir, tsx_test_data, output_slc):
    # Run SLC processing in a temp dir
    assert not output_slc.exists()

    # build raw data path to equivalent to path returned in sensors/tsx.py acquire_source_data()
    scene_date = tsx_test_data[0].name
    tsx_dir = "TDX1_SAR__SSC______SM_S_SRA_20170411T192821_20170411T192829"
    product_path = tsx_test_data[0] / scene_date / tsx_dir

    process_tsx_slc(product_path, default_pol, output_slc)

    # Ensure the output is created and no errors occurred
    assert pgp.error_count == 0
    assert len(pgp.call_sequence) >= 2
    assert output_slc.exists()
    output_slc_par = output_slc.with_suffix(".slc.par")
    assert output_slc_par.exists(), str("\n".join([str(x) for x in temp_out_dir.glob('*')]))


def test_tsx_slc_fails_with_missing_input(pgp, pgmock, temp_out_dir, tsx_test_data, dummy_output_slc):
    # try running SLC processing from a src dir that does not exist
    data_path = temp_out_dir / "21230102"

    with pytest.raises(ProcessSlcException):
        process_tsx_slc(data_path, default_pol, dummy_output_slc)

    # Ensure not a single GAMMA call occurred & no output exists
    assert len(pgp.call_sequence) == 0
    out_slc_paths = list(temp_out_dir.glob("*.slc"))
    assert out_slc_paths == []


def test_tsx_slc_fails_with_incomplete_data(pgp, pgmock, temp_out_dir, tsx_test_data, dummy_output_slc):
    # copy test data & avoid modifying the source data
    data_copy = temp_out_dir / "tsx_data_copy"
    shutil.copytree(tsx_test_data[0], data_copy)

    # "Delete" important data from the set, making it incomplete
    scene_date = tsx_test_data[0].name
    annotation_xml = (data_copy / scene_date / TSX_TEST_DATA_SUBDIRS[0] / TSX_TEST_DATA_SUBDIRS[0]).with_suffix(".xml")
    shutil.move(annotation_xml, annotation_xml.with_suffix(".bak"))

    # Run the SLC processing in a temp dest dir
    with pytest.raises(ProcessSlcException):
        process_tsx_slc(data_copy, default_pol, dummy_output_slc)

    # Ensure not a single GAMMA call occurred & no output exists
    assert len(pgp.call_sequence) == 0
    paths = list(temp_out_dir.glob("*"))
    assert paths == [data_copy]  # nothing produced, only the data dir should exist there


def test_tsx_slc_fails_with_incomplete_missing_dir(pgp, pgmock, temp_out_dir, dummy_output_slc):
    # try instance where the big ugly dir name is missing
    data = temp_out_dir / "20001234"
    data.mkdir(exist_ok=False)  # error, root dir doesn't contain the ugly subdir

    # Run the SLC processing in a temp dest dir
    with pytest.raises(ProcessSlcException):
        process_tsx_slc(data, default_pol, dummy_output_slc)

    assert list(temp_out_dir.glob("*")) == [data]
    assert len(pgp.call_sequence) == 0
