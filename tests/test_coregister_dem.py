import tempfile
import shutil
from pathlib import Path
from unittest import mock
import pytest
from PIL import Image

from tests.py_gamma_test_proxy import PyGammaTestProxy

import insar.coregister_dem
from insar.coregister_dem import CoregisterDem, CoregisterDemException
from insar.project import ProcConfig, IfgFileNames, DEMFileNames


def get_test_context():
    temp_dir = tempfile.TemporaryDirectory()
    data_dir = Path(temp_dir.name) / '20151127'

    pgp = PyGammaTestProxy(exception_type=CoregisterDemException)
    pgmock = mock.Mock(spec=PyGammaTestProxy, wraps=pgp)

    # Make offset_fit return parseable stdout as required for coregister_slc to function
    def offset_fit_se(*args, **kwargs):
        result = pgp.offset_fit(*args, **kwargs)
        OFF_par = args[2]
        shutil.copyfile(data_dir / 'offset_fit.start', OFF_par)
        return result[0], 'final model fit std. dev. (samples) range:   0.3699  azimuth:   0.1943', ''

    # raspwr needs to create a dummy bmp
    def raspwr_se(*args, **kwargs):
        rasf = args[9]
        slave_gamma0_eqa = data_dir / rasf
        Image.new('RGB', size=(50, 50), color=(155, 0, 0)).save(slave_gamma0_eqa)
        return pgp.raspwr(*args, **kwargs)

    def SLC_copy_se(*args, **kwargs):
        result = pgp.SLC_copy(*args, **kwargs)
        SLC_in, SLC_par_in, SLC_out, SLC_par_out = args[:4]
        shutil.copyfile(SLC_in, SLC_out)
        shutil.copyfile(SLC_par_in, SLC_par_out)
        return result

    def multi_look_se(*args, **kwargs):
        result = pgp.multi_look(*args, **kwargs)
        MLI_in_par = args[1]
        MLI_out_par = args[3]
        shutil.copyfile(MLI_in_par, MLI_out_par)
        return result

    def gc_map1_se(*args, **kwargs):
        result = pgp.gc_map1(*args, **kwargs)
        DEM_par, DEM, DEM_seg_par, DEM_seg = args[2:6]
        shutil.copyfile(DEM_par, DEM_seg_par)
        Path(DEM_seg).touch()
        return result

    def rashgt_se(*args, **kwargs):
        rasf = args[12]
        Image.new('RGB', size=(50, 50), color=(155, 0, 0)).save(rasf)
        return pgp.rashgt(*args, **kwargs)

    pgmock.raspwr.side_effect = raspwr_se
    pgmock.raspwr.return_value = 0, '', ''

    pgmock.offset_fit.side_effect = offset_fit_se
    pgmock.offset_fit.return_value = 0, 'final model fit std. dev. (samples) range:   0.3699  azimuth:   0.1943', ''

    pgmock.SLC_copy.side_effect = SLC_copy_se
    pgmock.SLC_copy.return_value = 0, '', ''

    pgmock.multi_look.side_effect = multi_look_se
    pgmock.multi_look.return_value = 0, '', ''

    pgmock.gc_map1.side_effect = gc_map1_se
    pgmock.gc_map1.return_value = 0, '', ''

    pgmock.rashgt.side_effect = rashgt_se
    pgmock.rashgt.return_value = 0, '', ''

    # Copy test data
    shutil.copytree(Path(__file__).parent.absolute() / 'data' / '20151127', data_dir)

    # Note: The filenames below aren't necessarily representative of a valid scene at the moment...
    # this isn't inherently a problem, as the unit tests don't test for file naming conventions of
    # input data (input data is outside the control of our code / not something we can test).
    data = {
        'rlks': 8,
        'alks': 8,
        'dem': data_dir / '20180127_VV_blah.dem',
        'slc': data_dir / '20151127_VV.slc',
        'dem_par': data_dir / '20180127_VV_8rlks_eqa.dem.par',
        'slc_par': data_dir / '20151127_VV.slc.par',
        'dem_patch_window': 1024,
        'dem_rpos': None,
        'dem_azpos': None,
        'dem_offset': (0, 0),
        'dem_offset_measure': (32, 32),
        'dem_window': (256, 256),
        'dem_snr': 0.15,
        'dem_rad_max': 4,
        'dem_ovr': 1,
    }

    # Create dummy data inputs (config/par/etc files don't need to be touched, as we provide real test files for those)
    data['slc'].touch()
    data['dem'].touch()

    return pgp, pgmock, data, temp_dir


