#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_resize_sentinel_scene_job: script used in processing sentinel resize   *"
    echo "*                                        	                                    *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             							                                    *"
    echo "*******************************************************************************"
    echo -e "Usage: calc_resize_sentinel_scene_job.bash [proc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1

##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $scene

######################################################################
pbs_job_dirs
final_file_loc
proc_file="$(basename -- $proc_file)"

# Calculate Sentinel-1 resizing reference scene
if [ $do_s1_resize == 'yes' ]; then
    if [ $s1_resize_ref == "auto" ]; then # ref scene not calculated
        cd $slc_batch_dir
        depend_job=0
        depend_type=-
        job_type=1 #1 for batch job, 2 for manual job
        pbs_job_prefix4=s1_resize_ref
        echo ""
        echo "Calculating Sentinel-1 resizing reference scene ..."
        script_type=-
        script=calc_resize_S1_ref_scene.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix4 $nci_project $slc_batch_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }

        # Create manual PBS jobs
        cd $slc_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        {
            single_job $pbs_run_loc $pbs_job_prefix4 $nci_project $slc_manual_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }

        # Error collation for calculating Sentinel-1 resizing reference scene
        cd $slc_batch_dir
        echo ""
        echo "Preparing error collation for calculating Sentinel-1 resizing reference scene ..."
        depend_job=`sed s/.r-man2// $pbs_job_prefix4"_job_id"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix5=s1_ref_err
        err_type=7
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix5 $nci_project $slc_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }

    elif [[ $s1_resize_ref =~ ^-?[0-9]+$ ]]; then
        echo ""
        echo "Sentinel-1 resizing reference scene already calculated."
    else
        echo ""
        echo "Sentinel-1 resizing reference scene not valid, check and re-process."
    fi
else
    :
fi

