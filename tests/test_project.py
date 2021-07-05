import io
import pathlib
from insar import project

from unittest.mock import Mock
import pytest


def test_create_config():
    config = project.Config()
    assert config.proc_variables is None
    assert config.final_file_loc is None
    assert config.dem_primary_names is None
    assert config.dem_file_names is None
    assert config.ifg_file_names is None


# tests for ProcConfig
def test_read_proc_file():
    file_obj = open(pathlib.Path(__file__).parent.absolute() / 'data' / '20151127' / 'gamma.proc', 'r')
    assert file_obj.closed is False

    pv = project.ProcConfig.from_file(file_obj)
    assert pv.nci_path.as_posix() == "/some/test/data"
    assert pv.slc_dir.as_posix() == "SLC"
    assert pv.ifg_list == "ifgs.list"
    assert pv.primary_dem_image

    # check secondary variables derived from the proc file
    assert pv.dem_img.as_posix() == "{}/GAMMA_DEM_SRTM_1as_mosaic.img".format(
        pv.primary_dem_image
    )
    assert pv.proj_dir.as_posix() == "{}/{}/{}/GAMMA".format(
        pv.nci_path, pv.project, pv.sensor
    )
    assert pv.raw_data_track_dir.as_posix() == "{}/{}".format(pv.raw_data_dir, pv.track)
    assert pv.dem_noff1 == "0"
    assert pv.dem_noff2 == "0"
    assert pv.ifg_rpos == pv.dem_rpos
    assert pv.ifg_azpos == pv.dem_azpos


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
    mock_proc = Mock()
    mock_proc.batch_job_dir = BATCH_BASE
    mock_proc.manual_job_dir = MANUAL_BASE
    mock_proc.proj_dir = pathlib.Path("tmp/")
    mock_proc.slc_dir = "slc-dir"
    mock_proc.ref_primary_scene = "ref-primary-scene"
    mock_proc.polarisation = "polarisation"
    mock_proc.range_looks = "range-looks"
    mock_proc.gamma_dem_dir = "gamma-dem-dir"
    mock_proc.dem_name = "dem-name"
    mock_proc.dem_dir = "dem-dir"
    mock_proc.results_dir = "results-dir"
    mock_proc.track = "track"

    return mock_proc


def test_default_dem_primary_paths(mproc):
    slc_dir = f"tmp/{mproc.track}/slc-dir"
    ref_primary_scene = "ref-primary-scene"
    polarisation = "polarisation"
    range_looks = "range-looks"

    cfg = project.DEMPrimaryNames(mproc)
    assert len([x for x in dir(cfg) if x.startswith("dem_")]) == 12
    assert len([x for x in dir(cfg) if x.startswith("r_dem_")]) == 7

    # pathlib.Path objs are immutable, requiring as_posix() & changing full ext using with_suffix()
    # some of this is a bit ugly
    assert cfg.dem_primary_dir.as_posix() == "{}/{}".format(slc_dir, ref_primary_scene)
    assert cfg.dem_primary_slc_name.as_posix() == "{}/{}_{}".format(
        cfg.dem_primary_dir, ref_primary_scene, polarisation
    )
    assert cfg.dem_primary_slc == cfg.dem_primary_slc_name.with_suffix(".slc")
    assert cfg.dem_primary_slc_par == cfg.dem_primary_slc.with_suffix(".slc.par")

    assert cfg.dem_primary_mli_name.as_posix() == "{}/{}_{}_{}rlks".format(
        cfg.dem_primary_dir, ref_primary_scene, polarisation, range_looks
    )
    assert cfg.dem_primary_mli == cfg.dem_primary_mli_name.with_suffix(".mli")
    assert cfg.dem_primary_mli_par == cfg.dem_primary_mli.with_suffix(".mli.par")

    assert cfg.dem_primary_gamma0 == cfg.dem_primary_mli_name.with_suffix(".gamma0")
    assert cfg.dem_primary_gamma0_bmp == cfg.dem_primary_gamma0.with_suffix(".gamma0.bmp")
    assert (
        cfg.dem_primary_gamma0_geo.as_posix()
        == cfg.dem_primary_mli_name.as_posix() + "_geo.gamma0"
    )
    assert (
        cfg.dem_primary_gamma0_geo_bmp.as_posix()
        == cfg.dem_primary_gamma0_geo.as_posix() + ".bmp"
    )
    assert (
        cfg.dem_primary_gamma0_geo_geo.as_posix()
        == cfg.dem_primary_gamma0_geo.as_posix() + ".tif"
    )

    assert cfg.r_dem_primary_slc_name.as_posix() == "{}/r{}_{}".format(
        cfg.dem_primary_dir, ref_primary_scene, polarisation
    )
    assert cfg.r_dem_primary_slc == cfg.r_dem_primary_slc_name.with_suffix(".slc")
    assert cfg.r_dem_primary_slc_par == cfg.r_dem_primary_slc.with_suffix(".slc.par")

    assert cfg.r_dem_primary_mli_name.as_posix() == "{}/r{}_{}_{}rlks".format(
        cfg.dem_primary_dir, ref_primary_scene, polarisation, range_looks
    )

    assert cfg.r_dem_primary_mli == cfg.r_dem_primary_mli_name.with_suffix(".mli")
    assert cfg.r_dem_primary_mli_par == cfg.r_dem_primary_mli.with_suffix(".mli.par")
    assert cfg.r_dem_primary_mli_bmp == cfg.r_dem_primary_mli.with_suffix(".mli.bmp")


def test_default_dem_primary_paths_none_setting(mproc):
    """Ensure incomplete proc settings prevent DEM config from being initialised."""
    mproc.slc_dir = None

    with pytest.raises(Exception):
        project.DEMPrimaryNames(mproc)


def test_default_dem_file_names(mproc):
    cfg = project.DEMFileNames(mproc)

    outdir = pathlib.Path("tmp/") / mproc.track

    assert cfg.dem.as_posix() == "tmp/{}/{}/{}.dem".format(
        mproc.track, mproc.gamma_dem_dir, mproc.dem_name
    )
    assert cfg.dem_par.as_posix() == "{}.par".format(cfg.dem)
    assert cfg.dem_primary_name.as_posix() == "tmp/{}/{}/{}_{}_{}rlks".format(
        mproc.track,
        mproc.dem_dir,
        mproc.ref_primary_scene,
        mproc.polarisation,
        mproc.range_looks,
    )

    assert cfg.dem_diff.as_posix() == "tmp/{}/{}/diff_{}_{}_{}rlks.par".format(
        mproc.track,
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
    assert cfg.ext_image_flt == tail(dem_primary_name, "_ext_img_sar.flt")
    assert cfg.ext_image_init_sar == tail(dem_primary_name, "_ext_img_init.sar")
    assert cfg.ext_image_sar == tail(dem_primary_name, "_ext_img.sar")

    assert cfg.dem_check_file == outdir / "results-dir/track_DEM_coreg_results"
    assert cfg.lat_lon_pix == outdir / "dem-dir/track_range-looksrlks_sar_latlon.txt"


def test_default_ifg_file_names(mproc):
    mproc.int_dir = pathlib.Path("INT")
    shapefile = pathlib.Path("shapefile.shp")
    primary = pathlib.Path("primary")
    secondary = pathlib.Path("secondary")
    cfg = project.IfgFileNames(mproc, shapefile, primary, secondary)
    outdir = f"tmp/{mproc.track}"
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

