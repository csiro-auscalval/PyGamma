import pathlib
from unittest import mock

from insar import process_ifg
from insar.process_ifg import ProcessIfgException
from insar.project import ProcConfig, IfgFileNames

import structlog
import pytest


# FIXME: tweak settings to ensure working dir doesn't have to be changed for INT processing (do in workflow)


# TODO: can monkeypatch be done at higher level scope to apply to multiple test funcs?
@pytest.fixture
def pg_int_mock():
    """Create basic mock of the py_gamma module for INT processing step."""
    pg_mock = mock.Mock()
    pg_mock.create_offset.return_value = 0
    pg_mock.offset_pwr.return_value = 0
    pg_mock.offset_fit.return_value = 0
    pg_mock.create_diff_par.return_value = 0
    return pg_mock


@pytest.fixture
def pc_mock():
    """Returns basic mock to simulate a ProcConfig object."""
    pc = mock.Mock(spec=ProcConfig)
    return pc


@pytest.fixture
def ic_mock():
    """Returns basic mock to simulate an IfgFileNames object."""
    ic = mock.Mock(spec=IfgFileNames)
    return ic


def test_calc_int(monkeypatch, pg_int_mock, pc_mock, ic_mock):
    """Verify default path through the INT processing step without cleanup."""

    # craftily substitute the 'pg' py_gamma obj for a mock: avoids a missing import when testing
    # locally, or calling the real thing on Gadi...
    # TODO: monkeypatch or use unittest.mock's patch? Which is better?
    monkeypatch.setattr(process_ifg, "pg", pg_int_mock)

    ic_mock.ifg_off = mock.Mock(spec=pathlib.Path)
    ic_mock.ifg_off.exists.return_value = False  # offset not yet processed

    process_ifg.calc_int(pc_mock, ic_mock, clean_up=False)

    assert pg_int_mock.create_offset.called

    # ensure CSK sensor block / SP mode section is skipped
    assert pg_int_mock.init_offset_orbit.called is False
    assert pg_int_mock.init_offset.called is False

    # check the core processing was called
    assert pg_int_mock.offset_pwr.called
    assert pg_int_mock.offset_fit.called
    assert pg_int_mock.create_diff_par.called


def test_calc_int_with_cleanup(monkeypatch, pg_int_mock, pc_mock, ic_mock):
    monkeypatch.setattr(process_ifg, "pg", pg_int_mock)

    ic_mock.ifg_off = mock.Mock(spec=pathlib.Path)
    ic_mock.ifg_off.exists.return_value = False  # offset not yet processed

    ic_mock.ifg_offs = mock.Mock(spec=pathlib.Path)
    ic_mock.ifg_ccp = mock.Mock(spec=pathlib.Path)
    ic_mock.ifg_coffs = mock.Mock(spec=pathlib.Path)
    ic_mock.ifg_coffsets = mock.Mock(spec=pathlib.Path)

    assert ic_mock.ifg_offs.unlink.called is False
    assert ic_mock.ifg_ccp.unlink.called is False
    assert ic_mock.ifg_coffs.unlink.called is False
    assert ic_mock.ifg_coffsets.unlink.called is False

    process_ifg.calc_int(pc_mock, ic_mock, clean_up=True)

    assert ic_mock.ifg_offs.unlink.called
    assert ic_mock.ifg_ccp.unlink.called
    assert ic_mock.ifg_coffs.unlink.called
    assert ic_mock.ifg_coffsets.unlink.called


def test_calc_int_with_errors(monkeypatch, pg_int_mock, pc_mock, ic_mock):
    monkeypatch.setattr(process_ifg, "pg", pg_int_mock)

    log_mock = mock.Mock(
        spec=structlog.stdlib.BoundLogger
    )  # this spec has base error(), msg() etc
    assert log_mock.error.called is False
    monkeypatch.setattr(process_ifg, "_LOG", log_mock)

    ic_mock.ifg_off = mock.Mock(spec=pathlib.Path)
    ic_mock.ifg_off.exists.return_value = False
    pg_int_mock.create_offset.return_value = -1

    with pytest.raises(ProcessIfgException):
        process_ifg.calc_int(pc_mock, ic_mock, clean_up=False)

    assert log_mock.error.called
