#! /usr/bin/env python

import math
from typing import List, Tuple, Optional, Union
from pathlib import Path
import structlog
import py_gamma as pg

from insar.constant import MliFilenames
from insar.subprocess_utils import working_directory
from insar.logs import get_wrapped_logger

_LOG = structlog.get_logger("insar")


def calculate_slc_look_values(slc_par_file: Union[Path, str]) -> Tuple:
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


def calculate_mean_look_values(slc_par_files: List, multi_look: int) -> Tuple:
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
    slc: Union[Path, str],
    slc_par: Union[Path, str],
    rlks: int,
    alks: int,
    outdir: Optional[Path] = None,
) -> None:
    """Calculate a multi-look indensity (MLI) image from an SLC image.

    :param slc:
        A full path to SLC image file.
    :param slc_par:
        A full path to SLC image parameter file.
    :param rlks:
        Range look value.
    :param alks:
        Azimuth look value.
    :param outdir:
        An Optional path of an output director. Otherwise parent director
        of 'slc' file is default output directory.
    """

    slc = Path(slc)
    slc_par = Path(slc_par)

    try:
        scene_date, pol = slc.stem.split("_")
    except ValueError:
        err_msg = f"{slc.stem} needs to be in scene_date_polarization format"
        raise ValueError(err_msg)

    mli = MliFilenames.MLI_FILENAME.value.format(scene_date=scene_date, pol=pol, rlks=str(rlks))
    mli_par = MliFilenames.MLI_PAR_FILENAME.value.format(scene_date=scene_date, pol=pol, rlks=str(rlks))
    work_dir = slc.parent

    if outdir is not None:
        mli = outdir.joinpath(mli)
        mli_par = outdir.joinpath(mli_par)
        work_dir = outdir

    with working_directory(work_dir.as_posix()):
        # py_gamma parameters
        cout = []
        cerr = []
        slc_pathname = str(slc)
        slc_par_pathname = str(slc_par)
        mli_pathname = mli
        mli_par_pathname = mli_par
        azlks = alks
        loff = 0

        stat = pg.multi_look(
            slc_pathname,
            slc_par_pathname,
            mli_pathname,
            mli_par_pathname,
            rlks,
            azlks,
            loff,
            cout=cout,
            cerr=cerr,
            stdout_flag=False,
            stderr_flag=False
        )

        if stat != 0:
            msg = "failed to execute pg.multi_look"
            _LOG.error(
                msg,
                slc_pathname=slc_pathname,
                slc_par_pathname=slc_par_pathname,
                mli_pathname=mli_pathname,
                mli_par_pathname=mli_par_pathname,
                rlks=rlks,
                azlks=azlks,
                loff=loff,
                stat=stat,
                gamma_stdout=cout,
                gamma_stderr=cerr
            )
            raise Exception(msg)
