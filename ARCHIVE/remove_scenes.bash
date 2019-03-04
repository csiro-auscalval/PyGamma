#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* remove_scenes: Removes scene/s which have SLCs that don't work from SLC     *"
    echo " *               directory and from scenes.list, slaves.list and ifms.list.   *"
    echo "*                                                                             *"
    echo "*                Requires a 'remove_scenes.list' file to be created in the    *"                                     
    echo "*                track directory. This lists the dates to remove.             *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       26/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       20/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*******************************************************************************"
    echo -e "Usage: remove_scenes.bash [proc_file]"
    }

if [ $# -lt 1 ]
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
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
remove_list=$proj_dir/$track_dir/lists/`grep List_of_remove_scenes= $proc_file | cut -d "=" -f 2`
scene_list=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
slave_list=$proj_dir/$track_dir/lists/`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
ifm_list=$proj_dir/$track_dir/lists/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`
add_scene_list=$proj_dir/$track_dir/lists/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
add_slave_list=$proj_dir/$track_dir/lists/`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`
add_ifm_list=$proj_dir/$track_dir/lists/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`


## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2
echo "" 1>&2
echo "Remove Scenes" 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING_PROJECT: "$project $track_dir
echo "" 
echo "Remove Scenes"
echo "" 

cd $proj_dir/$track_dir/lists
cp $scene_list org_scenes.list
cp $slave_list org_slaves.list
if [ -f all_ifms.list ]; then # for NCI processing
    cp all_ifms.list org_all_ifms.list
    rm -rf ifm_files.list ifms.list_*
    mv all_ifms.list ifms.list
else # for GA processing
    cp $ifm_list org_ifms.list
fi

## Remove scenes from scenes.list
grep -Fvx -f $remove_list $scene_list > temp1
mv temp1 $scene_list

## Remove scenes from slave.list
grep -Fvx -f $remove_list $slave_list > temp2
mv temp2 $slave_list

## Remove scenes from ifms.list
while read rm_scene; do
    while read list; do
	mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	ifm=$mas,$slv
	if [ "$mas" = "$rm_scene" ] || [ "$slv" = "$rm_scene" ]; then
	    echo $ifm >> temp3
	else
	    :
	fi
    done < $ifm_list
done < $remove_list
grep -Fvx -f temp3 $ifm_list > temp4
mv temp4 $ifm_list

rm -rf temp*

## Remove scenes from SLC directory
cd $slc_dir
while read rm_scene; do
    rm -rf $rm_scene
done < $remove_list


# script end 
####################