#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* crop_S1_SLCs: Crop a stack of Sentinel-1 SLCs, to a reference scene. This   *"
    echo "*               scene can be auto selected (ie. the smallest one) or          *"
    echo "*               manually selected.                                            *"
    echo "*               Ensures all SLCs have same shape and size for processing      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA          08/09/2017, v1.0                         *"
    echo "*******************************************************************************"
    echo -e "Usage: crop_S1_SLCs.bash [proc_file]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
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
do_auto_crop=`grep Do_auto_crop= $proc_file | cut -d "=" -f 2`
ref_scene=`grep Ref_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
    raw_dir=$proj_dir/raw_data/$track_dir
    orbit_dir=$raw_dir/orbits
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir/$track_dir

mkdir -p auto_crop_slc_pdfs

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir 
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
scene_list=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`


CALC_REF_SCENE()
{
    min_bursts=$proj_dir/$track_dir/lists/min_bursts
    echo "Scene Min_Bursts Swath Start_Time" > $min_bursts

    # determine total bursts and start time
    while read scene; do
	scene_dir=$slc_dir/$scene
	cd $scene_dir
	slc_name=$scene"_"$polar
	burst_file=$scene_dir/slc_burst_values.txt
	sed -n '/total/p' $burst_file | awk '{print $3}' > temp1
	sed -n '/Swath:/p' $burst_file | awk '{print $2}' > temp2
	sed -n '/start/p' $burst_file | awk '{print $3}' > temp3
	paste temp1 temp2 temp3 > temp4
	min=`awk 'BEGIN{a=1000}{if ($1<0+a) a=$1} END{print a}' temp4`
        # select all the swaths that have min number of bursts, and then find the swath that starts first
	sed -n "/^$min/p" temp4 > temp5
	sort -k3 -n temp5 > temp6
	burst=`awk 'NR==1 {print}' temp6`
	echo $scene $burst >> $min_bursts
	rm -rf temp*
	cd $slc_dir
    done < $scene_list

    # find scene with min number of bursts
    cd $proj_dir/$track_dir/lists
    min=`awk 'BEGIN{a=1000}{if ($2<0+a) a=$2} END{print a}' $min_bursts`

    # if more than one scene has the same min number of bursts, select the one that starts first
    sed -n "/$min/p" $min_bursts > temp1
    sort -k4 -n temp1 > temp2
    ref_scene=`awk 'NR==1 {print $1}' temp2`

    # update proc file with ref scene 
    cp $proc_file temp3
    sed -i "s/Ref_scene=-/Ref_scene=$ref_scene/g" temp3
    mv temp3 $proc_file
    rm -rf temp*
}



