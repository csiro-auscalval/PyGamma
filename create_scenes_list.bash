#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_scenes_list: Creates a list of scene SLCs.                           *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       30/04/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: create_scenes_list.bash [proc_file]"
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
raw_dir_ga=`grep Raw_data_GA= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_data_MDSS= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

scene_list=$proj_dir/$track_dir/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
frame_list=$proj_dir/$track_dir/`grep List_of_frames= $proc_file | cut -d "=" -f 2`

if [ $platform == GA ]; then
    if [ -f $frame_list ]; then 
	while read frame; do
	    if [ ! -z $frame ]; then 
		cd $raw_dir_ga/F$frame
		ls *.tar.gz > tar_list
		if [ -f date_list ]; then # remove old file, just adding to it not creating a new one
		    rm -rf date_list
		fi
		while read list; do
		    if [ ! -z $list ]; then
			date=`echo $list | awk '{print substr($1,1,8)}'`
			echo $date >> date_list
		    fi
		done < tar_list
		sort -n date_list > $scene_list
		rm -rf tar_list date_list
	    fi
	done < $frame_list
    else
	cd $raw_dir_ga
	ls *.tar.gz > tar_list
	if [ -f date_list ]; then # remove old file, just adding to it not creating a new one
	    rm -rf date_list
	fi
	while read list; do
	    if [ ! -z $list ]; then
		date=`echo $list | awk '{print substr($1,1,8)}'`
		echo $date >> date_list
	    fi
	done < tar_list
	sort -n date_list > $scene_list
	rm -rf tar_list date_list
    fi


else 
    cd $proj_dir/$track_dir
    if [ -f $frame_list ]; then # if frames exist
	while read frame; do
	    if [ ! -z $frame ]; then 
		mdss ls $raw_dir_mdss/F$frame < /dev/null > tar_list # /dev/null allows mdss command to work properly in loop
		echo >> tar_list # adds carriage return to last line of file (required for loop to work)
		if [ -f date_list ]; then # remove old file, just adding to it not creating a new one
		    rm -rf date_list
		fi
		while read list; do
		    if [ ! -z $list ]; then
			date=`echo $list | awk '{print substr($1,1,8)}'`
			echo $date >> date_list
		    fi
		done < tar_list
		sort -n date_list > $scene_list
		rm -rf tar_list date_list
	    fi
	done < $frame_list
    else
	mdss ls $raw_dir_mdss < /dev/null > tar_list # /dev/null allows mdss command to work properly in loop
	if [ -f date_list ]; then # remove old file, just adding to it not creating a new one
	    rm -rf date_list
	fi
	while read list; do
	    if [ ! -z $list ]; then
		date=`echo $list | awk '{print substr($1,1,8)}'`
		echo $date >> date_list
	    fi
	done < tar_list
	sort -n date_list > $scene_list
	rm -rf tar_list date_list
    fi
fi
