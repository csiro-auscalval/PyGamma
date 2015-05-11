#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* check_ifm_processing:  Check processing result of unwrapped and geocoded    *"
    echo "*                        interferograms.                                      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [list_type]  ifm list type (1 = ifms.list, 2 = add_ifms.list,       *"
    echo "*                      default is 1)                                          *"
    echo "*         <start>      starting line of SLC (optional, default: 1)            *"
    echo "*         <nlines>     number of lines to display (optional, default: 4000)   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       11/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: check_ifm_processing.bash [proc_file] [list_type] <start> <nlines>"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

if [ $# -eq 2 ]; then
    list_type=$2
else
    list_type=1
fi
if [ $# -eq 3 ]; then
    start=$3
else
    start=1
fi
if [ $# -eq 4 ]; then
    nlines=$4
else
    nlines=-
fi

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
mas=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
ifm_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`

if [ $list_type -eq 1 ]; then
    ifm_list=`grep List_of_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Checking unwrapped interferograms..."
else
    ifm_list=`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Checking additional unwrapped interferograms..."
fi

cd $proj_dir/$track_dir

## Set viewing width for interferograms
width_file=$dem_dir/*$ifm_looks"rlks_utm.dem.par"
width=`grep width: $width_file | awk '{print $2}'`
lines=`grep nlines: $width_file | awk '{print $2}'`
if [ $# -lt 4 ]; then
    if [ $lines -gt 4000 ]; then
	echo  " "
	echo "Image length is "$lines", auto setting length to 4000 lines. If different length required, enter no. lines."
	echo  " "
	nlines=4000
    else
	nlines=$4
    fi
fi

## Check interferograms
while read list; do
    if [ ! -z $list ]; then
	mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	int_dir=$ifm_dir/$mas-$slv
	mas_slv_name=$mas-$slv"_"$polar"_"$ifm_looks"rlks"
	geocoded_ifm=$int_dir/$mas_slv_name"_utm.unw"
	cd $int_dir
	disrmg $geocoded_ifm - $width $start - $nlines - - - -
    fi
done < $ifm_list

echo " "
echo "Checked unwrapped geocoded interferograms."
echo " "
