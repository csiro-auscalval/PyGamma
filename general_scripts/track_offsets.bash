#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* track_offsets: Map azimuth and range pixel displacements.                   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [master]     earlier scene ID (eg. 20170423)                        *"
    echo "*         [slave]      later scene ID (eg. 20180423)                          *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       13/08/2018, v2.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: track_offsets.bash [proc_file] [master] [slave]"
    }

if [ $# -lt 3 ]
then 
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" -o $3 -lt "10000000" ]; then
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    master=$2
    slave=$3
fi

proc_file=$1


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

######################################################################

## File names
ifg_file_names


track_off_dir=$ifg_dir/track_offsets
mkdir -p $track_off_dir

cd $track_off_dir


## Determine range and azimuth looks for multi-looking
echo "MLI range and azimuth looks: "$rlks $alks
orlks=`echo $rlks $looks | awk '{print $1*$2}'` 
oalks=`echo $alks $looks | awk '{print $1*$2}'` 
echo "Offset image range and azimuth looks: " $orlks $oalks


slc_width=`grep range_samples $r_slave_slc_par | awk '{print $2}'`
width=`echo $slc_width $orlks | awk '{printf "%.0f", $1/$2}'`
rwin=64
azwin=`echo "$oalks $orlks $rwin" | awk '{print $1/$2, $3}' | awk '{print $1*$2}'`
echo "rwin = "$rwin" ; azwin = "$azwin
echo "width = "$width

## calculate and refine offset between interferometric SLC pair
## Also done in during interferogram production so test if this has been run
if [ ! -e $ifg_off ]; then
    returns=$track_off_dir/returns
    echo "" > $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    echo "" >> $returns
    GM create_offset $r_master_slc_par $r_slave_slc_par $off < $returns
    GM offset_pwr $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off offs snr 64 64 - 2 128 128 7.0
    GM offset_fit offs snr $ifg_off coffs coffsets
    rm -f $returns
fi

## Precise estimation of the offsets with measurement offset equal to MLI resolution
GM offset_pwr_tracking $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off offsN snrN $rwin $azwin offsetsN 2 4.0 $orlks $oalks

## Convert range and azimuth offsets to displacement map
GM offset_tracking offsN snrN $r_master_slc_par $ifg_off coffsN coffsetsN 2 4.0 1

## Extract range and azimuth displacements and magnitude to separate files
GM cpx_to_real coffsN coffsN_range $width 0
GM cpx_to_real coffsN coffsN_range $width 1
GM cpx_to_real coffsN coffsN_mag $width 3


# script end
####################