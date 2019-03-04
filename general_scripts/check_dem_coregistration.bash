#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* check_dem_coregistration: Script takes the simulated radar DEM and the      *"
    echo "*                           reference master MLI to enable coregistration     *"
    echo "*                           checking.                                         *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         <start>      starting line of SLC (optional, default: 1)            *"
    echo "*         <nlines>     number of lines to display (optional, default: 4000)   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       15/08/2016, v1.0                            *"
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
    echo -e "Usage: check_dem_coregistration.bash [proc_file] <start> <nlines>"
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
dem_master_names
dem_file_names

cd $proj_dir/$track


r_mli_width=`grep range_samples: $r_dem_master_mli_par | awk '{print $2}'`
r_mli_lines=`grep azimuth_lines: $r_dem_master_mli_par | awk '{print $2}'`
rdc_width=`grep range_samp_1: $dem_diff | awk '{print $2}'`
rdc_lines=`grep az_samp_1: $dem_diff | awk '{print $2}'`

if [ $# -lt 3 -a $r_mli_lines -gt 4000 ]; then
    echo  " "
    echo "Image length is "$r_mli_lines", auto setting length to 4000 lines. If different length required, enter no. lines."
    echo  " "
    start=1
    nlines=4000
elif [ $# -eq 3 -a $r_mli_lines -gt 4000 ]; then
    start=$2
    nlines=$3
else
    start=1
    nlines=-
fi
dis2pwr $r_dem_master_mli $dem_rdc_sim_sar $r_mli_width $rdc_width $start $nlines - - - - 0

echo " "
echo "Checked coregistration of DEM with reference SLC MLI."
echo " "

# script end
####################
