#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* geocode:  Geocodes SLC and INT directory files with DEM in map coordinates. *"
    echo "*           There is an option to create a geotif file.                       *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]    name of GAMMA proc file (eg. gamma.proc)             *"
    echo "*         [file]         file to geocode                                      *"
    echo "*         <geotiff>      option to geotiff (1: yes, 2: no, default is 1)      *"
    echo "*         <nlines_out>   number of lines of output file (default is - for     *"
    echo "*                        number of lines of lookup table)                     *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: geocode.bash [proc_file] [file] <geotiff> <nlines_out>"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
file=$2

if [ $# -eq 3 ]; then
    tif_flag=$3
else
    tif_flag=1
fi
if [ $# -eq 4 ]; then
    nlines_out=$4
else
    nlines_out=-
fi

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $scene 1>&2
echo "" 1>&2
echo "Geocode Data" 1>&2

## Insert scene details top of NCI .o file
echo "" 
echo "" 
echo "PROCESSING_SCENE: "$project $track_dir $scene
echo ""
echo "Geocode Data" 

## Copy output of Gamma programs to log files
GM()
{
    echo $* | tee -a command.log
    echo
    $* >> output.log 2> temp_log
    cat temp_log >> error.log
    #cat output.log (option to add output results to NCI .o file if required)
}

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

file_name=`echo $file | cut -d'.' -f1`
file_ext=`echo $file | awk -F . '{if (NF>1) {print $NF}}'` 
lks=`echo $file_name | awk -F _ '{print $3}'`

geocode_out=$file_name"_utm."$file_ext
geotif=$file_name"_utm_"$file_ext.tif

if [ $file_ext == slc ]; then
    format=1 #fcomplex
    lks=0rlks
elif [ $file_ext == mli ]; then
    format=0 #float
elif [ $file_ext == cc ]; then
    format=0 #float
elif [ $file_ext == flag ]; then
    format=3 #unsigned char
elif [ $file_ext == int ]; then
    format=1 #fcomplex
elif [ $file_ext == ras ]; then
    format=2 #raster
elif [ $file_ext == unw ]; then
    format=0 #float
else
    echo " "
    echo "Geocoding file extension: *."$file_ext" not currently supported."
    echo " "
    exit 1
fi

width_in=`grep range_samp_1: $dem_dir/"diff_"$master"_"$polar"_"$lks.par | awk '{print $2}'`
gc_map=$dem_dir/$master"_"$polar"_"$lks"_fine_utm_to_rdc.lt"
dem_par=$dem_dir/$master"_"$polar"_"$lks"_utm.dem.par"
width_out=`grep width: $dem_par | awk '{print $2}'`


## Backward geocoding from SAR to map coordinates
## Use nearest neighbour for interpolation - maintain SAR resolution
echo " "
echo "Geocoding file "$file"..."
echo " "
GM geocode_back $file $width_in $gc_map $geocode_out $width_out $nlines_out 0 $format - -
echo " "
echo "Geocoded file "$file
echo " "


## Create geotiff
real=$file_name"_utm_"$file_ext.flt
if [ $tif_flag -eq 1 ]; then
    echo " "
    echo "Creating geotiffed file for "$file"..."
    echo " "
    if [ $file_ext == slc ]; then
	GM cpx_to_real $geocode_out $real $width_out 2 #convert fcomplex to float - intensity
    elif [ $file_ext == mli ]; then
	cp $geocode_out $real
    elif [ $file_ext == cc ]; then
     	cp $geocode_out $real
    elif [ $file_ext == flag ]; then
	echo " "
	echo "Option to geotiff "$file" not currently supported."
	echo " "
    elif [ $file_ext == int ]; then
	GM cpx_to_real $geocode_out $real $width_out 4 #convert fcomplex to float - phase
    elif [ $file_ext == ras ]; then
	cp $geocode_out $real
    elif [ $file_ext == unw ]; then
	cp $geocode_out $real
    else
	echo " "
	echo "Option to geotiff *."$file_ext" not currently supported."
	echo " "
	exit 1
    fi
    GM data2geotiff $dem_par $real 2 $geotif 0.0
    rm -f $real
    echo " "
    echo "Created geotiffed file for "$file
    echo " "
else
    echo " "
    echo "Create geotiff option not selected."
    echo " "
fi


# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
   cat error.log 1>&2
   rm temp_log
else
    :
fi