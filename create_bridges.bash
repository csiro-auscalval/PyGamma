#!/bin/bash


##### DRAFT SCRIPT, NOT TESTED YET #####

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_bridges:  View unwrapped ifg with wrapped ifg and unwrapping flag    *"
    echo "*                  file to determine if any bridges need to be created (for   *"
    echo "*                  branch-cut unwrapping method only).                        *"
    echo "*                                                                             *"
    echo "*                  NOTE:                                                      *"
    echo "*                  Will automatically open the bridges text file for editing  *"
    echo "*                  Run script from individual interferogram directory         *"
    echo "*                                                                             *"
    echo "* input:  [flag_file]  phase unwrapping flag file (*_filt_cc.flag)            *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       07/01/2016, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: create_bridges.bash [flag_file]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

int_dir=pwd
cd $int_dir

flag_file=`echo $1 | cut -d'.' -f1`
mas_slv=`echo $flag_file | awk -F _ '{print $1}'`
polar=`echo $flag_file | awk -F _ '{print $2}'`
ifm_rlks=`echo $flag_file | awk -F _ '{print $3}'`
mas_slv_name=$mas_slv"_"$polar"_"$ifm_rlks

# files 
int_unw=$int_dir/$mas_slv_name.unw
int_filt=$int_dir/$mas_slv_name"_filt.int"
flag_ras=$int_dir/$mas_slv_name"_filt_cc_flag.ras"

# file width
dem_dir= ../DEM
diff_dem=$dem_dir/"diff_"*$polar*$ifm_rlks.par
int_width=`grep range_samp_1 $diff_dem | awk '{print $2}'`

# bridge file
bridge=$int_dir/$mas_slv_name.bridges


# view flag file and images
rastree $flag_file $int_unw $int_filt $int_width - - - $flag_ras

# open bridges file for editing
if [ ! -f $bridge ]; then
    echo "col_unw " > temp1
    echo "row_unw " > temp2
    echo "col_wrp " > temp3
    echo "row_wrp " > temp4
    echo "phs_offset" > temp5
    paste temp1 temp2 temp3 temp4 temp5 > $bridge
    rm -f temp1 temp2 temp3 temp4 temp5
    emacs $bridge
else
    emacs $bridge
fi