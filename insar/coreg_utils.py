import datetime
from insar.constant import SCENE_DATE_FMT
from pathlib import Path
import geopandas
import tempfile
import os
from typing import Tuple, Optional, List

import insar.constant as const
from insar.project import ProcConfig
from insar.subprocess_utils import run_command


def rm_file(path):
    """
    A hacky unlink/delete file function for Python <3.8.

    The pathlib module <3.8 lacks a missing_ok parameter in Path.unlink().
    """
    path = Path(path)

    if path.exists():
        path.unlink()


def parse_date(scene_name):
    """ Parse str scene_name into datetime object. """
    return datetime.datetime.strptime(scene_name, SCENE_DATE_FMT)


def read_land_center_coords(shapefile: Path):
    """
    Reads the land center coordinates from a shapefile, if any exists.

    :param shapefile: the path to the shape file for the scene
    :return (latitude, longitude) coordinates
    """

    path = shapefile.with_suffix(".dbf")

    if not path.exists():
        raise FileNotFoundError(path)

    # Load the land center from shape file
    dbf = geopandas.GeoDataFrame.from_file(path)

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

    return north_lat, east_lon


def latlon_to_px(pg, mli_par: Path, lat, lon):
    """
    Reads land center coordinates from a shapefile and converts into pixel coordinates for a multilook image

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
    return int(rpos), int(azpos)


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
    set of polynomials from which the offset model is initialised.

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
            "1",  # SLC/MLI_par input types
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


def standardise_to_date(dt):
    if isinstance(dt, datetime.datetime):
        return dt.date()
    elif isinstance(dt, str):
        return datetime.datetime.strptime(dt, SCENE_DATE_FMT).date()
    elif isinstance(dt, datetime.date):
        return dt

    raise NotImplementedError("Unsupported date type")


def load_coreg_tree(proc_config: ProcConfig) -> List[List[Tuple[str,str]]]:
    list_dir = proc_config.output_path / proc_config.list_dir
    result = []

    coreg_id = "secondaries"

    idx = 1
    scene_file = Path(list_dir / f"{coreg_id}1.list")

    # Support older naming convention for existing stacks
    if not scene_file.exists():
        coreg_id = "slaves"
        scene_file = Path(list_dir / f"{coreg_id}1.list")

    while scene_file.exists():
        scenes = scene_file.read_text().strip().splitlines()
        scenes = [standardise_to_date(i) for i in scenes]
        result.append(scenes)

        idx += 1
        scene_file = Path(list_dir / f"{coreg_id}{idx}.list")

    return result


def find_scenes_in_range(
    primary_dt, date_list, thres_days: int, include_closest: bool = True
):
    """
    Creates a list of frame dates that within range of a primary date.

    :param primary_dt:
        The primary date in which we are searching for scenes relative to.
    :param date_list:
        The list which we're searching for dates in.
    :param thres_days:
        The number of days threshold in which scenes must be within relative to
        the primary date.
    :param include_closest:
        When true - if there exist slc frames on either side of the primary date, which are NOT
        within the threshold window then the closest date from each side will be
        used instead of no scene at all.
    """

    # We do everything with datetime.date's (can't mix and match date vs. datetime)
    if isinstance(primary_dt, datetime.datetime):
        primary_dt = primary_dt.date()
    elif not isinstance(primary_dt, datetime.date):
        primary_dt = datetime.date(primary_dt)

    thresh_dt = datetime.timedelta(days=thres_days)
    tree_lhs = []  # This was the 'lower' side in the bash...
    tree_rhs = []  # This was the 'upper' side in the bash...
    closest_lhs = None
    closest_rhs = None
    closest_lhs_diff = None
    closest_rhs_diff = None

    for dt in date_list:
        if isinstance(dt, datetime.datetime):
            dt = dt.date()
        elif isinstance(dt, str):
            dt = datetime.datetime.strptime(dt, SCENE_DATE_FMT).date()
        elif not isinstance(primary_dt, datetime.date):
            dt = datetime.date(dt)

        dt_diff = dt - primary_dt

        # Skip scenes that match the primary date
        if dt_diff.days == 0:
            continue

        # Record closest scene
        if dt_diff < datetime.timedelta(0):
            is_closer = closest_lhs is None or dt_diff > closest_lhs_diff

            if is_closer:
                closest_lhs = dt
                closest_lhs_diff = dt_diff
        else:
            is_closer = closest_rhs is None or dt_diff < closest_rhs_diff

            if is_closer:
                closest_rhs = dt
                closest_rhs_diff = dt_diff

        # Skip scenes outside threshold window
        if abs(dt_diff) > thresh_dt:
            continue

        if dt_diff < datetime.timedelta(0):
            tree_lhs.append(dt)
        else:
            tree_rhs.append(dt)

    # Use closest scene if none are in threshold window
    if include_closest:
        if len(tree_lhs) == 0 and closest_lhs is not None:
            _LOG.info(
                f"Date difference to closest secondary greater than {thres_days} days, using closest secondary only: {closest_lhs}"
            )
            tree_lhs = [closest_lhs]

        if len(tree_rhs) == 0 and closest_rhs is not None:
            _LOG.info(
                f"Date difference to closest secondary greater than {thres_days} days, using closest secondary only: {closest_rhs}"
            )
            tree_rhs = [closest_rhs]

    return tree_lhs, tree_rhs


def create_secondary_coreg_tree(primary_dt, date_list, thres_days=63):
    """
    Creates a set of co-registration lists containing subsets of the prior set, to create a tree-like co-registration structure.

    Notes from the bash on :thres_days: parameter:
        #thres_days=93 # three months, S1A/B repeats 84, 90, 96, ... (90 still ok, 96 too long)
        # -> some secondaries with zero averages for azimuth offset refinement
        thres_days=63 # three months, S1A/B repeats 54, 60, 66, ... (60 still ok, 66 too long)
         -> 63 days seems to be a good compromise between runtime and coregistration success
        #thres_days=51 # maximum 7 weeks, S1A/B repeats 42, 48, 54, ... (48 still ok, 54 too long)
        # -> longer runtime compared to 63, similar number of badly coregistered scenes
        # do secondaries with time difference less than thres_days
    """

    # We do everything with datetime.date's (can't mix and match date vs. datetime)
    primary_dt = standardise_to_date(primary_dt)

    lists = []

    # Note: when compositing the lists, rhs comes first because the bash puts the rhs as
    # the "lower" part of the tree, which seems to appear first in the list file...
    #
    # I've opted for rhs vs. lhs because it's more obvious, newer scenes are to the right
    # in sequence as they're greater than, older scenes are to the left / less than.

    # Initial Primary<->Secondary coreg list
    lhs, rhs = find_scenes_in_range(primary_dt, date_list, thres_days)
    last_list = lhs + rhs

    while len(last_list) > 0:
        lists.append(last_list)

        if last_list[0] < primary_dt:
            lhs, rhs = find_scenes_in_range(last_list[0], date_list, thres_days)
            sub_list1 = lhs
        else:
            sub_list1 = []

        if last_list[-1] > primary_dt:
            lhs, rhs = find_scenes_in_range(last_list[-1], date_list, thres_days)
            sub_list2 = rhs
        else:
            sub_list2 = []

        last_list = sub_list1 + sub_list2

    return lists


def append_secondary_coreg_tree(primary_dt, old_date_lists, new_date_list, thres_days=63):
    """
    This function continues the tree structure defined by create_secondary_coreg_tree, by adding
    a new set of dates to an existing coregistration tree.

    :param primary_dt:
        The primary date, which should be the root of the tree that other dates branch out from
    :param old_date_lists:
        The original coregistration tree dates (not the original tree itself), one entry per stack append.

        This is used to re-create the original coregistration tree that will be appended to.
    :param new_date_list:
        The list of new dates to be added to the coregistration tree.
    :param thres_days:
        A threshold (in days) of how close dates must be to the prior/parent coregistration tree level,
        to be included in the subsequent coregistration tree level.
    :returns:
        An array of dates, each entry being one level in the coregistration tree.
    """
    thresh_dt = datetime.timedelta(days=thres_days)

    # We do everything with datetime.date's (can't mix and match date vs. datetime)
    primary_dt = standardise_to_date(primary_dt)

    # Find the original stack dates, as there would be no tree if only 1 date
    # was in the stack at first (very niche corner case - common in our unit tests though).
    first_tree_dates = []
    first_trees_count = 0
    for list in old_date_lists:
        first_tree_dates += list
        first_trees_count += 1

        if len(first_tree_dates) >= 2:
            break

    # If there was no tree originally, create our first tree w/ the original products + appended
    if len(first_tree_dates) < 2:
        first_tree_dates += new_date_list
        return create_secondary_coreg_tree(primary_dt, first_tree_dates, thres_days=thres_days)

    # Note: we are intentionally re-producing the full tree from the original + all the
    # new sets of dates.  This allows us to be a bit paranoid and double-check everything
    # remains consistent every run instead of just blindly writing the new elements and
    # hope nothing has changed since the stack last processed
    og_tree = create_secondary_coreg_tree(primary_dt, first_tree_dates, thres_days=thres_days)

    new_date_lists = list(old_date_lists[first_trees_count:]) + [new_date_list]

    final_tree = og_tree.copy()
    last_list = final_tree[-1]
    latest_stack_date = max(last_list)

    # For each set of new dates, add a new level to the tree
    for new_dates in new_date_lists:
        new_dates = [standardise_to_date(i) for i in new_dates]

        # Sanity check new dates, we require all new dates within thres_days of
        # each other AND at least one is within thres_days of the latest date
        # already in the stack (eg: there's a chain from latest to all these dates)
        if not any(abs(latest_stack_date - dt) <= thresh_dt for dt in new_dates):
            raise ValueError("The provided dates do not contain any that are within thres_dt of the latest date in the coreg tree")

        for date in new_dates:
            if not any(abs(date - dt) <= thresh_dt for dt in new_dates if dt != date):
                raise ValueError("The provided dates do not have at least one date within thres_dt of each other")

        # Note: This design really works best when we only append new dates 'after' (or before) the whole set
        # of dates already in the stack... in theory it's possible to back-and-forward for any order of dates
        # within thres_days, but it will produce a weird looking tree - if we only append new subsequent dates
        # you will get a consistent looking tree similar-ish to the original tree.
        #
        # This is understood, we have no real data or theories on how this could impact
        # accuracy yet... so for now this is fine, until we see data showing us otherwise.

        while len(last_list) > 0:
            if last_list[0] < primary_dt:
                lhs, rhs = find_scenes_in_range(last_list[0], new_dates, thres_days)
                sub_list1 = lhs
            else:
                sub_list1 = []

            if last_list[-1] > primary_dt:
                lhs, rhs = find_scenes_in_range(last_list[-1], new_dates, thres_days)
                sub_list2 = rhs
            else:
                sub_list2 = []

            last_list = sub_list1 + sub_list2
            final_tree.append(last_list)

    return final_tree
