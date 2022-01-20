import io
import pathlib
from insar import project
from insar.paths.interferogram import InterferogramPaths
from insar.paths.dem import DEMPaths

from unittest.mock import MagicMock
import pytest

# tests for ProcConfig
def test_read_proc_file():
    file_obj = open(pathlib.Path(__file__).parent.absolute() / 'data' / '20151127' / 'gamma.proc', 'r')
    assert file_obj.closed is False

    pv = project.ProcConfig.from_file(file_obj)
    assert pv.slc_dir.as_posix() == "SLC"
    assert pv.ifg_list == "ifgs.list"
    assert pathlib.Path(pv.primary_dem_image).name == "GAMMA_DEM_SRTM_1as_mosaic.img"


def test_read_incomplete_proc_file_fails():
    """Ensure partial proc files cannot be used."""
    file_obj = open(pathlib.Path(__file__).parent.absolute() / 'data' / '20151127' / 'gamma.proc', 'r')
    file_obj.seek(500)

    with pytest.raises(AttributeError):
        project.ProcConfig.from_file(file_obj)


def test_read_unknown_settings():
    """Fail fast if unrecognised settings are found"""
    content = "FAKE_SETTING=foo\n"
    file_obj = io.StringIO(content)

    with pytest.raises(AttributeError):
        project.ProcConfig.from_file(file_obj)


# tests for the PBS job dirs section
BATCH_BASE = "tmp/pbs"
MANUAL_BASE = "tmp/manual"


@pytest.fixture
def mproc():
    """Mock the Gamma proc file/config settings."""
    mock_proc = MagicMock()
    mock_proc.batch_job_dir = BATCH_BASE
    mock_proc.manual_job_dir = MANUAL_BASE
    mock_proc.output_path = pathlib.Path("tmp/")
    mock_proc.slc_dir = "slc-dir"
    mock_proc.ref_primary_scene = "ref-primary-scene"
    mock_proc.polarisation = "polarisation"
    mock_proc.range_looks = "range-looks"
    mock_proc.gamma_dem_dir = "gamma-dem-dir"
    mock_proc.dem_dir = "dem-dir"
    mock_proc.track = "track"
    mock_proc.stack_id = "test_stack"

    return mock_proc


def test_default_dem_file_names(mproc):
    cfg = DEMPaths(mproc)

    assert cfg.dem.as_posix() == "{}/{}/{}.dem".format(
        mproc.output_path, mproc.gamma_dem_dir, mproc.stack_id
    )
    assert cfg.dem_par.as_posix() == "{}.par".format(cfg.dem)
    assert cfg.dem_primary_name.as_posix() == "{}/{}/{}_{}_{}rlks".format(
        mproc.output_path,
        mproc.dem_dir,
        mproc.ref_primary_scene,
        mproc.polarisation,
        mproc.range_looks,
    )

    assert cfg.dem_diff.as_posix() == "{}/{}/diff_{}_{}_{}rlks.par".format(
        mproc.output_path,
        mproc.dem_dir,
        mproc.ref_primary_scene,
        mproc.polarisation,
        mproc.range_looks,
    )

    dem_primary_name = cfg.dem_primary_name

    def tail(path, suffix):
        return path.parent / (path.name + suffix)

    assert cfg.rdc_dem == tail(dem_primary_name, "_rdc.dem")

    # NB: rest of these are only string concatenation, so probably not worth testing!
    assert cfg.geo_dem == tail(dem_primary_name, "_geo.dem")
    # assert cfg.geo_dem_par == geo_dem.par
    assert cfg.seamask == tail(dem_primary_name, "_geo_seamask.tif")
    assert cfg.dem_lt_rough == tail(dem_primary_name, "_rough_geo_to_rdc.lt")
    assert cfg.dem_lt_fine == tail(dem_primary_name, "_geo_to_rdc.lt")
    assert cfg.dem_geo_sim_sar == tail(dem_primary_name, "_geo.sim")
    assert cfg.dem_rdc_sim_sar == tail(dem_primary_name, "_rdc.sim")
    assert cfg.dem_loc_inc == tail(dem_primary_name, "_geo.linc")
    assert cfg.dem_rdc_inc == tail(dem_primary_name, "_rdc.linc")
    assert cfg.dem_lsmap == tail(dem_primary_name, "_geo.lsmap")
    assert cfg.ellip_pix_sigma0 == tail(dem_primary_name, "_ellip_pix_sigma0")
    assert cfg.dem_pix_gam == tail(dem_primary_name, "_rdc_pix_gamma0")
    # assert cfg.dem_pix_gam_bmp == dem_pix_gam".bmp"
    assert cfg.dem_off == tail(dem_primary_name, ".off")
    assert cfg.dem_offs == tail(dem_primary_name, ".offs")
    assert cfg.dem_ccp == tail(dem_primary_name, ".ccp")
    assert cfg.dem_offsets == tail(dem_primary_name, ".offsets")
    assert cfg.dem_coffs == tail(dem_primary_name, ".coffs")
    assert cfg.dem_coffsets == tail(dem_primary_name, ".coffsets")
    assert cfg.dem_lv_theta == tail(dem_primary_name, "_geo.lv_theta")
    assert cfg.dem_lv_phi == tail(dem_primary_name, "_geo.lv_phi")


