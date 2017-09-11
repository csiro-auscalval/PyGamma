#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_PALSAR_L1_SLC: Script takes Level 1.1 PALSAR1 and PALSAR2 data and  *"
    echo "*                        produces sigma0 calibrated SLC.                      *"
    echo "*                                                                             *"
    echo "*                        Requires a 'frame.list' text file to be created in   *"
    echo "*                        the project directory. This lists the frame numbers  *"
    echo "*                        on each line (e.g. 7160).                            *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*         <beam>       Beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       20/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.1                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*         Sarah Lawrie @ GA       16/06/2016, v1.2                            *"
    echo "*             - modify concatenation to allow for up to 3 frames              *"
    echo "*******************************************************************************"
    echo -e "Usage: process_PALSAR_L1_SLC.bash [proc_file] [scene] [rlks] [alks] <beam>"
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
#cat_snr=`grep cat_snr= $proc_file | cut -d "=" -f 2`
#cat_win=`grep cat_win= $proc_file | cut -d "=" -f 2`

slc_rlks=$3
slc_alks=$4
beam=$5

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$proj_dir/raw_data/$track_dir
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$raw_dir_ga
fi

cd $proj_dir/$track_dir

beam_list=$proj_dir/$track_dir/lists/`grep List_of_beams= $proc_file | cut -d "=" -f 2`
frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $scene $slc_rlks"rlks" $slc_alks"alks" $beam 1>&2

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
#if beams exist, need to identify beam in file name
if [ -z $beam ]; then # no beam
    slc_name=$scene"_"$polar
    mli_name=$scene"_"$polar"_"$slc_rlks"rlks"
else # beam exists
    slc_name=$scene"_"$polar"_"$beam
    mli_name=$scene"_"$polar"_"$beam"_"$slc_rlks"rlks"
fi
para=$slc_name"_SLC_parameters.txt"
slc=$slc_name.slc
slc_par=$slc.par
mli=$mli_name.mli
mli_par=$mli.par
tiff=$mli_name.tif
ras_out=$mli_name.ras
fbd2fbs_slc=$slc_name"_FBS.slc"
fbd2fbs_par=p$slc_name"_FBS.slc.par"


## Set mode based on polarisation
pol_list=$scene_dir/pol_list
rm -f $pol_list

if [ ! -e $slc_dir/$scene/$slc ]; then
    while read frame_num; do
	if [ ! -z $frame_num ]; then
	    frame=`echo $frame_num | awk '{print $1}'`
	    if [ $platform == GA ]; then
		ls $raw_dir/F$frame/date_dirs/$scene/IMG-HH*$beam* >& hh_temp
		ls $raw_dir/F$frame/date_dirs/$scene/IMG-HV*$beam* >& hv_temp
		temp="ls: cannot access"
		temp1=`awk '{print $1" "$2" "$3}' hh_temp`
		if [ "$temp1" == "$temp" ]; then
		    :
		else
		    basename $raw_dir/F$frame/$scene/IMG-HH*$beam* >> $pol_list 
		fi
		temp2=`awk '{print $1" "$2" "$3}' hv_temp`
		if [ "$temp2"  == "$temp" ]; then
		    :
		else
		    basename $raw_dir/F$frame/$scene/IMG-HV*$beam* >> $pol_list
		fi
		rm -rf hh_temp hv_temp
	    else
		ls $raw_dir/F$frame/$scene/IMG-HH*$beam* >& hh_temp
		ls $raw_dir/F$frame/$scene/IMG-HV*$beam* >& hv_temp
		temp="ls: cannot access"
		temp1=`awk '{print $1" "$2" "$3}' hh_temp`
		if [ "$temp1" == "$temp" ]; then
		    :
		else
		    basename $raw_dir/F$frame/$scene/IMG-HH*$beam* >> $pol_list 
		fi
		temp2=`awk '{print $1" "$2" "$3}' hv_temp`
		if [ "$temp2"  == "$temp" ]; then
		    :
		else
		    basename $raw_dir/F$frame/$scene/IMG-HV*$beam* >> $pol_list
		fi
		rm -rf hh_temp hv_temp
	    fi
	fi
    done < $frame_list
  
    num_hv=`grep -co "HV" $pol_list`
    if [ -f $sensor == PALSAR2 ]; then # no FBD or FBS conversion if PALSAR2 wide swath data
	:
    else
	if [ "$num_hv" -eq 0 -a "$polar" == HH ]; then 
	    mode=FBS
	elif [ "$num_hv" -ge 1 -a "$polar" == HH ]; then 
	    mode=FBD
	elif [ $polar == HV ]; then
	    mode=FBD
	else
	    :
	fi
    fi
    echo "Mode:" $mode "  Polarisation:" $polar
    rm -f $pol_list

    ## Produce SLC data files
    while read frame_num; do
	if [ ! -z $frame_num ]; then
	    frame=`echo $frame_num | awk '{print $1}'`
	    if [ -z $beam ]; then # no beam
		fr_slc_name=$scene"_"$polar"_F"$frame
		fr_mli_name=$scene"_"$polar"_F"$frame"_"$slc_rlks"rlks"
                IMG=$raw_dir/F$frame/$scene/IMG-$polar-*
	    else # beam exists
		fr_slc_name=$scene"_"$polar"_"$beam"_F"$frame
		fr_mli_name=$scene"_"$polar"_"$beam"_F"$frame"_"$slc_rlks"rlks"
                IMG=$raw_dir/F$frame/$scene/IMG-$polar-*$beam
	    fi
	    fr_slc=$fr_slc_name.slc
	    fr_slc_par=$fr_slc.par
	    fr_mli=$fr_mli_name.mli
	    fr_mli_par=$fr_mli.par
	    #if [ $platform == GA ]; then
		#LED=$raw_dir/F$frame/date_dirs/$scene/LED-*
    		#IMG=$raw_dir/F$frame/date_dirs/$scene/IMG-$polar-*
	    #else
	    LED=$raw_dir/F$frame/$scene/LED-*
    		
	    #fi
	    GM par_EORC_PALSAR $LED $fr_slc_par $IMG $fr_slc

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
    # concatenate first 2 frames (maximum 3 frames allowed for)
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
	rm -rf cat_slc cat_slc_tab tab1 tab2 SLC_cat_all*.log create_offset.in 
	# concatenate 3rd frame to concatenated frames above
	if [ $lines -eq 3 ]; then
	    slc1=$slc_name"_F1-F2.slc"
	    slc1_par=$slc1.par
	    mv $slc $slc1
	    mv $slc_par $slc1_par
	    echo $slc1 $slc1_par > tab1
	    slc2=`awk 'NR==3 {print $1}' $raw_file_list`
	    slc2_par=`awk 'NR==3 {print $2}' $raw_file_list`
	    echo $slc2 $slc2_par > tab2
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
	fi
	rm -rf $raw_file_list cat_slc cat_slc_tab tab1 tab2 test1.dat test2.dat t1.dat SLC_cat_all*.log create_offset.in *_resamp.log *.snr *.off* *.coffs
    fi

