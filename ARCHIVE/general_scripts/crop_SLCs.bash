#!/bin/bash


display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* crop_SLCs: crop the spatial extent of SLC files (e.g. ocean areas)          *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA    10/08/2017, v0.9                            *"
    echo "*                                 include into process_gamma workflow         *"
    echo "*                                 to enable correct number of az looks        *"
    echo "*******************************************************************************"
    echo -e "Usage: crop_SLCs.bash [proc_file roff nr loff nl alks_factor]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1
beam=

roff=$2
nr=$3
loff=$4
nl=$5
alks_factor=$6

echo "Azimuth-multilooking factor w.r.t. range: "$alks_factor

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
mode=`grep Sensor_mode= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
slc_looks=`grep SLC_multi_look= $proc_file | cut -d "=" -f 2`
rlks=$slc_looks
alks=`echo $slc_looks $alks_factor | awk '{print $1*$2}'`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir


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



## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

echo " "
echo "Parameters for cropping (roff nr loff nl): "$roff" "$nr" "$loff" "$nl

# directories
slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
scene_list=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`

while read scene; do
    if [ ! -z $scene ]; then
	echo " "
	echo "Cropping SLC for "$scene" with "$rlks" range and "$alks" azimuth looks..."
        cd $slc_dir/$scene
        scn_name=$scene"_"$polar
        mv $scn_name".slc" $scn_name"_full.slc"
        mv $scn_name".slc.par" $scn_name"_full.slc.par"
        mv $scn_name"_"$rlks"rlks.mli" $scn_name"_"$rlks"rlks_full.mli"
        mv $scn_name"_"$rlks"rlks.mli.par" $scn_name"_"$rlks"rlks_full.mli.par"
        SLC_copy $scn_name"_full.slc" $scn_name"_full.slc.par" $scn_name".slc" $scn_name".slc.par" - - $roff $nr $loff $nl
        multi_look $scn_name".slc" $scn_name".slc.par" $scn_name"_"$rlks"rlks.mli" $scn_name"_"$rlks"rlks.mli.par" $rlks $alks 0
    fi
done < $scene_list
