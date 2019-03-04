#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ASAR_SLC:  Script takes Level 1.0 (raw) ASAR fine beam data and     *"
    echo "*                    produces sigma0 calibrated SLC.                          *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "* author: Thomas Fuhrmann  @ GA   21/10/2016, v1.1                            *"
    echo "*         - added $scene as paramater to plot_rspec.bash to enable the func.  *"
    echo "*         -  deleted all params for pre_rc (default paraemters are used)      *"
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
    echo -e "Usage: process_ASAR_SLC.bash [proc_file] [scene]"
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
asar_ers_jers_slc_file_names


mkdir -p $scene_dir
cd $scene_dir


if [ ! -e $scene_dir/$slc ]; then

     # extract header information from raw file
    IMG=`ls $raw_data_track_dir/$scene/*$scene*.N1`

    head -c 3000 $IMG > $scene"_raw_header.txt"
    swath=`grep SWATH= $scene"_raw_header.txt" | cut -d "=" -f 2 | sed 's/"//' | sed 's/"//'`

    ant=ASAR_$swath"_"$polar"_antenna.gain"
    sensor_par=ASAR_$swath"_sensor.par"

    # Directory for DELFT orbits
    XCA_dir=$envisat_orbits/XCA
    INS_dir=$envisat_orbits/INS

    # ASAR IS2 VV cal constant from MSP/sensors/sensor_cal_MSP.dat file = -30.4, all other modes are '-'
    if [ $swath == IS2 ]; then
	cal_const=-30.4
    else
	cal_const=-
    fi

    # Generate antenna gain parameter file from ASAR XCA file
    year=`echo $scene | awk '{print substr($1,1,2)}' | sed s/0/\ /`
    xcafind=0

    cd $XCA_dir
    ls ASA_XCA_* > $scene_dir/xca.list

    while read xca; do
	vec_start=`echo $xca | awk '{print substr($1,31,8)'}`
	vec_end=`echo $xca | awk '{print substr($1,47,8)'}`
	if [ $scene -gt $vec_start -a $scene -lt $vec_end ]; then
	    xcafile=$XCA_dir/$xca
	    xcafind=1
	    break # exit loop if parameters met
	fi
    done < $scene_dir/xca.list
    rm -rf $scene_dir/xca.list

    cd $scene_dir

    if [ $xcafind -eq 1 ]; then
	GM ASAR_XCA $xcafile $ant $swath $polar
    else
	echo "ERROR: Can not find proper ASA_XCA_* file!"
	exit 1
    fi

    # Find appropriate ASAR instrument file
    insfind=0

    cd $INS_dir
    ls ASA_INS_* > $scene_dir/ins.list

    while read ins; do
	vec_start=`echo $ins | awk '{print substr($1,31,8)'}`
	vec_end=`echo $ins | awk '{print substr($1,47,8)'}`
	if [ $scene -gt $vec_start -a $scene -lt $vec_end ]; then
	    insfile=$INS_dir/$ins
	    insfind=1
	    break # exit loop if parameters met
	fi
    done < $scene_dir/ins.list
    rm -rf $scene_dir/ins.list

    cd $scene_dir

    if [ $insfind -eq 0 ]; then
	echo "ERROR: Can not find proper ASA_INS_* file!"
	exit 1
    fi

    # Generate the MSP processing parameter file and raw data in GAMMA format
    GM ASAR_IM_proc $IMG $insfile $sensor_par $msp_par $raw $ant

    # Update orbital state vectors in MSP processing parameter file
    GM DELFT_proc2 $msp_par $envisat_orbits

    # Determine the Doppler Ambiguity
    GM dop_ambig $sensor_par $msp_par $raw 2 - $slc_name.mlbf
    # Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
    #GM dop_mlcc $sensor_par $msp_par $raw $slc_name.mlcc

    # Determine the fractional Doppler centroid using the azimuth spectrum
    GM azsp_IQ $sensor_par $msp_par $raw $slc_name.azsp

    # Estimate the doppler centroid across the swath
    GM doppler $sensor_par $msp_par $raw $slc_name.dop

    # Estimate the range power spectrum
    # Look for potential radio frequency interference (RFI) to the SAR signal
    GM rspec_IQ $sensor_par $msp_par $raw $slc_name.rspec

    # Range compression
    # second to last parameter is for RFI suppression.
    GM pre_rc $sensor_par $msp_par $raw $slc_name.rc

    # REMOVE RAW IMAGE FILE HERE
    rm -f $raw

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
    GM par_MSP $sensor_par $msp_par $slc_par 0

    # Make quick-look png image of SLC
    width=`grep range_samples: $slc_par | awk '{print $2}'`
    lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
    GM rasSLC $slc $width 1 $lines 50 20 - - 1 0 0 $slc_bmp
    GM convert $slc_bmp $slc_png
    rm -f $slc_bmp

else
    echo " "
    echo "Full SLC already created."
    echo " "
fi


# script end
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2

