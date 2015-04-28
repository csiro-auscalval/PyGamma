#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_PALSAR2_SLC: Script takes Level 1.1 PALSAR1 and PALSAR2 data and    *"
    echo "*                      produces sigma0 calibrated SLC.                        *"
    echo "*                                                                             *"
    echo "*                      Requires a 'frame.list' text file to be created in     *"
    echo "*                      the project directory. This lists the frame numbers    *"
    echo "*                      on each line (e.g. 7160).                              *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       09/04/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: process_PALSAR2_SLC.bash [proc_file] [scene] [rlks] [alks]"
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
frame_list=`grep List_of_frames= $proc_file | cut -d "=" -f 2`
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
echo "PROCESSING_PROJECT: "$project $track_dir $scene 1>&2

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
sensor_antpat=$MSP_HOME/sensors/palsar_ant_20061024.dat
msp_antpat="PALSAR_antpat_MSP_"$polar.dat
sensor_par="PALSAR_sensor_"$polar.par
msp_par="p"$slc_name.slc.par
para=$slc_name"_SLC_parameters.txt"
raw=$slc_name.raw
slc=$slc_name.slc
slc_par=$slc.par
mli=$mli_name.mli
mli_par=$mli.par
tiff=$mli_name.tif
ras_out=$mli_name.ras


## Produce SLC data files
while read frame_num; do
    if [ ! -z $frame_num ]; then
	frame=`echo $frame_num | awk '{print $1}'`
	ls $raw_dir/F$frame/date_dirs/$scene/LED-ALP* >& temp
	LED=`awk '{print $1}' temp`
	rm -f temp
        # Check polarisation
	if [ $polar == HH ]; then
	    ls $raw_dir/F$frame/date_dirs/$scene/IMG-HH* >& temp
	    IMG=`awk '{print $1}' temp`
	    rm -f temp
	else 
	    ls $raw_dir/F$frame/date_dirs/$scene/IMG-HV* >& temp
	    IMG=`awk '{print $1}' temp`
	    rm -f temp
	fi
	
	par_EORC_PALSAR $LED $slc_par $IMG $slc


## Concatenate two SLC files into one SLC - details from SLC_cat ref manual. can only concatenate 2 slcs at a time

create_offset      slc1_par slc2_par *.off 
init_offset_orbit  slc1_par slc2_par *.off - - 0
init_offset        slc1 slc2 slc1_par slc2_par *.off 1 1 - - 0 0 - 512 512 1
offset_pwr         slc1 slc2 slc1_par slc2_par *.off offs snr
offset_fit         offs snr *.off coffs coffsets 
SLC_cat            slc1 slc2 slc1_par slc2_par *.off new_slc new_slc_par


        ## Generate the processing parameter files and raw data in GAMMA format
	GM PALSAR_proc $LED $sensor_fm_par $msp_fm_par $IMG $raw_fm_file $tx_pol1 $rx_pol1

        ## Copy raw data file details to text file to check if concatenation of scenes along track is required
	echo $raw_fm_file $sensor_fm_par $msp_fm_par >> $raw_file_list
    fi
done < $proj_dir/$track_dir/$frame_list

## Check if scene concatenation is required (i.e. a scene has more than one frame)
lines=`awk 'END{print NR}' $raw_file_list`
if [ $lines -eq 1 ]; then
    ## rename files to enable further processing (remove reference to 'frame' in file names)
    mv $sensor_fm_par $sensor_par
    mv $msp_fm_par $msp_par
    mv $raw_fm_file $raw
    rm -f $raw_file_list
else












    ## Concatenate scenes into one output data file
    GM cat_raw $raw_file_list $sensor_par $msp_par $raw 1 0 - 
    rm -f p$scene"_"*"_"$polar.slc.par
    rm -f "PALSAR_sensor_"*"_"$polar.par
    rm -f $scene"_"*"_"$polar.raw
    rm -f $raw_file_list
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
