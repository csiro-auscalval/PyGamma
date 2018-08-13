#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_azsp:  Script plots the Azimuth doppler spectrum as computed by        *"
    echo "*             GAMMA MSP.                                                      *"
    echo "*                                                                             *"
    echo "*                                                                             *"
    echo "* input:  [azsp_value]   azsp value                                           *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       27/06/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_azsp.bash [azsp_value]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi


azsp=$1
psfile=`echo $azsp | sed 's/.azsp/_azsp.ps/g'`
maxrange=`awk '{print $1}' $azsp | tail -1`

range=-R0/1/0/1
proj=-JX9c/6c

gmtset ANNOT_FONT_SIZE_PRIMARY 10p LABEL_FONT_SIZE 12p HEADER_FONT_SIZE 14p

awk '{print $1, $2}' $azsp | psxy $proj $range -Bf0.1a0.2:"Normalised Azimuth Frequency / PRF":/f0.1a0.2:"Normalised Power Spectral Density"::."Azimuth Doppler Spectrum":nSeW -Wblue > $psfile

ps2raster -A -Tf -P $psfile

rm -f $psfile