#!/usr/bin/python3

import os
from os.path import exists, join as pjoin


def get_path(proc_file):
    """
    A method to access paths within InSAR processing directory structure.

    :param proc_file: A 'Path' to a proc file.

    :return:
        A 'dict' containing the path names for required processing
        workflow from a which is derived from a 'proc file'
    """
    pathname_dict = dict()

    if not exists(proc_file):
        raise IOError

    with open(proc_file, "r") as src:
        for line in src.readlines():
            if line.startswith("NCI_PATH="):
                nci_path = line.split("=")[1].strip()
            if line.startswith("S1_PATH="):
                s1_path = line.split("=")[1].strip()
            if line.startswith("PROJECT="):
                project = line.split("=")[1].strip()
            if line.startswith("SENSOR="):
                sensor = line.split("=")[1].strip()
            if line.startswith("TRACK="):
                track = line.split("=")[1].strip()
            if line.startswith("FRAME="):
                frame = line.split("=")[1].strip()
            if line.startswith("SLC_DIR="):
                slc_dir1 = line.split("=")[1].strip()
            if line.startswith("DEM_DIR="):
                dem_dir1 = line.split("=")[1].strip()
            if line.startswith("PDF_DIR"):
                pdf_dir1 = line.split("=")[1].strip()
            if line.startswith("INT_DIR="):
                int_dir1 = line.split("=")[1].strip()
            if line.startswith("REF_MASTER_SCENE="):
                pathname_dict["master_scene"] = line.split("=")[1].strip()
            if line.startswith("CLEAN_UP="):
                pathname_dict["clean_up"] = line.split("=")[1].strip()
            if line.startswith("BASE_DIR="):
                base_dir1 = line.split("=")[1].strip()
            if line.startswith("ERROR_DIR="):
                error_dir1 = line.split("=")[1].strip()
            if line.startswith("BATCH_JOB_DIR="):
                batch_job_dir1 = line.split("=")[1].strip()
            if line.startswith("MANUAL_JOB_DIR="):
                manual_job_dir1 = line.split("=")[1].strip()
            if line.startswith("RAW_DATA_DIR="):
                raw_data_dir1 = line.split("=")[1].strip()
            if line.startswith("LIST_DIR="):
                list_dir1 = line.split("=")[1].strip()
            if line.startswith("PRE_PROC_DIR="):
                pre_proc_dir1 = line.split("=")[1].strip()
            if line.startswith("SCENE_LIST="):
                scene_list = line.split("=")[1].strip()
            if line.startswith("SLAVE_LIST="):
                slave_list = line.split("=")[1].strip()
            if line.startswith("IFG_LIST="):
                ifg_list = line.split("=")[1].strip()
            if line.startswith("S1_FILE_LIST="):
                s1_file_list = line.split("=")[1].strip()
            if line.startswith("POLARISATION="):
                pathname_dict["polarization"] = line.split("=")[1].strip()
            if line.startswith("S1_ORBITS="):
                pathname_dict["s1_orbits"] = line.split("=")[1].strip()
            if line.startswith("RANGE_LOOKS="):
                pathname_dict["range_looks"] = line.split("=")[1].strip()

        # Project directories
        proj_dir1 = pjoin(nci_path, "INSAR_ANALYSIS", project, sensor, "GAMMA")
        pathname_dict["track_frame"] = "{}_{}".format(track, frame)
        pathname_dict["track"] = track
        pathname_dict["frame"] = frame
        pathname_dict["proj_dir"] = proj_dir1
        pathname_dict["checkpoint_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], "checkpoints"
        )
        pathname_dict["list_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], list_dir1
        )
        pathname_dict["dem_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], dem_dir1
        )
        pathname_dict["s1_dir"] = s1_path
        pathname_dict["track_dir"] = pjoin(proj_dir1, pathname_dict["track_frame"])
        pathname_dict["slc_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], slc_dir1
        )
        pathname_dict["ifg_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], int_dir1
        )
        pathname_dict["batch_job_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], batch_job_dir1
        )
        pathname_dict["pdf_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], pdf_dir1
        )
        pathname_dict["manual_job_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], manual_job_dir1
        )
        pathname_dict["raw_data_dir"] = pjoin(
            proj_dir1, raw_data_dir1, pathname_dict["track"], pathname_dict["frame"]
        )
        pathname_dict["base_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], base_dir1
        )
        pathname_dict["pre_proc_dir"] = pjoin(proj_dir1, pre_proc_dir1)
        pathname_dict["results_dir"] = pjoin(
            proj_dir1, pathname_dict["track_frame"], "results"
        )
        pathname_dict["gamma_dem"] = pjoin(proj_dir1, "gamma_dem")

        # batch jobs directories
        pathname_dict["extract_raw_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "extract_raw_jobs"
        )
        pathname_dict["baseline_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "baseline_jobs"
        )
        pathname_dict["dem_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "dem_jobs"
        )
        pathname_dict["coreg_slc_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "coreg_slc_jobs"
        )
        pathname_dict["ifg_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "ifg_jobs"
        )
        pathname_dict["ml_slc_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "ml_slc_jobs"
        )
        pathname_dict["slc_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "slc_jobs"
        )
        pathname_dict["resize_S1_slc_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "resize_S1_slc_jobs"
        )
        pathname_dict["subset_S1_slc_jobs_dir"] = pjoin(
            pathname_dict["batch_job_dir"], "subset_S1_slc_jobs"
        )

        # manual jobs directories
        pathname_dict["manual_extract_raw_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "extract_raw_jobs"
        )
        pathname_dict["manual_baseline_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "baseline_jobs"
        )
        pathname_dict["manual_dem_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "dem_jobs"
        )
        pathname_dict["manual_coreg_slc_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "coreg_slc_jobs"
        )
        pathname_dict["manual_ifg_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "ifg_jobs"
        )
        pathname_dict["manual_ml_slc_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "ml_slc_jobs"
        )
        pathname_dict["manual_slc_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "slc_jobs"
        )
        pathname_dict["manual_resize_S1_slc_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "resize_S1_slc_jobs"
        )
        pathname_dict["manual_subset_S1_slc_jobs_dir"] = pjoin(
            pathname_dict["manual_job_dir"], "subset_S1_slc_jobs"
        )

        # Lists
        pathname_dict["scenes_list"] = pjoin(pathname_dict["list_dir"], scene_list)
        pathname_dict["slaves_list"] = pjoin(pathname_dict["list_dir"], slave_list)
        pathname_dict["ifgs_list"] = pjoin(pathname_dict["list_dir"], ifg_list)
        pathname_dict["download_list"] = pjoin(
            pathname_dict["list_dir"], "download_list"
        )
        pathname_dict["s1_file_list"] = pjoin(pathname_dict["list_dir"], s1_file_list)
        pathname_dict["slc_input"] = pjoin(pathname_dict["list_dir"], "slc_input.csv")

        # error list files
        error_dir = pjoin(proj_dir1, pathname_dict["track_frame"], error_dir1)
        pathname_dict["error_dir"] = error_dir
        pathname_dict["extract_raw_errors"] = pjoin(error_dir, "extract_raw_errors")
        pathname_dict["create_dem_errors"] = pjoin(error_dir, "create_dem_errors")
        pathname_dict["slc_creation_errors"] = pjoin(error_dir, "slc_creation_errors")
        pathname_dict["ml_values_calc_errors"] = pjoin(
            error_dir, "ml_values_calc_errors"
        )
        pathname_dict["multi-look_slc_errors"] = pjoin(
            error_dir, "multi-look_slc_errors"
        )
        pathname_dict["init_baseline_errors"] = pjoin(error_dir, "init_baseline_errors")
        pathname_dict["ref_s1_resize_calc_errors"] = pjoin(
            error_dir, "ref_s1_resize_calc_errors"
        )
        pathname_dict["resize_S1_slc_errors"] = pjoin(error_dir, "resize_S1_slc_errors")
        pathname_dict["subset_S1_slc_errors"] = pjoin(error_dir, "subset_S1_slc_errors")
        pathname_dict["coreg_dem_errors"] = pjoin(error_dir, "coreg_dem_errors")
        pathname_dict["lat-lon_errors"] = pjoin(error_dir, "lat-lon_errors")
        pathname_dict["coreg_slc_errors"] = pjoin(error_dir, "coreg_slc_errors")
        pathname_dict["ifg_errors"] = pjoin(error_dir, "ifg_errors")
        pathname_dict["prec_baseline_errors"] = pjoin(error_dir, "prec_baseline_errors")
        pathname_dict["post_ifg_errors"] = pjoin(error_dir, "post_ifg_errors")

    return pathname_dict


