import io
import pathlib
import functools
from unittest import mock
from tempfile import TemporaryDirectory
from PIL import Image
import numpy as np

import insar.constant as const
from insar import process_ifg, py_gamma_ga
from insar.process_ifg import ProcessIfgException, TempFileConfig
from insar.project import ProcConfig, IfgFileNames, DEMFileNames

import structlog
import pytest

from tests.fixtures import *


# FIXME: tweak settings to ensure working dir doesn't have to be changed for INT processing (do in workflow)
# TODO: can monkeypatch be done at higher level scope to apply to multiple test funcs?

PG_RETURN_VALUE = (0, ["default-cout"], ["default-cerr"])
PG_RETURN_VALUE_FAIL = (-1, ["cout-with-error"], ["cerr-with-error"])
PG_RETURN_SARPIX_VALUE = (0, ["SLC/MLI range, azimuth pixel (int):         7340        17060"], [])

test_dir = TemporaryDirectory('test_process_ifg')


def base_orbit_se(*args, **kwargs):
    out_par = args[2]
    pathlib.Path(out_par).touch()
    return PG_RETURN_VALUE

@pytest.fixture
def pg_int_mock():
    """Create basic mock of the py_gamma module for INT processing step."""
    pg_mock = mock.NonCallableMock()
    pg_mock.create_offset.return_value = PG_RETURN_VALUE
    pg_mock.offset_pwr.return_value = PG_RETURN_VALUE
    pg_mock.offset_fit.return_value = PG_RETURN_VALUE
    pg_mock.create_diff_par.return_value = PG_RETURN_VALUE

    return pg_mock


@pytest.fixture
def pc_mock():
    """Returns basic mock to simulate a ProcConfig object."""
    with open(pathlib.Path(__file__).parent.absolute() / 'data' / '20151127' / 'gamma.proc', 'r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    pc = mock.NonCallableMock(spec=ProcConfig, wraps=proc_config)
    pc.multi_look = 2  # always 2 for Sentinel 1
    pc.ifg_coherence_threshold = 2.5  # fake value

    mock_path = functools.partial(mock.MagicMock, spec=pathlib.Path)
    pc.proj_dir = mock_path()

    return pc


@pytest.fixture
def ic_mock():
    """Returns basic mock to simulate an IfgFileNames object."""
    ic = mock.NonCallableMock(spec=IfgFileNames)

    mock_path = functools.partial(mock.MagicMock, spec=pathlib.Path)

    # Explicitly set a bunch of path objecst (as the mocked Path objects don't
    # implement / or + correctly).   Note: the unit tests are all mocked, the
    # directories don't have to have valid files or in some cases even exist...
    #
    # Despite being dummy data, we use semi-realistic paths to keep test errors
    # easier to understand.
    base_path = pathlib.Path(test_dir.name)

    ic.ifg_dir = base_path / "INT" / '20151103-20151127'
    ic.primary_dir = base_path / "SLC" / '20151103'
    ic.secondary_dir = base_path / "SLC" / '20151127'
    ic.ifg_unw_geocode_2pi_bmp = ic.ifg_dir / 'geo_unw_2pi.bmp'
    ic.ifg_unw_geocode_6pi_bmp = ic.ifg_dir / 'geo_unw_6pi.bmp'
    ic.ifg_flat_geocode_bmp = ic.ifg_dir / 'ifg_flat_geocode.bmp'
    ic.ifg_unw_geocode_2pi_png = ic.ifg_dir / "geo_unw_2pi.png"
    ic.ifg_unw_geocode_6pi_png = ic.ifg_dir / "geo_unw_6pi.png"
    ic.ifg_filt_coh_geocode_png = ic.ifg_dir / "test_filt_coh.png"
    ic.ifg_filt_geocode_png = ic.ifg_dir / "test_filt_geo_int.png"
    ic.ifg_flat_coh_geocode_png = ic.ifg_dir / "test_flat_filt_coh.png"
    ic.ifg_flat_geocode_png = ic.ifg_dir / "test_flat_geo_int.png"
    ic.ifg_base_init = ic.ifg_dir / "test_base_init.par"
    ic.ifg_base = ic.ifg_dir / "test_base.par"

    ic.ifg_bperp = mock_path()
    ic.r_primary_slc = mock_path()
    ic.r_primary_mli = mock_path()
    ic.r_secondary_slc = mock_path()
    ic.r_secondary_mli = mock_path()

    ic.ifg_flat = mock_path()
    ic.ifg_flat1 = mock_path()
    ic.ifg_flat10 = mock_path()

    ic.shapefile = pathlib.Path(__file__).parent.absolute() / 'data' / 'T147D_F28S_S1A.shp'

    return ic


@pytest.fixture
def tc_mock():
    """Returns basic mock to simulate a TempFileConfig object."""
    tc = mock.NonCallableMock(spec=TempFileConfig)
    return tc


@pytest.fixture
def remove_mock():
    """Returns basic mock to simulate remove_files()."""
    rm = mock.Mock()
    return rm


def test_run_workflow_full(
    logging_ctx, monkeypatch, pc_mock, ic_mock, dc_mock, tc_mock, remove_mock
):
    """Test workflow runs from end to end"""

    # mock out larger elements like modules/dependencies
    m_pathlib = mock.NonCallableMock()
    m_pathlib.Path.return_value.glob.return_value = ["fake-path0", "fake-path1"]
    monkeypatch.setattr(process_ifg, "pathlib", m_pathlib)

    m_shutil = mock.NonCallableMock()
    m_shutil.copy.return_value = []
    monkeypatch.setattr(process_ifg, "shutil", m_shutil)

    m_pygamma = mock.NonCallableMock()
    m_pygamma.base_perp.return_value = PG_RETURN_VALUE
    m_pygamma.coord_to_sarpix.return_value = PG_RETURN_SARPIX_VALUE
    m_pygamma.base_orbit.side_effect = base_orbit_se
    m_pygamma.base_orbit.return_value = PG_RETURN_VALUE
    monkeypatch.setattr(process_ifg, "pg", m_pygamma)

    # mock out smaller helper functions (prevent I/O etc)
    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)

    fake_width10 = 334
    fake_width_in = 77
    fake_width_out = 66
    monkeypatch.setattr(process_ifg, "get_width10", lambda _: fake_width10)
    monkeypatch.setattr(process_ifg, "get_width_in", lambda _: fake_width_in)
    monkeypatch.setattr(process_ifg, "get_width_out", lambda _: fake_width_out)
    monkeypatch.setattr(process_ifg, "convert", mock.Mock())

    # mock required individual values
    pc_mock.ifg_geotiff.lower.return_value = "yes"
    ic_mock.ifg_off.exists.return_value = False

    # finally run the workflow :-)
    process_ifg.run_workflow(
        pc_mock, ic_mock, dc_mock, tc_mock, ifg_width=fake_width_in
    )

    # check some of the funcs in each step are called
    assert m_pygamma.create_offset.called
    assert m_pygamma.base_orbit.called
    # assert m_pygamma.multi_cpx.called  - only called if refinement enabled
    assert m_pygamma.adf.called
    assert m_pygamma.rascc_mask.called
    assert m_pygamma.interp_ad.called
    assert m_pygamma.data2geotiff.called
    assert remove_mock.called


