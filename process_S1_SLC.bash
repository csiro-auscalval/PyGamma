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
    echo "*         Sarah Lawrie @ GA          28/07/2016, v1.2                         *"
    echo "*         Add concatenation of consecutive burst SLCs (join 2 or 3 frames)    *"
    echo "*         Add use of precise orbit information                                *"
    echo "*         Sarah Lawrie @ GA         08/09/2017, v1.3                          *"
    echo "*         Update burst tabs to enable auto subset of scenes                   *"
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
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
pol=`echo $polar | tr '[:upper:]' '[:lower:]'`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
raw_dir_ga=`grep Raw_data_GA= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_data_MDSS= $proc_file | cut -d "=" -f 2`

slc_rlks=$3
slc_alks=$4

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$proj_dir/raw_data/$track_dir
    orbit_dir=$raw_dir/orbits
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$raw_dir_ga
fi

frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir

mkdir -p full_slc_pdfs

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
slc_bmp=$slc_name.bmp
slc1=$slc_name"_IW1.slc"
slc_par1=$slc1.par
tops_par1=$slc1.TOPS_par
slc_bmp1=$slc1.bmp
slc1_1=$slc_name"_IW1_1.slc"
slc_par1_1=$slc1_1.par
tops_par1_1=$slc1_1.TOPS_par
slc_pre1=$slc_name"_IW1_pre_shift.slc"
slc_pre_par1=$slc_pre1.par
tops_pre_par1=$slc_pre1.TOPS_par
slc_pre_bmp1=$slc_pre1.bmp
slc1s=$slc_name"_IW1_s.slc"
slc_par1s=$slc1s.par
tops_par1s=$slc1s.TOPS_par
slc2=$slc_name"_IW2.slc"
slc_par2=$slc2.par
tops_par2=$slc2.TOPS_par
slc_bmp2=$slc2.bmp
slc2_1=$slc_name"_IW2_1.slc"
slc_par2_1=$slc2_1.par
tops_par2_1=$slc2_1.TOPS_par
slc3=$slc_name"_IW3.slc"
slc_par3=$slc3.par
tops_par3=$slc3.TOPS_par
slc_bmp3=$slc3.bmp
slc3_1=$slc_name"_IW3_1.slc"
slc_par3_1=$slc3_1.par
tops_par3_1=$slc3_1.TOPS_par
mli=$mli_name.mli
mli_par=$mli.par
slc_full_tab=$slc_name"_full_tab"



