#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* collate_nci_errors: Collates errors from SLC generation, slave              *"
    echo "*                     coregistration and interferogram processing on the NCI  *"
    echo "*                     into one file.                                          *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [type]       type of error checking to be done (eg. 1=setup dirs,   *"
    echo "*                      2=raw data extraction, 3=slc creation, 4=dem creation, *"
    echo "*                      5=coregister slcs, 6=interferogram creation,           *"
    echo "*                      7=ifm plots, 8=mosaic beam ifms, 9=additional slc      *"
    echo "*                      creation, 10=additional slc coregistration,            *"
    echo "*                      11=additional interferogram creation, 12=additional    *"
    echo "*                      mosaic ifms)                                           *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       27/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       09/06/2015, v1.1                            *"
    echo "*             - incorporate error collection from auto splitting jobs         *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.2                            *"
    echo "*             - add additional error collation                                *"
    echo "*         Sarah Lawrie @ GA       06/08/2015, v1.3                            *"
    echo "*             - add additional error collation for ifm plots                  *"
    echo "*         Sarah Lawrie @ GA       28/07/2016, v1.4                            *"
    echo "*             - add error collation for subsetting S1 SLCs                    *"
    echo "*         Sarah Lawrie @ GA       08/09/2017, v1.5                            *"
    echo "*             - add error collation for auto cropping S1 SLCs                 *"
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
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    :
fi

beam_list=$proj_dir/$track_dir/lists/`grep List_of_beams= $proc_file | cut -d "=" -f 2`

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir
echo ""

batch_dir=$proj_dir/$track_dir/batch_jobs
error_dir=$proj_dir/$track_dir/error_results



## Setup Errors
if [ $type -eq 1 ]; then
    echo "Collating Errors from Setup..."
    echo "" 1>&2
    
# lists creation
    error_list=$error_dir/list_creation_errors
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    cd $batch_dir
    ls scene_list*.e* > list
    ls slave_list*.e* >> list
    ls ifm_list*.e* >> list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list


## Raw Data Extraction Errors
elif [ $type -eq 2 ]; then
    echo "Collating Errors from Raw Data Extraction..."
    echo "" 1>&2
    error_list=$error_dir/extract_raw_errors
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    cd $batch_dir
    ls extract_raw*.e* > list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list


## SLC Creation Errors
elif [ $type -eq 3 ]; then
    echo "Collating Errors from SLC Creation..."
    echo ""
    dir=$batch_dir/slc_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/$beam"_slc_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$beam/$list
		ls *.e* > list
		while read error; do
		    if [ ! -z $error ]; then
			less $error > temp
			paste temp >> $error_list
			rm -rf temp
		    fi
		done < list
		rm -rf list
		cd $dir/$beam
	    fi
	done < dir_list
	rm -rf dir_list
    else
	cd $dir
	error_list=$error_dir/slc_creation_errors
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$list
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
	done < dir_list
	rm -rf dir_list
    fi


## Auto Crop Sentinel-1 SLC Errors
elif [ $type -eq 4 ]; then
    echo "Collating Errors from Sentinel-1 auto crop SLCs..."
    echo ""
    dir=$batch_dir/slc_crop_jobs
    cd $dir

    error_list=$error_dir/crop_slc_creation_errors
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


## Subset Sentinel-1 SLC Errors
elif [ $type -eq 5 ]; then
    echo "Collating Errors from Sentinel-1 subset SLCs..."
    echo ""
    dir=$batch_dir/sub_slc_jobs
    cd $dir

    error_list=$error_dir/subset_slc_creation_errors
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    ls -d job_* > dir_list
    while read list; do
	if [ ! -z $list ]; then
	    cd $dir/$list
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
    done < dir_list
    rm -rf dir_list


## Ref DEM Creation Errors
elif [ $type -eq 6 ]; then
    echo "Collating Errors from Make Reference Master DEM..."
    echo ""
    dir=$batch_dir/dem_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/$beam"_dem_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls *.e* > list
	while read error; do
	    if [ ! -z $error ]; then
		less $error > temp
		paste temp >> $error_list
		rm -rf temp
	    fi
	done < list
	rm -rf list
    else
	error_list=$error_dir/dem_creation_errors
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

## Coregister SLC Errors
elif [ $type -eq 7 ]; then
    echo "Collating Errors from SLC Coregistration..."
    echo ""
    dir=$batch_dir/slc_coreg_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/$beam"_slc_coreg_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$beam/$list
		ls *.e* > list
		while read error; do
		    if [ ! -z $error ]; then
			less $error > temp
			paste temp >> $error_list
			rm -rf temp
		    fi
		done < list
		rm -rf list
		cd $dir/$beam
	    fi
	done < dir_list
	rm -rf dir_list
    else
	error_list=$error_dir/slc_coreg_errors
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$list
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
	done < dir_list
	rm -rf dir_list
    fi

## Interferogram Errors
elif [ $type -eq 8 ]; then
    echo "Collating Errors from Interferogram Creation..."
    echo ""
    dir=$batch_dir/ifm_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/$beam"_ifm_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$beam/$list
		ls *.e* > org_list
		while read err; do # remove unnecessary lines created from float2ascii - creates hundreds of output lines, not errors)
		    cp $err temp1
		    sed '/^line:/ d ' < temp1 > temp2
		    mv temp2 $err
		    rm -rf temp1
		done < org_list
		rm -rf org_list
		ls *.e* > list
		ls "post_ifm_"$beam*.e* >> list
		while read error; do
		    if [ ! -z $error ]; then
			less $error > temp
			paste temp >> $error_list
			rm -rf temp
		    fi
		done < list
		rm -rf list
		cd $dir/$beam
	    fi
	done < dir_list
	rm -rf dir_list
    else
	error_list=$error_dir/ifm_errors
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$list
		ls *.e* > org_list
		while read err; do # remove unnecessary lines created from float2ascii - creates hundreds of output lines, not errors)
		    cp $err temp1
		    sed '/^line:/ d ' < temp1 > temp2
		    mv temp2 $err
		    rm -rf temp1
		done < org_list
		rm -rf org_list
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
	done < dir_list
	rm -rf dir_list
    fi

