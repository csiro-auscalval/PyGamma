#!/bin/bash

## Create geocoded MLI (for identifying subset area in ArcGIS)

project=MELBOURNE
sensor=CSK
track=T085A
mas_date=20160723
polar=HH
rlks=2

mli=r$mas_date"_"$polar"_"$rlks"rlks.mli"
mli_utm=r$mas_date"_"$rlks"rlks_utm_subset.mli"
mli_geo=r$mas_date"_"$rlks"rlks_utm_mli_subset.tif"

diff_dem=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/"diff_"$mas_date"_"$polar"_"$rlks"rlks.par"
dem_par=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_"$rlks"rlks_utm.dem.par"
gc_map=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_"$rlks"rlks_fine_utm_to_rdc.lt"

width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
width_out=`grep width: $dem_par | awk '{print $2}'`

#change from radar to utm geometry
geocode_back $mli $width_in $gc_map $mli_utm $width_out - 0 0 - -

#view SLC
#disSLC $slc_utm $width_out 1 0 1 0.5 0

#create geotiff
data2geotiff $dem_par $mli_utm 2 $mli_geo 0.0