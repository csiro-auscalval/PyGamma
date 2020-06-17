# TODO:
# map func call names to gamma EXEs
# map func args to subprocess call

import os
import unittest
from unittest import mock
from pprint import pprint
from collections import Sequence

import pytest
from insar import py_gamma_ga

import pudb


FAKE_INSTALL_DIR = "/fake/gamma/dir"


def test_find_gamma_installed_packages(monkeypatch):
    monkeypatch.setattr(os, "listdir", lambda _: [".", "..", "ISP", "MSP"])

    pkgs = py_gamma_ga.find_gamma_installed_packages(FAKE_INSTALL_DIR)
    assert isinstance(pkgs, Sequence)
    assert "ISP" in pkgs


def test_find_gamma_installed_exes(monkeypatch):
    def dummy_walk(_):
        """Fake os.walk()"""
        yield ("/some/dir", "", ["S1_burstloc", "FakeProg"])

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
    iface = py_gamma_ga.AltGamma(FAKE_INSTALL_DIR)
    iface._gamma_exes = {
        "S1_burstloc": "/path/ISP/bin/S1_burstloc",
        "fake_gamma": "/path/ISP/bin/fake_gamma",
    }
    return iface


def test_getattr_function_lookup(pg):
    assert pg.S1_burstloc  # test it exists without calling


def test_getattr_function_not_exist(pg):
    with pytest.raises(AttributeError):
        pg.FakeMethod
