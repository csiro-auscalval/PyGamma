#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_S1_SLC: Script takes SLC format Sentinel-1 Interferometric Wide     *"
    echo "*                 Swath data and mosaics the three sub-swathes into a single  *"
    echo "*                 SLC.                                                        *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*                                                                             *"
    echo "* author: Matt Garthwaite @ GA       11/05/2015, v1.0                         *"
    echo "*******************************************************************************"
    echo -e "Usage: process_S1_SLC.bash [proc_file] [scene] [rlks] [alks]"
    }

if [ $# -lt 4 ]
then 
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" ]; then 
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    scene=$2
fi

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
#beam=`grep Beam= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
frame_list=`grep List_of_frames= $proc_file | cut -d "=" -f 2`
raw_dir_ga=`grep Raw_data_GA= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_data_MDSS= $proc_file | cut -d "=" -f 2`

slc_rlks=$3
slc_alks=$4

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$proj_dir/raw_data/$track_dir
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$raw_dir_ga
fi

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $scene $slc_rlks"rlks" $slc_alks"alks" 1>&2

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

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
scene_dir=$slc_dir/$scene

echo " "
echo "MLI range and azimuth looks: "$slc_rlks $slc_alks
echo " "

mkdir -p $slc_dir
cd $slc_dir
mkdir -p $scene
cd $scene_dir

raw_file_list=raw_file_list
rm -f $scene_dir/$raw_file_list 

## File names
slc_name=$scene"_"$polar
mli_name=$scene"_"$polar"_"$slc_rlks"rlks"
#para=$slc_name"_SLC_parameters.txt"
slc=$slc_name.slc
slc_par=$slc.par
slc1=$slc_name"_IW1.slc"
slc1_par=$slc1.par
tops_par1=$slc1.TOPS_par
slc2=$slc_name"_IW2.slc"
slc2_par=$slc2.par
tops_par2=$slc2.TOPS_par
slc3=$slc_name"_IW3.slc"
slc3_par=$slc3.par
tops_par3=$slc3.TOPS_par
mli=$mli_name.mli
mli_par=$mli.par
tiff=$mli_name.tif
ras_out=$mli_name.ras
#fbd2fbs_slc=$slc_name"_FBS.slc"
#fbd2fbs_par=p$slc_name"_FBS.slc.par"

## Set mode based on polarisation
#pol_list=$scene_dir/pol_list
#rm -f $pol_list

if [ ! -e $slc_dir/$scene/$slc ]; then
#    while read frame_num; do
#	if [ ! -z $frame_num ]; then
#	    frame=`echo $frame_num | awk '{print $1}'`
#	    if [ $platform == GA ]; then
#		ls $raw_dir/F$frame/date_dirs/$scene/IMG-HH* >& hh_temp
#		ls $raw_dir/F$frame/date_dirs/$scene/IMG-HV* >& hv_temp
#		temp="ls: cannot access"
#		temp1=`awk '{print $1" "$2" "$3}' hh_temp`
#		if [ "$temp1" == "$temp" ]; then
#		    :
#		else
#		    basename $raw_dir/F$frame/$scene/IMG-HH* >> $pol_list 
#		fi
#		temp2=`awk '{print $1" "$2" "$3}' hv_temp`
#		if [ "$temp2"  == "$temp" ]; then
#		    :
#		else
#		    basename $raw_dir/F$frame/$scene/IMG-HV* >> $pol_list
#		fi
#		rm -rf hh_temp hv_temp
#	    else
#		ls $raw_dir/F$frame/$scene/IMG-HH* >& hh_temp
#		ls $raw_dir/F$frame/$scene/IMG-HV* >& hv_temp
#		temp="ls: cannot access"
#		temp1=`awk '{print $1" "$2" "$3}' hh_temp`
#		if [ "$temp1" == "$temp" ]; then
#		    :
#		else
#		    basename $raw_dir/F$frame/$scene/IMG-HH* >> $pol_list 
#		fi
#		temp2=`awk '{print $1" "$2" "$3}' hv_temp`
#		if [ "$temp2"  == "$temp" ]; then
#		    :
#		else
#		    basename $raw_dir/F$frame/$scene/IMG-HV* >> $pol_list
#		fi
#		rm -rf hh_temp hv_temp
#	    fi
#	fi
#    done < $proj_dir/$track_dir/$frame_list
#
#    num_hv=`grep -co "HV" $pol_list`
#    if [ "$num_hv" -eq 0 -a "$polar" == HH ]; then 
#	mode=FBS
#    elif [ "$num_hv" -ge 1 -a "$polar" == HH ]; then 
#	mode=FBD
#    elif [ $polar == HV ]; then
#	mode=FBD
#    else
#	:
#    fi
#    echo "Mode:" $mode "  Polarisation:" $polar
#    rm -f $pol_list

rm -f slc_tab

    ## Produce SLC data files
    for swath in 1 2 3
    do
	echo " "
	echo "Processing SLC for sub-swath "$swath
	echo " "
	while read frame_num; do

	    if [ ! -z $frame_num ]; then
		frame=`echo $frame_num | awk '{print $1}'`
		#fr_slc_name=$scene"_"$polar"_F"$frame
		#fr_slc=$fr_slc_name.slc
		#fr_slc_par=$fr_slc.par
		if [ $platform == GA ]; then
		    annot=`ls $raw_dir/F$frame/date_dirs/$scene/annotation/s1a-iw$swath-slc*.xml`
    		    data=`ls $raw_dir/F$frame/date_dirs/$scene/measurement/s1a-iw$swath-slc*.tiff`
		    calib=`ls $raw_dir/F$frame/date_dirs/$scene/annotation/calibration/calibration-s1a-iw$swath-slc*.xml`
		    noise=`ls $raw_dir/F$frame/date_dirs/$scene/annotation/calibration/noise-s1a-iw$swath-slc*.xml`
		else
		    annot=`ls $raw_dir/F$frame/$scene/annotation/s1a-iw$swath-slc*.xml`
    		    data=`ls $raw_dir/F$frame/$scene/measurement/s1a-iw$swath-slc*.tiff`
		    calib=`ls $raw_dir/F$frame/$scene/annotation/calibration/calibration-s1a-iw$swath-slc*.xml`
		    noise=`ls $raw_dir/F$frame/$scene/annotation/calibration/noise-s1a-iw$swath-slc*.xml`
		fi
		bslc="slc$swath"
		bslc_par=${!bslc}.par
		btops="tops_par$swath"
		# Import S1 sub-swath SLC
		GM par_S1_SLC $data $annot $calib $noise $bslc_par ${!bslc} ${!btops}

		## Make quick-look image
		width=`grep range_samples: $bslc_par | awk '{print $2}'`
		lines=`grep azimuth_lines: $bslc_par | awk '{print $2}'`
		GM rasSLC ${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bslc}.ras

		echo ${!bslc} $bslc_par ${!btops} >> slc_tab

                ## Copy data file details to text file to check if concatenation of scenes along track is required
		#echo $fr_slc $fr_slc_par >> $raw_file_list
	    fi
	done < $proj_dir/$track_dir/$frame_list
    done

    GM SLC_mosaic_S1_TOPS slc_tab $slc $slc_par $slc_rlks $slc_alks

    width=`grep range_samples: $slc_par | awk '{print $2}'`
    lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
    GM rasSLC $slc $width 1 $lines 50 10 - - 1 0 0 $slc.ras

## Check if scene concatenation is required (i.e. a scene has more than one frame)
#lines=`awk 'END{print NR}' $raw_file_list`
#if [ $lines -eq 1 ]; then
#    ## rename files to enable further processing (remove reference to 'frame' in file names)
#    mv $fr_slc $slc
#    mv $fr_slc_par $slc_par
#    rm -f $raw_file_list
#else
#    ## Concatenate scenes into one output data file (works for 2 frames only)
#    awk 'NR==1 {print $1,$2}' $raw_file_list > slc_tab1
#    awk 'NR==2 {print $1,$2}' $raw_file_list > slc_tab2
#    # create temp directory for processing files under scene directory
#    mkdir -p temp
#    # create offset parameter file
#    GM SLC_cat_all slc_tab1 slc_tab2 $scene_dir/temp cat_slc.list 0
#    # measure initial range and azimuth offsets using orbit information
#    GM SLC_cat_all slc_tab1 slc_tab2 $scene_dir/temp cat_slc.list 1
#    # concatenate 
#    GM SLC_cat_all slc_tab1 slc_tab2 $scene_dir/temp cat_slc.list 4
#    # rename files and move files
#    rm -rf *.slc *.slc.par # remove frame slcs
#    cd temp
#    mv *.slc $slc
#    mv *.slc.par $slc_par
#    mv $slc $slc_par $scene_dir
#    mv *.off *.log $scene_dir
#    cd $scene_dir
#    rm -rf temp $raw_file_list slc_tab* cat_slc.list
#fi
   
else
    echo " "
    echo "Full SLC already created."
    echo " "
fi

## Multi-look SLC
GM multi_look $slc $slc_par $mli $mli_par $slc_rlks $slc_alks 0

## Create low-res preview tiff
#mli_width=`grep range_samples: $mli_par | awk '{print $2}'`
#GM data2tiff $mli $mli_width 2 $tiff

## Create low-res ras image (for location plot)
#GM raspwr $mli $mli_width 1 0 1 1 1 0.35 1 $ras_out 0 0

## corner coordinates given in SLC MSP parameter file
#grep map_coordinate_4 $msp_par | awk '{print $2, $3}' > slc_coords
#grep map_coordinate_2 $msp_par | awk '{print $2, $3}' >> slc_coords
#grep map_coordinate_1 $msp_par | awk '{print $2, $3}' >> slc_coords
#grep map_coordinate_3 $msp_par | awk '{print $2, $3}' >> slc_coords
#grep map_coordinate_5 $msp_par | awk '{print $2, $3}' >> slc_coords

## Make SLC location plot
#plot_SLC_loc.bash $proc_file $scene $msp_par $sensor $ras_out



# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
   cat error.log 1>&2
   rm temp_log
else
   rm temp_log
fi
