"""
Utilities for managing Gamma settings for the InSAR ARD workflow.
"""

import os
import pathlib
from collections import namedtuple


class ProcConfig:
    """Container for Gamma proc files (collection of runtime settings)."""

    # NB: use slots to prevent accidental addition of variables from typos
    __slots__ = [
        "gamma_config",
        "nci_path",
        "envisat_orbits",
        "ers_orbits",
        "s1_orbits",
        "s1_path",
        "master_dem_image",
        "slc_dir",
        "dem_dir",
        "int_dir",
        "base_dir",
        "list_dir",
        "error_dir",
        "pdf_dir",
        "raw_data_dir",
        "batch_job_dir",
        "manual_job_dir",
        "pre_proc_dir",
        "scene_list",
        "slave_list",
        "ifg_list",
        "frame_list",
        "s1_burst_list",
        "s1_download_list",
        "remove_scene_list",
        "project",
        "track",
        "dem_area",
        "dem_name",
        "mdss_data_dir",
        "mdss_dem_tar",
        "ext_image",
        "polarisation",
        "sensor",
        "sensor_mode",
        "ers_sensor",
        "palsar2_type",
        "multi_look",
        "range_looks",
        "azimuth_looks",
        "process_method",
        "ref_master_scene",
        "min_connect",
        "max_connect",
        "post_process_method",
        "extract_raw_data",
        "do_slc",
        "do_s1_resize",
        "s1_resize_ref_slc",
        "do_s1_burst_subset",
        "coregister_dem",
        "use_ext_image",
        "coregister_slaves",
        "process_ifgs",
        "ifg_geotiff",
        "clean_up",
        "dem_patch_window",
        "dem_rpos",
        "dem_azpos",
        "dem_offset",
        "dem_offset_measure",
        "dem_win",
        "dem_snr",
        "dem_rad_max",
        "coreg_cc_thresh",
        "coreg_model_params",
        "coreg_window_size",
        "coreg_num_windows",
        "coreg_oversampling",
        "coreg_num_iterations",
        "slave_offset_measure",
        "slave_win",
        "slave_cc_thresh",
        "coreg_s1_cc_thresh",
        "coreg_s1_frac_thresh",
        "coreg_s1_stdev_thresh",
        "ifg_begin",
        "ifg_end",
        "ifg_coherence_threshold",
        "ifg_unw_mask",
        "ifg_patches_range",
        "ifg_patches_azimuth",
        "ifg_patches_overlap_px",
        "ifg_ref_point_range",
        "ifg_ref_point_azimuth",
        "ifg_exponent",
        "ifg_filtering_window",
        "ifg_coherence_window",
        "ifg_iterative",
        "ifg_thres",
        "ifg_init_win",
        "ifg_offset_win",
        "post_ifg_da_threshold",
        "post_ifg_area_range",
        "post_ifg_area_azimuth",
        # 'post_ifg_area_range',
        # 'post_ifg_area_azimuth',
        "post_ifg_patches_range",
        "post_ifg_patches_azimuth",
        "post_ifg_overlap_range",
        "post_ifg_overlap_azimuth",
        "nci_project",
        "min_jobs",
        "max_jobs",
        "pbs_run_loc",
        "queue",
        "exp_queue",
        "mdss_queue",
        "raw_walltime",
        "raw_mem",
        "raw_ncpus",
        "create_dem_walltime",
        "create_dem_mem",
        "create_dem_ncpus",
        "slc_walltime",
        "slc_mem",
        "slc_ncpus",
        "calc_walltime",
        "calc_mem",
        "calc_ncpus",
        "base_walltime",
        "base_mem",
        "base_ncpus",
        "ml_walltime",
        "ml_mem",
        "ml_ncpus",
        "resize_walltime",
        "resize_mem",
        "resize_ncpus",
        "dem_walltime",
        "dem_mem",
        "dem_ncpus",
        "pix_walltime",
        "pix_mem",
        "pix_ncpus",
        "coreg_walltime",
        "coreg_mem",
        "coreg_ncpus",
        "ifg_walltime",
        "ifg_mem",
        "ifg_ncpus",
        "post_walltime",
        "post_mem",
        "post_ncpus",
        "error_walltime",
        "error_mem",
        "error_ncpus",
        "image_walltime",
        "image_mem",
        "image_ncpus",
        # derived member vars
        "dem_img",
        "proj_dir",
        "raw_data_track_dir",
        "gamma_dem_dir",
        "results_dir",
        "dem_noff1",
        "dem_noff2",
        "ifg_rpos",
        "ifg_azpos",
    ]

    def __init__(self, outdir, **kwargs):
        """
        Create a ProcConfig instance.
        :param kwargs: mapping of keywords and values from a proc config settings file.
        """
        for k, v in kwargs.items():
            # auto convert string paths to Paths to clean up workflow file handling
            if "_path" in k or "_dir" in k or "_img" in k:
                v = pathlib.Path(v)
            setattr(self, k, v)

        # prepare derived settings variables
        self.dem_img = (
            pathlib.Path(self.master_dem_image) / "GAMMA_DEM_SRTM_1as_mosaic.img"
        )
        self.proj_dir = pathlib.Path(self.nci_path) / self.project / self.sensor / "GAMMA"
        self.raw_data_track_dir = pathlib.Path(self.raw_data_dir) / self.track
        self.gamma_dem_dir = "gamma_dem"
        self.results_dir = "results"

        self.dem_noff1, self.dem_noff2 = self.dem_offset.split(" ")
        self.ifg_rpos = self.dem_rpos
        self.ifg_azpos = self.dem_azpos

        # Handle "auto" reference scene
        if self.ref_master_scene.lower() == "auto":
            # Read computed master scene and use it
            with open(pathlib.Path(outdir) / self.list_dir / 'primary_ref_scene', 'r') as ref_scene_file:
                auto_master_scene = ref_scene_file.readline().strip()

            self.ref_master_scene = auto_master_scene

    @classmethod
    def from_file(cls, file_obj, outdir):
        """
        Returns a ProcConfig instantiated from the given file like obj.

        :param file_obj: an open file like object
        :return: new ProcConfig object
        """
        raw_lines = [
            line.strip() for line in file_obj.readlines() if is_valid_config_line(line)
        ]
        kv_pairs = [line.split("=") for line in raw_lines]

        # rename any keys with hyphens
        for pair in kv_pairs:
            pair[0] = pair[0].replace("-", "_")

        cfg = {e[0].strip().lower(): e[1].strip() for e in kv_pairs}
        return ProcConfig(outdir, **cfg)


