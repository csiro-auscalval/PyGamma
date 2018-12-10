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
if [ $do_slc == yes ]; then
    cd $slc_batch_dir
    if [ -e all_slc_job_ids ]; then
        echo "SLC data already created."
        echo ""
    else
        echo ""
        echo "Processing full SLCs ..."
        rm -f list # temp file used to collate all PBS job numbers to dependency list

        nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
        echo Need to process $nlines files

        if [ $sensor == PALSAR1 -o $sensor == PALSAR2 ]; then
            sensor=PALSAR
        elif [ $sensor == ERS1 -o $sensor == ERS2 ]; then
            sensor=ERS
        else
            :
        fi

        # PBS parameters
        wt1=`echo $slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single process_slc in minutes
        pbs_job_prefix=slc_
        script="process_"$sensor"_SLC.bash"
        script_type=slc #slc for full SLCs (all sensors), subset for subset Sentinel-1 SLCs
        depend_job=0  # if no dependency, needs to zero

        depend_type=afterok
        job_type=1 #1 for batch job, 2 for manual job

        # Work out number of jobs to run within maximum number of jobs allowed and create jobs
        if [ $nlines -le $maxjobs ]; then
            jobs1=$nlines
            steps1=1
            jobs2=0
            steps2=0
        else
            steps2=$((nlines/maxjobs))
            steps1=$((nlines%maxjobs))
            jobs1=$steps1
            steps1=$((steps2+1))
            jobs2=$((maxjobs-jobs1))
        fi
        echo Preparing to run $jobs1 jobs with $steps1 steps and $jobs2 jobs with $steps2 steps processing $((jobs1*steps1+jobs2*steps2)) files
        j=0
        {
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_batch_dir $script_type jobs1 steps1 j
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_batch_dir $script_type jobs2 steps2 jobs1
        } < $scene_list

        # Create manual PBS jobs
        cd $slc_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        j=0
        {
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_manual_dir $script_type jobs1 steps1 j
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_manual_dir $script_type jobs2 steps2 jobs1
        } < $scene_list

        # Create preview PDF of SLCs
        cd $slc_batch_dir
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterok
        job_type=1
        echo ""
        echo "Plotting preview of full SLCs ..."
        pbs_job_prefix1=plot_full_slc
        plot_type=full_slc
        script=plot_preview_pdfs.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix1 $nci_project $slc_batch_dir $img_walltime $img_mem $img_ncpus $exp_queue $depend_job $depend_type $job_type $plot_type $script
        }

        # Error collation for full SLC creation
        echo ""
        echo "Preparing error collation for full SLC creation ..."
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix2=slc_err
        err_type=3
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $slc_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }

    fi
elif [ $do_slc == no ]; then
    echo "Option to create SLC data not selected."
    echo ""
else
    :
fi

