#!/usr/bin/python3

from os.path import join as pjoin


def get_path(proc_file):
    """
    :param proc_file:
        A 'proc_file' which
    :return:
        A 'dict' containing the path names for required processing
        workflow from a which is derived from a 'proc file'
    """
    pathname_dict = {}
    with open(proc_file, 'r') as src:
        for line in src.readlines():
            if line.startswith('NCI_PATH='):
                nci_path = line.split('=')[1].strip()
            if line.startswith('S1_PATH='):
                s1_path = line.split('=')[1].strip()
            if line.startswith('PROJECT='):
                project = line.split('=')[1].strip()
            if line.startswith('SENSOR='):
                sensor = line.split('=')[1].strip()
            if line.startswith('TRACK='):
                track = line.split('=')[1].strip()
            if line.startswith('SLC_DIR='):
                slc_dir1 = line.split('=')[1].strip()
            if line.startswith('DEM_DIR='):
                dem_dir1 = line.split('=')[1].strip()
            if line.startswith('INT_DIR='):
                int_dir1 = line.split('=')[1].strip()
            if line.startswith('REF_MASTER_SCENE='):
                pathname_dict['master_scene'] = line.split('=')[1].strip()
            if line.startswith('CLEAN_UP='):
                pathname_dict['clean_up'] = line.split('=')[1].strip()
            if line.startswith('BASE_DIR='):
                base_dir1 = line.split('=')[1].strip()
            if line.startswith('ERROR_DIR='):
                error_dir1 = line.split('=')[1].strip()
            if line.startswith('BATCH_JOB_DIR='):
                batch_job_dir1 = line.split('=')[1].strip()
            if line.startswith('RAW_DATA_DIR='):
                raw_data_dir1 = line.split('=')[1].strip()
            if line.startswith('LIST_DIR='):
                list_dir1 = line.split('=')[1].strip()
            if line.startswith('PRE_PROC_DIR='):
                pre_proc_dir1 = line.split('=')[1].strip()
            if line.startswith('SCENE_LIST='):
                scene_list = line.split('=')[1].strip()
            if line.startswith('SLAVE_LIST='):
                slave_list = line.split('=')[1].strip()
            if line.startswith('IFG_LIST='):
                ifg_list = line.split('=')[1].strip()
            if line.startswith('S1_DOWNLOAD_LIST='):
                download_list = line.split('=')[1].strip()

        # Project directories
        proj_dir1 = pjoin(nci_path, "INSAR_ANALYSIS", project, sensor, "GAMMA")
        error_dir = pjoin(proj_dir1, track, error_dir1)

        pathname_dict['track'] = track
        pathname_dict['proj_dir'] = proj_dir1
        pathname_dict['checkpoint_dir'] = pjoin(proj_dir1, track, 'checkpoints')
        pathname_dict['list_dir'] = pjoin(proj_dir1, track, list_dir1)
        pathname_dict['dem_dir'] = pjoin(proj_dir1, track, dem_dir1)
        pathname_dict['s1_dir'] = s1_path
        pathname_dict['track_dir'] = pjoin(proj_dir1, track)
        pathname_dict['slc_dir'] = pjoin(proj_dir1, track, slc_dir1)
        pathname_dict['ifg_dir'] = pjoin(proj_dir1, track, int_dir1)
        pathname_dict['batch_job_dir'] = pjoin(proj_dir1, track, batch_job_dir1)
        pathname_dict['raw_data_dir'] = pjoin(proj_dir1, raw_data_dir1, track, 'F1')
        pathname_dict['base_dir'] = pjoin(proj_dir1, track, base_dir1)
        pathname_dict['pre_proc_dir'] = pjoin(proj_dir1, pre_proc_dir1)
        pathname_dict['results_dir'] = pjoin(proj_dir1, track, "results")
        pathname_dict['gamma_dem'] = pjoin(proj_dir1, 'gamma_dem')

        # batch jobs directories
        pathname_dict['extract_raw_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'extract_raw_jobs')
        pathname_dict['baseline_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'baseline_jobs')
        pathname_dict['dem_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'dem_jobs')
        pathname_dict['coreg_slc_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'coreg_slc_jobs')
        pathname_dict['ifg_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'ifg_jobs')
        pathname_dict['ml_slc_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'ml_slc_jobs')
        pathname_dict['resize_S1_slc_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'resize_S1_slc_jobs')
        pathname_dict['subset_S1_slc_jobs_dir'] = pjoin(pathname_dict['batch_job_dir'], 'subset_S1_slc_jobs')

        # Lists
        pathname_dict['scenes_list'] = pjoin(pathname_dict['list_dir'], scene_list)
        pathname_dict['slaves_list'] = pjoin(pathname_dict['list_dir'], slave_list)
        pathname_dict['ifgs_list'] = pjoin(pathname_dict['list_dir'], ifg_list)
        pathname_dict['download_list'] = pjoin(pathname_dict['list_dir'], download_list)

        # error list files
        pathname_dict['extract_raw_errors'] = pjoin(error_dir, 'extract_raw_errors')
        pathname_dict['create_dem_errors'] = pjoin(error_dir, 'create_dem_errors')
        pathname_dict['slc_creation_errors'] = pjoin(error_dir, 'slc_creation_errors')
        pathname_dict['ml_values_calc_errors'] = pjoin(error_dir, 'ml_values_calc_errors')
        pathname_dict['multi-look_slc_errors'] = pjoin(error_dir, 'multi-look_slc_errors')
        pathname_dict['init_baseline_errors'] = pjoin(error_dir, 'init_baseline_errors')
        pathname_dict['ref_s1_resize_calc_errors'] = pjoin(error_dir, 'ref_s1_resize_calc_errors')
        pathname_dict['resize_S1_slc_errors'] = pjoin(error_dir, 'resize_S1_slc_errors')
        pathname_dict['subset_S1_slc_errors'] = pjoin(error_dir, 'subset_S1_slc_errors')
        pathname_dict['coreg_dem_errors'] = pjoin(error_dir, 'coreg_dem_errors')
        pathname_dict['lat-lon_errors'] = pjoin(error_dir, 'lat-lon_errors')
        pathname_dict['coreg_slc_errors'] = pjoin(error_dir, 'coreg_slc_errors')
        pathname_dict['ifg_errors'] = pjoin(error_dir, 'ifg_errors')
        pathname_dict['prec_baseline_errors'] = pjoin(error_dir, 'prec_baseline_errors')
        pathname_dict['post_ifg_errors'] = pjoin(error_dir, 'post_ifg_errors')

    return pathname_dict
