import pytest
import tempfile
import tarfile
import shutil
import os
import re
from PIL import Image
from pathlib import Path
from unittest import mock

from tests.py_gamma_test_proxy import PyGammaTestProxy

from insar.project import ProcConfig
from insar.py_gamma_ga import GammaInterface

import insar.process_rsat2_slc
import insar.coregister_dem
import insar.coregister_secondary

TEST_DATA_BASE = Path(__file__).parent.absolute() / "data"

RS2_TEST_DATA_ID = "RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_HH_SLC"
RS2_TEST_DATA_PATH = TEST_DATA_BASE / f"{RS2_TEST_DATA_ID}.tar.gz"

@pytest.fixture(scope="session")
def proc_config():
    with open(TEST_DATA_BASE / '20151127' / 'gamma.proc', 'r') as fileobj:
        return ProcConfig.from_file(fileobj)

@pytest.fixture(scope="session")
def rs2_data_dir():
    dir = tempfile.TemporaryDirectory()

    with dir as dir_path:
        yield Path(dir_path)

@pytest.fixture(scope="session")
def rs2_proc(rs2_data_dir):
    # Load test .proc text
    src_proc_path = TEST_DATA_BASE / "test_rs2.proc"
    with (src_proc_path).open("r") as procfile:
        procfile_txt = procfile.read()

    # Set DEM path
    dem_path = TEST_DATA_BASE / "test_dem_10km.tif"
    procfile_txt = re.sub("PRIMARY_DEM_IMAGE.*", "PRIMARY_DEM_IMAGE="+str(dem_path), procfile_txt)

    test_procfile_path = rs2_data_dir / "test_rs2.proc"
    with test_procfile_path.open("w") as procfile:
        procfile.write(procfile_txt)

    return test_procfile_path

@pytest.fixture
def pgp():
    return PyGammaTestProxy(exception_type=RuntimeError)

@pytest.fixture
def pgmock(monkeypatch, pgp):
    pgmock = mock.Mock(spec=PyGammaTestProxy, wraps=pgp)
    pgmock.ParFile.side_effect = pgp.ParFile

    def par_RSAT2_SLC_mock(*args, **kwargs):
        result = pgp.par_RSAT2_SLC(*args, **kwargs)

        src_path, _, _, _, out_par, _ = args[:6]

        # Substitute well-known .par files for well-known data
        # so unit tests have real data to work with
        if Path(src_path).parent.stem == RS2_TEST_DATA_ID:
            test_slc_par = TEST_DATA_BASE / (RS2_TEST_DATA_ID + ".slc.par")
            shutil.copyfile(test_slc_par, out_par)

        return result

    pgmock.par_RSAT2_SLC.side_effect = par_RSAT2_SLC_mock

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
        Path(diff_par_path).touch()

    # rasterisation functions should produce valid images (with fake/blank pixel data)
    # - this is required for our GDAL/rasterio related logic.
    #
    # Note: pixel contents or image resolution usually don't matter in our higher level
    # logic, so we use a tiny 32x32 image to keep IO down. Exceptional cases do write
    # resolution-appropriate images (eg: data2geotiff).
    fake_image = Image.new("L", (32, 32))

    def raspwr_mock(*args, **kwargs):
        result = pgp.raspwr(*args, **kwargs)
        out_file = args[9]
        fake_image.save(out_file)
        return result

    def rashgt_mock(*args, **kwargs):
        result = pgp.rashgt(*args, **kwargs)
        out_file = args[12]
        fake_image.save(out_file)
        return result

    def rascc_mock(*args, **kwargs):
        result = pgp.rascc(*args, **kwargs)
        out_file = args[13]
        fake_image.save(out_file)
        return result

    def rascc_mask_mock(*args, **kwargs):
        result = pgp.rascc_mask(*args, **kwargs)
        out_file = args[15]
        fake_image.save(out_file)
        return result

    def ras2ras_mock(*args, **kwargs):
        result = pgp.ras2ras(*args, **kwargs)
        out_file = args[1]
        fake_image.save(out_file)
        return result

    def rasrmg_mock(*args, **kwargs):
        result = pgp.rasrmg(*args, **kwargs)
        out_file = args[13]
        fake_image.save(out_file)
        return result

    def data2geotiff_mock(*args, **kwargs):
        result = pgp.data2geotiff(*args, **kwargs)
        par_file = pgp.ParFile(args[0])
        width = par_file.get_value("width", dtype=int, index=0)
        height = par_file.get_value("nlines", dtype=int, index=0)
        out_file = args[3]
        Image.new("L", (width, height)).save(out_file)
        return result

    def data2tiff_mock(*args, **kwargs):
        result = pgp.data2tiff(*args, **kwargs)
        out_file = args[3]
        fake_image.save(out_file)
        return result

    pgmock.raspwr.side_effect = raspwr_mock
    pgmock.rashgt.side_effect = rashgt_mock
    pgmock.rascc.side_effect = rascc_mock
    pgmock.rascc_mask.side_effect = rascc_mask_mock
    pgmock.ras2ras.side_effect = ras2ras_mock
    pgmock.rasrmg.side_effect = rasrmg_mock
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
    pgmock.offset_fit.return_value = (
        0,
        [
            "final model fit std. dev. (samples) range:   0.3699  azimuth:   0.1943",
            "final range offset poly. coeff.:             -0.00408   5.88056e-07   3.95634e-08  -1.75528e-11",
            "final azimuth offset poly. coeff.:             -0.00408   5.88056e-07   3.95634e-08  -1.75528e-11",
        ],
        [],
    )

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

        with open(burst_tab, 'r') as file:
            burst_tab = file.read().splitlines()

        for line in slc1_tab:
            slc, par, tops_par = line.split()
            assert(Path(slc).exists())
            assert(Path(par).exists())
            assert(Path(tops_par).exists())

        for line in slc2_tab:
            slc, par, tops_par = line.split()
            assert(Path(slc).exists())
            assert(Path(par).exists())
            assert(Path(tops_par).exists())

        for line in burst_tab:
            slc, par, tops_par = line.split()

            # TODO: Should we make a fake geotiff so it can be loaded by gdal/etc?
            Path(slc).exists().touch()
            # TBD: Should we copy from inputs so we have valid .par files?
            Path(par).exists().touch()
            Path(tops_par).exists().touch()

        return result

    pgmock.SLC_copy_ScanSAR.side_effect = SLC_copy_ScanSAR_se

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

    out_path = rs2_test_data.parent / "test_output.slc"

    process_rsat2_slc(rs2_test_data, "HH", out_path)
    pgp.reset_proxy()

    return out_path
