#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* track_offsets: Map azimuth and range pixel displacements.                   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [master]     earlier scene ID (eg. 20121130)                        *"
    echo "*         [slave]      later scene ID (eg. 20121211)                          *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: track_offsets.bash [proc_file] [master] [slave]"
    }

if [ $# -lt 3 ]
then 
    display_usage
    exit 1
fi

proc_file=$1

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`

mas=$2
slv=$3

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
int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`


mas_dir=$slc_dir/$mas
slv_dir=$slc_dir/$slv
int_dir=$int_dir/$mas-$slv

returns=$projdir/$track_dir/returns
echo "" > $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns

## files located in SLC directories
mas_mli=$mas_dir/r$mas"_"$polar"_"$ifm_looks"rlks.mli"
mas_mli_par=$mas_mli.par
mas_slc=$mas_dir/r$mas"_"$polar.slc
mas_slc_par=$mas_slc.par
slv_mli=$slv_dir/r$slv"_"$polar"_"$ifm_looks"rlks.mli"
slv_mli_par=$slv_mli.par
slv_slc=$slv_dir/r$slv"_"$polar.slc
slv_slc_par=$slv_slc.par
mas_slv_name=$mas-$slv"_"$polar"_"$ifm_looks"rlks"
off=$int_dir/$mas_slv_name.off

## Determine range and azimuth looks for multi-looking
rlks=`grep range_looks $slv_mli_par | awk '{print $2}'`
alks=`grep azimuth_looks $slv_mli_par | awk '{print $2}'`
echo "MLI range and azimuth looks: "$rlks $alks

orlks=`echo $rlks $ifm_looks | awk '{print $1*$2}'` 
oalks=`echo $alks $ifm_looks | awk '{print $1*$2}'` 
echo "Offset image range and azimuth looks: " $orlks $oalks

slc_width=`grep range_samples $slv_slc_par | awk '{print $2}'`
width=`echo $slc_width $orlks | awk '{printf "%.0f", $1/$2}'`
rwin=64
azwin=`echo "$oalks $orlks $rwin" | awk '{print $1/$2, $3}' | awk '{print $1*$2}'`
echo "rwin = "$rwin" ; azwin = "$azwin
echo "width = "$width

## calculate and refine offset between interferometric SLC pair
## Also done in during interferogram production so test if this has been run
if [ ! -e $off ]; then
    GM create_offset $mas_slc_par $slv_slc_par $off < $returns
    GM offset_pwr $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off offs snr 64 64 - 2 128 128 7.0
    GM offset_fit offs snr $off coffs coffsets
fi

## Precise estimation of the offsets with measurement offset equal to MLI resolution
GM offset_pwr_tracking $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off offsN snrN $rwin $azwin offsetsN 2 4.0 $orlks $oalks

## Convert range and azimuth offsets to displacement map
GM offset_tracking offsN snrN $mas_slc_par $off coffsN coffsetsN 2 4.0 1

## Extract range and azimuth displacements and magnitude to separate files
GM cpx_to_real coffsN coffsN_range $width 0
GM cpx_to_real coffsN coffsN_range $width 1
GM cpx_to_real coffsN coffsN_mag $width 3

