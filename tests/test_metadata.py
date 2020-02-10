#!/usr/bin/env python

"""Tests for `insar` package."""
from pathlib import Path
import unittest
import pytest

from ..insar.meta_data import s1_slc


__DATA__ = Path(__file__).parent.joinpath("data")


@pytest.fixture()
def slc_data():
    s1_zips = [fp for fp in __DATA__.glob("*.zip")]
    return s1_zips


@pytest.fixture()
def sqlite_database(tmp_path, slc_data):
    db_name = tmp_path.joinpath("test_slcdb.db")
    db_name = __DATA__.joinpath("test_database.db")
    for s1_path in slc_data:
        meta = s1_slc.SlcMetadata(s1_path).get_metadata()
        print(meta)
        with s1_slc.Archive(db_name.as_posix()) as archive:
            archive.archive_scene(meta)
    return db_name


class TestSlcMetadata:

    def test_something(self, sqlite_database):
        """Test something."""
        print(sqlite_database)