def test_run_workflow_missing_r_primary_slc(ic_mock, tc_mock, logging_ctx):
    ic_mock.r_primary_slc.exists.return_value = False

    with pytest.raises(ProcessIfgException):
        process_ifg.run_workflow(
            pc_mock, ic_mock, dc_mock, tc_mock, ifg_width=10
        )


def test_run_workflow_missing_r_primary_mli(ic_mock, tc_mock, logging_ctx):
    ic_mock.r_primary_slc.exists.return_value = True
    ic_mock.r_primary_mli.exists.return_value = False

    with pytest.raises(ProcessIfgException):
        process_ifg.run_workflow(
            pc_mock, ic_mock, dc_mock, tc_mock, ifg_width=11
        )


def test_run_workflow_missing_r_secondary_slc(ic_mock, tc_mock, logging_ctx):
    ic_mock.r_primary_slc.exists.return_value = True
    ic_mock.r_primary_mli.exists.return_value = True
    ic_mock.r_secondary_slc.exists.return_value = False

    with pytest.raises(ProcessIfgException):
        process_ifg.run_workflow(
            pc_mock, ic_mock, dc_mock, tc_mock, ifg_width=12
        )


def test_run_workflow_missing_r_secondary_mli(ic_mock, tc_mock, logging_ctx):
    ic_mock.r_primary_slc.exists.return_value = True
    ic_mock.r_primary_mli.exists.return_value = True
    ic_mock.r_secondary_slc.exists.return_value = True
    ic_mock.r_secondary_mli.exists.return_value = False

    with pytest.raises(ProcessIfgException):
        process_ifg.run_workflow(
            pc_mock, ic_mock, dc_mock, tc_mock, ifg_width=13
        )


def test_get_ifg_width():
    # content from gadi:/g/data/dg9/INSAR_ANALYSIS/CAMDEN/S1/GAMMA/T147D/SLC/20200105/r20200105_VV_8rlks.mli.par
    c = "line_header_size:                  0\nrange_samples:                  8630\nazimuth_lines:                85\n"
    config = io.StringIO(c)
    assert process_ifg.get_ifg_width(config) == 8630


