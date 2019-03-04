#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ASAR_SLC:  Script takes Level 1.0 (raw) ASAR fine beam data and     *"
    echo "*                    produces sigma0 calibrated SLC.                          *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "* author: Thomas Fuhrmann  @ GA   21/10/2016, v1.1                            *"
    echo "*         - added $scene as paramater to plot_rspec.bash to enable the func.  *"
    echo "*         -  deleted all params for pre_rc (default paraemters are used)      *"
    echo "*******************************************************************************"
    echo -e "Usage: process_ASAR_SLC.bash [proc_file] [scene] [rlks] [alks]"
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
echo "PROCESSING_PROJECT: "$project"_"$track_dir"_"$scene $slc_rlks"rlks" $slc_alks"alks" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir $scene $slc_rlks"rlks" $slc_alks"alks" $beam
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
raw_dir=$proj_dir/raw_data/$track_dir

mkdir -p $slc_dir
cd $slc_dir
mkdir -p $scene
cd $scene_dir

IMG=`ls $raw_dir/*$scene*.N1`

## extract header information from raw file
head -c 3000 $IMG > $scene"_raw_header.txt"
swath=`grep SWATH= $scene"_raw_header.txt" | cut -d "=" -f 2 | sed 's/"//' | sed 's/"//'`

ant=ASAR_$swath"_"$polar"_antenna.gain"
sensor_par=ASAR_$swath"_sensor.par"

if [ $platform == NCI ]; then
    XCA_dir=/g/data1/dg9/SAR_ORBITS/ENVISAT/XCA
    INS_dir=/g/data1/dg9/SAR_ORBITS/ENVISAT/INS
    orb_dir=/g/data1/dg9/SAR_ORBITS/ODR/ENVISAT # directory for DELFT orbits
else
    XCA_dir=/nas/gemd/insar/SAR_ORBITS/ENVISAT/XCA
    INS_dir=/nas/gemd/insar/SAR_ORBITS/ENVISAT/INS
    orb_dir=/nas/gemd/insar/SAR_ORBITS/ODR/ENVISAT # directory for DELFT orbits
fi

## ASAR IS2 VV cal constant from MSP/sensors/sensor_cal_MSP.dat file = -30.4, all other modes are '-'
if [ $swath == IS2 ]; then
    cal_const=-30.4
else
    cal_const=-
fi

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

##generate antenna gain parameter file from ASAR XCA file
year=`echo $scene | awk '{print substr($1,1,2)}' | sed s/0/\ /`
xcafind=0
cd $XCA_dir
ls ASA_XCA_* > xca.list
while read xca; do
  vec_start=`echo $xca | awk '{print substr($1,31,8)'}`
  vec_end=`echo $xca | awk '{print substr($1,47,8)'}`
  if [ $scene -gt $vec_start -a $scene -lt $vec_end ]; then
    xcafile=$XCA_dir/$xca
    xcafind=1
    break # exit loop if parameters met
  fi
done < xca.list
rm -rf xca.list
cd $scene_dir
if [ $xcafind -eq 1 ]; then
  GM ASAR_XCA $xcafile $ant $swath $polar
else
  echo "ERROR: Can not find proper ASA_XCA_* file!"
  exit 1
fi

## Find appropriate ASAR instrument file
insfind=0
cd $INS_dir
ls ASA_INS_* > ins.list
while read ins; do
  vec_start=`echo $ins | awk '{print substr($1,31,8)'}`
  vec_end=`echo $ins | awk '{print substr($1,47,8)'}`
  if [ $scene -gt $vec_start -a $scene -lt $vec_end ]; then
    insfile=$INS_dir/$ins
    insfind=1
    break # exit loop if parameters met
  fi
done < ins.list
rm -rf ins.list
cd $scene_dir
if [ $insfind -eq 0 ]; then
  echo "ERROR: Can not find proper ASA_INS_* file!"
  exit 1
fi

## Generate the MSP processing parameter file and raw data in GAMMA format
GM ASAR_IM_proc $IMG $insfile $sensor_par $msp_par $raw $ant

## Update orbital state vectors in MSP processing parameter file
GM DELFT_proc2 $msp_par $orb_dir

## Determine the Doppler Ambiguity
GM dop_ambig $sensor_par $msp_par $raw 2 - $slc_name.mlbf
## Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
#GM dop_mlcc $sensor_par $msp_par $raw $slc_name.mlcc

#plot_mlcc.bash $slc_name.mlcc
#plot_mlbf.bash $slc_name.mlbf

## Determine the fractional Doppler centroid using the azimuth spectrum
GM azsp_IQ $sensor_par $msp_par $raw $slc_name.azsp

plot_azsp.bash $slc_name.azsp

## Estimate the doppler centroid across the swath
GM doppler $sensor_par $msp_par $raw $slc_name.dop - - 2 0

plot_dop.bash $slc_name.dop

## Estimate the range power spectrum
## Look for potential radio frequency interference (RFI) to the SAR signal
GM rspec_IQ $sensor_par $msp_par $raw $slc_name.rspec

## Check range spectrum for spikes indicating RFI. If they exist can be suppresed during range compression 'pre_rc'
plot_rspec.bash $slc_name.rspec $scene

## Range compression
## second to last parameter is for RFI suppression.
GM pre_rc $sensor_par $msp_par $raw $slc_name.rc

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
par_MSP $sensor_par $msp_par $slc_par 0

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
