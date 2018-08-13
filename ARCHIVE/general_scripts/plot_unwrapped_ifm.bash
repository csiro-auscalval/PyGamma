#!/bin/bash

## Create image of geocoded unwrapped and filtered ifm of Sorong data for dgal presentation

int=5
top_pad=0.01
bot_pad=0.2
side_pad=0.05


#mli_eqa=20081014-20090114_HH_4rlks_eqa.unw
#mli_eqa=20081014-20090114_HH_20rlks_filt_int_eqa.flt


# grd files created in process_ifm.bash
mli_grd=20081014-20090114_HH_20rlks_eqa.grd
#mli_grd=20081014-20090114_HH_20rlks_filt_int_eqa.grd

mli_txt=20081014-20090114_unw.txt
psfile=20081014-20090114_unw.ps

lon_min=132.1547097
lon_max=132.969154151
lat_min=-1.02500962958
lat_max=-0.1052874

range=-R$lon_min/$lon_max/$lat_min/$lat_max

lat_min2=$(echo $lat_min - $bot_pad | bc)
lat_max2=$(echo $lat_max + $top_pad | bc)
lon_min2=$(echo $lon_min - $side_pad | bc)
lon_max2=$(echo $lon_max + $side_pad | bc)

plotrange=-R$lon_min2/$lon_max2/$lat_min2/$lat_max2


#tif_width=6.96c
#tif_height=7.71c
dpi=300
scale_title="LOS Phase (radians)"


gmtset MAP_FRAME_TYPE plain
gmtset MAP_FRAME_PEN thick
gmtset MAP_TICK_LENGTH_PRIMARY 3p/1.8p
gmtset PROJ_LENGTH_UNIT c
gmtset FORMAT_GEO_MAP ddd:mm
gmtset FONT_ANNOT_PRIMARY 8.5p
proj=-JM8

inc=-I0.000069444445

cpt=/g/data/dg9/repo/general_scripts/bcgyr.cpt

pos_cpt=/g/data/dg9/repo/general_scripts/gr.cpt
neg_cpt=/g/data/dg9/repo/general_scripts/bg.cpt


# Make colour scale
grdinfo $mli_grd | tee temp1
z_min=`grep z_min: temp1 | awk '{print $3}'`
z_max=`grep z_max: temp1 | awk '{print $5}'`
#span=-T$z_min/$z_max/1
#span=-T-3.14/3.14/1
#makecpt -C$cpt $span -I -Z > phs.cpt

makecpt -C$neg_cpt -T-32/0/1 -N -Z -Fr > neg.cpt
makecpt -C$pos_cpt -T0/7/1 -N -Z -Fr > pos.cpt
cp neg.cpt phs.cpt
cat pos.cpt >> phs.cpt
rm -f neg.cpt pos.cpt

# Plot ifm
grdimage $mli_grd -Cphs.cpt $proj $plotrange -Qs -K -P -V > $psfile

# Plot coast and colour scale
pscoast -R -JM -Dh -Swhite -K -O -P -V >> $psfile
#psscale -D4/1/6/0.3h -S -Al -B3 -Cphs.cpt -K -O -P -V >> $psfile
psscale -D4/1/6/0.3h -S -Al -B$int -Cphs.cpt -K -O -P -V >> $psfile

# Plot basemap
psbasemap $proj $plotrange -Ba0.5f0.25/a0.5f0.25WSen -K -O -P -V >> $psfile

# Position of scale bar
temp1=$(echo $lon_max2 - $lon_min2 | bc -l)
temp2=$(echo $temp1/2 | bc -l)
scale_lon=$(echo $lon_min2 + $temp2 | bc -l)
scale_lat=$(echo $lat_min2 + 0.155 | bc -l)

# Plot colour scale label
pstext $proj $plotrange -F+f10p,Helvetica-Bold -N -K -O -P -V <<EOF >> $psfile
$scale_lon $scale_lat $scale_title
EOF

# Add pi symbols (for filt ifm)
#pstext $proj $plotrange -F+f11p -Gwhite  -O -K -P -V <<EOF >> $psfile
#132.23 -1.1 @~p
#EOF

#pstext $proj $plotrange -F+f11p -Gwhite -O -K -P -V <<EOF >> $psfile
#132.75 -1.1 @~p
#EOF



# Plot LOS arrow
t1=$(echo $lon_min2 + 0.74 | bc -l)
t2=$(echo $lat_min2 + 0.93 | bc -l)

t3=$(echo $lon_min2 + 0.723 | bc -l)
t4=$(echo $lat_min2 + 0.988 | bc -l)

t5=$(echo $lon_min2 + 0.675 | bc -l)
t6=$(echo $lat_min2 + 1.1 | bc -l)

t7=$(echo $lon_min2 + 0.865 | bc -l)
t8=$(echo $lat_min2 + 0.998 | bc -l)

psxy $proj $plotrange -W0.8 -Sv0.25+e -Gblack -O -K -P -V <<EOF >> $psfile
$t1 $t2 105 1.2
EOF
psxy $proj $plotrange -W0.8 -Sv0.25+e -Gblack -O -K -P -V <<EOF >> $psfile
$t3 $t4 17 0.6
EOF
pstext $proj $plotrange -F+f8p,Helvetica-Bold,+j -Gwhite -O -K -P -V <<EOF >> $psfile
$t5 $t6 TL Az
EOF
pstext $proj $plotrange -F+f8p,Helvetica-Bold,+j -Gwhite -O -P -V <<EOF >> $psfile
$t7 $t8 BR LOS
EOF


# Export image to .png
ps2raster $psfile -A -E300 -Tg -V
