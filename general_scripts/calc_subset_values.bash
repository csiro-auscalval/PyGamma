#!/bin/bash


display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_subset_values:   calculate subset values to be used in .proc file      *"
    echo "*                       prior to DEM coregistration                           *"
    echo "*                       Not applicable to Sentinel-1 data with bursts/swaths  *"
    echo "*                       v1.1: write rounded subsetting values to .proc file   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                       subset_info.txt as calc. when plotting SLC locations  *"
    echo "* author: Thomas Fuhrmann @ GA    13/12/2016, v1.0                            *"
    echo "*                                 12/06/2018, v1.1                            *"
    echo "*******************************************************************************"
    echo -e "Usage: calc_subset_values.bash [proc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
orientation=`grep Orientation= $proc_file | cut -d "=" -f 2`
slc_looks=`grep SLC_multi_look= $proc_file | cut -d "=" -f 2`

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
master_dir=$slc_dir/$master

subset_info=$slc_dir/subset_info.txt

counter=0
azspsum=0
rgspsum=0
incsum=0
while read line; do
 let counter=counter+1
 if [ $counter -eq 1 ]; then
   : # headerline
 else
    date=`echo $line | awk '{print $1}'`
    lat=`echo $line | awk '{print $2}'`
    lon=`echo $line | awk '{print $3}'`
    az=`echo $line | awk '{print $4}'`
    rg=`echo $line | awk '{print $5}'`
    azsp=`echo $line | awk '{print $6}'`
    rgsp=`echo $line | awk '{print $7}'`
    inc=`echo $line | awk '{print $8}'`

  # find master lat and lon
  if [ $date -eq $master ]; then
    masterlat=`echo $lat`
    masterlon=`echo $lon`
  fi
  # find min/max
  if [ $counter -eq 2 ]; then # set initial values for min/max calculation
    latmin=`echo $lat`
    latmax=`echo $lat`
    lonmin=`echo $lon`
    lonmax=`echo $lon`
    azmin=`echo $az`
    rgmin=`echo $rg`
  else
    if [ $(echo "$lat < $latmin" | bc) -eq 1 ]; then
      latmin=`echo $lat`
    fi
    if [ $(echo "$lat > $latmax" | bc) -eq 1 ]; then
      latmax=`echo $lat`
    fi
    if [ $(echo "$lon < $lonmin" | bc) -eq 1 ]; then
      lonmin=`echo $lon`
    fi
    if [ $(echo "$lon > $lonmax" | bc) -eq 1 ]; then
      lonmax=`echo $lon`
    fi
    if [ $(echo "$az < $azmin" | bc) -eq 1 ]; then
      azmin=`echo $az`
    fi
    if [ $(echo "$rg < $rgmin" | bc) -eq 1 ]; then
      rgmin=`echo $rg`
    fi
  fi
  # sum up for mean value calculation
  azspsum=`echo "$azspsum + $azsp" | bc`
  rgspsum=`echo "$rgspsum + $rgsp" | bc`
  incsum=`echo "$incsum + $inc" | bc`
 fi # headerline?
done < $subset_info

let counter=counter-1 # first line is header line!
pi=3.1415926535

echo "Master latitude: "$masterlat 1>&2
echo "Master longitude: "$masterlon 1>&2
echo "Minimum centre latitude: "$latmin 1>&2
echo "Maximum centre latitude: "$latmax 1>&2
echo "Minimum centre longtitude: "$lonmin 1>&2
echo "Maximum centre longtitude: "$lonmax 1>&2
echo "" 1>&2
echo "Minimum number of azimuth lines: "$azmin 1>&2
echo "Minimum number of range samples: "$rgmin 1>&2
echo "" 1>&2
# Mean az/rg spacing and incidence angle
azspmean=`echo "scale=6; $azspsum/$counter" | bc`
rgspmean=`echo "scale=6; $rgspsum/$counter" | bc`
incmean=`echo "scale=6; $incsum/$counter" | bc`
grrgspmean=`echo "scale=6; $rgspmean/s($incmean/180*$pi)" | bc -l`
echo "Mean azimuth spacing: "$azspmean 1>&2
echo "Mean range spacing (ground): "$grrgspmean 1>&2
echo "" 1>&2

