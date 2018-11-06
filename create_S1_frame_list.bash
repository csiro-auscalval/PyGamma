#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_S1_frame_list: Script creates frame.list from details in             *"
    echo "*                       s1_download.list file.                                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
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
    echo -e "Usage: create_S1_frame_list.bash [proc_file]"
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

######################################################################


cd $proj_dir

while read scene; do
    while read line; do
	scene1=`echo $line | awk '{print $1}'`
	if [ $scene == $scene1 ]; then
	    count=`grep -r $scene $s1_download_list | wc -l`
	    echo $scene $count >> temp1
	fi
    done < $s1_download_list
done < $scene_list

sort temp1 | uniq > $frame_list
rm -f temp1

# script end 
####################


