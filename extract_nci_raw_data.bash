#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_nci_raw_data: Script extracts raw data files (SAR and DEM) from the *"
    echo "*                       MDSS and puts them into the 'raw_data' directory for  *"
    echo "*                       processing with GAMMA.                                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       23/06/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: extract_nci_raw_data.bash [proc_file]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
frame_list=`grep List_of_frames= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_location_MDSS= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project 1>&2

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

## Get list of files in raw data directory on MDSS and copy raw data
raw_dir=$proj_dir/raw_data
cd $proj_dir/$track_dir
if [ -e $proj_dir/$track_dir/$frame_list ]; then # if frames exist
   while read frame; do
       if [ ! -z $frame ]; then # skips any empty lines
	   mdss ls $raw_dir_mdss/FR_$frame < /dev/null > $raw_dir/$track_dir/FR_$frame/tar.list # /dev/null allows mdss command to work properly in loop
	   echo >> $raw_dir/$track_dir/FR_$frame/tar.list # adds carriage return to last line of file (required for loop to work)
	   cd $raw_dir/$track_dir/FR_$frame
	   while read tar; do 
	       if [ ! -z $tar ]; then # skips any empty lines
		   mdss get $raw_dir_mdss/FR_$frame/$tar < /dev/null $raw_dir/$track_dir/FR_$frame # /dev/null allows mdss command to work properly in loop
		   tar xvzf $tar
		   rm -rf $tar
	       fi
	   done < $raw_dir/$track_dir/FR_$frame/tar.list        
	   rm -f $raw_dir/$track_dir/FR_$frame/tar.list
	   ls -d 1* > list
	   ls -d 2* >> list
	   sort -n list > scenes.list
	   echo >> scenes.list  # adds carriage return to last line of file (required for loop to work)
	   rm -rf list
	   mv scenes.list $proj_dir/$track_dir
        fi
    done < $proj_dir/$track_dir/$frame_list
else # no frames exist
    mdss ls $raw_dir_mdss < /dev/null > $raw_dir/$track_dir/tar.list # /dev/null allows mdss command to work properly in loop
    echo >> $raw_dir/$track_dir/tar.list # adds carriage return to last line of file (required for loop to work)
    while read tar; do
	if [ ! -z $tar ]; then # skips any empty lines
	    mdss get $raw_dir_mdss/$tar < /dev/null $raw_dir/$track_dir # /dev/null allows mdss command to work properly in loop
	    tar xvzf $tar
	    rm -rf $tar
	fi
    done < $raw_dir/$track_dir/tar.list
fi


# script end 
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2
rm temp_log
