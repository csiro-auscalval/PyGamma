#!/usr/bin/env python

import datetime
from insar.constant import SCENE_DATE_FMT


def parse_date(scene_name):
    """ Parse str scene_name into datetime object. """
    return datetime.datetime.strptime(scene_name, SCENE_DATE_FMT)


def coregristration_candidates(
    scenes,
    master_idx,
    threshold,
    max_slave_idx=None,
):
    """
    Returns slave scene index  to be co-registered with master scene and
    checks if co-registration of scenes are complete or not.
    """
    if master_idx == len(scenes) - 1:
        return None, True

    slave_idx = None
    is_complete = False
    _master_date = parse_date(scenes[master_idx])

    for idx, scene in enumerate(scenes[master_idx + 1 :], master_idx + 1):
        if max_slave_idx and idx > max_slave_idx:
            break
        if abs((parse_date(scene) - _master_date).days) > threshold:
            break
        slave_idx = idx

    if slave_idx and slave_idx == len(scenes) - 1:
        is_complete = True

    if not slave_idx and idx < len(scenes) - 1:
        slave_idx = idx

    return slave_idx, is_complete


def coreg_candidates_after_master_scene(
    scenes,
    masters_list,
    main_master,
):
    """
    Return co-registration pairs for scenes after main master scene's date.
    :param scenes: list of scenes strings in '%Y%m%d' format.
    :param masters: list of master scenes strings in '%Y%m%d format.
    :return coregistration_scenes as a dict with key = master and
            values = list of slave scenes for a master to be coregistered with.
    """
    # secondary masters(inclusive of main master scene) are sorted in ascending order with
    # main master scene as a starting scene
    masters = [
        scene for scene in masters_list if parse_date(scene) >= parse_date(main_master)
    ]
    masters.sort(key=lambda date: datetime.datetime.strptime(date, SCENE_DATE_FMT))

    coregistration_scenes = {}
    for idx, master in enumerate(masters):
        tmp_list = []
        if idx < len(masters) - 1:
            for scene in scenes:
                if (
                    parse_date(master)
                    < parse_date(scene)
                    < parse_date(masters[idx + 1])
                ):
                    tmp_list.append(scene)
            coregistration_scenes[master] = tmp_list
        else:
            for scene in scenes:
                if parse_date(scene) > parse_date(master):
                    tmp_list.append(scene)
            coregistration_scenes[master] = tmp_list
    return coregistration_scenes


def coreg_candidates_before_master_scene(
    scenes,
    masters_list,
    main_master,
):
    """
    Return co-registration pairs for scenes before main master scene's date.

    :param scenes: list of scenes strings in '%Y%m%d' format.
    :param masters: list of master scenes strings in '%Y%m%d format.
    :return coregistration_scenes: dict with master(key) and scenes(value)
    """
    # secondary masters (inclusive of master scene) are sorted in descending order with
    # main master scene as starting scene
    masters = [
        scene for scene in masters_list if parse_date(scene) <= parse_date(main_master)
    ]
    masters.sort(
        key=lambda date: datetime.datetime.strptime(date, SCENE_DATE_FMT),
        reverse=True,
    )

    coregistration_scenes = {}
    for idx, master in enumerate(masters):
        tmp_list = []
        if idx < len(masters) - 1:
            for scene in scenes:
                if (
                    parse_date(master)
                    > parse_date(scene)
                    > parse_date(masters[idx + 1])
                ):
                    tmp_list.append(scene)

            coregistration_scenes[master] = tmp_list
        else:
            for scene in scenes:
                if parse_date(scene) < parse_date(master):
                    tmp_list.append(scene)
            coregistration_scenes[master] = tmp_list
    return coregistration_scenes
