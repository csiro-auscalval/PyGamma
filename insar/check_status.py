#!/usr/bin/python3

import os
from os.path import join as pjoin, basename, getsize, splitext, exists, isdir
import fnmatch
import logging

from structlog import wrap_logger
from structlog.processors import JSONRenderer

from python_scripts.constant import Wildcards, MatchStrings, FolderNames, ErrorMessages

STATUS_LOGGER = wrap_logger(
    logging.getLogger("status"), processors=[JSONRenderer(indent=1, sort_keys=True)]
)
ERROR_LOGGER = wrap_logger(
    logging.getLogger("errors"), processors=[JSONRenderer(indent=1, sort_keys=True)]
)


def checkgammadem(gamma_dem_path, track_frame):
    """
    Checks if gamma dem has been created
    Check implemented here is checking the existence of {track}.dem and {track}.dem.par files

    :param gamma_dem_path:
        A 'path' to gamma dem directory
    :param track_frame:
        A 'name' of a sentinel 1 track

    :return:
        complete_status = True if all checks pass raise an Error
    """
    # lists all the file in gamma dem directory
    gamma_dem_files = [f for f in os.listdir(gamma_dem_path)]

    # set the name of dem and dem par files
    dem_file = Wildcards.TRACK_DEM_TYPE.value.format(track_frame=track_frame)
    dem_par_file = Wildcards.TRACK_DEM_PAR_TYPE.value.format(track_frame=track_frame)

    # check if both dem file and dem par file exists in gamma dem directory
    # set complete status to True if both exits, else set to False
    if all(item in gamma_dem_files for item in [dem_file, dem_par_file]):
        complete_status = True
    else:
        error = "{f1} or {f2} missing from the gamma dem directory".format(
            f1=dem_file, f2=dem_par_file
        )
        ERROR_LOGGER.error(error)
        complete_status = False

    return complete_status


def checkfullslc(slc_path):
    """
    Checks if full slc creation is completed or not.
    Check implemented here is 'error.log' file size check, which should be zero
    byte for successful slc tasks.

    :param slc_path:
        A 'path' to SLC directory

    :return:
        complete_status = True if all checks pass else raise an Error
    """
    scenes = []
    slc_status = []

    # check error log file size for all the scenes in slc directory
    for scene in os.listdir(slc_path):

        # set the path for scene slc directory
        scene_dir = os.path.join(slc_path, scene)

        # get all files in slc directory
        slc_files = [f for f in os.listdir(scene_dir)]

        # get the error log
        error_log = fnmatch.filter(slc_files, Wildcards.SLC_ERROR_LOG_TYPE.value)[0]

        # get the file size
        error_file_size = getsize(pjoin(scene_dir, error_log))

        flag = True
        if error_file_size > 0:
            flag = False

        # collect individual scene's slc status
        scenes.append(scene)
        slc_status.append(flag)

    # if all the slc_status are True then complete status is True else set to False
    if all(slc_status):
        complete_status = True
    else:
        failed_slc = [scenes[i] for i, e in enumerate(slc_status) if e is False]
        error = "Following {slc} error.log does not have expected file size of 0 B".format(
            slc=failed_slc
        )
        ERROR_LOGGER.error(error)
        complete_status = False

    return complete_status


def checkmultilook(slc_path):
    """
     Checks if full multi-look image is created or not.
     Check implemented here is '.mli' file size check, which should be greater than 0
     byte for successful multi-look tasks.

     :param slc_path:
         A 'path' to SLC directory

     :return:
         complete_status = True if all checks pass else False
     """
    scenes = []
    mli_status = []

    # check error log file size for all the scenes in slc directory
    for scene in os.listdir(slc_path):

        # set the path for scene slc directory
        scene_dir = os.path.join(slc_path, scene)

        # get all files in slc directory
        slc_files = [f for f in os.listdir(scene_dir)]

        # get the mli file
        mli_file = fnmatch.filter(slc_files, Wildcards.MLI_TYPE.value)[0]

        # get mli file size
        mli_file_size = getsize(pjoin(scene_dir, mli_file))

        flag = True
        if mli_file_size > 0:
            pass
        else:
            flag = False

        # collect individual scene's mli status
        scenes.append(scene)
        mli_status.append(flag)

    # if all the mli_status are True then complete status is True else raise an Error
    if all(mli_status):
        complete_status = True
    else:
        failed_mli = [scenes[i] for i, e in enumerate(mli_status) if e is False]
        error = "Following {mli} scenes does not have expected file size greater than 0 B".format(
            mli=failed_mli
        )
        ERROR_LOGGER.error(error)
        complete_status = False

    return complete_status


