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


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    :
fi

beam_list=$proj_dir/$track_dir/`grep List_of_beams= $proc_file | cut -d "=" -f 2`

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
	    if [ ! -z $beam_num ]; then
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
	    fi
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
elif [ $type -eq 2 ]; then
    dir=$batch_dir/dem_jobs
    cd $dir
    echo "Collating Errors from Make Reference Master DEM" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
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
	    fi
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
elif [ $type -eq 3 ]; then
    dir=$batch_dir/slc_coreg_jobs
    cd $dir
    echo "Collating Errors from SLC Coregistration" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
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
	    fi
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
elif [ $type -eq 4 ]; then
    dir=$batch_dir/ifm_jobs
    dir=$proj_dir/$track_dir/batch_scripts/ifm_jobs
    ifm_files=$proj_dir/$track_dir/ifm_files.list
    cd $dir
    echo "Collating Errors from Interferogram Creation" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		error_list=$dir/$project"_"$track_dir"_"$beam_num"_ifm_errors.list"
		if [ -f $error_list ]; then
		    rm -rf $error_list
		else
		    :
		fi
		cd $beam_num
		while read list; do
		    if [ ! -z $list ]; then
			for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
			do
			    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
			    array_dir=$dir/$beam_num/$array1
			    cd $array_dir
 			    ls *.e* > _org_list
			    while read err; do # remove unnecessary lines created from float2ascii - creates hundreds of output lines, not errors)
				cp $err temp1
				sed '/^line:/ d ' < temp1 > temp2
				mv temp2 $err
				rm -rf temp1
			    done < org_list
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
			done
		    fi
		done < $ifm_files
	    fi
	done < $beam_list
    else
	error_list=$dir/$project"_"$track_dir"_ifm_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	while read list; do
	    if [ ! -z $list ]; then
		for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
		do
		    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
		    array_dir=$dir/$array1
		    cd $array_dir
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
		done
	    fi
	done < $ifm_files
    fi
elif [ $type -eq 5 ]; then
    dir1=$batch_dir/slc_jobs/add_slc_jobs
    dir2=$batch_dir/slc_jobs
    cd $dir1
    echo "Collating Errors from Additional SLC Creation" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		error_list=$dir2/$project"_"$track_dir"_"$beam_num"_add_slc_errors.list"
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
	    fi
	done < $beam_list
    else
	error_list=$dir2/$project"_"$track_dir"_add_slc_errors.list"
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
elif [ $type -eq 6 ]; then
    dir1=$batch_dir/slc_coreg_jobs/add_slc_coreg_jobs
    dir2=$batch_dir/slc_coreg_jobs
    cd $dir1
    echo "Collating Errors from Additional SLC Coregistration" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		error_list=$dir2/$project"_"$track_dir"_"$beam_num"_add_slc_coreg_errors.list"
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
	    fi
	done < $beam_list
    else
	error_list=$dir2/$project"_"$track_dir"_add_slc_coreg_errors.list"
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
elif [ $type -eq 7 ]; then
    dir1=$batch_dir/ifm_jobs/add_ifm_jobs
    dir2=$batch_dir/ifm_jobs
    ifm_files=$proj_dir/$track_dir/add_ifm_files.list
    cd $dir1
    echo "Collating Errors from Additional Interferogram Creation" 1>&2
    echo "" 1>&2
    if [ -f $beam_list ]; then
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		error_list=$dir/$project"_"$track_dir"_"$beam_num"_add_ifm_errors.list"
		if [ -f $error_list ]; then
		    rm -rf $error_list
		else
		    :
		fi
		cd $beam_num
		while read list; do
		    if [ ! -z $list ]; then
			for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
			do
			    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
			    array_dir=$dir/$beam_num/$array1
			    cd $array_dir
 			    ls *.e* > _org_list
			    while read err; do # remove unnecessary lines created from float2ascii - creates hundreds of output lines, not errors)
				cp $err temp1
				sed '/^line:/ d ' < temp1 > temp2
				mv temp2 $err
				rm -rf temp1
			    done < org_list
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
			done
		    fi
		done < $ifm_files
	    fi
	done < $beam_list
    else
	error_list=$dir/$project"_"$track_dir"_add_ifm_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	while read list; do
	    if [ ! -z $list ]; then
		for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
		do
		    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
		    array_dir=$dir/$array1
		    cd $array_dir
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
		done
	    fi
	done < $ifm_files
    fi
else
    :
fi

