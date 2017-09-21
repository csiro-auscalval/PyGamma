#!/bin/bash

## Create geocoded MLI (for identifying subset area in ArcGIS)

project=NORTH_KOREA
sensor=S1
track=T134D
mas_date=20170829
polar=VV
rlks=10

date=20170910

mli=r$date"_"$polar"_"$rlks"rlks.mli"
mli_eqa=r$date"_"$rlks"rlks_eqa.mli"
mli_geo=r$date"_"$rlks"rlks_eqa_mli.tif"

diff_dem=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/"diff_"$mas_date"_"$polar"_"$rlks"rlks.par"
dem_par=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_"$rlks"rlks_eqa.dem.par"
gc_map=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_"$rlks"rlks_fine_eqa_to_rdc.lt"

width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
width_out=`grep width: $dem_par | awk '{print $2}'`

#change from radar to eqa geometry
geocode_back $mli $width_in $gc_map $mli_eqa $width_out - 0 0 - -

#view SLC
#disSLC $slc_eqa $width_out 1 0 1 0.5 0

#create geotiff
data2geotiff $dem_par $mli_eqa 2 $mli_geo 0.0


