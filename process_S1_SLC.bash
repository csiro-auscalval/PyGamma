#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_S1_SLC: Script takes SLC format Sentinel-1 Interferometric Wide     *"
    echo "*                 Swath data and mosaics the three sub-swathes into a single  *"
    echo "*                 SLC, and subsets SLC by bursts after full SLC creation.     *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20180423)                                *"
    echo "*         [option]     processing type ('slc' for creating SLC, or 'subset'   *"
    echo "*                      for subsetting SLC by bursts)                          *"
    echo "*                                                                             *"
    echo "*    Format of burst list: scene, swath#, burst_start, burst_end, eg:         *"
    echo "*                   20180423 1 5 10                                           *"
    echo "*                   20180423 2 6 11                                           *"
    echo "*                   20180423 3 4 9                                            *"
    echo "*                                                                             *"
    echo "* author: Matt Garthwaite @ GA    11/05/2015, v1.0                            *"
    echo "*         Negin Moghaddam @ GA    13/05/2016, v1.1                            *"
    echo "*         Add the phase_shift function to apply on IW1 of the image before    *"
    echo "*         mid-March 2015                                                      *"
    echo "*         Sarah Lawrie @ GA       28/07/2016, v1.2                            *"
    echo "*         Add concatenation of consecutive burst SLCs (join 2 or 3 frames)    *"
    echo "*         Add use of precise orbit information                                *"
    echo "*         Sarah Lawrie @ GA       08/09/2017, v1.3                            *"
    echo "*         Update burst tabs to enable auto subset of scenes                   *"
    echo "*         Sarah Lawrie @ GA       13/08/2018, v2.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: process_S1_SLC.bash [proc_file] [scene] [option]"
    }