### MANUAL PROCESS THAT WASN'T WORKING PROPERLY
    # create offset parameter files for estimation of the offsets
#    GM create_offset $slc1_par $slc2_par $cat_off 1 - - 0
    # measure initial range and azimuth offsets using orbit information
#    GM init_offset_orbit $slc1_par $slc2_par $cat_off - - 1 
    # measure initial range and azimuth offsets using the images
#    GM init_offset $slc1 $slc2 $slc1_par $slc2_par $cat_off 1 1 - - 0 0 $cat_snr $cat_win $cat_win 1
    # estimate range and azimuth offset models using correlation of image intensities
#    GM offset_pwr $slc1 $slc2 $slc1_par $slc2_par $cat_off $offs $snr
#    GM offset_fit $offs $snr $cat_off $coffs - - 3
    # concatenate SLC images
#    GM SLC_cat $slc1 $slc2 $slc1_par $slc2_par $cat_off $slc $slc_par 1 0 1
    # clean up files
    # if correlation is below threshold, warning not automatically appearing in error log
#    grep "WARNING:" output.log  1>&2 
#    grep "ERROR:" output.log  1>&2 
#    rm -rf temp $raw_file_list
fi


## Compute the azimuth Doppler spectrum and the Doppler centroid from SLC data
GM az_spec_SLC $slc $slc_par $slc_name.dop - 0 

## update ISP file with new estimated doppler centroid frequency (must be done manually)
org_value=`grep doppler_polynomial: $slc_par | awk '{print $2}'`
new_value=`grep "new estimated Doppler centroid frequency (Hz):" output.log | awk '{print $7}'`
sed ' s/'"$org_value"'/'"$new_value"'/' $slc_par > $slc_name.temp
mv -f $slc_name.temp $slc_par
rm -rf $slc_name"_temp.dop"

## FBD to FBS Conversion
if [ $sensor == PALSAR2 ]; then
    :
else
    if [ $polar == HH -a $mode == FBD ]; then
	GM SLC_ovr $slc $slc_par $fbd2fbs_slc $fbd2fbs_par 2
	rm -f $slc
	rm -f $slc_par
	mv $fbd2fbs_slc $slc
	mv $fbd2fbs_par $slc_par
    else
	:
    fi
fi

else
    echo " "
    echo "Full SLC already created."
    echo " "
fi

## Multi-look SLC
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

## Rename log files if beam exists
if [ -z $beam ]; then # no beam
    :    
else # beam exists
    if [ -f $beam"_command.log" ]; then
	cat command.log >>$beam"_command.log"
    else
	mv command.log $beam"_command.log"
    fi
    if [ -f $beam"_output.log" ]; then
	cat output.log >>$beam"_output.log"
    else
	mv output.log $beam"_output.log"
    fi
    if [ -f $beam"_error.log" ]; then
	cat error.log >>$beam"_error.log"
    else
	mv error.log $beam"_error.log"
    fi
fi

