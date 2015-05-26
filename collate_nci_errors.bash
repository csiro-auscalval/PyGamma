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
    echo "* author: Sarah Lawrie @ GA       26/05/2015, v1.0                            *"
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

if [ $do_slc == yes -o $add_slc == yes ]; then
    dir=$proj_dir/$track_dir/batch_scripts/slc_jobs
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
elif [ $coregister_dem == yes ]; then
    dir=$proj_dir/$track_dir/batch_scripts/dem_jobs
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
elif [ $coregister == yes -o $coregister_add == yes ]; then
    dir=$proj_dir/$track_dir/batch_scripts/coreg_slc_jobs
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
elif [ $do_ifms == yes -o $do_add_ifms == yes ]; then
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
else
    :
fi