def test_get_ifg_width_not_found():
    config = io.StringIO("Fake line 0\nFake line 1\nFake line 2\n")
    with pytest.raises(ProcessIfgException):
        process_ifg.get_ifg_width(config)


def test_calc_int(logging_ctx, monkeypatch, pg_int_mock, pc_mock, ic_mock):
    """Verify default path through the INT processing step."""

    # craftily substitute the 'pg' py_gamma obj for a mock:
    # 1) avoids missing import errors when testing locally
    # 2) prevents calling the real thing on Gadi and all the errors with that
    monkeypatch.setattr(process_ifg, "pg", pg_int_mock)
    ic_mock.ifg_off = mock.Mock(spec=pathlib.Path)
    ic_mock.ifg_off.exists.return_value = False  # offset not yet processed

    process_ifg.calc_int(pc_mock, ic_mock)

    assert pg_int_mock.create_offset.called
    assert pg_int_mock.offset_pwr.called
    assert pg_int_mock.offset_fit.called
    assert pg_int_mock.create_diff_par.called


def test_error_handling_decorator(monkeypatch, logging_ctx):
    m_subprocess_wrapper = mock.Mock()

    # ensure mock logger has all core error(), msg() etc logging functions
    log_mock = mock.NonCallableMock(spec=structlog.stdlib.BoundLogger)
    assert log_mock.error.called is False

    pgi = py_gamma_ga.GammaInterface(
        install_dir="./fake-install",
        gamma_exes={"create_offset": "fake-EXE-name"},
        subprocess_func=process_ifg.auto_logging_decorator(
            m_subprocess_wrapper, ProcessIfgException, log_mock
        ),
    )

    with pytest.raises(ProcessIfgException):
        pgi.create_offset(1, 2, 3, key="value")

    assert m_subprocess_wrapper.called
    assert log_mock.error.called
    has_cout = False
    has_cerr = False

    for c in log_mock.error.call_args:
        if const.COUT in c:
            has_cout = True

        if const.CERR in c:
            has_cerr = True

    assert has_cout
    assert has_cerr


@pytest.fixture
def pg_flat_mock():
    """Create basic mock of the py_gamma module for the FLAT processing step."""
    pg_mock = mock.NonCallableMock()
    pg_mock.base_orbit.return_value = PG_RETURN_VALUE
    pg_mock.phase_sim_orb.return_value = PG_RETURN_VALUE
    pg_mock.SLC_diff_intf.return_value = PG_RETURN_VALUE
    pg_mock.base_init.return_value = PG_RETURN_VALUE
    pg_mock.base_add.return_value = PG_RETURN_VALUE
    pg_mock.phase_sim.return_value = PG_RETURN_VALUE

    pg_mock.gcp_phase.return_value = PG_RETURN_VALUE
    pg_mock.sub_phase.return_value = PG_RETURN_VALUE
    pg_mock.mcf.return_value = PG_RETURN_VALUE
    pg_mock.base_ls.return_value = PG_RETURN_VALUE
    pg_mock.cc_wave.return_value = PG_RETURN_VALUE
    pg_mock.rascc_mask.return_value = PG_RETURN_VALUE
    pg_mock.multi_cpx.return_value = PG_RETURN_VALUE
    pg_mock.multi_real.return_value = PG_RETURN_VALUE
    pg_mock.extract_gcp.return_value = PG_RETURN_VALUE

    pg_mock.base_perp.return_value = PG_RETURN_VALUE
    return pg_mock


@pytest.fixture
def dc_mock():
    """Default mock for DEMFileNames config."""
    dcm = mock.NonCallableMock(spec=DEMFileNames)
    return dcm


def test_initial_flattened_ifg(
    logging_ctx, monkeypatch, pg_flat_mock, pc_mock, ic_mock, dc_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_flat_mock)

    assert pg_flat_mock.base_orbit.called is False
    assert pg_flat_mock.phase_sim_orb.called is False
    assert pg_flat_mock.SLC_diff_intf.called is False
#    assert pg_flat_mock.base_init.called is False
#    assert pg_flat_mock.base_add.called is False
#    assert pg_flat_mock.phase_sim.called is False

    process_ifg.initial_flattened_ifg(pc_mock, ic_mock, dc_mock)

    assert pg_flat_mock.base_orbit.called
    assert pg_flat_mock.phase_sim_orb.called
    assert pg_flat_mock.SLC_diff_intf.called
