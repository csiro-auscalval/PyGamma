#!/bin/bash
display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_subset_burst_list: Creates the list for a given start/end burst      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  proc file TxxxX.proc                                   *"
    echo "*         [b_start]    start burst number                                     *"
    echo "*         [b_end]      end burst number                                       *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA       23/08/2018, v1.0                         *"
    echo "*******************************************************************************"
    echo -e "Usage: create_subset_burst_list.bash [proc_file] [b_start] [b_end]"
    }

if [ $# -lt 3 ]
then
    display_usage
    exit 1
fi

# Parameters
proc_file=$1
b_start=$2
b_end=$3

# Sentinel-1 IW mode has three swaths: IW1, IW2, IW3
sw_start=1
sw_end=3


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

######################################################################


cd $list_dir

# read the number of bursts per file from min_bursts
burst_max=999
line=0
while read list; do
    ((line++))
    if [ $line -gt 1 ]; then # first line is a headerline
        burst_temp=`echo $list | awk '{print $2}'`
        if [ $burst_temp -lt $burst_max ]; then
            burst_max=$burst_temp
        fi
    fi
done < min_bursts

echo ""
# check that input parameters are reasonable
if [ $b_start -lt 1 ]; then
    echo "Start burst should be >= 1."
    display_usage
    echo ""
    exit 1
fi
if [ $b_start -gt $b_end ]; then
    echo "End burst should be greater than start burst."
    display_usage
    echo ""
    exit 1
fi
if [ $b_end -gt $burst_max ]; then
    echo "End burst exceeds maximum burst number of "$burst_max"."
    display_usage
    echo ""
    exit 1
fi

# create output file subset_burst.list
subset_b_list="subset_burst.list"
if [ -e $subset_b_list ]; then
   rm -f $subset_b_list
fi
while read list; do
    date=`echo $list | awk '{print $1}'`
    for swath in `seq $sw_start $sw_end`; do
        echo $date $swath $b_start $b_end >> $subset_b_list
    done
done < scenes.list
echo "File subset_burst.list was created in the lists directory."
echo ""

# script end
####################
