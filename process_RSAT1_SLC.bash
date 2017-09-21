#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_RSAT1_SLC:  Script takes Level 1.0 (raw) RADARSAT-1 image mode data *"
    echo "*                     and produces sigma0 calibrated SLC.                     *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: process_RSAT1_SLC.bash [proc_file] [scene] [rlks] [alks]"
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
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$raw_dir_ga
fi

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $scene $slc_rlks"rlks" $slc_alks"alks" 1>&2

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


## File names
slc_name=$scene"_"$polar
mli_name=$scene"_"$polar"_"$slc_rlks"rlks"
msp_par=p$slc_name.slc.par
para=$slc_name"_SLC_parameters.txt"
raw=$slc_name.raw
leader=$slc_name.ldr
slc=$slc_name.slc
slc_par=$slc.par
mli=$mli_name.mli
mli_par=$mli.par
sensor_par=RSAT.par
tiff=$mli_name.tif
ras_out=$mli_name.ras

IMG=`ls $raw_dir/date_dirs/$scene/scene01/dat_01.001`
LED=`ls $raw_dir/date_dirs/$scene/scene01/lea_01.001`

## Determine beam mode from metadata file for antenna file
xml_grep 'SUPPLEMENTARYINFORMATION' $raw_dir/date_dirs/$scene/metadata.xml --text_only > temp1
awk -F"BEAM_MODE=" '{print $2}' temp1 > temp2
beam=`awk '{print substr($1,1,2)}' temp2`

cp -f $MSP_HOME/sensors/RSAT_{$beam}_antenna.gain .

## Make dummy file to accept default values for the parameter file
returns=$scene_dir/returns
echo "" > $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns
echo "" >> $returns

if [ ! -e $slc_dir/$scene/$slc ]; then
    ## Copy raw and leader file data and rename it to reflect .raw and .ldr files
    cp $IMG $raw
    cp $LED $leader

    ## Create MSP processing parameter file and condition data
    GM RSAT_raw $leader $sensor_par $msp_par $raw $slc_name.fix < $returns

    ## Determine the Doppler Ambiguity
    GM dop_ambig $sensor_par $msp_par $slc_name.fix 2 - $slc_name.mlbf
    ## Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
    #GM dop_mlcc $sensor_par $msp_par $slc_name.fix $slc_name.mlcc

    #plot_mlcc.bash $slc_name.mlcc
    #plot_mlbf.bash $slc_name.mlbf

    ## Estimate the doppler centroid across the swath
    GM doppler $sensor_par $msp_par $slc_name.fix $slc_name.dop

    plot_dop.bash $slc_name.dop

    ## Estimate the range power spectrum
    ## Look for potential radio frequency interference (RFI) to the SAR signal
    GM rspec_IQ $sensor_par $msp_par $slc_name.fix $slc_name.rspec

    ## Check range spectrum for spikes indicating RFI. If they exist can be suppresed during range compression 'pre_rc'
    plot_rspec.bash $slc_name.rspec

    ## Range compression
    GM pre_rc_RSAT $sensor_par $msp_par $slc_name.fix $slc_name.rc 

    ## REMOVE RAW IMAGE FILE HERE
    rm -f $raw $slc_name.fix

    ## Autofocus estimation and Azimuth compression (af replaces autof)
    ## run az_proc and af twice, DO NOT run af mutliple times before reprocessing image
    ## default SNR threshold is 10
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 4096 0 $cal_const 0
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af
    GM az_proc $sensor_par $msp_par $slc_name.rc $slc 4096 0 $cal_const 0
    GM af $sensor_par $msp_par $slc 1024 4096 - - 10 1 0 0 $slc_name.af

    ## REMOVE RC FILE HERE
    rm -f $slc_name.rc

    ## Generate ISP SLC parameter file from MSP SLC parameter file (for full SLC)
    par_MSP $sensor_par $msp_par $slc_par 0
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
