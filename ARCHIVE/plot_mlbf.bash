#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_mlbf:  Script plots the MLBF result as computed by GAMMA MSP.          *"
    echo "*                                                                             *"
    echo "*                                                                             *"
    echo "* input:  [mlbf_value]   mlbf value                                           *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       27/06/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_mlbf.bash [mlbf_value]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

mlbf=$1
psfile=`echo $mlbf | sed 's/.mlbf/_mlbf.ps/g'`
maxrange=`awk '{print $1}' $mlbf | tail -1`
maxy=`awk '{printf "%g\n",  $2}' $mlbf | sort -n | tail -1`
miny=`awk '{printf "%g\n", $2}' $mlbf | sort -n | head -1`

range=-R0/$maxrange/0/0.002
proj=-JX9c/6c

gmtset ANNOT_FONT_SIZE_PRIMARY 10p LABEL_FONT_SIZE 12p HEADER_FONT_SIZE 14p

awk '{printf "%g %g\n", $1, $2}' $mlbf | psxy $proj $range -Bf1000a2000:"":/f0.0001a0.0002:""::."Multi Look Beat Frequency":nSeW -Wblue > $psfile

ps2raster -A -Tf -P $psfile

rm -f $psfile