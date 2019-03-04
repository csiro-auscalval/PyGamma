#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_PALSAR_SLC: Script takes either Level 1.0 (raw) PALSAR1 fine beam   *"
    echo "*                     or Level 1.1 PALSAR1 and PALSAR2 data and produces      *"
    echo "*                     sigma0 calibrated SLC.                                  *"
    echo "*                                                                             *"
    echo "*                        Requires a 'frame.list' text file to be created in   *"
    echo "*                        the project directory. This lists the frame numbers  *"
    echo "*                        on each line (e.g. 7160).                            *"
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
    echo -e "Usage: process_PALSAR_SLC.bash [proc_file] [scene]"
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
palsar_slc_file_names

mkdir -p $scene_dir
cd $scene_dir

raw_file_list=$scene_dir/raw_file_list
rm -f $raw_file_list


## Set mode based on polarisation
function set_mode {
    rm -f $pol_list
    while read frame_num; do
	if [ ! -z $frame_num ]; then
	    frame=`echo $frame_num | awk '{print $1}'`
	    ls $raw_data_track_dir/F$frame/$scene/IMG-HH* >& hh_temp
	    ls $raw_data_track_dir/F$frame/$scene/IMG-HV* >& hv_temp
	    temp="ls: cannot access"
	    temp1=`awk '{print $1" "$2" "$3}' hh_temp`
	    if [ "$temp1" == "$temp" ]; then
		:
	    else
		basename $raw_data_track_dir/F$frame/$scene/IMG-HH* >> $pol_list 
	    fi
	    temp2=`awk '{print $1" "$2" "$3}' hv_temp`
	    if [ "$temp2"  == "$temp" ]; then
		:
	    else
		basename $raw_data_track_dir/F$frame/$scene/IMG-HV* >> $pol_list
	    fi
	    rm -rf hh_temp hv_temp
	fi
    done < $frame_list

    num_hv=`grep -co "HV" $pol_list`
    if [ $sensor == PALSAR1 ]; then # no FBD or FBS conversion if PALSAR2 wide swath data
	if [[ "$num_hv" -eq 0 && "$polar" == HH ]]; then 
	    mode=FBS
	elif [[ "$num_hv" -ge 1 && "$polar" == HH ]]; then
	    mode=FBD
	elif [ "$polar" == HV ]; then
	    mode=FBD
	else
	    :
	fi
    else
	:
    fi
    echo "Mode:" $mode "  Polarisation:" $polar
    rm -f $pol_list
}

## Produce Level 0 SLC data files
function level0_slc {
    # Produce raw data files

    while read frame_num; do
	if [ ! -z $frame_num ]; then
	    frame=`echo $frame_num | awk '{print $1}'`
	    ls $raw_data_track_dir/F$frame/$scene/LED-ALP* >& temp
	    LED=`awk '{print $1}' temp`
	    rm -f temp
	    
            # Check polarisation
	    if [ $polar == HH ]; then
		ls $raw_data_track_dir/F$frame/$scene/IMG-HH* >& temp
		IMG=`awk '{print $1}' temp`
		rm -f temp
	    else 
		ls $raw_data_track_dir/F$frame/$scene/IMG-HV* >& temp
		IMG=`awk '{print $1}' temp`
		rm -f temp
	    fi
	    sensor_fm_par="PALSAR_sensor_"$frame"_"$polar.par
	    msp_fm_par=$scene"_"$frame"_"$polar"_p.slc.par"
	    raw_fm_file=$scene"_"$frame"_"$polar.raw
	    
            # Set polarisation (0 = H, 1 = V)
	    tx_pol=`echo $polar | awk '{print substr($1,1,1)}'`
	    rx_pol=`echo $polar | awk '{print substr($1,2,1)}'`
            if [ $tx_pol == H ]; then
		tx_pol1=0
	    else
		tx_pol1=1
	    fi
	    if [ $rx_pol == H ]; then
		rx_pol1=0
	    else
		rx_pol1=1
	    fi
	    
            # Generate the processing parameter files and raw data in GAMMA format
	    GM PALSAR_proc $LED $sensor_fm_par $msp_fm_par $IMG $raw_fm_file $tx_pol1 $rx_pol1
	    
            # Copy raw data file details to text file to check if concatenation of scenes along track is required
	    echo $raw_fm_file $sensor_fm_par $msp_fm_par >> $raw_file_list
	fi
    done < $frame_list

    # Check if scene concatenation is required (i.e. a scene has more than one frame)
    lines=`awk 'END{print NR}' $raw_file_list`
    if [ $lines -eq 1 ]; then
        ## rename files to enable further processing (remove reference to 'frame' in file names)
	mv $sensor_fm_par $sensor_par
	mv $msp_fm_par $msp_par
	mv $raw_fm_file $raw
	rm -f $raw_file_list
    else
        ## Concatenate scenes into one output raw data file
	GM cat_raw $raw_file_list $sensor_par $msp_par $raw 1 0 - 
	rm -f $scene"_"*"_"$polar"_p.slc.par"
	rm -f "PALSAR_sensor_"*"_"$polar.par
	rm -f $scene"_"*"_"$polar.raw
	rm -f $raw_file_list
    fi

    # Correction for antenna pattern
    GM PALSAR_antpat $sensor_par $msp_par $sensor_antpat $msp_antpat - $tx_pol1 $rx_pol1

    # Determine the Doppler Ambiguity
    # Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
    GM dop_mlcc $sensor_par $msp_par $raw $slc_name.mlcc

    # Estimate the doppler centroid with cross correlation method
    # If result of 'doppler' shows that linear model is not good enough use 'azsp_IQ' to determine constant value
    GM doppler $sensor_par $msp_par $raw $slc_name.dop

    # Estimate the range power spectrum
    # Look for potential radio frequency interference (RFI) to the SAR signal
    GM rspec_IQ $sensor_par $msp_par $raw $slc_name.rspec

    # Range compression
    # second to last parameter is for RFI suppression.
    GM pre_rc $sensor_par $msp_par $raw $slc_name.rc - - - - - - - - 0 -

    # REMOVE RAW IMAGE FILE HERE
    rm -f $raw

    # Autofocus estimation and Azimuth compression (af replaces autof)
    # run az_proc and af twice, DO NOT run af mutliple times before reprocessing image
    # default SNR threshold is 10
    # slc calibrated as sigma0 (assume 34.3 angle)
    if [ $polar == HH -a $mode == FBS ]; then
	cal_const=-51.9
    elif [ $polar == HH -a $mode == FBD ]; then
	cal_const=-51.8
    elif [ $polar == HV -a $mode == FBD ]; then
	cal_const=-58.3
    else
	:
    fi
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 16384 0 $cal_const 0
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 16384 0 $cal_const 0
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af

    # REMOVE RC FILE HERE
    rm -f $slc_name.rc

    # Generate ISP SLC parameter file from MSP SLC parameter file (for full SLC)
    GM par_MSP $sensor_par $msp_par $slc_par 0
}

