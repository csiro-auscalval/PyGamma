#!/bin/bash

### Script doesn't include scene concatenation

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
    echo "* author: Sarah Lawrie @ GA       20/04/2015, v1.0                            *"
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
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$raw_dir_ga
fi

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $scene 1>&2

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

## File names
slc_name=$scene"_"$polar
mli_name=$scene"_"$polar"_"$slc_rlks"rlks"
slc=$slc_name.slc
slc_par=$slc.par
mli=$mli_name.mli
mli_par=$mli.par
tiff=$mli_name.tif
ras_out=$mli_name.ras

xml=`ls $raw_dir/date/dirs/$scene/RS2_OK*$scene*SLC/product.xml`
lut=`ls $raw_dir/date_dirs/$scene/RS2_OK*$scene*SLC/lutSigma.xml`
#lut=`ls $raw_dir/date_dirs/$scene/RS2_OK*$scene*SLC/lutBeta.xml`
tif=`ls $raw_dir/date_dirs/$scene/RS2_OK*$scene*SLC/imagery*.tif`

if [ ! -e $slc_dir/$scene/$slc ]; then
    ## Read RADARSAT-2 data and produce sigma0 calibrated slc and parameter files in GAMMA format
    # Message below added 19/1/2015
    echo "process_RSAT2_SLC.bash: bugfix required for correct polarisation. hardwired to 'H'"
    GM par_RSAT2_SLC $xml $lut $tif H $slc_par $slc

    ## MG verified in Jan 2015 that images processed using lutSigma.xml in par_RSAT2_SLC alone are 
    ## identical to 3 d.p. in decibels to using lutBeta.xml and then using radcal_SLC to convert to sigma0
    #GM radcal_SLC $slc $slc_par sigma0.slc sigma0.slc.par 1 - 0 0 1 0 0

    #mv -f sigma0.slc $slc
    #mv -f sigma0.slc.par $slc_par
else
    echo " "
    echo "Full SLC already created."
    echo " "
fi

## Multi-look SLC to SLC multi-look value
GM multi_look $slc $slc_par $slc_mli $slc_mli_par $slc_rlks $slc_alks 0

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