#!/usr/bin/env python

import datetime
from insar.constant import SCENE_DATE_FMT
from pathlib import Path
import geopandas
import tempfile
import os
from typing import Tuple, Optional, List

import insar.constant as const
from insar.subprocess_utils import run_command


def rm_file(path):
    '''A hacky unlink/delete file function for Python <3.8 which lacks a missing_ok parameter in Path.unlink'''
    path = Path(path)

    if path.exists():
        path.unlink()


def parse_date(scene_name):
    """ Parse str scene_name into datetime object. """
    return datetime.datetime.strptime(scene_name, SCENE_DATE_FMT)


def read_land_center_coords(shapefile: Path):
    """
    Reads the land center coordinates from a shapefile, if any exists.

    :param shapefie: the path to the shape file for the scene
    :return (latitude, longitude) coordinates
    """

    # Load the land center from shape file
    dbf = geopandas.GeoDataFrame.from_file(shapefile.with_suffix(".dbf"))

    north_lat, east_lon = None, None

    if hasattr(dbf, "land_cen_l") and hasattr(dbf, "land_cen_1"):
        # Note: land center is duplicated for every burst,
        # we just take the first value since they're all the same
        north_lat = dbf.land_cen_l[0]
        east_lon = dbf.land_cen_1[0]

        # "0" values are interpreted as "no value" / None
        north_lat = None if north_lat == "0" else north_lat
        east_lon = None if east_lon == "0" else east_lon

    # We return None if we don't have both values, doesn't make much
    # sense to try and support land columns/rows, we need an exact pixel.
    if north_lat is None or east_lon is None:
        return None

    return (north_lat, east_lon)

def latlon_to_px(pg, mli_par: Path, lat, lon):
    """
    Reads the land center coordinates from a shapefile and converts it into pixel coordinates for a multilook image

    :param pg: the PyGamma wrapper object used to dispatch gamma commands
    :param mli_par: the path to the .mli.par file in which the pixel coordinates should be for
    :param lat: The latitude coordinate
    :param lon: The longitude coordinate
    :return (range/altitude, line/azimuth) pixel coordinates
    """

    # Convert lat/long to pixel coords
    _, cout, _ = pg.coord_to_sarpix(
        mli_par,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        lat,
        lon,
        const.NOT_PROVIDED,  # hgt
    )

    # Extract pixel coordinates from stdout
    # Example: SLC/MLI range, azimuth pixel (int):         7340        17060
    matched = [i for i in cout if i.startswith("SLC/MLI range, azimuth pixel (int):")]
    if len(matched) != 1:
        error_msg = "Failed to convert scene land center from lat/lon into pixel coordinates!"
        raise Exception(error_msg)

    rpos, azpos = matched[0].split()[-2:]
    return (int(rpos), int(azpos))


def create_diff_par(
    first_par_path: Path,
    second_par_path: Optional[Path],
    diff_par_path: Path,
    offset: Optional[Tuple[int, int]],
    num_measurements: Optional[Tuple[int, int]],
    window_sizes: Optional[Tuple[int, int]],
    cc_thresh: Optional[float]
) -> None:
    """
    This is a wrapper around the GAMMA `create_diff_par` program.

    The wrapper exists as unlike most GAMMA programs `create_diff_par` cannot
    actually be given all of it's settings via command line arguments, instead
    it relies on an 'interactive' mode where it takes a sequence of settings
    via the terminal's standard input (which this function constructs as a temp
    file, and pipes into it so we can treat it like a non-interactive function)

    `create_diff_par --help`:
    Create DIFF/GEO parameter file for geocoding and differential interferometry.

    All optional parameters will defer to GAMMA's defaults if set to `None`.

    This is an initial stage in coregistration that kicks off the offset model
    refinement stage.  At a high level it makes a few measurements at regular
    locations across both images, and correlates them to determine an initial
    set of polynomials from which the offset model is initalised.

    :param first_par_path:
        (input) image parameter file 1 (see PAR_type option)
    :param second_par_path:
        (input) image parameter file 2 (or - if not provided)
    :param diff_par_path:
        (input/output) DIFF/GEO parameter file
    :param offset:
        The known pixel offset estimate between first_par_path and second_par_path.
    :param num_measurements:
        The number of measurements to make along each axis.
    :param window_sizes:
        The window sizes (in pixels) of measurements being made.
    :param cc_thresh:
        The cross correlation threshold that must be met by measurements
        to be included in the resulting diff.
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        return_file = Path(temp_dir) / "returns"

        with return_file.open("w") as fid:
            fid.write("\n")

            for pair_param in [offset, num_measurements, window_sizes]:
                if pair_param:
                    fid.write("{} {}\n".format(*pair_param))
                else:
                    fid.write("\n")

            if cc_thresh is not None:
                fid.write("{}".format(cc_thresh))
            else:
                fid.write("\n")

        command = [
            "create_diff_par",
            str(first_par_path),
            str(second_par_path or const.NOT_PROVIDED),
            str(diff_par_path),
            "1", # SLC/MLI_par input types
            "<",
            return_file.as_posix(),
        ]
        run_command(command, os.getcwd())


def grep_stdout(std_output: List[str], match_start_string: str) -> str:
    """
    A helper method to return matched string from std_out.

    :param std_output:
        A list containing the std output collected by py_gamma.
    :param match_start_string:
        A case sensitive string to be scanned in stdout.

    :returns:
        A full string line of the matched string.
    """
    for line in std_output:
        if line.startswith(match_start_string):
            return line