def checkdemmaster(dem_path, slc_path, master_scene):
    """
    Checks if master scene and DEM co-registration is correctly performed
    Check implemented are file size check on the error.log from DEM and
    SLC master scene. In addition, expected file size check is performed on
    radar coded multi-look image (r*.mli) in Master SLC directory and rdc file
    in the DEM directory.
    :param dem_path:
        A 'path' to DEM directory
    :param slc_path:
        A 'path' to SLC directory
    :param master_scene:
        A 'master scene' folder name
    :return:
        True if checks are successful else return False
    """
    # master scene slc dir
    master_scene_path = pjoin(slc_path, master_scene)

    # get list of files from dem and master scene slc path
    slc_files = [f for f in os.listdir(master_scene_path)]
    dem_files = [f for f in os.listdir(dem_path)]

    # get the dem and slc error log
    dem_error_log = pjoin(
        dem_path, fnmatch.filter(dem_files, Wildcards.DEM_ERROR_LOG_TYPE.value)[0]
    )
    slc_error_log = pjoin(
        master_scene_path,
        fnmatch.filter(slc_files, Wildcards.SLC_ERROR_LOG_TYPE.value)[0],
    )

    # get radar coded mli and par file, and rdc sim file,
    r_mli_file = pjoin(
        master_scene_path,
        fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_TYPE.value)[0],
    )
    r_mli_par_file = pjoin(
        master_scene_path,
        fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_PAR_TYPE.value)[0],
    )
    rdc_sim_file = pjoin(
        dem_path, fnmatch.filter(dem_files, Wildcards.RDC_SIM_TYPE.value)[0]
    )

    # perform slc error log checks
    slc_error_log_size = getsize(slc_error_log)
    if slc_error_log_size > 0:
        error = ErrorMessages.ERROR_LOG_MSGS.value.format(
            f=slc_error_log, s=slc_error_log_size, d=0
        )
        ERROR_LOGGER.error(error)
        return False

    # perform dem error log checks
    dem_error_log_size = getsize(dem_error_log)
    if dem_error_log_size > 450:
        with open(dem_error_log, "r") as src:
            lines = src.readlines()
            for line in lines:
                if line.isspace() or line.startswith(
                    (
                        MatchStrings.DEM_USAGE_NOTE.value,
                        MatchStrings.DEM_SCENE_TITLE.value,
                        MatchStrings.DEM_WARNING.value,
                        MatchStrings.DEM_ISP.value,
                    )
                ):
                    pass
                else:
                    error = ErrorMessages.ERROR_CONTENT_MSGS.value.format(
                        f=basename(dem_error_log), s=line.strip()
                    )
                    ERROR_LOGGER.error(error)
                    return False

    # check on rdc sim file
    rdc_sim_file_size = getsize(rdc_sim_file)

    if rdc_sim_file_size == 0:
        error = ErrorMessages.MLI_FILE_SIZE_ERROR_MSGS.value.format(
            s=rdc_sim_file_size, f=rdc_sim_file
        )
        ERROR_LOGGER.error(error)
        return False

    # check on r_mli file
    r_mli_file_size = getsize(r_mli_file)

    # if file size is greater than 0 byte
    # additional check for to see if file size is same as expected file size
    ranges, azimuths, expected_rmli_size = 0, 0, 0
    if r_mli_file_size > 0:

        with open(r_mli_par_file, "r") as src:
            lines = src.readlines()
            for line in lines:
                if line.startswith(MatchStrings.SLC_RANGE_SAMPLES.value):
                    ranges = int(line.split(":")[1])
                if line.startswith(MatchStrings.SLC_AZIMUTH_LINES.value):
                    azimuths = int(line.split(":")[1])

                line_azimuth = ranges * azimuths
                if line_azimuth > 0:
                    expected_rmli_size = line_azimuth * 4
                    break

        # check if file size are same
        if expected_rmli_size != r_mli_file_size:
            error = ErrorMessages.ERROR_LOG_MSGS.value.format(
                f=r_mli_file, s=expected_rmli_size, d=r_mli_file_size
            )
            ERROR_LOGGER.error(error)
            return False
        else:
            return True
    else:
        return False


