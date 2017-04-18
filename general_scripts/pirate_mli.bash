#!/bin/bash

## Create geocoded MLI (for identifying percent of NaN pixels in Pirate)


# Creates a geocoded MLI with the boarder pixels having a value of 9999, instead of 0. 
# All pixels in the actual mli region will have a value, so this image is used to determine
# the actual number of pixels in the ifgs and the number of pixels in the boarder.


project=SURAT
sensor=TSX
track=T140A
mas_date=20121205
polar=HH
lks=4

mli=r$mas_date"_"$polar"_"$lks"rlks.mli"
mli_utm=r$mas_date"_"$polar"_"$lks"rlks_utm.mli"
mli_utm2=r$mas_date"_"$polar"_"$lks"rlks_utm.mli2"

diff_dem=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/"diff_"$mas_date"_"$polar"_"$lks"rlks.par"
dem_par=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_"$lks"rlks_utm.dem.par"
gc_map=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track/DEM/$mas_date"_"$polar"_"$lks"rlks_fine_utm_to_rdc.lt"

width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
width_out=`grep width: $dem_par | awk '{print $2}'`


#change from radar to utm geometry
geocode_back $mli $width_in $gc_map $mli_utm $width_out - 0 0 - -

#view mli
#dispwr $mli_utm $width_out 1 0 1 0.35 0

# replace nan (0) with 9999
replace_values $mli_utm 0 9999 $mli_utm2 $width_out 0 2
    