CROP_SLCS()
{
    ref_scene=`grep Ref_scene= $proc_file | cut -d "=" -f 2`

    #  tab file for min scene (scene all others will be cropped to)
    slc_name=$ref_scene"_"$polar
    ref_slc_full_tab=$slc_dir/$ref_scene/$slc_name"_full_tab"

    while read scene; do
	if [ $scene != $ref_scene ]; then
	    scene_dir=$slc_dir/$scene
	    cd $scene_dir
	    slc_name=$scene"_"$polar
	    mli_name1=`ls $scene"_"*.mli`
	    rlks=`echo $mli_name1 | cut -d "_" -f 3 | cut -d "." -f 1`
	    mli_name=$scene"_"$polar"_"$rlks
	    full_slc_tab=$slc_name"_full_tab"
	    slc_crop_tab=$slc_name"_crop_tab"
	    burst_tab=$slc_name"_crop_burst_tab"

            # rename full SLCs and MLIs
	    slc=$slc_name.slc
	    slc_par=$slc.par
	    slc_bmp=$slc_name.bmp
	    slc1=$slc_name"_IW1.slc"
	    slc_par1=$slc1.par
	    tops_par1=$slc1.TOPS_par
	    slc2=$slc_name"_IW2.slc"
	    slc_par2=$slc2.par
	    tops_par2=$slc2.TOPS_par
	    slc3=$slc_name"_IW3.slc"
	    slc_par3=$slc3.par
	    tops_par3=$slc3.TOPS_par
	    slc_bmp1=$slc1.bmp
	    slc_bmp2=$slc2.bmp
	    slc_bmp3=$slc3.bmp
	    mli=$mli_name.mli
	    mli_par=$mli.par
	    rlks=`grep range_looks: $mli_par | cut -d ":" -f 2`
	    alks=`grep azimuth_looks: $mli_par | cut -d ":" -f 2`
	    full_slc=$slc_name"_full.slc"
	    full_slc_par=$full_slc.par
	    full_slc_bmp=$slc_name"_full.bmp"
	    full_slc1=$slc_name"_full_IW1.slc"
	    full_slc_par1=$full_slc1.par
	    full_tops_par1=$full_slc1.TOPS_par
	    full_slc2=$slc_name"_full_IW2.slc"
	    full_slc_par2=$full_slc2.par
	    full_tops_par2=$full_slc2.TOPS_par
	    full_slc3=$slc_name"_full_IW3.slc"
	    full_slc_par3=$full_slc3.par
	    full_tops_par3=$full_slc3.TOPS_par
	    full_slc_bmp1=$full_slc1.bmp
	    full_slc_bmp2=$full_slc2.bmp
	    full_slc_bmp3=$full_slc3.bmp
	    full_mli=$mli_name"_full.mli"
	    full_mli_par=$full_mli.par
	    mv -f $slc $full_slc
	    mv -f $slc_par $full_slc_par
	    mv -f $slc_bmp $full_slc_bmp
	    mv -f $slc1 $full_slc1
	    mv -f $slc_par1 $full_slc_par1
	    mv -f $tops_par1 $full_tops_par1
	    mv -f $slc2 $full_slc2
	    mv -f $slc_par2 $full_slc_par2
	    mv -f $tops_par2 $full_tops_par2
	    mv -f $slc3 $full_slc3
	    mv -f $slc_par3 $full_slc_par3
	    mv -f $tops_par3 $full_tops_par3
	    mv -f $slc_bmp1 $full_slc_bmp1
	    mv -f $slc_bmp2 $full_slc_bmp2
	    mv -f $slc_bmp3 $full_slc_bmp3
	    mv -f $mli $full_mli
	    mv -f $mli_par $full_mli_par

            # create tab file for full SLCs
	    echo $scene_dir/$full_slc1 $scene_dir/$full_slc_par1 $scene_dir/$full_tops_par1 > $full_slc_tab
	    echo $scene_dir/$full_slc2 $scene_dir/$full_slc_par2 $scene_dir/$full_tops_par2 >> $full_slc_tab
	    echo $scene_dir/$full_slc3 $scene_dir/$full_slc_par3 $scene_dir/$full_tops_par3 >> $full_slc_tab 

	    # create tab file for crop SLCs
	    echo $scene_dir/$slc1 $scene_dir/$slc_par1 $scene_dir/$tops_par1 > $slc_crop_tab
	    echo $scene_dir/$slc2 $scene_dir/$slc_par2 $scene_dir/$tops_par2 >> $slc_crop_tab
	    echo $scene_dir/$slc3 $scene_dir/$slc_par3 $scene_dir/$tops_par3 >> $slc_crop_tab 

            # use existing GAMMA script to determine subset burst tab
	    GM S1_BURST_tab $ref_slc_full_tab $full_slc_tab $burst_tab
	    rm -rf S1_BURST_tab.log

            # GAMMA program to crop scene to min scene
	    GM SLC_copy_S1_TOPS $full_slc_tab $slc_crop_tab $burst_tab 

            # Make quick-look image of bursts for each swath
	    for swath in 1 2 3; do
		bslc="slc$swath"
		bslc_par=${!bslc}.par
		bmp="slc_bmp$swath"
		width=`grep range_samples: $bslc_par | awk '{print $2}'`
		lines=`grep azimuth_lines: $bslc_par | awk '{print $2}'`
		GM rasSLC ${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bmp}
	    done

    	    # Create SLC mosaic from individual burst SLCs
	    GM SLC_mosaic_S1_TOPS $slc_crop_tab $slc $slc_par $rlks $alks  

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

            # Make quick-look image of subset SLC
	    width=`grep range_samples: $slc_par | awk '{print $2}'`
	    lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
	    GM rasSLC $slc $width 1 $lines 50 20 - - 1 0 0 $slc_bmp

            # Multi-look subset SLC
	    GM multi_look $slc $slc_par $mli $mli_par $slc_rlks $slc_alks 0

            # Check number of bursts and their corner coordinates and put into central file
	    burst_file=$scene_dir/slc_crop_burst_values.txt
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
	    done < $slc_crop_tab
	    rm -f temp1 temp2 temp3

            # Preview of subset SLC and bursts

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
	    psfile=$scene"_"$polar"_auto_crop_SLC.ps"
	    psbasemap $outline $range -Bnesw -K -P > $psfile
	    pstext $outline $range -F+cTL+f15p -O -K -P <<EOF >> $psfile
$project $track $scene $polar Auto Crop SLC
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
            #evince $scene"_"$polar"_auto_crop_SLC.pdf"

	    cp $scene"_"$polar"_auto_crop_SLC.pdf" $proj_dir/$track_dir/auto_crop_slc_pdfs

	    cd $slc_dir
	else
	    :
	fi
    done < $scene_list
}



if [ $ref_scene == "-" ]; then # ref scene not calculated
    CALC_REF_SCENE
    CROP_SLCS
else # ref scene provided
    CROP_SLCS
fi



