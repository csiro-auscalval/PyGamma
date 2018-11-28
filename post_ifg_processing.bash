#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* post_ifg_processing:  Copy files from each interferogram directory to a     *"
    echo "*                       central location for post processing (ie. stamps,     *"
    echo "*                       pymode or pyrate). Also copies geotiffs if created.   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       16/06/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       22/06/2015, v1.1                            *"
    echo "*           - add capture of bperp value from ifm processing                  *"
    echo "*         Sarah Lawrie @ GA       06/08/2015, v1.2                            *"
    echo "*           - add plotting of cc and filt ifms and split up plot creation     *"
    echo "*             to separate scripts.                                            *"
    echo "*         Sarah Lawrie @ GA       13/08/2018, v2.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: post_ifg_processing.bash [proc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1


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

# File names
post_process


cd $proj_dir/$track

## Copy geotiffs if created
if [ $ifg_geotiff == 'yes' ]; then
    mkdir -p $geotiff_dir
    mkdir -p $geotiff_flat_ifg
    mkdir -p $geotiff_filt_ifg
    mkdir -p $geotiff_unw_ifg
    mkdir -p $geotiff_flat_cc
    mkdir -p $geotiff_filt_cc
    while read list; do
        if [ ! -z $list ]; then
            master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
            slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifg_file_names
	    cp $ifg_flat_geocode_out.tif $geotiff_flat_ifg/
	    cp $ifg_filt_geocode_out.tif $geotiff_filt_ifg/
	    cp $ifg_unw_geocode_out.tif $geotiff_unw_ifg/
	    cp $ifg_flat_cc_geocode_out.tif $geotiff_flat_cc/
	    cp $ifg_filt_cc_geocode_out.tif $geotiff_filt_cc/
        fi
    done < $ifg_list
fi

if [ $post_method == 'stamps' ]; then
    :
else
    mkdir -p $post_dir
    cd $post_dir
fi