def fake_cmd_runner(cmds, cwd):
    shutil.copyfile(cmds[1], cmds[3])


def test_valid_data(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        out_dir = Path(temp_path)
        slc_outdir = out_dir / '20151127'
        dem_outdir = out_dir / '20151127' / 'dem'

        coreg = CoregisterDem(
            *data.values(),
            dem_outdir,
            slc_outdir
        )

        dem_outdir.mkdir(parents=True, exist_ok=True)
        slc_outdir.mkdir(parents=True, exist_ok=True)

        assert(str(coreg.dem_outdir) == str(dem_outdir))

        coreg.main()

        assert(pgp.error_count == 0)

        dem_filenames = coreg.dem_filenames(dem_prefix=f"{coreg.slc.stem}_{coreg.rlks}rlks", outdir=coreg.dem_outdir)
        for name, path in dem_filenames.items():
            if path.suffix == '.dem':
                assert(Path(path).exists())


def test_missing_par_files_cause_errors(monkeypatch):
    par_file_patterns = [
        '*.slc',
        '*.dem',
        '*.slc.par',
    ]

    for pattern in par_file_patterns:
        pgp, pgmock, data, temp_dir = get_test_context()
        monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
        monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

        with temp_dir as temp_path:
            out_dir = Path(temp_path)
            slc_outdir = out_dir / '20151127'
            dem_outdir = out_dir / '20151127' / 'dem'

            # Remove matched files
            for matched_file in slc_outdir.glob(pattern):
                matched_file.unlink()

            coreg = CoregisterDem(
                *data.values(),
                dem_outdir,
                slc_outdir
            )

            dem_outdir.mkdir(parents=True, exist_ok=True)
            slc_outdir.mkdir(parents=True, exist_ok=True)

            with pytest.raises(CoregisterDemException):
                coreg.main()

            # Simply assert that removal of the files cause errors (when test_valid_data asserts 0 errors otherwise)
            assert(pgp.error_count != 0)

def test_copy_slc(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        out_dir = Path(temp_path)
        slc_outdir = out_dir / '20151127'
        dem_outdir = out_dir / '20151127' / 'dem'

        coreg = CoregisterDem(
            *data.values(),
            dem_outdir,
            slc_outdir
        )

        dem_outdir.mkdir(parents=True, exist_ok=True)
        slc_outdir.mkdir(parents=True, exist_ok=True)

        coreg.copy_slc(False)

        assert(Path(coreg.r_dem_master_mli).exists())
        assert(Path(coreg.r_dem_master_mli_par).exists())
        assert(not Path(coreg.r_dem_master_mli_bmp).exists())

        coreg.copy_slc(True)

        assert(Path(coreg.r_dem_master_mli).exists())
        assert(Path(coreg.r_dem_master_mli_par).exists())
        assert(Path(coreg.r_dem_master_mli_bmp).exists())


def test_gen_dem_rdc(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        out_dir = Path(temp_path)
        slc_outdir = out_dir / '20151127'
        dem_outdir = out_dir / '20151127' / 'dem'

        coreg = CoregisterDem(
            *data.values(),
            dem_outdir,
            slc_outdir
        )

        dem_outdir.mkdir(parents=True, exist_ok=True)
        slc_outdir.mkdir(parents=True, exist_ok=True)

        coreg.copy_slc()

        coreg.gen_dem_rdc(False)

        assert(Path(coreg.dem_pix_gam).exists())
        assert(not Path(coreg.ext_image_flt).exists())
        assert(not Path(coreg.ext_image_init_sar).exists())

        # FIXME: This branch seems to not be implemented fully/correctly (nothing ever sets ext_image)
        # coreg.gen_dem_rdc(True)

        # assert(Path(coreg.dem_pix_gam).exists())
        # assert(Path(coreg.ext_image_flt).exists())
        # assert(Path(coreg.ext_image_init_sar).exists())


def test_create_diff_par(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        outdir = Path(temp_path) / '20151127'
        outdir.mkdir(parents=True, exist_ok=True)

        coreg = CoregisterDem(
            *data.values(),
            outdir,
            outdir
        )

        coreg.copy_slc()
        coreg.gen_dem_rdc()

        # create_diff_par runs an external command to generate the diff, we create it explicitly...
        # which defeats the purpose of the test right now - but when it's migrated to pg.create_diff_par
        # we can remove this hack.  At the very least this is a smoke test for CoregisterDemcreate_diff_par
        monkeypatch.setattr(insar.coregister_dem, 'run_command', lambda cmds, cwd: Path(coreg.dem_diff).touch())

        coreg.create_diff_par()

        assert(Path(coreg.dem_diff).exists())


def test_offset_calc(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        out_dir = Path(temp_path)
        slc_outdir = out_dir / '20151127'
        dem_outdir = out_dir / '20151127' / 'dem'

        coreg = CoregisterDem(
            *data.values(),
            dem_outdir,
            slc_outdir
        )

        dem_outdir.mkdir(parents=True, exist_ok=True)
        slc_outdir.mkdir(parents=True, exist_ok=True)

        # Create dummy inputs that would have been created in normal workflow before this test call
        coreg.dem_loc_inc.touch()

        coreg.copy_slc()
        coreg.gen_dem_rdc()
        coreg.create_diff_par()

        coreg.offset_calc()

        assert(Path(coreg.dem_lt_fine).exists())
        assert(Path(coreg.dem_master_gamma0).exists())
        assert(Path(coreg.dem_master_gamma0_bmp).exists())
        assert(Path(coreg.seamask).exists())


def test_geocode(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        outdir = Path(temp_path) / '20151127'
        outdir.mkdir(parents=True, exist_ok=True)

        coreg = CoregisterDem(
            *data.values(),
            outdir,
            outdir
        )

        # Create dummy inputs that would have been created in normal workflow before this test call
        coreg.copy_slc()
        coreg.gen_dem_rdc()
        coreg.create_diff_par()
        coreg.offset_calc()

        coreg.geocode()

        assert(Path(coreg.rdc_dem).exists())
        assert(Path((coreg.dem_outdir / coreg.rdc_dem).with_suffix(".png")).exists())
        assert(Path(coreg.dem_rdc_sim_sar).exists())
        assert(Path(coreg.dem_rdc_inc).exists())
        assert(Path(coreg.dem_master_gamma0_eqa).exists())
        assert(Path(coreg.dem_master_gamma0_eqa_bmp).exists())
        assert(Path(coreg.dem_master_gamma0_eqa_bmp.with_suffix(".png")).exists())
        assert(Path(coreg.dem_master_gamma0_eqa_geo).exists())
        assert(Path(coreg.dem_master_sigma0_eqa).exists())
        assert(Path(coreg.dem_master_sigma0_eqa_geo).exists())

        assert(Path(coreg.dem_master_gamma0_eqa_bmp.with_suffix(".kml")).exists())

        # And with external image
        Path(coreg.ext_image_flt).touch();

        coreg.geocode(True)

        assert(Path(coreg.ext_image_sar).exists())


def test_look_vector(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        outdir = Path(temp_path) / '20151127'

        outdir.mkdir(parents=True, exist_ok=True)

        coreg = CoregisterDem(
            *data.values(),
            outdir,
            outdir
        )

        # Create dummy inputs that would have been created in normal workflow before this test call
        coreg.eqa_dem.touch()

        coreg.look_vector()

        assert(Path(coreg.dem_lv_theta).exists())
        assert(Path(coreg.dem_lv_phi).exists())
        assert(Path(coreg.dem_lv_phi_geo).exists())


def test_small_settings_get_fixed_up(monkeypatch):
    pgp, pgmock, data, temp_dir = get_test_context()
    monkeypatch.setattr(insar.coregister_dem, 'pg', pgmock)
    monkeypatch.setattr(insar.coregister_dem, 'run_command', fake_cmd_runner)

    with temp_dir as temp_path:
        outdir = Path(temp_path) / '20151127'

        outdir.mkdir(parents=True, exist_ok=True)

        # Make smaller than acceptable values
        data['dem_window'] = (8, 8)
        data['dem_patch_window'] = 64

        coreg = CoregisterDem(
            *data.values(),
            outdir,
            outdir
        )

        assert(coreg.dem_window[0] > 8)
        assert(coreg.dem_window[1] > 8)
        assert(coreg.dem_patch_window > 64)


# TODO: Test more specific corner cases (what are they?)
