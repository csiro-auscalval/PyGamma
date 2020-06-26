"""
Utilities for managing Gamma settings for the InSAR ARD workflow.
"""


class ProcConfig:
    """Container for Gamma proc files (collection of runtime settings)."""

    def __init__(self, **kwargs):
        self.gamma_config = None
        self.nci_path = None
        self.envisat_orbits = None
        self.ers_orbits = None
        self.s1_orbits = None
        self.s1_path = None
        self.master_dem_image = None
        self.slc_dir = None
        self.dem_dir = None
        self.int_dir = None
        self.base_dir = None
        self.list_dir = None
        self.error_dir = None
        self.pdf_dir = None
        self.raw_data_dir = None
        self.batch_job_dir = None
        self.manual_job_dir = None
        self.pre_proc_dir = None
        self.scene_list = None
        self.slave_list = None
        self.ifg_list = None
        self.frame_list = None
        self.s1_burst_list = None
        self.s1_download_list = None
        self.remove_scene_list = None
        self.project = None
        self.track = None
        self.dem_area = None
        self.dem_name = None
        self.mdss_data_dir = None
        self.mdss_dem_tar = None
        self.ext_image = None
        self.polarisation = None
        self.sensor = None
        self.sensor_mode = None
        self.ers_sensor = None
        self.palsar2_type = None
        self.multi_look = None
        self.range_looks = None
        self.azimuth_looks = None
        self.process_method = None
        self.ref_master_scene = None
        self.min_connect = None
        self.max_connect = None
        self.post_process_method = None
        self.extract_raw_data = None
        self.do_slc = None
        self.do_s1_resize = None
        self.s1_resize_ref_slc = None
        self.do_s1_burst_subset = None
        self.coregister_dem = None
        self.use_ext_image = None
        self.coregister_slaves = None
        self.process_ifgs = None
        self.ifg_geotiff = None
        self.clean_up = None
        self.dem_patch_window = None
        self.dem_rpos = None
        self.dem_azpos = None
        self.dem_offset = None
        self.dem_offset_measure = None
        self.dem_win = None
        self.dem_snr = None
        self.dem_rad_max = None
        self.coreg_cc_thresh = None
        self.coreg_model_params = None
        self.coreg_window_size = None
        self.coreg_num_windows = None
        self.coreg_oversampling = None
        self.coreg_num_iterations = None
        self.slave_offset_measure = None
        self.slave_win = None
        self.slave_cc_thresh = None
        self.coreg_s1_cc_thresh = None
        self.coreg_s1_frac_thresh = None
        self.coreg_s1_stdev_thresh = None
        self.ifg_begin = None
        self.ifg_end = None
        self.ifg_coherence_threshold = None
        self.ifg_unw_mask = None
        self.ifg_patches_range = None
        self.ifg_patches_azimuth = None
        self.ifg_ref_point_range = None
        self.ifg_ref_point_azimuth = None
        self.ifg_exponent = None
        self.ifg_filtering_window = None
        self.ifg_coherence_window = None
        self.ifg_iterative = None
        self.ifg_thres = None
        self.ifg_init_win = None
        self.ifg_offset_win = None
        self.post_ifg_da_threshold = None
        self.post_ifg_area_range = None
        self.post_ifg_area_azimuth = None
        # self.post_ifg_area_range = None
        # self.post_ifg_area_azimuth = None
        self.post_ifg_patches_range = None
        self.post_ifg_patches_azimuth = None
        self.post_ifg_overlap_range = None
        self.post_ifg_overlap_azimuth = None
        self.nci_project = None
        self.min_jobs = None
        self.max_jobs = None
        self.pbs_run_loc = None
        self.queue = None
        self.exp_queue = None
        self.mdss_queue = None
        self.raw_walltime = None
        self.raw_mem = None
        self.raw_ncpus = None
        self.create_dem_walltime = None
        self.create_dem_mem = None
        self.create_dem_ncpus = None
        self.slc_walltime = None
        self.slc_mem = None
        self.slc_ncpus = None
        self.calc_walltime = None
        self.calc_mem = None
        self.calc_ncpus = None
        self.base_walltime = None
        self.base_mem = None
        self.base_ncpus = None
        self.ml_walltime = None
        self.ml_mem = None
        self.ml_ncpus = None
        self.resize_walltime = None
        self.resize_mem = None
        self.resize_ncpus = None
        self.dem_walltime = None
        self.dem_mem = None
        self.dem_ncpus = None
        self.pix_walltime = None
        self.pix_mem = None
        self.pix_ncpus = None
        self.coreg_walltime = None
        self.coreg_mem = None
        self.coreg_ncpus = None
        self.ifg_walltime = None
        self.ifg_mem = None
        self.ifg_ncpus = None
        self.post_walltime = None
        self.post_mem = None
        self.post_ncpus = None
        self.error_walltime = None
        self.error_mem = None
        self.error_ncpus = None
        self.image_walltime = None
        self.image_mem = None
        self.image_ncpus = None

        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                raise AttributeError(k)

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


class Config:
    """Stores config for the Gamma InSAR workflow."""

    def __init__(self):
        self.proc_variables = None
        self.final_file_loc = None
        self.dem_master_names = None
        self.dem_file_names = None
        self.ifg_file_names = None