if [ $post_method == 'stamps' ]; then
    echo "Preparing files for post-processing using StaMPS (SBAS approach)"
    echo

    ## check area to be processed in StaMPS
    rg_min=`echo $post_ifg_area_rg | awk '{print $1}'`
    rg_max=`echo $post_ifg_area_rg | awk '{print $2}'`
    az_min=`echo $post_ifg_area_az | awk '{print $1}'`
    az_max=`echo $post_ifg_area_az | awk '{print $2}'`
    dem_master_names
    master_mli_width=`grep range_samples: $r_dem_master_mli_par | cut -d ":" -f 2`
    master_mli_nlines=`grep azimuth_lines: $r_dem_master_mli_par | cut -d ":" -f 2`
    # no values given -> use full extent
    if [ "$post_ifg_area_rg" == "- -" ]; then
        post_ifg_area_rg=`echo "0 $master_mli_width"`
    fi
    if [ "$post_ifg_area_az" == "- -" ]; then
        post_ifg_area_az=`echo "0 $master_mli_nlines"`
    fi
    # max values greater maximum number of pixels -> use maximum number
    if [ $rg_max -gt $master_mli_width ]; then
        echo "Maximum range greater than number of range pixels ("$master_mli_width")"
        echo "Maximum range set to" $master_mli_width
        echo
        post_ifg_area_rg=`echo "$rg_min $master_mli_width"`
    fi
    if [ $az_max -gt $master_mli_nlines ]; then
        echo "Maximum azimuth greater than number of azimuth pixels ("$master_mli_nlines")"
        echo "Maximum azimuth set to" $master_mli_nlines
        echo
        post_ifg_area_az=`echo "$az_min $master_mli_nlines"`
    fi
    # min values greater max values -> error
    if [ $rg_min -gt $rg_max ]; then
        echo "ERROR: maximum range must be greater than minimum range"
        echo "Min/max range extent given:" $rg_min $rg_max
        echo
        exit 1
    fi
    if [ $az_min -gt $az_max ]; then
        echo "ERROR: maximum aziumth must be greater than minimum azimuth"
        echo "Min/max azimuth extent given:" $az_min $az_max
        echo
        exit 1
    fi
    ## list parameters from .proc file
    echo "The folloing parameters will be used:"
    echo "Amplitude Dispersion Threshold:" $post_ifg_d_a
    echo "Area to be processed in StaMPS (min/max range, min/max azimuth):" $post_ifg_area_rg $post_ifg_area_az
    echo "Number of patches in range and azimuth directions:" $post_ifg_patches_rg $post_ifg_patches_az
    echo "Number of overlapping range and azimuth pixels per patch:" $post_ifg_overlap_rg $post_ifg_overlap_az
    echo

    echo "Creating directories and copying files..."
    echo

    ## Directories
    mkdir -p $gamma_data_dir
    mkdir -p $stamps_geo_dir
    mkdir -p $stamps_baselines_dir
    mkdir -p $stamps_diff_dir
    mkdir -p $stamps_rslc_dir

    ## DEM files
    cd $stamps_geo_dir
    dem_file_names
    cp $lat_lon_pix .
    cp $rdc_dem .
    # rename sar_latlon for compatibility with mt_prep
    mv $gamma_data_dir/geo/*sar_latlon.txt $gamma_data_dir/geo/sar_latlon.txt

    ## MLI files
    cd $stamps_rslc_dir
    while read list; do
        if [ ! -z $list ]; then
            slave=`echo $list`
            slave_file_names
            cp $r_slave_mli .
            cp $r_slave_mli_par .
        fi
    done < $scene_list

    ## IFG files
    cd $stamps_diff_dir
    while read list; do
        if [ ! -z $list ]; then
            master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
            slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifg_file_names
	    cp $ifg_flat .
	    cp $ifg_base .
        fi
    done < $ifg_list

    ## CR file if exists
    crfile=$proj_dir/$track/CR_site_lon_lat_hgt_date_az_rg.txt
    if [ -f $crfile ]; then
	cp $crfile $post_dir
    else
	:
    fi

    ## any interferograms that should be exluded?
        # place here by giving the date and copying the two rm lines
        # could be added to proc file
    #echo "The following Interferogram dates are excluded:"
    #echo
    #date=20150524
    #echo $date
    #rm -f $gamma_data_dir/SMALL_BASELINES/rslc/r$date*
    #rm -f $gamma_data_dir/SMALL_BASELINES/diff0/$date*
    #rm -f $gamma_data_dir/SMALL_BASELINES/diff0/*-$date*
    #date=20150605
    #echo $date
    #rm -f $gamma_data_dir/SMALL_BASELINES/rslc/r$date*
    #rm -f $gamma_data_dir/SMALL_BASELINES/diff0/$date*
    #rm -f $gamma_data_dir/SMALL_BASELINES/diff0/*-$date*

    ## Swap bytes for fcomplex data
    echo "Swapping bytes (big endian > little endian)"
    echo
    for file in $stamps_rslc_dir/*.mli
    do
	mv $file temp1
	swap_bytes temp1 $file 4 >/dev/null
    done
    for file in $stamps_diff_dir/*.int
    do
	mv $file temp1
	swap_bytes temp1 $file 4 >/dev/null
    done
    rm -r temp1

    echo "Starting interface and PS candidate selection using Amplitude Dispersion"
    /g/data1/dg9/SOFTWARE/dg9-apps/stamps-4.1/bin/mt_prep_gamma_area $master_scene $gamma_data_dir $post_ifg_d_a $post_ifg_area_rg $post_ifg_area_az $post_ifg_patches_rg $post_ifg_patches_az $post_ifg_overlap_rg $post_ifg_overlap_az

    ## remove files which are not needed anymore
    rm -f $stamps_diff_dir/*_flat.int
    rm -rf $stamps_geo_dir
    rm -f $stamps_rslc_dir/*.mli

elif [ $post_method == 'pymode' ]; then
   ## interferogram files
    while read list; do
        if [ ! -z $list ]; then
            master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
            slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifg_file_names
	    cp $ifg_unw_geocode_out .
	    cp $ifg_unw_geocode_out.tif .
	    cp $ifg_flat_geocode_out .
        fi
    done < $ifg_list

    ## DEM files
    dem_master_names
    dem_file_names
    cp $r_dem_master_slc_par .
    cp $eqa_dem .
    cp $eqa_dem_par .
    cp $dem_lv_theta .
    cp $dem_lv_phi .

elif [ $post_method == 'pyrate' ]; then
    cd $post_dir
    ## DEM files
    dem_file_names
#    cp $eqa_dem . # Not currently used in PyRate
    cp $eqa_dem_par .
#    cp $dem_lv_theta . # Not currently used in PyRate
#    cp $dem_lv_phi . # Not currently used in PyRate
#    ls * > dem_list

    ## SLC par files
    dem_master_names
    cp $r_dem_master_slc_par .

    while read list; do
        if [ ! -z $list ]; then
            slave=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
            slave_file_names
            cp $r_slave_slc_par .
        fi
    done < $slave_list

    ## Unwrapped interferogram files
    while read list; do
        if [ ! -z $list ]; then
            master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
            slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifg_file_names
	    cp $ifg_unw_geocode_out .
        fi
    done < $ifg_list

    ## Flattened coherence files - not currently used in PyRate
#    while read list; do
#        if [ ! -z $list ]; then
#            master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
#            slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
#	    ifg_file_names
#	    cp $ifg_flat_cc_geocode_out .
#	    cp $ifg_dir/ifg.rsc .
#        fi
#    done < $ifg_list

else
    :
fi



# script end
####################