## Produce SLC data files
if [ ! -e $slc_dir/$scene/$slc ]; then
    rm -f $slc_full_tab slc_tab_s pslc_tab 

    # Get list of IW SLCs 
    echo $scene_dir/$slc1 $scene_dir/$slc_par1 $scene_dir/$tops_par1 > $slc_full_tab
    echo $scene_dir/$slc2 $scene_dir/$slc_par2 $scene_dir/$tops_par2 >> $slc_full_tab
    echo $scene_dir/$slc3 $scene_dir/$slc_par3 $scene_dir/$tops_par3 >> $slc_full_tab 

    if [ -e $frame_list ]; then
	while read frame_num; do
	   #frame_num=`echo $list | awk '{print $1}'`
	    if [ ! -z "$frame_num" ]; then
		date=`echo $frame_num | awk '{print $2}'`
		if [ "$date" -eq "$scene" ]; then
		    tot_frame=`echo $frame_num | awk '{print $1}'`
		    if [ $tot_frame -eq 1 ]; then # single frame, no concatenation
			for swath in 1 2 3; do
			    echo " "
			    echo "Processing swath "$swath" for SLC "$scene
			    echo " "
			    annot=`ls $raw_dir/F1/$scene/*$scene*/annotation/s1a-iw$swath-slc-$pol*.xml`
			    data=`ls $raw_dir/F1/$scene/*$scene*/measurement/s1a-iw$swath-slc-$pol*.tiff`
			    calib=`ls $raw_dir/F1/$scene/*$scene*/annotation/calibration/calibration-s1a-iw$swath-slc-$pol*.xml`
			    noise=`ls $raw_dir/F1/$scene/*$scene*/annotation/calibration/noise-s1a-iw$swath-slc-$pol*.xml`
			    bslc="slc$swath"
			    bslc_par=${!bslc}.par
			    btops="tops_par$swath"
			    GM par_S1_SLC $data $annot $calib $noise $bslc_par ${!bslc} ${!btops}
			done 
		    else # multiple frames
			i=1
			while [ "$i" -le "$tot_frame" ]; do
			    for swath in 1 2 3; do
    				fr_slc_name=$scene"_"$polar"_F"$i
				fr_slc1=$fr_slc_name"_IW1.slc"
				fr_slc_par1=$fr_slc1.par
				fr_tops_par1=$fr_slc1.TOPS_par
				fr_slc2=$fr_slc_name"_IW2.slc"
				fr_slc_par2=$fr_slc2.par
				fr_tops_par2=$fr_slc2.TOPS_par
				fr_slc3=$fr_slc_name"_IW3.slc"
				fr_slc_par3=$fr_slc3.par
				fr_tops_par3=$fr_slc3.TOPS_par
				echo " "

				echo "Processing swath "$swath" for frame "$i", SLC "$scene
				echo " "
				annot=`ls $raw_dir/F$i/$scene/*$scene*/annotation/s1a-iw$swath-slc-$pol*.xml`
				data=`ls $raw_dir/F$i/$scene/*$scene*/measurement/s1a-iw$swath-slc-$pol*.tiff`
				calib=`ls $raw_dir/F$i/$scene/*$scene*/annotation/calibration/calibration-s1a-iw$swath-slc-$pol*.xml`
				noise=`ls $raw_dir/F$i/$scene/*$scene*/annotation/calibration/noise-s1a-iw$swath-slc-$pol*.xml`
				bslc="fr_slc$swath"
				bslc_par=${!bslc}.par
				btops="fr_tops_par$swath"
				GM par_S1_SLC $data $annot $calib $noise $bslc_par ${!bslc} ${!btops}
				
				echo ${!bslc} >> slc_list
				echo $bslc_par >> par_list
				echo ${!btops} >> tops_list	
			    done
			    i=$(($i + 1))
			done
		    fi
		fi
	    fi
	done < $frame_list
    else
	echo "no frame list, if scenes has a single frame, enter 1 for the total number of frames in frame list file"
    fi


