#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_ifms_list: Creates a list of all possible interferogram combinations *"
    echo "*                   from the scenes list.                                     *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       30/04/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: create_ifms_list.bash [proc_file]"
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
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
do_add_ifms=`grep Process_add_ifms= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir/$track_dir

scene_list=$proj_dir/$track_dir/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
slave_list=$proj_dir/$track_dir/`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
ifm_list=$proj_dir/$track_dir/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`  

## Identify if doing initial ifm list or updated ifm list with additional scenes
if [ $do_add_ifms == yes ]; then
    add_scene_list=$proj_dir/$track_dir/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
    add_slave_list=$proj_dir/$track_dir/`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`
    cp $ifm_list org_ifms.list
# update scenes and slave lists
    cp $scene_list org_scenes1.list
    cat $add_scene_list >> org_scenes1.list
    sed '/^$/d' org_scenes1.list > org_scenes.list # removes any blank lines
    awk ''!'x[$0]++' org_scenes.list > $scene_list # removes any duplicate scene dates
    rm -rf org_scenes1.list org_scenes.list
    cp $slave_list org_slaves1.list
    cat $add_slave_list >> org_slaves1.list
    sed '/^$/d' org_slaves1.list > org_slaves.list # removes any blank lines
    awk ''!'x[$0]++' org_slaves.list > $slave_list # removes any duplicate scene dates
    rm -rf org_slaves1.list org_slaves.list
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
		echo $ifm >> $ifm_list
	    fi
	done < $list
    fi
done < dates.list

## File clean up
rm -rf *_master *_master_keep_list *_initial_ifm_list dates.list master.list initial_ifm.list


## Identify new interferograms (not in original ifm list)
if [ $do_add_ifms == yes ]; then
    add_ifm_list=$proj_dir/$track_dir/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`
    comm -13 org_ifms.list $ifm_list > $add_ifm_list
    rm -rf org_ifms.list
else
    :
fi

## number of interferograms, split list if greater than 190 records (for NCI processing)

if [ $platform == NCI ]; then
    num_ifms=`cat $ifms_list | sed '/^\s*$/d' | wc -l`
    if [ $num_ifms -le 190 ]; then
	echo $ifm_list > ifm_files.list
    elif [ $num_ifms -gt 190 ]; then
	split -dl 190 $ifm_list $ifm_list"_"
	mv $ifm_list all_$ifm_list
	echo ifm.list_* > temp
	cat temp | tr " " "\n" > ifm_files.list
    else
	:
    fi
else
    :
fi



