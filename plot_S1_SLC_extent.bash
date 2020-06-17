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
    echo "*         [type]       processing type ('slc' for creating SLC, 'resize' for  *"
    echo "*                      resizing SLC or 'subset' for subsetting SLC by bursts) *"
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
PBS_processing_details $project $track $scene 

######################################################################

## File names
slc_file_names
s1_slc_file_names
mli_file_names

cd $scene_dir


if [ $type == 'slc' ]; then
    tab=$slc_name"_tab"
    burst_file=slc_burst_values.txt
    psfile=$slc_name"_Full_SLC.ps"
    header="Full SLC"
    pdf=$slc_name"_Full_SLC.pdf"
    mkdir -p $pdf_dir/full_SLCs
    out_dir=$pdf_dir/full_SLCs
elif [ $type == 'resize' ]; then
    tab=$slc_name"_resize_tab"
    burst_file=slc_resized_burst_values.txt
    psfile=$slc_name"_Resized_SLC.ps"
    header="Resized SLC"
    pdf=$slc_name"_Resized_SLC.pdf"
    mkdir -p $pdf_dir/resized_SLCs
    out_dir=$pdf_dir/resized_SLCs
elif [ $type == 'subset' ]; then
    tab=$slc_name"_tab"
    burst_file=slc_subset_burst_values.txt
    psfile=$slc_name"_Subset_SLC.ps"
    header="Subset SLC"
    pdf=$slc_name"_Subset_SLC.pdf"
    mkdir -p $pdf_dir/subset_SLCs
    out_dir=$pdf_dir/subset_SLCs
else
    echo "Option not recognised, check details and re-run script."
fi


## Check number of bursts and their corner coordinates and put into central file
echo "Number of Bursts per Swath" > $burst_file
echo " " >> $burst_file
while read file; do
    par=`echo $file | awk '{print $2}'`
    tops=`echo $file | awk '{print $3}'`
    ScanSAR_burst_corners $par $tops > temp1
    swath=`awk 'NR==7 {print $6}' temp1`
    echo "Swath: "$swath >> $burst_file
    start=`grep start_time: $par | awk '{print $2}'`
    echo "   start time: "$start >> $burst_file
    bursts=`awk 'NR==8 {print $6}' temp1`
    echo "   total bursts: "$bursts >> $burst_file
    echo "Num     Upper_Right                     Upper_left                      Lower_Left                      Lower_Right" >> $burst_file
    tail -n +10 temp1 > temp2
    head -n -9 temp2 > temp3
    awk '{print $2"\t"$3" "$4"\t"$5" "$6"\t"$7" "$8"\t"$9" "$10}' temp3 >> $burst_file
    echo " " >> $burst_file
done < $tab
rm -f temp1 temp2 temp3


## Number of bursts per swath
sed -n '/Swath: IW1/,/Num/p' $burst_file > temp1
sw1_burst=`awk 'NR==3 {print}' temp1 | awk '{print $3}'`
sed -n '/Swath: IW2/,/Num/p' $burst_file > temp1
sw2_burst=`awk 'NR==3 {print}' temp1 | awk '{print $3}'`
sed -n '/Swath: IW3/,/Num/p' $burst_file > temp1
sw3_burst=`awk 'NR==3 {print}' temp1 | awk '{print $3}'`

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
top="-2.9"
middle="-3.2"
bottom="-3.5"
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
sw1_len=`echo $sw1_burst*0.9 | bc -l`
sw2_len=`echo $sw2_burst*0.9 | bc -l`
sw3_len=`echo $sw3_burst*0.9 | bc -l`

## Adjust position based on length of swath
pos1=`echo $pos1+27-$sw1_burst | bc -l` 
pos2=`echo $pos2+27-$sw2_burst | bc -l` 
pos3=`echo $pos3+27-$sw3_burst | bc -l` 

## Plot swaths
gmtset PAPER_MEDIA A4
outline="-JX21c/27c"
range="-R0/100/0/100"
psbasemap $outline $range -G -K -P > $psfile
pstext $outline $range -O -K -P -m -N <<EOF >> $psfile
> 0 100 12 0 4 LT 14p 6i l
$project $track $scene $polar $header
EOF

convert $slc_png slc.ras 
psimage slc.ras -W3.5c/3c -C14.8c/24.2c -O -K -P >> $psfile
pstext $outline $range -O -K -P -m -N <<EOF >> $psfile
> 5 97 12 0 4 LT 13p 3i l
Swath 1 ($sw1_burst)
EOF

convert $slc_png1 slc1.ras
psimage slc1.ras -W4.5c/$sw1_len"c" -C0c/$pos1"c" -O -K -P >> $psfile
pstext $outline $range -O -K -P -m -N <<EOF >> $psfile
> 32 97 12 0 4 LT 13p 3i l
Swath 2 ($sw2_burst)
EOF

convert $slc_png2 slc2.ras
psimage slc2.ras -W4.5c/$sw2_len"c" -C5.5c/$pos2"c" -O -K -P >> $psfile
pstext $outline $range -O -K -P -m -N <<EOF >> $psfile
> 58 97 12 0 4 LT 13p 3i l
Swath 3 ($sw3_burst)
EOF

convert $slc_png3 slc3.ras
psimage slc3.ras -W4.5c/$sw3_len"c" -C11c/$pos3"c" -O -P >> $psfile

ps2raster -A -Tf $psfile


rm -rf $psfile sorted_end_times

# Removing the temporary .ras files used by psimage
rm slc.ras slc1.ras slc2.ras slc3.ras

cp $pdf $out_dir

rm -f gmt.history gmt.conf


# script end 
####################
