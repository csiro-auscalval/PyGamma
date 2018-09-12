#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_master_DEM_img: create Erdas Imagine (*.img) file of input SRTM 1as  *"
    echo "*                        DEM geotif tiles that have been pre-configured for   *"
    echo "*                        for use in GAMMA (no 0 values & WGS 84 projection).  *"
    echo "*                                                                             *"
    echo "*   *.img file used by 'make_GAMMA_DEM_auto.bash' to automatically create     *"
    echo "*    a GAMMA DEM which covers a Sentinel-1 scene extent (inlcuding a buffer)  *"
    echo "*                                                                             *"
    echo "*  Script doesn't need to be run again once *.img file is created.            *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       12/09/2018, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage:create_master_DEM_img.bash"
    }

## Load GAMMA to access GAMMA programs
source /g/data1/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_CONFIG

## Directories
proj_dir=/g/data1/dg9/MASTER_DEM
input_tiles=$proj_dir/input_geotif_tiles

## File names
dem_extents=$proj_dir/DEM_tile_extents
out_dem=GAMMA_DEM_SRTM_1as_mosaic


cd $input_tiles

## Create text file with geotif tile extents for reference purposes
echo "Tile Min_Lat Max_Lat Min_Lon Max_lon" > $dem_extents

# get list of input tiles
ls dem_srtm_1as_*.tif > tile_list

# get tile extents and save to file
while read tile; do
    gdalinfo $tile > temp1
    sed -n '22,25p;26q' temp1 > temp2
    awk '{print $4}' temp2 | sed 's/,//g' | sort -u > lon
    awk '{print $5}' temp2 | sed 's/)//g' | sort -u > lat
    tile_min_lat=`head -1 lat`
    tile_max_lat=`tail -1 lat`
    tile_min_lon=`head -1 lon`
    tile_max_lon=`tail -1 lon`
    echo $tile $tile_min_lat $tile_max_lat $tile_min_lon $tile_max_lon >> $dem_extents
    rm -rf temp1 temp2 lon lat
done < tile_list
rm -rf tile_list


## Mosiac geotifs to single *.img file for later subsetting for GAMMA DEMs
cd $proj_dir

# create virtual mosaic of all geotifs
gdalbuildvrt $out_dem.vrt $input_tiles/*.tif

# convert to Erdas Imagine (.img) format (no file size limit)
gdal_translate -of HFA $out_dem.vrt $out_dem.img

# check metadata
# gdalinfo $out_dem.img


# script end
####################

