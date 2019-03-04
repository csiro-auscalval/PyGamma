#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ifm_rerun: list INT subfolders and compare with ifgs.list           *"
    echo "*                    rerun ifg processing for non-existing subfolders         *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA       10/09/2018, v1.0                         *"
    echo "*******************************************************************************"
    echo -e "Usage: process_ifg_rerun [proc_file]"
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
final_file_loc
pbs_job_dirs

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track

######################################################################

# list of ifgs to be rerun
ifg_rerun_list=$ifg_list"_rerun"
if [ -s $ifg_rerun_list ]; then
    rm -f $ifg_rerun_list
fi

# read ifg.list file and check for missing folders
while read ifg; do
    # replace , by -
    ifgdir=${ifg/,/-}
    if [ -e $int_dir/$ifgdir ]; then
        # check if flattened interferogram png exists
        if [ ! -s $int_dir/$ifgdir/*flat_eqa_int.png ]; then
            echo "Flattened IFG result image does not exist for $ifgdir."
            echo $ifg >> $ifg_rerun_list
        fi
    else
        echo "IFG directory does not exist for $ifgdir."
        echo $ifg >> $ifg_rerun_list
    fi
done < $ifg_list

echo ""
echo "Rerunning IFGs..."
echo ""

# rerun non-existing ifgs (if any)
if [ -s $ifg_rerun_list ]; then
    cd $ifg_batch_dir
    rm -f list # temp file used to collate all PBS job numbers to dependency list

    nlines=`cat $ifg_rerun_list | sed '/^\s*$/d' | wc -l`
    echo Need to process $nlines files

    # PBS parameters
    depend_job=0  # if no dependency, needs to zero
    wt1=`echo $ifg_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single process_slc in minutes
    pbs_job_prefix=ifg_
    script=process_ifg.bash
    script_type=-
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
        multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $ifg_mem $ifg_ncpus $queue $script $depend_job $depend_type $job_type $ifg_batch_dir $script_type jobs1 steps1 j
        multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $ifg_mem $ifg_ncpus $queue $script $depend_job $depend_type $job_type $ifg_batch_dir $script_type jobs2 steps2 jobs1
    } < $ifg_rerun_list
fi


# script end
####################

