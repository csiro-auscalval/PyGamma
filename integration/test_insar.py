#!/usr/bin/env python

"""
Full integration test for insar workflow.

This integration test is written to test whole insar workflow
till slave-master coregistration step. The integration test
was run on nci gadi compute node using 8 cpus, 64GB memory and
jobfs of 400GB. Approximately 2 hours is required to run all the
tests.
"""

from pathlib import Path
import datetime
import time
import shutil

import zipfile
import unittest
import pytest
import pandas as pd

from insar.meta_data import (
    s1_slc,
)  ## this script uses Archive, SlcMetadata and S1DataDownload

from insar.generate_slc_inputs import query_slc_inputs, slc_inputs
from insar.make_gamma_dem import create_gamma_dem
from insar.process_s1_slc import SlcProcess
from insar.calc_multilook_values import multilook, calculate_mean_look_values
from insar.calc_baselines_new import BaselineProcess
from insar.coregister_dem import CoregisterDem
from insar.coregister_slc import CoregisterSlc


__DATA__ = Path(__file__).parent.joinpath("data")
__AOI__ = Path(__file__).parent.joinpath("data", "T134D_F22S.shp")
__DB__ = Path(__file__).parent.joinpath("data", "test_slcdb.db")
__DEM__ = Path("/g/data/dg9/MASTER_DEM/GAMMA_DEM_SRTM_1as_mosaic.img")


def param_parser(par_file):
    """method to parse parameter files"""
    par_file = Path(par_file).as_posix()

    with open(par_file, "r") as fid:
        tmp_dict = dict()
        lines = fid.readlines()
        for line in lines:
            vals = line.strip().split(":")
            try:
                tmp_dict[vals[0]] = [v for v in vals[1].split()]
            except IndexError:
                pass
        return tmp_dict


@pytest.fixture()
def slc_data():
    s1_zips = [fp for fp in __DATA__.glob("*.zip")]
    return s1_zips


@pytest.fixture()
def sqlite_database(
    tmp_path, slc_data,
):
    db_name = tmp_path.joinpath("test_slcdb.db")
    with s1_slc.Archive(db_name) as archive:
        for s1_path in slc_data:
            meta = s1_slc.SlcMetadata(s1_path).get_metadata()
            archive.archive_scene(meta)
    return db_name


@pytest.fixture()
def query_results(sqlite_database):
    _db = sqlite_database
    query_args = (
        _db.as_posix(),
        __AOI__.as_posix(),
        datetime.datetime(2016, 1, 1),
        datetime.datetime(2016, 1, 31),
        "D",
        134,
        ["VV", "VH"],
    )
    results_test = query_slc_inputs(*query_args)
    new_args = list(query_args)
    new_args[0] = __DB__.as_posix()
    results_validate = query_slc_inputs(*tuple(new_args))

    return results_test, results_validate


def test_query_slc_inputs(query_results):
    """Test slc query inputs"""
    results_test, results_validate = query_results
    key1 = datetime.date(2016, 1, 1)
    key2 = "IW1"
    key3 = "burst_number"

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


def test_slc_inputs(query_results):
    """Test slc inputs"""
    results_test, results_validate = query_results
    for pol in ["VV", "VH"]:
        slc_test = slc_inputs(results_test[pol])
        slc_val = slc_inputs(results_validate[pol])
        assert set(slc_test.acquistion_datetime.values) == set(
            slc_val.acquistion_datetime.values
        )
        for swath in ["IW1", "IW2", "IW3"]:
            slc_test_swath = slc_test[slc_test.swath == swath]
            slc_val_swath = slc_val[slc_val.swath == swath]
            assert set(sum(slc_test_swath.burst_number.values, [])) == set(
                sum(slc_val_swath.burst_number.values, [])
            )


