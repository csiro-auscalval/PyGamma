#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_RSAT2_SLC:  Script takes MDA Geotiff format SLC from RADARSAT-2     *"
    echo "*                     and produces sigma0 calibrated SLC and Multi-look       *"
    echo "*                     intensity (MLI) images in GAMMA format.                 *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       19/08/2016, v1.1                            *"
    echo "*            - add ability to concatenate 2 frames                            *"
    echo "*******************************************************************************"
    echo -e "Usage: process_RSAT2_SLC.bash [proc_file] [scene] [rlks] [alks]"
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
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
raw_dir_ga=`grep Raw_data_GA= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_data_MDSS= $proc_file | cut -d "=" -f 2`

slc_rlks=$3
slc_alks=$4

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$proj_dir/raw_data/$track_dir
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$raw_dir_ga
fi

frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $scene $slc_rlks"rlks" $slc_alks"alks" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir $scene $slc_rlks"rlks" $slc_alks"alks"
echo ""

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
slc=$slc_name.slc
slc_par=$slc.par
mli=$mli_name.mli
mli_par=$mli.par
tiff=$mli_name.tif
ras_out=$mli_name.ras

## Produce SLC data files
if [ ! -e $slc_dir/$scene/$slc ]; then
    while read frame_num; do
	if [ ! -z $frame_num ]; then
	    frame=`echo $frame_num | awk '{print $1}'`
	    fr_slc_name=$scene"_"$polar"_F"$frame
	    fr_mli_name=$scene"_"$polar"_F"$frame"_"$slc_rlks"rlks"
	    fr_slc=$fr_slc_name.slc
	    fr_slc_par=$fr_slc.par
	    fr_mli=$fr_mli_name.mli
	    fr_mli_par=$fr_mli.par

	    xml=$raw_dir/F$frame/$scene/RS2_OK*$scene*SLC/product.xml
	    lut=$raw_dir/F$frame/$scene/RS2_OK*$scene*SLC/lutSigma.xml
	    tif=$raw_dir/F$frame/$scene/RS2_OK*$scene*SLC/imagery_$polar.tif

            ## Read RADARSAT-2 data and produce sigma0 calibrated slc and parameter files in GAMMA format
            # Message below added 19/1/2015
	    echo "process_RSAT2_SLC.bash: bugfix required for correct polarisation. hardwired to 'H'"
	    GM par_RSAT2_SLC $xml $lut $tif H $fr_slc_par $fr_slc

            ## MG verified in Jan 2015 that images processed using lutSigma.xml in par_RSAT2_SLC alone are 
            ## identical to 3 d.p. in decibels to using lutBeta.xml and then using radcal_SLC to convert to sigma0
            #GM radcal_SLC $slc $slc_par sigma0.slc sigma0.slc.par 1 - 0 0 1 0 0
            #mv -f sigma0.slc $slc
            #mv -f sigma0.slc.par $slc_par

            # Make quick-look image
	    GM multi_look $fr_slc $fr_slc_par $fr_mli $fr_mli_par $slc_rlks $slc_alks 0
	    width=`grep range_samples: $fr_mli_par | awk '{print $2}'`
	    lines=`grep azimuth_lines: $fr_mli_par | awk '{print $2}'`
	    GM raspwr $fr_mli $width 1 $lines 10 10 1 0.35 1 $fr_mli.bmp 0

            # Copy data file details to text file to check if concatenation of scenes along track is required
	    echo $fr_slc $fr_slc_par >> $raw_file_list
	fi
    done < $frame_list

    ## Check if scene concatenation is required (i.e. a scene has more than one frame)
    lines=`awk 'END{print NR}' $raw_file_list`
    if [ $lines -eq 1 ]; then
        # rename files to enable further processing (remove reference to 'frame' in file names)
	mv $fr_slc $slc
	mv $fr_slc_par $slc_par
	rm -f $raw_file_list
    # concatenate 2 frames
    else 
	slc1=`awk 'NR==1 {print $1}' $raw_file_list`
	slc1_par=`awk 'NR==1 {print $2}' $raw_file_list`
	echo $slc1 $slc1_par > tab1
	slc2=`awk 'NR==2 {print $1}' $raw_file_list`
	slc2_par=`awk 'NR==2 {print $2}' $raw_file_list`
	echo $slc2 $slc2_par > tab2
	slc1_name=`echo $slc1 | awk -F . '{print $1}'`
	slc2_name=`echo $slc2 | awk -F . '{print $1}'`
	cat_off=$slc1_name-$slc2_name"_cat.off"
	offs=$slc1_name-$slc2_name.offs
	snr=$slc1_name-$slc2_name.snr
	coffs=$slc1_name-$slc2_name.coffs
	mkdir cat_slc
        # create offset parameter files for estimation of the offsets
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 0
        # measure initial range and azimuth offsets using orbit information
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 1
        # estimate range and azimuth offset models using correlation of image intensities
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 3
        # concatenate SLC images using offset polynomials determined above
	GM SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 4
        # clean up files
	cd cat_slc
	cat_slc=*.slc
	cat_slc_par=*.slc.par
	mv $cat_slc $slc
	mv $cat_slc_par $slc_par
	mv * ../
	cd ../
	rm -rf $raw_file_list cat_slc cat_slc_tab tab1 tab2 SLC_cat_all*.log create_offset.in 
    fi
else
    echo " "
    echo "Full SLC already created."
    echo " "
fi

## Multi-look SLC to SLC multi-look value
GM multi_look $slc $slc_par $mli $mli_par $slc_rlks $slc_alks 0

# Make quick-look image
width=`grep range_samples: $mli_par | awk '{print $2}'`
lines=`grep azimuth_lines: $mli_par | awk '{print $2}'`
GM raspwr $mli $width 1 $lines 10 10 1 0.35 1 $mli.bmp 0


## Create low-res preview tiff
#mli_width=`grep range_samples: $mli_par | awk '{print $2}'`
#GM data2tiff $mli $mli_width 2 $tiff

## Create low-res ras image (for location plot)
#GM raspwr $mli $mli_width 1 0 1 1 1 0.35 1 $ras_out 0 0

## corner coordinates given in SLC MSP parameter file     ####### MSP FILE NOT PRODUCED FOR RSAT2 ######
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