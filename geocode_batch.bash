#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* geocode_batch:  Scripts runs geocode.bash as a batch processing using a     *"
    echo "*                 a list of scenes.                                           *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]    name of GAMMA proc file (eg. gamma.proc)             *"
    echo "*         [list]         list of file names                                   *"
    echo "*         [type]         file type (eg. slc/int/cc)                           *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: geocode_batch.bash [proc_file] [list] [type]"
    }

if [ $# -lt 3 ]
then 
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" ]; then 
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
fi

proc_file=$1
list=$2
type=$3

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir/$int_dir/  ### fix directory to be interferograrm dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $scene 1>&2
echo "" 1>&2
echo "Batch Geocoding" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING_SCENE: "$project $track_dir $scene
echo ""
echo "Batch Geocoding"

## Copy output of Gamma programs to log files
GM()
{
    echo $* | tee -a command.log
    echo
    $* >> output.log 2> temp_log
    cat temp_log >> error.log
    #cat output.log (option to add output results to NCI .o file if required)
}

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

file_name=`echo $file | awk -F. '{print $1}'`
file_ext=`echo $file |awk -F . '{if (NF>1) {print $NF}}'` 
geocode_out=$file_name"_utm."$file_ext
geotif=$geocode_out.tif

while read file; do

    if [ $type == slc ]; then
	dir=$slc_dir
    elif [ $type == int -o $type == cc ]; then
	dir=$int_dir
    fi
    
    pair=`echo $file | sed 's/,/-/g'`
    #prefix=`echo $scene | awk '{print $1}'`
    file=`echo $dir/$date/{$prefix}*.$type | awk '{print $1}'`
    #echo $file
    geocode.bash $proc_file $file -
    #cp -f $dir/$date/*.slc.tif $proj_dir/geotiff/.
done < $list