def test_s1datadownload(
    tmp_path, query_results,
):
    """Test SLC download"""
    results_test, results_validate = query_results
    slc_inputs_df = pd.concat([slc_inputs(results_test[pol]) for pol in ["VV", "VH"]])
    download_list = slc_inputs_df.url.unique()
    raw_dir = tmp_path.joinpath("RAW")
    for fp in download_list:
        fp = Path(fp)
        if (
            fp.stem
            != "S1A_IW_SLC__1SDV_20160101T214934_20160101T215000_009306_00D719_38CC"
        ):
            continue

        kwargs = {
            "slc_scene": fp,
            "polarization": ["VV", "VH"],
            "s1_orbits_poeorb_path": __DATA__,
            "s1_orbits_resorb_path": __DATA__,
        }
        dobj = s1_slc.S1DataDownload(**kwargs)
        dobj.slc_download(raw_dir)
        files = [
            "S1A_OPER_AUX_POEORB_OPOD_20160121T121801_V20151231T225943_20160102T005943.EOF",
            "measurement",
            "annotation",
            "manifest.safe",
            "s1a-iw1-slc-vh-20160101t214935-20160101t215000-009306-00d719-001.tiff",
            "s1a-iw1-slc-vv-20160101t214935-20160101t215000-009306-00d719-004.tiff",
            "s1a-iw2-slc-vh-20160101t214934-20160101t214959-009306-00d719-002.tiff",
            "s1a-iw2-slc-vv-20160101t214934-20160101t214959-009306-00d719-005.tiff",
            "s1a-iw3-slc-vv-20160101t214934-20160101t215000-009306-00d719-006.tiff",
            "s1a-iw3-slc-vh-20160101t214934-20160101t215000-009306-00d719-003.tiff",
            "s1a-iw1-slc-vh-20160101t214935-20160101t215000-009306-00d719-001.xml",
            "calibration",
            "s1a-iw1-slc-vv-20160101t214935-20160101t215000-009306-00d719-004.xml",
            "s1a-iw3-slc-vv-20160101t214934-20160101t215000-009306-00d719-006.xml",
            "s1a-iw3-slc-vh-20160101t214934-20160101t215000-009306-00d719-003.xml",
            "s1a-iw2-slc-vh-20160101t214934-20160101t214959-009306-00d719-002.xml",
            "s1a-iw2-slc-vv-20160101t214934-20160101t214959-009306-00d719-005.xml",
            "calibration-s1a-iw2-slc-vv-20160101t214934-20160101t214959-009306-00d719-005.xml",
            "noise-s1a-iw2-slc-vv-20160101t214934-20160101t214959-009306-00d719-005.xml",
            "noise-s1a-iw3-slc-vh-20160101t214934-20160101t215000-009306-00d719-003.xml",
            "calibration-s1a-iw2-slc-vh-20160101t214934-20160101t214959-009306-00d719-002.xml",
            "calibration-s1a-iw1-slc-vh-20160101t214935-20160101t215000-009306-00d719-001.xml",
            "noise-s1a-iw3-slc-vv-20160101t214934-20160101t215000-009306-00d719-006.xml",
            "calibration-s1a-iw3-slc-vv-20160101t214934-20160101t215000-009306-00d719-006.xml",
            "calibration-s1a-iw1-slc-vv-20160101t214935-20160101t215000-009306-00d719-004.xml",
            "noise-s1a-iw1-slc-vh-20160101t214935-20160101t215000-009306-00d719-001.xml",
            "calibration-s1a-iw3-slc-vh-20160101t214934-20160101t215000-009306-00d719-003.xml",
            "noise-s1a-iw2-slc-vh-20160101t214934-20160101t214959-009306-00d719-002.xml",
            "noise-s1a-iw1-slc-vv-20160101t214935-20160101t215000-009306-00d719-004.xml",
        ]

        test_files = [
            item.name
            for item in raw_dir.joinpath(fp.stem).with_suffix(".SAFE").glob("**/*")
        ]
        assert set(files) == set(test_files)


def test_creategammadem(tmp_path):
    """Test create gamma dem"""
    outdir = tmp_path.joinpath("gamma")
    outdir.mkdir(parents=True, exist_ok=True)

    track_frame = "T134D_F20S"
    kwargs = {
        "gamma_dem_dir": outdir,
        "dem_img": __DEM__.as_posix(),
        "track_frame": track_frame,
        "shapefile": __AOI__.as_posix(),
    }

    create_gamma_dem(**kwargs)

    assert outdir.joinpath(f"{track_frame}.dem").exists()

    with open(outdir.joinpath(f"{track_frame}.dem.par").as_posix(), "r") as fid:
        test_pars = [
            item.rstrip().split(":")[1].strip() for item in fid.readlines() if ":" in item
        ]
        with open(__DATA__.joinpath(f"{track_frame}.dem.par").as_posix(), "r") as fid1:
            val_pars = [
                item.strip().split(":")[1].strip()
                for item in fid1.readlines()
                if ":" in item
            ]
        assert set(test_pars) == set(val_pars)


