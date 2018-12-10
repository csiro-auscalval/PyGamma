#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_slc_data: script used to set up pipeline for create slc data         *"
    echo "*                                        	                                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             							        *"
    echo "*******************************************************************************"
    echo -e "Usage: initial_setup.bash [proc_file]"
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

# Calculate multi-looking values
cd $slc_batch_dir
if [ -e ml_values_job_id ]; then
    echo "multi-looked values already calculated."
    echo ""
else
    if [ $rlks == "auto" -a $alks == "auto" ]; then
        depend_job=0
        depend_type=-
        job_type=1 #1 for batch job, 2 for manual job
        pbs_job_prefix3=ml_values
        echo ""
        echo "Calculating multi-looking values ..."
        script_type=-
        script=calc_multi-look_values.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $slc_batch_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }

        # Create manual PBS jobs
        cd $slc_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        {
            single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $slc_manual_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }

        # Error collation for calculating multi-looking values
        cd $slc_batch_dir
        echo ""
        echo "Preparing error collation for calculating multi-looking values ..."
        depend_job=`sed s/.r-man2// $pbs_job_prefix3"_job_id"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix4=ml_values_err
        err_type=4
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix4 $nci_project $slc_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }

    elif [[ $rlks =~ ^-?[0-9]+$ ]] && [[ $alks =~ ^-?[0-9]+$ ]]; then
        echo "Multi-looking values already calculated."
    else
        echo "Multi-look values not valid, check and re-process."
    fi
fi

# Multi-look full SLCs
cd $ml_batch_dir

if [ -e all_ml_slc_job_ids ]; then
    echo "SLCs already multi-looked."
    echo ""
else
    echo ""
    echo "Multi-looking SLCs ..."
    rm -f list # temp file used to collate all PBS job numbers to dependency list

    nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
    echo Need to process $nlines files
    # PBS parameters
    wt1=`echo $ml_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single slc in minutes
    pbs_job_prefix5=ml_slc_
    script=multi-look_SLCs.bash
    script_type=-
    pbs_job_prefix=slc_
    if [ $rlks == "auto" -a $alks == "auto" ]; then
        depend_job=`sed s/.r-man2// $slc_batch_dir/$pbs_job_prefix3"_job_id"`
        depend_type=afterok
    elif [[ $rlks =~ ^-?[0-9]+$ ]] && [[ $alks =~ ^-?[0-9]+$ ]]; then
        depend_job=`sed s/.r-man2// $slc_batch_dir/"all_"$pbs_job_prefix"job_ids"`
        depend_type=afterok
    else
        :
    fi
    job_type=1 #1 for batch job, 2 for manual job

    # Work out number of jobs to run within maximum number of jobs allowed and create jobs
    if [ $nlines -le $minjobs ]; then
        jobs1=$nlines
        steps1=1
        jobs2=0
        steps2=0
    else
        steps2=$((nlines/minjobs))
        steps1=$((nlines%minjobs))
        jobs1=$steps1
        steps1=$((steps2+1))
        jobs2=$((minjobs-jobs1))
    fi
    echo Preparing to run $jobs1 jobs with $steps1 steps and $jobs2 jobs with $steps2 steps processing $((jobs1*steps1+jobs2*steps2)) files
    j=0
    {
        multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_batch_dir $script_type jobs1 steps1 j
        multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_batch_dir $script_type jobs2 steps2 jobs1
    } < $scene_list

    # Create manual PBS jobs
    cd $ml_manual_dir
    job_type=2 #1 for batch job, 2 for manual job
    depend_job=0
    j=0
    {
        multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_manual_dir $script_type jobs1 steps1 j
        multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_manual_dir $script_type jobs2 steps2 jobs1
    } < $scene_list

    # Error collation
    cd $ml_batch_dir
    echo ""
    echo "Preparing error collation for multi-looking SLCs ..."
    depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix5"job_ids"`
    depend_type=afterany
    job_type=1
    pbs_job_prefix6=multi_err
    err_type=5
    script=collate_nci_errors.bash
    {
        single_job $pbs_run_loc $pbs_job_prefix6 $nci_project $ml_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
    }
        # clean up PBS job dir
    cd $ml_batch_dir
    rm -rf list* $pbs_job_prefix5*"job_id"
fi
