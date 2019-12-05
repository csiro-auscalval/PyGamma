#! /usr/bin/env python

import math
from typing import List, Tuple, Optional
from pathlib import Path
from python_scripts.subprocess_utils import run_command


def calculate_slc_look_values(slc_par_file: Path):
    """calculates the range and azimuth look values """
    with open(slc_par_file, 'r') as src:
        lines = src.readlines()
        for line in lines:
            if line.startswith("azimuth_pixel_spacing"):
                azsp = float(line.split()[1])
            if line.startswith("range_pixel_spacing"):
                rgsp = float(line.split()[1])
            if line.startswith("center_range_slc"):
                rg = float(line.split()[1])
            if line.startswith("sar_to_earth_center"):
                se = float(line.split()[1])
            if line.startswith("earth_radius_below_sensor"):
                re = float(line.split()[1])

        inc_a = (se**2 - re**2 - rg**2) / (2 * re * rg)

        if inc_a == 0.0:
            inc = math.atan(1.0) * 2.0
        elif -1.0 <= inc_a < 0.0:
            inc = math.atan(1.0) * 4.0 - math.atan(math.sqrt((1.0 / (inc_a**2)) - 1.0))
        elif 0.0 < inc_a <= 1.0:
            inc = math.atan(math.sqrt((1.0 / inc_a**2) - 1.0))
        else:
            raise ValueError("input out of range")

        return azsp, rgsp, inc


def caculate_mean_look_values(slc_par_files: List, multi_look: int) -> Tuple:
    """calculate mean slc look (range, azimuth, and incidence) angles from temporal stack"""

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


def multilook(slc: Path, slc_par: Path, rlks: int, alks: int, outdir: Optional[Path] = None):

    mli = '{}_{}rlks.mli'.format(slc.stem, str(rlks))
    mli_par = '{}.par'.format(mli)
    work_dir = slc.parent

    if outdir is not None:
        mli = outdir.joinpath(mli)
        mli_par = outdir.joinpath(mli_par)
        work_dir = outdir

    command = [
        "multi_look",
        slc.as_posix(),
        slc_par.as_posix(),
        mli,
        mli_par,
        str(rlks),
        str(alks),
        "0"
    ]

    run_command(command, work_dir.as_posix())