## Interferogram Plotting Errors
elif [ $type -eq 9 ]; then
    echo "Collating Errors from Interferogram Plots..."
    echo ""
    dir=$batch_dir/ifm_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/$beam"_ifm_plots.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls plot*.e* > list
	while read error; do
	    if [ ! -z $error ]; then
		less $error > temp
		paste temp >> $error_list
		rm -rf temp
	    fi
	done < list
	rm -rf list
    else
	error_list=$error_dir/ifm_plot_errors
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls plot*.e* > list
	while read error; do
	    if [ ! -z $error ]; then
		less $error > temp
		paste temp >> $error_list
		rm -rf temp
	    fi
	done < list
	rm -rf list
    fi



## Mosaic Beam Interferograms
elif [ $type -eq 10 ]; then
    echo "Collating Errors from Mosaicing Beam Interferograms..."
    echo ""
    dir=$batch_dir/ifm_jobs
    cd $dir
    error_list=$error_dir/mosaic_beam_errors
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    cd $dir
    ls mosaic_beam*.e* > list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list


## Additional Scene Setup Errors
elif [ $type -eq 11 ]; then
    echo "Collating Errors from Adding Additional Scenes..."
    echo "" 1>&2
    dir=$batch_dir
    cd $dir
# lists creation
    error_list=$error_dir/add_scene_errors
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    cd $batch_dir
    ls add_scene_list*.e* > list
    ls add_slave_list*.e* >> list
    ls add_ifm_list*.e* >> list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list

    echo "Collating Errors from Extracting Addtional Raw Data..."
    echo "" 1>&2
    error_list=$error_dir/add_extract_raw_errors
    if [ -f $error_list ]; then
	rm -rf $error_list
    else
	:
    fi
    cd $batch_dir
    ls add_extract_raw*.e* > list
    while read error; do
	if [ ! -z $error ]; then
	    less $error > temp
	    paste temp >> $error_list
	    rm -rf temp
	fi
    done < list
    rm -rf list


## SLC Creation Errors
elif [ $type -eq 12 ]; then
    echo "Collating Errors from SLC Creation..."
    echo ""
    dir=$batch_dir/add_slc_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/"add_"$beam"_slc_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$beam/$list
		ls *.e* > list
		while read error; do
		    if [ ! -z $error ]; then
			less $error > temp
			paste temp >> $error_list
			rm -rf temp
		    fi
		done < list
		rm -rf list
		cd $dir/$beam
	    fi
	done < dir_list
	rm -rf dir_list
    else
	cd $dir
	error_list=$error_dir/add_slc_creation_errors
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$list
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
	done < dir_list
	rm -rf dir_list
    fi

## Coregister additional SLC Errors
elif [ $type -eq 13 ]; then
    echo "Collating Errors from SLC Coregistration..."
    echo ""
    dir=$batch_dir/add_slc_coreg_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/"add_"$beam"_slc_coreg_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$beam/$list
		ls *.e* > list
		while read error; do
		    if [ ! -z $error ]; then
			less $error > temp
			paste temp >> $error_list
			rm -rf temp
		    fi
		done < list
		rm -rf list
		cd $dir/$beam
	    fi
	done < dir_list
	rm -rf dir_list
    else
	error_list=$error_dir/add_slc_coreg_errors
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$list
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
	done < dir_list
	rm -rf dir_list
    fi

## Interferogram Errors
elif [ $type -eq 14 ]; then
    echo "Collating Errors from Addtional Interferogram Creation..."
    echo ""
    dir=$batch_dir/add_ifm_jobs
    cd $dir
    if [ ! -z $beam ]; then
	error_list=$error_dir/"add_"$beam"_ifm_errors.list"
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	cd $beam
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$beam/$list
		ls *.e* > org_list
		while read err; do # remove unnecessary lines created from float2ascii - creates hundreds of output lines, not errors)
		    cp $err temp1
		    sed '/^line:/ d ' < temp1 > temp2
		    mv temp2 $err
		    rm -rf temp1
		done < org_list
		rm -rf org_list
		ls *.e* > list
		ls "post_ifm_"$beam*.e* >> list
		while read error; do
		    if [ ! -z $error ]; then
			less $error > temp
			paste temp >> $error_list
			rm -rf temp
		    fi
		done < list
		rm -rf list
		cd $dir/$beam
	    fi
	done < dir_list
	rm -rf dir_list
    else
	error_list=$error_dir/add_ifm_errors
	if [ -f $error_list ]; then
	    rm -rf $error_list
	else
	    :
	fi
	ls -d job_* > dir_list
	while read list; do
	    if [ ! -z $list ]; then
		cd $dir/$list
		ls *.e* > org_list
		while read err; do # remove unnecessary lines created from float2ascii - creates hundreds of output lines, not errors)
		    cp $err temp1
		    sed '/^line:/ d ' < temp1 > temp2
		    mv temp2 $err
		    rm -rf temp1
		done < org_list
		rm -rf org_list
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
	done < dir_list
	rm -rf dir_list
    fi
else
    :
fi