#    assert pg_flat_mock.SLC_diff_intf.call_count == 2
#    assert pg_flat_mock.base_init.called
#    assert pg_flat_mock.base_add.called
#    assert pg_flat_mock.phase_sim.called


def test_refined_flattened_ifg(
    logging_ctx, monkeypatch, pg_flat_mock, pc_mock, ic_mock, dc_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_flat_mock)

#    assert pg_flat_mock.base_orbit.called is False
#    assert pg_flat_mock.phase_sim_orb.called is False
    assert pg_flat_mock.base_init.called is False
    assert pg_flat_mock.base_add.called is False
    assert pg_flat_mock.phase_sim.called is False
    assert pg_flat_mock.SLC_diff_intf.called is False

    process_ifg.refined_flattened_ifg(pc_mock, ic_mock, dc_mock, ic_mock.ifg_flat0)

#    assert pg_flat_mock.base_orbit.called
#    assert pg_flat_mock.phase_sim_orb.called
#    assert pg_flat_mock.SLC_diff_intf.call_count == 2
    assert pg_flat_mock.base_init.called
    assert pg_flat_mock.base_add.called
    assert pg_flat_mock.phase_sim.called
    assert pg_flat_mock.SLC_diff_intf.called


def test_precise_flattened_ifg(
    logging_ctx, monkeypatch, pg_flat_mock, pc_mock, ic_mock, dc_mock, tc_mock
):
    # test refinement of baseline model using ground control points
    monkeypatch.setattr(process_ifg, "pg", pg_flat_mock)

    assert pg_flat_mock.multi_cpx.called is False
    assert pg_flat_mock.cc_wave.called is False
    assert pg_flat_mock.rascc_mask.called is False
    assert pg_flat_mock.mcf.called is False
    assert pg_flat_mock.multi_real.called is False
    assert pg_flat_mock.sub_phase.called is False
    assert pg_flat_mock.extract_gcp.called is False
    assert pg_flat_mock.gcp_phase.called is False
    assert pg_flat_mock.base_ls.called is False
    assert pg_flat_mock.phase_sim.called is False
    assert pg_flat_mock.SLC_diff_intf.called is False
#    assert pg_flat_mock.base_perp.called is False

    fake_width10 = 400
    m_get_width10 = mock.Mock(return_value=fake_width10)
    monkeypatch.setattr(process_ifg, "get_width10", m_get_width10)

    fake_ifg_width = 99
    process_ifg.precise_flattened_ifg(
        pc_mock, ic_mock, dc_mock, tc_mock, ic_mock.ifg_flat1, fake_ifg_width
    )

    assert pg_flat_mock.multi_cpx.called
    assert pg_flat_mock.cc_wave.call_count == 2
#    assert pg_flat_mock.cc_wave.call_count == 3
    assert pg_flat_mock.rascc_mask.call_count == 2
    assert pg_flat_mock.mcf.called
    assert pg_flat_mock.multi_real.called
    assert pg_flat_mock.sub_phase.call_count == 2
    assert pg_flat_mock.extract_gcp.called
    assert pg_flat_mock.gcp_phase.called
    assert pg_flat_mock.base_ls.called
    assert pg_flat_mock.phase_sim.called
    assert pg_flat_mock.SLC_diff_intf.called
#    assert pg_flat_mock.base_perp.call_count == 1


def test_calc_bperp_coh_filt_write_fail(
    logging_ctx, monkeypatch, pg_flat_mock, pc_mock, ic_mock, dc_mock, tc_mock
):
    monkeypatch.setattr(process_ifg, "get_width10", lambda _: 52)
    monkeypatch.setattr(process_ifg, "pg", pg_flat_mock)
    ic_mock.ifg_bperp.open.side_effect = IOError("Simulated ifg_bperp failure")

    with pytest.raises(IOError):
        fake_ifg_width = 99
        process_ifg.calc_bperp_coh_filt(
            pc_mock, ic_mock, ic_mock.ifg_flat, ic_mock.ifg_base, fake_ifg_width
        )


def _get_mock_file_and_path(fake_content):
    """
    Helper function to mock out pathlib.Path.open() and file.readlines()
    :param fake_content: Sequence of values for file.readlines() to emit
    :return: (file_mock, path_mock)
    """
    # file like object to be returned from context manager
    m_file = mock.NonCallableMock()
    m_file.readlines.return_value = fake_content

    # TRICKY: mock chain of open() calls, context manager etc to return custom file mock
    m_path = mock.MagicMock(spec=pathlib.Path)
    m_path.open.return_value.__enter__.return_value = m_file
    return m_file, m_path


