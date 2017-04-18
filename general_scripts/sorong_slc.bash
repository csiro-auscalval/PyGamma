#!/bin/bash

## Create geocoded MLIs of Sorong data for dgal presentation

date=20081014

mli=r$date"_HH_4rlks.mli"
mli_utm=$date"_utm.mli"
mli_txt=$date"_mli.txt"
psfile=$date"_mli.ps"

diff_dem=/g/data1/dg9/INSAR_ANALYSIS/SORONG/PALSAR1/GAMMA/T387A/DEM/diff_20081014_HH_4rlks.par
dem_par=/g/data1/dg9/INSAR_ANALYSIS/SORONG/PALSAR1/GAMMA/T387A/DEM/20081014_HH_4rlks_utm.dem.par
gc_map=/g/data1/dg9/INSAR_ANALYSIS/SORONG/PALSAR1/GAMMA/T387A/DEM/20081014_HH_4rlks_fine_utm_to_rdc.lt

width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
width_out=`grep width: $dem_par | awk '{print $2}'`

geocode_back $mli $width_in $gc_map $mli_utm $width_out - 1 0 - -

gmtset MAP_FRAME_TYPE plain
range=-R132.1538764/132.96970973986/-1.02556509626/-0.1041762
inc=-I0.000069444445
proj=-JM8
cpt=/g/data/dg9/repo/general_scripts/bcgyr.cpt

# Convert file to one column ascii
float2ascii $mli_utm 1 $mli_txt 0 -

# Convert ascii to grd
xyz2grd $mli_txt -N0 $range -ZTLa -r $inc -Gmli.grd

# Make colour scale
grdinfo mli.grd | tee temp
z_min=`grep z_min: temp | awk '{print $3}'`
z_max=`grep z_max: temp | awk '{print $5}'`
span=-T$z_min/$z_max/1
span=-T0/1/1
makecpt -Cgray $span -I -Z > mli.cpt

# Plot ifm
grdimage mli.grd -Cmli.cpt $proj $range -Qs -P -V > $psfile

# Export image to .png
ps2raster $psfile -A -E300 -Tt -V
