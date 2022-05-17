"""
Utilities for managing Gamma settings for the InSAR ARD workflow.
"""

import string
import pathlib
import itertools
import enum
import numbers
from typing import Union

import insar.sensors.s1 as s1
import insar.sensors.rsat2 as rsat2
import insar.sensors.palsar as palsar
import insar.sensors.tsx as tsx


class ARDWorkflow(enum.Enum):
    """Defines all the supported workflows of the processing script"""

    Backscatter = 1, 'Produce all products up to (and including) SLC backscatter'
    Interferogram = 2, 'Product all products up to (and including) interferograms'
    BackscatterNRT = 3, 'Produce SLC and their backscatter, without coregistration'


class ProcConfig:
    """Container for Gamma proc files (collection of runtime settings)."""

    __path_attribs__ = [
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
        "gamma_dem_dir",
        "int_dir",
        "list_dir",
        "raw_data_dir",
        "gamma_dem_dir"
    ]

    __filename_attribs__ = [
        "database_path",
        "primary_dem_image",
        # FIXME: Implement this (GH issue #244)
        "scene_list",
        "secondary_list",
        "ifg_list",
        # FIXME: Implement this (GH issue #244)
        "remove_scene_list",
    ]

    # NB: use slots to prevent accidental addition of variables from typos
    __slots__ = [
        *__path_attribs__,
        *__subdir_attribs__,
        *__filename_attribs__,
        "stack_id",
        "track",
        "orbit",
        "land_center",
        "polarisation",
        "sensor",
        # TODO: In the future we may want to revise these into a single generic
        # "sensor_subtype" setting or something along those lines, IF we never
        # intend to support mixed-sensor stacks (if we do, keeping separate makes sense)
        "ers_sensor",
        "multi_look",
        "range_looks",
        "azimuth_looks",
        "process_method",
        "ref_primary_scene",
        "min_connect",
        "max_connect",
        "workflow",
        "cleanup",
        # TODO: This isn't used, but would be if we supported burst subsetting (GH issue #244)
        "s1_resize_ref_slc",
        # TODO: Implement these (GH issue #244)
        "dem_patch_window",
        "dem_rpos",
        "dem_azpos",
        "dem_offset",
        "dem_offset_measure",
        "dem_win",
        "dem_snr",
        "dem_rad_max",
        # FIXME: We have multiple cross-correlation thresholds with similar/ambiguous names
        # - these need addressing in the future (GH issue #326)
        "coreg_cc_thresh",
        "coreg_model_params",
        "coreg_window_size",
        "coreg_num_windows",
        "coreg_oversampling",
        "coreg_num_iterations",
        # FIXME: Should these be coreg_ as well?
        "secondary_offset_measure",
        # FIXME: do these really need to be identified w/ S1? (cc_thresh is common... other thresholds surely could be too?)
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
        # FIXME: Should this be implemented? (GH issue #244)
        "ifg_iterative",
        # FIXME: Should this be implemented? (GH issue #244)
        # (we use a hard-coded const.CROSS_CORRELATION_THRESHOLD currently)
        "ifg_thres",
        "ifg_init_win",
        # FIXME: Should this be implemented?  (GH issue #244) (hard-coded currently)
        "ifg_offset_win",
        "ifg_baseline_refinement",
        "num_linked_append_dates"
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

        # FIXME: Should be a setting
        self.gamma_dem_dir = "GAMMA_DEM"


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
        sensor_caps = {
            "S1": s1,
            "RSAT2": rsat2,
            "PALSAR1": palsar,
            "PALSAR2": palsar,
            "TSX": tsx  # NB: assumed to cover TDX as well
        }

        if hasattr(self, "sensor"):
            if self.sensor not in sensor_caps:
                msg += f"Unsupported sensor: {self.sensor}\n"

            caps = sensor_caps[self.sensor]

            # Validate polarisations
            # Note: currently this is just the 'primary' polarisation (used for IFGs)
            if hasattr(self, "polarisation"):
                if self.polarisation not in caps.POLARISATIONS:
                    msg += f"Invalid polarisation for {self.sensor}: {self.polarisation} (expected one of: {', '.join(caps.POLARISATIONS)})\n"

        if hasattr(self, "process_method"):
            if self.process_method != "sbas":
                msg += f"Attribute process_method must be sbas, not: {self.process_method} (currently only sbas is supported)\n"

        if hasattr(self, "workflow"):
            workflow_values = [o.name.lower() for o in ARDWorkflow]
            if self.workflow and self.workflow.lower() not in workflow_values:
                msg += f"Attribute workflow must be one of {'/'.join(workflow_values)}, not {self.workflow}\n"

        # Validate flag properties
        flag_values = ["YES", "NO", "ENABLE", "DISABLE", "TRUE", "FALSE"]
        flag_properties = ["cleanup", "ifg_unw_mask", "ifg_iterative", "ifg_geotiff"]
        for name in flag_properties:
            if hasattr(self, name):
                value = getattr(self, name)

                if value and value.upper() not in flag_values:
                    msg += f"Attribute {name} must be one of {'/'.join(flag_values)}, not {value}\n"

        # Validate date properties
        date_properties = ["ref_primary_scene", "s1_resize_ref_slc"]
        for name in date_properties:
            if hasattr(self, name):
                value = getattr(self, name)

                if value and value.lower() != "auto" and (value.isdigit() and len(value) == 8):
                    msg += f"Attribute {name} must be a YYYYMMDD date or 'auto', not {value}\n"

        # Validate IFG flags
        ifg_baseline_refinement_values = flag_values + [
            "OFF",
            "ON",
            "IF_ANY_NOT_PRECISE",
            "IF_BOTH_NOT_PRECISE",
            "IF_FIRST_NOT_PRECISE",
            "IF_SECOND_NOT_PRECISE"
        ]

        if hasattr(self, "ifg_baseline_refinement"):
            self.ifg_baseline_refinement = self.ifg_baseline_refinement.upper()

            if self.ifg_baseline_refinement not in ifg_baseline_refinement_values:
                msg += f"Attribute ifg_baseline_refinement must be one of {ifg_baseline_refinement_values}\n"

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


def is_flag_value_enabled(value: Union[str, bool]) -> bool:
    """
    Checks if a value (typically from a ProcConfig / .proc settings file) is an enabled/on flag, or not.

    :param value:
        The flag value being checked.
    :returns:
        True if the supplied value indicates the setting should be enabled, otherwise False.
    """

    # Falsey is disabled... (could be None or "" = no setting = off, or a boolean)
    if not value:
        return False

    on_values = ["yes", "enable", "true", "on"]
    off_values = ["no", "disable", "false", "off"]

    if str(value).lower() in off_values:
        return False

    if str(value).lower() in on_values:
        return True

    raise ValueError(f"Unsupported boolean settings flag: {value}")
