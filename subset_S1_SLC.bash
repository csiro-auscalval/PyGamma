#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* subset_S1_SLC: Script takes full SLCs produced by 'process_S1_SLC.bash'     *"
    echo "*                and subsets them based on the burst numbers in the burst     *"
    echo "*                list.                                                        *"
    echo "*                                                                             *"
    echo "*        Format of burst list: scene, swath#, burst_start, burst_end, eg:     *"
    echo "*                    20160601 1 5 10                                          *"
    echo "*                    20160601 2 6 11                                          *" 
    echo "*                    20160601 3 4 9                                           *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20070112)                                *"
    echo "*         [rlks]       MLI range looks                                        *"
    echo "*         [alks]       MLI azimuth looks                                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       28/07/2016, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: subset_S1_SLC.bash [proc_file] [scene] [rlks] [alks]"
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

slc_rlks=$3
slc_alks=$4

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

burst_list=$proj_dir/$track_dir/lists/`grep List_of_s1_bursts= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir

mkdir -p subset_slc_pdfs

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

cd $scene_dir

## File names
slc_name=$scene"_"$polar
mli_name=$scene"_"$polar"_"$slc_rlks"rlks"
#para=$slc_name"_SLC_parameters.txt"
slc=$slc_name.slc
slc_par=$slc.par
slc_bmp=$slc_name.bmp
slc_full=$slc_name"_full.slc"
slc_full_par=$slc_full.par
slc_full_bmp=$slc_full.bmp
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
slc_full1=$slc_name"_IW1_full.slc"
slc_full_par1=$slc_full1.par
tops_full_par1=$slc_full1.TOPS_par
slc_full_bmp1=$slc_full1.bmp
slc2=$slc_name"_IW2.slc"
slc_par2=$slc2.par
tops_par2=$slc2.TOPS_par
slc_bmp2=$slc2.bmp
slc2_1=$slc_name"_IW2_1.slc"
slc_par2_1=$slc2_1.par
tops_par2_1=$slc2_1.TOPS_par
slc_full2=$slc_name"_IW2_full.slc"
slc_full_par2=$slc_full2.par
tops_full_par2=$slc_full2.TOPS_par
slc_full_bmp2=$slc_full2.bmp
slc3=$slc_name"_IW3.slc"
slc_par3=$slc3.par
tops_par3=$slc3.TOPS_par
slc_bmp3=$slc3.bmp
slc3_1=$slc_name"_IW3_1.slc"
slc_par3_1=$slc3_1.par
tops_par3_1=$slc3_1.TOPS_par
slc_full3=$slc_name"_IW3_full.slc"
slc_full_par3=$slc_full3.par
tops_full_par3=$slc_full3.TOPS_par
slc_full_bmp3=$slc_full3.bmp
mli=$mli_name.mli
mli_par=$mli.par
mli_full=$mli_name"_full.mli"
mli_full_par=$mli_full.par



## Subset SLC by bursts (cannot subset by pixels for Sentinel-1)
echo " "
echo "Subsetting SLC..."
echo " "
rm -f sub_slc_tab slc_tab_full slc_in slc_out burst_tab

# Create burst tab file
sed -n "/$scene/p" $burst_list > temp1
awk '{print $3"\t"$4}' temp1 > burst_tab


# Setup file names
while read burst; do
    burst_scene=`echo $burst | awk '{print $1}'`
    burst_swath=`echo $burst | awk '{print $2}'`
    start_burst=`echo $burst | awk '{print $3}'`
    end_burst=`echo $burst | awk '{print $4}'`
    for swath in $burst_swath
    do
	sub_slc1=$slc_name"_IW1_B"$start_burst"-"$end_burst.slc
	sub_slc_par1=$sub_slc1.par
	sub_tops_par1=$sub_slc1.TOPS_par
	sub_slc2=$slc_name"_IW2_B"$start_burst"-"$end_burst.slc
	sub_slc_par2=$sub_slc2.par
	sub_tops_par2=$sub_slc2.TOPS_par
	sub_slc3=$slc_name"_IW3_B"$start_burst"-"$end_burst.slc
	sub_slc_par3=$sub_slc3.par
	sub_tops_par3=$sub_slc3.TOPS_par
	bslc="slc$swath"
	bslc_par=${!bslc}.par
	btops="tops_par$swath"
	bmp="slc_bmp$swath"
	fslc="slc_full$swath"
	fslc_par=${!fslc}.par
	ftops="tops_full_par$swath"
	fbmp="slc_full_bmp$swath"
	sub_slc="sub_slc$swath"
	sub_slc_par=${!sub_slc}.par
	sub_tops="sub_tops_par$swath"
	sub_bmp="sub_slc_bmp$swath"

	echo $scene_dir/${!bslc} $scene_dir/$bslc_par $scene_dir/${!btops} >> slc_in
	echo $scene_dir/${!sub_slc} $scene_dir/$sub_slc_par $scene_dir/${!sub_tops} >> slc_out 
	echo $scene_dir/${!fslc} $scene_dir/$fslc_par $scene_dir/${!ftops} >> slc_tab_full
    done
done < temp1
rm -f temp1

# Copy bursts
GM SLC_copy_S1_TOPS slc_in slc_out burst_tab 0

# Rename full slc files
awk '{print $1}' slc_in > temp1
awk '{print $1}' slc_tab_full > temp2
paste temp1 temp2 > rename1
while read file1; do
    in_file=`echo $file1 | awk '{print $1}'`
    out_file=`echo $file1 | awk '{print $2}'`
    mv -f $in_file $out_file
    mv -f $in_file.bmp $out_file.bmp
done < rename1

awk '{print $2}' slc_in > temp1
awk '{print $2}' slc_tab_full > temp2
paste temp1 temp2 > rename2
while read file1; do
    in_file=`echo $file1 | awk '{print $1}'`
    out_file=`echo $file1 | awk '{print $2}'`
    mv -f $in_file $out_file
done < rename2

awk '{print $3}' slc_in > temp1
awk '{print $3}' slc_tab_full > temp2
paste temp1 temp2 > rename3
while read file1; do
    in_file=`echo $file1 | awk '{print $1}'`
    out_file=`echo $file1 | awk '{print $2}'`
    mv -f $in_file $out_file
done < rename3
rm -f temp1 temp2 rename*

mv -f $slc $slc_full
mv -f $slc_par $slc_full_par
mv -f $slc_bmp $slc_full_bmp
mv -f $mli $mli_full
mv -f $mli_par $mli_full_par

# Rename subset slc files
awk '{print $1}' slc_out > temp1
awk '{print $1}' slc_in > temp2
paste temp1 temp2 > rename1
while read file1; do
    in_file=`echo $file1 | awk '{print $1}'`
    out_file=`echo $file1 | awk '{print $2}'`
    mv -f $in_file $out_file
done < rename1

awk '{print $2}' slc_out > temp1
awk '{print $2}' slc_in > temp2
paste temp1 temp2 > rename2
while read file1; do
    in_file=`echo $file1 | awk '{print $1}'`
    out_file=`echo $file1 | awk '{print $2}'`
    mv -f $in_file $out_file
done < rename2

awk '{print $3}' slc_out > temp1
awk '{print $3}' slc_in > temp2
paste temp1 temp2 > rename3
while read file1; do
    in_file=`echo $file1 | awk '{print $1}'`
    out_file=`echo $file1 | awk '{print $2}'`
    mv -f $in_file $out_file
done < rename3
rm -f temp1 temp2 rename*

    # Make quick-look image for subset bursts
for swath in 1 2 3; do
    bslc="slc$swath"
    bslc_par=${!bslc}.par
    bmp="slc_bmp$swath"
    width=`grep range_samples: $bslc_par | awk '{print $2}'`
    lines=`grep azimuth_lines: $bslc_par | awk '{print $2}'`
    GM rasSLC ${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bmp}
done
rm -f slc_in slc_out slc_tab_full

# Make the SLC mosaic from individual burst SLCs
GM SLC_mosaic_S1_TOPS slc_tab $slc $slc_par $slc_rlks $slc_alks  

# Make quick-look image of subset SLC
width=`grep range_samples: $slc_par | awk '{print $2}'`
lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
GM rasSLC $slc $width 1 $lines 50 10 - - 1 0 0 $slc_bmp

# Multi-look subset SLC
GM multi_look $slc $slc_par $mli $mli_par $slc_rlks $slc_alks 0


# Preview of subset SLC and bursts
burst_file=$scene_dir/slc_subset_burst_values.txt
echo "Number of Bursts per Swath" > $burst_file
echo " " >> $burst_file

# check number of bursts and their corner coordinates and put into central file
while read file; do
    par=`echo $file | awk '{print $2}'`
    tops=`echo $file | awk '{print $3}'`

    SLC_burst_corners $par $tops > temp1

    swath=`awk 'NR==7 {print $6}' temp1`
    echo "Swath: "$swath >> $burst_file
    bursts=`awk 'NR==8 {print $7}' temp1`
    echo "   total bursts: "$bursts >> $burst_file
    echo "Num     Upper_Right                      Upper_left                      Lower_Left                     Lower_Right" >> $burst_file
    tail -n +10 temp1 > temp2
    head -n -9 temp2 > temp3
    awk '{print $2"\t"$3" "$4"\t"$5" "$6"\t"$7" "$8"\t"$9" "$10}' temp3 >> $burst_file
    echo " " >> $burst_file
done < slc_tab
rm -f temp1 temp2 temp3

# number of bursts per swath
sed -n '/Swath: IW1/,/Num/p' $burst_file > temp1
sw1_burst=`awk 'NR==2 {print}' temp1 | awk '{print $3}'`
sed -n '/Swath: IW2/,/Num/p' $burst_file > temp1
sw2_burst=`awk 'NR==2 {print}' temp1 | awk '{print $3}'`
sed -n '/Swath: IW3/,/Num/p' $burst_file > temp1
sw3_burst=`awk 'NR==2 {print}' temp1 | awk '{print $3}'`

# swath stop times
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
psfile=$scene"_"$polar"_subset_SLC.ps"
psbasemap $outline $range -Bnesw -K -P > $psfile
pstext $outline $range -F+cTL+f15p -O -K -P <<EOF >> $psfile
$project $track $scene $polar Subset SLC
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
#evince $scene"_"$polar"_subset_SLC.pdf"

cp $scene"_"$polar"_subset_SLC.pdf" $proj_dir/$track_dir/subset_slc_pdfs



# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
   cat error.log 1>&2
   rm temp_log
else
   rm temp_log
fi
