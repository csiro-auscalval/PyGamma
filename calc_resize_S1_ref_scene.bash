#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_resize_S1_ref_scene: Automatic calculation of Sentinel-1 reference     *"
    echo "*                           scene for resizing SLC stack. The scene selected  *"
    echo "*                           is the smallest one in the stack.                 *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
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
    echo -e "Usage: calc_resize_S1_ref_scene.bash [proc_file]"
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

# Print processing summary to .o & .e files
PBS_processing_details $project $track 

######################################################################

# File names
s1_resize

cd $proj_dir/$track

if [ $s1_resize_ref == "auto" ]; then # ref scene not calculated
    echo "Scene Min_Bursts Swath Start_Time" > $min_bursts

    # determine total bursts and start time
    while read scene; do
	slc_file_names
	cd $scene_dir
	s1_resize
	sed -n '/total/p' $burst_file | awk '{print $3}' > temp1
	sed -n '/Swath:/p' $burst_file | awk '{print $2}' > temp2
	sed -n '/start/p' $burst_file | awk '{print $3}' > temp3
	paste temp1 temp2 temp3 > temp4
	min=`awk 'BEGIN{a=1000}{if ($1<0+a) a=$1} END{print a}' temp4`
       # select all the swaths that have min number of bursts, and then find the swath that starts first
	sed -n "/^$min/p" temp4 > temp5
	sort -k3 -n temp5 > temp6
	burst=`awk 'NR==1 {print}' temp6`
	echo $scene $burst >> $min_bursts
	rm -rf temp1 temp2 temp3 temp4 temp5 temp6
	cd $slc_dir
    done < $scene_list

    # find scene with min number of bursts
    cd $list_dir
    min=`awk 'BEGIN{a=1000}{if ($2<0+a) a=$2} END{print a}' $min_bursts`

    # if more than one scene has the same min number of bursts, select the one that starts first
    sed -n "/$min/p" $min_bursts > temp1
    sort -k4 -n temp1 > temp2
    ref_scene=`awk 'NR==1 {print $1}' temp2`

    # update proc file with ref scene 
    cp $proc_file temp1
    sed -i "s/S1_RESIZE_REF_SLC=auto/S1_RESIZE_REF_SLC=$ref_scene/g" temp1
    cp $proc_file $pre_proc_dir/$track".proc_pre_resize"
    mv temp1 $proc_file
    rm -rf temp1 temp2
    echo "SENTINEL-1 RESIZING REFERENCE SCENE" > $resize_ref_results
    echo "" >> $resize_ref_results
    echo $ref_scene >> $resize_ref_results

else
    echo "Sentinel-1 resizing reference scene already identified in *.proc file."
fi
# script end 
####################


