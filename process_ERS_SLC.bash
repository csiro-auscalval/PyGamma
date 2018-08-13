#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ERS_SLC:  Script takes Level 1.0 (raw) ERS fine beam data and       *"
    echo "*                   produces sigma0 calibrated SLC images.                    *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20180423)                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
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
    echo -e "Usage: process_ERS_SLC.bash [proc_file] [scene]"
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
asar_ers_jers_slc_file_names

mkdir -p $scene_dir
cd $scene_dir

if [ ! -e $scene_dir/$slc ]; then
    # Set up sensor parameters
    if [ $ers_sensor == ERS1 ]; then
	sensor_par=ERS1_ESA_sensor.par
	cp -f $MSP_HOME/sensors/ERS1_ESA.par $sensor_par
	cp -f $MSP_HOME/sensors/ERS1_antenna.gain .
        ## calibration constant from MSP/sensors/sensor_cal_MSP.dat file: 
	if [ $scene -le "19961231" ]; then # ERS1 19910717-19961231 = -10.3
	    cal_const=-10.3
	else # ERS1 19970101-20000310 = -12.5
	    cal_const=-12.5
	fi
    elif [ $ers_sensor == ERS2 ]; then
	sensor_par=ERS2_ESA_sensor.par
	cp -f $MSP_HOME/sensors/ERS2_ESA.par $sensor_par
	cp -f $MSP_HOME/sensors/ERS2_antenna.gain .
        ## calibration constant from MSP/sensors/sensor_cal_MSP.dat file: ERS2 = -2.8
	cal_const=-2.8
    else
	echo "ERROR: Must be ERS1 or ERS2"
	exit 1
    fi
    # set directory of DELFT orbits
    orb_dir=$ers_orbits/$ers_sensor

    # Produce raw data files
    LED=`ls $raw_data_track_dir/$scene/scene01/lea_01.001`
    IMG=`ls $raw_data_track_dir/$scene/scene01/dat_01.001`

    # Generate the MSP processing parameter file
    if [ $scene -le "19971231" ]; then # CEOS leader format is different before and after 1998
	format=0 # before 1998
    else
	format=1 # after 1998
    fi
    # Make dummy file to accept default values for the parameter file
    returns=$scene_dir/returns
    echo "$ers_sensor $scene" > $returns
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
    GM ERS_proc_ACRES $LED $msp_par $format < $returns

    # Condition the raw data and produce raw file in GAMMA format; check for missing lines
    GM ERS_fix ACRES $sensor_par $msp_par 1 $IMG $raw

    # Update orbital state vectors in MSP processing parameter file
    # Note that Delft orbits are believed to be more precise than D-PAF orbits (PRC files). See Scharoo and Visser and Delft Orbits website
    # Four 10-second state vectors should cover one 100km long ERS frame. More are required at either end of the scene. Providing more than necessary cannot hurt.
    GM DELFT_proc2 $msp_par $orb_dir 21 10

    # Determine the Doppler Ambiguity
    # This is required for southern hemisphere data due to error in ERS pointing algorithm that introduces an ambiguity outside of the +/-(PRF/2) baseband
    GM dop_ambig $sensor_par $msp_par $raw 2 - $slc_name.mlbf
    # Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
    #GM dop_mlcc $sensor_par $msp_par $raw $name.mlcc

    # Determine the fractional Doppler centroid using the azimuth spectrum
    GM azsp_IQ $sensor_par $msp_par $raw $slc_name.azsp

    # Estimate the doppler centroid across the swath
    # Should be negligible (near constant) for ERS since yaw steering was employed to maintain the doppler centroid within +/-(PRF/2) 
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

