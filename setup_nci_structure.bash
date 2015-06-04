#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* setup_nci_structure: Creates project directories in preparation for         *"
    echo "*                      GAMMA processing.                                      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       27/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: setup_nci_structure.bash [proc_file]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2
echo "" 1>&2
echo "Setup Directory Structure" 1>&2
echo "" 1>&2

cd $proj_dir

# Move lists if they exist to track directory
if [ -f frame.list ]; then
    mv frame.list $track_dir
else
    :
fi
if [ -f beam.list ]; then
    mv beam.list $track_dir
else
    :
fi

frame_list=$proj_dir/$track_dir/`grep List_of_frames= $proc_file | cut -d "=" -f 2`
beam_list=$proj_dir/$track_dir/`grep List_of_beams= $proc_file | cut -d "=" -f 2`

# PBS job directories
mkdir -p $track_dir/batch_scripts/slc_jobs
mkdir -p $track_dir/batch_scripts/dem_jobs
mkdir -p $track_dir/batch_scripts/slc_coreg_jobs
mkdir -p $track_dir/batch_scripts/ifm_jobs

if [ -f $beam_list ]; then # if beams exist
    while read beam; do
	mkdir -p $track_dir/batch_scripts/slc_jobs/$beam
	mkdir -p $track_dir/batch_scripts/dem_jobs/$beam
	mkdir -p $track_dir/batch_scripts/slc_coreg_jobs/$beam
	mkdir -p $track_dir/batch_scripts/ifm_jobs/$beam
	mkdir -p $track_dir/batch_scripts/slc_jobs/$beam/manual_jobs
	mkdir -p $track_dir/batch_scripts/slc_coreg_jobs/$beam/manual_jobs
	mkdir -p $track_dir/batch_scripts/ifm_jobs/$beam/manual_jobs
    done < $beam_list
else # no beam
    mkdir -p $track_dir/batch_scripts/slc_jobs/manual_jobs
    mkdir -p $track_dir/batch_scripts/dem_jobs
    mkdir -p $track_dir/batch_scripts/slc_coreg_jobs/manual_jobs
    mkdir -p $track_dir/batch_scripts/ifm_jobs/manual_jobs
fi

# Raw data directories
mkdir -p raw_data
mkdir -p raw_data/$track_dir
if [ -f $frame_list ]; then
    while read frame; do
	if [ ! -z $frame ]; then # skips any empty lines
	    mkdir -p raw_data/$track_dir/F$frame
	fi
    done < $frame_list
else
    :
fi


# script end 
####################

