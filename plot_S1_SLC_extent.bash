#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_S1_SLC_extent: Script plots a Sentinel-1 scene's SLC and swath/bursts  *"
    echo "*                     in a PDF to determine shape/size of scene. Used for     *"
    echo "*                     working out which scene to use as the resize reference  *"
    echo "*                     scene and which bursts to subset by.                     *"
    echo "*                                                                             *"
    echo "*   Script is called within 'process_S1_SLC.bash' and 'resize_S1_SLC.bash'.   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20180423)                                *"
    echo "*         [type]       processing type ('slc' for creating frame SLC, or      *"
    echo "*                                'subset' for subsetting frame SLC by bursts) *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_process_S1_SLC.bash [proc_file] [scene] [type]"
    }

if [ $# -lt 3 ]
then 
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" ]; then 
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    scene=$2
fi

proc_file=$1
type=$3

##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $frame $scene 

######################################################################

## File names
slc_file_names
s1_slc_file_names
mli_file_names

cd $scene_dir


if [ $type == 'slc' ]; then
    tab=$slc_name"_tab"
    burst_file=slc_burst_values.txt
    psfile=$slc_name"_Frame_SLC.ps"
    header="Frame SLC"
    pdf=$slc_name"_Frame_SLC.pdf"
    mkdir -p $pdf_dir/frame_SLCs
    out_dir=$pdf_dir/frame_SLCs
elif [ $type == 'subset' ]; then
    tab=$slc_name"_tab"
    burst_file=slc_subset_burst_values.txt
    psfile=$slc_name"_Subset_Frame_SLC.ps"
    header="Subset Frame SLC"
    pdf=$slc_name"_Subset_Frame_SLC.pdf"
    mkdir -p $pdf_dir/subset_frame_SLCs
    out_dir=$pdf_dir/subset_frame_SLCs
else
    echo "Option not recognised, check details and re-run script."
fi

## Swath stop times
grep end_time: $slc_par1 | awk '{print $2}' > temp1
echo "IW1" > temp2
paste temp2 temp1 > temp3
grep end_time: $slc_par2 | awk '{print $2}' > temp1
echo "IW2" > temp2
paste temp2 temp1 >> temp3
grep end_time: $slc_par3 | awk '{print $2}' > temp1
echo "IW3" > temp2
paste temp2 temp1 >> temp3
sort -k2 -n temp3 > sorted_end_times
rm -f temp1 temp2 temp3


## Determine swath order
first=`awk 'NR==1 {print $1}' sorted_end_times`
second=`awk 'NR==2 {print $1}' sorted_end_times`
third=`awk 'NR==3 {print $1}' sorted_end_times`


## Auto positioning of swaths on plot
top="-0.9c"
middle="-1.2c"
bottom="-1.5c"
if [ $first == "IW1" ]; then
    pos1=$top
elif [ $first == "IW2" ]; then
    pos2=$top
elif [ $first == "IW3" ]; then
    pos3=$top
fi
if [ $second == "IW1" ]; then
    pos1=$middle
elif [ $second == "IW2" ]; then
    pos2=$middle
elif [ $second == "IW3" ]; then
    pos3=$middle
fi
if [ $third == "IW1" ]; then
    pos1=$bottom
elif [ $third == "IW2" ]; then
    pos2=$bottom
elif [ $third == "IW3" ]; then
    pos3=$bottom
fi

## Auto length of swaths
sw_len=`echo 12*0.95 | bc -l`

## Plot swaths
gmtset PS_MEDIA A4
outline="-JX23c/26c"
range="-R0/100/0/100"
psbasemap $outline $range -Bnesw -K -P > $psfile
pstext $outline $range -F+cTL+f15p -O -K -P <<EOF >> $psfile
$project $track $frame $scene $polar $header
EOF
psimage $slc_png -W4c/4c -Fthin -C14c/22c -O -K -P >> $psfile
pstext $outline $range -F+f13p -O -K -P <<EOF >> $psfile
5.5 88.5 Swath 1
EOF
psimage $slc_png1 -W4.5c/$sw_len"c" -Fthin -C-1c/$pos1 -O -K -P >> $psfile
pstext $outline $range -F+f13p -O -K -P <<EOF >> $psfile
26 88.5 Swath 2
EOF
psimage $slc_png2 -W4.5c/$sw_len"c" -Fthin -C4c/$pos2 -K -O -P >> $psfile
pstext $outline $range -F+f13p -K -O -P <<EOF >> $psfile
47 88.5 Swath 3 
EOF
psimage $slc_png3 -W4.5c/$sw_len"c" -Fthin -C9c/$pos3 -O -P >> $psfile

ps2raster -Tf $psfile
rm -rf $psfile sorted_end_times

cp $pdf $out_dir

rm -f gmt.history gmt.conf


# script end 
####################
