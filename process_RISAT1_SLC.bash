#!/bin/bash

### Script doesn't include scene concatenation

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_RISAT1_SLC:  Script takes xxxx format xxxx from xxxx and            *"
    echo "*                      and produces sigma0 calibrated SLC images.             *"
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
    echo -e "Usage: process_RISAT1_SLC.bash [proc_file] [scene]"
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

mkdir -p $scene_dir
cd $scene_dir

## Raw data location
xml=`ls $raw_data_track_dir/$scene/*X1_SAR__SSC______SM_S_SRA_*$scene*/*.xml`
cosar=`ls $raw_data_track_dir/$scene/*X1_SAR__SSC______SM_S_SRA_*$scene*/IMAGEDATA/IMAGE*.cos`


if [ ! -e $scene_dir/$slc ]; then
    GM par_RISAT_SLC $xml $cosar $slc_par $slc

    # Apply the stated calFactor from the xml file, scale according to sin(inc_angle) and convert from scomplex to fcomplex. Output is sigma0
    GM radcal_SLC $slc $slc.par sigma0.slc sigma0.slc.par 3 - 0 0 1 0 -
    mv -f sigma0.slc $slc
    mv -f sigma0.slc.par $slc_par

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

