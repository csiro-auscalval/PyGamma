import pytest
import tempfile
import shutil
import os
import re
from zipfile import ZipFile
from datetime import datetime, timedelta
from osgeo import gdal
from osgeo import osr
from PIL import Image
import pandas as pd
from pathlib import Path
from unittest import mock
import numpy as np
import logging.config
import structlog
import pkg_resources
from insar.logs import COMMON_PROCESSORS

from tests.py_gamma_test_proxy import PyGammaTestProxy

from insar.constant import SCENE_DATE_FMT
from insar.project import ProcConfig
from insar.py_gamma_ga import GammaInterface
from insar.sensors import get_data_swath_info

import insar.process_rsat2_slc
import insar.coregister_dem
import insar.coregister_secondary

TEST_DATA_BASE = Path(__file__).parent.absolute() / "data"

TEST_DEM_DIFF_S1 = TEST_DATA_BASE / "test_dem_diff_s1.par"
TEST_DEM_DIFF_RS2 = TEST_DATA_BASE / "test_dem_diff_rs2.par"

S1_TEST_STACK_ID = "T133D_F20S"
S1_TEST_DATA_DATES = [
    "20190918",
    "20190930",
]

S1_TEST_DATA_IDS = [
    "S1A_IW_SLC__1SDV_20190918T200909_20190918T200936_029080_034CEE_C1F9",
    "S1A_IW_SLC__1SDV_20190918T200934_20190918T201001_029080_034CEE_270E",
    "S1A_IW_SLC__1SDV_20190930T200910_20190930T200937_029255_0352F4_A544",
    "S1A_IW_SLC__1SDV_20190930T200935_20190930T201002_029255_0352F4_7CBB",
]

RS2_TEST_DATA_DATES = [
    "20170430",
    "20170617",
]

RS2_TEST_DATA_IDS = [
    "RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_HH_SLC",
    "RS2_OK127568_PK1123206_DK1078375_F0W2_20170617_084251_HH_SLC"
]

@pytest.fixture(scope="session")
def proc_config():
    with open(TEST_DATA_BASE / '20151127' / 'gamma.proc', 'r') as fileobj:
        return ProcConfig.from_file(fileobj)

@pytest.fixture
def temp_out_dir():
    """Simply returns a temporary directory that lives as long as the rest"""
    dir = tempfile.TemporaryDirectory()

    with dir as dir_path:
        yield Path(dir_path)

@pytest.fixture(scope="session")
def test_data_dir():
    dir = tempfile.TemporaryDirectory()

    with dir as dir_path:
        yield Path(dir_path)

@pytest.fixture(scope="session")
def rs2_proc(test_data_dir):
    # Load test .proc text
    src_proc_path = TEST_DATA_BASE / "test_rs2.proc"
    with (src_proc_path).open("r") as procfile:
        procfile_txt = procfile.read()

    # Replace NCI style paths w/ test data dir
    procfile_txt = procfile_txt.replace("/g/data", str(test_data_dir))

    # Set DEM path
    dem_path = TEST_DATA_BASE / "test_dem_10km.tif"
    procfile_txt = re.sub("PRIMARY_DEM_IMAGE.*", "PRIMARY_DEM_IMAGE="+str(dem_path), procfile_txt)

    test_procfile_path = test_data_dir / "test_rs2.proc"
    with test_procfile_path.open("w") as procfile:
        procfile.write(procfile_txt)

    return test_procfile_path


@pytest.fixture
def rs2_test_zips():
    return [TEST_DATA_BASE / f"{id}.zip" for id in RS2_TEST_DATA_IDS]


@pytest.fixture(scope="session")
def rs2_test_data(test_data_dir):
    # Extract test data
    for id in RS2_TEST_DATA_IDS:
        with ZipFile(TEST_DATA_BASE / f"{id}.zip", 'r') as zip:
            zip.extractall(test_data_dir)

    return [test_data_dir / i for i in RS2_TEST_DATA_IDS]

