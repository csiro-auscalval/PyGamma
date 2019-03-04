#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_scenes_list: Creates a list of scene SLCs.                           *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [type]       list type to create (eg. 1=scenes.list or              *"
    echo "*                      2=add_scenes.list)                                     *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*         Sarah Lawrie @ GA       29/01/2016, v1.2                            *"
    echo "*             - add ability to create list from S1 data on the RDSI           *"
    echo "*         Sarah Lawrie @ GA       08/09/2017, v1.3                            *"
    echo "*             - add ability to create frame list for S1 data                  *"
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
    echo -e "Usage: create_scenes_list.bash [proc_file] [type]"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
type=$2

##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

######################################################################


cd $list_dir

## Copy existing scene list to compare with additional scene list
if [ $type -eq 2 ]; then
    cp $scene_list temp1
    sort temp1 > org_scenes.list
    rm -f temp1
else
    :
fi

cd $proj_dir/$track_dir


## Create list of scenes
if [ $sensor != 'S1' ]; then # non Sentinel-1 data
    if [ -f $frame_list ]; then 
	while read frame; do
	    if [ ! -z $frame ]; then 
		if [ -f date.list ]; then # remove old file, just adding to it not creating a new one
		    rm -rf date.list
		fi
	        # data on MDSS
		mdss ls $mdss_data_dir/F$frame/ < /dev/null > tar.list # /dev/null allows mdss command to work properly in loop
		echo >> tar.list # adds carriage return to last line of file (required for loop to work)
		    # remove any non date data from tar.list (eg. other directory names within frame dir)
		grep ^1 tar.list > temp
		grep ^2 tar.list >> temp
		mv temp tar.list
		while read list; do
		    if [ ! -z $list ]; then
			date=`echo $list | awk '{print substr($1,1,8)}'`
			echo $date >> date.list
		    fi
		done < tar.list
		sort -n date.list > $scene_list
		rm -rf tar.list date.list
	    fi
	done < $frame_list
    else #no frame list
	mdss ls $mdss_data_dir < /dev/null > tar.list # /dev/null allows mdss command to work properly in loop
	    # remove any non date data from tar.list (eg. other directory names within track dir)
	grep ^1 tar.list > temp
	grep ^2 tar.list >> temp
	mv temp tar.list
	while read list; do
	    if [ ! -z $list ]; then
		date=`echo $list | awk '{print substr($1,1,8)}'`
		echo $date >> date.list
	    fi
	done < tar.list
	sort -n date.list > $scene_list
	rm -rf tar.list date.list
    fi
else # Sentinel-1 data
    if [ -f $s1_file_list ]; then
	awk '/FILES_TO_DOWNLOAD/ { show=1 } show; /SUBSET_BURSTS/ { show=0 }' $s1_file_list | tail -n+3 | head -n -2 > file_list
	awk '{print $1}' file_list | sort | uniq > $scene_list
	rm -rf file_list
    else
	echo "No Sentinel-1 data file list exists, create list and re-run script"
    fi
fi


# Create additional scene list
if [ $type -eq 2 ]; then
    cd $list_dir
    echo "Additional Slaves List File Creation" 1>&2
    comm -13 org_scenes.list $scene_list > $add_scene_list
else
    :
fi

# script end 
####################
