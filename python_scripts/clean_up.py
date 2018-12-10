#!/usr/bin/python3

import os
from os.path import join as pjoin, exists, getmtime
from python_scripts.constant import Wildcards
import fnmatch
import shutil
import numpy


def clean_rawdatadir(raw_data_path=None):
    """
    Deletes all files in the raw data directory
    """
    if exists(raw_data_path):
        print("deleting raw data dir ...")
        shutil.rmtree(raw_data_path)


def clean_slcdir(slc_path=None, patterns=None):
    """
    Deletes files associated with wildcard patterns from slc directory
    """
    if not patterns:
        patterns = [Wildcards.SWATH_TYPE.value, Wildcards.SCENE_CONNECTION_TYPE.value]

    if exists(slc_path):
        for scene in os.listdir(slc_path):
            scene_dir = pjoin(slc_path, scene)
            # delete the files set by wildcard patterns
            files_list = get_wildcard_match_files(dirs_path=scene_dir, wildcards=patterns)
            _del_files(file_dir=scene_dir, files_list=files_list)

            # get all the remaining files in slc scene directory
            files_list = get_wildcard_match_files(dirs_path=scene_dir, wildcards=Wildcards.ALL_TYPE.value)

            # set the patterns for files that needs saved
            save_patterns = [Wildcards.GAMMA0_TYPE.value, Wildcards.RADAR_CODED_TYPE.value]

            # get the save files associated with save patterns
            save_files = get_wildcard_match_files(dirs_path=scene_dir, wildcards=save_patterns)

            # get the del file lists (files which are not in save files)
            del_files_list = [item for item in files_list if item not in save_files]

            # delete the files
            _del_files(file_dir=scene_dir, files_list=del_files_list)


def clean_ifgdir(ifg_path=None, patterns=None):
    """
    Deletes files associated with wildcard patterns from ifg directory
    """
    if not patterns:
        patterns = [Wildcards.FLT_TYPE.value, Wildcards.MODEL_UNW_TYPE.value, Wildcards.SIM_UNW_TYPE.value,
                    Wildcards.THIN_UNW_TYPE.value]

    if exists(ifg_path):
        for scene_conn in os.listdir(ifg_path):
            scene_conn_dir = pjoin(ifg_path, scene_conn)

            # delete the files set by wildcard patterns
            files_list = get_wildcard_match_files(dirs_path=scene_conn_dir, wildcards=patterns)
            _del_files(file_dir=scene_conn_dir, files_list=files_list)


def clean_gammademdir(gamma_dem_path=None, track=None):
    """
    Deletes files associated with wildcard patterns from gamma dem directory
    """
    if track:
        patterns = [Wildcards.TRACK_DEM_TYPE.value.format(track=track),
                    Wildcards.TRACK_DEM_PAR_TYPE.value.format(track=track)]

    if exists(gamma_dem_path):
        files_list = get_wildcard_match_files(dirs_path=gamma_dem_path, wildcards=patterns)
        _del_files(file_dir=gamma_dem_path, files_list=files_list)


def clean_demdir(dem_path=None, patterns=None):
    """
    Deletes files associated with wildcard patterns from DEM directory
    """
    if not patterns:
        patterns = [Wildcards.CCP_TYPE.value, Wildcards.SIM_TYPE.value, Wildcards.PIX_TYPE.value,
                    Wildcards.RDC_TYPE.value]

    if exists(dem_path):
        files_list = get_wildcard_match_files(dirs_path=dem_path, wildcards=patterns)
        _del_files(file_dir=dem_path, files_list=files_list)


def clean_checkpoints(checkpoint_path=None, patterns=None):
    """
    Deletes the last check point file if pattern is None
    else deletes files associated with patterns
    """
    if exists(checkpoint_path):
        if not patterns:
            time_lists, checkpoint_files = [], []
            for item in os.listdir(checkpoint_path):
                checkpoint_files.append(item)
                time_lists.append(getmtime(pjoin(checkpoint_path, item)))

            del_file = [checkpoint_files[numpy.argmax(time_lists)]]

            _del_files(file_dir=checkpoint_path, files_list=del_file)

        else:
            files_list = get_wildcard_match_files(dirs_path=checkpoint_path, wildcards=patterns)
            _del_files(file_dir=checkpoint_path, files_list=files_list)


def get_wildcard_match_files(dirs_path=None, wildcards=None):
    """
    returns files associated with wildcard patterns from directory 'dirs_path'
    """
    files_list = []
    if exists(dirs_path):
        all_files = [f for f in os.listdir(dirs_path)]

    for pattern in wildcards:
        match_files = fnmatch.filter(all_files, pattern)
        if match_files:
            files_list.append(match_files)

    return [item for sublist in files_list for item in sublist]


def _del_files(file_dir=None, files_list=None):
    """
    Deletes all files in 'files_list' from the directory 'file_dir'
    """
    if files_list:
        for item in files_list:
            print(item)
            if exists(pjoin(file_dir, item)):
                print('deleting file: {}'.format(item))
                os.remove(pjoin(file_dir, item))