def test_get_width10():
    _, m_path = _get_mock_file_and_path(
        ["a    1\n", "interferogram_width:         43\n", "b         24\n"]
    )
    width = process_ifg.get_width10(m_path)
    assert width == 43, "got {}".format(width)


def test_get_width10_not_found():
    _, m_path = _get_mock_file_and_path(["fake1    1\n", "fake2    2\n"])

    with pytest.raises(ProcessIfgException):
        process_ifg.get_width10(m_path)


@pytest.fixture
def pg_filt_mock():
    """Create basic mock of the py_gamma module for the FILT processing step."""
    pgm = mock.NonCallableMock()
    pgm.cc_wave.return_value = PG_RETURN_VALUE
    pgm.adf.return_value = PG_RETURN_VALUE
    pgm.base_perp.return_value = PG_RETURN_VALUE
    return pgm


def test_calc_bperp_coh_filt(logging_ctx, monkeypatch, pg_filt_mock, pc_mock, ic_mock):
    monkeypatch.setattr(process_ifg, "pg", pg_filt_mock)
    ic_mock.ifg_flat.exists.return_value = True

    assert pg_filt_mock.base_perp.called is False
    assert pg_filt_mock.cc_wave.called is False
    assert pg_filt_mock.adf.called is False
    process_ifg.calc_bperp_coh_filt(pc_mock, ic_mock, ic_mock.ifg_flat, ic_mock.ifg_base, ifg_width=230)
    assert pg_filt_mock.base_perp.called
    assert pg_filt_mock.cc_wave.called
    assert pg_filt_mock.adf.called


def test_calc_bperp_coh_filt_no_flat_file(logging_ctx, monkeypatch, pg_filt_mock, pc_mock, ic_mock):
    monkeypatch.setattr(process_ifg, "pg", pg_filt_mock)
    ic_mock.ifg_flat.exists.return_value = False

    with pytest.raises(ProcessIfgException):
        process_ifg.calc_bperp_coh_filt(pc_mock, ic_mock, ic_mock.ifg_flat, ic_mock.ifg_base, ifg_width=180)


@pytest.fixture
def pg_unw_mock():
    """Basic mock of the py_gamma module for the UNW processing step."""
    pgm = mock.NonCallableMock()
    pgm.rascc_mask.return_value = PG_RETURN_VALUE
    pgm.rascc_mask_thinning.return_value = PG_RETURN_VALUE
    pgm.mcf.return_value = PG_RETURN_VALUE
    pgm.interp_ad.return_value = PG_RETURN_VALUE
    pgm.unw_model.return_value = PG_RETURN_VALUE
    pgm.mask_data.return_value = PG_RETURN_VALUE
    return pgm


def test_calc_unw(logging_ctx, monkeypatch, pg_unw_mock, pc_mock, ic_mock, tc_mock):
    # NB: (m)looks will always be 2 for Sentinel-1 ARD product generation
    monkeypatch.setattr(process_ifg, "pg", pg_unw_mock)

    # ignore the thinning step as it will be tested separately
    m_thin = mock.Mock()
    monkeypatch.setattr(process_ifg, "calc_unw_thinning", m_thin)

    pc_mock.ifg_unw_mask = "no"
    fake_ifg_width = 13

    assert pg_unw_mock.rascc_mask.called is False
    assert m_thin.called is False
    assert pg_unw_mock.mask_data.called is False

    process_ifg.calc_unw(pc_mock, ic_mock, tc_mock, fake_ifg_width)

    assert pg_unw_mock.rascc_mask.called
    assert m_thin.call_count == 1
    assert pg_unw_mock.mask_data.called is False


def test_calc_unw_no_ifg_filt(logging_ctx, monkeypatch, pg_unw_mock, pc_mock, ic_mock, tc_mock):
    monkeypatch.setattr(process_ifg, "pg", pg_unw_mock)
    ic_mock.ifg_filt.exists.return_value = False

    with pytest.raises(ProcessIfgException):
        process_ifg.calc_unw(pc_mock, ic_mock, tc_mock, ifg_width=101)


def test_calc_unw_with_mask(
    logging_ctx, monkeypatch, pg_unw_mock, pc_mock, ic_mock, tc_mock, remove_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_unw_mock)
    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)
    pc_mock.ifg_unw_mask = "yes"

    assert pg_unw_mock.mask_data.called is False
    assert remove_mock.called is False

    process_ifg.calc_unw(pc_mock, ic_mock, tc_mock, ifg_width=202)

    assert pg_unw_mock.mask_data.called is True
    assert remove_mock.called is True


