#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_raw_data: Script extracts and untars raw data files from the MDSS   *"
    echo "*                   or Sentinel-1 archive (NCI) and puts them into the        *"
    echo "*                   'raw_data' directory for GAMMA processing.                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]    name of GAMMA proc file (eg. gamma.proc)             *"
    echo "*         [scene]        scene ID (eg. 20180423)                              *"
    echo "*         <S1_grid_dir>  S1 grid directory name                               *"
    echo "*         <S1_zip_file>  S1 zip file name                                     *"
    echo "*         <S1_frame_number>     S1 frame number                               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       01/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*         Sarah Lawrie @ GA       29/01/2016, v1.2                            *"
    echo "*             - add ability to extract S1 data from the RDSI                  *"
    echo "*         Sarah Lawrie @ GA       08/09/2017, v1.3                            *"
    echo "*             - update paths to S1 data and auto create frame dirs for S1     *"
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
    echo -e "Usage: extract_raw_data.bash [proc_file] [scene] <S1_grid_dir> <S1_zip_file> <S1_frame_number>"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

proc_file=$1
scene=$2
grid=$3
zip=$4
frame_num=$5


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


cd $raw_data_track_dir

## Create list of scenes
if [ $sensor != 'S1' ]; then #non Sentinel-1
    if [ -f $frame_list ]; then # if frames exist
	while read frame; do
	    if [ ! -z $frame ]; then # skips any empty lines
		tar=$scene"_"$sensor"_"$track"_F"$frame.tar.gz
		if [ ! -z $tar ]; then
		    if [ -d $raw_data_track_dir/F$frame/$scene ]; then #check if data have already been extracted from tar file
			:
		    else #data on MDSS
			mdss get $mdss_data_dir/F$frame/$tar < /dev/null $raw_data_track_dir/F$frame # /dev/null allows mdss command to work properly in loop
			cd $raw_data_track_dir/F$frame
			tar -xvzf $tar
			rm -rf $tar
		    fi
		else
		    :
		fi
	    fi
	done < $frame_list
    else # no frames exist
	tar=$scene"_"$sensor"_"$track.tar.gz
	if [ ! -z $tar ]; then
	    if [ -d $raw_data_track_dir/$scene ]; then #check if data have already been extracted from tar file
	   	:
	    else
		mdss get $mdss_data_dir/$tar < /dev/null $raw_data_track_dir # /dev/null allows mdss command to work properly in loop
		cd $raw_data_track_dir
		tar -xvzf $tar
		rm -rf $tar
	    fi
	else
	    :
	fi
    fi
else # Sentinel-1 
    year=`echo $scene | awk '{print substr($1,1,4)}'`
    month=`echo $scene | awk '{print substr($1,5,2)}'`
    s1_type=`echo $zip | cut -d "_" -f 1`
    # create scene directories
    cd $raw_data_track_dir/F$frame_num
    if [ -f $scene ]; then
	: # data already extracted
    else
	mkdir -p $scene
	cd $scene
	# copy zip file
	cp $s1_path/$year/$year-$month/$grid/$zip $zip
        # unzip file
	unzip $zip
	rm -f $zip
	# get precision orbit file
	start_date=`date -d "$scene -1 days" +%Y%m%d`
	stop_date=`date -d "$scene +1 days" +%Y%m%d`
	# check if orbit files are missing are missing
	if [ $s1_type == "S1A" ]; then
	    if grep -R "$scene" $s1_orbits/missing_S1A; then
		echo "No orbit file available for date: "$scene
	    else
		cp $s1_orbits/$s1_type/*V$start_date*_$stop_date*.EOF .
	    fi
	elif [ $s1_type == "S1B" ]; then
	    if grep -R "$scene" $s1_orbits/missing_S1B; then
		echo "No orbit file available for date: "$scene
	    else
		cp $s1_orbits/$s1_type/*V$start_date*_$stop_date*.EOF .
	    fi
	fi
	cd $proj_dir
    fi
fi
# script end
####################

