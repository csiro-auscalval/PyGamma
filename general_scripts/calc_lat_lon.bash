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
beam=

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



## Determine range and azimuth looks for 'square' pixels
if [ $sensor == ASAR -o $sensor = ERS ]; then
    rlks=$slc_looks
    alks=`echo $slc_looks | awk '{print $1*5}'`
elif [ $sensor == JERS1 ]; then
    rlks=$slc_looks
    alks=`echo $slc_looks | awk '{print $1*3}'`
elif [ $sensor == RSAT1 ]; then
    rlks=$slc_looks
    alks=`echo $slc_looks | awk '{print $1*4}'`
elif [ $sensor == S1 ]; then
    alks=$slc_looks
    rlks=`echo $slc_looks | awk '{print $1*5}'`
elif [ $sensor == PALSAR1 -o $sensor == PALSAR2 ]; then
    rlks=$slc_looks
    alks=`echo $slc_looks | awk '{print $1*2}'`
else
    # CSK, RSAT2, TSX
    rlks=$slc_looks
    alks=$slc_looks
fi

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi


# directories
slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
master_dir=$slc_dir/$master
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir

    if [ -z $beam ]; then # no beam
	mli_name=$master"_"$polar"_"$rlks"rlks"
    else # beam exists
	mli_name=$master"_"$polar"_"$beam"_"$rlks"rlks"
    fi

# coregistered master scene
master_mli=$master_dir/r$mli_name.mli
master_mli_par=$master_dir/r$mli_name.mli.par

# radarcoded DEM file in DEM directory
rdc_dem=$dem_dir/$mli_name"_rdc.dem"


# get width and length of the coregistered master scene
master_width=`grep range_samples: $master_mli_par | awk '{print $2}'`
master_length=`grep azimuth_lines: $master_mli_par | awk '{print $2}'`

if [ -e sar_latlon.txt ]; then
   rm -f sar_latlon.txt
fi

# Calculation of lat and lon for all pixel positions
echo "Starting loop over $master_length azimuth lines and $master_width range pixels"
azline=0
while [ $azline -lt $master_length ]
do
  if (( $azline % 100 == 0 ))
  then
     echo "processing line $azline"
  fi

  # convert radarcoded DEM to ASCII in order to be able to extract the height values at each SAR pixel
  float2ascii $rdc_dem $master_width temp_dem.txt $azline 1 >/dev/null

  # read the heights from the temporary file temp_dem.txt (contains one line only)
  while read -a linearray; do
    printf "%s\n" "${linearray[@]}" > temp_heights.txt
  done < temp_dem.txt
  rm -f temp_dem.txt

  # write the input file for GAMMA routine sarpix_coord_list
  rgpixel=0
  while read height
  do
    printf "%.0f %.0f %s\n" "$azline" "$rgpixel" "$height" >> sar_coord.txt
    ((rgpixel++))
  done < temp_heights.txt
  rm -f temp_heights.txt

  # calculate latitude and longitude for all SAR pixels and save them into sar_latlon.txt
  sarpix_coord_list $master_mli_par - - sar_coord.txt map_coord.txt >/dev/null
  awk '{print $1 " " $2}' map_coord.txt >> sar_latlon.txt
  rm -f sar_coord.txt
  rm -f map_coord.txt

  # next line
  ((azline++))
done
