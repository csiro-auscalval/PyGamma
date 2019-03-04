#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_RSAT_SLC: Script takes either level 1.0 (raw) RADARSAT-1 or SLC     *"
    echo "*                   (MDA geotiff format) RADARSAT-2 image mode data and       *"
    echo "*                   produces sigma0 calibrated SLC.                           *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20180423)                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*         Sarah Lawrie @ GA       16/06/2016, v1.2                            *"
    echo "*             - modify concatenation to allow for up to 3 frames              *"
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
    echo -e "Usage: process_RADARSAT_SLC.bash [proc_file] [scene]"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" ]; then 
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    scene=$2
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
PBS_processing_details $project $track $scene 

######################################################################

## File names
slc_file_names
final_file_loc
radarsat_slc_file_names 


mkdir -p $scene_dir
cd $scene_dir


## RADARSAT-1 SLC generation
function rsat1 {
    # Determine beam mode from metadata file for antenna file
    xml_grep 'SUPPLEMENTARYINFORMATION' $raw_data_track_dir/$scene/metadata.xml --text_only > temp1
    awk -F"BEAM_MODE=" '{print $2}' temp1 > temp2
    beam=`awk '{print substr($1,1,2)}' temp2`
    cp -f $MSP_HOME/sensors/RSAT_{$beam}_antenna.gain .

    # Copy raw and leader file data and rename it to reflect .raw and .ldr files
    IMG=`ls $raw_data_track_dir/$scene/scene01/dat_01.001`
    LED=`ls $raw_data_track_dir/$scene/scene01/lea_01.001`
    cp $IMG $raw
    cp $LED $leader

    # Create MSP processing parameter file and condition data
    # Make dummy file to accept default values for the parameter file
    returns=$scene_dir/returns
    echo "" > $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    GM RSAT_raw $leader $sensor_par $msp_par $raw $slc_name.fix < $returns
    rm -f $returns

    # Determine the Doppler Ambiguity
    GM dop_ambig $sensor_par $msp_par $slc_name.fix 2 - $slc_name.mlbf
    # Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
    #GM dop_mlcc $sensor_par $msp_par $slc_name.fix $slc_name.mlcc

    # Estimate the doppler centroid across the swath
    GM doppler $sensor_par $msp_par $slc_name.fix $slc_name.dop

    # Estimate the range power spectrum
    # Look for potential radio frequency interference (RFI) to the SAR signal
    GM rspec_IQ $sensor_par $msp_par $slc_name.fix $slc_name.rspec

    # Range compression
    GM pre_rc_RSAT $sensor_par $msp_par $slc_name.fix $slc_name.rc 

    # REMOVE RAW IMAGE FILE HERE
    rm -f $raw $slc_name.fix

    # Autofocus estimation and Azimuth compression (af replaces autof)
    # run az_proc and af twice, DO NOT run af mutliple times before reprocessing image
    # default SNR threshold is 10
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 4096 0 $cal_const 0
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 4096 0 $cal_const 0
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af

    # REMOVE RC FILE HERE
    rm -f $slc_name.rc

    # Generate ISP SLC parameter file from MSP SLC parameter file (for full SLC)
    par_MSP $sensor_par $msp_par $slc_par 0
}


## RADARSAT-2 SLC generation
function rsat2 {
    raw_file_list=$scene_dir/raw_file_list
    rm -f $raw_file_list
    while read frame_num; do
	radarsat_slc_file_names 
	if [ ! -z $frame_num ]; then
	    frame=`echo $frame_num | awk '{print $1}'`
	    xml=$raw_data_track_dir/F$frame/$scene/RS2_OK*$scene*SLC/product.xml
	    lut=$raw_data_track_dir/F$frame/$scene/RS2_OK*$scene*SLC/lutSigma.xml
	    tif=$raw_date_track_dir/F$frame/$scene/RS2_OK*$scene*SLC/imagery_$polar.tif

            # Read RADARSAT-2 data and produce sigma0 calibrated slc and parameter files in GAMMA format
	    echo "process_RSAT2_SLC.bash: bugfix required for correct polarisation. hardwired to 'H'"
	    GM par_RSAT2_SLC $xml $lut $tif H $fr_slc_par $fr_slc

            # Copy data file details to text file to check if concatenation of scenes along track is required
	    echo $fr_slc $fr_slc_par >> $raw_file_list
	fi
    done < $frame_list

    # Check if scene concatenation is required (i.e. a scene has more than one frame)
    lines=`awk 'END{print NR}' $raw_file_list`
    if [ $lines -eq 1 ]; then
        # rename files to enable further processing (remove reference to 'frame' in file names)
	mv $fr_slc $slc
	mv $fr_slc_par $slc_par
	rm -f $raw_file_list
    # concatenate 2 frames
    else 
	slc1=`awk 'NR==1 {print $1}' $raw_file_list`
	slc1_par=`awk 'NR==1 {print $2}' $raw_file_list`
	echo $slc1 $slc1_par > tab1
	slc2=`awk 'NR==2 {print $1}' $raw_file_list`
	slc2_par=`awk 'NR==2 {print $2}' $raw_file_list`
	echo $slc2 $slc2_par > tab2
	slc1_name=`echo $slc1 | awk -F . '{print $1}'`
	slc2_name=`echo $slc2 | awk -F . '{print $1}'`
	offs=$slc1_name-$slc2_name.offs
	snr=$slc1_name-$slc2_name.snr
	coffs=$slc1_name-$slc2_name.coffs
	mkdir cat_slc
        # create offset parameter files for estimation of the offsets
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 0
        # measure initial range and azimuth offsets using orbit information
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 1
        # estimate range and azimuth offset models using correlation of image intensities
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 3
        # concatenate SLC images using offset polynomials determined above
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 4
        # clean up files
	cd cat_slc
	cat_slc=*.slc
	cat_slc_par=*.slc.par
	mv $cat_slc $slc
	mv $cat_slc_par $slc_par
	mv * ../
	cd ../
	rm -rf  cat_slc cat_slc_tab tab1 tab2 SLC_cat_all*.log create_offset.in 
    fi
}


# Make quick-look png image of SLC
function slc_image {
    width=`grep range_samples: $slc_par | awk '{print $2}'`
    lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
    GM rasSLC $slc $width 1 $lines 50 20 - - 1 0 0 $slc_bmp
    GM convert $slc_bmp $slc_png
    rm -f $slc_bmp
}


if [ ! -e $scene_dir/$slc ]; then
    if [ $sensor == 'RSAT1' ]; then
	rsat1
	slc_image
    elif [ $sensor == 'RSAT2' ]; then
	rsat2
	slc_image
    else
	:
    fi
else
    echo " "
    echo "Full SLC already created."
    echo " "
fi

# script end 
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2
rm temp_log
