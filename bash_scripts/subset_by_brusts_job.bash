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

##########################   SUBSET SENTINEL-1 BY BURSTS  ##########################

if [ $sensor == S1 ]; then
    if [ $do_s1_subset == yes ]; then
	    s1_pbs_job_dirs
	    mkdir -p $subset_batch_dir
	    mkdir -p $subset_manual_dir

        cd $subset_batch_dir

        if [ -e all_subset_s1_job_ids ]; then
            echo "Sentinel-1 data already subsetted by bursts."
            echo ""
        else
            echo ""
            echo "Subsetting Sentinel-1 SLCs by bursts ..."
            rm -f list # temp file used to collate all PBS job numbers to dependency list

            nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
            echo Need to process $nlines files

                # PBS parameters
            wt1=`echo $resize_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single process_slc in minutes
            pbs_job_prefix=subset_s1_
            script=process_S1_SLC.bash
            script_type=subset #slc for full SLCs (all sensors), subset for subset Sentinel-1 SLCs
            depend_job=0  # if no dependency, needs to zero
            depend_type=-
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
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $subset_batch_dir $script_type jobs1 steps1 j
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $subset_batch_dir $script_type jobs2 steps2 jobs1
            } < $scene_list

                # Create manual PBS jobs
            cd $subset_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            depend_job=0
            j=0
            {
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $subset_manual_dir $script_type jobs1 steps1 j
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $subset_manual_dir $script_type jobs2 steps2 jobs1
            } < $scene_list

            # Create preview PDF of images to view subsetted results
            cd $subset_batch_dir
            depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
            depend_type=afterok
            job_type=1
            echo ""
            echo "Plotting preview of subsetted Sentinel-1 SLCs ..."
            pbs_job_prefix1=plot_subset_s1
            plot_type=subset_slc
            script=plot_preview_pdfs.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix1 $nci_project $subset_batch_dir $img_walltime $img_mem $img_ncpus $exp_queue $depend_job $depend_type $job_type $plot_type $script
            }

            # Error collation
            echo ""
            echo "Preparing error collation for subsetting Sentinel-1 SLCs..."
            depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
            depend_type=afterany
            job_type=1
            pbs_job_prefix2=subset_err
            err_type=7
            script=collate_nci_errors.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $subset_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
            }
            # clean up PBS job dir
            cd $subset_batch_dir
            rm -rf list* $pbs_job_prefix*"job_id"
        fi

    elif [ $do_s1_subset == no ]; then
	    echo "Option to subset Sentinel-1 SLCs not selected."
	    echo ""
    else
	:
    fi
else
    :
fi