#!/bin/bash


display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_alks_factor:     calculate the factor for azimuth multi-looking        *"
    echo "*                       from azimuth pixel spacing, range pixel spacing and   *"
    echo "*                       incidence angle in *.slc.par files                    *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                       list of scenes (eg. scenes.list)                      *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA    27/02/2018, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: calc_alks_factor.bash [proc_file] [scene_list]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1
list=$2

# Constants
pi=3.1415926535

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2
echo "" 1>&2

# directories
slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`

# initialise parameters for loop
counter=0
azspsum=0
rgspsum=0
incsum=0
# loop over all SLC files in scene.list
while read file; do
  let counter=counter+1
  scene=$file
  scene_dir=$slc_dir/$scene
  slc_name=$scene"_"$polar

  # grep information on latitude and longitude and save into txt file to be used for offset calculations
  slc_par=$scene_dir"/"$slc_name".slc.par"
  azsp=`grep azimuth_pixel_spacing $slc_par | awk '{print $2}'`
  rgsp=`grep range_pixel_spacing $slc_par | awk '{print $2}'`
  inc=`grep incidence_angle $slc_par | awk '{print $2}'`

  # sum up for mean value calculation
  azspsum=`echo "$azspsum + $azsp" | bc`
  rgspsum=`echo "$rgspsum + $rgsp" | bc`
  incsum=`echo "$incsum + $inc" | bc`
done < $list

# Mean az/rg spacing and incidence angle
azspmean=`echo "scale=6; $azspsum/$counter" | bc`
rgspmean=`echo "scale=6; $rgspsum/$counter" | bc`
incmean=`echo "scale=6; $incsum/$counter" | bc`
grrgspmean=`echo "scale=6; $rgspmean/s($incmean/180*$pi)" | bc -l`

# Output and calculation of Azimuth ML factor
echo "******************"
echo "Mean azimuth spacing [m]: "$azspmean 1>&2
echo "Mean range spacing (ground) [m]: "$grrgspmean 1>&2
# check is 1 if ground rg spacing is greater than az spacing (usual case)
check=`echo $grrgspmean'>'$azspmean | bc -l`
if [ $check -eq 1 ]; then
  # Calculate azimuth multi-look factor to retrieve square pixels
  az_ml_factor=`printf %.0f $(echo "$grrgspmean/$azspmean" | bc -l)`
  echo "Azimuth Multi-looking factor to obtain square pixels: "$az_ml_factor 1>&2
  # note that printf %.0f is used to round to the nearest integer
else
  echo "Azimuth spacing is greater than range spacing, please define ML factors manually."
fi
echo "******************"
echo "" 1>&2

# for usage within SLC processing: this parameter is the Azimuth Multi-looking factor: $az_ml_factor
# we have to think about what to do if the azimuth spacing is greater than the range spacing (Sentinel-1)