def test_calc_unw_mlooks_over_threshold_not_implemented(
    logging_ctx, monkeypatch, pg_unw_mock, pc_mock, ic_mock, tc_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_unw_mock)
    pc_mock.multi_look = 5

    with pytest.raises(NotImplementedError):
        process_ifg.calc_unw(pc_mock, ic_mock, tc_mock, ifg_width=15)


def test_calc_unw_thinning(logging_ctx, monkeypatch, pg_unw_mock, pc_mock, ic_mock, tc_mock):
    monkeypatch.setattr(process_ifg, "pg", pg_unw_mock)

    assert pg_unw_mock.rascc_mask_thinning.called is False
    assert pg_unw_mock.mcf.called is False
    assert pg_unw_mock.interp_ad.called is False
    assert pg_unw_mock.unw_model.called is False

    process_ifg.calc_unw_thinning(pc_mock, ic_mock, tc_mock, 17)

    assert pg_unw_mock.rascc_mask_thinning.called
    assert pg_unw_mock.mcf.called
    assert pg_unw_mock.interp_ad.called
    assert pg_unw_mock.unw_model.called


@pytest.fixture
def pg_geocode_mock():
    """Basic mock for pygamma calls in GEOCODE"""
    pgm = mock.NonCallableMock()
    pgm.geocode_back.return_value = PG_RETURN_VALUE
    pgm.mask_data.return_value = PG_RETURN_VALUE
    pgm.convert.return_value = PG_RETURN_VALUE
    pgm.kml_map.return_value = PG_RETURN_VALUE
    pgm.cpx_to_real.return_value = PG_RETURN_VALUE
    pgm.rascc.return_value = PG_RETURN_VALUE
    pgm.ras2ras.return_value = PG_RETURN_VALUE
    pgm.rasrmg.return_value = PG_RETURN_VALUE
    pgm.data2geotiff.return_value = PG_RETURN_VALUE
    return pgm


# TODO: can fixtures call other fixtures to get their setup? (e.g. mock pg inside another fixture?)
def test_geocode_unwrapped_ifg(
    logging_ctx, monkeypatch, ic_mock, dc_mock, pg_geocode_mock, tc_mock, remove_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)

    m_convert = mock.Mock()
    monkeypatch.setattr(process_ifg, "convert", m_convert)

    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)

    assert pg_geocode_mock.geocode_back.called is False
    assert pg_geocode_mock.mask_data.called is False
    assert pg_geocode_mock.rasrmg.called is False
    assert pg_geocode_mock.kml_map.called is False

    assert m_convert.called is False
    assert remove_mock.called is False

    width_in, width_out = 5, 7  # fake values
    process_ifg.geocode_unwrapped_ifg(ic_mock, dc_mock, tc_mock, width_in, width_out)

    assert pg_geocode_mock.geocode_back.called
    assert pg_geocode_mock.mask_data.called
    assert pg_geocode_mock.rasrmg.called
    assert pg_geocode_mock.kml_map.called

    assert m_convert.called
    assert remove_mock.called


def test_geocode_flattened_ifg(
    logging_ctx, monkeypatch, ic_mock, dc_mock, pg_geocode_mock, tc_mock, remove_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)

    # patch convert function for testing this part of geocode step
    m_convert = mock.Mock(spec=process_ifg.convert)
    monkeypatch.setattr(process_ifg, "convert", m_convert)

    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)

    assert pg_geocode_mock.cpx_to_real.called is False
    assert pg_geocode_mock.geocode_back.called is False
    assert pg_geocode_mock.mask_data.called is False
    assert pg_geocode_mock.rasrmg.called is False
    assert pg_geocode_mock.kml_map.called is False
    assert m_convert.called is False
    assert remove_mock.called is False

    width_in, width_out = 9, 13  # fake values
    process_ifg.geocode_flattened_ifg(ic_mock, dc_mock, tc_mock, width_in, width_out)

    assert pg_geocode_mock.cpx_to_real.called
    assert pg_geocode_mock.geocode_back.called
    assert pg_geocode_mock.mask_data.called
    assert pg_geocode_mock.rasrmg.called
    assert pg_geocode_mock.kml_map.called
    assert m_convert.called
    assert remove_mock.called