# constants
a=6378137
f=0.0033528107
#
e2=`echo "scale=12; 1/(1 - $f)^2 - 1" | bc`
c=`echo "scale=12; $a*sqrt(1+$e2)" | bc`
# Curvature radii using lat/lon of master scene:
V=`echo "scale=12; sqrt((1+($e2*(c($masterlat/180*$pi))^2)))" | bc -l`
N=`echo "scale=12; $c/$V" | bc`
M=`echo "scale=12; $c/($V)^3" | bc`
#echo $c 1>&2
#echo $V 1>&2
#echo $N 1>&2
#echo $M 1>&2

# Min/Max differences to Master
difflat1=`echo "$masterlat - $latmin" | bc`
difflat2=`echo "$latmax - $masterlat" | bc`
difflon1=`echo "$masterlon - $lonmin" | bc`
difflon2=`echo "$lonmax - $masterlon" | bc`

# Metric differences
difflat1_met=`echo "scale=12; sqrt($M*$N)*$difflat1/180*$pi" | bc`
difflat2_met=`echo "scale=12; sqrt($M*$N)*$difflat2/180*$pi" | bc`
difflon1_met=`echo "scale=12; sqrt($M*$N)*c($masterlat/180*$pi)*$difflon1/180*$pi" | bc -l`
difflon2_met=`echo "scale=12; sqrt($M*$N)*c($masterlat/180*$pi)*$difflon2/180*$pi" | bc -l`

echo "Metric differences to Master scene (minlat, maxlat, minlon, maxlon):"
printf "Minimum latitude: %6.2f\n" $difflat1_met 1>&2
printf "Maximum latitude: %6.2f\n" $difflat2_met 1>&2
printf "Minimum longitude: %6.2f\n" $difflon1_met 1>&2
printf "Maximum longitude: %6.2f\n" $difflon2_met 1>&2
echo "" 1>&2

echo "Calculation of subsetting values for "$orientation" Track..."

if [ $orientation == ascending ]; then
  azoff=`echo "scale=12; $difflat2_met/$azspmean" | bc`
  azlines=`echo "scale=12; $azmin - $difflat1_met/$azspmean - $azoff" | bc`
  rgoff=`echo "scale=12; $difflon2_met/$grrgspmean" | bc`
  rglines=`echo "scale=12; $rgmin - $difflon1_met/$grrgspmean - $rgoff" | bc`
fi
if [ $orientation == descending ]; then
  azoff=`echo "scale=12; $difflat1_met/$azspmean" | bc`
  azlines=`echo "scale=12; $azmin - $difflat2_met/$azspmean - $azoff" | bc`
  rgoff=`echo "scale=12; $difflon1_met/$grrgspmean" | bc`
  rglines=`echo "scale=12; $rgmin - $difflon2_met/$grrgspmean - $rgoff" | bc`
fi

echo "******************"
echo "Subsetting values:"
printf "Range offset: %6.2f\n" $rgoff 1>&2
printf "Range lines: %6.2f\n" $rglines 1>&2
printf "Azimuth offset: %6.2f\n" $azoff 1>&2
printf "Azimuth lines: %6.2f\n" $azlines 1>&2
echo "******************"
echo "Recommended to round up offset values and round down line numbers by several pixels"
echo "" 1>&2

# add a pixel seam and round subsetting values to closest integer
seam=10
# note that this seam could be made adaptive to the ML factors
temp=`echo "scale=0; $rgoff+$seam" | bc`
rg_off=`echo $temp | xargs printf "%.*f\n" 0`
temp=`echo "scale=0; $rglines-$seam" | bc`
rg_lines=`echo $temp | xargs printf "%.*f\n" 0`
temp=`echo "scale=0; $azoff+$seam" | bc`
az_off=`echo $temp | xargs printf "%.*f\n" 0`
temp=`echo "scale=0; $azlines-$seam" | bc`
az_lines=`echo $temp | xargs printf "%.*f\n" 0`


echo "Writting rounded subsetting values to .proc file..."
echo "******************"
strrep=`echo range_offset=$rg_off`
echo $strrep
sed -i "s/range_offset=.*/$strrep/g" $proc_file
strrep=`echo range_lines=$rg_lines`
echo $strrep
sed -i "s/range_lines=.*/$strrep/g" $proc_file
strrep=`echo azimuth_offset=$az_off`
echo $strrep
sed -i "s/azimuth_offset=.*/$strrep/g" $proc_file
strrep=`echo azimuth_lines=$az_lines`
echo $strrep
sed -i "s/azimuth_lines=.*/$strrep/g" $proc_file
echo "******************"
