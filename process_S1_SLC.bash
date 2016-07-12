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
    echo "*         Negin Moghaddam @ GA       13/05/2016, v1.1                         *"
    echo "*         Add the phase_shift function to apply on IW1 of the image before    *"
    echo "*         mid-March 2015                                                      *"
    echo "*         Sarah Lawrie @ GA          25/05/2016, v1.2                         *"
    echo "*         Add concatenation of consecutive burst SLCs (join two frames)       *"
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
pol=`echo $polar | tr '[:upper:]' '[:lower:]'`
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

frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`

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
#para=$slc_name"_SLC_parameters.txt"
slc=$slc_name.slc
slc_par=$slc.par
slc1=$slc_name"_IW1.slc"
slc1_par=$slc1.par
tops_par1=$slc1.TOPS_par
slc1s=$slc_name"_IW1_s.slc"
slc1s_par=$slc1s.par
tops_par1s=$slc1s.TOPS_par
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

if [ ! -e $slc_dir/$scene/$slc ]; then
    rm -f slc_tab slc_tab_s pslc_tab fr_tab1 fr_tab2 

    ## Produce SLC data files
    if [ -f $frame_list ]; then # if frames exist

	# get list of IW SLCs for concatnation
	echo $slc1 $slc1_par $tops_par1 > slc_tab
	echo $slc2 $slc2_par $tops_par2 >> slc_tab
	echo $slc3 $slc3_par $tops_par3 >> slc_tab

	while read frame_num; do
	    if [ ! -z $frame_num ]; then
		if [ $platform == GA ]; then
		    : # do later
		else 
		    frame=`echo $frame_num | awk '{print $1}'`
		    fr_slc_name=$scene"_"$polar"_F"$frame
		    fr_slc1=$fr_slc_name"_IW1.slc"
		    fr_slc1_par=$fr_slc1.par
		    fr_tops_par1=$fr_slc1.TOPS_par
		    fr_slc2=$fr_slc_name"_IW2.slc"
		    fr_slc2_par=$fr_slc2.par
		    fr_tops_par2=$fr_slc2.TOPS_par
		    fr_slc3=$fr_slc_name"_IW3.slc"
		    fr_slc3_par=$fr_slc3.par
		    fr_tops_par3=$fr_slc3.TOPS_par

		    for swath in 1 2 3; do
			echo " "
			echo "Processing frame "$frame"'s sub-swath "$swath
			echo " "
			annot=`ls $raw_dir/F$frame/$scene/*$scene*/annotation/s1a-iw$swath-slc-$pol*.xml`
			data=`ls $raw_dir/F$frame/$scene/*$scene*/measurement/s1a-iw$swath-slc-$pol*.tiff`
			calib=`ls $raw_dir/F$frame/$scene/*$scene*/annotation/calibration/calibration-s1a-iw$swath-slc-$pol*.xml`
			noise=`ls $raw_dir/F$frame/$scene/*$scene*/annotation/calibration/noise-s1a-iw$swath-slc-$pol*.xml`

			bslc="fr_slc$swath"
			bslc_par=${!bslc}.par
			btops="fr_tops_par$swath"

                        # Import S1 sub-swath SLC
			GM par_S1_SLC $data $annot $calib $noise $bslc_par ${!bslc} ${!btops}
			
			# Make quick-look image
			width=`grep range_samples: $bslc_par | awk '{print $2}'`
			lines=`grep azimuth_lines: $bslc_par | awk '{print $2}'`
			GM rasSLC ${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bslc}.bmp

			# lists for concatenation
			echo ${!bslc} >> slc_list
			echo $bslc_par >> par_list
			echo ${!btops} >> tops_list	
		    done     
		fi
	    fi
	done < $frame_list
	echo " "
	echo "Concatenate frames to produce SLC bursts ..."
	echo " "

	## Concatenate consecutive burst SLCs (only works with two frames)
	paste slc_list par_list tops_list > lists
	head -n 3 lists > fr_tab1
	tail -3 lists > fr_tab2
	rm -f slc_list par_list tops_list lists

	GM SLC_cat_S1_TOPS fr_tab1 fr_tab2 slc_tab
	
	## Deramp the burst SLCs and output subtracted phase ramps
        ## Only needed if the SLC is to be oversampled e.g. for use with offset tracking programs
	#sed 's/'"$scene"'/p'"$scene"'/g' slc_tab > pslc_tab
	#GM SLC_deramp_S1_TOPS pslc_tab slc_tab 0 1

	echo " "
	echo "Mosaic SLC bursts ..."
	echo " "

        ## Phase shift for IW1 of the image before 15th of March 2015
	if [ $scene -lt 20150310 ]; then 
	    GM SLC_phase_shift $slc1 $slc1_par $slc1s $slc1s_par -1.25
	    cp  $tops_par1 $tops_par1s
	    sed 's/IW1/IW1_s/g' slc_tab > slc_tab_s
	    # Make the SLC mosaic from individual burst SLCs
	    GM SLC_mosaic_S1_TOPS slc_tab_s $slc $slc_par $slc_rlks $slc_alks
        else
            # Make the SLC mosaic from individual burst SLCs
	    GM SLC_mosaic_S1_TOPS slc_tab $slc $slc_par $slc_rlks $slc_alks
	fi     

	width=`grep range_samples: $slc_par | awk '{print $2}'`
	lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
	GM rasSLC $slc $width 1 $lines 50 10 - - 1 0 0 $slc.bmp

    else # no frames
	for swath in 1 2 3
	do
	    echo " "
	    echo "Processing SLC for sub-swath "$swath
	    echo " "
	    if [ $platform == GA ]; then
		annot=`ls $raw_dir/$track_dir/date_dirs/$scene/*$scene*/annotation/s1a-iw$swath-slc-$pol*.xml`
    		data=`ls $raw_dir/$track_dir/date_dirs/$scene/*$scene*/measurement/s1a-iw$swath-slc-$pol*.tiff`
		calib=`ls $raw_dir/$track_dir/date_dirs/$scene/*$scene*/annotation/calibration/calibration-s1a-iw$swath-slc-$pol*.xml`
		noise=`ls $raw_dir/$track_dir/date_dirs/$scene/*$scene*/annotation/calibration/noise-s1a-iw$swath-slc-$pol*.xml`
	    else
		annot=`ls $raw_dir/$scene/*$scene*/annotation/s1a-iw$swath-slc-$pol*.xml`
    		data=`ls $raw_dir/$scene/*$scene*/measurement/s1a-iw$swath-slc-$pol*.tiff`
		calib=`ls $raw_dir/$scene/*$scene*/annotation/calibration/calibration-s1a-iw$swath-slc-$pol*.xml`
		noise=`ls $raw_dir/$scene/*$scene*/annotation/calibration/noise-s1a-iw$swath-slc-$pol*.xml`
	    fi
	    
	    bslc="slc$swath"
	    bslc_par=${!bslc}.par
	    btops="tops_par$swath"

	    # Import S1 sub-swath SLC
	    GM par_S1_SLC $data $annot $calib $noise $bslc_par ${!bslc} ${!btops}
	    ##GM par_S1_SLC $data $annot $calib $noise p$bslc_par p${!bslc} p${!btops}

	    ## Make quick-look image
	    #width=`grep range_samples: $bslc_par | awk '{print $2}'`
	    #lines=`grep azimuth_lines: $bslc_par | awk '{print $2}'`
	    #GM rasSLC ${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bslc}.bmp
	    ##GM rasSLC p${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bslc}.bmp

   	    #echo $scene_dir/p${!bslc} $scene_dir/p$bslc_par $scene_dir/p${!btops} >> pslc_tab
	    echo $scene_dir/${!bslc} $scene_dir/$bslc_par $scene_dir/${!btops} >> slc_tab

	done

        ## Deramp the burst SLCs and output subtracted phase ramps
        ## Only needed if the SLC is to be oversampled e.g. for use with offset tracking programs
        #GM SLC_deramp_S1_TOPS pslc_tab slc_tab 0 1

        ## Phase shift for IW1 of the image before 15th of March 2015
	if [ $scene -lt 20150310 ]; then 
	    GM SLC_phase_shift $slc1 $slc1_par $slc1s $slc1s_par -1.25
	    cp  $tops_par1 $tops_par1s
	    sed 's/IW1/IW1_s/g' slc_tab > slc_tab_s
	    GM SLC_mosaic_S1_TOPS slc_tab_s $slc $slc_par $slc_rlks $slc_alks
	else
            ## Make the SLC mosaic from individual burst SLCs
	    GM SLC_mosaic_S1_TOPS slc_tab $slc $slc_par $slc_rlks $slc_alks
	fi     

	width=`grep range_samples: $slc_par | awk '{print $2}'`
	lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
	GM rasSLC $slc $width 1 $lines 50 10 - - 1 0 0 $slc.bmp
    fi    
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
