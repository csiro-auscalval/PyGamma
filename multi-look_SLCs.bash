#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* multi-look_SLCs: Script multi-looks SLCs using the multi-looking values     *"
    echo "*                  calculated by 'calc_multi_look_values.bash'                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*         [scene]      scene ID (eg. 20180423)                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: multi-look_SLCs.bash [proc_file] [scene]"
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
PBS_processing_details $project $track $frame $scene 

######################################################################


## File names
slc_file_names
mli_file_names

cd $scene_dir

if [ ! -e $mli ]; then
    echo " "
    echo "Multi-looking SLC with range and azimuth looks: "$rlks $alks" ..."
    echo " "
    GM multi_look $slc $slc_par $mli $mli_par $rlks $alks 0
else
    "SLC already multi-looked."
fi


# script end 
####################



