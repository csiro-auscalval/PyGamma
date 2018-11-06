#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_subscene:  Extracts a subset of an SLC image and corresponding      *"
    echo "*                    multi-look (MLI) image after scene coregistration.       *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20121130)                                *"
    echo "*         [roff]       offset to starting range sample                        *"
    echo "*         [nr]         number of range samples                                *"
    echo "*         [loff]       offset to starting line                                *"
    echo "*         [nl]         number of lines to copy                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: extract_subscene.bash [proc_file] [scene] [roff] [nr] [loff] [nl]"
    }

if [ $# -lt 6 ]
then 
    display_usage
    exit 1
fi

scene=$2
roff=$3
nr=$4
loff=$5
nl=$6

proc_file=$1

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
slc_looks=`grep slc_multi_look= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
mas=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $scene 1>&2
echo "" 1>&2
echo "Extract Subscene" 1>&2

## Insert scene details top of NCI .o file
echo "" 
echo "" 
echo "PROCESSING_PROJECT: "$project $track_dir $scene
echo "" 
echo "Extract Subscene" 

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`


scene_dir=$SLC_dir/$scene

slc=$scene_dir/r$scene"_"$polar.slc
slc_par=$scene_dir/$slc.par
sub_slc=$scene_dir/sub_r$scene"_"$polar.slc
sub_slc_par=$scene_dir/$sub_slc.par

mli=$scene_dir/r$scene"_"$polar"_"$slc_looks"rlks.mli"
mli_par=$scene_dir/$mli.par
sub_mli=$scene_dir/sub_r$scene"_"$polar"_"$slc_looks"rlks.mli"
sub_mli_par=$scene_dir/$sub_mli.par


# fcase for the command SLC_copy
sfmt=`grep image_format:  $slc_par | awk '{print $2}'`
if [ $sfmt == "SCOMPLEX" ]; then
    fcase=4 
else
    fcase=2 
fi

# clip full SLC to subset
GM SLC_copy $slc $slc_par $sub_slc $sub_slc_par $fcase - $roff $nr $loff $nl

# clip full MLI to subset
GM MLI_copy $mli $mli_par $sub_mli $sub_mli_par $roff $nr $loff $nl

