#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_SLC_loc_ers:  Creates a location map image of SLC extent using GMT     *"
    echo "*                    for ERS data.                                            *"
    echo "*                                                                             *"
    echo "* input:  [scene]        scene ID   (e.g. 20070112)                           *"
    echo "*         [msp_par]      SLC MSP parameter file                               *"
    echo "*         [ers_sensor]   ERS1 or ERS2                                         *"
    echo "*         [ras_image]    MLI image (.ras)                                     *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       16/07/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_SLC_loc_ers.bash [scene] [msp_par] [ers_sensor] [ras_image]"
    }

if [ $# -lt 4 ]
then 
    display_usage
    exit 1
fi

scene=$1
msp_par=$2
sensor_name=$3
ras=$4
polar=VV
logo=/short/dg9/insar/dg9-apps/dg9-apps/GAMMA/gamma_scripts/GEOSCIENCE_INLINE.ras

year=`echo $scene | awk '{print substr($1,1,4)}'`
mth=`echo $scene | awk '{print substr($1,5,2)}'`
day=`echo $scene | awk '{print substr($1,7,2)}'`
track=`grep track: $msp_par | awk '{print $2}'`
frame=`grep frame: $msp_par | awk '{print $2}'`
orientation=`grep orientation: $msp_par | awk '{print $2}'`

psfile=$scene"_"$polar"_location_map.ps"
proj=-JM10
layout=-P 

# Calculate SLC location plot extents
s_org=`awk '{print $1}' slc_coords | sort -n | head -1`
n_org=`awk '{print $1}' slc_coords | sort -n | tail -1`
e_org=`awk '{print $2}' slc_coords | sort -n | tail -1`
w_org=`awk '{print $2}' slc_coords | sort -n | head -1`
val=0.7 # amount to add to create plot area

# converts any exponential numbers to decimal
s_temp=`printf "%f\n" $s_org`
n_temp=`printf "%f\n" $n_org`
e_temp=`printf "%f\n" $e_org`
w_temp=`printf "%f\n" $w_org`
val_temp=`printf "%f\n" $val`

s=$(expr $s_org-$val | bc)
n=$(expr $n_org+$val | bc)
e=$(expr $e_org+$val | bc)
w=$(expr $w_org-$val | bc)

bounds=-R$w/$e/$s/$n

## Set GMT parameters
gmtset BASEMAP_TYPE plain LABEL_FONT_SIZE 8p PAPER_MEDIA A4 

# Page outline
map_outline="-JX18c/27c"
range="-R0/100/0/10"
psbasemap $map_outline -X1.5c -Y1.4c -R0/100/0/10 -Bnesw $layout -K > $psfile

# Header information
pstext $map_outline $range -Bnesw -K -O <<EOF >> $psfile
31.5 9.65 18 0 0 0 SLC Data Location Map
EOF

# Scene information
pstext $map_outline $range -Bnesw -K -O <<EOF >> $psfile
17 9.35 13 0 0 0 Sensor: $sensor_name  Date: $year-$mth-$day  Track: $track  Frame: $frame
EOF

# LOS arrows
if [ $orientation == ascending ]; then
locate="83 5.5"
psxy $map_outline $range -SVb0.08/0.3/0.2 -G0 -O -K $layout <<EOF >> $psfile
$locate 345 2
EOF
psxy $map_outline $range -SVt0.08/0.3/0.2 -G0 -O -K $layout <<EOF >> $psfile
$locate 75 1
EOF
pstext $map_outline $range -D-0.4/-0.6 -O -K $layout <<EOF >> $psfile
79.6 6.24 11 0 0 TL Azimuth
EOF
pstext $map_outline $range -D-1.1/0.2 -O -K $layout <<EOF >> $psfile
95.3 5.58 11 0 0 TL Range
EOF
else
locate="85 5.7"
psxy $map_outline $range -SVb0.08/0.3/0.2 -G0 -O -K $layout <<EOF >> $psfile
$locate 195 2
EOF
psxy $map_outline $range -SVt0.08/0.3/0.2 -G0 -O -K $layout <<EOF >> $psfile
$locate 285 1
EOF
pstext $map_outline $range -D-0.4/-0.6 -O -K $layout <<EOF >> $psfile
81.7 5.52 11 0 0 TL Azimuth
EOF
pstext $map_outline $range -D-1.1/0.2 -O -K $layout <<EOF >> $psfile
78.7 5.78 11 0 0 TL Range
EOF
fi

# Add SLC MLI ras image
psimage $ras -W8c/9c -C2.7/1.5/BL -Fthicker -K -O >> $psfile

# Add GA logo
pslegend -R0/45/0/30 -JX45c/30c -D12.5/-4.5/10c/5c/BL -K -O <<EOF >> $psfile
I $logo 5c BL
EOF

# World map with scene centre location
centre_x=`awk 'NR==5 {printf "%i\n", $2}' slc_coords`
centre_y=`awk 'NR==5 {printf "%i\n", $1}' slc_coords`
pscoast -Rd -X12.5c -Y19c -JG$centre_x/$centre_y/5c -B15g15 -S182/211/255 -Di -A5000 -G240,240,240 -W1/2/100/100/100 $layout -K -O >> $psfile

# Mark scene centre on overview
awk 'NR==5 {print $2, $1}' slc_coords | psxy -J -R -Sa0.3c -Gred -K -O >> $psfile

# Add political boundaries and coastlines to SLC location map
pscoast -X-10.8c -Y-6.7c $bounds $proj -Dh -B0.2g1a1neSW -S182/211/255 -N1 -Ia -W $layout -K -O >> $psfile

# Plot out SLC frame
awk 'NR<5 {print $2, $1}' slc_coords | psxy $bounds $proj $layout -W5/255/0/0 -L -m -O >> $psfile

ps2raster $psfile -Tf

rm -f $psfile

#evince $scene"_"$polar"_location_map.pdf"


