#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ERS_SLC:  Script takes Level 1.0 (raw) ERS fine beam data and       *"
    echo "*                   produces sigma0 calibrated SLC and and Multi-look         *"
    echo "*                   intensity (MLI) images in GAMMA format.                   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: process_ERS_SLC.bash [proc_file] [scene] [rlks] [alks]"
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
ers_sensor=`grep ERS_sensor= $proc_file | cut -d "=" -f 2`
#frame_list=`grep List_of_frames= $proc_file | cut -d "=" -f 2`
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
raw=$slc_name.raw
slc=$slc_name.slc
slc_par=$slc.par
mli=$mli_name.mli
mli_par=$mli.par
tiff=$mli_name.tif
ras_out=$mli_name.ras

if [ ! -e $slc_dir/$scene/$slc ]; then
    ## Make dummy file to accept default values for the parameter file
    echo "$ers_sensor $scene" > returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns
    echo "" >> returns

    ## Set up sensor parameters
    if [ $ers_sensor == ERS1 ]; then
	sensor_par=ERS1_ESA_sensor.par
	cp -f $MSP_HOME/sensors/ERS1_ESA.par $sensor_par
	cp -f $MSP_HOME/sensors/ERS1_antenna.gain .
        ## calibration constant from MSP/sensors/sensor_cal_MSP.dat file: 
	if [ $scene -le "19961231" ]; then # ERS1 19910717-19961231 = -10.3
	    cal_const=-10.3
	else # ERS1 19970101-20000310 = -12.5
	    cal_const=-12.5
	fi
        ## set directory of DELFT orbits
	orb_dir=/g/data1/dg9/SAR_ORBITS/ERS_ODR_UPDATED/ERS1
    elif [ $ers_sensor == ERS2 ]; then
	sensor_par=ERS2_ESA_sensor.par
	cp -f $MSP_HOME/sensors/ERS2_ESA.par $sensor_par
	cp -f $MSP_HOME/sensors/ERS2_antenna.gain .
        ## calibration constant from MSP/sensors/sensor_cal_MSP.dat file: ERS2 = -2.8
	cal_const=-2.8
        ## set directory of DELFT orbits
	orb_dir=/g/data1/dg9/SAR_ORBITS/ERS_ODR_UPDATED/ERS2
    else
	echo "ERROR: Must be ERS1 or ERS2"
	exit 1
    fi

    ## Produce raw data files
    LED=`ls $raw_dir/date_dirs/scene01/lea_01.001`
    IMG=`ls $raw_dir/date_sirs/scene01/dat_01.001`

    ## Generate the MSP processing parameter file
    if [ $scene -le "19971231" ]; then # CEOS leader format is different before and after 1998
	format=0 # before 1998
    else
	format=1 # after 1998
    fi
    GM ERS_proc_ACRES $LED $msp_par $format < returns

    ## Condition the raw data and produce raw file in GAMMA format; check for missing lines
    GM ERS_fix ACRES $sensor_par $msp_par 1 $IMG $raw

    ## Update orbital state vectors in MSP processing parameter file
    ## Note that Delft orbits are believed to be more precise than D-PAF orbits (PRC files). See Scharoo and Visser and Delft Orbits website
    ## Four 10-second state vectors should cover one 100km long ERS frame. More are required at either end of the scene. Providing more than necessary cannot hurt.
    GM DELFT_proc2 $msp_par $orb_dir 21 10

    ## Determine the Doppler Ambiguity
    ## This is required for southern hemisphere data due to error in ERS pointing algorithm that introduces an ambiguity outside of the +/-(PRF/2) baseband
    GM dop_ambig $sensor_par $msp_par $raw 2 - $slc_name.mlbf
    ## Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
    #GM dop_mlcc $sensor_par $msp_par $raw $name.mlcc

    #plot_mlcc.bash $slc_name.mlcc
    plot_mlbf.bash $slc_name.mlbf

    ## Determine the fractional Doppler centroid using the azimuth spectrum
    GM azsp_IQ $sensor_par $msp_par $raw $slc_name.azsp

    plot_azsp.bash $slc_name.azsp

    ## Estimate the doppler centroid across the swath
    ## Should be negligible (near constant) for ERS since yaw steering was employed to maintain the doppler centroid within +/-(PRF/2) 
    GM doppler $sensor_par $msp_par $raw $slc_name.dop

    plot_dop.bash $slc_name.dop

    ## Estimate the range power spectrum
    ## Look for potential radio frequency interference (RFI) to the SAR signal
    GM rspec_IQ $sensor_par $msp_par $raw $slc_name.rspec

    ## Check range spectrum for spikes indicating RFI. If they exist can be suppresed during range compression 'pre_rc'
    plot_rspec.bash $slc_name.rspec $scene $raw_dir $msp_par

    ## Range compression
    ## second to last parameter is for RFI suppression.
    GM pre_rc $sensor_par $msp_par $raw $slc_name.rc - - - - - - - - 0 -

    ## REMOVE RAW IMAGE FILE HERE
    rm -f $raw

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
    GM par_MSP $sensor_par $msp_par $slc_par 0

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