#width=`grep range_samples: 20151020_VV_F2_IW3.slc.par | awk '{print $2}'`  
#rasSLC 20151020_VV_F2_IW3.slc $width 1 0 50 20 1 0.35 1 0 0 20151020_VV_F2_IW3_slc.bmp

    # Concatenate frames
    echo " "
    echo "Concatenate frames to produce SLC bursts ..."
    echo " "
    while read frame_num; do
	if [ ! -z "$frame_num" ]; then
	    date=`echo $frame_num | awk '{print $2}'`
	    if [ "$date" -eq "$scene" ]; then
		tot_frame=`echo $frame_num | awk '{print $1}'`
		if [ $tot_frame -eq 1 ]; then # single frame, no concatenation
		    :
		elif [ $tot_frame -eq 2 ]; then # 2 frames
		    paste slc_list par_list tops_list > lists
		    head -n 3 lists > fr_tab1
		    tail -3 lists > fr_tab2
		    
		    GM SLC_cat_S1_TOPS fr_tab1 fr_tab2 $slc_full_tab

		elif [ $tot_frame -eq 3 ]; then # 3 frames
		    paste slc_list par_list tops_list > lists
		    echo $scene_dir/$slc1_1 $scene_dir/$slc_par1_1 $scene_dir/$tops_par1_1 > slc1_tab
		    echo $scene_dir/$slc2_1 $scene_dir/$slc_par2_1 $scene_dir/$tops_par2_1 >> slc1_tab
		    echo $scene_dir/$slc3_1 $scene_dir/$slc_par3_1 $scene_dir/$tops_par3_1 >> slc1_tab
		    head -n 3 lists > fr_tab1
		    tail -n +4 lists | head -3 > fr_tab2
		    tail -3 lists > fr_tab3
		    
		    GM SLC_cat_S1_TOPS fr_tab1 fr_tab2 slc1_tab
		    GM SLC_cat_S1_TOPS slc1_tab fr_tab3 $slc_full_tab 
		else
		    echo "script can only concatenate up to 3 frames"   
		fi
	        # remove frame slc files
		if [ -e slc_list ]; then
		    paste slc_list > to_remove
		    paste par_list >> to_remove
		    while read remove; do
			rm -f $remove
		    done < to_remove
		fi
	    fi
	fi
    done < $frame_list

    rm -f to_remove slc_list par_list tops_list lists fr_tab* slc1_tab 

    # Make quick-look image of bursts for each swath
    for swath in 1 2 3; do
	bslc="slc$swath"
	bslc_par=${!bslc}.par
	bmp="slc_bmp$swath"
	width=`grep range_samples: $bslc_par | awk '{print $2}'`
	lines=`grep azimuth_lines: $bslc_par | awk '{print $2}'`
	GM rasSLC ${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bmp}
    done

    # If using deramp
    #GM par_S1_SLC $data $annot $calib $noise p$bslc_par p${!bslc} p${!btops}
    #echo $scene_dir/p${!bslc} $scene_dir/p$bslc_par $scene_dir/p${!btops} >> pslc_tab

    ## Deramp the burst SLCs and output subtracted phase ramps
    ## Only needed if the SLC is to be oversampled e.g. for use with offset tracking programs
    #GM SLC_deramp_S1_TOPS pslc_tab $slc_full_tab 0 1

    ## Phase shift for IW1 of the image before 15th of March 2015
    if [ $scene -lt 20150310 ]; then 
	GM SLC_phase_shift $slc1 $slc_par1 $slc1s $slc_par1s -1.25
	cp $tops_par1 $tops_par1s
        #rename original slc files to 'pre_shift' and rename new slcs back to original filenames
	mv $slc1 $slc_pre1
	mv $slc_par1 $slc_pre_par1
	mv $tops_par1 $tops_pre_par1
	mv $slc1s $slc1
	mv $slc_par1s $slc1_par
	mv $tops_par1s $tops_par1
    else
	:
    fi 

    # Create SLC mosaic from individual burst SLCs
    echo " "
    echo "Mosaic SLC bursts ..."
    echo " "

    GM SLC_mosaic_S1_TOPS $slc_full_tab $slc $slc_par $slc_rlks $slc_alks  

    # Import precise orbit information (if they have been downloaded)
    if [ -n "$(ls -A $orbit_dir)" ]; then #directory contains files
	ls $orbit_dir/* > temp1
	date_sub=1
	orb_date=$(date "--date=${scene} -${date_sub} day" +%Y%m%d)
	opod=`sed -n "/$orb_date/p" temp1`
	if [ ! -z $opod ]; then #correct orbit file exists
	    GM S1_OPOD_vec $slc_par $opod 
	else
	    :
	fi
	rm -f temp1
    else # orbit directory empty
	:
    fi

    # Make quick-look image of full SLC
    width=`grep range_samples: $slc_par | awk '{print $2}'`
    lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
    GM rasSLC $slc $width 1 $lines 50 20 - - 1 0 0 $slc_bmp

    # Multi-look full SLC
    GM multi_look $slc $slc_par $mli $mli_par $slc_rlks $slc_alks 0



    # Check number of bursts and their corner coordinates and put into central file
    burst_file=$scene_dir/slc_burst_values.txt
    echo "Number of Bursts per Swath" > $burst_file
    echo " " >> $burst_file
    while read file; do
	par=`echo $file | awk '{print $2}'`
	tops=`echo $file | awk '{print $3}'`

	SLC_burst_corners $par $tops > temp1

	swath=`awk 'NR==7 {print $6}' temp1`
	echo "Swath: "$swath >> $burst_file
	start=`grep start_time: $par | awk '{print $2}'`
	echo "   start time: "$start >> $burst_file
	bursts=`awk 'NR==8 {print $7}' temp1`
	echo "   total bursts: "$bursts >> $burst_file
	echo "Num     Upper_Right                      Upper_left                      Lower_Left                     Lower_Right" >> $burst_file
	tail -n +10 temp1 > temp2
	head -n -9 temp2 > temp3
	awk '{print $2"\t"$3" "$4"\t"$5" "$6"\t"$7" "$8"\t"$9" "$10}' temp3 >> $burst_file
	echo " " >> $burst_file
    done < $slc_full_tab
    rm -f temp1 temp2 temp3

    # Preview of full SLC and bursts

    # number of bursts per swath
    sed -n '/Swath: IW1/,/Num/p' $burst_file > temp1
    sw1_burst=`awk 'NR==3 {print}' temp1 | awk '{print $3}'`
    sed -n '/Swath: IW2/,/Num/p' $burst_file > temp1
    sw2_burst=`awk 'NR==3 {print}' temp1 | awk '{print $3}'`
    sed -n '/Swath: IW3/,/Num/p' $burst_file > temp1
    sw3_burst=`awk 'NR==3 {print}' temp1 | awk '{print $3}'`

    # swath stop times (to determine placement of each swath plot)
    grep end_time: $slc_par1 | awk '{print $2}' > temp1
    echo "IW1" > temp2
    paste temp2 temp1 > temp3
    grep end_time: $slc_par2 | awk '{print $2}' > temp1
    echo "IW2" > temp2
    paste temp2 temp1 >> temp3
    grep end_time: $slc_par3 | awk '{print $2}' > temp1
    echo "IW3" > temp2
    paste temp2 temp1 >> temp3
    sort -k2 -n temp3 > sorted_end_times
    rm -f temp1 temp2 temp3

    # determine swath order
    first=`awk 'NR==1 {print $1}' sorted_end_times`
    second=`awk 'NR==2 {print $1}' sorted_end_times`
    third=`awk 'NR==3 {print $1}' sorted_end_times`

    # auto positioning of swaths on plot
    top="-0.9c"
    middle="-1.2c"
    bottom="-1.5c"
    if [ $first == "IW1" ]; then
	pos1=$top
    elif [ $first == "IW2" ]; then
	pos2=$top
    elif [ $first == "IW3" ]; then
	pos3=$top
    fi
    if [ $second == "IW1" ]; then
	pos1=$middle
    elif [ $second == "IW2" ]; then
	pos2=$middle
    elif [ $second == "IW3" ]; then
	pos3=$middle
    fi
    if [ $third == "IW1" ]; then
	pos1=$bottom
    elif [ $third == "IW2" ]; then
	pos2=$bottom
    elif [ $third == "IW3" ]; then
	pos3=$bottom
    fi
    # auto length of swaths
    sw1_len=`echo $sw1_burst*0.95 | bc -l`
    sw2_len=`echo $sw2_burst*0.95 | bc -l`
    sw3_len=`echo $sw3_burst*0.95 | bc -l`

    # plot swaths
    gmtset PS_MEDIA A4
    outline="-JX23c/26c"
    range="-R0/100/0/100"
    psfile=$scene"_"$polar"_full_SLC.ps"
    psbasemap $outline $range -Bnesw -K -P > $psfile
    pstext $outline $range -F+cTL+f15p -O -K -P <<EOF >> $psfile
$project $track $scene $polar Full SLC
EOF
    psimage $slc_bmp -W4c/4c -Fthin -C14c/22c -O -K -P >> $psfile
    pstext $outline $range -F+f13p -O -K -P <<EOF >> $psfile
5.5 88.5 Swath 1 ($sw1_burst)
EOF
    psimage $slc_bmp1 -W4.5c/$sw1_len"c" -Fthin -C-1c/$pos1 -O -K -P >> $psfile
    pstext $outline $range -F+f13p -O -K -P <<EOF >> $psfile
26 88.5 Swath 2 ($sw2_burst)
EOF
    psimage $slc_bmp2 -W4.5c/$sw2_len"c" -Fthin -C4c/$pos2 -K -O -P >> $psfile
    pstext $outline $range -F+f13p -K -O -P <<EOF >> $psfile
47 88.5 Swath 3 ($sw3_burst)
EOF
    psimage $slc_bmp3 -W4.5c/$sw3_len"c" -Fthin -C9c/$pos3 -O -P >> $psfile

    ps2raster -Tf $psfile
    rm -rf $psfile sorted_end_times
    #evince $scene"_"$polar"_full_SLC.pdf"

    cp $scene"_"$polar"_full_SLC.pdf" $proj_dir/$track_dir/full_slc_pdfs

    echo " "
    echo "Full SLC created."
    echo " "
else
    echo " "
    echo "Full SLC already created."
    echo " "
fi



# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
   cat error.log 1>&2
   rm temp_log
else
   rm temp_log
fi
