#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* collate_nci_errors: Collates errors from SLC generation, slave              *"
    echo "*                     coregistration and interferogram processing on the NCI  *"
    echo "*                     into one file.                                          *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [type]       type of error checking to be done (eg. 1=slc creation, *"
    echo "*                      2=ref dem creation, 3=slc coregistration, 4=ifm        *"
    echo "*                      creation, 5=additional slc creation, 6=additional      *"
    echo "*                      slc coregistration, 7=additional ifm creation)         *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       27/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: collate_nci_errors.bash [proc_file] [type]"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
type=$2

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`

beam_list=$proj_dir/$track_dir/`grep List_of_beams= $proc_file | cut -d "=" -f 2`

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
echo "" 1>&2

batch_dir=$proj_dir/$track_dir/batch_scripts

if [ $type -eq 1 ]; then
    dir=$batch_dir/slc_jobs
    cd $dir
    echo "Collating Errors from SLC Creation" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    error_list=$dir/$project"_"$track_dir"_"$beam_num"_slc_errors.list"
	    if [ -f $error_list ]; then
		rm -rf $error_list
	    else
		:
	    fi
	    cd $beam_num
	    ls *.e* > list
	    while read error; do
		if [ ! -z $error ]; then
		    less $error > temp
		    paste temp >> $error_list
		    rm -rf temp
		fi
	    done < list
	    rm -rf list
	    cd $dir
	done < $beam_list
    else
	error_list=$dir/$project"_"$track_dir"_slc_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls *.e* > list
	while read error; do
	    if [ ! -z $error ]; then
		less $error > temp
		paste temp >> $error_list
		rm -rf temp
	    fi
	done < list
	rm -rf list
    fi
if [ $type -eq 2 ]; then
    dir=$batch_dir/dem_jobs
    cd $dir
    echo "Collating Errors from Make Reference Master DEM" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    error_list=$dir/$project"_"$track_dir"_"$beam_num"_dem_errors.list"
	    if [ -f $error_list ]; then
		rm -rf $error_list
	    else
		:
	    fi
	    cd $beam_num
	    ls *.e* > list
	    while read error; do
		if [ ! -z $error ]; then
		    less $error > temp
		    paste temp >> $error_list
		    rm -rf temp
		fi
	    done < list
	    rm -rf list
	    cd $dir
	done < $beam_list
    else
	error_list=$dir/$project"_"$track_dir"_dem_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls *.e* > list
	while read error; do
	    if [ ! -z $error ]; then
		less $error > temp
		paste temp >> $error_list
		rm -rf temp
	    fi
	done < list
	rm -rf list
    fi
if [ $type -eq 3 ]; then
    dir=$batch_dir/slc_coreg_jobs
    cd $dir
    echo "Collating Errors from SLC Coregistration" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    error_list=$dir/$project"_"$track_dir"_"$beam_num"_slc_coreg_errors.list"
	    if [ -f $error_list ]; then
		rm -rf $error_list
	    else
		:
	    fi
	    cd $beam_num
	    ls *.e* > list
	    while read error; do
		if [ ! -z $error ]; then
		    less $error > temp
		    paste temp >> $error_list
		    rm -rf temp
		fi
	    done < list
	    rm -rf list
	    cd $dir
	done < $beam_list
    else
	error_list=$dir/$project"_"$track_dir"_slc_coreg_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls *.e* > list
	while read error; do
	    if [ ! -z $error ]; then
		less $error > temp
		paste temp >> $error_list
		rm -rf temp
	    fi
	done < list
	rm -rf list
    fi
if [ $type -eq 4 ]; then
    dir=$batch_dir/ifm_jobs
    dir=$proj_dir/$track_dir/batch_scripts/ifm_jobs
    cd $dir
    echo "Collating Errors from Interferogram Creation" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    error_list=$dir/$project"_"$track_dir"_"$beam_num"_ifm_errors.list"
	    if [ -f $error_list ]; then
		rm -rf $error_list
	    else
		:
	    fi
	    cd $beam_num
	    ls *.e* > list
	    while read error; do
		if [ ! -z $error ]; then
		    less $error > temp
		    paste temp >> $error_list
		    rm -rf temp
		fi
	    done < list
	    rm -rf list
	    cd $dir
	done < $beam_list
    else
	error_list=$dir/$project"_"$track_dir"_ifm_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls *.e* > list
	while read error; do
	    if [ ! -z $error ]; then
		less $error > temp
		paste temp >> $error_list
		rm -rf temp
	    fi
	done < list
	rm -rf list
    fi
if [ $type -eq 5 ]; then
    dir=$batch_dir/xxxx
if [ $type -eq 6 ]; then
    dir=$batch_dir/xxxx
if [ $type -eq 7 ]; then
    dir=$batch_dir/xxxx
else
    :
fi

