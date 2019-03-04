#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* make_GAMMA_DEM_auto: Script automatically creates a DEM and par file for    *"
    echo "*                      use with GAMMA. Uses S1 master frame extent to         *"
    echo "*                      extract DEM over AOI.                                  *"
    echo "*                                                                             *"
    echo "*                      Uses 19 SRTM 1as geotiff tiles pre-configured for      *"
    echo "*                      GAMMA use (ie. no 0 values & WGS 84 projection)        *"
    echo "*                                                                             *"
    echo "*     NOTE: currently only works with Sentinel-1                              *"
    echo "*                                                                             *"
    echo "*   To be used when AOI is in Australia. Manual DEM creation required for     *" 
    echo "*   AOI outside this region.                                                  *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]       name of GAMMA proc file (eg. gamma.proc)          *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/09/2018, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       24/01/2019, v1.1                            *"
    echo "*                - updated input coordinates to be extracted from S1 file     *"
    echo "*                  list (coordinates calculated from master frame)            *"
    echo "*******************************************************************************"
    echo -e "Usage: make_GAMMA_DEM_auto.bash [proc_file] "
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 
fi

proc_file=$1


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $frame

######################################################################

## File names
dem_file_names

mkdir -p $gamma_dem_dir

cd $gamma_dem_dir

coords=`grep ^DEM_COORDINATES $s1_file_list | cut -d ':' -f 2 | sed 's/[,()]//g'`
min_lat=`echo $coords | awk '{print $2}'`
max_lat=`echo $coords | awk '{print $4}'`
min_lon=`echo $coords | awk '{print $1}'`
max_lon=`echo $coords | awk '{print $3}'`

## Extract AOI as a geotif
gdal_translate -projwin $min_lon $max_lat $max_lon $min_lat $dem_img $track"_"$frame"_temp.tif"

# find nodata value
gdalinfo $track"_"$frame"_temp.tif" > temp
no_data=`grep NoData temp | cut -d "=" -f 2`

## GAMMA regards 0 as null data, change default null value from -3.4028234663852886e+38 to 0 (no data value may vary slightly, so not hardcoded)
## MG: change 0 to 0.0001 (i.e. 0.1 mm) so that water areas are not masked in coregistered slaves
gdalwarp -srcnodata $no_data -dstnodata "0.0001" $track"_"$frame"_temp.tif" $track"_"$frame"_temp2.tif"
# remove nodata value so 0.0001 is recognised as a value
gdal_translate $track"_"$frame"_temp2.tif" $track"_"$frame"_temp3.tif" -a_nodata none

## Create GAMMA DEM and DEM_par from geotif
dem_import $track"_"$frame"_temp3.tif" $dem $dem_par 0 1 - - - - - - -

## Create preview image
gdal_translate -of PNG -outsize 10% 10% $track"_"$frame"_temp3.tif" $track"_"$frame"_dem_preview.png"

rm -rf $track"_"$frame"_temp.tif" $track"_"$frame"_temp2.tif" $track"_"$frame"_temp3.tif" temp $track"_"$frame"_dem_preview.png.aux.xml"



# script end
####################


