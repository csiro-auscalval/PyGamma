#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* check_slave_coregistration: Script takes each single-look complex (SLC)     *"
    echo "*                             and MLI image and runs dis2SLC to enable        *"
    echo "*                             checking of coregistration between reference    *"
    echo "*                             master and slave scenes.                        *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [list_type]  slave list type (1 = slaves.list, 2 = add_slaves.list, *"
    echo "*                      default is 1)                                          *"
    echo "*         <start>      starting line of SLC (optional, default: 1)            *"
    echo "*         <nlines>     number of lines to display (optional, default: 4000)   *"
    echo "*         <beam>       beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: check_slave_coregistration.bash [proc_file] [list_type] <start> <nlines> <beam>"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

if [ $# -eq 2 ]; then
    list_type=$2
else
    list_type=1
fi
if [ $# -eq 3 ]; then
    start=$3
else
    start=1
fi
if [ $# -eq 4 ]; then
    nlines=$4
else
    nlines=4000
fi

proc_file=$1
beam=$5

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
slc_looks=`grep SLC_multi_look= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
mas=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

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

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
scene_dir=$slc_dir/$scene

if [ $list_type -eq 1 ]; then
    list=$proj_dir/$track_dir/lists/`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
echo " "
echo "Checking coregistration of slaves with master scene..."
else
    list=$proj_dir/$track_dir/lists/`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`
echo " "
echo "Checking coregistration of additional slaves with master scene..."
fi

cd $proj_dir/$track_dir

#echo "   Checking full SLC images..."
#echo " "

#mas_dir=$slc_dir/$mas
#if [ -z $beam ]; then #no beam
#    mas_slc=$mas_dir/r$mas"_"$polar.slc
#else #beam exists
#    mas_slc=$mas_dir/r$mas"_"$polar"_"$beam.slc
#fi
#mas_slc_par=$mas_slc.par
#mas_slc_width=`grep range_samples: $mas_slc_par | awk '{print $2}'`

#while read slave; do
#    if [ ! -z $slave ]; then
#	slv=`echo $slave | awk '{print $1}'`
#	slv_dir=$slc_dir/$slv
#	slv_slc=$slv_dir/r$slv"_"$polar.slc
#	slv_slc_par=$slv_slc.par
#	slv_slc_width=`grep range_samples: $slv_slc_par | awk '{print $2}'`
#	format=`grep image_format: $slv_slc_par | awk '{print $2}'`    
#	if [ $format == SCOMPLEX ]; then
#	    fflag=1
#	else # format = FCOMPLEX
#            fflag=0
#	fi
#	dis2SLC $mas_slc $slv_slc $mas_slc_width $slv_slc_width $start $nlines - - 1 0.5 $fflag
#    fi
#done < $list

#echo " "
#echo "Checked full SLC images."

if [ $slc_looks -ne $ifm_looks ]; then
    echo "   Checking SLC MLI images..."
    echo " "
    mas_dir=$slc_dir/$mas
    if [ -z $beam ]; then #no beam
	mas_slc=$mas_dir/r$mas"_"$polar"_"$slc_looks"rlks.mli"
    else #beam exists
	mas_slc=$mas_dir/r$mas"_"$polar"_"$beam"_"$slc_looks"rlks.mli"
    fi
    mas_slc_par=$mas_slc.par
    mas_slc_width=`grep range_samples: $mas_slc_par | awk '{print $2}'`
    while read slave; do
	if [ ! -z $slave ]; then
	    slv=`echo $slave | awk '{print $1}'`
	    slv_dir=$slc_dir/$slv
	    slv_slc=$slv_dir/r$slv"_"$polar"_"$slc_looks"rlks.mli"
	    slv_slc_par=$slv_slc.par
	    slv_slc_width=`grep range_samples: $slv_slc_par | awk '{print $2}'`
	    dis2pwr $mas_slc $slv_slc $mas_slc_width $slv_slc_width $start $nlines - - - - 0
	fi
    done < $list
    echo " "
    echo "Checked SLC MLI images."
    echo "   Checking ifm MLI images..."
    echo  " "
    mas_dir=$slc_dir/$mas
    if [ -z $beam ]; then #no beam
	mas_slc=$mas_dir/r$mas"_"$polar"_"$ifm_looks"rlks.mli"
    else #beam exists
	mas_slc=$mas_dir/r$mas"_"$polar"_"$beam"_"$ifm_looks"rlks.mli"
    fi
    mas_slc_par=$mas_slc.par
    mas_slc_width=`grep range_samples: $mas_slc_par | awk '{print $2}'`
    while read slave; do
	if [ ! -z $slave ]; then
	    slv=`echo $slave | awk '{print $1}'`
	    slv_dir=$slc_dir/$slv
	    slv_slc=$slv_dir/r$slv"_"$polar"_"$ifm_looks"rlks.mli"
	    slv_slc_par=$slv_slc.par
	    slv_slc_width=`grep range_samples: $slv_slc_par | awk '{print $2}'`
	    dis2pwr $mas_slc $slv_slc $mas_slc_width $slv_slc_width $start $nlines - - - - 0
	fi
    done < $list
    echo " "
    echo "Checked ifm MLI images. Checking slave coregistration complete."
    echo " "
else #slc and ifm looks the same
    echo "   Checking SLC MLI images..."
    mas_dir=$slc_dir/$mas
    if [ -z $beam ]; then #no beam
	mas_slc=$mas_dir/r$mas"_"$polar"_"$slc_looks"rlks.mli"
    else #beam exists
	mas_slc=$mas_dir/r$mas"_"$polar"_"$beam"_"$slc_looks"rlks.mli"
    fi
    mas_slc_par=$mas_slc.par
    mas_slc_width=`grep range_samples: $mas_slc_par | awk '{print $2}'`
    while read slave; do
	if [ ! -z $slave ]; then
	    slv=`echo $slave | awk '{print $1}'`
	    slv_dir=$slc_dir/$slv
	    slv_slc=$slv_dir/r$slv"_"$polar"_"$slc_looks"rlks.mli"
	    slv_slc_par=$slv_slc.par
	    slv_slc_width=`grep range_samples: $slv_slc_par | awk '{print $2}'`
	    dis2pwr $mas_slc $slv_slc $mas_slc_width $slv_slc_width $start $nlines - - - - 0
	fi
    done < $list
    echo " "
    echo "Checked SLC MLI images."
    echo " "
    echo " "
    echo "SLC multi-looks and ifm multi-looks the same, checking slave coregistration complete."
    echo " "
fi
