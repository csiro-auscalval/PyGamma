#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* collate_nci_slc_errors: Collates errors from processing SLCs on the NCI     *"
    echo "*                         into one file.                                      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       01/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: collate_nci_slc_errors.bash [proc_file]"
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
    :
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2


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