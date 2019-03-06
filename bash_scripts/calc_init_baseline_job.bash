#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_init_baseline_job: script used to process initial baseline computation *"
    echo "*                         job           	                                    *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             							                                    *"
    echo "*******************************************************************************"
    echo -e "Usage: calc_init_baseline_job.bash [proc_file]"
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

# Calculate intital baselines
cd $base_batch_dir

if [ -e init_base_job_id ]; then
    echo "Initial baselines already calculated ."
    echo ""
else
    depend_job=0
    depend_type=-
    job_type=1 #1 for batch job, 2 for manual job
    pbs_job_prefix7=init_base
    echo ""
    echo "Calculating initial baselines ..."
    script_type=initial
    script=calc_baselines.py
    {
        single_job $pbs_run_loc $pbs_job_prefix7 $nci_project $base_batch_dir $base_walltime $base_mem $base_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
    }

        # Create manual PBS jobs
    cd $base_manual_dir
    job_type=2 #1 for batch job, 2 for manual job
    depend_job=0
    {
        single_job $pbs_run_loc $pbs_job_prefix7 $nci_project $base_manual_dir $base_walltime $base_mem $base_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
    }

        # Error collation for calculating initial baselines
    cd $base_batch_dir
    echo ""
    echo "Preparing error collation for calculating initial baselines ..."
    depend_job=`sed s/.r-man2// $pbs_job_prefix7"_job_id"`
    depend_type=afterany
    job_type=1
    pbs_job_prefix8=init_base_err
    err_type=6
    script=collate_nci_errors.bash
    {
        single_job $pbs_run_loc $pbs_job_prefix8 $nci_project $base_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
    }
fi