## Produce Level 1 SLC data files
function level1_slc {
    while read frame_num; do
	if [ ! -z $frame_num ]; then
	    frame=`echo $frame_num | awk '{print $1}'`
	    fr_slc_name=$scene"_"$polar"_F"$frame
	    fr_slc=$fr_slc_name.slc
	    fr_slc_par=$fr_slc.par

            IMG=$raw_data_track_dir/F$frame/$scene/IMG-$polar-*
	    LED=$raw_data_track_dir/F$frame/$scene/LED-*
    	    
	    GM par_EORC_PALSAR $LED $fr_slc_par $IMG $fr_slc

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
        # concatenate first 2 frames (maximum 3 frames allowed for)
    else 
	slc1=`awk 'NR==1 {print $1}' $raw_file_list`
	slc1_par=`awk 'NR==1 {print $2}' $raw_file_list`
	echo $slc1 $slc1_par > tab1
	slc2=`awk 'NR==2 {print $1}' $raw_file_list`
	slc2_par=`awk 'NR==2 {print $2}' $raw_file_list`
	echo $slc2 $slc2_par > tab2
	slc1_name=`echo $slc1 | awk -F . '{print $1}'`
	slc2_name=`echo $slc2 | awk -F . '{print $1}'`
	cat_off=$slc1_name-$slc2_name"_cat.off"
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
	rm -rf cat_slc cat_slc_tab tab1 tab2 SLC_cat_all*.log create_offset.in 
	# concatenate 3rd frame to concatenated frames above
	if [ $lines -eq 3 ]; then
	    slc1=$slc_name"_F1-F2.slc"
	    slc1_par=$slc1.par
	    mv $slc $slc1
	    mv $slc_par $slc1_par
	    echo $slc1 $slc1_par > tab1
	    slc2=`awk 'NR==3 {print $1}' $raw_file_list`
	    slc2_par=`awk 'NR==3 {print $2}' $raw_file_list`
	    echo $slc2 $slc2_par > tab2
	    cat_off=$slc1_name-$slc2_name"_cat.off"
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
	fi
	rm -rf $raw_file_list cat_slc cat_slc_tab tab1 tab2 test1.dat test2.dat t1.dat SLC_cat_all*.log create_offset.in *_resamp.log *.snr *.off* *.coffs
    fi

    # Compute the azimuth Doppler spectrum and the Doppler centroid from SLC data
    GM az_spec_SLC $slc $slc_par $slc_name.dop - 0 

    # update ISP file with new estimated doppler centroid frequency (must be done manually)
    org_value=`grep doppler_polynomial: $slc_par | awk '{print $2}'`
    new_value=`grep "new estimated Doppler centroid frequency (Hz):" output.log | awk '{print $7}'`
    sed ' s/'"$org_value"'/'"$new_value"'/' $slc_par > $slc_name.temp
    mv -f $slc_name.temp $slc_par
    rm -rf $slc_name"_temp.dop"
}

## FBD to FBS Conversion
function fbd_to_fbs {
    if [ $polar == HH -a $mode == FBD ]; then
	GM SLC_ovr $slc $slc_par $fbd2fbs_slc $fbd2fbs_par 2
	rm -f $slc
	rm -f $slc_par
	mv $fbd2fbs_slc $slc
	mv $fbd2fbs_par $slc_par
    else
	:
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

if [ ! -e $slc ]; then
    if [ $sensor == 'PALSAR1' ]; then
	set_mode
	level0_slc
	fbd_to_fbs
	slc_image
    else
	if [ $palsar2_type == 'raw' ]; then
	    set_mode
	    level0_slc
	    fbd_to_fbs
	    slc_image
	elif [ $palsar2_type == 'slc' ]; then
	    set_mode
	    level1_slc
	    fbd_to_fbs
	    slc_image
	else
	    :
	fi
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

