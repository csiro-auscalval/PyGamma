#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* make_GAMMA_DEM: Script takes an ASCII file created in ArcGIS and creates    *"
    echo "*                 a DEM for use with GAMMA.                                   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]    name of GAMMA proc file (eg. gamma.proc)             *"
    echo "*         [ascii_file]   name of ascii DEM file (eg. surat.txt)               *"
    echo "*         optional:                                                           *"
    echo "*            <west>:     western longitude for subsetting                     *"
    echo "*            <east>:     eastern longitude for subsetting                     *"
    echo "*            <south>:    southern latitude for subsetting                     *"
    echo "*            <north>:    northern latitude for subsetting                     *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       31/03/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: make_GAMMA_DEM.bash [proc_file] [ascii_file] <optional_parameters>"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

ascii_file=$2
proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
dem_dir_ga=`grep DEM_location_GA= $proc_file | cut -d "=" -f 2`
dem_dir_mdss=`grep DEM_location_MDSS= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project 1>&2

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

## Subset DEM
if [ $# -gt 2 -a $# -lt 6 ]; then
    echo "ERROR: enter west, east, south and north parameters for subsetting, in that order"
elif [ $# -eq 6 ]; then
    cut=1
    subset=-R$2/$3/$4/$5
else
    :
fi

## Copy dem data from MDSS and convert to GAMMA format
if [ $platform == NCI ]; then
    xxxxx
    dem_dir=$proj_dir/gamma_dem
    cd $dem_dir
    mdss ls $dem_dir_mdss > dem.list # /dev/null allows mdss command to work properly in loop
    echo >> dem.list # adds carriage return to last line of file (required for loop to work)
    while read dem; do
	if [ ! -z $dem ]; then # skips any empty lines
	    mdss get $dem_dir_mdss/$dem < /dev/null $dem_dir # /dev/null allows mdss command to work properly in loop
	    tar xvzf $dem
	    rm -rf $dem
	fi
    done < dem.list
    rm -f dem.list
    file=`ls *.txt`
    name=`echo $file | sed 's/\.[^.]*$//'`
else 
    cd $dem_dir_ga
    name=`echo $ascii_file | sed 's/\.[^.]*$//'`
fi

## Convert ArcGIS ascii text file to grd format
xyz2grd $name.txt -G$name"_org.grd" -E -V

# Optionally subset the DEM
#if [ $cut -eq 1 ]; then
#    mv $name"_org.grd" temp.grd
#    grdcut temp.grd -G$name"_org.grd" $subset 
#    rm -f temp.grd
#else
#    :
#if

## Extract grd information for inclusion into DEM parameter file
grdinfo $name"_org.grd" > temp1
offset=`awk 'NR==9 {print $5}' temp1` #add_offset
scale=`awk 'NR==9 {print $3}' temp1` #scale_factor
width=`awk 'NR==6 {print $11}' temp1` #nx
length=`awk 'NR==7 {print $11}' temp1` #ny
lat_post=-`awk 'NR==7 {print $7}' temp1` #y_inc (negative)
lon_post=`awk 'NR==6 {print $7}' temp1 ` #x_inc
lat=`awk 'NR==7 {print $5}' temp1` #y_max
lon=`awk 'NR==6 {print $3}' temp1` #x_min

## Convert grd format to GAMMA format (4 byte floating point)
grdreformat $name"_org.grd" $name"_org.dem"=bf -N -V

## Change to big endian
swap_bytes $name"_org.dem" $name.dem 4

## Create parameter file
echo "EQA" > temp2
echo "WGS84" >> temp2
echo "1" >> temp2
echo $name.dem >> temp2
echo "REAL*4" >> temp2
echo $offset >> temp2
echo $scale >> temp2
echo $width >> temp2
echo $length >> temp2
echo $lat_post $lon_post >> temp2
echo $lat $lon >> temp2
create_dem_par $name.dem.par < temp2

## Correct missing values in DEM
replace_values $name.dem 0 0.0001 temp_dem $width 0 2
replace_values temp_dem -32768 0 temp_dem2 $width 0 2
interp_ad temp_dem2 $name.dem $width 9 40 81 2 2 1 

## TEMP FILE CLEANUP
rm temp1 temp2 $name"_org.grd" $name"_org.dem" temp_dem temp_dem2


# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
   cat error.log 1>&2
   rm temp_log
else
   :
fi
