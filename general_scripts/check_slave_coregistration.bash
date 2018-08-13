#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* check_slave_coregistration: Script takes each MLI image and runs dis2pwr    *"
    echo "*                             to enable checking of coregistration between    *"
    echo "*                             reference master and slave scenes.              *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [list_type]  slave list type (1 = slaves.list, 2 = add_slaves.list, *"
    echo "*                      default is 1)                                          *"
    echo "*         <start>      starting line of SLC (optional, default: 1)            *"
    echo "*         <nlines>     number of lines to display (optional, default: 4000)   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/05/2015, v1.0                            *"
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
    echo -e "Usage: check_slave_coregistration.bash [proc_file] [list_type] <start> <nlines>"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

if [ $# -eq 2 ]; then
    list_type=$2
else
    list_type=1
fi
if [ $# -eq 3 ]; then
    start=$3
else
    start=1
fi
if [ $# -eq 4 ]; then
    nlines=$4
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

cd $proj_dir/$track

if [ $list_type -eq 1 ]; then
    list=$slave_list
    echo " "
    echo "Checking coregistration of slaves with master scene..."
else
    list=$add_slave_list
    echo " "
    echo "Checking coregistration of additional slaves with master scene..."
fi

while read slave; do
    if [ ! -z $slave ]; then
	slave_file_names
	s1_slave_file_names
	r_dem_master_mli_width=`grep range_samples: $r_dem_master_mli_par | awk '{print $2}'`
	r_slave_mli_width=`grep range_samples: $r_slave_mli_par | awk '{print $2}'`
	dis2pwr $r_dem_master_mli $r_slave_mli $r_dem_master_mli_width $r_slave_mli_width $start $nlines - - - - 0
    fi
done < $list
echo " "
echo "Checked slave coregistration to reference SLC."
echo " "

# script end
####################