def is_valid_config_line(line):
    """
    Test a line is a valid configuration entry: e.g. "setting=value"

    Assumes line has been stripped of whitespace.
    """
    if not line.startswith("#"):
        return "=" in line
    return False


PBS_job_dirs = namedtuple(
    "PBS_job_dirs",
    [
        "extract_raw_batch_dir",
        "slc_batch_dir",
        "ml_batch_dir",
        "base_batch_dir",
        "dem_batch_dir",
        "co_slc_batch_dir",
        "ifg_batch_dir",
        "extract_raw_manual_dir",
        "slc_manual_dir",
        "ml_manual_dir",
        "base_manual_dir",
        "dem_manual_dir",
        "co_slc_manual_dir",
        "ifg_manual_dir",
    ],
)


def get_default_pbs_job_dirs(proc):
    """
    Return a PBS_job_dirs obj with the defaulted directory settings.

    :param proc: ProcConfig obj
    :return: default PBS_job_dirs obj
    """

    batch_dirs = [
        "extract_raw_jobs",
        "slc_jobs",
        "ml_slc_jobs",
        "baseline_jobs",
        "dem_jobs",
        "coreg_slc_jobs",
        "ifg_jobs",
    ]

    manual_dirs = [
        "extract_raw_jobs",
        "slc_jobs",
        "ml_slc_jobs",
        "baseline_jobs",
        "dem_jobs",
        "coreg_slc_jobs",
        "ifg_jobs",
    ]

    args = [pathlib.Path(proc.batch_job_dir) / d for d in batch_dirs]
    args.extend([pathlib.Path(proc.manual_job_dir) / d for d in manual_dirs])
    return PBS_job_dirs(*args)


