#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_JERS_SLC:  Script takes Level 1.0 (raw) JERS image mode data and    *"
    echo "*                    produces sigma0 calibrated SLC.                          *"
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
    echo -e "Usage: process_JERS_SLC.bash [proc_file] [scene]"
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


## Set up sensor parameters
sensor_par=$MSP_HOME/sensors/JERS-1.par
cp -f $MSP_HOME/sensors/JERS1_antenna.gain .
# calibration constant from MSP/sensors/sensor_cal_MSP.dat file: JERS = -22.1
cal_const=-22.1

if [ ! -e $scene_dir/$slc ]; then
    # Copy raw and leader file data and rename it to reflect .raw and .ldr files
    IMG=`ls $raw_data_track_dir/$scene/scene01/dat_01.001`
    LED=`ls $raw_data_track_dir/$scene/scene01/lea_01.001`
    cp $IMG $raw
    cp $LED $leader

    ## Create MSP processign parameter file
    # Make dummy file to accept default values for the parameter file
    set returns = $scene_dir/returns
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
    GM JERS_proc $leader $msp_par < $returns

    # Condition raw JERS data
    GM JERS_fix $sensor_par $msp_par $raw $slc_name.fix

    # Determine the Doppler Ambiguity
    GM dop_ambig $sensor_par $msp_par $slc_name.fix 2 - $slc_name.mlbf
    # Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
    #GM dop_mlcc $sensor_par $msp_par $slc_name.fix $slc_name.mlcc

    # Estimate the doppler centroid across the swath
    GM doppler $sensor_par $msp_par $slc_name.fix $slc_name.dop

    # Estimate the range power spectrum
    # Look for potential radio frequency interference (RFI) to the SAR signal
    GM rspec_IQ $sensor_par $msp_par $slc_name.fix $slc_name.rspec

    # Estimate radio frequency interference
    GM rspec_JERS $sensor_par $msp_par $slc_name.fix $slc_name.psd
    # option to plot data using 'extract_psd'

    # Range compression
    GM pre_rc_JERS $sensor_par $msp_par $slc_name.psd $slc_name.fix $slc_name.rc 

    # REMOVE RAW IMAGE FILE HERE
    rm -f $raw $slc_name.fix

    # Autofocus estimation and Azimuth compression (af replaces autof)
    # run az_proc and af twice, DO NOT run af mutliple times before reprocessing image
    # default SNR threshold is 10
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 8192 0 $cal_const 0 2.12
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 8192 0 $cal_const 0 2.12
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af

    # REMOVE RC FILE HERE
    rm -f $slc_name.rc

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