@pytest.fixture
def rs2_slc(pgp, pgmock, rs2_test_data):
    from insar.process_rsat2_slc import process_rsat2_slc

    out_path = rs2_test_data[0].parent / "test_output.slc"

    process_rsat2_slc(rs2_test_data[0], "HH", out_path)
    pgp.reset_proxy()

    return out_path

@pytest.fixture(scope="session")
def s1_proc(test_data_dir):
    # Load test .proc text
    src_proc_path = TEST_DATA_BASE / f"{S1_TEST_STACK_ID}_S1A.proc"
    with (src_proc_path).open("r") as procfile:
        procfile_txt = procfile.read()

    # Replace NCI style paths w/ test data dir
    procfile_txt = procfile_txt.replace("/g/data", str(test_data_dir))

    # Set DEM path
    dem_path = TEST_DATA_BASE / "test_dem_10km.tif"
    procfile_txt = re.sub("PRIMARY_DEM_IMAGE.*", "PRIMARY_DEM_IMAGE="+str(dem_path), procfile_txt)

    test_procfile_path = test_data_dir / src_proc_path.name
    with test_procfile_path.open("w") as procfile:
        procfile.write(procfile_txt)

    with test_procfile_path.open('r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    # Create empty orbit files
    for name in ["s1_orbits", "poeorb_path", "resorb_path", "s1_path"]:
        (Path(getattr(proc_config, name)) / "S1A").mkdir(parents=True, exist_ok=True)

    for src_date in S1_TEST_DATA_DATES:
        # Create a fake orbit file as well (stack setup typically does this)
        # as the S1 SLC processing seems to assume this will exist here too
        src_day = datetime.strptime(src_date, SCENE_DATE_FMT)
        day_prior = (src_day - timedelta(days=1)).strftime(SCENE_DATE_FMT)
        day_after = (src_day + timedelta(days=1)).strftime(SCENE_DATE_FMT)

        fake_orbit_name = f"S1A_OPER_AUX_POEORB_OPOD_{src_date}T120745_V{day_prior}T225942_{day_after}T005942.EOF"

        poeorb = Path(proc_config.poeorb_path) / "S1A" / fake_orbit_name
        poeorb.touch()

    return test_procfile_path

@pytest.fixture(scope="session")
def s1_test_data_zips():
    return [TEST_DATA_BASE / f"{i}.zip" for i in S1_TEST_DATA_IDS]

@pytest.fixture(scope="session")
def s1_test_data(test_data_dir: Path, s1_test_data_zips):
    safe_dirs = []

    # Extract test data
    for src_zip in s1_test_data_zips:
        src_date = None

        for d in S1_TEST_DATA_DATES:
            if d in src_zip.name:
                src_date = d
                break

        assert(src_date)
        test_data_date_dir = test_data_dir / src_date
        test_data_date_dir.mkdir(exist_ok=True, parents=True)

        with ZipFile(src_zip, "r") as zip:
            zip.extractall(test_data_date_dir)

        safe_dirs.append(test_data_date_dir / f"{src_zip.stem}.SAFE")

        # Create a fake orbit file as well (stack setup typically does this)
        # as the S1 SLC processing seems to assume this will exist here too
        src_day = datetime.strptime(src_date, SCENE_DATE_FMT)
        day_prior = (src_day - timedelta(days=1)).strftime(SCENE_DATE_FMT)
        day_after = (src_day + timedelta(days=1)).strftime(SCENE_DATE_FMT)

        fake_orbit_name = f"S1A_OPER_AUX_POEORB_OPOD_{src_date}T120745_V{day_prior}T225942_{day_after}T005942.EOF"
        (safe_dirs[-1] / fake_orbit_name).touch()

    return safe_dirs

@pytest.fixture
def s1_test_data_csv(pgp, pgmock, test_data_dir, s1_test_data_zips):
    slc_inputs_df = pd.DataFrame()

    for data_path in s1_test_data_zips:
        for swath_data in get_data_swath_info(data_path):
            slc_inputs_df = slc_inputs_df.append(swath_data, ignore_index=True)

    result_path = test_data_dir / f"burst_data_{S1_TEST_STACK_ID}.csv"
    slc_inputs_df.to_csv(result_path)
    return result_path

@pytest.fixture
def pgp():
    return PyGammaTestProxy(exception_type=RuntimeError)

def copy_tab_entries(src_tab_lines, dst_tab_lines):
    for src_line, dst_line in zip(src_tab_lines, dst_tab_lines):
        src_slc, src_par, src_tops_par = src_line.split()
        dst_slc, dst_par, dst_tops_par = dst_line.split()
        shutil.copyfile(src_slc, dst_slc)
        shutil.copyfile(src_par, dst_par)
        shutil.copyfile(src_tops_par, dst_tops_par)

@pytest.fixture
def pgmock(monkeypatch, pgp):
    pgmock = mock.Mock(spec=PyGammaTestProxy, wraps=pgp)
    pgmock.ParFile.side_effect = pgp.ParFile

    def par_RSAT2_SLC_mock(*args, **kwargs):
        result = pgp.par_RSAT2_SLC(*args, **kwargs)

        src_path, _, _, _, out_par, _ = args[:6]

        # Substitute well-known .par files for well-known data
        # so unit tests have real data to work with
        prod_id = Path(src_path).parent.stem
        if prod_id in RS2_TEST_DATA_IDS:
            test_slc_par = TEST_DATA_BASE / (prod_id + ".slc.par")
            shutil.copyfile(test_slc_par, out_par)

        return result

    pgmock.par_RSAT2_SLC.side_effect = par_RSAT2_SLC_mock

    def par_S1_SLC_mock(*args, **kwargs):
        result = pgp.par_S1_SLC(*args, **kwargs)

        xml_path, _, _, _, out_par, _, out_tops_par = args[:7]

        # Substitute well-known .par files for well-known data
        # so unit tests have real data to work with...
        #
        # Note: Unlike RS2, this is not-exact... S1 has subswaths,
        # and our test file is for an IW1, but we're using it as the
        # source for IW1+IW2+IW3... in reality this would cause incorrect
        # data outputs, but since our GAMMA mock doesn't do anything real
        # this works out fine for our testing purposes...
        for date in S1_TEST_DATA_DATES:
            if f"_{date}T" in str(xml_path):
                test_slc_par = TEST_DATA_BASE / f"{S1_TEST_STACK_ID}_{date}_VV.slc.par"
                test_tops_slc_par = TEST_DATA_BASE / f"{S1_TEST_STACK_ID}_{date}_VV.slc.TOPS_par"
                shutil.copyfile(test_slc_par, out_par)
                shutil.copyfile(test_tops_slc_par, out_tops_par)
                break

        return result

    pgmock.par_S1_SLC.side_effect = par_S1_SLC_mock

    def dem_import_mock(*args, **kwargs):
        result = pgp.dem_import(*args, **kwargs)

        # Produce a real .par file for our test_dem_10km.tif
        dst_dem_par = args[2]
        shutil.copyfile(TEST_DATA_BASE / "test_dem_10km.par", dst_dem_par)

        return result

    pgmock.dem_import.side_effect = dem_import_mock

    def gc_map1_mock(*args, **kwargs):
        result = pgp.gc_map1(*args, **kwargs)

        # Produce a real .par file for our test_dem_10km.tif
        # Note: This gives the original .par file still, not coregistered/re-projected
        # - since the unit tests don't really process data, this is fine as the
        # - only thing that matters is that the .par files has valid-looking attributes
        src_dem_par = args[2]
        dst_dem_par = args[4]

        shutil.copyfile(src_dem_par, dst_dem_par)

        return result

    pgmock.gc_map1.side_effect = gc_map1_mock

    def create_diff_par_mock(*args, **kwargs):
        first_par_path = args[0]
        second_par_path = args[1]
        diff_par_path = args[2]

        assert(Path(first_par_path).exists())
        assert(second_par_path is None or Path(second_par_path).exists())

        if "_HH_" in str(first_par_path):
            shutil.copyfile(TEST_DEM_DIFF_RS2, diff_par_path)
        else:
            shutil.copyfile(TEST_DEM_DIFF_S1, diff_par_path)

    # rasterisation functions should produce valid images (with fake/blank pixel data)
    # - this is required for our GDAL/rasterio related logic.
    #
    # Note: pixel contents or image resolution usually don't matter in our higher level
    # logic, so we use a tiny 32x32 image to keep IO down. Exceptional cases do write
    # resolution-appropriate images (eg: data2geotiff).
    def save_fake_img(path: Path, width: int = 32, height: int = 32):
        if path.suffix == ".tif" or path.suffix == ".tiff":
            gtiff_file = gdal.GetDriverByName("GTiff").Create(
                str(path),
                width, height, 1,
                gdal.GDT_Byte,
                options=["COMPRESS=PACKBITS"]
            )

            # Add some fake georeferencing (eastern australia) to our fake image
            srs = osr.SpatialReference()
            srs.ImportFromEPSG(4326)
            projection = srs.ExportToWkt()

            tl = gdal.GCP(138.7354168, -18.1726391, 0, 0, 0)
            br = gdal.GCP(141.7201391, -21.0256947, 0, width-1, height-1)

            gtiff_file.SetProjection(projection)
            gtiff_file.SetGeoTransform([
                tl.GCPX,
                (br.GCPX - tl.GCPX) / width,
                0.0,
                tl.GCPY,
                0.0,
                (br.GCPY - tl.GCPY) / height
            ])
            gtiff_file.GetRasterBand(1).WriteArray(np.zeros((height, width), dtype=np.uint8))
            gtiff_file.GetRasterBand(1).SetNoDataValue(0)
            gtiff_file.FlushCache()
            gtiff_file = None
        else:
            Image.new("L", (width, height)).save(path)

    def raspwr_mock(*args, **kwargs):
        result = pgp.raspwr(*args, **kwargs)
        out_file = Path(args[9])
        save_fake_img(out_file)
        return result

    def rashgt_mock(*args, **kwargs):
        result = pgp.rashgt(*args, **kwargs)
        out_file = Path(args[12])
        save_fake_img(out_file)
        return result

    def rascc_mock(*args, **kwargs):
        result = pgp.rascc(*args, **kwargs)
        out_file = Path(args[13])
        save_fake_img(out_file)
        return result

    def ras2ras_mock(*args, **kwargs):
        result = pgp.ras2ras(*args, **kwargs)
        out_file = Path(args[1])
        save_fake_img(out_file)
        return result

    def rasrmg_mock(*args, **kwargs):
        result = pgp.rasrmg(*args, **kwargs)
        out_file = Path(args[13])
        save_fake_img(out_file)
        return result

    def rasSLC_mock(*args, **kwargs):
        result = pgp.rasSLC(*args, **kwargs)
        out_file = Path(args[11])
        save_fake_img(out_file)
        return result

    def data2geotiff_mock(*args, **kwargs):
        result = pgp.data2geotiff(*args, **kwargs)
        par_file = pgp.ParFile(args[0])
        width = par_file.get_value("width", dtype=int, index=0)
        height = par_file.get_value("nlines", dtype=int, index=0)
        out_file = Path(args[3])
        save_fake_img(out_file, width, height)
        return result

    def data2tiff_mock(*args, **kwargs):
        result = pgp.data2tiff(*args, **kwargs)
        out_file = Path(args[3])
        save_fake_img(out_file)
        return result

    pgmock.raspwr.side_effect = raspwr_mock
    pgmock.rashgt.side_effect = rashgt_mock
    pgmock.rascc.side_effect = rascc_mock
    pgmock.ras2ras.side_effect = ras2ras_mock
    pgmock.rasrmg.side_effect = rasrmg_mock
    pgmock.rasSLC.side_effect = rasSLC_mock
    pgmock.data2geotiff.side_effect = data2geotiff_mock
    pgmock.data2tiff.side_effect = data2tiff_mock

    # Produce a fake pixel coordinate (coord doesn't matter as we're not truly processing data / GAMMA is mocked)
    pgmock.coord_to_sarpix.return_value = (
        0,
        [
            "SLC/MLI range, azimuth pixel (int):         7340        17060",
        ],
        [],
    )

    # Coreg tests need some stdout data from offset_fit to work...
    # - this fake data should meet accuracy requirements / result in just
    # - a single refinement iteration as a result (which is all we need for testing).
    offset_fit_stdout = [
        "final model fit std. dev. (samples) range:   0.3699  azimuth:   0.1943",
        "final range offset poly. coeff.:             -0.00408   5.88056e-07   3.95634e-08  -1.75528e-11",
        "final azimuth offset poly. coeff.:             -0.00408   5.88056e-07   3.95634e-08  -1.75528e-11",
    ]

    offset_fit_doff = [
        "fake header",
        "",
        "range_offset_polynomial:         0.00587   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00",
        "azimuth_offset_polynomial:      -0.00227   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00",
        "slc1_starting_azimuth_line:               0",
        "interferogram_azimuth_lines:           9268",
        "interferogram_width:                   8551",
    ]

    def offset_fit_mock(*args, **kwargs):
        result = pgp.offset_fit(*args, **kwargs)

        doff = Path(args[2])
        with doff.open("w") as file:
            file.write("\n".join(offset_fit_doff))

        return result[0], offset_fit_stdout, []

    pgmock.offset_fit.side_effect = offset_fit_mock

    # Note: This is a hack to get data processing working... but it's incorrect (gives a single static subswath no matter the input)
    # - we'd probably be better recording this for our test data scenes we use for processing instead, and returning those pre-recorded
    # - outputs specific to each .xml in the test S1A_IW_SLC .SAFE's
    pgmock.S1_burstloc.return_value = (
        0,
        [
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   1    133 IW1 VH 72577.10938100 201.19792562  0.00000000     -20.05066032 141.33827992     -20.23086577 141.29334202     -20.04635710 140.49153530     -19.86643746 140.53751416",
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   2    133 IW1 VH 72579.86793700 201.36680827  0.16888265     -20.21664279 141.29689276     -20.39658715 141.25191976     -20.21181426 140.44914628     -20.03215673 140.49516859",
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   3    133 IW1 VH 72582.62649400 201.53568026  0.16887198     -20.38261265 141.25541628     -20.56279048 141.21028353     -20.37775129 140.40653133     -20.19786210 140.45272467",
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   4    133 IW1 VH 72585.38505000 201.70454140  0.16886114     -20.54716454 141.20767637     -20.72720258 141.16246734     -20.54246531 140.36031242     -20.36271633 140.40658711",
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   5    133 IW1 VH 72588.14360700 201.87339177  0.16885037     -20.71310677 141.16601094     -20.89325434 141.12067116     -20.70824908 140.31752379     -20.52839219 140.36393985",
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   6    133 IW1 VH 72590.90216300 202.04223120  0.16883944     -20.87903594 141.12425376     -21.05916928 141.07881344     -20.87389490 140.27466521     -20.69405368 140.32119173",
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   7    133 IW1 VH 72593.65866400 202.21093395  0.16870275     -21.04482842 141.08243522     -21.22482380 141.03692484     -21.03927935 140.23176809     -20.85957735 140.27837387",
            "Burst: s1a-iw1-slc-vh-20190918t200935-20190918t201000-029080-034cee-001.xml   8    133 IW1 VH 72596.41516500 202.37962575  0.16869180     -21.21073132 141.04049214     -21.39071226 140.99487952     -21.20489598 140.18870351     -21.02520990 140.23542155",
        ],
        []
    )

    def SLC_cat_ScanSAR_se(*args, **kwargs):
        result = pgp.SLC_cat_ScanSAR(*args, **kwargs)

        in_tab1, in_tab2, out_tab = args[:3]
        in_tab1 = Path(in_tab1)
        in_tab2 = Path(in_tab2)
        out_tab = Path(out_tab)

        assert(in_tab1.exists())
        assert(in_tab2.exists())
        assert(out_tab.exists())

        in_tab1 = in_tab1.read_text().splitlines()
        in_tab2 = in_tab2.read_text().splitlines()
        out_tab = out_tab.read_text().splitlines()

        for in_tab in [in_tab1, in_tab2]:
            for line in in_tab:
                slc, par, tops_par = line.split()
                assert(Path(slc).exists())
                assert(Path(par).exists())
                assert(Path(tops_par).exists())

        copy_tab_entries(in_tab1, out_tab)

        return result

    pgmock.SLC_cat_ScanSAR.side_effect = SLC_cat_ScanSAR_se

    def SLC_copy_mock(*args, **kwargs):
        result = pgp.SLC_copy(*args, **kwargs)

        in_slc, in_par, out_slc, out_par = args[:4]
        shutil.copyfile(in_slc, out_slc)
        shutil.copyfile(in_par, out_par)

        return result

    pgmock.SLC_copy.side_effect = SLC_copy_mock

    # Add a more sophisticated SLC_copy_ScanSAR implementation than py_gamma_test_proxy.py
    # which actually parses the tab files, checks inputs and touches outputs
    def SLC_copy_ScanSAR_se(*args, **kwargs):
        result = pgp.SLC_copy_ScanSAR(*args, **kwargs)

        slc1_tab, slc2_tab, burst_tab = args[:3]
        assert(Path(slc1_tab).exists())
        assert(Path(slc2_tab).exists())
        assert(Path(burst_tab).exists())

        with open(slc1_tab, 'r') as file:
            slc1_tab = file.read().splitlines()

        with open(slc2_tab, 'r') as file:
            slc2_tab = file.read().splitlines()

        assert(len(slc1_tab) == len(slc2_tab))

        for line in slc1_tab:
            slc, par, tops_par = line.split()
            assert(Path(slc).exists())
            assert(Path(par).exists())
            assert(Path(tops_par).exists())

        copy_tab_entries(slc1_tab, slc2_tab)

        return result

    pgmock.SLC_copy_ScanSAR.side_effect = SLC_copy_ScanSAR_se

    def SLC_mosaic_S1_TOPS_mock(*args, **kwargs):
        result = pgp.SLC_mosaic_S1_TOPS(*args, **kwargs)

        _, slc_path, slc_par_path = args[:3]
        slc_path = Path(slc_path)

        # Substitute well-known .par files for well-known data
        # so unit tests have real data to work with
        test_slc_par = TEST_DATA_BASE / f"{S1_TEST_STACK_ID}_{slc_path.stem}.slc.par"
        if test_slc_par.exists():
            shutil.copyfile(test_slc_par, slc_par_path)

        return result

    pgmock.SLC_mosaic_S1_TOPS.side_effect = SLC_mosaic_S1_TOPS_mock

    def SLC_interp_lt_mock(*args, **kwargs):
        result = pgp.SLC_interp_lt(*args, **kwargs)

        slc_2nd_path, slc_1st_par_path, slc_2nd_par_path = args[:3]
        mli_1st_par_path, mli_2nd_par_path = args[3:5]
        slc_out, slc_par_out = args[7:9]

        shutil.copyfile(mli_2nd_par_path, slc_par_out)

        return result

    pgmock.SLC_interp_lt.side_effect = SLC_interp_lt_mock

    def SLC_interp_lt_ScanSAR_mock(*args, **kwargs):
        result = pgp.SLC_interp_lt_ScanSAR(*args, **kwargs)

        SLC2_tab, SLC2_par = args[:2]
        SLC2R_tab, _, SLC2R_par = args[8:11]

        SLC2_tab = Path(SLC2_tab)
        SLC2R_tab = Path(SLC2R_tab)

        if SLC2R_tab.exists():
            SLC2_tab = SLC2_tab.read_text().splitlines()
            SLC2R_tab = SLC2R_tab.read_text().splitlines()

            copy_tab_entries(SLC2_tab, SLC2R_tab)
        else:
            shutil.copyfile(SLC2_tab, SLC2R_tab)

        shutil.copyfile(SLC2_par, SLC2R_par)

        return result

    pgmock.SLC_interp_lt_ScanSAR.side_effect = SLC_interp_lt_ScanSAR_mock

    def multi_look_mock(*args, **kwargs):
        result = pgp.multi_look(*args, **kwargs)

        src_par = args[1]
        dst_par = args[3]
        shutil.copyfile(src_par, dst_par)

        return result

    pgmock.multi_look.side_effect = multi_look_mock

    def image_stat_mock(*args, **kwargs):
        result = pgp.image_stat(*args, **kwargs)

        dst_stat_file = Path(args[6])
        with dst_stat_file.open("w") as file:
            # Produce some fake image stats for a very flat image
            # - this implicitly passes all our coreg iterations,
            # - which is simply trying to minimise the difference
            # - between two images, thus smaller = less difference
            file.write("mean: 0.1\n")
            file.write("stdev: 0.01\n")
            file.write("fraction_valid: 0.98\n")

        return result

    pgmock.image_stat.side_effect = image_stat_mock

    # Record pre-mock state (so it can be restored after)
    orig_install = os.environ.get("GAMMA_INSTALL_DIR")
    orig_proxy = GammaInterface._gamma_proxy
    before_pg = insar.process_rsat2_slc.pg
    before_diff_par = insar.coregister_dem.create_diff_par

    # Use PyGamma mock interface in all processing modules
    os.environ["GAMMA_INSTALL_DIR"] = "PyGammaTestProxy-1234"
    GammaInterface.set_proxy(pgmock)

    monkeypatch.setattr(insar.process_rsat2_slc, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_secondary, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'create_diff_par', create_diff_par_mock)
    monkeypatch.setattr(insar.coregister_secondary, 'create_diff_par', create_diff_par_mock)

    try:
        yield pgmock
    finally:
        # Restore pre-mock state
        if orig_install:
            os.environ["GAMMA_INSTALL_DIR"] = orig_install
        else:
            del os.environ["GAMMA_INSTALL_DIR"]

        GammaInterface.set_proxy(orig_proxy)
        insar.process_rsat2_slc.pg = before_pg
        insar.coregister_secondary.pg = before_pg
        insar.coregister_dem.create_diff_par = before_diff_par
        insar.coregister_secondary.create_diff_par = before_diff_par


@pytest.fixture
def logging_ctx():
    """
    This fixture creates a temporary logging context for our code which expects
    to be able to use our structlog configuration.  This is useful for tests
    which use code that uses these logs implicitly (eg: S1 metadata code...)
    """
    temp_dir = tempfile.TemporaryDirectory()

    with temp_dir as temp_path:
        os.chdir(temp_path)

        # Configure logging from built-in script logging config file
        logging_conf = pkg_resources.resource_filename("insar", "logging.cfg")
        logging.config.fileConfig(logging_conf)

        insar_log_path = Path(temp_path) / "insar-log.jsonl"
        with insar_log_path.open("a") as fobj:
            structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj), processors=COMMON_PROCESSORS)
            yield insar_log_path

