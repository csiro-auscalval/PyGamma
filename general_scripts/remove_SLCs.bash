#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* remove_SLCs: Removes scene/s which have SLCs that don't work from SLC     *"
    echo "*                directory and from scenes.list, slaves.list and ifms.list.   *"
    echo "*                                                                             *"
    echo "*                Requires a 'remove_scenes.list' file to be created in the    *"                                     
    echo "*                lists directory. This lists the dates to remove.             *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       26/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       20/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
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
    echo -e "Usage: remove_SLCs.bash [proc_file]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
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


cd $list_dir

# Remove SLCs from scene list
cp $scene_list pre_remove_SLCs_scenes.list
grep -Fvx -f $remove_slc_list $scene_list > temp1
mv temp1 $scene_list
rm -f temp1

# Remove scenes from slaves list
if [ -e $slave_list ]; then
    cp $slave_list pre_remove_SLCs_slaves.list
    grep -Fvx -f $remove_slc_list $slave_list > temp2
    mv temp2 $slave_list
    rm -f temp2
fi

# Remove scenes from ifgs list
if [ -e $ifg_list ]; then
    cp $ifg_list pre_remove_SLCs_ifgs.list
    while read rm_scene; do
	while read list; do
	    master=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slave=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifg=$master,$slave
	    if [ "$master" = "$rm_scene" ] || [ "$slave" = "$rm_scene" ]; then
		echo $ifg >> temp3
	    else
		:
	    fi
	done < $ifg_list
    done < $remove_slc_list
    grep -Fvx -f temp3 $ifg_list > temp4
    mv temp4 $ifg_list
    rm -f temp3 temp4
fi


# Remove scenes from SLC directory
cd $slc_dir

while read rm_scene; do
    rm -rf $rm_scene
done < $remove_slc_list


# script end 
####################