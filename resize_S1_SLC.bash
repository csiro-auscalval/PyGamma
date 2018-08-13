#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* resize_S1_SLC: Resize stack of Sentinel-1 SLCs to a reference scene.        *"
    echo "*                This scene can be auto selected (ie. the smallest one) or    *"
    echo "*                manually selected.                                           *"
    echo "*                Ensures all SLCs have same size and shape to enable          *"
    echo "*                processing to continue.                                      *" 
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [scene]      scene ID (eg. 20180423)                                *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: resize_S1_SLC.bash [proc_file] [scene]"
    }

if [ $# -lt 2 ]
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

# file names
slc_file_names
s1_resize


cd $scene_dir

if [ $s1_resize_ref == "auto" ]; then # ref scene not calculated
    echo "Sentinel-1 resizing reference scene not specified in *.proc file. "
else
    if [ $scene == $s1_resize_ref ]; then
	:
    else
	slc_file_names
	mli_file_names
	s1_slc_file_names
	s1_resize

        # rename full SLCs
	mv -f $slc $full_slc
	mv -f $slc_par $full_slc_par
	mv -f $slc_png $full_slc_png
	mv -f $slc1 $full_slc1
	mv -f $slc_par1 $full_slc_par1
	mv -f $tops_par1 $full_tops_par1
	mv -f $slc2 $full_slc2
	mv -f $slc_par2 $full_slc_par2
	mv -f $tops_par2 $full_tops_par2
	mv -f $slc3 $full_slc3
	mv -f $slc_par3 $full_slc_par3
	mv -f $tops_par3 $full_tops_par3
	mv -f $slc_png1 $full_slc_png1
	mv -f $slc_png2 $full_slc_png2
	mv -f $slc_png3 $full_slc_png3

        # create tab file for full SLCs
	echo $full_slc1 $full_slc_par1 $full_tops_par1 > $full_slc_tab
	echo $full_slc2 $full_slc_par2 $full_tops_par2 >> $full_slc_tab
	echo $full_slc3 $full_slc_par3 $full_tops_par3 >> $full_slc_tab 

	# create tab file for resize SLCs
	echo $slc1 $slc_par1 $tops_par1 > $slc_resize_tab
	echo $slc2 $slc_par2 $tops_par2 >> $slc_resize_tab
	echo $slc3 $slc_par3 $tops_par3 >> $slc_resize_tab 

        # use existing GAMMA script to determine resize burst tab
	GM S1_BURST_tab $ref_slc_tab $full_slc_tab $burst_tab
	rm -rf S1_BURST_tab.log

        # GAMMA program to resize scene to ref scene
	GM SLC_copy_S1_TOPS $full_slc_tab $slc_resize_tab $burst_tab 

        # Make quick-look image of bursts for each swath
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

    	# Create SLC mosaic from individual burst SLCs
	GM SLC_mosaic_S1_TOPS $slc_resize_tab $slc $slc_par $rlks $alks  

        # Import precise orbit information (if available)
	if [ -e $raw_data_track_dir/$scene/*.EOF ]; then
	    GM S1_OPOD_vec $slc_par $raw_data_track_dir/$scene/*.EOF
	else 
	    :
	fi

	# Multi-look resized SLC
	GM multi_look $slc $slc_par $mli $mli_par $rlks $alks 0

        # Make quick-look image of resized SLC
	width=`grep range_samples: $slc_par | awk '{print $2}'`
	lines=`grep azimuth_lines: $slc_par | awk '{print $2}'`
	GM rasSLC $slc $width 1 $lines 50 20 - - 1 0 0 $slc_bmp
	GM convert $slc_bmp $slc_png
	rm -f $slc_bmp

	# Create PDF of resized SLC extent
	~/repo/gamma_insar/plot_S1_SLC_extent.bash $proc_file $scene resize
    fi
fi
# script end 
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2