# TODO: I'm not sure what to do w/ these tests... having tests that compare
# fields (which are set to some structured path in the __init__ of their class)
# to some other structured paths in the test doesn't really test anything besides
# that two people wrote the same structured paths in two different files.
#
# I guess the intent of the test is to check the stack structure? but over
# many tests (for each set of file path classes) - might be better to
# do this as an actual workflow test that sanity checks the actual stack output
# structure in this case? (we already partially do this in test_workflow)
def test_default_ifg_file_names(mproc):
    mproc.int_dir = pathlib.Path("INT")
    primary = pathlib.Path("primary")
    secondary = pathlib.Path("secondary")
    cfg = InterferogramPaths(mproc, primary, secondary)
    outdir = mproc.output_path
    intdir = f"{outdir}/INT"
    slcdir = f"{outdir}/slc-dir"

    assert cfg.ifg_dir.as_posix() == f"{intdir}/primary-secondary"
    assert cfg.primary_dir.as_posix() == f"{slcdir}/primary"
    assert cfg.secondary_dir.as_posix() == f"{slcdir}/secondary"
    assert cfg.r_primary_slc_name.as_posix() == f"{slcdir}/primary/rprimary_polarisation"
    assert cfg.r_primary_slc.as_posix() == f"{slcdir}/primary/rprimary_polarisation.slc"
    assert (
        cfg.r_primary_slc_par.as_posix() == f"{slcdir}/primary/rprimary_polarisation.slc.par"
    )

    assert (
        cfg.r_primary_mli_name.as_posix()
        == f"{slcdir}/primary/rprimary_polarisation_range-looksrlks"
    )
    assert (
        cfg.r_primary_mli.as_posix()
        == f"{slcdir}/primary/rprimary_polarisation_range-looksrlks.mli"
    )
    assert (
        cfg.r_primary_mli_par.as_posix()
        == f"{slcdir}/primary/rprimary_polarisation_range-looksrlks.mli.par"
    )

    assert cfg.r_secondary_slc_name.as_posix() == f"{slcdir}/secondary/rsecondary_polarisation"
    assert cfg.r_secondary_slc.as_posix() == f"{slcdir}/secondary/rsecondary_polarisation.slc"
    assert cfg.r_secondary_slc_par.as_posix() == f"{slcdir}/secondary/rsecondary_polarisation.slc.par"

    assert (
        cfg.r_secondary_mli_name.as_posix()
        == f"{slcdir}/secondary/rsecondary_polarisation_range-looksrlks"
    )

    # ignore vars after this as it's just testing string concatenation
    assert (
        cfg.primary_secondary_name.as_posix()
        == f"{intdir}/primary-secondary/primary-secondary_polarisation_range-looksrlks"
    )

    # tests for the GEOCODE() output filenames
    assert cfg.ifg_unw_geocode_out_tiff.as_posix().count(".") == 1
    assert cfg.ifg_flat_geocode_out_tiff.as_posix().count(".") == 1
    assert cfg.ifg_filt_geocode_out_tiff.as_posix().count(".") == 1
    assert cfg.ifg_flat_coh_geocode_out_tiff.as_posix().count(".") == 1
    assert cfg.ifg_filt_coh_geocode_out_tiff.as_posix().count(".") == 1

    ms_base = "primary-secondary_polarisation_range-looksrlks{}"
    assert cfg.ifg_unw_geocode_out_tiff.as_posix() == ms_base.format("_geo_unw.tif")
    assert cfg.ifg_flat_geocode_out_tiff.as_posix().endswith("_flat_geo_int.tif")
    assert cfg.ifg_filt_geocode_out_tiff.as_posix().endswith("_filt_geo_int.tif")
    assert cfg.ifg_flat_coh_geocode_out_tiff.as_posix().endswith("_flat_geo_coh.tif")
    assert cfg.ifg_filt_coh_geocode_out_tiff.as_posix().endswith("_filt_geo_coh.tif")

