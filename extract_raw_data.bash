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
    echo "*         Sarah Lawrie @ GA       12/09/2018, v2.1                            *"
    echo "*                  - refine zip download to only include files related to     *"
    echo "*                    polarisation rather than full zip file                   *"
    echo "*         Sarah Lawrie @ GA       01/11/2018, v2.3                            *"
    echo "*                  - add option to download RESORB if no precise orbit file   *"
    echo "*******************************************************************************"
    echo -e "Usage: extract_raw_data.bash [proc_file] [scene] <S1_grid_dir> <S1_zip_file>"
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



##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $scene $frame

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
    cd $raw_data_track_dir/$frame
    if [ -f $scene ]; then
	: # data already extracted
    else
	mkdir -p $scene
	cd $scene
	
	# change polarisation variable to lowercase
	pol=`echo $polar | tr '[:upper:]' '[:lower:]'`

	# copy relevant parts of zip file 
	dir_name=`basename $zip | cut -d "." -f 1`
	dir=$dir_name.SAFE
	anno_dir=$dir/annotation
	meas_dir=$dir/measurement
	cal_noise_dir=$anno_dir/calibration
	preview_dir=$dir/preview
	zip_loc=$s1_path/$year/$year-$month/$grid/$zip

	# extract manifest.safe file
	unzip -j $zip_loc $dir/manifest.safe -d $dir

	# extract kml files
	quick_look_image=`unzip -l $zip_loc | grep -E 'preview/quick-look.png' | awk '{print $4}'`
	kml=`unzip -l $zip_loc | grep -E 'preview/map-overlay.kml' | awk '{print $4}'`
	unzip -j $zip_loc $quick_look_image -d $preview_dir
	unzip -j $zip_loc $kml -d $preview_dir	

	# extract files based on polarisation
	unzip -l $zip_loc | grep -E 'annotation/s1' | awk '{print $4}' | cut -d "/" -f 3 | sed -n '/'-"$pol"-'/p' > xml_list
	unzip -l $zip_loc | grep -E 'measurement/s1' | awk '{print $4}' | cut -d "/" -f 3 | sed -n '/'-"$pol"-'/p' > data_list
	unzip -l $zip_loc | grep -E 'calibration/calibration-s1' | awk '{print $4}' | cut -d "/" -f 4 | sed -n '/'-"$pol"-'/p' > calib_list
	unzip -l $zip_loc | grep -E 'calibration/noise-s1' | awk '{print $4}' | cut -d "/" -f 4 | sed -n '/'-"$pol"-'/p' > noise_list
	while read xml; do
	    unzip -j $zip_loc $anno_dir/$xml -d $anno_dir
	done < xml_list
	rm -f xml_list
	while read data; do
	    unzip -j $zip_loc $meas_dir/$data -d $meas_dir
	done < data_list
	rm -f data_list
	while read calib; do
	    unzip -j $zip_loc $cal_noise_dir/$calib -d $cal_noise_dir
	done < calib_list
	rm -f calib_list
	while read noise; do
	    unzip -j $zip_loc $cal_noise_dir/$noise -d $cal_noise_dir
	done < noise_list
	rm -f noise_list

	# get precision orbit file
	start_date=`date -d "$scene -1 days" +%Y%m%d`
	stop_date=`date -d "$scene +1 days" +%Y%m%d`

	start_time=`sed -n 's/.*<safe.startTime>\([^<]*\)<\/safe.startTime>.*/\1/p' $dir/manifest.safe | cut -d 'T' -f 2 | cut -d '.' -f 1 | sed 's/\://g'`
	stop_time=`sed -n 's/.*<safe.stopTime>\([^<]*\)<\/safe.stopTime>.*/\1/p' $dir/manifest.safe | cut -d 'T' -f 2 | cut -d '.' -f 1 | sed 's/\://g'`

	# check if precise orbit file is available
        if [ -e $s1_orbits/POEORB/$s1_type/*V$start_date*_$stop_date*.EOF ]; then
            ## determine the most recent file (in case there are duplicates)
            recent=`ls $s1_orbits/POEORB/$s1_type/*V$start_date*_$stop_date*.EOF | sort | tail -1`
            cp -r $recent .
	# if no precise orbit, use restituted orbit file
	else
	    echo "No precise orbit file (POEORB) available for date: "$scene
	    ls  $s1_orbits/RESORB/$s1_type/*V$scene*_$scene*.EOF > list
	    while read line; do
		echo $line | cut -d '/' -f 9 >> list2
	    done < list
	    rm -rf list
	    while read line; do
		start=`echo $line | cut -d '_' -f 7 | cut -d 'T' -f 2`
		stop=`echo $line | cut -d '_' -f 8 | cut -d 'T' -f 2 | cut -d '.' -f 1`
		if [ "$start_time" -ge "$start" ] && [ "$stop_time" -le "$stop" ]; then
		    echo $line | tr '_' ' ' | tr 'T' ' ' >> list3
		fi
	    done < list2
	    rm -rf list2
	    file=`sort -k7 -n -r list3 | head -1 | awk 'BEGIN{FS=OFS="_"}{split($1, a, " "); $1=a[1]"_"a[2]"_"a[3]"_"a[4]"_"a[5]"_"a[6]"T"a[7]"_"a[8]"T"a[9]"_"a[10]"T"a[11]}1'`
	    recent=$s1_orbits/RESORB/$s1_type/$file
	    cp -r $recent .
	    rm -rf list3
        fi
	cd $proj_dir
    fi
fi
# script end
####################

