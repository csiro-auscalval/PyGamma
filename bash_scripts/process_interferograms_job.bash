#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* initial_setup: Initial setup scripts used to set up directory and files     *"
    echo "*                 used throughout processing pipeline                         *"
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

if [ $do_ifgs == yes ]; then
    cd $ifg_batch_dir
    if [ -e all_ifg_job_ids ]; then
	    echo "Interferogram generation already completed."
    else
        rm -f list # temp file used to collate all PBS job numbers to dependency list
        depend_job=0
	    echo ""
	    echo "Generating interferograms ..."

        nlines=`cat $ifg_list | sed '/^\s*$/d' | wc -l`
        echo Need to process $nlines files

        # PBS parameters
        wt1=`echo $ifg_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single process_slc in minutes
        pbs_job_prefix=ifg_
        script=process_ifg.bash
        script_type=-
        depend_type=-
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
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $ifg_mem $ifg_ncpus $queue $script $depend_job $depend_type $job_type $ifg_batch_dir $script_type jobs1 steps1 j
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $ifg_mem $ifg_ncpus $queue $script $depend_job $depend_type $job_type $ifg_batch_dir $script_type jobs2 steps2 jobs1
        } < $ifg_list

            # Create manual PBS jobs
        cd $ifg_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        j=0
        {
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $ifg_mem $ifg_ncpus $queue $script $depend_job $depend_type $job_type $ifg_manual_dir $script_type jobs1 steps1 j
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $ifg_mem $ifg_ncpus $queue $script $depend_job $depend_type $job_type $ifg_manual_dir $script_type jobs2 steps2 jobs1
        } < $ifg_list

        # Create preview PDF of interferograms
        cd $ifg_batch_dir
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterok
        job_type=1
        echo ""
        echo "Plotting preview of interferograms ..."
        pbs_job_prefix1=plot_ifg
        plot_type=ifg
        script=plot_preview_pdfs.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix1 $nci_project $ifg_batch_dir $img_walltime $img_mem $img_ncpus $exp_queue $depend_job $depend_type $job_type $plot_type $script
        }

            # Error collation for interferogram generation
        cd $ifg_batch_dir
        echo ""
        echo "Preparing error collation for interferogram generation ..."
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix2=ifg_err
        err_type=11
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $ifg_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }

        # clean up PBS job dir
        cd $ifg_batch_dir
        rm -rf list* $pbs_job_prefix*"_job_id"

        # Calculate precision baselines
        cd $base_batch_dir
        if [ -e prec_base_job_id ]; then
            echo "Precision baselines already calculated ."
            echo ""
        else
            depend_job=`sed s/.r-man2// $ifg_batch_dir/"all_"$pbs_job_prefix"job_ids"`
            depend_type=afterok
            job_type=1 #1 for batch job, 2 for manual job
            pbs_job_prefix3=prec_base
            echo ""
            echo "Calculating precision baselines ..."
            script_type=precision
            script=calc_baselines.py
            {
            single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $base_batch_dir $base_walltime $base_mem $base_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
            }

                # Create manual PBS jobs
            cd $base_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            depend_job=0
            {
            single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $base_manual_dir $base_walltime $base_mem $base_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
            }

                # Error collation for calculating precision baselines
            cd $base_batch_dir
            echo ""
            echo "Preparing error collation for calculating precision baselines ..."
            depend_job=`sed s/.r-man2// $pbs_job_prefix3"_job_id"`
            depend_type=afterany
            job_type=1
            pbs_job_prefix4=prec_base_err
            err_type=12
            script=collate_nci_errors.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix4 $nci_project $base_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
            }
        fi

        # Post interferogram processing
        cd $ifg_batch_dir
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterok
        job_type=1 #1 for batch job, 2 for manual job
        pbs_job_prefix5=post_ifg
        echo ""
        echo "Collating files for post processing ..."
        script_type=-
        script=post_ifg_processing.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix5 $nci_project $ifg_batch_dir $post_walltime $post_mem $post_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }

            # Create manual PBS jobs
        cd $ifg_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        {
            single_job $pbs_run_loc $pbs_job_prefix5 $nci_project $ifg_manual_dir $post_walltime $post_mem $post_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }

            # Error collation for post processing
        cd $ifg_batch_dir
        echo ""
        echo "Preparing error collation for collating files for post processing ..."
        depend_job=`sed s/.r-man2// $pbs_job_prefix5"_job_id"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix6=post_ifg_err
        err_type=13
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix6 $nci_project $ifg_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }
    fi
elif [ $do_ifgs == no ]; then
    echo "Option to generate interferograms not selected."
    echo ""
else
    :
fi
