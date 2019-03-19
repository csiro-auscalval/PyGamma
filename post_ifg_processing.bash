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

## Move geotiffs 
mkdir -p $geotiff_dir
mkdir -p $geotiff_dem
mkdir -p $geotiff_slc
mkdir -p $geotiff_flat_ifg
#mkdir -p $geotiff_filt_ifg
mkdir -p $geotiff_unw_ifg
mkdir -p $geotiff_flat_cc
#mkdir -p $geotiff_filt_cc

while read list; do
    if [ ! -z $list ]; then
        master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
        slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	ifg_file_names
	mv $ifg_flat_geocode_out.tif $geotiff_flat_ifg/
	#cp $ifg_filt_geocode_out.tif $geotiff_filt_ifg/
	mv $ifg_unw_geocode_out.tif $geotiff_unw_ifg/
	mv $ifg_flat_cc_geocode_out.tif $geotiff_flat_cc/
	#cp $ifg_filt_cc_geocode_out.tif $geotiff_filt_cc/
    fi
done < $ifg_list
fi

dem_master_names
dem_file_names
mv $dem_master_gamma0_eqa_geo $dem_master_sigma0_eqa_geo $geotiff_slc
mv $dem_lv_theta_geo $dem_lv_phi_geo $geotiff_dem

while read list; do
    if [ ! -z $list ]; then
        slave=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
        slave_file_names
        mv $slave_gamma0_eqa_geo $slave_sigma0_eqa_geo $geotiff_slc
    fi
done < $slave_list




if [ $post_method == 'stamps' ]; then
    :
else
    mkdir -p $post_dir
    cd $post_dir
fi


if [ $post_method == 'stamps' ]; then
    echo "stamps post ifg processing not implemented yet, needs stamps to be installed centrally"
    exit

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

    cd $stamps_rslc_dir
    dem_master_names
    slave_file_names
    cp $r_dem_master_mli .
    cp $r_dem_master_mli_par .
    cp $r_slave_mli .
    cp $r_slave_mli_par .
    rm -f *eqa_subset.mli

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
        # place here by giving the date an copying the two rm lines
    #echo "The following Interferograms are excluded:"
    #echo
    #date=20050912
    #echo $date
    #rm -f $stamps_rslc_dir/r$date*
    #rm -f $stamps_diff_dir/$master-$date*
    #date=20100419
    #echo $date
    #rm -f $stamps_rslc_dir/r$date*
    #rm -f $stamps_diff_dir/$master-$date*
    # ifgs excluded

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

    /home/547/txf547/StaMPS_v3.3b1/bin/mt_prep_gamma_area $master_scene $gamma_data_dir 0.6 0 1008 1871 3541 1 1 50 50

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
    cp $eqa_dem . # Not currently used in PyRate
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
#    while read list; do
#        if [ ! -z $list ]; then
#            master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
#            slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
#	    ifg_file_names
#	    cp $ifg_unw_geocode_out .
#        fi
#    done < $ifg_list

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
