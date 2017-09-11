#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_ifms_list: Creates a list of all possible interferogram combinations *"
    echo "*                   from the scenes list.                                     *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [type]       list type to create (eg. 1=ifms.list or                *"
    echo "*                      2=add_ifms.list)                                       *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       29/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*******************************************************************************"
    echo -e "Usage: create_ifms_list.bash [proc_file] [type]"
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
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
thres=`grep Threshold= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

scene_list=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
slave_list=$proj_dir/$track_dir/lists/`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
ifm_list=$proj_dir/$track_dir/lists/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`  
add_scene_list=$proj_dir/$track_dir/lists/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
add_slave_list=$proj_dir/$track_dir/lists/`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`
add_ifm_list=$proj_dir/$track_dir/lists/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "Interferogram List File Creation" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir
echo ""

list_dir=$proj_dir/$track_dir/lists
cd $list_dir

## Copy existing ifms list to compare with additional ifms list
if [ $type -eq 2 ]; then
    cp $ifm_list temp1
    sort temp1 > org_ifms.list
    rm -f temp1
else
    :
fi

## Make lists of potential slaves for each master date (ie. selected master date excluded from date list)
while read date; do
    if [ ! -z $date ]; then
	sed '/$date/d' $scene_list > $date"_master"
    fi
done < $scene_list
ls *_master > master.list

## Work out which dates in the list is younger than the selected master date
while read list; do
    if [ ! -z $list ]; then
	master=`echo $list | awk '{print substr($1,1,8)}'`
	if [ -f $master"_master_keep_list" ]; then
	    rm -rf $master"_master_keep_list" # remove old file as just adding to it not creating a new one
	fi
	while read date; do
	    if [ ! -z $date ]; then
		if [ $date -gt $master ]; then
		    echo $date >> $master"_master_keep_list"
		fi
	    fi
	done < $scene_list
    fi
done < master.list


## Remove last date master file because it's the youngest date so it can't be a master to any other dates
last_date=`awk 'END{print}' $scene_list`
rm -rf $last_date"_master"
# Revised dates list
ls *_master > dates.list
sed "/$last_date/d" master.list > dates.list 

## Create interferogram list
while read list; do
    if [ ! -z $list ]; then
	master=`echo $list | awk '{print substr($1,1,8)}'`
	if [ -f $master"_initial_ifm_list" ]; then
	    rm -rf $master"_initial_ifm_list" # remove old file as just adding to it not creating a new one
	fi
        keep_list=$master"_master_keep_list"
	while read date; do
	    if [ ! -z $date ]; then
		echo $master","$date >> $master"_initial_ifm_list"
	    fi
	done < $keep_list
    fi
done < dates.list

ls *_initial_ifm_list > initial_ifm.list

if [ -f $ifm_list ]; then
    rm -rf $ifm_list # remove old ifm list file as just adding to it not creating a new one
fi

while read list; do
    if [ ! -z $list ]; then
	master=`echo $list | awk '{print substr($1,1,8)}'`
	list=$master"_initial_ifm_list"
	while read ifm; do
	    if [ ! -z $ifm ]; then
		echo $ifm >> temp_ifm.list
	    fi
	done < $list
    fi
done < dates.list

## Identify which interferograms fall within the temporal baseline threshold 
while read list; do
    if [ ! -z $list ]; then
	mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	let diff=(`date +%s -d $slv`-`date +%s -d $mas`)/86400
	if [ $diff -le $thres ]; then
	    echo $list >> $ifm_list
	else
	    :
	fi
    fi
done < temp_ifm.list

## File clean up
rm -rf *_master *_master_keep_list *_initial_ifm_list dates.list master.list initial_ifm.list temp_ifm.list



# Identify new interferograms (not in original ifm list)
if [ $type -eq 2 ]; then
    cd $list_dir
    echo "Additional Slaves List File Creation" 1>&2
    comm -13 org_ifms.list $ifm_list > $add_ifm_list
else
    :
fi




# script end 
####################

