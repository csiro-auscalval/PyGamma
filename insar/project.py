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

    def __init__(self, **kwargs):
        """
        Create a ProcConfig instance.
        :param kwargs: mapping of keywords and values from a proc config settings file.
        """
        for k, v in kwargs.items():
            # auto convert string paths to Paths to clean up workflow file handling
            if '_path' in k or '_dir' in k or '_img' in k:
                v = pathlib.Path(v)
            setattr(self, k, v)

        # prepare derived settings variables
        self.dem_img = pathlib.Path(self.master_dem_image) / "GAMMA_DEM_SRTM_1as_mosaic.img"
        self.proj_dir = pathlib.Path(self.nci_path) / self.project / self.sensor / "GAMMA"
        self.raw_data_track_dir = pathlib.Path(self.raw_data_dir) / self.track
        self.gamma_dem_dir = pathlib.Path(self.proj_dir) / "gamma_dem"
        self.results_dir = pathlib.Path(self.proj_dir) / self.track / "results"

        self.dem_noff1, self.dem_noff2 = self.dem_offset.split(" ")
        self.ifg_rpos = self.dem_rpos
        self.ifg_azpos = self.dem_azpos

    @classmethod
    def from_file(cls, file_obj):
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
        return ProcConfig(**cfg)


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
        "dem_master_gamma0_eqa",
        "dem_master_gamma0_eqa_bmp",
        "dem_master_gamma0_eqa_geo",
        "r_dem_master_slc_name",
        "r_dem_master_slc",
        "r_dem_master_slc_par",
        "r_dem_master_mli_name",
        "r_dem_master_mli",
        "r_dem_master_mli_par",
        "r_dem_master_mli_bmp",
    ]

    def __init__(self, proc=None):
        if proc:
            self.dem_master_dir = pathlib.Path(proc.slc_dir) / proc.ref_master_scene

            suffix = proc.ref_master_scene + "_" + proc.polarisation
            self.dem_master_slc_name = pathlib.Path(self.dem_master_dir) / suffix

            self.dem_master_slc = pathlib.Path(self.dem_master_dir) / (suffix + ".slc")
            self.dem_master_slc_par = pathlib.Path(self.dem_master_dir) / (suffix + ".slc.par")

            suffix_lks = proc.ref_master_scene + "_" + proc.polarisation + "_" + proc.range_looks + "rlks"
            self.dem_master_mli_name = pathlib.Path(self.dem_master_dir) / suffix_lks

            self.dem_master_mli = pathlib.Path(self.dem_master_dir) / (suffix_lks + ".mli")
            self.dem_master_mli_par = pathlib.Path(self.dem_master_dir) / (suffix_lks + ".mli.par")
            self.dem_master_gamma0 = pathlib.Path(self.dem_master_dir) / (suffix_lks + ".gamma0")
            self.dem_master_gamma0_bmp = pathlib.Path(self.dem_master_dir) / (suffix_lks + ".gamma0.bmp")

            self.dem_master_gamma0_eqa = pathlib.Path(self.dem_master_dir) / (suffix_lks + "_eqa.gamma0")
            self.dem_master_gamma0_eqa_bmp = pathlib.Path(self.dem_master_dir) / (suffix_lks + "_eqa.gamma0.bmp")
            self.dem_master_gamma0_eqa_geo = pathlib.Path(self.dem_master_dir) / (suffix_lks + "_eqa.gamma0.tif")

            suffix_slc = "r{}_{}".format(proc.ref_master_scene, proc.polarisation)
            self.r_dem_master_slc_name = pathlib.Path(self.dem_master_dir) / suffix_slc

            self.r_dem_master_slc = pathlib.Path(self.dem_master_dir) / (suffix_slc + ".slc")
            self.r_dem_master_slc_par = pathlib.Path(self.dem_master_dir) / (suffix_slc + ".slc.par")

            suffix_mli = "r{}_{}_{}rlks".format(proc.ref_master_scene, proc.polarisation, proc.range_looks)
            self.r_dem_master_mli_name = pathlib.Path(self.dem_master_dir) / suffix_mli

            self.r_dem_master_mli = pathlib.Path(self.dem_master_dir) / (suffix_mli + ".mli")
            self.r_dem_master_mli_par = pathlib.Path(self.dem_master_dir) / (suffix_mli + ".mli.par")
            self.r_dem_master_mli_bmp = pathlib.Path(self.dem_master_dir) / (suffix_mli + ".mli.bmp")


