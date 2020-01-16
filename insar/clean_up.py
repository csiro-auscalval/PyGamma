#!/usr/bin/env python

import fnmatch
import shutil
from pathlib import Path
from typing import Union, List, Optional

from insar.constant import Wildcards, SlcFilenames, MliFilenames


def clean_rawdatadir(raw_data_path: Union[Path, str]) -> None:
    """
    Deletes all files in the raw data directory.

    :param raw_data_path:
        A full path to raw data path.
    """
    if Path(raw_data_path).exists():
        shutil.rmtree(raw_data_path)


def clean_coreg_scene(
    slc_path: Union[Path, str], scene: str, pol: str, rlks: int
) -> None:
    """
    Deletes files that were created during co-registration steps

    :param slc_path:
        A full path to slc directory.
    :param scene:
        A string formatted ('YYYYMMDD') SLC scene data.
    :param pol:
        Polarization of a SLC image.
    :param rlks:
        A range look value used in formatting the mli filenames.
    """

    slc_path = Path(slc_path)
    if slc_path.exists():
        
        slc_files = []
        slc_files.append(SlcFilenames.SLC_FILENAME.value.format(scene, pol))
        slc_files.append(SlcFilenames.SLC_PAR_FILENAME.value.format(scene, pol))
        slc_files.append(SlcFilenames.SLC_TOPS_PAR_FILENAME.value.format(scene, pol))
        slc_files.append(SlcFilenames.SLC_TAB_FILENAME.value.format(scene, pol))
        
        mli_files = [
            item.value.format(scene_date=scene, pol=pol, rlks=rlks)
            for item in MliFilenames
        ]
        for fp in slc_path.joinpath(scene).iterdir():
            if fp.name not in slc_files + mli_files:
                fp.unlink()


def clean_slcdir(
    slc_path: Union[Path, str], patterns: Optional[List[str]] = None
) -> None:
    """
    Deletes files associated with wildcard patterns from slc directory.

    :param slc_path:
        A full path to a slc base directory.
    :param patterns:
        A List with wildcard patterns to match files to delete.
    """

    if not patterns:
        patterns = [Wildcards.SWATH_TYPE.value, Wildcards.SCENE_CONNECTION_TYPE.value]

    slc_path = Path(slc_path)

    if slc_path.exists():
        for scene_dir in slc_path.iterdir():
            # delete the files set by wildcard patterns
            files_list = get_wildcard_match_files(
                dirs_path=scene_dir, wildcards=patterns
            )
            _del_files(file_dir=scene_dir, files_list=files_list)

            # get all the remaining files in slc scene directory
            files_list = get_wildcard_match_files(
                dirs_path=scene_dir, wildcards=Wildcards.ALL_TYPE.value
            )

            # set the patterns for files that needs saved
            save_patterns = [
                Wildcards.GAMMA0_TYPE.value,
                Wildcards.RADAR_CODED_TYPE.value,
                Wildcards.GAMMA0_TYPE.value,
            ]

            # get the save files associated with save patterns
            save_files = get_wildcard_match_files(
                dirs_path=scene_dir, wildcards=save_patterns
            )

            # get the del file lists (files which are not in save files)
            del_files_list = [item for item in files_list if item not in save_files]

            # delete the files
            _del_files(file_dir=scene_dir, files_list=del_files_list)


def clean_ifgdir(
    ifg_path: Union[Path, str], patterns: Optional[List[str]] = None
) -> None:
    """
    Deletes files associated with wildcard patterns from ifg directory.

    :param ifg_path:
        A full path to a base path of ifg directory.
    :param patterns:
        A List with wildcard patterns to match files to delete.
    """

    if not patterns:
        patterns = [
            Wildcards.FLT_TYPE.value,
            Wildcards.MODEL_UNW_TYPE.value,
            Wildcards.SIM_UNW_TYPE.value,
            Wildcards.THIN_UNW_TYPE.value,
        ]

    ifg_path = Path(ifg_path)
    if ifg_path.exists():
        for scene_dir in ifg_path.iterdir():
            # delete the files set by wildcard patterns
            files_list = get_wildcard_match_files(
                dirs_path=scene_dir, wildcards=patterns
            )
            _del_files(file_dir=scene_dir, files_list=files_list)


def clean_gammademdir(gamma_dem_path: Union[Path, str], track_frame=None) -> None:
    """
    Deletes files associated with wildcard patterns from gamma dem directory.

    :param gamma_dem_path:
        A full path to a gamma dem directory.
    :param track_frame:
        A track_frame name to match files to delete.
    """
    if track_frame:
        patterns = [
            Wildcards.TRACK_DEM_TYPE.value.format(track_frame=track_frame),
            Wildcards.TRACK_DEM_PAR_TYPE.value.format(track_frame=track_frame),
            Wildcards.TRACK_DEM_PNG_TYPE.value,
        ]
    else:
        patterns = None

    gamma_dem_path = Path(gamma_dem_path)
    if gamma_dem_path.exists():
        files_list = get_wildcard_match_files(
            dirs_path=gamma_dem_path, wildcards=patterns
        )
        _del_files(file_dir=gamma_dem_path, files_list=files_list)


def clean_demdir(
    dem_path: Union[Path, str], patterns: Optional[List[str]] = None
) -> None:
    """
    Deletes files associated with wildcard patterns from DEM directory

    :param dem_path:
        A full path to a DEM directory.
    :param patterns:
        A List with wildcard patterns to match files to delete.
    """
    if not patterns:
        patterns = [
            Wildcards.CCP_TYPE.value,
            Wildcards.SIM_TYPE.value,
            Wildcards.PIX_TYPE.value,
            Wildcards.RDC_TYPE.value,
        ]

    if Path(dem_path).exists():
        files_list = get_wildcard_match_files(
            dirs_path=Path(dem_path), wildcards=patterns
        )
        _del_files(file_dir=Path(dem_path), files_list=files_list)


def get_wildcard_match_files(
    dirs_path: Union[Path, str], wildcards: Optional[List[str]] = None
) -> Union[None, List]:
    """
    Returns files associated with wildcard patterns from directory 'dirs_path'

    :param dirs_path:
        A full path to a  directory.
    :param wildcards:
        A List with wildcard patterns to match files to delete.
    """

    files_list = []
    if not Path(dirs_path).exists():
        return None

    all_files = [fp.name for fp in Path(dirs_path).iterdir()]
    if wildcards is not None:
        for pattern in wildcards:
            match_files = fnmatch.filter(all_files, pattern)
            if match_files:
                files_list.append(match_files)
        return sum(files_list, [])
    return None


def _del_files(file_dir=None, files_list=None):
    """
    Deletes all files in 'files_list' from the directory 'file_dir'
    """
    if files_list is not None:
        for item in files_list:
            Path(file_dir).joinpath(item).unlink()
