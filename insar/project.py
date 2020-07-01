"""
Utilities for managing Gamma settings for the InSAR ARD workflow.
"""

import os
from collections import namedtuple


class ProcConfig:
    """Container for Gamma proc files (collection of runtime settings)."""

    # NB: use slots to prevent accidental addition of variables from typos
    __slots__ = ['gamma_config',
                 'nci_path',
                 'envisat_orbits',
                 'ers_orbits',
                 's1_orbits',
                 's1_path',
                 'master_dem_image',
                 'slc_dir',
                 'dem_dir',
                 'int_dir',
                 'base_dir',
                 'list_dir',
                 'error_dir',
                 'pdf_dir',
                 'raw_data_dir',
                 'batch_job_dir',
                 'manual_job_dir',
                 'pre_proc_dir',
                 'scene_list',
                 'slave_list',
                 'ifg_list',
                 'frame_list',
                 's1_burst_list',
                 's1_download_list',
                 'remove_scene_list',
                 'project',
                 'track',
                 'dem_area',
                 'dem_name',
                 'mdss_data_dir',
                 'mdss_dem_tar',
                 'ext_image',
                 'polarisation',
                 'sensor',
                 'sensor_mode',
                 'ers_sensor',
                 'palsar2_type',
                 'multi_look',
                 'range_looks',
                 'azimuth_looks',
                 'process_method',
                 'ref_master_scene',
                 'min_connect',
                 'max_connect',
                 'post_process_method',
                 'extract_raw_data',
                 'do_slc',
                 'do_s1_resize',
                 's1_resize_ref_slc',
                 'do_s1_burst_subset',
                 'coregister_dem',
                 'use_ext_image',
                 'coregister_slaves',
                 'process_ifgs',
                 'ifg_geotiff',
                 'clean_up',
                 'dem_patch_window',
                 'dem_rpos',
                 'dem_azpos',
                 'dem_offset',
                 'dem_offset_measure',
                 'dem_win',
                 'dem_snr',
                 'dem_rad_max',
                 'coreg_cc_thresh',
                 'coreg_model_params',
                 'coreg_window_size',
                 'coreg_num_windows',
                 'coreg_oversampling',
                 'coreg_num_iterations',
                 'slave_offset_measure',
                 'slave_win',
                 'slave_cc_thresh',
                 'coreg_s1_cc_thresh',
                 'coreg_s1_frac_thresh',
                 'coreg_s1_stdev_thresh',
                 'ifg_begin',
                 'ifg_end',
                 'ifg_coherence_threshold',
                 'ifg_unw_mask',
                 'ifg_patches_range',
                 'ifg_patches_azimuth',
                 'ifg_ref_point_range',
                 'ifg_ref_point_azimuth',
                 'ifg_exponent',
                 'ifg_filtering_window',
                 'ifg_coherence_window',
                 'ifg_iterative',
                 'ifg_thres',
                 'ifg_init_win',
                 'ifg_offset_win',
                 'post_ifg_da_threshold',
                 'post_ifg_area_range',
                 'post_ifg_area_azimuth',
                 # 'post_ifg_area_range',
                 # 'post_ifg_area_azimuth',
                 'post_ifg_patches_range',
                 'post_ifg_patches_azimuth',
                 'post_ifg_overlap_range',
                 'post_ifg_overlap_azimuth',
                 'nci_project',
                 'min_jobs',
                 'max_jobs',
                 'pbs_run_loc',
                 'queue',
                 'exp_queue',
                 'mdss_queue',
                 'raw_walltime',
                 'raw_mem',
                 'raw_ncpus',
                 'create_dem_walltime',
                 'create_dem_mem',
                 'create_dem_ncpus',
                 'slc_walltime',
                 'slc_mem',
                 'slc_ncpus',
                 'calc_walltime',
                 'calc_mem',
                 'calc_ncpus',
                 'base_walltime',
                 'base_mem',
                 'base_ncpus',
                 'ml_walltime',
                 'ml_mem',
                 'ml_ncpus',
                 'resize_walltime',
                 'resize_mem',
                 'resize_ncpus',
                 'dem_walltime',
                 'dem_mem',
                 'dem_ncpus',
                 'pix_walltime',
                 'pix_mem',
                 'pix_ncpus',
                 'coreg_walltime',
                 'coreg_mem',
                 'coreg_ncpus',
                 'ifg_walltime',
                 'ifg_mem',
                 'ifg_ncpus',
                 'post_walltime',
                 'post_mem',
                 'post_ncpus',
                 'error_walltime',
                 'error_mem',
                 'error_ncpus',
                 'image_walltime',
                 'image_mem',
                 'image_ncpus',

                 # derived member vars
                 'dem_img',
                 'proj_dir',
                 'raw_data_track_dir',
                 'gamma_dem_dir',
                 'results_dir',
                 'dem_noff1',
                 'dem_noff2',
                 'ifg_rpos',
                 'ifg_azpos', ]

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

        # now prepare the derived settings variables
        self.dem_img = os.path.join(self.master_dem_image, 'GAMMA_DEM_SRTM_1as_mosaic.img')
        self.proj_dir = os.path.join(self.nci_path, self.project, self.sensor, "GAMMA")
        self.raw_data_track_dir = os.path.join(self.raw_data_dir, self.track)
        self.gamma_dem_dir = os.path.join(self.proj_dir, "gamma_dem")
        self.results_dir = os.path.join(self.proj_dir, self.track, "results")
        self.dem_noff1, self.dem_noff2 = self.dem_offset.split(' ')
        self.ifg_rpos = self.dem_rpos
        self.ifg_azpos = self.dem_azpos

    @classmethod
    def from_file(cls, file_obj):
        """
        Returns a ProcConfig instantiated from the given file like obj.

        :param file_obj: an open file like object
        :return: new ProcConfig object
        """
        raw_lines = [line.strip() for line in file_obj.readlines() if is_valid_config_line(line)]
        kv_pairs = [line.split('=') for line in raw_lines]

        # rename any keys with hyphens
        for pair in kv_pairs:
            pair[0] = pair[0].replace('-', '_')

        cfg = {e[0].strip().lower(): e[1].strip() for e in kv_pairs}
        return ProcConfig(**cfg)