if [ $# -lt 3 ]
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
type=$3


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $scene 

######################################################################

## File names
slc_file_names
s1_slc_file_names
mli_file_names


pol=`echo $polar | tr '[:upper:]' '[:lower:]'`

mkdir -p $scene_dir
cd $scene_dir


## FUNCTIONS 

# Get list of full SLCs 
function slc_list {
    echo $slc1 $slc_par1 $tops_par1 > $slc_tab
    echo $slc2 $slc_par2 $tops_par2 >> $slc_tab
    echo $slc3 $slc_par3 $tops_par3 >> $slc_tab 
}

# create SLC par file  (three frames maximum)
function read_raw_data {
    while read frame_num; do
	if [ ! -z "$frame_num" ]; then
	    date=`echo $frame_num | awk '{print $1}'`
	    if [ "$date" -eq "$scene" ]; then
		tot_frame=`echo $frame_num | awk '{print $2}'`
		i=1
		if [ $tot_frame -eq 1 ]; then # single frame, no concatenation
		    for swath in 1 2 3; do
			echo " "
			echo "Processing swath "$swath" for SLC "$scene
			echo " "
			annot=`ls $raw_data_track_dir/F$i/$scene/*$scene*/annotation/s1*-iw$swath-slc-$pol*.xml`
			data=`ls $raw_data_track_dir/F$i/$scene/*$scene*/measurement/s1*-iw$swath-slc-$pol*.tiff`
			calib=`ls $raw_data_track_dir/F$i/$scene/*$scene*/annotation/calibration/calibration-s1*-iw$swath-slc-$pol*.xml`
			noise=`ls $raw_data_track_dir/F$i/$scene/*$scene*/annotation/calibration/noise-s1*-iw$swath-slc-$pol*.xml`
			bslc="slc$swath"
			bslc_par=${!bslc}.par
			btops="tops_par$swath"
			GM par_S1_SLC $data $annot $calib $noise $bslc_par ${!bslc} ${!btops} 0 60.0000 -
		    done 
		else # multiple frames
		    while [ "$i" -le "$tot_frame" ]; do
			for swath in 1 2 3; do
			    s1_slc_file_names
			    echo " "
			    echo "Processing swath "$swath" for frame "$i", SLC "$scene
			    echo " "
			    annot=`ls $raw_data_track_dir/F$i/$scene/*$scene*/annotation/s1*-iw$swath-slc-$pol*.xml`
			    data=`ls $raw_data_track_dir/F$i/$scene/*$scene*/measurement/s1*-iw$swath-slc-$pol*.tiff`
			    calib=`ls $raw_data_track_dir/F$i/$scene/*$scene*/annotation/calibration/calibration-s1*-iw$swath-slc-$pol*.xml`
			    noise=`ls $raw_data_track_dir/F$i/$scene/*$scene*/annotation/calibration/noise-s1*-iw$swath-slc-$pol*.xml`
			    bslc="fr_slc$swath"
			    bslc_par=${!bslc}.par
			    btops="fr_tops_par$swath"
			    GM par_S1_SLC $data $annot $calib $noise $bslc_par ${!bslc} ${!btops} 0 60.0000 -

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
}

# concatenate multi-frames (three frames maximum)
function concat {
    echo " "
    echo "Concatenate frames to produce SLC bursts ..."
    echo " "
    while read frame_num; do
	if [ ! -z "$frame_num" ]; then
	    date=`echo $frame_num | awk '{print $1}'`
	    if [ "$date" -eq "$scene" ]; then
		tot_frame=`echo $frame_num | awk '{print $2}'`
		if [ $tot_frame -eq 1 ]; then # single frame, no concatenation
		    :
		elif [ $tot_frame -eq 2 ]; then # 2 frames
		    paste slc_list par_list tops_list > lists
		    head -n 3 lists > fr_tab1
		    tail -3 lists > fr_tab2	
		    GM SLC_cat_S1_TOPS fr_tab1 fr_tab2 $slc_tab
		elif [ $tot_frame -eq 3 ]; then # 3 frames
		    paste slc_list par_list tops_list > lists
		    echo $slc1_1 $slc_par1_1 $tops_par1_1 > slc1_tab
		    echo $slc2_1 $slc_par2_1 $tops_par2_1 >> slc1_tab
		    echo $slc3_1 $slc_par3_1 $tops_par3_1 >> slc1_tab
		    head -n 3 lists > fr_tab1
		    tail -n +4 lists | head -3 > fr_tab2
		    tail -3 lists > fr_tab3
		    GM SLC_cat_S1_TOPS fr_tab1 fr_tab2 slc1_tab
		    GM SLC_cat_S1_TOPS slc1_tab fr_tab3 $slc_tab 
		else
		    echo "script can only concatenate up to 3 frames"   
		fi
                # remove frame slc files
		if [ -e slc_list ]; then
		    paste slc_list > to_remove
		    paste par_list >> to_remove
		    paste tops_list >> to_remove
		    if [ -e slc1_tab ]; then
			cat slc1_tab | awk '{print $1}' > temp1
			cat slc1_tab | awk '{print $2}' >> temp1
			cat slc1_tab | awk '{print $3}' >> temp1
			paste temp1 >> to_remove
		    fi
		    while read remove; do
			rm -f $remove
		    done < to_remove
		fi
	    fi
	fi
    done < $frame_list
    rm -f slc_list par_list tops_list lists fr_tab1 fr_tab2 fr_tab3 to_remove slc1_tab temp1
}

# Make quick-look png image of bursts for each swath
function burst_images {
    for swath in 1 2 3; do
	bslc="slc$swath"
	bslc_par=${!bslc}.par
	bmp="slc_bmp$swath"
	width=`grep range_samples: $bslc_par | awk '{print $2}'`
	lines=`grep azimuth_lines: $bslc_par | awk '{print $2}'`
	GM rasSLC ${!bslc} $width 1 $lines 50 10 - - 1 0 0 ${!bmp}
	GM convert ${!bmp} ${!bslc/.bmp}.png
	rm -f ${!bmp}
    done
}

# Phase shift for IW1 of the image before 15th of March 2015
function phase_shift {
    if [ $scene -lt 20150310 ]; then 
	GM SLC_phase_shift $slc1 $slc_par1 $slc1s $slc_par1s -1.25
	cp $tops_par1 $tops_par1s
        # rename original slc files to 'pre_shift' and rename new slcs back to original filenames
	mv $slc1 $slc_pre1
	mv $slc_par1 $slc_pre_par1
	mv $tops_par1 $tops_pre_par1
	mv $slc1s $slc1
	mv $slc_par1s $slc_par1
	mv $tops_par1s $tops_par1
    else
	:
    fi 
}

# Create SLC mosaic from individual burst SLCs
function mosaic_slc {
    if [ $type == 'slc' ]; then
        # needs rlks and alks, but these aren't calculated until after initial SLC creation, temporary values allocated for this program
	GM SLC_mosaic_S1_TOPS $slc_tab $slc $slc_par 12 2
    elif [ $type == 'subset' ]; then
	GM SLC_mosaic_S1_TOPS $slc_tab $slc $slc_par $rlks $alks  
    else
	:
    fi
}

# Import precise orbit information (if available)
function orbits {
    if [ -e $raw_data_track_dir/$scene/*.EOF ]; then
	GM S1_OPOD_vec $slc_par $raw_data_track_dir/$scene/*.EOF
    else 
	:
    fi
}

# Make quick-look png image of SLC
function slc_image {
    width=`grep range_samples: $slc_par | awk '{print $2}'`
    lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
    GM rasSLC $slc $width 1 $lines 50 20 - - 1 0 0 $slc_bmp
    GM convert $slc_bmp ${slc_bmp/.bmp}.png
    rm -f $slc_bmp
}

# subset full SLC
function subset_full_slc {
    rm -f slc_tab_pre-subset slc_in slc_out burst_tab

    # Create burst tab file
    sed -n "/$scene/p" $s1_burst_list > temp1
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
	    fslc="slc_pre_sub$swath"
	    fslc_par=${!fslc}.par
	    ftops="tops_pre_sub_par$swath"
	    fbmp="slc_pre_sub_bmp$swath"
	    sub_slc="sub_slc$swath"
	    sub_slc_par=${!sub_slc}.par
	    sub_tops="sub_tops_par$swath"
	    sub_bmp="sub_slc_bmp$swath"

	    echo ${!bslc} $bslc_par ${!btops} >> slc_in
	    echo ${!sub_slc} $sub_slc_par ${!sub_tops} >> slc_out 
	    echo ${!fslc} $fslc_par ${!ftops} >> slc_tab_pre-subset
	done
    done < temp1
    rm -f temp1

    # Copy bursts
    GM SLC_copy_S1_TOPS slc_in slc_out burst_tab 0

    # Rename full SLC files
    awk '{print $1}' slc_in > temp1
    awk '{print $1}' slc_tab_pre-subset > temp2
    paste temp1 temp2 > rename1
    while read file1; do
	in_file=`echo $file1 | awk '{print $1}'`
	out_file=`echo $file1 | awk '{print $2}'`
	mv -f $in_file $out_file
	mv -f $in_file.png $out_file.png
    done < rename1

    awk '{print $2}' slc_in > temp1
    awk '{print $2}' slc_tab_pre-subset > temp2
    paste temp1 temp2 > rename2
    while read file1; do
	in_file=`echo $file1 | awk '{print $1}'`
	out_file=`echo $file1 | awk '{print $2}'`
	mv -f $in_file $out_file
    done < rename2

    awk '{print $3}' slc_in > temp1
    awk '{print $3}' slc_tab_pre-subset > temp2
    paste temp1 temp2 > rename3
    while read file1; do
	in_file=`echo $file1 | awk '{print $1}'`
	out_file=`echo $file1 | awk '{print $2}'`
	mv -f $in_file $out_file
    done < rename3
    rm -f temp1 temp2 rename*

    mv -f $slc $slc_pre_sub
    mv -f $slc_par $slc_pre_sub_par
    mv -f $slc_png $slc_pre_sub_png

    # Rename subset SLC files
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

    rm -f slc_tab_pre-subset slc_in slc_out burst_tab
}

# Multi-look subsetted SLC
function ml_subset {
    GM multi_look $slc $slc_par $mli $mli_par $rlks $alks 0
}


if [ $type == 'slc' ]; then
    if [ ! -e $scene_dir/$slc ]; then
	echo " "
	echo "Creating SLC..."
	echo " "
	slc_list 
	read_raw_data
	concat
	burst_images
	phase_shift
	mosaic_slc
	orbits
	slc_image
	~/repo/gamma_insar/plot_S1_SLC_extent.bash $proc_file $scene slc 
	echo " "
	echo "Full SLC created."
	echo " "
    else
	echo " "
	echo "Full SLC already created."
	echo " "
    fi
elif [ $type == 'subset' ]; then     
    echo " "
    echo "Subsetting SLC..."
    echo " "
    slc_list
    subset_full_slc
    burst_images
    mosaic_slc
    slc_image
    ml_subset
    ~/repo/gamma_insar/plot_S1_SLC_extent.bash $proc_file $scene subset
    echo " "
    echo "Subsetting Sentinel-1 SLC by bursts completed."
    echo " "
else
    echo "Option not recognised, check details and re-run script."
fi
# script end 
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2



