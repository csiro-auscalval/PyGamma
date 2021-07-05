#!/usr/bin/env python

import datetime
from insar.constant import SCENE_DATE_FMT
from pathlib import Path
import geopandas

import insar.constant as const


def rm_file(path):
    '''A hacky unlink/delete file function for Python <3.8 which lacks a missing_ok parameter in Path.unlink'''
    path = Path(path)

    if path.exists():
        path.unlink()


def parse_date(scene_name):
    """ Parse str scene_name into datetime object. """
    return datetime.datetime.strptime(scene_name, SCENE_DATE_FMT)


def coregristration_candidates(
    scenes, primary_idx, threshold, max_secondary_idx=None,
):
    """
    Returns secondary scene index  to be co-registered with primary scene and
    checks if co-registration of scenes are complete or not.
    """
    if primary_idx == len(scenes) - 1:
        return None, True

    secondary_idx = None
    is_complete = False
    _primary_date = parse_date(scenes[primary_idx])

    for idx, scene in enumerate(scenes[primary_idx + 1 :], primary_idx + 1):
        if max_secondary_idx and idx > max_secondary_idx:
            break
        if abs((parse_date(scene) - _primary_date).days) > threshold:
            break
        secondary_idx = idx

    if secondary_idx and secondary_idx == len(scenes) - 1:
        is_complete = True

    if not secondary_idx and idx < len(scenes) - 1:
        secondary_idx = idx

    return secondary_idx, is_complete


def coreg_candidates_after_primary_scene(
    scenes, primaries_list, main_primary,
):
    """
    Return co-registration pairs for scenes after main primary scene's date.
    :param scenes: list of scenes strings in '%Y%m%d' format.
    :param primaries: list of primary scenes strings in '%Y%m%d format.
    :return coregistration_scenes as a dict with key = primary and
            values = list of secondary scenes for a primary to be coregistered with.
    """
    # secondary primaries(inclusive of main primary scene) are sorted in ascending order with
    # main primary scene as a starting scene
    primaries = [
        scene for scene in primaries_list if parse_date(scene) >= parse_date(main_primary)
    ]
    primaries.sort(key=lambda date: datetime.datetime.strptime(date, SCENE_DATE_FMT))

    coregistration_scenes = {}
    for idx, primary in enumerate(primaries):
        tmp_list = []
        if idx < len(primaries) - 1:
            for scene in scenes:
                if parse_date(primary) < parse_date(scene) < parse_date(primaries[idx + 1]):
                    tmp_list.append(scene)
            coregistration_scenes[primary] = tmp_list
        else:
            for scene in scenes:
                if parse_date(scene) > parse_date(primary):
                    tmp_list.append(scene)
            coregistration_scenes[primary] = tmp_list
    return coregistration_scenes


def coreg_candidates_before_primary_scene(
    scenes, primaries_list, main_primary,
):
    """
    Return co-registration pairs for scenes before main primary scene's date.

    :param scenes: list of scenes strings in '%Y%m%d' format.
    :param primaries: list of primary scenes strings in '%Y%m%d format.
    :return coregistration_scenes: dict with primary(key) and scenes(value)
    """
    # secondary primaries (inclusive of primary scene) are sorted in descending order with
    # main primary scene as starting scene
    primaries = [
        scene for scene in primaries_list if parse_date(scene) <= parse_date(main_primary)
    ]
    primaries.sort(
        key=lambda date: datetime.datetime.strptime(date, SCENE_DATE_FMT), reverse=True,
    )

    coregistration_scenes = {}
    for idx, primary in enumerate(primaries):
        tmp_list = []
        if idx < len(primaries) - 1:
            for scene in scenes:
                if parse_date(primary) > parse_date(scene) > parse_date(primaries[idx + 1]):
                    tmp_list.append(scene)

            coregistration_scenes[primary] = tmp_list
        else:
            for scene in scenes:
                if parse_date(scene) < parse_date(primary):
                    tmp_list.append(scene)
            coregistration_scenes[primary] = tmp_list
    return coregistration_scenes


def read_land_center_coords(pg, mli_par: Path, shapefile: Path):
    """
    Reads the land center coordinates from a shapefile and converts it into pixel coordinates for a multilook image

    :param pg: the PyGamma wrapper object used to dispatch gamma commands
    :param mli_par: the path to the .mli.par file in which the pixel coordinates should be for
    :param shapefie: the path to the shape file for the scene
    :return (range/altitude, line/azimuth) pixel coordinates
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

    # Convert lat/long to pixel coords
    _, cout, _ = pg.coord_to_sarpix(
        mli_par,
        const.NOT_PROVIDED,
        const.NOT_PROVIDED,
        north_lat,
        east_lon,
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