def test_geocode_filtered_ifg(
    logging_ctx, monkeypatch, ic_mock, dc_mock, pg_geocode_mock, tc_mock, remove_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)

    # patch convert function for testing this part of geocode step
    m_convert = mock.Mock(spec=process_ifg.convert)
    monkeypatch.setattr(process_ifg, "convert", m_convert)

    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)

    assert pg_geocode_mock.cpx_to_real.called is False
    assert pg_geocode_mock.geocode_back.called is False
    assert pg_geocode_mock.mask_data.called is False
    assert pg_geocode_mock.rasrmg.called is False
    assert pg_geocode_mock.kml_map.called is False
    assert m_convert.called is False
    assert remove_mock.called is False

    width_in, width_out = 15, 19  # fake values
    process_ifg.geocode_filtered_ifg(ic_mock, dc_mock, tc_mock, width_in, width_out)

    assert pg_geocode_mock.cpx_to_real.called
    assert pg_geocode_mock.geocode_back.called
    assert pg_geocode_mock.mask_data.called
    assert pg_geocode_mock.rasrmg.called
    assert pg_geocode_mock.kml_map.called
    assert m_convert.called
    assert remove_mock.called


def test_geocode_flat_coherence_file(
    logging_ctx, monkeypatch, ic_mock, dc_mock, pg_geocode_mock, tc_mock, remove_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)

    # patch convert function for testing this part of geocode step
    m_convert = mock.Mock(spec=process_ifg.convert)
    monkeypatch.setattr(process_ifg, "convert", m_convert)

    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)

    assert pg_geocode_mock.geocode_back.called is False
    assert pg_geocode_mock.rascc.called is False
    assert pg_geocode_mock.ras2ras.called is False
    assert pg_geocode_mock.kml_map.called is False
    assert m_convert.called is False

    width_in, width_out = 33, 37  # fake values
    process_ifg.geocode_flat_coherence_file(
        ic_mock, dc_mock, tc_mock, width_in, width_out
    )

    assert pg_geocode_mock.geocode_back.called
    assert pg_geocode_mock.rascc.called
    assert pg_geocode_mock.ras2ras.called
    assert pg_geocode_mock.kml_map.called
    assert m_convert.called


def test_geocode_filtered_coherence_file(
    logging_ctx, monkeypatch, ic_mock, dc_mock, pg_geocode_mock, tc_mock, remove_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)

    m_convert = mock.Mock(spec=process_ifg.convert)
    monkeypatch.setattr(process_ifg, "convert", m_convert)

    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)

    assert pg_geocode_mock.geocode_back.called is False
    assert pg_geocode_mock.rascc.called is False
    assert pg_geocode_mock.ras2ras.called is False
    assert pg_geocode_mock.kml_map.called is False
    assert m_convert.called is False

    width_in, width_out = 43, 31  # fake values
    process_ifg.geocode_filtered_coherence_file(
        ic_mock, dc_mock, tc_mock, width_in, width_out
    )

    assert pg_geocode_mock.geocode_back.called
    assert pg_geocode_mock.rascc.called
    assert pg_geocode_mock.ras2ras.called
    assert pg_geocode_mock.kml_map.called
    assert m_convert.called


def test_do_geocode(
    logging_ctx, monkeypatch, pc_mock, ic_mock, dc_mock, tc_mock, pg_geocode_mock, remove_mock
):
    """Test the full geocode step"""
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)

    pc_mock.ifg_geotiff.lower.return_value = "yes"

    # mock the width config file readers
    fake_ifg_width = 22
    m_width_in = mock.Mock(return_value=fake_ifg_width)
    m_width_out = mock.Mock(return_value=11)
    monkeypatch.setattr(process_ifg, "get_width_in", m_width_in)
    monkeypatch.setattr(process_ifg, "get_width_out", m_width_out)

    # mock individual processing functions as they're tested elsewhere
    m_geocode_unwrapped_ifg = mock.Mock()
    m_geocode_flattened_ifg = mock.Mock()
    m_geocode_filtered_ifg = mock.Mock()
    m_geocode_flat_coherence_file = mock.Mock()
    m_geocode_filtered_coherence_file = mock.Mock()
    m_rasrmg_wrapper = mock.Mock()

    monkeypatch.setattr(process_ifg, "geocode_unwrapped_ifg", m_geocode_unwrapped_ifg)
    monkeypatch.setattr(process_ifg, "geocode_flattened_ifg", m_geocode_flattened_ifg)
    monkeypatch.setattr(process_ifg, "geocode_filtered_ifg", m_geocode_filtered_ifg)
    monkeypatch.setattr(
        process_ifg, "geocode_flat_coherence_file", m_geocode_flat_coherence_file
    )
    monkeypatch.setattr(
        process_ifg, "geocode_filtered_coherence_file", m_geocode_filtered_coherence_file
    )
    monkeypatch.setattr(process_ifg, "remove_files", remove_mock)
    monkeypatch.setattr(process_ifg, "rasrmg_wrapper", m_rasrmg_wrapper)

    process_ifg.do_geocode(pc_mock, ic_mock, dc_mock, tc_mock, fake_ifg_width)

    assert m_width_in.called
    assert m_width_out.called
    assert m_geocode_unwrapped_ifg.called
    assert m_geocode_flattened_ifg.called
    assert m_geocode_filtered_ifg.called
    assert m_geocode_flat_coherence_file.called
    assert m_geocode_filtered_ifg.called

    assert pg_geocode_mock.data2geotiff.call_count == 5
    assert remove_mock.call_count == len(const.TEMP_FILE_GLOBS)