def is_valid_config_line(line):
    """
    Test a line is a valid configuration entry: e.g. "setting=value"

    Assumes line has been stripped of whitespace.
    """
    if not line.startswith('#'):
        if '=' in line:
            return True
    return False


PBS_job_dirs = namedtuple('PBS_job_dirs', ['extract_raw_batch_dir',
                                           'slc_batch_dir',
                                           'ml_batch_dir',
                                           'base_batch_dir',
                                           'dem_batch_dir',
                                           'co_slc_batch_dir',
                                           'ifg_batch_dir',
                                           'extract_raw_manual_dir',
                                           'slc_manual_dir',
                                           'ml_manual_dir',
                                           'base_manual_dir',
                                           'dem_manual_dir',
                                           'co_slc_manual_dir',
                                           'ifg_manual_dir'])


def get_default_pbs_job_dirs(proc):
    """
    Return a PBS_job_dirs obj with the defaulted directory settings.

    :param proc: ProcConfig obj
    :return: default PBS_job_dirs obj
    """

    batch_dirs = ['extract_raw_jobs',
                  'slc_jobs',
                  'ml_slc_jobs',
                  'baseline_jobs',
                  'dem_jobs',
                  'coreg_slc_jobs',
                  'ifg_jobs']

    manual_dirs = ['extract_raw_jobs',
                   'slc_jobs',
                   'ml_slc_jobs',
                   'baseline_jobs',
                   'dem_jobs',
                   'coreg_slc_jobs',
                   'ifg_jobs']

    args = [os.path.join(proc.batch_job_dir, d) for d in batch_dirs]
    args.extend([os.path.join(proc.manual_job_dir, d) for d in manual_dirs])
    return PBS_job_dirs(*args)


Sentinel1_PBS_job_dirs = namedtuple('Sentinel1_PBS_job_dirs', ["resize_batch_dir",
                                                               "subset_batch_dir",
                                                               "resize_manual_dir",
                                                               "subset_manual_dir"])


def get_default_sentinel1_pbs_job_dirs(proc):
    batch_dirs = ["resize_S1_slc_jobs",
                  "subset_S1_slc_jobs"]

    manual_dirs = ["resize_S1_slc_jobs",
                   "subset_S1_slc_jobs"]

    args = [os.path.join(proc.batch_job_dir, d) for d in batch_dirs]
    args.extend([os.path.join(proc.manual_job_dir, d) for d in manual_dirs])
    return Sentinel1_PBS_job_dirs(*args)


