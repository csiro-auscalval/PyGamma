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
    echo "*         Sarah Lawrie @ GA       13/08/2018, v2.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*         Sarah Lawrie @ GA       13/09/2018, v2.1                            *"
    echo "*             -  Add automatic GAMMA DEM generation from scene extent         *"
    echo "*         Sarah Lawrie @ GA       26/03/2019, v2.2                            *"
    echo "*             -  Add 'add scenes' functionality to workflow                   *"
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


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track 

######################################################################

# Single PBS job function
function single_err_job {
    local err_list=$1
    local job_dir=$2
    local job_err=$3
    
    cd $job_dir
    less $job_err > $err_list
}

# Multiple PBS jobs function
function multi_err_job {
    local err_list=$1
    local job_dir=$2

    if [ -f $err_list ]; then
	rm -rf $er_list
    else
	:
    fi
    cd $job_dir
    ls -d job_* > dir_list
    while read list; do
	if [ ! -z $list ]; then
	    cd $job_dir/$list
	    ls *.e* > list
	    while read error; do
		if [ ! -z $error ]; then
		    less $error > temp
		    paste temp >> $err_list
		    rm -rf temp
		fi
	    done < list
	    rm -rf list  
	    cd ../
	fi
    done < dir_list
    rm -rf dir_list
}

## Raw Data extraction errors
if [ $type -eq 1 ]; then
    list=$error_dir/extract_raw_errors
    dir=$batch_dir/extract_raw_jobs
    multi_err_job $list $dir 

## Create DEM errors
elif [ $type -eq 2 ]; then
    dir=$batch_dir/dem_jobs
    list=$error_dir/create_dem_errors
    err_job=create_dem.e* 
    single_err_job $list $dir $err_job

## Full SLC creation errors
elif [ $type -eq 3 ]; then
    list=$error_dir/slc_creation_errors
    dir=$batch_dir/slc_jobs  
    multi_err_job $list $dir 

## Multi-looking values calculation errors
elif [ $type -eq 4 ]; then
    list=$error_dir/ml_values_calc_errors
    dir=$batch_dir/slc_jobs
    err_job=ml_values.e*
    single_err_job $list $dir $err_job
    
## Multi-look SLC errors
elif [ $type -eq 5 ]; then
    list=$error_dir/multi-look_slc_errors
    dir=$batch_dir/ml_slc_jobs
    multi_err_job $list $dir 

## Baseline estimation errors
elif [ $type -eq 6 ]; then
    list=$error_dir/init_baseline_errors
    dir=$batch_dir/baseline_jobs
    err_job=init_base.e*
    single_err_job $list $dir $err_job

## Subset Sentinel-1 SLC errors
elif [ $type -eq 7 ]; then
    list=$error_dir/subset_S1_slc_errors
    dir=$batch_dir/subset_S1_slc_jobs
    multi_err_job $list $dir 

## Coregister DEM errors
elif [ $type -eq 8 ]; then
    dir=$batch_dir/dem_jobs
    list=$error_dir/coreg_dem_errors
    err_job=coreg_dem.e* 
    single_err_job $list $dir $err_job

## Lat-lon Pixel calculation errors
elif [ $type -eq 9 ]; then
    dir=$batch_dir/dem_jobs
    list=$error_dir/lat-lon_errors
    err_job=calc_lat_lon.e* 
    single_err_job $list $dir $err_job

## Coregister SLC errors
elif [ $type -eq 10 ]; then
    list=$error_dir/coreg_slc_errors
    dir=$batch_dir/coreg_slc_jobs
    multi_err_job $list $dir 

## Interferogram errors
elif [ $type -eq 11 ]; then
    list=$error_dir/ifg_errors
    dir=$batch_dir/ifg_jobs
    multi_err_job $list $dir 

## Baseline estimation errors
elif [ $type -eq 12 ]; then
    list=$error_dir/prec_baseline_errors
    dir=$batch_dir/baseline_jobs
    err_job=prec_base.e*
    single_err_job $list $dir $err_job

## Post processing errors
elif [ $type -eq 13 ]; then
    list=$error_dir/post_ifg_errors
    dir=$batch_dir/post_ifg_jobs
    err_job=post_ifg.e* 
    single_err_job $list $dir $err_job

## Additional raw data extraction errors
elif [ $type -eq 14 ]; then
    list=$error_dir/add_extract_raw_errors
    dir=$batch_dir/add_extract_raw_jobs
    multi_err_job $list $dir 

## Additional full SLC creation errors
elif [ $type -eq 15 ]; then
    list=$error_dir/add_slc_creation_errors
    dir=$batch_dir/add_slc_jobs  
    multi_err_job $list $dir 
   
## Multi-look additional SLC errors
elif [ $type -eq 16 ]; then
    list=$error_dir/add_multi-look_slc_errors
    dir=$batch_dir/add_ml_slc_jobs
    multi_err_job $list $dir 

## Baseline estimation errors
elif [ $type -eq 17 ]; then
    list=$error_dir/add_init_baseline_errors
    dir=$batch_dir/add_baseline_jobs
    err_job=add_init_base.e*
    single_err_job $list $dir $err_job

## Subset Sentinel-1 additional SLC errors
elif [ $type -eq 18 ]; then
    list=$error_dir/add_subset_S1_slc_errors
    dir=$batch_dir/add_subset_S1_slc_jobs
    multi_err_job $list $dir 

## Coregister additional SLC errors
elif [ $type -eq 19 ]; then
    list=$error_dir/add_coreg_slc_errors
    dir=$batch_dir/add_coreg_slc_jobs
    multi_err_job $list $dir 

## Additional interferogram errors
elif [ $type -eq 20 ]; then
    list=$error_dir/add_ifg_errors
    dir=$batch_dir/add_ifg_jobs
    multi_err_job $list $dir 

## Baseline estimation errors
elif [ $type -eq 21 ]; then
    list=$error_dir/add_prec_baseline_errors
    dir=$batch_dir/add_baseline_jobs
    err_job=add_prec_base.e*
    single_err_job $list $dir $err_job

## Post processing errors
elif [ $type -eq 22 ]; then
    list=$error_dir/add_post_ifg_errors
    dir=$batch_dir/add_post_ifg_jobs
    err_job=add_post_ifg.e* 
    single_err_job $list $dir $err_job

else
    :
fi
# script end 
####################