def test_do_geocode_no_geotiff(
    logging_ctx, monkeypatch, pc_mock, ic_mock, dc_mock, tc_mock, pg_geocode_mock
):
    fake_ifg_width = 32
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)
    pc_mock.ifg_geotiff.lower.return_value = "no"
    monkeypatch.setattr(
        process_ifg, "get_width_in", mock.Mock(return_value=fake_ifg_width)
    )
    monkeypatch.setattr(process_ifg, "get_width_out", mock.Mock(return_value=31))

    monkeypatch.setattr(process_ifg, "geocode_unwrapped_ifg", mock.Mock())
    monkeypatch.setattr(process_ifg, "geocode_flattened_ifg", mock.Mock())
    monkeypatch.setattr(process_ifg, "geocode_filtered_ifg", mock.Mock())
    monkeypatch.setattr(process_ifg, "geocode_flat_coherence_file", mock.Mock())
    monkeypatch.setattr(process_ifg, "geocode_filtered_coherence_file", mock.Mock())
    monkeypatch.setattr(process_ifg, "rasrmg_wrapper", mock.Mock())

    process_ifg.do_geocode(pc_mock, ic_mock, dc_mock, tc_mock, fake_ifg_width)

    assert pg_geocode_mock.data2geotiff.called is False


def test_do_geocode_width_mismatch(
    logging_ctx, monkeypatch, pc_mock, ic_mock, dc_mock, tc_mock, pg_geocode_mock
):
    monkeypatch.setattr(process_ifg, "pg", pg_geocode_mock)
    pc_mock.ifg_geotiff.lower.return_value = "no"

    fake_ifg_width = 10
    fake_width_in = 20
    monkeypatch.setattr(
        process_ifg, "get_width_in", mock.Mock(return_value=fake_width_in)
    )

    with pytest.raises(ProcessIfgException):
        process_ifg.do_geocode(pc_mock, ic_mock, dc_mock, tc_mock, fake_ifg_width)


def test_get_width_in():
    config = io.StringIO("Fake line\nrange_samp_1: 45\nAnother fake\n")
    assert process_ifg.get_width_in(config) == 45


def test_get_width_in_not_found():
    config = io.StringIO("Fake line 0\nFake line 1\nFake line 2\n")
    with pytest.raises(ProcessIfgException):
        process_ifg.get_width_in(config)


def test_get_width_out():
    config = io.StringIO("Fake line\nwidth: 32\nAnother fake\n")
    assert process_ifg.get_width_out(config) == 32


def test_get_width_out_not_found():
    config = io.StringIO("Fake line 0\nFake line 1\nFake line 2\n")
    with pytest.raises(ProcessIfgException):
        process_ifg.get_width_out(config)


def test_convert(monkeypatch):
    m_file = mock.NonCallableMock()
    m_convert = mock.Mock()
    monkeypatch.setattr(process_ifg, "convert", m_convert)

    assert m_convert.called is False
    process_ifg.convert(m_file)
    assert m_convert.called is True
    assert m_file.called is False


def test_remove_files_empty_path():
    process_ifg.remove_files("")  # should pass quietly


def test_remove_files_with_error(monkeypatch):
    m_file_not_found = mock.NonCallableMock()
    m_file_not_found.unlink.side_effect = FileNotFoundError("Fake File Not Found")

    m_log = mock.NonCallableMock()
    monkeypatch.setattr(process_ifg, "_LOG", m_log)

    # file not found should be logged but ignored
    process_ifg.remove_files(m_file_not_found)
    assert m_log.error.called


def test_temp_files(ic_mock):
    tc = process_ifg.TempFileConfig(ic_mock)

    # check paths in FLAT/flattening step
    assert tc.ifg_flat10_unw.as_posix()
    assert tc.ifg_flat1_unw.as_posix()
    assert tc.ifg_flat_diff_int_unw.as_posix()

    # check paths in geocoding steps
    assert tc.geocode_unwrapped_ifg.as_posix()
    assert tc.geocode_flat_ifg.as_posix()
    assert tc.geocode_filt_ifg.as_posix()
    assert tc.geocode_flat_coherence_file.as_posix()
    assert tc.geocode_filt_coherence_file.as_posix()

    # TODO: geocoded binary file globs/patterns
