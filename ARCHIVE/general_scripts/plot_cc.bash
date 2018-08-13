#!/bin/bash

date=20161028-20170201
polar=HH
rlks=4
master=20140804

diff_dem="../../DEM/diff_"$master"_"$polar"_"$rlks"rlks.par"
gc_map="../../DEM/"$master"_"$polar"_"$rlks"rlks_fine_eqa_to_rdc.lt"
dem_par="../../DEM/"$master"_"$polar"_"$rlks"rlks_eqa.dem.par"

width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
width_out=`grep width: $dem_par | awk '{print $2}'`

eqa_cc=$date"_"$polar"_"$rlks"rlks_filt_eqa.cc"
eqa_tif=$date"_"$polar"_"$rlks"rlks_filt_eqa_cc.tif"

xyz=$date"_filt_cc.xyz"
ps=$date"_filt_cc.ps"
png=$date"_filt_cc.png"


# Replace nan values (which are actually 0) with 9999 (enable nan values to be properly dealt with making geotiff and display in arcgis)
replace_values $eqa_cc 0 9999 temp.flt $width_out 0 2

# Geotiff geocoded ifg
data2geotiff $dem_par temp.flt 2 $eqa_tif 9999


rm -rf temp.flt

exit

# Create plot
gmtset MAP_FRAME_TYPE plain
range=-R127.9003788/129.6217677/-16.4278818/-14.7117706
inc=-I0.000069444446126
proj=-JM8
cpt=/g/data/dg9/repo/general_scripts/bcgyr.cpt

# translate geotif to xyz ascii table
gdal_translate -of XYZ -a_nodata 9999 $eqa_tif $xyz  

xyz2grd $xyz -Gtemp.grd $inc $range -V

span=-T-3.14/3.14/0.785
makecpt -F -C$cpt $span -I -Z -V > tif.cpt

grdimage temp.grd -Ctif.cpt $proj $range -Qs -P -V > $ps
#pscoast -R -JM -Dh -Swhite -O -P -V >> $ps

ps2raster $ps -A -E300 -Tg -V

#rm -rf temp.flt temp.grd $xyz $ps 

display $png

