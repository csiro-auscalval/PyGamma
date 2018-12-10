#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_raw_data: scripts used to extract raw data                          *"
    echo "*                                                                             *"
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

# Create GAMMA DEM
if [ ! -f $gamma_dem_dir/$dem_name.dem ]; then
    if [ $sensor == 'S1' ] && [ $dem_area == 'aust' ]; then
        cd $dem_batch_dir
        depend_job=0
        depend_type=-
        job_type=1 #1 for batch job, 2 for manual job
        pbs_job_prefix2=create_dem
        echo ""
        echo "Creating GAMMA DEM from scene extents ..."
        script_type=-
        script=make_GAMMA_DEM_auto.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $dem_batch_dir $create_dem_walltime $create_dem_mem $create_dem_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }
        # Create manual PBS jobs
        cd $dem_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        {
            single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $dem_manual_dir $create_dem_walltime $create_dem_mem $create_dem_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
        }
        # Error collation for creating GAMMA DEM
        cd $dem_batch_dir
        echo ""
        echo "Preparing error collation for creating GAMMA DEM ..."
        depend_job=`sed s/.r-man2// $pbs_job_prefix2"_job_id"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix3=create_dem_err
        err_type=2
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $dem_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }
    fi
fi