class DEMMasterNames:
    __slots__ = ['dem_master_dir',
                 'dem_master_slc_name',
                 'dem_master_slc',
                 'dem_master_slc_par',
                 'dem_master_mli_name',
                 'dem_master_mli',
                 'dem_master_mli_par',
                 'dem_master_gamma0',
                 'dem_master_gamma0_bmp',
                 'dem_master_gamma0_eqa',
                 'dem_master_gamma0_eqa_bmp',
                 'dem_master_gamma0_eqa_geo',
                 'r_dem_master_slc_name',
                 'r_dem_master_slc',
                 'r_dem_master_slc_par',
                 'r_dem_master_mli_name',
                 'r_dem_master_mli',
                 'r_dem_master_mli_par',
                 'r_dem_master_mli_bmp']

    def __init__(self, proc=None):
        if proc:
            self.dem_master_dir = os.path.join(proc.slc_dir, proc.ref_master_scene)
            self.dem_master_slc_name = os.path.join(self.dem_master_dir,
                                                    proc.ref_master_scene + "_" + proc.polarisation)
            self.dem_master_slc = self.dem_master_slc_name + ".slc"
            self.dem_master_slc_par = self.dem_master_slc + ".par"

            self.dem_master_mli_name = os.path.join(self.dem_master_dir, proc.ref_master_scene
                                                    + "_" + proc.polarisation + "_"
                                                    + proc.range_looks + "rlks")
            self.dem_master_mli = self.dem_master_mli_name + ".mli"
            self.dem_master_mli_par = self.dem_master_mli + ".par"

            self.dem_master_gamma0 = self.dem_master_mli_name + ".gamma0"
            self.dem_master_gamma0_bmp = self.dem_master_gamma0 + ".bmp"
            self.dem_master_gamma0_eqa = self.dem_master_mli_name + "_eqa.gamma0"
            self.dem_master_gamma0_eqa_bmp = self.dem_master_gamma0_eqa + ".bmp"
            self.dem_master_gamma0_eqa_geo = self.dem_master_gamma0_eqa + ".tif"

            self.r_dem_master_slc_name = os.path.join(self.dem_master_dir, 'r' + proc.ref_master_scene) \
                + "_" + proc.polarisation

            self.r_dem_master_slc = self.r_dem_master_slc_name + ".slc"
            self.r_dem_master_slc_par = self.r_dem_master_slc + ".par"

            self.r_dem_master_mli_name = os.path.join(self.dem_master_dir, 'r' + proc.ref_master_scene) \
                + "_" + proc.polarisation \
                + "_" + proc.range_looks + "rlks"
            self.r_dem_master_mli = self.r_dem_master_mli_name + ".mli"
            self.r_dem_master_mli_par = self.r_dem_master_mli + ".par"
            self.r_dem_master_mli_bmp = self.r_dem_master_mli + ".bmp"


class DEMFileNames:

    __slots__ = ['dem',
                 'dem_par',
                 'dem_master_name',
                 'dem_diff',
                 'rdc_dem',
                 'eqa_dem',
                 'eqa_dem_par',
                 'seamask',
                 'dem_lt_rough',
                 'dem_lt_fine',
                 'dem_eqa_sim_sar',
                 'dem_rdc_sim_sar',
                 'dem_loc_inc',
                 'dem_rdc_inc',
                 'dem_lsmap',
                 'ellip_pix_sigma0',
                 'dem_pix_gam',
                 'dem_pix_gam_bmp',
                 'dem_off',
                 'dem_offs',
                 'dem_ccp',
                 'dem_offsets',
                 'dem_coffs',
                 'dem_coffsets',
                 'dem_lv_theta',
                 'dem_lv_phi',
                 'ext_image_flt',
                 'ext_image_init_sar',
                 'ext_image_sar',
                 'dem_check_file',
                 'lat_lon_pix']

    def __init__(self, proc):
        self.dem = os.path.join(proc.gamma_dem_dir, proc.dem_name + ".dem")
        self.dem_par = self.dem + ".par"
        self.dem_master_name = os.path.join(proc.dem_dir, proc.ref_master_scene) + "_" + proc.polarisation + "_" + proc.range_looks + "rlks"
        self.dem_diff = os.path.join(proc.dem_dir, "diff_{}_{}_{}rlks.par".format(proc.ref_master_scene,
                                                                                  proc.polarisation,
                                                                                  proc.range_looks))
        # following block is semi useless as it's testing string concatenation
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

        self.dem_check_file = os.path.join(proc.results_dir, proc.track + "_DEM_coreg_results")
        self.lat_lon_pix = os.path.join(proc.dem_dir, proc.track) + "_" + proc.range_looks + "rlks_sar_latlon.txt"


class Config:
    """Stores config for the Gamma InSAR workflow."""

    def __init__(self):
        self.proc_variables = None
        self.final_file_loc = None
        self.dem_master_names = None
        self.dem_file_names = None
        self.ifg_file_names = None
