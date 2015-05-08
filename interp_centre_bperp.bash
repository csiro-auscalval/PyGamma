#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* interp_centre_bperp:  Extract the perpendicular baseline value.             *"
    echo "*                                                                             *"
    echo "* input:  [bperp_file]  bperp file produced during interferogram              *"
    echo "*                       processing (*._bperp.par).                            *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/04/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: interp_centre_bperp.bash [bperp_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

file=$1

# extract line numbers of useful data
flen=`cat $file | wc -l`
len1=`echo $flen - 5 | bc -l`
len2=`echo $len1 - 15 | bc -l`

# extract data from bperp file
awk '{print $1, $2, $8}' $file | head -$len1 | tail -$len2 > xyz

# calculate centre pixel
ctry=`awk 'NR==4 {printf "%.0f", $3/2}' $1`
ctrx=`awk 'NR==4 {printf "%.0f", $6/2}' $1`

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

rm -f xyz xyz2 out.grd

echo $bperp
