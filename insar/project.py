"""
Utilities for managing Gamma settings for the InSAR ARD workflow.
"""

import string
import pathlib
import itertools
import enum
import numbers


class ARDWorkflow(enum.Enum):
    """Defines all the supported workflows of the processing script"""

    Backscatter = 1, 'Produce all products up to (and including) SLC backscatter'
    Interferogram = 2, 'Product all products up to (and including) interferograms'
    BackscatterNRT = 3, 'Produce SLC and their backscatter, without coregistration'


class ProcConfig:
    """Container for Gamma proc files (collection of runtime settings)."""

    __path_attribs__ = [
        "gamma_config",
        "nci_path",
        "output_path",
        "job_path",
        "envisat_orbits",
        "ers_orbits",
        "s1_orbits",
        "s1_path",
        "poeorb_path",
        "resorb_path"
    ]

    __subdir_attribs__ = [
        "slc_dir",
        "dem_dir",
        "int_dir",
        "base_dir",
        "list_dir",
        "error_dir",
        "raw_data_dir",
    ]

    __filename_attribs__ = [
        "database_path",
        "primary_dem_image",
        "scene_list",
        "secondary_list",
        "ifg_list",
        "frame_list",
        "s1_burst_list",
        "s1_download_list",
        "remove_scene_list",
    ]

    # NB: use slots to prevent accidental addition of variables from typos
    __slots__ = [
        *__path_attribs__,
        *__subdir_attribs__,
        *__filename_attribs__,
        "stack_id",
        "project",
        "track",
        "orbit",
        "land_center",
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
        "ref_primary_scene",
        "min_connect",
        "max_connect",
        "workflow",
        "cleanup",
        "s1_resize_ref_slc",
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
        "secondary_offset_measure",
        "secondary_win",
        "secondary_cc_thresh",
        "coreg_s1_cc_thresh",
        "coreg_s1_frac_thresh",
        "coreg_s1_stdev_thresh",
        "ifg_geotiff",
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
        # derived member vars
        "proj_dir",
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
            if "_path" in k or "_dir" in k or "_img" in k:
                v = pathlib.Path(v)
            setattr(self, k, v)

        # Convert settings to appropriate types
        if self.land_center:
            if isinstance(self.land_center, str):
                try:
                    self.land_center = self.land_center.strip("()[]").split(',')
                    self.land_center = tuple(float(i.strip()) for i in self.land_center)
                except:
                    raise ValueError(f"Could not parse .proc land_center: '{self.land_center}'")

            assert(len(self.land_center) == 2)
            assert(isinstance(self.land_center[0], numbers.Number))
            assert(isinstance(self.land_center[1], numbers.Number))

        # prepare derived settings variables

        # FIXME: proj_dir isn't used, nci_path isn't really NCI specific (and also unused), etc...
        # ^- there's quite a few .proc settings we can remove! A good linter will pick up on
        # these longer term when CI comes up..?
        self.proj_dir = pathlib.Path(self.nci_path) / self.project / self.sensor / "GAMMA"
        self.gamma_dem_dir = "gamma_dem"
        self.results_dir = "results"

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

    def validate(self) -> str:
        """
        Validates the .proc configuration file values provided.

        :return: A string describing what errors make the config invalid, will be falsy if valid.
        """
        msg = ""

        # Validate all attributes exist!
        for name in self.__slots__:
            if not hasattr(self, name) or getattr(self, name) is None:
                msg += f"Missing attribute: {name}\n"

        # Validate paths/subdirs/filenames confirm to allowed characters
        valid_path_chars = f"-_./ {string.ascii_letters}{string.digits}"
        for name in itertools.chain(self.__path_attribs__, self.__subdir_attribs__, self.__filename_attribs__):
            if not hasattr(self, name):
                continue

            pathname = str(getattr(self, name))
            validity_mask = [c in valid_path_chars for c in pathname]
            valid = all(validity_mask)

            if not valid:
                invalid_chars = [c for i,c in enumerate(pathname) if not validity_mask[i]]
                msg += f"Attribute {name} is not a valid path name: {pathname} (must not contain {invalid_chars})\n"

        # Validate sensor
        # TODO: When we add multiple sensor support (eg: radarsat 2) we will want to generalise this into a kind of
        # "capability" table somewhere that's re-used by the codebase.
        if hasattr(self, "sensor"):
            allowed_sensors = ["S1"]  # TODO: Add "RSAT2" when we support radarsat 2
            if self.sensor not in allowed_sensors:
                msg += f"Unsupported sensor: {self.sensor}\n"

            # Validate polarisations
            # Note: currently this is just the 'primary' polarisation (used for IFGs)
            if hasattr(self, "polarisation"):
                if self.sensor == "S1":
                    allowed_s1_pols = ["VV", "VH"]

                    if self.polarisation not in allowed_s1_pols:
                        msg += f"Invalid polarisation for S1: {self.polarisation} (expected one of: {', '.join(allowed_s1_pols)})"

        if hasattr(self, "process_method"):
            if self.process_method != "sbas":
                msg += f"Attribute process_method must be sbas, not: {self.process_method} (currently only sbas is supported)"

        if hasattr(self, "workflow"):
            workflow_values = [o.name.lower() for o in ARDWorkflow]
            if self.workflow and self.workflow.lower() not in workflow_values:
                msg += f"Attribute workflow must be one of {'/'.join(workflow_values)}, not {self.workflow}"

        # Validate flag properties
        flag_values = ["yes", "no", "enable", "disable", "true", "false"]
        flag_properties = ["cleanup", "ifg_unw_mask", "ifg_iterative", "ifg_geotiff"]
        for name in flag_properties:
            if hasattr(self, name):
                value = getattr(self, name)

                if value and value.lower() not in flag_values:
                    msg += f"Attribute {name} must be one of {'/'.join(flag_values)}, not {value}"

        # Validate date proeprties
        date_properties = ["ref_primary_scene", "s1_resize_ref_slc"]
        for name in date_properties:
            if hasattr(self, name):
                value = getattr(self, name)

                if value and value.lower() != "auto" and (value.isdigit() and len(value) == 8):
                    msg += f"Attribute {name} must be a YYYYMMDD date or 'auto', not {value}"

        # Note: In the future we may want to limit some of the numeric values, but for now we
        # simply let them remain as-is.
        #
        # At that stage we probably want a thirdparty data model validation solution, eg: marshmallow

        return msg

    def save(self, file_obj):
        for name in self.__slots__:
            val_str = ""

            if hasattr(self, name) and getattr(self, name):
                val_str = str(getattr(self, name))

            file_obj.write(f"{name.upper()}={val_str}\n")


def is_valid_config_line(line):
    """
    Test a line is a valid configuration entry: e.g. "setting=value"

    Assumes line has been stripped of whitespace.
    """
    if not line.startswith("#"):
        return "=" in line
    return False


class DEMPrimaryNames:
    __slots__ = [
        "dem_primary_dir",
        "dem_primary_slc_name",
        "dem_primary_slc",
        "dem_primary_slc_par",
        "dem_primary_mli_name",
        "dem_primary_mli",
        "dem_primary_mli_par",
        "dem_primary_gamma0",
        "dem_primary_gamma0_bmp",
        "dem_primary_gamma0_geo",
        "dem_primary_gamma0_geo_bmp",
        "dem_primary_gamma0_geo_geo",
        "r_dem_primary_slc_name",
        "r_dem_primary_slc",
        "r_dem_primary_slc_par",
        "r_dem_primary_mli_name",
        "r_dem_primary_mli",
        "r_dem_primary_mli_par",
        "r_dem_primary_mli_bmp",
    ]

    def __init__(self, proc=None, out_dir = None):
        if proc:
            if not out_dir:
                out_dir = proc.proj_dir / proc.track

            out_dir = pathlib.Path(out_dir)

            self.dem_primary_dir = out_dir / proc.slc_dir / proc.ref_primary_scene

            suffix = proc.ref_primary_scene + "_" + proc.polarisation
            self.dem_primary_slc_name = self.dem_primary_dir / suffix

            self.dem_primary_slc = self.dem_primary_dir / (suffix + ".slc")
            self.dem_primary_slc_par = self.dem_primary_dir / (
                suffix + ".slc.par"
            )

            suffix_lks = (
                proc.ref_primary_scene
                + "_"
                + proc.polarisation
                + "_"
                + proc.range_looks
                + "rlks"
            )
            self.dem_primary_mli_name = self.dem_primary_dir / suffix_lks

            self.dem_primary_mli = self.dem_primary_dir / (
                suffix_lks + ".mli"
            )
            self.dem_primary_mli_par = self.dem_primary_dir / (
                suffix_lks + ".mli.par"
            )
            self.dem_primary_gamma0 = self.dem_primary_dir / (
                suffix_lks + ".gamma0"
            )
            self.dem_primary_gamma0_bmp = self.dem_primary_dir / (
                suffix_lks + ".gamma0.bmp"
            )

            self.dem_primary_gamma0_geo = self.dem_primary_dir / (
                suffix_lks + "_geo.gamma0"
            )
            self.dem_primary_gamma0_geo_bmp = self.dem_primary_dir / (
                suffix_lks + "_geo.gamma0.bmp"
            )
            self.dem_primary_gamma0_geo_geo = self.dem_primary_dir / (
                suffix_lks + "_geo.gamma0.tif"
            )

            suffix_slc = "r{}_{}".format(proc.ref_primary_scene, proc.polarisation)
            self.r_dem_primary_slc_name = self.dem_primary_dir / suffix_slc

            self.r_dem_primary_slc = self.dem_primary_dir / (
                suffix_slc + ".slc"
            )
            self.r_dem_primary_slc_par = self.dem_primary_dir / (
                suffix_slc + ".slc.par"
            )

            suffix_mli = "r{}_{}_{}rlks".format(
                proc.ref_primary_scene, proc.polarisation, proc.range_looks
            )
            self.r_dem_primary_mli_name = self.dem_primary_dir / suffix_mli

            self.r_dem_primary_mli = self.dem_primary_dir / (
                suffix_mli + ".mli"
            )
            self.r_dem_primary_mli_par = self.dem_primary_dir / (
                suffix_mli + ".mli.par"
            )
            self.r_dem_primary_mli_bmp = self.dem_primary_dir / (
                suffix_mli + ".mli.bmp"
            )


class DEMFileNames:
    __slots__ = [
        "dem",
        "dem_par",
        "dem_primary_name",
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
        self.dem_primary_name = "{}_{}_{}rlks".format(
            proc.ref_primary_scene, proc.polarisation, proc.range_looks
        )
        self.dem_primary_name = out_dir / proc.dem_dir / self.dem_primary_name
        dmn = self.dem_primary_name

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
        "primary_dir",
        "secondary_dir",
        "r_primary_slc_name",
        "r_primary_slc",
        "r_primary_slc_par",
        "r_primary_mli_name",
        "r_primary_mli",
        "r_primary_mli_par",
        "r_secondary_slc_name",
        "r_secondary_slc",
        "r_secondary_slc_par",
        "r_secondary_mli_name",
        "r_secondary_mli",
        "r_secondary_mli_par",
        "primary_secondary_name",
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
    ]

    def __init__(self, proc, primary, secondary, out_dir = None):
        if not out_dir:
            out_dir = proc.proj_dir / proc.track

        out_dir = pathlib.Path(out_dir)

        self.ifg_dir = out_dir / proc.int_dir / "{}-{}".format(primary, secondary)
        self.primary_dir = out_dir / proc.slc_dir / primary
        self.secondary_dir = out_dir / proc.slc_dir / secondary

        self.r_primary_slc_name = self.primary_dir / "r{}_{}".format(
            primary, proc.polarisation
        )

        self.r_primary_slc = self.r_primary_slc_name.with_suffix(".slc")
        self.r_primary_slc_par = self.r_primary_slc_name.with_suffix(".slc.par")

        self.r_primary_mli_name = self.primary_dir / "r{}_{}_{}rlks".format(
            primary, proc.polarisation, proc.range_looks
        )
        self.r_primary_mli = self.r_primary_mli_name.with_suffix(".mli")
        self.r_primary_mli_par = self.r_primary_mli.with_suffix(".mli.par")

        self.r_secondary_slc_name = self.secondary_dir / "r{}_{}".format(secondary, proc.polarisation)

        self.r_secondary_slc = self.r_secondary_slc_name.with_suffix(".slc")
        self.r_secondary_slc_par = self.r_secondary_slc.with_suffix(".slc.par")
        self.r_secondary_mli_name = self.secondary_dir / "r{}_{}_{}rlks".format(
            secondary, proc.polarisation, proc.range_looks
        )
        self.r_secondary_mli = self.r_secondary_mli_name.with_suffix(".mli")
        self.r_secondary_mli_par = self.r_secondary_mli.with_suffix(".mli.par")

        # use intermed str as pathlib.Path doesn't handle filename concatenation
        _primary_secondary_name = "{}-{}_{}_{}rlks".format(
            primary, secondary, proc.polarisation, proc.range_looks
        )
        self.primary_secondary_name = self.ifg_dir / _primary_secondary_name

        self.ifg_base = self.ifg_dir / (_primary_secondary_name + "_base.par")
        self.ifg_base_init = pathlib.Path(_primary_secondary_name + "_base_init.par")
        self.ifg_base_res = pathlib.Path(_primary_secondary_name + "_base_res.par")
        self.ifg_base_temp = pathlib.Path(_primary_secondary_name + "_base_temp.par")
        self.ifg_bperp = pathlib.Path(_primary_secondary_name + "_bperp.par")

        self.ifg_ccp = pathlib.Path(_primary_secondary_name + ".ccp")
        self.ifg_coffs = pathlib.Path(_primary_secondary_name + ".coffs")
        self.ifg_coffsets = pathlib.Path(_primary_secondary_name + ".coffsets")
        self.ifg_diff_par = pathlib.Path(_primary_secondary_name + "_diff.par")

        self.ifg_filt = pathlib.Path(_primary_secondary_name + "_filt_int")
        self.ifg_filt_float = pathlib.Path(_primary_secondary_name + "_filt_int_flt")
        self.ifg_filt_geocode_bmp = pathlib.Path(_primary_secondary_name + "_filt_geo_int.bmp")
        self.ifg_filt_geocode_out = pathlib.Path(_primary_secondary_name + "_filt_geo_int")
        self.ifg_filt_geocode_png = pathlib.Path(_primary_secondary_name + "_filt_geo_int.png")
        self.ifg_filt_mask = pathlib.Path(_primary_secondary_name + "_filt_mask_int")
        self.ifg_filt_coh = pathlib.Path(_primary_secondary_name + "_filt_coh")
        self.ifg_filt_coh_geocode_bmp = pathlib.Path(
            _primary_secondary_name + "_filt_geo_coh.bmp"
        )
        self.ifg_filt_coh_geocode_out = pathlib.Path(_primary_secondary_name + "_filt_geo_coh")
        self.ifg_filt_coh_geocode_png = pathlib.Path(
            _primary_secondary_name + "_filt_geo_coh.png"
        )

        self.ifg_flat = pathlib.Path(_primary_secondary_name + "_flat_int")
        self.ifg_flat_float = pathlib.Path(_primary_secondary_name + "_flat_int_flt")
        self.ifg_flat_geocode_bmp = pathlib.Path(_primary_secondary_name + "_flat_geo_int.bmp")
        self.ifg_flat_geocode_out = pathlib.Path(_primary_secondary_name + "_flat_geo_int")
        self.ifg_flat_geocode_png = pathlib.Path(_primary_secondary_name + "_flat_geo_int.png")
        self.ifg_flat_temp = pathlib.Path(_primary_secondary_name + "_flat_temp_int")
        self.ifg_flat0 = pathlib.Path(_primary_secondary_name + "_flat0_int")
        self.ifg_flat1 = pathlib.Path(_primary_secondary_name + "_flat1_int")
        self.ifg_flat10 = pathlib.Path(_primary_secondary_name + "_flat10_int")
        self.ifg_flat_coh = pathlib.Path(_primary_secondary_name + "_flat_coh")
        self.ifg_flat_coh_geocode_bmp = pathlib.Path(
            _primary_secondary_name + "_flat_geo_coh.bmp"
        )
        self.ifg_flat_coh_geocode_out = pathlib.Path(_primary_secondary_name + "_flat_geo_coh")
        self.ifg_flat_coh_geocode_png = pathlib.Path(
            _primary_secondary_name + "_flat_geo_coh.png"
        )
        self.ifg_flat_coh0 = pathlib.Path(_primary_secondary_name + "_flat0_coh")
        self.ifg_flat_coh0_mask = pathlib.Path(_primary_secondary_name + "_flat0_coh_mask.ras")
        self.ifg_flat_coh10 = pathlib.Path(_primary_secondary_name + "_flat10_coh")
        self.ifg_flat_coh10_mask = pathlib.Path(_primary_secondary_name + "_flat10_coh_mask.ras")

        self.ifg_gcp = pathlib.Path(_primary_secondary_name + ".gcp")
        self.ifg_gcp_ph = pathlib.Path(_primary_secondary_name + ".gcp_ph")
        self.ifg_mask = pathlib.Path(_primary_secondary_name + "_mask.ras")
        self.ifg_mask_thin = pathlib.Path(_primary_secondary_name + "_mask_thin.ras")
        self.ifg_off = pathlib.Path(_primary_secondary_name + "_off.par")
        self.ifg_off10 = pathlib.Path(_primary_secondary_name + "_off10.par")
        self.ifg_offs = pathlib.Path(_primary_secondary_name + ".offs")

        self.ifg_sim_diff = pathlib.Path(_primary_secondary_name + "_sim_diff_unw")
        self.ifg_sim_unw = pathlib.Path(_primary_secondary_name + "_sim_unw")
        self.ifg_sim_unw0 = pathlib.Path(_primary_secondary_name + "_sim0_unw")
        self.ifg_sim_unw1 = pathlib.Path(_primary_secondary_name + "_sim1_unw")
        self.ifg_sim_unw_ph = pathlib.Path(_primary_secondary_name + "_sim_ph_unw")
        self.ifg_unw = pathlib.Path(_primary_secondary_name + "_unw")
        self.ifg_unw_geocode_2pi_bmp = pathlib.Path(_primary_secondary_name + "_geo_unw_2pi.bmp")
        self.ifg_unw_geocode_6pi_bmp = pathlib.Path(_primary_secondary_name + "_geo_unw_6pi.bmp")
        self.ifg_unw_geocode_out = pathlib.Path(_primary_secondary_name + "_geo_unw")
        self.ifg_unw_geocode_2pi_png = pathlib.Path(_primary_secondary_name + "_geo_unw_2pi.png")
        self.ifg_unw_geocode_6pi_png = pathlib.Path(_primary_secondary_name + "_geo_unw_6pi.png")
        self.ifg_unw_mask = pathlib.Path(_primary_secondary_name + "_mask_unw")
        self.ifg_unw_model = pathlib.Path(_primary_secondary_name + "_model_unw")
        self.ifg_unw_thin = pathlib.Path(_primary_secondary_name + "_thin_unw")

        self.ifg_unw_geocode_out_tiff = pathlib.Path(_primary_secondary_name + "_geo_unw.tif")
        self.ifg_flat_geocode_out_tiff = pathlib.Path(
            _primary_secondary_name + "_flat_geo_int.tif"
        )
        self.ifg_filt_geocode_out_tiff = pathlib.Path(
            _primary_secondary_name + "_filt_geo_int.tif"
        )
        self.ifg_flat_coh_geocode_out_tiff = pathlib.Path(
            _primary_secondary_name + "_flat_geo_coh.tif"
        )
        self.ifg_filt_coh_geocode_out_tiff = pathlib.Path(
            _primary_secondary_name + "_filt_geo_coh.tif"
        )


class Config:
    """Stores config for the Gamma InSAR workflow."""

    def __init__(self):
        self.proc_variables = None
        self.final_file_loc = None
        self.dem_primary_names = None
        self.dem_file_names = None
        self.ifg_file_names = None
