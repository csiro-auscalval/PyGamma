import sys
import pathlib
from unittest import mock

import pytest


PY_GAMMA_MODULE = "py_gamma"

if PY_GAMMA_MODULE not in sys.modules:
    # mock Gamma for local testing
    py_gamma_mock = mock.Mock()
    msg = "This is a mock py_gamma, Gamma not found/installed on this platform"
    sys.modules[PY_GAMMA_MODULE] = py_gamma_mock

from insar import process_ifg  # noqa


@pytest.fixture
def pg_int_mock():
    """Create basic mock of the py_gamma module for the INT processing step."""
    pg_mock = mock.Mock()
    pg_mock.create_offset.return_value = 0
    pg_mock.offset_pwr.return_value = 0
    pg_mock.offset_fit.return_value = 0
    return pg_mock

# FIXME: tweak settings to ensure working dir don't have to be changed for INT processing
# TODO: check if structlog called at least once for messages? Needs structlog mock


def test_int(monkeypatch, pg_int_mock):
    """Verify default path through the INT processing step without cleanup."""

    monkeypatch.setattr(process_ifg, 'pg', pg_int_mock)  # TODO: or use unittest.mock's patch? Which is better?

    ifg_offset = mock.Mock(spec=pathlib.Path)
    ifg_offset.exists.return_value = False  # offset not yet processed

    process_ifg.calc_int(ifg_offset, *range(13), clean_up=False)  # use fake args for now

    assert pg_int_mock.create_offset.called

    # ensure CSK sensor block / SP mode section is skipped
    assert pg_int_mock.init_offset_orbit.called is False
    assert pg_int_mock.init_offset.called is False

    # check the core processing was called
    assert pg_int_mock.offset_pwr.called
    assert pg_int_mock.offset_fit.called
    assert pg_int_mock.create_diff_par.called


def test_int_with_cleanup(monkeypatch, pg_int_mock):
    monkeypatch.setattr(process_ifg, 'pg', pg_int_mock)  # TODO: or use unittest.mock's patch? Which is better?

    ifg_offset = mock.Mock(spec=pathlib.Path)
    ifg_offset.exists.return_value = False  # offset not yet processed

    ifg_offs = mock.Mock(spec=pathlib.Path)
    ifg_ccp = mock.Mock(spec=pathlib.Path)
    ifg_coffs = mock.Mock(spec=pathlib.Path)
    ifg_coffsets = mock.Mock(spec=pathlib.Path)

    assert ifg_offs.unlink.called is False
    assert ifg_ccp.unlink.called is False
    assert ifg_coffs.unlink.called is False
    assert ifg_coffsets.unlink.called is False

    process_ifg.calc_int(ifg_offset, *range(6),
                         ifg_offs, ifg_coffs, ifg_coffsets, ifg_ccp,
                         "fake1", "fake2", "fake3",
                         clean_up=True)  # use fake args for now

    assert ifg_offs.unlink.called
    assert ifg_ccp.unlink.called
    assert ifg_coffs.unlink.called
    assert ifg_coffsets.unlink.called