Sentinel1_PBS_job_dirs = namedtuple(
    "Sentinel1_PBS_job_dirs",
    ["resize_batch_dir", "subset_batch_dir", "resize_manual_dir", "subset_manual_dir"],
)


def get_default_sentinel1_pbs_job_dirs(proc):
    batch_dirs = ["resize_S1_slc_jobs", "subset_S1_slc_jobs"]
    manual_dirs = ["resize_S1_slc_jobs", "subset_S1_slc_jobs"]

    args = [pathlib.Path(proc.batch_job_dir) / d for d in batch_dirs]
    args.extend([pathlib.Path(proc.manual_job_dir) / d for d in manual_dirs])
    return Sentinel1_PBS_job_dirs(*args)


class DEMMasterNames:
    __slots__ = [
        "dem_master_dir",
        "dem_master_slc_name",
        "dem_master_slc",
        "dem_master_slc_par",
        "dem_master_mli_name",
        "dem_master_mli",
        "dem_master_mli_par",
        "dem_master_gamma0",
        "dem_master_gamma0_bmp",
        "dem_master_gamma0_geo",
        "dem_master_gamma0_geo_bmp",
        "dem_master_gamma0_geo_geo",
        "r_dem_master_slc_name",
        "r_dem_master_slc",
        "r_dem_master_slc_par",
        "r_dem_master_mli_name",
        "r_dem_master_mli",
        "r_dem_master_mli_par",
        "r_dem_master_mli_bmp",
    ]

    def __init__(self, proc=None, out_dir = None):
        if proc:
            if not out_dir:
                out_dir = proc.proj_dir / proc.track

            out_dir = pathlib.Path(out_dir)

            self.dem_master_dir = out_dir / proc.slc_dir / proc.ref_master_scene

            suffix = proc.ref_master_scene + "_" + proc.polarisation
            self.dem_master_slc_name = self.dem_master_dir / suffix

            self.dem_master_slc = self.dem_master_dir / (suffix + ".slc")
            self.dem_master_slc_par = self.dem_master_dir / (
                suffix + ".slc.par"
            )

            suffix_lks = (
                proc.ref_master_scene
                + "_"
                + proc.polarisation
                + "_"
                + proc.range_looks
                + "rlks"
            )
            self.dem_master_mli_name = self.dem_master_dir / suffix_lks

            self.dem_master_mli = self.dem_master_dir / (
                suffix_lks + ".mli"
            )
            self.dem_master_mli_par = self.dem_master_dir / (
                suffix_lks + ".mli.par"
            )
            self.dem_master_gamma0 = self.dem_master_dir / (
                suffix_lks + ".gamma0"
            )
            self.dem_master_gamma0_bmp = self.dem_master_dir / (
                suffix_lks + ".gamma0.bmp"
            )

            self.dem_master_gamma0_geo = self.dem_master_dir / (
                suffix_lks + "_geo.gamma0"
            )
            self.dem_master_gamma0_geo_bmp = self.dem_master_dir / (
                suffix_lks + "_geo.gamma0.bmp"
            )
            self.dem_master_gamma0_geo_geo = self.dem_master_dir / (
                suffix_lks + "_geo.gamma0.tif"
            )

            suffix_slc = "r{}_{}".format(proc.ref_master_scene, proc.polarisation)
            self.r_dem_master_slc_name = self.dem_master_dir / suffix_slc

            self.r_dem_master_slc = self.dem_master_dir / (
                suffix_slc + ".slc"
            )
            self.r_dem_master_slc_par = self.dem_master_dir / (
                suffix_slc + ".slc.par"
            )

            suffix_mli = "r{}_{}_{}rlks".format(
                proc.ref_master_scene, proc.polarisation, proc.range_looks
            )
            self.r_dem_master_mli_name = self.dem_master_dir / suffix_mli

            self.r_dem_master_mli = self.dem_master_dir / (
                suffix_mli + ".mli"
            )
            self.r_dem_master_mli_par = self.dem_master_dir / (
                suffix_mli + ".mli.par"
            )
            self.r_dem_master_mli_bmp = self.dem_master_dir / (
                suffix_mli + ".mli.bmp"
            )


