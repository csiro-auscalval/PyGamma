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

##########################   RESIZE SENTINEL-1   ##########################

if [ $sensor == S1 ]; then
    if [ $do_s1_resize == yes ]; then
	s1_pbs_job_dirs
	mkdir -p $resize_batch_dir
	mkdir -p $resize_manual_dir

	cd $resize_batch_dir
	if [ -e all_resize_s1_job_ids ]; then
	    echo "Sentinel-1 data already resized."
	    echo ""
	else
		echo "Resizing Sentinel-1 SLCs ..."
		depend_job=0  # no dependency if restarted

		cd $resize_batch_dir

		rm -f list # temp file used to collate all PBS job numbers to dependency list

		nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
		echo Need to process $nlines files

                # PBS parameters
		wt1=`echo $resize_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single process_slc in minutes
		pbs_job_prefix=resize_s1_
		script=resize_S1_SLC.bash
		script_type=-
		depend_type=afterok
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
		    multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $resize_batch_dir $script_type jobs1 steps1 j
		    multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $resize_batch_dir $script_type jobs2 steps2 jobs1
		} < $scene_list

                # Create manual PBS jobs
		cd $resize_manual_dir
		job_type=2 #1 for batch job, 2 for manual job
		depend_job=0
		j=0
		{
		    multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $resize_manual_dir $script_type jobs1 steps1 j
		    multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $resize_mem $resize_ncpus $queue $script $depend_job $depend_type $job_type $resize_manual_dir $script_type jobs2 steps2 jobs1
		} < $scene_list

                # Create preview PDF of images determine shape and size
		cd $resize_batch_dir
		depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
		depend_type=afterok
		job_type=1
		echo ""
		echo "Plotting preview of resized Sentinel-1 SLCs ..."
		pbs_job_prefix1=plot_resized_s1
		plot_type=resize_slc
		script=plot_preview_pdfs.bash
		{
		    single_job $pbs_run_loc $pbs_job_prefix1 $nci_project $resize_batch_dir $img_walltime $img_mem $img_ncpus $exp_queue $depend_job $depend_type $job_type $plot_type $script
		}

                # Error collation
		echo ""
		echo "Preparing error collation for resizing Sentinel-1 SLCs..."
		depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
		depend_type=afterany
		job_type=1
		pbs_job_prefix2=resize_err
		err_type=8
		script=collate_nci_errors.bash
		{
		    single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $resize_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
		}

                # clean up PBS job dir
		cd $resize_batch_dir
		rm -rf list* $pbs_job_prefix*"job_id"
	fi
    elif [ $do_s1_resize == no ]; then
	echo "Option to resize Sentinel-1 SLCs not selected."
	echo ""
    else
	:
    fi
else
    :
fi