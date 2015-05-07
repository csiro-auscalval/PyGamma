#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* collate_nci_errors: Collates errors from SLC generation, slave              *"
    echo "*                     coregistration and interferogram processing on the NCI  *"
    echo "*                     into one file.                                          *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       07/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: collate_nci_errors.bash [proc_file]"
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
do_slc=`grep Do_SLC= $proc_file | cut -d "=" -f 2`
coregister=`grep Coregister_slaves= $proc_file | cut -d "=" -f 2`
do_ifms=`grep Process_ifms= $proc_file | cut -d "=" -f 2`
add_slc=`grep Add_new_SLC= $proc_file | cut -d "=" -f 2`
coregister_add=`grep Coregister_add_slaves= $proc_file | cut -d "=" -f 2`
do_add_ifms=`grep Process_add_ifms= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    :
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2


if [ $do_slc == yes -o $add_slc == yes ]; then
    cd $proj_dir/$track_dir/batch_scripts
    error_list=$project"_"$track_dir"_slc_errors.list"
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    ls slc_*.e* > list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list
elif [ $coregister == yes -o $coregister_add == yes ]; then
    cd $proj_dir/$track_dir/batch_scripts
    error_list=$project"_"$track_dir"_slc_coreg_errors.list"
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    ls co_slc_*.e* > list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list
elif [ $do_ifms == yes -o $do_add_ifms == yes ]; then
    cd $proj_dir/$track_dir/batch_scripts
    error_list=$project"_"$track_dir"_ifm_errors.list"
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    ls ifm_*-*.e* > list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list
else
    :
if

