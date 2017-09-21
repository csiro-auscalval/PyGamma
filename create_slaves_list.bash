#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_slaves_list: Creates a list of slave SLCs based on the SLC scene     *"
    echo "*                     list and master scene date.                             *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [type]       list type to create (eg. 1=slaves.list or              *"
    echo "*                      2=add_slaves.list)                                     *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       29/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*******************************************************************************"
    echo -e "Usage: create_slaves_list.bash [proc_file] [type]"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
type=$2

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

scene_list=`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
slave_list=`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
add_scene_list=`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
add_slave_list=`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`


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

cd $proj_dir/$track_dir/lists

if [ $type -eq 2 ]; then
    cp $slave_list $proj_dir/$track_dir/lists/org_slaves.list
    echo "Additional Slaves List File Creation" 1>&2
    cp $add_scene_list $add_slave_list
else
    :
fi

echo "Slaves List File Creation" 1>&2
## Create list of slave SLCs
sed "/$master/d" $scene_list > $slave_list





# script end 
####################