#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_baseline_values:  Extract the perpendicular and temporal baseline   *"
    echo "*                           values for an interferogram.                      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]       name of GAMMA proc file (eg. gamma.proc)          *"
    echo "*                                                                             *"
    echo "* author: Matt Garthwaite @ GA       11/05/2015, v1.1                         *"
    echo "*         Sarah Lawrie @ GA          18/06/2015, v1.1                         *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*******************************************************************************"
    echo -e "Usage: extract_baseline_values.bash [proc_file]"
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
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir/$track_dir
proc_file=$proj_dir/$1
ifm_list=$proj_dir/$track_dir/lists/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $scene 1>&2
echo "" 1>&2
echo "Extract Baseline Values" 1>&2

## Insert scene details top of NCI .o file
echo "" 
echo ""
echo "PROCESSING_PROJECT: "$project $track_dir $scene
echo ""
echo "Extract Baseline Values" 

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

results=$base_dir/$project"_"$sensor"_"$track_dir"_"ifm_bperp_results.txt

if [ -e $results ]; then
    rm -f $results 
fi

echo "mas-slv unwrapped_ifm file_size bperp btemp" > $results

while read file; do
    mas=`echo $file | awk 'BEGIN {FS=","} ; {print $1}'`
    slv=`echo $file | awk 'BEGIN {FS=","} ; {print $2}'`
    dir=$int_dir/$mas-$slv
    mas_slv_name=$mas-$slv"_"$polar"_"$ifm_looks"rlks"
    int_unw=$dir/$mas_slv_name.unw

    ## calculate temporal baseline in days
    let btemp=(`date +%s -d $slv`-`date +%s -d $mas`)/86400

    ## find file size of unwrapped ifm    
    fsize=`ls -ltrh $int_unw | awk '{print $5}'`

    ## estimate the scene centre perpendicular baseline
    bperp=$dir/$mas_slv_name"_bperp.par"
    bpval=`interp_centre_bperp.bash $proc_file $bperp`

    echo $mas-$slv $mas_slv_name.unw $fsize $bpval $btemp
    echo $mas-$slv $mas_slv_name.unw $fsize $bpval $btemp >> $results
done < $ifm_list



