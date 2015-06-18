#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_raw_data: Script untars raw data files on the GA network or         *"
    echo "*                   extracts and untars raw data files and DEM files from     *"
    echo "*                   the MDSS (NCI) puts them into the 'raw_data' directory    *"
    echo "*                   for processing with GAMMA.                                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [flag]       0: use 'List_of_scenes' file (default)                 *"
    echo "*                      1: use 'List_of_add_scenes' file                       *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       01/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*******************************************************************************"
    echo -e "Usage: extract_raw_data.bash [proc_file] [flag]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi
if [ $# -lt 2 ]
then
    flag=0
else
    flag=$2
fi

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
raw_dir_ga=`grep Raw_data_GA= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_data_MDSS= $proc_file | cut -d "=" -f 2`
dem_loc_nci=`grep DEM_location_MDSS= $proc_file | cut -d "=" -f 2`
dem_name_nci=`grep DEM_name_NCI= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`

if [ $flag == 0 ]; then
    scene_list=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
else
    scene_list=$proj_dir/$track_dir/lists/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
fi

## Insert scene details top of NCI .e file
    echo "" 1>&2 
    echo "" 1>&2
    echo "PROCESSING_PROJECT: "$project $track_dir 1>&2
    echo "" 1>&2
    echo "Extract Raw Data" 1>&2
    echo "" 1>&2

if [ $platform == GA ]; then # raw data only, DEM already extracted
    if [ -f $frame_list ]; then 
	while read frame; do
	    if [ ! -z $frame ]; then 
		cd $raw_dir_ga/F$frame
		mkdir -p date_dirs
		while read scene; do
		    tar=`echo $scene*.gz`
		    if [ ! -z $tar ]; then
			if [ ! -d $raw_dir_ga/F$frame/date_dirs/$scene ]; then #check if data have already been extracted from tar file
			    tar -xvzf $tar
			    mv $scene date_dirs
			else
			    echo "Raw data already extracted for F"$frame $scene"."
			fi
		    fi
		done < $scene_list
	    fi
	done < $frame_list
    else
    cd $raw_dir_ga
    echo "Extracting raw data..."
    echo " "
    mkdir -p date_dirs
    while read scene; do
	tar=`echo $scene*.gz`
	if [ ! -z $tar ]; then
	    if [ ! -d $raw_dir_ga/date_dirs/$scene ]; then #check if data have already been extracted from tar file
		tar -xvzf $tar
		mv $scene date_dirs
	    else
		echo "Raw data already extracted for "$scene"."
	    fi
	fi
    done < $scene_list
    echo " "
    echo "Raw data extracted for "$project $sensor $track_dir"."
    fi
elif [ $platform == NCI ]; then
    raw_dir=$proj_dir/raw_data # extract raw data
    cd $raw_dir/$track_dir
    if [ -f $frame_list ]; then # if frames exist
	while read frame; do
	    if [ ! -z $frame ]; then # skips any empty lines
		while read scene; do
		    tar=$scene"_"$sensor"_"$track_dir"_F"$frame.tar.gz
		    if [ ! -z $tar ]; then
			if [ ! -d $raw_dir/$track_dir/F$frame/$scene ]; then #check if data have already been extracted from tar file
			    mdss get $raw_dir_mdss/F$frame/$tar < /dev/null $raw_dir/$track_dir/F$frame # /dev/null allows mdss command to work properly in loop
			    cd $raw_dir/$track_dir/F$frame
			    tar -xvzf $tar
			    rm -rf $tar
			else
			    :
			fi
		    else
			:
		    fi
		done < $scene_list
	    fi
	done < $frame_list
    else # no frames exist
	while read scene; do
	    tar=$scene"_"$sensor"_"$track_dir.tar.gz
	    if [ ! -z $tar ]; then
		if [ ! -d $raw_dir/$track_dir/$scene ]; then #check if data have already been extracted from tar file
		    mdss get $raw_dir_mdss/$tar < /dev/null $raw_dir/$track_dir # /dev/null allows mdss command to work properly in loop
		    cd $raw_dir/$track_dir
		    tar -xvzf $tar
		    rm -rf $tar
		else
		    :
		fi
	    else
		:
	    fi
	done < $scene_list
    fi
   dem_dir=$proj_dir/gamma_dem # extract DEM
   cd $proj_dir
   if [ ! -e $dem_dir/$dem_name_nci ]; then
       dem=`echo $dem_name_nci | cut -d'.' -f1` 
       tar=$dem.tar.gz
       mdss get $dem_loc_nci/$tar < /dev/null $proj_dir # /dev/null allows mdss command to work properly in loop
       tar -xvzf $tar
       rm -rf $tar
       cd $dem_dir
       if [ -f $dem.txt ]; then # if acsii file of DEM exists in tar file
	   rm -rf $dem.txt
       fi
   else
       :
   fi
else
    :
fi


# script end 
####################
