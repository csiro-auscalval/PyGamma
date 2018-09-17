#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* make_GAMMA_DEM_auto: Script automatically creates a DEM and par file for    *"
    echo "*                      use with GAMMA. Uses scene extents to determine min    *"
    echo "*                      and max coordinate values and adds a buffer to ensure  *"
    echo "*                      DEM covers AOI.                                        *"
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
PBS_processing_details $project $track 

######################################################################

## File names
auto_dem_creation
dem_file_names


cd $proj_dir/$track

mkdir -p $gamma_dem_dir

## Get Sentinel-1 scene extents from each scene's raw data manifest.safe file
while read input; do
    scene=`echo $input | awk '{print $1}'`
    frame_num=`echo $input | awk '{print $4}'`
    manifest=$raw_data_track_dir/F$frame_num/$scene/S1*_IW_SLC*.SAFE/manifest.safe
    grep "<gml:coordinates>" $manifest | sed -e 's/<[^>]*>//g' | xargs -n1 >> "scene_coords_F"$frame_num
done < $s1_download_list

## join multiple frame lists together (get overall extent for concatenated scenes)
ls scene_coords_F* > temp1
while read file; do
    paste $file >> temp2
done < temp1

## split latitude and longitude and identify min and max values
awk -F "\"*,\"*" '{print $1}' temp2 | sort -k 1 -g > lat
awk -F "\"*,\"*" '{print $2}' temp2 | sort -k 1 -g > lon
min_lat1=`head -1 lat`
max_lat1=`tail -1 lat`
min_lon1=`head -1 lon`
max_lon1=`tail -1 lon`
rm -rf temp1 temp2 scene_coords_F* lat lon



## other sensors extents  -  TO DO


## Add buffer to values to scene extents
buffer=0.2 # equates to ~20km
min_lat=`echo "$min_lat1 - $buffer" | bc -l`
max_lat=`echo "$max_lat1 + $buffer" | bc -l`
min_lon=`echo "$min_lon1 - $buffer" | bc -l`
max_lon=`echo "$max_lon1 + $buffer" | bc -l`

echo "INPUT SCENE COORDINATES FOR AUTO DEM CREATION (with ~20km buffer)" > $dem_scene_extent_results
echo "" >> $dem_scene_extent_results
echo "Min Lat: "$min_lat >> $dem_scene_extent_results
echo "Max Lat: "$max_lat >> $dem_scene_extent_results
echo "Min Lon: "$min_lon >> $dem_scene_extent_results
echo "Max_Lon: "$max_lon >> $dem_scene_extent_results


## Extract AOI as a geotif
gdal_translate -projwin $min_lon $max_lat $max_lon $min_lat $dem_img temp.tif

## GAMMA regards 0 as null data, change default null value from -3.4028234663852886e+38 to 0
gdalwarp -srcnodata "-3.40282346638529011e+38" -dstnodata "0" temp.tif temp2.tif

## Create GAMMA DEM and DEM_par from geotif
dem_import temp2.tif $dem $dem_par 0 1
rm -rf temp.tif temp2.tif

# script end
####################


