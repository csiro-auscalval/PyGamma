#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_rspec:  Plots the range frequency spectrum as computed by GAMMA MSP.   *"
    echo "*                                                                             *"
    echo "* input:  [rspec_file]  rspec file (*.rspec)                                  *"
    echo "*         [scene]       scene ID   (e.g. 20070112)                            *"
    echo "*         [raw_dir]     location of raw data                                  *"
    echo "*         [msp_par]     SLC MSP parameter file                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       15/08/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_rspec.bash [rspec_file] [scene] [raw_dir] [msp_par]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

rspec=$1
scene=$2
#raw_dir=$3
#msp_par=$4

year=`echo $scene | awk '{print substr($1,1,4)}'`
mth=`echo $scene | awk '{print substr($1,5,2)}'`
day=`echo $scene | awk '{print substr($1,7,2)}'`

#track=`echo $raw_dir | cut -d "_" -f5` # for final naming convention
#frame=`echo $raw_dir | cut -d "_" -f6` # for final naming convention

#track=999
#frame=4565
#frame=`echo $raw_dir | cut -d "_" -f5`

#sensor=ERS1
#polar=VV

#sensor=`grep title: $msp_par | awk '{print $2}'` # works for ERS, need to check for other sensors
#polar=`grep channel/mode: $msp_par | awk '{print $2}'` # works for ERS, need to check for other sensors

psfile=`echo $rspec | sed 's/.rspec/_rspec.ps/g'`
minx=`awk '{print $1}' $rspec | head -1`
maxx=`awk '{print $1}' $rspec | tail -1`
miny=`awk '{print $2}' $rspec| sort -n | head -1`
maxy=`awk '{print $2}' $rspec | sort -n | tail -1`

range=-R$minx/$maxx/$miny/$maxy
proj=-JX9c/6c

gmtset ANNOT_FONT_SIZE_PRIMARY 10p LABEL_FONT_SIZE 12p HEADER_FONT_SIZE 14p

awk '{print $1, $2}' $rspec | psxy $proj $range -Bf1a5g1000:"Frequency (x10@+6@+ Hz)":/f1a5:"Intensity (dB)"::."Range Spectrum":nSeW -Wblue > $psfile

ps2raster -A -Tf -P $psfile

rm -f $psfile