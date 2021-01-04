import tempfile
import shutil
from pathlib import Path
from unittest import mock
import pytest
from PIL import Image

from tests.py_gamma_test_proxy import PyGammaTestProxy

import insar.coregister_slc
from insar.coregister_slc import CoregisterSlc, CoregisterSlcException
from insar.project import ProcConfig, IfgFileNames, DEMFileNames


def get_test_context():
    temp_dir = tempfile.TemporaryDirectory()
    data_dir = Path(temp_dir.name) / '20151127'

    pgp = PyGammaTestProxy(exception_type=CoregisterSlcException)
    pgmock = mock.Mock(spec=PyGammaTestProxy, wraps=pgp)

    # Make offset_fit return parseable stdout as required for coregister_slc to function
    def offset_fit_se(*args, **kwargs):
        result = pgp.offset_fit(*args, **kwargs)
        OFF_par = args[2]
        shutil.copyfile(data_dir / 'offset_fit.start', OFF_par)
        return result[0], ['final model fit std. dev. (samples) range:   0.3699  azimuth:   0.1943'], []

    # raspwr needs to create a dummy bmp
    def raspwr_se(*args, **kwargs):
        rasf = args[9]
        slave_gamma0_eqa = data_dir / rasf
        Image.new('RGB', size=(50, 50), color=(155, 0, 0)).save(slave_gamma0_eqa)
        return pgp.raspwr(*args, **kwargs)

    def mcf_se(*args, **kwargs):
        # mcf's unw output parameter needs to have content for image_stat calls to go through
        unw = Path(args[3])
        unw.touch()
        with unw.open('w') as file:
            file.write("TEST CONTENT\n")
        
        result = pgp.mcf(*args, **kwargs)
        return result

    def image_stat_se(*args, **kwargs):
        result = pgp.image_stat(*args, **kwargs)
        report = args[6]

        with open(report, 'w') as file:
            file.write('mean:             0.42\n')
            file.write('stdev:            0.03\n')
            file.write('fraction_valid:   0.8\n')

        return result

    def SLC_copy_se(*args, **kwargs):
        result = pgp.SLC_copy(*args, **kwargs)
        SLC_in, SLC_par_in, SLC_out, SLC_par_out = args[:4]
        shutil.copyfile(SLC_in, SLC_out)
        shutil.copyfile(SLC_par_in, SLC_par_out)
        return result

    pgmock.raspwr.side_effect = raspwr_se
    pgmock.raspwr.return_value = 0, [], []

    pgmock.offset_fit.side_effect = offset_fit_se
    pgmock.offset_fit.return_value = (0, ['final model fit std. dev. (samples) range:   0.3699  azimuth:   0.1943'], [])

    pgmock.mcf.side_effect = mcf_se
    pgmock.mcf.return_value = 0, [], []

    pgmock.image_stat.side_effect = image_stat_se
    pgmock.image_stat.return_value = 0, [], []

    pgmock.SLC_copy.side_effect = SLC_copy_se
    pgmock.SLC_copy.return_value = 0, [], []

    # Copy test data
    shutil.copytree(Path(__file__).parent.absolute() / 'data' / '20151127', data_dir)

    with open(Path(__file__).parent.absolute() / 'data' / '20151127' / 'gamma.proc', 'r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    # Note: The filenames below aren't necessarily representative of a valid scene at the moment...
    # this isn't inherently a problem, as the unit tests don't test for file naming conventions of
    # input data (input data is outside the control of our code / not something we can test).
    data = {
        'proc': proc_config,
        'list_idx': '-',
        'slc_master': data_dir / '20151127_VV.slc',
        'slc_slave': data_dir / '20151127_VV.slc',  # if slave/master are the same... everything should still run i assume? just useless outputs?
        'slave_mli': data_dir / '20151127_VV_8rlks.mli',
        'range_looks': 1,
        'azimuth_looks': 1,
        'ellip_pix_sigma0': data_dir / '20151127_VV_8rlks_ellip_pix.sigma0',
        'dem_pix_gamma0': data_dir / '20151127_VV_8rlks_rdc_pix.gamma0',
        'r_dem_master_mli': data_dir / 'r20151127_VV_8rlks.mli',
        'rdc_dem': data_dir / '20151127_VV_8rlks_rdc.dem',
        'eqa_dem_par': data_dir / '20180127_VV_8rlks_eqa.dem.par',
        'dem_lt_fine': data_dir / '20151127_VV_8rlks_eqa_to_rdc.lt',
    }

    # Create dummy data inputs (config/par/etc files don't need to be touched, as we provide real test files for those)
    touch_exts = ['.slc', '.mli', '.dem', '.gamma0', '.sigma0', '.lt']

    for k,v in data.items():
        if any([str(v).endswith(ext) for ext in touch_exts]):
            Path(v).touch()

    for p in data_dir.iterdir():
        if p.name.endswith('.par'):
            Path(p.parent / p.stem).touch()

    return pgp, pgmock, data, temp_dir


def test_valid_data(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_slc, 'pg', pgmock)

    with temp_dir as temp_path:
        coreg = CoregisterSlc(
            *data.values(),
            Path(temp_path)
        )

        assert(str(coreg.out_dir) == temp_path)

        coreg.main()

        # Assert no failure status for any gamma call
        assert(pgp.error_count == 0)

        # Assert outputs exist
        assert(coreg.r_slave_slc.exists())

        slave_gamma0 = coreg.out_dir / f"{coreg.slave_mli.stem}.gamma0"
        slave_gamma0_eqa = coreg.out_dir / f"{coreg.slave_mli.stem}_eqa.gamma0"
        assert(slave_gamma0.exists())
        assert(slave_gamma0_eqa.exists())

        # Assert quick-look images exist
        slave_png = coreg.out_dir / f"{slave_gamma0_eqa.name}.png"
        assert(slave_png.exists())


def test_set_tab_files(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_slc, 'pg', pgmock)

    with temp_dir as temp_path:
        coreg = CoregisterSlc(
            *data.values(),
            Path(temp_path)
        )

        coreg.set_tab_files()
        assert(coreg.slave_slc_tab.exists())
        assert(coreg.r_slave_slc_tab.exists())
        assert(coreg.master_slc_tab.exists())

        custom_dir = 'test123abc'
        (Path(temp_path) / custom_dir).mkdir()
        coreg.set_tab_files(Path(temp_path) / custom_dir)
        assert(coreg.slave_slc_tab.exists() and coreg.slave_slc_tab.parent.name == custom_dir)
        assert(coreg.r_slave_slc_tab.exists() and coreg.r_slave_slc_tab.parent.name == custom_dir)
        assert(coreg.master_slc_tab.exists() and coreg.master_slc_tab.parent.name == custom_dir)


def test_get_lookup(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_slc, 'pg', pgmock)

    with temp_dir as temp_path:
        coreg = CoregisterSlc(
            *data.values(),
            Path(temp_path)
        )

        # Create dummy inputs that are expected
        coreg.r_dem_master_mli_par.touch()
        coreg.rdc_dem.touch()
        coreg.slave_mli_par.touch()

        # Run function
        coreg.get_lookup()

        # Ensure the output is produced
        assert(coreg.slave_lt.exists())


def test_resample_full(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_slc, 'pg', pgmock)

    with temp_dir as temp_path:
        coreg = CoregisterSlc(
            *data.values(),
            Path(temp_path)
        )

        # Pre-work before resample (coarse coreg is enough)
        coreg.set_tab_files()
        coreg.get_lookup()
        coreg.reduce_offset()
        coreg.coarse_registration()

        coreg.resample_full()

        assert(Path(coreg.r_slave_slc_tab).exists())
        assert(Path(coreg.r_slave_slc).exists())
        assert(Path(coreg.r_slave_slc_par).exists())


def test_multi_look(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_slc, 'pg', pgmock)

    with temp_dir as temp_path:
        coreg = CoregisterSlc(
            *data.values(),
            Path(temp_path)
        )

        # Pre-work before multi_look (coarse coreg is enough)
        coreg.set_tab_files()
        coreg.get_lookup()
        coreg.reduce_offset()
        coreg.coarse_registration()
        coreg.resample_full()
        
        coreg.multi_look()

        assert(Path(coreg.r_slave_mli).exists())
        assert(Path(coreg.r_slave_mli_par).exists())


def test_generate_normalised_backscatter(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_slc, 'pg', pgmock)

    with temp_dir as temp_path:
        coreg = CoregisterSlc(
            *data.values(),
            Path(temp_path)
        )

        # Pre-work before backscatter (coarse coreg is enough)
        coreg.set_tab_files()
        coreg.get_lookup()
        coreg.reduce_offset()
        coreg.coarse_registration()
        coreg.resample_full()
        coreg.multi_look()
        
        coreg.generate_normalised_backscatter()

        slave_gamma0 = coreg.out_dir / f"{coreg.slave_mli.stem}.gamma0"
        slave_gamma0_eqa = coreg.out_dir / f"{coreg.slave_mli.stem}_eqa.gamma0"
        slave_png = coreg.out_dir / f"{slave_gamma0_eqa.name}.png"

        assert(slave_gamma0.exists())
        assert(slave_gamma0_eqa.exists())
        assert(slave_png.exists())

        assert(slave_gamma0_eqa.with_suffix(".gamma0.tif").exists())

        assert(slave_gamma0_eqa.with_suffix(".sigma0").exists())
        assert(slave_gamma0_eqa.with_suffix(".sigma0.tif").exists())


# TODO: Test more specific corner cases (what are they?)
