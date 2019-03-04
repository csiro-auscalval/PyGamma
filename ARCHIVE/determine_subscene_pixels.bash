#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* determine_subscene_pixels:  Determines the subscene parameters from points  *"
    echo "*                             calculated in ArcGIS and updates the            *"
    echo "*                             gamma.proc file with these values.              *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [text_file]  name of text file generated in ArcGIS                  *"
    echo "*         <beam>       beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       18/06/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: determine_subscene_pixels.bash [proc_file] [text_file] <beam>"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
text_file=$2
beam=$3

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
mas=`grep Master_scene= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2
echo "" 1>&2
echo "Calculate Subscene" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING_PROJECT: "$project $track_dir
echo ""
echo "Calculate Subscene"

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

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

mas_dir=$slc_dir/$mas

#if beams exist, need to identify beam in file name
if [ -z $beam ]; then # no beam
    slc_par=$mas_dir/$mas"_"$polar.slc.par
    diff_par=$dem_dir/"diff_"$mas"_"$polar"_0rlks.par"
else # beam exists
    slc_par=$mas_dir/$mas"_"$polar"_"$beam.slc.par
    diff_par=$dem_dir/"diff_"$mas"_"$polar"_"$beam"_0rlks.par"
fi

cd $proj_dir/$track_dir


# remove any carriage returns in text file
cat $text_file | tr -d '\r' > temp1
# remove header
tail -n +2 temp1 > temp2
# X coordinates
awk -F "," '{print $5}' temp2 > temp3
# Y coordinates
awk -F "," '{print $6}' temp2 > temp4
# height
awk -F "," '{print $7}' temp2 > temp5
paste temp4 temp3 temp5 > temp6

if [ -e range -o azimuth ]; then
    rm -rf range azimuth
fi

while read point; do
    if [ ! -z "${point}" ]; then
	GM coord_to_sarpix $slc_par - - $point $diff_par
    fi
done < temp6

grep "SLC/MLI range, azimuth pixel (int):" output.log | awk '{print $7}' >> range
grep "SLC/MLI range, azimuth pixel (int):" output.log | awk '{print $8}' >> azimuth

min_range=`sort -k1 -n range | awk 'NR==1 {print $1}'`
max_range=`sort -k1 -n range | awk 'NR==4 {print $1}'`
min_azimuth=`sort -k1 -n azimuth | awk 'NR==1 {print $1}'`
max_azimuth=`sort -k1 -n azimuth | awk 'NR==4 {print $1}'`
range_lines=`expr "$max_range" - "$min_range"`
azimuth_lines=`expr "$max_azimuth" - "$min_azimuth"`

cp $proc_file temp7

sed -i "s/range_offset=-/range_offset=$min_range/g" temp7
sed -i "s/range_lines=-/range_lines=$range_lines/g" temp7
sed -i "s/azimuth_offset=-/azimuth_offset=$min_azimuth/g" temp7
sed -i "s/azimuth_lines=-/azimuth_lines=$azimuth_lines/g" temp7

mv temp7 $proc_file
rm -rf temp* range azimuth


# script end 
####################


# logs are not required to be saved
cd $proj_dir/$track_dir 
rm -rf command.log output.log error.log