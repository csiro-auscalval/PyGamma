#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* check_ref_master_dem: Script takes the simulated radar DEM and the          *"
    echo "*                       reference master MLI to enable coregistration         *"
    echo "*                       checking.                                             *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         <start>      starting line of SLC (optional, default: 1)            *"
    echo "*         <nlines>     number of lines to display (optional, default: 4000)   *"
    echo "*         <beam>       beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       15/08/2016, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: check_ref_master_dem.bash [proc_file] <start> <nlines> <beam>"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

if [ $# -eq 2 ]; then
    start=$2
else
    start=1
fi
if [ $# -eq 3 ]; then
    nlines=$3
else
    nlines=4000
fi

proc_file=$1
beam=$4

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
slc_looks=`grep SLC_multi_look= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING PROJECT: "$project $track_dir 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir
echo ""

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
master_dir=$slc_dir/$master


## Determine range and azimuth looks for 'square' pixels
if [ $sensor == ASAR -o $sensor = ERS ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*5}'` 
elif [ $sensor == JERS1 ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*3}'` 
elif [ $sensor == RSAT1 ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*4}'` 
elif [ $sensor == S1 ]; then
    slc_alks=$slc_looks 
    slc_rlks=`echo $slc_looks | awk '{print $1*5}'` 

elif [ $sensor == PALSAR1 -o $sensor == PALSAR2 ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*2}'` 
else
    # CSK, RSAT2, TSX
    slc_rlks=$slc_looks
    slc_alks=$slc_looks
fi

mli_name=$master"_"$polar"_"$slc_rlks"rlks"
master_mli=$master_dir/r$mli_name.mli
master_mli_par=$master_mli.par
rdc_sim_sar=$dem_dir/$mli_name"_rdc.sim"
rdc_par_file=$dem_dir/"diff_"$mli_name.par


cd $proj_dir/$track_dir

mli_width=`grep range_samples: $master_mli_par | awk '{print $2}'`
mli_lines=`grep azimuth_lines: $master_mli_par | awk '{print $2}'`
rdc_width=`grep range_samp_1: $rdc_par_file | awk '{print $2}'`
rdc_lines=`grep az_samp_1: $rdc_par_file | awk '{print $2}'`


if [ $# -lt 3 -a $mli_lines -gt 4000 ]; then
    echo  " "
    echo "Image length is "$mli_lines", auto setting length to 4000 lines. If different length required, enter no. lines."
    echo  " "
    start=1
    nlines=4000
elif [ $# -eq 3 -a $mli_lines -gt 4000 ]; then
    start=$2
    nlines=$3
else
    start=1
    nlines=-
fi
dis2pwr $master_mli $rdc_sim_sar $mli_width $rdc_width $start $nlines - - - - 0

echo " "
echo "Checked SLC MLI and reference DEM images."
echo " "

