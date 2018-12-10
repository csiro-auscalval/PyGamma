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
    echo -e "Usage: initial_setup.bash [proc_file] [s1_download_file] "
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi 

proc_file=$1
download_file=$2
echo $proc_file
echo $download_file
##########################   GENERIC SETUP  #########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $scene

#####################################################################
mkdir -p $proj_dir

cp -n $proc_file $proj_dir

proc_file="$(basename -- $proc_file)"
echo $proc_file

cd $proj_dir
## Create processing directories (exc. CR dir as this is not part of standard processing for now, so not created)
mkdir -p $track
mkdir -p $slc_dir
mkdir -p $dem_dir
mkdir -p $int_dir
mkdir -p $base_dir
mkdir -p $list_dir
mkdir -p $error_dir
mkdir -p $pdf_dir
mkdir -p $raw_data_dir
mkdir -p $raw_data_dir/$track
mkdir -p $batch_dir
mkdir -p $manual_dir
mkdir -p $pre_proc_dir
mkdir -p $results_dir

## Create directories for PBS jobs
mkdir -p $batch_dir/extract_raw_jobs
mkdir -p $batch_dir/slc_jobs
mkdir -p $batch_dir/ml_slc_jobs
mkdir -p $batch_dir/baseline_jobs
mkdir -p $batch_dir/dem_jobs
mkdir -p $batch_dir/coreg_slc_jobs
mkdir -p $batch_dir/ifg_jobs
mkdir -p $manual_dir/extract_raw_jobs
mkdir -p $manual_dir/slc_jobs
mkdir -p $manual_dir/ml_slc_jobs
mkdir -p $manual_dir/baseline_jobs
mkdir -p $manual_dir/dem_jobs
mkdir -p $manual_dir/coreg_slc_jobs
mkdir -p $manual_dir/ifg_jobs

## Create directory to store a luigi checkpoints files
mkdir -p $track/checkpoints

echo $frame_list
## move download file to list dir

cp $download_file $list_dir

## PBS job directories
pbs_job_dirs

## Move lists if they exist to project's 'lists' directory
if [ -f $frame_list ]; then
    dos2unix -q $frame_list $frame_list # remove any DOS characters if list was created in Windows
    mv $frame_list $list_dir/$frame_list
else
   :
fi
if [ -f $s1_download_list ]; then
    dos2unix -q $s1_download_list $s1_download_list # remove any DOS characters if list was created in Windows
    sort -k1 -n $s1_download_list > temp1 #sort by date
    mv -f temp1 $s1_download_list
    rm -f temp1
    mv -f $s1_download_list $list_dir/$s1_download_list
else
    :
fi
if [ -f $s1_burst_list ]; then
    dos2unix -q $s1_burst_list $s1_burst_list # remove any DOS characters if list was created in Windows
    mv -f $s1_burst_list $list_dir/$s1_burst_list
else
    :
fi

##Final file locations for processing
final_file_loc

## Create scene list
if [ -f $scene_list ]; then
    echo ""
    echo "Initial setup and scene list creation already completed."
else
    echo "Running initial setup and creating scene list ..."
    create_scenes_list.bash $proj_dir/$proc_file 1
    echo "Initial setup and scene list creation completed."
    echo ""
fi

## Create frame list for Sentinel-1
if [ $sensor == 'S1' ]; then
    if [ -f $s1_download_list ]; then
        if [ ! -f $frame_list ]; then
            echo "Creating Sentinel-1 frame list ..."
            create_S1_frame_list.bash $proj_dir/$proc_file
            echo "Initial setup and scene list creation completed."
            echo ""
        else
            echo "Sentinel-1 frame list already created."
        fi
    else
        echo "Sentinel-1 download list doesn't exist."
    fi
else
    :
fi

## Create frame raw data directories (if required)
# Add carriage return to last line of frame list file if it exists (required for loops to work)
if [ -f $frame_list ]; then
    echo >> $frame_list
else
    :
fi
if [ -f $frame_list ]; then
    if [ $sensor == 'S1' ]; then
        while read frame; do
            frame_num=`echo $frame | awk '{print $2}'`
            count=1
            while [ $count -le $(($frame_num)) ]; do
                mkdir -p raw_data/$track/F$count
                count=$(($count+1))
            done
        done < $frame_list
    else
        while read frame; do
            if [ ! -z $frame ]; then # skips any empty lines
                mkdir -p raw_data/$track/F$frame
            fi
        done < $frame_list
    fi
else
    :
fi

## Check GAMMA DEM exists
if [ ! -f $gamma_dem_dir/$dem_name.dem ]; then
    if [ $sensor == 'S1' ] && [ $dem_area == 'aust' ]; then # auto generated GAMMA DEM
        echo "Need to automatically create GAMMA DEM, this will be done after raw data extraction."
    else
        echo "Extracting GAMMA DEM from MDSS ..."
        mdss get $mdss_dem < /dev/null $proj_dir # /dev/null allows mdss command to work properly in loop
        tar -xvzf $dem_name.tar.gz
        rm -rf $dem_name.tar.gz
        cd $proj_dir
        echo "GAMMA DEM extraction from MDSS completed."
        echo ""
    fi
else
    echo "GAMMA DEM already exists."
    echo ""
fi