class DEMFileNames:
    __slots__ = [
        "dem",
        "dem_par",
        "dem_master_name",
        "dem_diff",
        "rdc_dem",
        "eqa_dem",
        "eqa_dem_par",
        "seamask",
        "dem_lt_rough",
        "dem_lt_fine",
        "dem_eqa_sim_sar",
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

    def __init__(self, proc):
        self.dem = os.path.join(proc.gamma_dem_dir, proc.dem_name + ".dem")
        self.dem_par = self.dem + ".par"
        self.dem_master_name = (
            os.path.join(proc.dem_dir, proc.ref_master_scene)
            + "_"
            + proc.polarisation
            + "_"
            + proc.range_looks
            + "rlks"
        )
        self.dem_diff = os.path.join(
            proc.dem_dir,
            "diff_{}_{}_{}rlks.par".format(
                proc.ref_master_scene, proc.polarisation, proc.range_looks
            ),
        )

        self.rdc_dem = self.dem_master_name + "_rdc.dem"
        self.eqa_dem = self.dem_master_name + "_eqa.dem"
        self.eqa_dem_par = self.eqa_dem + ".par"
        self.seamask = self.dem_master_name + "_eqa_seamask.tif"
        self.dem_lt_rough = self.dem_master_name + "_rough_eqa_to_rdc.lt"
        self.dem_lt_fine = self.dem_master_name + "_eqa_to_rdc.lt"
        self.dem_eqa_sim_sar = self.dem_master_name + "_eqa.sim"
        self.dem_rdc_sim_sar = self.dem_master_name + "_rdc.sim"
        self.dem_loc_inc = self.dem_master_name + "_eqa.linc"
        self.dem_rdc_inc = self.dem_master_name + "_rdc.linc"
        self.dem_lsmap = self.dem_master_name + "_eqa.lsmap"
        self.ellip_pix_sigma0 = self.dem_master_name + "_ellip_pix_sigma0"
        self.dem_pix_gam = self.dem_master_name + "_rdc_pix_gamma0"
        self.dem_pix_gam_bmp = self.dem_pix_gam + ".bmp"
        self.dem_off = self.dem_master_name + ".off"
        self.dem_offs = self.dem_master_name + ".offs"
        self.dem_ccp = self.dem_master_name + ".ccp"
        self.dem_offsets = self.dem_master_name + ".offsets"
        self.dem_coffs = self.dem_master_name + ".coffs"
        self.dem_coffsets = self.dem_master_name + ".coffsets"
        self.dem_lv_theta = self.dem_master_name + "_eqa.lv_theta"
        self.dem_lv_phi = self.dem_master_name + "_eqa.lv_phi"
        self.ext_image_flt = self.dem_master_name + "_ext_img_sar.flt"
        self.ext_image_init_sar = self.dem_master_name + "_ext_img_init.sar"
        self.ext_image_sar = self.dem_master_name + "_ext_img.sar"

        self.dem_check_file = os.path.join(
            proc.results_dir, proc.track + "_DEM_coreg_results"
        )
        self.lat_lon_pix = (
            os.path.join(proc.dem_dir, proc.track)
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
        "ifg_filt_cc",
        "ifg_filt_cc_geocode_bmp",
        "ifg_filt_cc_geocode_out",
        "ifg_filt_cc_geocode_png",
        "ifg_flat",
        "ifg_flat_float",
        "ifg_flat_geocode_bmp",
        "ifg_flat_geocode_out",
        "ifg_flat_geocode_png",
        "ifg_flat_temp",
        "ifg_flat0",
        "ifg_flat1",
        "ifg_flat10",
        "ifg_flat_cc",
        "ifg_flat_cc_geocode_bmp",
        "ifg_flat_cc_geocode_out",
        "ifg_flat_cc_geocode_png",
        "ifg_flat_cc0",
        "ifg_flat_cc0_mask",
        "ifg_flat_cc10",
        "ifg_flat_cc10_mask",
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
        "ifg_unw_geocode_bmp",
        "ifg_unw_geocode_out",
        "ifg_unw_geocode_png",
        "ifg_unw_mask",
        "ifg_unw_model",
        "ifg_unw_thin",
    ]

    def __init__(self, proc, master, slave):
        self.ifg_dir = os.path.join(proc.int_dir, "{}-{}".format(master, slave))
        self.master_dir = os.path.join(proc.slc_dir, master)
        self.slave_dir = os.path.join(proc.slc_dir, slave)

        self.r_master_slc_name = os.path.join(
            self.master_dir, "r{}_{}".format(master, proc.polarisation)
        )
        self.r_master_slc = self.r_master_slc_name + ".slc"
        self.r_master_slc_par = self.r_master_slc_name + ".par"

        self.r_master_mli_name = os.path.join(
            self.master_dir,
            "r{}_{}_{}rlks".format(master, proc.polarisation, proc.range_looks),
        )
        self.r_master_mli = self.r_master_mli_name + ".mli"
        self.r_master_mli_par = self.r_master_mli + ".par"

        self.r_slave_slc_name = os.path.join(
            self.slave_dir, "r{}_{}".format(slave, proc.polarisation)
        )
        self.r_slave_slc = self.r_slave_slc_name + ".slc"
        self.r_slave_slc_par = self.r_slave_slc + ".par"

        self.r_slave_mli_name = os.path.join(
            self.slave_dir,
            "r{}_{}_{}rlks".format(slave, proc.polarisation, proc.range_looks),
        )
        self.r_slave_mli = self.r_slave_mli_name + ".mli"
        self.r_slave_mli_par = self.r_slave_mli + ".par"
        self.master_slave_name = os.path.join(
            self.ifg_dir,
            "{}-{}_{}_{}rlks".format(master, slave, proc.polarisation, proc.range_looks),
        )
        self.ifg_base = self.master_slave_name + "_base.par"
        self.ifg_base_init = self.master_slave_name + "_base_init.par"
        self.ifg_base_res = self.master_slave_name + "_base_res.par"
        self.ifg_base_temp = self.master_slave_name + "_base_temp.par"
        self.ifg_bperp = self.master_slave_name + "_bperp.par"
        self.ifg_ccp = self.master_slave_name + ".ccp"
        self.ifg_coffs = self.master_slave_name + ".coffs"
        self.ifg_coffsets = self.master_slave_name + ".coffsets"
        self.ifg_diff_par = self.master_slave_name + "_diff.par"
        self.ifg_filt = self.master_slave_name + "_filt.int"
        self.ifg_filt_float = self.master_slave_name + "_filt_int.flt"
        self.ifg_filt_geocode_bmp = self.master_slave_name + "_filt_eqa_int.bmp"
        self.ifg_filt_geocode_out = self.master_slave_name + "_filt_eqa.int"
        self.ifg_filt_geocode_png = self.master_slave_name + "_filt_eqa_int.png"
        self.ifg_filt_mask = self.master_slave_name + "_filt_mask.int"
        self.ifg_filt_cc = self.master_slave_name + "_filt.cc"
        self.ifg_filt_cc_geocode_bmp = self.master_slave_name + "_filt_eqa_cc.bmp"
        self.ifg_filt_cc_geocode_out = self.master_slave_name + "_filt_eqa.cc"
        self.ifg_filt_cc_geocode_png = self.master_slave_name + "_filt_eqa_cc.png"
        self.ifg_flat = self.master_slave_name + "_flat.int"
        self.ifg_flat_float = self.master_slave_name + "_flat_int.flt"
        self.ifg_flat_geocode_bmp = self.master_slave_name + "_flat_eqa_int.bmp"
        self.ifg_flat_geocode_out = self.master_slave_name + "_flat_eqa.int"
        self.ifg_flat_geocode_png = self.master_slave_name + "_flat_eqa_int.png"
        self.ifg_flat_temp = self.master_slave_name + "_flat_temp.int"
        self.ifg_flat0 = self.master_slave_name + "_flat0.int"
        self.ifg_flat1 = self.master_slave_name + "_flat1.int"
        self.ifg_flat10 = self.master_slave_name + "_flat10.int"
        self.ifg_flat_cc = self.master_slave_name + "_flat.cc"
        self.ifg_flat_cc_geocode_bmp = self.master_slave_name + "_flat_eqa_cc.bmp"
        self.ifg_flat_cc_geocode_out = self.master_slave_name + "_flat_eqa.cc"
        self.ifg_flat_cc_geocode_png = self.master_slave_name + "_flat_eqa_cc.png"
        self.ifg_flat_cc0 = self.master_slave_name + "_flat0.cc"
        self.ifg_flat_cc0_mask = self.master_slave_name + "_flat0_cc_mask.ras"
        self.ifg_flat_cc10 = self.master_slave_name + "_flat10.cc"
        self.ifg_flat_cc10_mask = self.master_slave_name + "_flat10_cc_mask.ras"
        self.ifg_gcp = self.master_slave_name + ".gcp"
        self.ifg_gcp_ph = self.master_slave_name + ".gcp_ph"
        self.ifg_mask = self.master_slave_name + "_mask.ras"
        self.ifg_mask_thin = self.master_slave_name + "_mask_thin.ras"
        self.ifg_off = self.master_slave_name + "_off.par"
        self.ifg_off10 = self.master_slave_name + "_off10.par"
        self.ifg_offs = self.master_slave_name + ".offs"
        self.ifg_sim_diff = self.master_slave_name + "_sim_diff.unw"
        self.ifg_sim_unw = self.master_slave_name + "_sim.unw"
        self.ifg_sim_unw0 = self.master_slave_name + "_sim0.unw"
        self.ifg_sim_unw1 = self.master_slave_name + "_sim1.unw"
        self.ifg_sim_unw_ph = self.master_slave_name + "_sim_ph.unw"
        self.ifg_unw = self.master_slave_name + ".unw"
        self.ifg_unw_geocode_bmp = self.master_slave_name + "_eqa_unw.bmp"
        self.ifg_unw_geocode_out = self.master_slave_name + "_eqa.unw"
        self.ifg_unw_geocode_png = self.master_slave_name + "_eqa_unw.png"
        self.ifg_unw_mask = self.master_slave_name + "_mask.unw"
        self.ifg_unw_model = self.master_slave_name + "_model.unw"
        self.ifg_unw_thin = self.master_slave_name + "_thin.unw"


class Config:
    """Stores config for the Gamma InSAR workflow."""

    def __init__(self):
        self.proc_variables = None
        self.final_file_loc = None
        self.dem_master_names = None
        self.dem_file_names = None
        self.ifg_file_names = None