class DEMFileNames:
    __slots__ = [
        "dem",
        "dem_par",
        "dem_master_name",
        "dem_diff",
        "rdc_dem",
        "geo_dem",
        "geo_dem_par",
        "seamask",
        "dem_lt_rough",
        "dem_lt_fine",
        "dem_geo_sim_sar",
        "dem_rdc_sim_sar",
        "dem_loc_inc",
        "dem_rdc_inc",
        "dem_lsmap",
        "ellip_pix_sigma0",
        "dem_pix_gam",
        "dem_pix_gam_bmp",
        "dem_off",
        "dem_offs",
        "dem_ccp",
        "dem_offsets",
        "dem_coffs",
        "dem_coffsets",
        "dem_lv_theta",
        "dem_lv_phi",
        "ext_image_flt",
        "ext_image_init_sar",
        "ext_image_sar",
        "dem_check_file",
        "lat_lon_pix",
    ]

    def __init__(self, proc, out_dir = None):
        if not out_dir:
            out_dir = proc.proj_dir / proc.track

        out_dir = pathlib.Path(out_dir)

        self.dem = (out_dir / proc.gamma_dem_dir / proc.dem_name).with_suffix(".dem")
        self.dem_par = self.dem.with_suffix(".dem.par")
        self.dem_master_name = "{}_{}_{}rlks".format(
            proc.ref_master_scene, proc.polarisation, proc.range_looks
        )
        self.dem_master_name = out_dir / proc.dem_dir / self.dem_master_name
        dmn = self.dem_master_name

        self.dem_diff = dmn.parent / ("diff_" + dmn.name + ".par")

        self.rdc_dem = dmn.parent / (dmn.name + "_rdc.dem")
        self.geo_dem = dmn.parent / (dmn.name + "_geo.dem")
        self.geo_dem_par = self.geo_dem.with_suffix(".dem.par")
        self.seamask = dmn.parent / (dmn.name + "_geo_seamask.tif")
        self.dem_lt_rough = dmn.parent / (dmn.name + "_rough_geo_to_rdc.lt")
        self.dem_lt_fine = dmn.parent / (dmn.name + "_geo_to_rdc.lt")
        self.dem_geo_sim_sar = dmn.parent / (dmn.name + "_geo.sim")
        self.dem_rdc_sim_sar = dmn.parent / (dmn.name + "_rdc.sim")
        self.dem_loc_inc = dmn.parent / (dmn.name + "_geo.linc")
        self.dem_rdc_inc = dmn.parent / (dmn.name + "_rdc.linc")
        self.dem_lsmap = dmn.parent / (dmn.name + "_geo.lsmap")
        self.ellip_pix_sigma0 = dmn.parent / (dmn.name + "_ellip_pix_sigma0")
        self.dem_pix_gam = dmn.parent / (dmn.name + "_rdc_pix_gamma0")
        self.dem_pix_gam_bmp = self.dem_pix_gam.with_suffix(".bmp")
        self.dem_off = dmn.with_suffix(".off")
        self.dem_offs = dmn.with_suffix(".offs")
        self.dem_ccp = dmn.with_suffix(".ccp")
        self.dem_offsets = dmn.with_suffix(".offsets")
        self.dem_coffs = dmn.with_suffix(".coffs")
        self.dem_coffsets = dmn.with_suffix(".coffsets")
        self.dem_lv_theta = dmn.parent / (dmn.name + "_geo.lv_theta")
        self.dem_lv_phi = dmn.parent / (dmn.name + "_geo.lv_phi")
        self.ext_image_flt = dmn.parent / (dmn.name + "_ext_img_sar.flt")
        self.ext_image_init_sar = dmn.parent / (dmn.name + "_ext_img_init.sar")
        self.ext_image_sar = dmn.parent / (dmn.name + "_ext_img.sar")

        results_dir = out_dir / proc.results_dir
        self.dem_check_file = results_dir / (proc.track + "_DEM_coreg_results")
        self.lat_lon_pix = out_dir / proc.dem_dir / (
            proc.track
            + "_"
            + proc.range_looks
            + "rlks_sar_latlon.txt"
        )