def test_slcprocess(
    tmp_path, query_results,
):
    """Test slc process"""
    results_test, _ = query_results
    scene_date = "20160101"
    raw_data_dir = tmp_path.joinpath("RAW", scene_date)
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    slc_inputs_df = pd.concat([slc_inputs(results_test[pol]) for pol in ["VV", "VH"]])
    burst_data = tmp_path.joinpath("burst_data.csv")
    slc_inputs_df.to_csv(burst_data.as_posix())
    download_list = slc_inputs_df.url.unique()
    orbit_file = __DATA__.joinpath(
        "S1A",
        "S1A_OPER_AUX_POEORB_OPOD_20160121T121801_V20151231T225943_20160102T005943.EOF",
    )
    for fp in download_list:
        with zipfile.ZipFile(fp, "r") as zref:
            zref.extractall(raw_data_dir)
    for save_dir in raw_data_dir.iterdir():
        shutil.copy(orbit_file, save_dir)

    slc_dir = tmp_path.joinpath("SLC")
    slc_dir.mkdir(parents=True, exist_ok=True)

    sjob = SlcProcess(
        raw_data_dir.parent.as_posix(),
        slc_dir.as_posix(),
        "VV",
        scene_date,
        burst_data.as_posix(),
    )
    sjob.main()

    slc_tab = sjob.slc_tab_names(scene_date)
    assert slc_dir.joinpath(scene_date, slc_tab.slc).exists()

    test_dict = param_parser(slc_dir.joinpath(scene_date, slc_tab.par))
    val_dict = param_parser(__DATA__.joinpath(slc_tab.par))

    # TODO assertion might fail since statements expect same values.
    # TODO Change to compare within accurracy of certain signiticant figures.
    for key, val in test_dict.items():
        assert val[0] == val_dict[key][0]


def test_calculatemeanlookvalues():
    """Test calculate mean look values"""
    par_files = [__DATA__.joinpath("20160101_VV.slc.par") for _ in range(11)]
    rlks, alks, *_ = calculate_mean_look_values(par_files, 1)

    assert rlks == 4
    assert alks == 1


def test_multilook(tmp_path):
    """Test multilook"""
    slc_par = __DATA__.joinpath("SLC", "20160101", "20160101_VV.slc.par")
    slc = slc_par.with_suffix("")
    multilook(slc=slc, slc_par=slc_par, rlks=4, alks=1, outdir=tmp_path)

    assert tmp_path.joinpath("20160101_VV_4rlks.mli").exists()

    test_dict = param_parser(tmp_path.joinpath("20160101_VV_4rlks.mli.par"))
    val_dict = param_parser(slc_par.parent.joinpath("20160101_VV_4rlks.mli.par"))

    # TODO assertion might fail since statements expect same values.
    # TODO Change to compare within accurracy of certain signiticant figures.
    for key, val in test_dict.items():
        assert val[0] == val_dict[key][0]


def test_baselineprocess(tmp_path):
    """Test baseline process"""
    par_files = [
        tmp_path.joinpath(
            f"{(datetime.datetime(2016,1,1)+datetime.timedelta(days=d*12)).strftime('%Y%m%d')}_VV.slc.par"
        )
        for d in range(11)
    ]

    for dst in par_files:
        shutil.copyfile(__DATA__.joinpath("20160101_VV.slc.par"), dst)

    bjob = BaselineProcess(
        par_files, ["VV"], master_scene=datetime.date(2016, 3, 1), outdir=tmp_path
    )
    bjob.sbas_list()

    with open(tmp_path.joinpath("ifg_list").as_posix(), "r") as fid:
        test_cons = [item.rstrip() for item in fid.readlines()]
        with open(__DATA__.joinpath("ifg_list").as_posix(), "r") as fid1:
            val_cons = [item.rstrip() for item in fid1.readlines()]
        assert set(test_cons) == set(val_cons)


