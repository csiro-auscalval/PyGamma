#!/usr/bin/env python

"""Tests for `insar` package."""
from pathlib import Path
import datetime

import unittest
import pytest

from ..insar.meta_data import s1_slc
from ..insar.generate_slc_inputs import query_slc_inputs, slc_inputs

__DATA__ = Path(__file__).parent.joinpath("data")
__AOI__ = Path(__file__).parent.joinpath("data", "T134D_F22S.shp")
__DB__ = Path(__file__).parent.joinpath("data", "test_slcdb.db")


@pytest.fixture()
def slc_data():
    s1_zips = [fp for fp in __DATA__.glob("*.zip")]
    return s1_zips


@pytest.fixture()
def sqlite_database(tmp_path, slc_data):
    db_name = tmp_path.joinpath("test_slcdb.db")
    with s1_slc.Archive(db_name) as archive:
        for s1_path in slc_data:
            meta = s1_slc.SlcMetadata(s1_path).get_metadata()
            archive.archive_scene(meta)
    return db_name


def test_query_slc_inputs(sqlite_database):
    """Test slc query inputs"""
    _db = sqlite_database
    query_args = (
        _db.as_posix(),
        __AOI__.as_posix(),
        datetime.datetime(2016, 1, 1),
        datetime.datetime(2016, 1, 31),
        'D',
        134,
        ["VV", "VH"]
    )
    results_test = query_slc_inputs(*query_args)
    new_args = list(query_args)
    new_args[0] = __DB__.as_posix()
    results_validate = query_slc_inputs(*tuple(new_args))

    key1 = datetime.date(2016, 1, 1)
    key2 = 'IW1'
    key3 = 'burst_number'

    for pol in ["VV", "VH"]:
        burst_sub_test = results_test[pol][key1][key2]
        burst_sub_val = results_validate[pol][key1][key2]
        burst_numbers_test = []
        burst_numbers_val = []
        acq_datetime_test = []
        acq_datetime_val = []
        for _id1, _id2 in zip(burst_sub_test.keys(), burst_sub_val.keys()):
            if "missing_master_bursts" != _id1:
                burst_numbers_test.append(burst_sub_test[_id1]["burst_number"])
                acq_datetime_test.append(burst_sub_test[_id1]["acquisition_datetime"])
            if "missing_master_bursts" != _id2:
                burst_numbers_val.append(burst_sub_val[_id2]["burst_number"])
                acq_datetime_val.append(burst_sub_val[_id2]["acquisition_datetime"])

        assert set(sum(burst_numbers_test, [])) == set(sum(burst_numbers_val, []))
        assert set(acq_datetime_test) == set(acq_datetime_val)




