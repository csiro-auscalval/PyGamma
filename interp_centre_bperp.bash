#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* interp_centre_bperp:  Extract the perpendicular baseline value.             *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*         [bperp_file]  bperp file produced during interferogram              *"
    echo "*                       processing (*._bperp.par).                            *"
    echo "*         [rlks]       range multi-look value                                 *"
    echo "*         [alks]       azimuth multi-look value                               *"
    echo "*         <beam>       Beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/04/2015, v1.0                            *"
    echo "* author: Sarah Lawrie @ GA       22/06/2015, v1.1                            *"
    echo "*           - update to enable incorporation into post ifm processing         *"
    echo "*******************************************************************************"
    echo -e "Usage: interp_centre_bperp.bash [proc_file] [bperp_file]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

proc_file=$1
file=$2

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi


# extract line numbers of useful data
flen=`cat $file | wc -l`
len1=`echo $flen - 5 | bc -l`
len2=`echo $len1 - 15 | bc -l`

# extract data from bperp file
awk '{print $1, $2, $8}' $file | head -$len1 | tail -$len2 > xyz

# calculate centre pixel
ctry=`awk 'NR==4 {printf "%.0f", $3/2}' $file`
ctrx=`awk 'NR==4 {printf "%.0f", $6/2}' $file`

# calculate max extents of input
maxx=`awk '{print $2}' xyz | sort -n | tail -1`
maxy=`awk '{print $1}' xyz | sort -n | tail -1`

range=-R0/$maxx/0/$maxy

# interpolate the data at 1x1 resolution
surface xyz $range -Gout.grd -I1

# make plot
#grd2cpt out.grd -Crainbow -E8 > col.cpt
#grdimage out.grd -JX10c $range -Ccol.cpt -K > out.ps
#echo $ctrx $ctry | psxy -Sx1c -W5,black -R -J -O -K >> out.ps
#psscale -D10.5c/1.5c/3c/0.3c -Ccol.cpt -O >> out.ps

# convert grid back to list
grd2xyz out.grd | awk '{print $1, $2, $3}' > xyz2

# find centre baseline value
bperp=`grep "$ctrx $ctry" xyz2 | awk '{print $3}'`

echo $bperp

echo $bperp

rm -f xyz xyz2 out.grd temp1 temp2