def setup_folders(proc_file):
    """
    A method to setup required directories for InSAR processing.

    :param proc_file: A 'Path' to a proc file.
    """
    dir_names = [
        "proj_dir",
        "checkpoint_dir",
        "list_dir",
        "dem_dir",
        "track_dir",
        "slc_dir",
        "ifg_dir",
        "pdf_dir",
        "batch_job_dir",
        "raw_data_dir",
        "base_dir",
        "pre_proc_dir",
        "results_dir",
        "gamma_dem",
        "error_dir",
        "extract_raw_jobs_dir",
        "baseline_jobs_dir",
        "batch_job_dir",
        "dem_jobs_dir",
        "ifg_jobs_dir",
        "coreg_slc_jobs_dir",
        "ml_slc_jobs_dir",
        "resize_S1_slc_jobs_dir",
        "subset_S1_slc_jobs_dir",
        "slc_jobs_dir",
        "manual_extract_raw_jobs_dir",
        "manual_baseline_jobs_dir",
        "manual_job_dir",
        "manual_dem_jobs_dir",
        "manual_ifg_jobs_dir",
        "manual_coreg_slc_jobs_dir",
        "manual_ml_slc_jobs_dir",
        "manual_resize_S1_slc_jobs_dir",
        "manual_subset_S1_slc_jobs_dir",
        "manual_slc_jobs_dir",
    ]

    # make directory if it does not exist
    dir_dict = get_path(proc_file)
    for dir_name in dir_names:
        if not exists(dir_dict[dir_name]):
            os.makedirs(dir_dict[dir_name], 0o744)


if __name__ == "__main__":
    proc_file = "/g/data/u46/users/pd1813/INSAR/test_insar/T45D_F19.proc"
    directories_setup(proc_file)
