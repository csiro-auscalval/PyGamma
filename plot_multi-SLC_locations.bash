#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_multi-SLC_locations:  ID location of multiple SLCs to determing if     *"
    echo "*                            they belong on the same track.                   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*         [scene_list]  list of scenes (eg. scenes.list)                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/04/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_multi-SLC_locations.bash [proc_file] [scene_list]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

list=$2

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $scene 1>&2

## Copy output of Gamma programs to log files
GM()
{
    echo $* | tee -a command.log
    echo
    $* >> output.log 2> temp_log
    cat temp_log >> error.log
    #cat output.log (option to add output results to NCI .o file if required)
}

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`

echo >! polygons.txt
echo >! labels.txt
echo >! min_max_lat.txt
echo >! min_max_lon.txt

poly=polygons.txt
label=labels.txt
min_max_lat=min_max_lat.txt #used to determine overall min and max coordinates for plotting
min_max_lon=min_max_lon.txt
echo ">" >> $poly

psfile=SLC_Locations.ps

# Extract coordinates for polygons and labels
while read file; do
    scene=$file
    scene_dir=$slc_dir/$scene
    coords=$scene_dir/slc_coords
    if [ ! -e $coords ]; then
	echo "ERROR: SLC coordinates file does not exist!"
	exit 1
    fi

    # coordinates for scene
    s=`awk '{print $1}' $coords | sort -n | head -1 | awk '{print $1-1}'`
    n=`awk '{print $1}' $coords | sort -n | tail -1 | awk '{print $1+1}'`
    e=`awk '{print $2}' $coords | sort -n | tail -1 | awk '{print $1+1}'`
    w=`awk '{print $2}' $coords | sort -n | head -1 | awk '{print $1-1}'`
    centre=`awk 'NR==5 {print $2, $1}' $coords` # centre point

    # populate polygons file (x,y) for each point
    echo $s > temp1
    echo $n > temp2
    echo $e > temp3
    echo $w > temp4
    paste temp3 temp2 >> $poly # E-N coord
    paste temp4 temp2 >> $poly # W-N coord
    paste temp4 temp1 >> $poly # W-S coord
    paste temp3 temp1 >> $poly # E-S coord
    echo ">" >> $poly

    # collect overall min and max coordinate values
    echo $s >> $min_max_lat
    echo $n >> $min_max_lat
    echo $e >> $min_max_lon
    echo $w >> $min_max_lon

    # populate labels file for each scene
    echo $centre > temp5
    echo "10 0 1 0" > temp6 
    echo $scene > temp7
    paste temp5 temp6 temp7 >> $label

done < $list

#remove any blank lines in files
sed '/^$/d' $poly > polygons2.txt
sed '/^$/d' $label > labels2.txt
sed '/^$/d' $min_max_lat > min_max_lat2.txt
sed '/^$/d' $min_max_lon > min_max_lon2.txt


# Extract minimum and maximum coordinate values for plot boundary
s_org=`awk '{print $1}' min_max_lat2.txt | sort -n | head -1 | awk '{print $1}'`
n_org=`awk '{print $1}' min_max_lat2.txt | sort -n | tail -1 | awk '{print $1}'`
e_org=`awk '{print $1}' min_max_lon2.txt | sort -n | tail -1 | awk '{print $1}'`
w_org=`awk '{print $1}' min_max_lon2.txt | sort -n | head -1 | awk '{print $1}'`
val=2 # amount to add to create plot area

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

# Create plot
bounds=-R$w/$e/$s/$n
proj=-JM10
layout=-P 

# set some GMT parameters
gmtset BASEMAP_TYPE plain LABEL_FONT_SIZE 16p FRAME_PEN 1.5p

# add political boundaries and coastlines to map
pscoast $bounds $proj -Dh -Bf0.5a2neSW $layout -S200 -K -N1 -Ia -W > $psfile

# plot out SLC frames
psxy polygons2.txt $bounds $proj $layout -L -W5/255/0/0 -L -m -K -O >> $psfile

# label SLC frames
pstext labels2.txt $bounds $proj $layout -O -K >> $psfile


## Plot list of epoch

#awk '{print $1}' $1 > dates

#epoch=$output"_"$sthr"m_"$2"yr_epoch_bperp.txt"

#awk '{print $1}' $epoch | psxy -Y-11.5c $bounds $proj -G225,225,225 -W6,black -Sc0.42c -K -O -m >> $psfile
#awk '{print 15.5, 20-NR*0.5, "7.5 0 1 MC", NR}' $epoch |  pstext $bounds $proj -Gblack -K -O >> $psfile
#awk '{printf "%4.0f\n", $1}' $epoch | awk '{print 16.6, 20-NR*0.5, "9 0 1 MC", $1}' |  pstext $bounds $proj -Gblack -O >> $psfile


ps2raster $psfile -A -Tf

evince SLC_Locations.pdf

mv -f SLC_Locations.pdf $SLC_dir

rm -f $psfile temp* $poly $label $min_max_lat $min_max_lon polygons2.txt labels2.txt min_max_lat2.txt min_max_lon2.txt
