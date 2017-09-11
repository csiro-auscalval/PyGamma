#!/bin/bash


display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_lat_lon:   calculate latitude and longitude for each SAR pixel         *"
    echo "*                 needed for the usage of GAMMA interferograms in StaMPS      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA    21/07/2016, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: calc_lon_lat.bash [proc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
slc_looks=`grep SLC_multi_look= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir


## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING PROJECT: "$project $track_dir 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir
echo ""

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi



rlks=4
alks=16


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi


# directories
int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`
ifg_dir=$int_dir/
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir






mli_name=$master"_"$polar"_"$rlks"rlks"
utm_dem=$dem_dir/$mli_name"_utm.dem"
utm_dem_par=$utm_dem.par







# get width and length of the coregistered master scene
dem_width=`grep width: $dem_par | awk '{print $2}'`
dem_length=`grep nlines: $dem_par | awk '{print $2}'`

if [ -e dem_latlon.txt ]; then
   rm -f dem_latlon.txt
fi

# Calculation of lat and lon for all pixel positions
echo "Starting loop over $dem_length azimuth lines and $dem_width range pixels"
azline=0
while [ $azline -lt $dem_length ]
do
    if (( $azline % 100 == 0 )); then
	echo "processing line $azline"
    fi

    # convert geocoded DEM to ASCII in order to be able to extract the height values at each SAR pixel
    float2ascii $dem $dem_width temp_dem.txt $azline 1 >/dev/null

    # read the heights from the temporary file temp_dem.txt (contains one line only)
    while read -a linearray; do
	printf "%s\n" "${linearray[@]}" > temp_heights.txt
    done < temp_dem.txt
    rm -f temp_dem.txt

  # write the input file for GAMMA routine sarpix_coord_list
    rgpixel=0 
    while read height
    do
	printf "%.0f %.0f %s\n" "$azline" "$rgpixel" "$height" >> dem_coord.txt
	((rgpixel++))
    done < temp_heights.txt
    rm -f temp_heights.txt

  # calculate latitude and longitude for all DEM pixels and save them into sar_latlon.txt
    sarpix_coord_list $dem_par - - dem_coord.txt map_coord.txt >/dev/null
    awk '{print $1 " " $2}' map_coord.txt >> dem_latlon.txt
    rm -f dem_coord.txt
    rm -f map_coord.txt
    
  # next line
    ((azline++))
done
