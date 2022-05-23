#! /usr/bin/env python

import math
from typing import List, Tuple, Union
from pathlib import Path

from insar.project import ProcConfig
from insar.stack import load_stack_config
from insar.paths.slc import SlcPaths
from insar.subprocess_utils import working_directory

from insar.gamma.proxy import create_gamma_proxy


class MultilookException(Exception):
    pass


pg = create_gamma_proxy(MultilookException)


def calculate_slc_look_values(slc_par_file: Union[Path, str],) -> Tuple:
    """Calculates the range and azimuth look values."""

    _par_vals = pg.ParFile(Path(slc_par_file).as_posix())

    azsp = _par_vals.get_value("azimuth_pixel_spacing", dtype=float, index=0)
    rgsp = _par_vals.get_value("range_pixel_spacing", dtype=float, index=0)
    rg = _par_vals.get_value("center_range_slc", dtype=float, index=0)
    se = _par_vals.get_value("sar_to_earth_center", dtype=float, index=0)
    re = _par_vals.get_value("earth_radius_below_sensor", dtype=float, index=0)

    inc_a = (se ** 2 - re ** 2 - rg ** 2) / (2 * re * rg)
    inc = math.acos(inc_a)

    return azsp, rgsp, inc


def calculate_mean_look_values(slc_par_files: List, multi_look: int,) -> Tuple:
    """Calculate mean slc look (range, azimuth, and incidence) angles from a temporal stack.

    :param slc_par_files:
        A List of full paths of slc parameter files.
    :param multi_look:
        Multi-look value.

    :returns:
        Tuple of (range look, azimuth look, mean_grrgsp, mean_inc_deg)
    """

    total_azsp, total_rgsp, total_inc = 0.0, 0.0, 0.0
    multi_look = int(multi_look)

    for slc_par in slc_par_files:
        azsp, rgsp, inc = calculate_slc_look_values(slc_par)
        total_azsp += azsp
        total_rgsp += rgsp
        total_inc += inc

    mean_azsp = total_azsp / len(slc_par_files)
    mean_rgsp = total_rgsp / len(slc_par_files)
    mean_inc = total_inc / len(slc_par_files)

    mean_grrgsp = mean_rgsp / math.sin(mean_inc)
    mean_inc_deg = mean_inc * 180.0 / math.pi

    if mean_grrgsp > mean_azsp:
        az_ml_factor = round(mean_grrgsp / mean_azsp)
        rlks = multi_look
        alks = multi_look * az_ml_factor
        return rlks, alks, mean_azsp, mean_grrgsp, mean_inc_deg

    rg_ml_factor = round(mean_azsp / mean_grrgsp)
    rlks = multi_look * rg_ml_factor
    alks = multi_look
    return rlks, alks, mean_azsp, mean_grrgsp, mean_inc_deg


def multilook(
    stack_config: Union[ProcConfig, Path],
    slc: Union[Path, str],
    slc_par: Union[Path, str],
    rlks: int,
    alks: int
) -> None:
    """Calculate a multi-look indensity (MLI) image from an SLC image.

    The MLI file will be produced in the same directory as the provided SLC path.

    :param stack_config:
        The stack config (or path-like compatible with `load_stack_config`) for the stack which owns the provided slc files.
    :param slc:
        A full path to SLC image file.
    :param slc_par:
        A full path to SLC image parameter file.
    :param rlks:
        Range look value.
    :param alks:
        Azimuth look value.
    """

    if not isinstance(stack_config, ProcConfig):
        stack_config = load_stack_config(stack_config)

    # FIXME: when we clean up multilook code... this needs to go / be based on the insar.paths module
    # - we shouldn't be making assumptions about filenames / trying to extract dates.
    slc = Path(slc)
    slc_par = Path(slc_par)

    try:
        scene_date, pol = slc.stem.split("_")
    except ValueError:
        err_msg = f"{slc.stem} needs to be in scene_date_polarization format"
        raise ValueError(err_msg)

    paths = SlcPaths(stack_config, scene_date, pol, rlks)

    # Temporary, until we clean-up the multilook code to take more sensible inputs
    assert(slc == paths.slc)
    assert(slc_par == paths.slc_par)

    with working_directory(paths.dir.as_posix()):
        pg.multi_look(
            paths.slc,
            paths.slc_par,
            paths.mli,
            paths.mli_par,
            rlks,
            alks,
            0,  # No offset
        )