class IfgFileNames:
    __slots__ = [
        "ifg_dir",
        "master_dir",
        "slave_dir",
        "r_master_slc_name",
        "r_master_slc",
        "r_master_slc_par",
        "r_master_mli_name",
        "r_master_mli",
        "r_master_mli_par",
        "r_slave_slc_name",
        "r_slave_slc",
        "r_slave_slc_par",
        "r_slave_mli_name",
        "r_slave_mli",
        "r_slave_mli_par",
        "master_slave_name",
        "ifg_base",
        "ifg_base_init",
        "ifg_base_res",
        "ifg_base_temp",
        "ifg_bperp",
        "ifg_ccp",
        "ifg_coffs",
        "ifg_coffsets",
        "ifg_diff_par",
        "ifg_filt",
        "ifg_filt_float",
        "ifg_filt_geocode_bmp",
        "ifg_filt_geocode_out",
        "ifg_filt_geocode_png",
        "ifg_filt_mask",
        "ifg_filt_coh",
        "ifg_filt_coh_geocode_bmp",
        "ifg_filt_coh_geocode_out",
        "ifg_filt_coh_geocode_png",
        "ifg_flat",
        "ifg_flat_float",
        "ifg_flat_geocode_bmp",
        "ifg_flat_geocode_out",
        "ifg_flat_geocode_png",
        "ifg_flat_temp",
        "ifg_flat0",
        "ifg_flat1",
        "ifg_flat10",
        "ifg_flat_coh",
        "ifg_flat_coh_geocode_bmp",
        "ifg_flat_coh_geocode_out",
        "ifg_flat_coh_geocode_png",
        "ifg_flat_coh0",
        "ifg_flat_coh0_mask",
        "ifg_flat_coh10",
        "ifg_flat_coh10_mask",
        "ifg_gcp",
        "ifg_gcp_ph",
        "ifg_mask",
        "ifg_mask_thin",
        "ifg_off",
        "ifg_off10",
        "ifg_offs",
        "ifg_sim_diff",
        "ifg_sim_unw",
        "ifg_sim_unw0",
        "ifg_sim_unw1",
        "ifg_sim_unw_ph",
        "ifg_unw",
        "ifg_unw_geocode_2pi_bmp",
        "ifg_unw_geocode_6pi_bmp",
        "ifg_unw_geocode_out",
        "ifg_unw_geocode_2pi_png",
        "ifg_unw_geocode_6pi_png",
        "ifg_unw_mask",
        "ifg_unw_model",
        "ifg_unw_thin",
        # vars for GeoTIFF outputs
        "ifg_unw_geocode_out_tiff",
        "ifg_flat_geocode_out_tiff",
        "ifg_filt_geocode_out_tiff",
        "ifg_flat_coh_geocode_out_tiff",
        "ifg_filt_coh_geocode_out_tiff",
        "shapefile",
    ]

    def __init__(self, proc, shapefile, master, slave, out_dir = None):
        self.shapefile = shapefile

        if not out_dir:
            out_dir = proc.proj_dir / proc.track

        out_dir = pathlib.Path(out_dir)

        self.ifg_dir = out_dir / proc.int_dir / "{}-{}".format(master, slave)
        self.master_dir = out_dir / proc.slc_dir / master
        self.slave_dir = out_dir / proc.slc_dir / slave

        self.r_master_slc_name = self.master_dir / "r{}_{}".format(
            master, proc.polarisation
        )

        self.r_master_slc = self.r_master_slc_name.with_suffix(".slc")
        self.r_master_slc_par = self.r_master_slc_name.with_suffix(".slc.par")

        self.r_master_mli_name = self.master_dir / "r{}_{}_{}rlks".format(
            master, proc.polarisation, proc.range_looks
        )
        self.r_master_mli = self.r_master_mli_name.with_suffix(".mli")
        self.r_master_mli_par = self.r_master_mli.with_suffix(".mli.par")

        self.r_slave_slc_name = self.slave_dir / "r{}_{}".format(slave, proc.polarisation)

        self.r_slave_slc = self.r_slave_slc_name.with_suffix(".slc")
        self.r_slave_slc_par = self.r_slave_slc.with_suffix(".slc.par")
        self.r_slave_mli_name = self.slave_dir / "r{}_{}_{}rlks".format(
            slave, proc.polarisation, proc.range_looks
        )
        self.r_slave_mli = self.r_slave_mli_name.with_suffix(".mli")
        self.r_slave_mli_par = self.r_slave_mli.with_suffix(".mli.par")

        # use intermed str as pathlib.Path doesn't handle filename concatenation
        _master_slave_name = "{}-{}_{}_{}rlks".format(
            master, slave, proc.polarisation, proc.range_looks
        )
        self.master_slave_name = self.ifg_dir / _master_slave_name

        self.ifg_base = self.ifg_dir / (_master_slave_name + "_base.par")
        self.ifg_base_init = pathlib.Path(_master_slave_name + "_base_init.par")
        self.ifg_base_res = pathlib.Path(_master_slave_name + "_base_res.par")
        self.ifg_base_temp = pathlib.Path(_master_slave_name + "_base_temp.par")
        self.ifg_bperp = pathlib.Path(_master_slave_name + "_bperp.par")

        self.ifg_ccp = pathlib.Path(_master_slave_name + ".ccp")
        self.ifg_coffs = pathlib.Path(_master_slave_name + ".coffs")
        self.ifg_coffsets = pathlib.Path(_master_slave_name + ".coffsets")
        self.ifg_diff_par = pathlib.Path(_master_slave_name + "_diff.par")

        self.ifg_filt = pathlib.Path(_master_slave_name + "_filt_int")
        self.ifg_filt_float = pathlib.Path(_master_slave_name + "_filt_int_flt")
        self.ifg_filt_geocode_bmp = pathlib.Path(_master_slave_name + "_filt_geo_int.bmp")
        self.ifg_filt_geocode_out = pathlib.Path(_master_slave_name + "_filt_geo_int")
        self.ifg_filt_geocode_png = pathlib.Path(_master_slave_name + "_filt_geo_int.png")
        self.ifg_filt_mask = pathlib.Path(_master_slave_name + "_filt_mask_int")
        self.ifg_filt_coh = pathlib.Path(_master_slave_name + "_filt_coh")
        self.ifg_filt_coh_geocode_bmp = pathlib.Path(
            _master_slave_name + "_filt_geo_coh.bmp"
        )
        self.ifg_filt_coh_geocode_out = pathlib.Path(_master_slave_name + "_filt_geo_coh")
        self.ifg_filt_coh_geocode_png = pathlib.Path(
            _master_slave_name + "_filt_geo_coh.png"
        )

        self.ifg_flat = pathlib.Path(_master_slave_name + "_flat_int")
        self.ifg_flat_float = pathlib.Path(_master_slave_name + "_flat_int_flt")
        self.ifg_flat_geocode_bmp = pathlib.Path(_master_slave_name + "_flat_geo_int.bmp")
        self.ifg_flat_geocode_out = pathlib.Path(_master_slave_name + "_flat_geo_int")
        self.ifg_flat_geocode_png = pathlib.Path(_master_slave_name + "_flat_geo_int.png")
        self.ifg_flat_temp = pathlib.Path(_master_slave_name + "_flat_temp_int")
        self.ifg_flat0 = pathlib.Path(_master_slave_name + "_flat0_int")
        self.ifg_flat1 = pathlib.Path(_master_slave_name + "_flat1_int")
        self.ifg_flat10 = pathlib.Path(_master_slave_name + "_flat10_int")
        self.ifg_flat_coh = pathlib.Path(_master_slave_name + "_flat_coh")
        self.ifg_flat_coh_geocode_bmp = pathlib.Path(
            _master_slave_name + "_flat_geo_coh.bmp"
        )
        self.ifg_flat_coh_geocode_out = pathlib.Path(_master_slave_name + "_flat_geo_coh")
        self.ifg_flat_coh_geocode_png = pathlib.Path(
            _master_slave_name + "_flat_geo_coh.png"
        )
        self.ifg_flat_coh0 = pathlib.Path(_master_slave_name + "_flat0_coh")
        self.ifg_flat_coh0_mask = pathlib.Path(_master_slave_name + "_flat0_coh_mask.ras")
        self.ifg_flat_coh10 = pathlib.Path(_master_slave_name + "_flat10_coh")
        self.ifg_flat_coh10_mask = pathlib.Path(_master_slave_name + "_flat10_coh_mask.ras")

        self.ifg_gcp = pathlib.Path(_master_slave_name + ".gcp")
        self.ifg_gcp_ph = pathlib.Path(_master_slave_name + ".gcp_ph")
        self.ifg_mask = pathlib.Path(_master_slave_name + "_mask.ras")
        self.ifg_mask_thin = pathlib.Path(_master_slave_name + "_mask_thin.ras")
        self.ifg_off = pathlib.Path(_master_slave_name + "_off.par")
        self.ifg_off10 = pathlib.Path(_master_slave_name + "_off10.par")
        self.ifg_offs = pathlib.Path(_master_slave_name + ".offs")

        self.ifg_sim_diff = pathlib.Path(_master_slave_name + "_sim_diff_unw")
        self.ifg_sim_unw = pathlib.Path(_master_slave_name + "_sim_unw")
        self.ifg_sim_unw0 = pathlib.Path(_master_slave_name + "_sim0_unw")
        self.ifg_sim_unw1 = pathlib.Path(_master_slave_name + "_sim1_unw")
        self.ifg_sim_unw_ph = pathlib.Path(_master_slave_name + "_sim_ph_unw")
        self.ifg_unw = pathlib.Path(_master_slave_name + "_unw")
        self.ifg_unw_geocode_2pi_bmp = pathlib.Path(_master_slave_name + "_geo_unw_2pi.bmp")
        self.ifg_unw_geocode_6pi_bmp = pathlib.Path(_master_slave_name + "_geo_unw_6pi.bmp")
        self.ifg_unw_geocode_out = pathlib.Path(_master_slave_name + "_geo_unw")
        self.ifg_unw_geocode_2pi_png = pathlib.Path(_master_slave_name + "_geo_unw_2pi.png")
        self.ifg_unw_geocode_6pi_png = pathlib.Path(_master_slave_name + "_geo_unw_6pi.png")
        self.ifg_unw_mask = pathlib.Path(_master_slave_name + "_mask_unw")
        self.ifg_unw_model = pathlib.Path(_master_slave_name + "_model_unw")
        self.ifg_unw_thin = pathlib.Path(_master_slave_name + "_thin_unw")

        self.ifg_unw_geocode_out_tiff = pathlib.Path(_master_slave_name + "_geo_unw.tif")
        self.ifg_flat_geocode_out_tiff = pathlib.Path(
            _master_slave_name + "_flat_geo_int.tif"
        )
        self.ifg_filt_geocode_out_tiff = pathlib.Path(
            _master_slave_name + "_filt_geo_int.tif"
        )
        self.ifg_flat_coh_geocode_out_tiff = pathlib.Path(
            _master_slave_name + "_flat_geo_coh.tif"
        )
        self.ifg_filt_coh_geocode_out_tiff = pathlib.Path(
            _master_slave_name + "_filt_geo_coh.tif"
        )


class Config:
    """Stores config for the Gamma InSAR workflow."""

    def __init__(self):
        self.proc_variables = None
        self.final_file_loc = None
        self.dem_master_names = None
        self.dem_file_names = None
        self.ifg_file_names = None
