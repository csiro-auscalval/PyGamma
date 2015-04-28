#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_cr_response:  Script plots the results of process_CR.bash.             *"
    echo "*                                                                             *"
    echo "* input:  [date]   date of scene (eg. 20121130)                               *"
    echo "*         [site]   site number                                                *"
    echo "*         [cr]     CR number                                                  *"
    echo "*         [width]  width of image file                                        *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/04/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_cr_response.bash [date] [site] [cr] [width]"
    }

if [ $# -lt 4 ]
then
    display_usage
    exit 1
fi

date=$1
site=$2
cr=$3
img_wid=$4
stub=$date"_"$site"_CR_"$cr

rg_peak=`grep range_peak_position $stub.txt | awk '{print $3}'`
az_peak=`grep azimuth_peak_position $stub.txt | awk '{print $3}'`

psfile=$stub.ps

rg=$stub"_rg.txt"
az=$stub"_az.txt"

gmtset HEADER_FONT_SIZE 16p HEADER_OFFSET 0c 
gmtset PAGE_ORIENTATION portrait PAPER_MEDIA A3
gmtset LABEL_FONT_SIZE 12p LABEL_OFFSET 0c

grdreformat $stub.ras=rb $stub.grd=nf

if [ ! -e gray.cpt ]; then
    cp /nas/gemd/insar/SOFTWARE/gray.cpt .
    #makecpt -Cgray -T0/255/1 -Z > gray.cpt
fi

val=`echo "$img_wid * 2" | bc -l` 

grdimage $stub.grd -R0/$img_wid/$img_wid/$val -JX9c/9c -Bf16:"Range sample":/f16:"Azimuth sample":nSeW -Cgray.cpt -K > $psfile

#range response

awk '{print $1+"'"$rg_peak"'", $2}' $rg > rg_data

min=`sort -k1 -n rg_data | awk '{print $1}' | head -1`
max=`sort -k1 -n rg_data | awk '{print $1}' | tail -1`
range=-R$min/$max/-70/0
proj=-JX9c/3c

psbasemap -Y9c $range $proj -Bf1g10a20:"":/g10a20f2:::."$date site $site CR #$cr":NseW -K -O >> $psfile

psxy rg_data $range $proj -W4,red -K -O >> $psfile
#awk '{print $1+"'"$rg_peak"'", $3}' $rg | psxy -R$min/$max/-5/5 $proj -Wblue -K -O >> $psfile

# azimuth response
awk '{print $1+"'"$az_peak"'", $2}' $az > az_data

min=`sort -k1 -n az_data | awk '{print $1}' | head -1`
max=`sort -k1 -n az_data | awk '{print $1}' | tail -1`
range=-R-70/0/$min/$max
proj=-JX3c/9c

psbasemap -Y-9c -X9c $range $proj -Bg10a20f2:"":/f1g10a20:::."":nSEw -K -O >> $psfile

psxy az_data -: $range $proj -W4,blue -O >> $psfile

ps2raster -A -Tf -P $psfile
ps2raster -A -Tg -P $psfile
rm -f $psfile






