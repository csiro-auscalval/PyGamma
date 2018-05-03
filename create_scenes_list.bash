#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_scenes_list: Creates a list of scene SLCs.                           *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [type]       list type to create (eg. 1=scenes.list or              *"
    echo "*                      2=add_scenes.list)                                     *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*         Sarah Lawrie @ GA       29/01/2016, v1.2                            *"
    echo "*             - add ability to create list from S1 data on the RDSI           *"
    echo "*         Sarah Lawrie @ GA       08/09/2017, v1.3                            *"
    echo "*             - add ability to create frame list for S1 data                  *"
    echo "*******************************************************************************"
    echo -e "Usage: create_scenes_list.bash [proc_file] [type]"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
type=$2

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
raw_dir_ga=`grep Raw_data_GA= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_data_MDSS= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

scene_list=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
add_scene_list=$proj_dir/$track_dir/lists/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`
s1_list=$proj_dir/$track_dir/lists/`grep S1_file_list= $proc_file | cut -d "=" -f 2`
frame_nums=$proj_dir/$track_dir/lists/frame_nums

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2
echo "" 1>&2
echo "Scenes List File Creation" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir
echo ""

list_dir=$proj_dir/$track_dir/lists
cd $list_dir

# copy existing scene list to compare with additional scene list
if [ $type -eq 2 ]; then
    cp $scene_list temp1
    sort temp1 > org_scenes.list
    rm -f temp1
else
    :
fi


echo "Scenes List File Creation" 1>&2
## Create list of scenes
if [ $platform == GA ]; then
    if [ -f $frame_list ]; then 
	while read frame; do
	    if [ ! -z $frame ]; then 
		cd $raw_dir_ga/F$frame
		ls *.tar.gz > tar.list
		if [ -f date.list ]; then # remove old file, just adding to it not creating a new one
		    rm -rf date.list
		fi
		while read list; do
		    if [ ! -z $list ]; then
			date=`echo $list | awk '{print substr($1,1,8)}'`
			echo $date >> date.list
		    fi
		done < tar.list
		sort -n date.list > $scene_list
		rm -rf tar.list date.list
	    fi
	done < $frame_list
    else
	cd $raw_dir_ga
	ls *.tar.gz > tar.list
	if [ -f date.list ]; then # remove old file, just adding to it not creating a new one
	    rm -rf date.list
	fi
	while read list; do
	    if [ ! -z $list ]; then
		date=`echo $list | awk '{print substr($1,1,8)}'`
		echo $date >> date.list
	    fi
	done < tar.list
	sort -n date.list > $scene_list
	rm -rf tar.list date.list
    fi
else ## NCI
    cd $proj_dir/$track_dir
    if [ $sensor != 'S1' ]; then  #not sentinel-1
	if [ -f $frame_list ]; then # if frames exist and not Sentinel-1
	    while read frame; do
		if [ ! -z $frame ]; then 
		    if [ -f date.list ]; then # remove old file, just adding to it not creating a new one
			rm -rf date.list
		    fi
	            #data on MDSS
		    mdss ls $raw_dir_mdss/F$frame/ < /dev/null > tar.list # /dev/null allows mdss command to work properly in loop
		    echo >> tar.list # adds carriage return to last line of file (required for loop to work)
		    # remove any non date data from tar.list (eg. other directory names within frame dir)
		    grep ^1 tar.list > temp
		    grep ^2 tar.list >> temp
		    mv temp tar.list
		    while read list; do
			if [ ! -z $list ]; then
			    date=`echo $list | awk '{print substr($1,1,8)}'`
			    echo $date >> date.list
			fi
		    done < tar.list
		    sort -n date.list > $scene_list
		    rm -rf tar.list date.list
		fi
	    done < $frame_list
	else #no frame list and not Sentinel-1
	    mdss ls $raw_dir_mdss < /dev/null > tar.list # /dev/null allows mdss command to work properly in loop
	    # remove any non date data from tar.list (eg. other directory names within track dir)
	    grep ^1 tar.list > temp
	    grep ^2 tar.list >> temp
	    mv temp tar.list
	    while read list; do
		if [ ! -z $list ]; then
		    date=`echo $list | awk '{print substr($1,1,8)}'`
		    echo $date >> date.list
		fi
	    done < tar.list
	    sort -n date.list > $scene_list
	    rm -rf tar.list date.list
	fi
    else #Sentinel-1 data on RDSI
	if [ -f $s1_list ]; then
	    rm -rf $frame_list #if frame list exists, remove and create new one
	    cp $s1_list $s1_list"_org"
	    rm -rf $s1_list
		# add date to file list
	    while read list; do
		grid_dir=`echo $list | awk '{print $1}'`
		zip=`echo $list | awk '{print $2}'`
		date=`echo $zip | awk '{print substr($1,18,8)}'`
		echo $date $grid_dir $zip >> $s1_list
	    done < $s1_list"_org"
                # count number of times a date occurs
	    awk '{print $1}' $s1_list | uniq -c > temp1
                # add count to each line
	    while read line; do
		max_count=`echo $line | awk '{print $1}'`
		date=`echo $line | awk '{print $2}'`
		if [ $max_count -gt 1 ]; then
		    seq 1 $max_count > temp2
		    sed -n "/^$date/p" $s1_list > temp3
		    paste temp2 temp3 >> temp4
		else
		    echo $max_count > temp2
		    sed -n "/^$date/p" $s1_list > temp3
		    paste temp2 temp3 >> temp4
		fi
	    done < temp1
	    mv -f temp4 $s1_list
	    rm -rf temp*
		# create frame list 
	    awk '{print $1}' $s1_list | sort | uniq > $frame_nums # for creating frame directories under raw data
	    awk '{print $1,$2}' $s1_list > $frame_list
                # create scene list from file list
	    while read list; do
		date=`echo $list | awk '{print $2}'`
		echo $date >> date.list
	    done < $s1_list
	    awk '{print $1}' date.list | sort | uniq > $scene_list 
	    rm -rf date.list
	else
	    echo "No Sentinel-1 data list exists, create list and re-run script"
	fi
    fi
fi

# Create additional scene list
if [ $type -eq 2 ]; then
    cd $list_dir
    echo "Additional Slaves List File Creation" 1>&2
    comm -13 org_scenes.list $scene_list > $add_scene_list
else
    :
fi

# script end 
####################