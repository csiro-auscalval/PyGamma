#!/bin/bash

## Create geocoded SLC (for identifying subset area in ArcGIS)

project=MERAPI
sensor=PALSAR1
track=T096D
mas_date=20081014
polar=HH

slc=r$mas_date"_"$polar.slc
slc_eqa=r$mas_date"_eqa.slc"
slc_geo=r$mas_date"_eqa_slc.tif"

diff_dem=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/"diff_"$mas_date"_"$polar"_0rlks.par"
dem_par=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_0rlks_eqa.dem.par"
gc_map=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_0rlks_fine_eqa_to_rdc.lt"

width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
width_out=`grep width: $dem_par | awk '{print $2}'`

#change from radar to eqa geometry
geocode_back $slc $width_in $gc_map $slc_eqa $width_out - 0 1 - -

#view SLC
#disSLC $slc_eqa $width_out 1 0 1 0.5 0

#create geotiff
data2geotiff $dem_par $slc_eqa 4 $slc_geo 0.0