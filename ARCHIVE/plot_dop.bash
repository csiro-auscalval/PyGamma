#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_dop:  Script xxxxxx     *"
    echo "*                                                                             *"
    echo "*                                                                             *"
    echo "*                                                                             *"
    echo "* input:  [dop_file]   name of GAMMA dop file                                 *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       27/06/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_dop.bash [dop_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

dop=$1
psfile=`echo $dop | sed 's/.dop/_dop.ps/g'`
maxx=`awk '{print $1}' $dop | tail -1`
miny=`awk '{print $3}' $dop | sort -n | head -1 | awk '{print $1-500}'`
maxy=`awk '{print $3}' $dop | sort -n | tail -1 | awk '{print $1+500}'`

range=-R0/$maxx/$miny/$maxy
proj=-JX9c/6c

gmtset ANNOT_FONT_SIZE_PRIMARY 10p LABEL_FONT_SIZE 12p HEADER_FONT_SIZE 14p

awk '{print $1, $2}' $dop | psxy $proj $range -Bf1000a5000:"Range bin (pixels)":/f100a500:"Doppler Centroid (Hz)"::."Doppler Centroid":nSeW -Wblue -K > $psfile

awk '{print $1, $3}' $dop | psxy $proj $range -B -Wblack -K -O >> $psfile

awk '{print $1, $4}' $dop | psxy $proj $range -B -Wred -K -O >> $psfile

awk '{print $1, $5}' $dop | psxy $proj $range -B -Wgreen -O >> $psfile

ps2raster -A -Tg -P $psfile

rm -f $psfile