def test_coregisterdemmaster(tmp_path):
    """Test coregister dem and master scene"""
    outdir = tmp_path.joinpath("gamma")
    outdir.mkdir(parents=True, exist_ok=True)

    track_frame = "T134D_F20S"
    kwargs = {
        "gamma_dem_dir": outdir,
        "dem_img": __DEM__.as_posix(),
        "track_frame": track_frame,
        "shapefile": __AOI__.as_posix(),
    }

    create_gamma_dem(**kwargs)

    gamma_dem = outdir.joinpath(f"{track_frame}.dem")
    gamma_dem_par = outdir.joinpath(f"{track_frame}.dem.par")

    slc_dir = tmp_path.joinpath("SLC", "20160101")
    slc_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy(__DATA__.joinpath("SLC", "20160101", "20160101_VV.slc.par"), slc_dir)
    shutil.copy(__DATA__.joinpath("SLC", "20160101", "20160101_VV.slc"), slc_dir)

    slc_par = slc_dir.joinpath("20160101_VV.slc.par")
    slc = slc_par.with_suffix("")

    dem_dir = tmp_path.joinpath("DEM")
    dem_dir.mkdir(parents=True, exist_ok=True)

    coreg = CoregisterDem(
        rlks=4,
        alks=1,
        dem=gamma_dem,
        slc=slc,
        dem_par=gamma_dem_par,
        slc_par=slc_par,
        dem_outdir=dem_dir,
    )
    coreg.main()

    assert dem_dir.joinpath("20160101_VV_4rlks_ellip_pix_sigma0").exists()
    assert dem_dir.joinpath("20160101_VV_4rlks_rdc_pix_gamma0").exists()
    assert dem_dir.joinpath("20160101_VV_4rlks_rdc.dem").exists()
    assert dem_dir.joinpath("20160101_VV_4rlks_eqa_to_rdc.lt").exists()
    assert slc_dir.joinpath("20160101_VV_4rlks_eqa.sigma0.tif").exists()
    assert slc_dir.joinpath("20160101_VV_4rlks_eqa.gamma0.tif").exists()

    test_dict = param_parser(dem_dir.joinpath("20160101_VV_4rlks_eqa.dem.par"))
    val_dict = param_parser(__DATA__.joinpath("DEM", "20160101_VV_4rlks_eqa.dem.par"))

    for key, val in test_dict.items():
        assert val[0] == val_dict[key][0]


def test_coregisterslaves(tmp_path):
    """Test coregister master and slaves slc"""
    outdir = tmp_path.joinpath("SLC", "20160101")
    outdir.mkdir(parents=True, exist_ok=True)

    slc_dir = __DATA__.joinpath("SLC", "20160101")
    dem_dir = __DATA__.joinpath("DEM")
    cjob = CoregisterSlc(
        slc_master=slc_dir.joinpath("20160101_VV.slc"),
        slc_slave=slc_dir.joinpath("20160101_VH.slc"),
        slave_mli=slc_dir.joinpath("20160101_VH_4rlks.mli"),
        range_looks=4,
        azimuth_looks=1,
        ellip_pix_sigma0=dem_dir.joinpath("20160101_VV_4rlks_ellip_pix_sigma0"),
        dem_pix_gamma0=dem_dir.joinpath("20160101_VV_4rlks_rdc_pix_gamma0"),
        r_dem_master_mli=slc_dir.joinpath("r20160101_VV_4rlks.mli"),
        rdc_dem=dem_dir.joinpath("20160101_VV_4rlks_rdc.dem"),
        eqa_dem_par=dem_dir.joinpath("20160101_VV_4rlks_eqa.dem.par"),
        dem_lt_fine=dem_dir.joinpath("20160101_VV_4rlks_eqa_to_rdc.lt"),
        outdir=outdir,
    )

    cjob.main()

    assert outdir.joinpath("20160101_VH_4rlks_eqa.sigma0.tif").exists()
    assert outdir.joinpath("20160101_VH_4rlks_eqa.gamma0.tif").exists()

    # TODO assertion might fail since statements expect same values.
    # TODO Change to compare within accurracy of certain signiticant figures.
    test_dict = param_parser(outdir.joinpath("r20160101_VH.slc.par"))
    val_dict = param_parser(slc_dir.joinpath("r20160101_VH.slc.par"))

    for key, val in test_dict.items():
        assert val[0] == val_dict[key][0]
