#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_mlcc:  Script xxxxxx     *"
    echo "*                                                                             *"
    echo "*                                                                             *"
    echo "*                                                                             *"
    echo "* input:  [mlcc_file]  name of GAMMA mlcc file                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       27/06/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_mlcc.bash [mlcc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

mlcc=$1
psfile=`echo $mlcc | sed 's/.mlcc/_mlcc.ps/g'`
maxrange=`awk '{print $1}' $mlcc | tail -1`

range=-R0/$maxrange/-0.25/1.25
proj=-JX9c/6c

gmtset ANNOT_FONT_SIZE_PRIMARY 10p LABEL_FONT_SIZE 12p HEADER_FONT_SIZE 14p

awk '{print $1, $2}' $mlcc | psxy $proj $range -B -Wred -K > $psfile

awk '{print $1, $3}' $mlcc | psxy $proj $range -B -Wblue -K -O >> $psfile

awk '{print $1, $4}' $mlcc | psxy $proj $range -Bf100a500:"Range bin (pixels)":/f0.25a0.5:"Correlation phase"::."Line to Line Correlation Phase (radians)":nSeW -Wgreen -O >> $psfile

ps2raster -A -Tf -P $psfile

rm -f $psfile
