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
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $scene

######################################################################

pbs_job_dirs
final_file_loc
echo "This is slc batch dir"
echo $slc_batch_dir

echo "This is the name of proc_file moved to proj_dir"
proc_file="$(basename -- $proc_file)"
echo $proc_file

if [ $coreg_dem == yes ]; then
    cd $dem_batch_dir
    if [ -e coreg_dem_job_id ]; then
        echo "DEM coregistration already completed."
    else
        echo ""
        echo "Coregistering DEM to master SLC ..."
        cd $dem_batch_dir
        rm -f list # temp file used to collate all PBS job numbers to dependency list

        # PBS parameters
        depend_job=0  # no dependency
        depend_type=-
        job_type=1 #1 for batch job, 2 for manual job
        pbs_job_prefix=coreg_dem
        script_type=-
        script=coregister_DEM.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix $nci_project $dem_batch_dir $dem_walltime $dem_mem $dem_ncpus $queue $depend_job $depend_type $job_type $script_type $script
        }

        # Create manual PBS jobs
        cd $dem_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        {
            single_job $pbs_run_loc $pbs_job_prefix $nci_project $dem_manual_dir $dem_walltime $dem_mem $dem_ncpus $queue $depend_job $depend_type $job_type $script_type $script
        }
        # Error collation for DEM coregistration
        cd $dem_batch_dir
        echo ""
        echo "Preparing error collation for DEM coregistation to master SLC ..."
        depend_job=`sed s/.r-man2// $pbs_job_prefix"_job_id"`
        depend_type=afterany
        job_type=1 #1 for batch job, 2 for manual job
        pbs_job_prefix1=coreg_dem_err
        err_type=10
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix1 $nci_project $dem_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }

        # If STAMPS post processing, calculate lat-lon for each SAR pixel
        if [ $post_method == 'stamps' ]; then
            depend_job=`sed s/.r-man2// $pbs_job_prefix"_job_id"`
            depend_type=afterok
            job_type=1 #1 for batch job, 2 for manual job
            pbs_job_prefix2=calc_lat_lon
            echo ""
            echo "Calculating latitude and longitude values for each pixel ..."
            script_type=-
            script=calc_lat_lon.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $dem_batch_dir $pix_walltime $pix_mem $pix_ncpus $queue $depend_job $depend_type $job_type $script_type $script
            }

            # Create manual PBS jobs
            cd $dem_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            {
                single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $dem_manual_dir $pix_walltime $pix_mem $pix_ncpus $queue $depend_job $depend_type $job_type $script_type $script
            }

            # Error collation for calculating lat-lon for each SAR pixel
            cd $dem_batch_dir
            echo ""
            echo "Preparing error collation for calculating latitude and longitude values for each pixel ..."
            depend_job=`sed s/.r-man2// $pbs_job_prefix2"_job_id"`
            depend_type=afterany
            job_type=1
            pbs_job_prefix3=lat_lon_values_err
            err_type=11
            script=collate_nci_errors.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $dem_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
            }
        fi
    fi
elif [ $coreg_dem == no ]; then
    echo "Option to coregister DEM to master SLC not selected."
    echo ""
else
    :
fi

