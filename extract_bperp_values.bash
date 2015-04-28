#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_bperp_values:  Extract the perpendicular baseline value for an      *"
    echo "*                        interferogram. Uses 'interp_centre_bperp.bash' to    *"
    echo "*                        extract the bperp value.                             *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*         [ifm_list]    list of interferograms                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/04/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: extract_bperp_values.bash [proc_file] [ifm_list]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

list=$2
proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $scene 1>&2

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

int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`
base_dir=$proj_dir/$track_dir/`grep base_dir= $proc_file | cut -d "=" -f 2`

mkdir -p $base_dir
cd $base_dir

results=$base_dir/$project"_"$sensor"_"$track"_"ifm_bperp_results.txt

if [ -e $results ]; then
    rm -f $results 
fi

echo "mas-slv unwrapped_ifm file_size bperp" > $results

while read file; do
    mas=`echo $file | awk 'BEGIN {FS=","} ; {print $1}'`
    slv=`echo $file | awk 'BEGIN {FS=","} ; {print $2}'`
    int_dir=$int_dir/$mas-$slv
    mas_slv_name=$mas-$slv"_"$polar"_"$ifm_looks"rlks"
    int_unw=$int_dir/$mas_slv_name.unw
    bperp=$int_dir/$mas_slv_name"_bperp.par"
    cd $int_dir
    echo $mas-$slv > temp1 # ifm pair
    echo $mas_slv_name.unw > temp2 # unw file name
    ls -ltrh $int_unw > temp3
    awk '{print $5}' temp3 > temp4 # unw file size
    interp_centre_bperp.bash $bperp > temp5 # bperp value
    paste temp1 temp2 temp4 temp5 >> $results 
    rm temp1 temp2 temp3 temp4 temp5
done < $list