def checkcoregslaves(slc_path, master_scene):
    """
    Checks if co-registration of slaves were performed correctly or not!
    Checks implemented here involves checking the error.log file size and
    its contents (blank spaces are accepted). Further, check on radar coded
    multi-look image is also carried out to see if its size is as expected.

    :param slc_path:
        A 'path' to slc directory
    :param master_scene:
        A 'master scene' folder name

    :return:
        complete_status = True if checks are successful else raises an error
    """
    scenes = []
    scene_error_msgs = {}
    coreg_status = []

    # check error log file size for all the scenes in slc directory
    for scene in os.listdir(slc_path):
        flag = True
        errors = {}
        if scene is not master_scene:
            # set the path for scene slc directory
            scene_dir = os.path.join(slc_path, scene)

            # get all files in slc directory
            slc_files = [f for f in os.listdir(scene_dir)]

            # get error log file
            slc_error_log = pjoin(
                scene_dir,
                fnmatch.filter(slc_files, Wildcards.SLC_ERROR_LOG_TYPE.value)[0],
            )

            # get radar coded mli and par file,
            r_mli_file = pjoin(
                scene_dir,
                fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_TYPE.value)[0],
            )
            r_mli_par_file = pjoin(
                scene_dir,
                fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_PAR_TYPE.value)[0],
            )

            # perform slc error log checks
            slc_error_log_size = getsize(slc_error_log)
            if slc_error_log_size > 0:
                with open(slc_error_log, "r") as src:
                    lines = src.readlines()
                    for line in lines:
                        if not line.isspace():
                            error1 = ErrorMessages.ERROR_CONTENT_MSGS.value.format(
                                f=basename(slc_error_log), s=line.strip()
                            )

                            error2 = ErrorMessages.ERROR_LOG_MSGS.value.format(
                                f=slc_error_log, s=slc_error_log_size, d=0
                            )
                            errors["error1"] = error1
                            errors["error2"] = error2
                            flag = False

            # check on r_mli file
            r_mli_file_size = getsize(r_mli_file)

            # if file size is greater than 0 byte
            # additional check for to see if file size is same as expected file size
            ranges, azimuths, expected_rmli_size = 0, 0, 0
            if r_mli_file_size > 0:
                with open(r_mli_par_file, "r") as src:
                    lines = src.readlines()
                    for line in lines:
                        if line.startswith(MatchStrings.SLC_RANGE_SAMPLES.value):
                            ranges = int(line.split(":")[1])
                        if line.startswith(MatchStrings.SLC_AZIMUTH_LINES.value):
                            azimuths = int(line.split(":")[1])
                        line_azimuth = ranges * azimuths
                        if line_azimuth > 0:
                            expected_rmli_size = line_azimuth * 4
                            break
                # check if file size are same
                if expected_rmli_size != r_mli_file_size:
                    error3 = ErrorMessages.ERROR_LOG_MSGS.value.format(
                        f=r_mli_file, s=expected_rmli_size, d=r_mli_file_size
                    )
                    errors["error3"] = error3
                    flag = False
            else:
                flag = False
            # collect individual scene's error and flag status
            scene_error_msgs[scene] = errors
            scenes.append(scene)
            coreg_status.append(flag)

    # if all the coreg_status are True then complete status is True else set raises Error
    if all(coreg_status):
        complete_status = True
    else:
        error = {k: v for (k, v) in scene_error_msgs.items()}
        ERROR_LOGGER.error(error)
        complete_status = False

    return complete_status


def checkifgs(ifg_path):
    """
    Checks if inter-ferogram genrattion tasks are performed successfully
    or not! Check implemented here are file size check on error.log,
    flattened inter-ferogram and un-wrapped inter-ferogram

    :param ifg_path:
        A 'path' to ifg directory
    :return:
        complete_status = True if checks are successful else raises an error
    """
    scenes = []
    scene_error_msgs = {}
    ifg_status = []

    # check error log file size for all the scenes connection in INT directory
    for scene in os.listdir(ifg_path):
        flag = True
        errors = {}
        # set the path for scene slc directory
        scene_dir = os.path.join(ifg_path, scene)

        # get all files in slc directory
        ifg_files = [f for f in os.listdir(scene_dir)]

        # get error log file
        ifg_error_log = pjoin(
            scene_dir, fnmatch.filter(ifg_files, Wildcards.SLC_ERROR_LOG_TYPE.value)[0]
        )

        # get flatten ifg, off_par and eqa_unw files
        flat_file = pjoin(
            scene_dir, fnmatch.filter(ifg_files, Wildcards.INT_FLAT_TYPE.value)[0]
        )
        eqa_unw_file = pjoin(
            scene_dir, fnmatch.filter(ifg_files, Wildcards.EQA_UNW_TYPE.value)[0]
        )

        # perform slc error log checks
        ifg_error_log_size = getsize(ifg_error_log)
        if ifg_error_log_size > 0:
            with open(ifg_error_log, "r") as src:
                lines = src.readlines()
                for line in lines:
                    if not line.isspace():
                        error1 = ErrorMessages.ERROR_CONTENT_MSGS.value.format(
                            f=basename(ifg_error_log), s=line.strip()
                        )

                        error2 = ErrorMessages.ERROR_LOG_MSGS.value.format(
                            f=ifg_error_log, s=ifg_error_log_size, d=0
                        )
                        errors["error1"] = error1
                        errors["error2"] = error2
                        flag = False

        flat_file_size = getsize(flat_file)
        if flat_file_size > 0:
            pass
        else:
            error3 = ErrorMessages.MLI_FILE_SIZE_ERROR_MSGS.value.format(
                f=flat_file, s=flat_file_size
            )
            errors["error3"] = error3
            flag = False

        eqa_unw_file_size = getsize(eqa_unw_file)
        if eqa_unw_file_size > 0:
            pass
        else:
            error4 = ErrorMessages.MLI_FILE_SIZE_ERROR_MSGS.value.format(
                f=eqa_unw_file, s=eqa_unw_file_size
            )
            errors["error4"] = error4
            flag = False

        # collect individual scene's error and flag status
        scene_error_msgs[scene] = errors
        scenes.append(scene)
        ifg_status.append(flag)

    # if all the ifg_status are True then complete status is True else raises an Error
    if all(ifg_status):
        complete_status = True
    else:
        failed_error = {k: v for (k, v) in scene_error_msgs.items()}
        ERROR_LOGGER.error(failed_error)
        complete_status = False

    return complete_status
