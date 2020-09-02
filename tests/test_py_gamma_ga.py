import os
from unittest import mock
from collections import Sequence, namedtuple
from insar import py_gamma_ga

import pytest


FAKE_INSTALL_DIR = "/fake/gamma/dir"


def test_find_gamma_installed_packages(monkeypatch):
    monkeypatch.setattr(os, "listdir", lambda _: [".", "..", "ISP", "MSP"])

    pkgs = py_gamma_ga.find_gamma_installed_packages(FAKE_INSTALL_DIR)
    assert isinstance(pkgs, Sequence)
    assert "ISP" in pkgs


def test_find_gamma_installed_exes(monkeypatch):
    def dummy_walk(_):
        """Fake os.walk()"""
        yield "/some/dir", "", ["S1_burstloc", "FakeProg"]

    def dummy_access(path, flag):
        """Fake os.access()"""
        return True

    monkeypatch.setattr(os, "walk", dummy_walk)
    monkeypatch.setattr(os, "access", dummy_access)

    pkgs = ["ISP"]
    exes = py_gamma_ga.find_gamma_installed_exes(FAKE_INSTALL_DIR, pkgs)
    assert exes, "Result: {}".format(exes)
    assert "S1_burstloc" in exes, str(exes)


@pytest.fixture
def pg():
    # simulates 'import py_gamma as pg'
    iface = py_gamma_ga.GammaInterface(FAKE_INSTALL_DIR)
    iface._gamma_exes = {
        "S1_burstloc": "/fake/gamma/dir/ISP/bin/S1_burstloc",
        "fake_gamma": "/fake/gamma/dir/ISP/bin/fake_gamma",
    }
    iface.__file__ = "{}/py_gamma.py".format(FAKE_INSTALL_DIR)
    return iface


def test_getattr_function_lookup(pg):
    assert pg.S1_burstloc  # test it exists without calling


def test_getattr_function_not_exist(pg):
    with pytest.raises(AttributeError):
        assert pg.FakeMethod


def test_dunder_file(pg):
    # ensure the default hack __file__ is set
    assert pg.__file__ == FAKE_INSTALL_DIR + "/py_gamma.py"


FakeCompletedProcess = namedtuple(
    "FakeCompletedProcess", ["returncode", "stdout", "stderr",]
)


def fake_subprocess_run(cmd_list, *args, **kwargs):
    return FakeCompletedProcess(0, "Line 1\nLine 2\nLine 3\n", "")


def fake_subprocess_run2(cmd_list, *args, **kwargs):
    return FakeCompletedProcess(0, "Line 1\nLine 2\nLine 3\n", None)


def fake_subprocess_run_error(cmd_list, *args, **kwargs):
    return FakeCompletedProcess(255, "Line 1\n", "ERROR: it broke!")


def test_function_call_args_only(pg, monkeypatch):
    monkeypatch.setattr(py_gamma_ga.subprocess, "run", fake_subprocess_run)

    minfo = mock.Mock()
    monkeypatch.setattr(py_gamma_ga._LOG, "info", minfo)

    path = "fake_annotation_args_only.xml"
    assert minfo.called is False
    stat = pg.S1_burstloc(path)
    assert stat == 0
    assert minfo.called


def test_function_call_args_kwargs(pg, monkeypatch):
    for p in (fake_subprocess_run, fake_subprocess_run2):
        monkeypatch.setattr(py_gamma_ga.subprocess, "run", fake_subprocess_run)

        cout = []
        cerr = []
        path = "fake_annotation_arg_kwargs.xml"
        stat = pg.S1_burstloc(
            path, cout=cout, cerr=cerr, stdout_flag=False, stderr_flag=False
        )
        assert stat == 0
        assert cout
        assert cerr in ([], [""])


def test_function_call_args_kwargs_error(pg, monkeypatch):
    monkeypatch.setattr(py_gamma_ga.subprocess, "run", fake_subprocess_run_error)

    cout = []
    cerr = []
    path = "fake_annotation_arg_kwargs_error.xml"
    stat = pg.S1_burstloc(
        path, cout=cout, cerr=cerr, stdout_flag=False, stderr_flag=False
    )
    assert stat != 0
    assert cout
    assert cerr not in ([], [""])
