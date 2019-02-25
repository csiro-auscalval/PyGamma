#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_preview_pdfs:   Plot low res images of SLCs and interferograms for     *"
    echo  "*                     quick check of processing outputs.                     *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [type]       input type (full_slc, subset_slc, ifg)                 *"
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
    echo -e "Usage: plot_preview_pdfs.bash [proc_file] [type]"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
type=$2


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $frame 

######################################################################


cd $proj_dir/$track_dir


function plot_pdfs {
    local image_list=$1
    local header=$2
    local pdf_name=$3
 
    ## Split image_files into 36 image chunks
    num_imgs=`cat $image_list | sed '/^\s*$/d' | wc -l`
    split -dl 36 $image_list $image_list"_"
    mv $image_list "all_"$image_list
    echo $image_list"_"* > temp
    cat temp | tr " " "\n" > image_files.list
    rm -rf temp

    ## Plot images
    image_files=image_files.list
    while read list; do
	if [ ! -z $list ]; then
	    lines=($(cat $list))
	    img1=`echo ${lines[0]}`
	    name1=`echo $img1 | cut -d "/" -f 11`
	    img2=`echo ${lines[1]}`
	    name2=`echo $img2 | cut -d "/" -f 11`
	    img3=`echo ${lines[2]}`
	    name3=`echo $img3 | cut -d "/" -f 11`
	    img4=`echo ${lines[3]}`
	    name4=`echo $img4 | cut -d "/" -f 11`
	    img5=`echo ${lines[4]}`
	    name5=`echo $img5 | cut -d "/" -f 11`
	    img6=`echo ${lines[5]}`
	    name6=`echo $img6 | cut -d "/" -f 11`
	    img7=`echo ${lines[6]}`
	    name7=`echo $img7 | cut -d "/" -f 11`
	    img8=`echo ${lines[7]}`
	    name8=`echo $img8 | cut -d "/" -f 11`
	    img9=`echo ${lines[8]}`
	    name9=`echo $img9 | cut -d "/" -f 11`
	    img10=`echo ${lines[9]}`
	    name10=`echo $img10 | cut -d "/" -f 11`
	    img11=`echo ${lines[10]}`
	    name11=`echo $img11 | cut -d "/" -f 11`
	    img12=`echo ${lines[11]}`
	    name12=`echo $img12 | cut -d "/" -f 11`
	    img13=`echo ${lines[12]}`
	    name13=`echo $img13 | cut -d "/" -f 11`
	    img14=`echo ${lines[13]}`
	    name14=`echo $img14 | cut -d "/" -f 11`
	    img15=`echo ${lines[14]}`
	    name15=`echo $img15 | cut -d "/" -f 11`
	    img16=`echo ${lines[15]}`
	    name16=`echo $img16 | cut -d "/" -f 11`
	    img17=`echo ${lines[16]}`
	    name17=`echo $img17 | cut -d "/" -f 11`
	    img18=`echo ${lines[17]}`
	    name18=`echo $img18 | cut -d "/" -f 11`
	    img19=`echo ${lines[18]}`
	    name19=`echo $img19 | cut -d "/" -f 11`
	    img20=`echo ${lines[19]}`
	    name20=`echo $img20 | cut -d "/" -f 11`
	    img21=`echo ${lines[20]}`
	    name21=`echo $img21 | cut -d "/" -f 11`
	    img22=`echo ${lines[21]}`
	    name22=`echo $img22 | cut -d "/" -f 11`
	    img23=`echo ${lines[22]}`
	    name23=`echo $img23 | cut -d "/" -f 11`
	    img24=`echo ${lines[23]}`
	    name24=`echo $img24 | cut -d "/" -f 11`
	    img25=`echo ${lines[24]}`
	    name25=`echo $img25 | cut -d "/" -f 11`
	    img26=`echo ${lines[25]}`
	    name26=`echo $img26 | cut -d "/" -f 11`
	    img27=`echo ${lines[26]}`
	    name27=`echo $img27 | cut -d "/" -f 11`
	    img28=`echo ${lines[27]}`
	    name28=`echo $img28 | cut -d "/" -f 11`
	    img29=`echo ${lines[28]}`
	    name29=`echo $img29 | cut -d "/" -f 11`
	    img30=`echo ${lines[29]}`
	    name30=`echo $img30 | cut -d "/" -f 11`
	    img31=`echo ${lines[30]}`
	    name31=`echo $img31 | cut -d "/" -f 11`
	    img32=`echo ${lines[31]}`
	    name32=`echo $img32 | cut -d "/" -f 11`
	    img33=`echo ${lines[32]}`
	    name33=`echo $img33 | cut -d "/" -f 11`
	    img34=`echo ${lines[33]}`
	    name34=`echo $img34 | cut -d "/" -f 11`
	    img35=`echo ${lines[34]}`
	    name35=`echo $img35 | cut -d "/" -f 11`
	    img36=`echo ${lines[35]}`
	    name36=`echo $img36 | cut -d "/" -f 11`

	    gmtset PS_MEDIA A4
	    outline="-JX21c/29.7c"
	    range="-R0/100/0/10"
	    box="-W3c/4c -Fthin"
	    font="-F+f8p"

	    psfile=$list.ps

	    psbasemap $outline $range -X0c -Y-1c -Bnesw -P -K > $psfile

	    if [ -z $frame ]; then
	        pstext $outline $range -F+cTC+f15p -O -P -K <<EOF >> $psfile
$project $sensor $track $polar $header
EOF
            else
                pstext $outline $range -F+cTC+f15p -O -P -K <<EOF >> $psfile
$project $sensor $track $frame $polar $header
EOF
            fi
            # 1st row
	    psimage $img1 $box -C0.5c/24.1c -O -P -K >> $psfile # top left left corner
	    pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 9.515 $name1 
EOF
	    if [ -z $img2 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img2 $box -C3.9c/24.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 9.515 $name2
EOF
	    fi
	    if [ -z $img3 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img3 $box -C7.3c/24.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 9.515 $name3
EOF
	    fi
	    if [ -z $img4 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img4 $box -C10.7c/24.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 9.515 $name4
EOF
	    fi
	    if [ -z $img5 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img5 $box -C14.1c/24.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 9.515 $name5
EOF
	    fi
	    if [ -z $img6 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img6 $box -C17.5c/24.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 9.515 $name6
EOF
	    fi

            # 2nd row
	    if [ -z $img7 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img7 $box -C0.5c/19.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 8 $name7
EOF
	    fi
	    if [ -z $img8 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img8 $box -C3.9c/19.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 8 $name8
EOF
	    fi
	    if [ -z $img9 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img9 $box -C7.3c/19.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 8 $name9
EOF
	    fi
	    if [ -z $img10 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img10 $box -C10.7c/19.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 8 $name10
EOF
	    fi
	    if [ -z $img11 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img11 $box -C14.1c/19.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 8 $name11
EOF
	    fi
	    if [ -z $img12 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img12 $box -C17.5c/19.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 8 $name12
EOF
	    fi

            # 3rd row
	    if [ -z $img13 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img13 $box -C0.5c/15.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 6.485 $name13
EOF
	    fi
	    if [ -z $img14 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img14 $box -C3.9c/15.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 6.485 $name14
EOF
	    fi
	    if [ -z $img15 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img15 $box -C7.3c/15.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 6.485 $name15
EOF
	    fi
	    if [ -z $img16 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img16 $box -C10.7c/15.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 6.485 $name16
EOF
	    fi
	    if [ -z $img17 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img17 $box -C14.1c/15.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 6.485 $name17
EOF
	    fi
	    if [ -z $img18 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img18 $box -C17.5c/15.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 6.485 $name18
EOF
	    fi

            # 4th row
	    if [ -z $img19 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img19 $box -C0.5c/10.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 4.97 $name19
EOF
	    fi
	    if [ -z $img20 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img20 $box -C3.9c/10.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 4.97 $name20
EOF
	    fi
	    if [ -z $img21 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img21 $box -C7.3c/10.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 4.97 $name21
EOF
	    fi
	    if [ -z $img22 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img22 $box -C10.7c/10.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 4.97 $name22
EOF
	    fi
	    if [ -z $img23 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img23 $box -C14.1c/10.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 4.97 $name23
EOF
	    fi
	    if [ -z $img24 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img24 $box -C17.5c/10.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 4.97 $name24
EOF
	    fi

            # 5th row
	    if [ -z $img25 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img25 $box -C0.5c/6.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 3.455 $name25
EOF
	    fi
	    if [ -z $img26 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img26 $box -C3.9c/6.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 3.455 $name26
EOF
	    fi
	    if [ -z $img27 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img27 $box -C7.3c/6.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 3.455 $name27
EOF
	    fi
	    if [ -z $img28 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img28 $box -C10.7c/6.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 3.455 $name28
EOF
	    fi
	    if [ -z $img29 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img29 $box -C14.1c/6.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 3.455 $name29
EOF
	    fi
	    if [ -z $img30 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img30 $box -C17.5c/6.1c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 3.455 $name30
EOF
	    fi

# 6th row
	    if [ -z $img31 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img31 $box -C0.5c/1.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 1.94 $name31
EOF
	    fi
	    if [ -z $img32 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img32 $box -C3.9c/1.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 1.94 $name32
EOF
	    fi
	    if [ -z $img33 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img33 $box -C7.3c/1.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 1.94 $name33
EOF
	    fi
	    if [ -z $img34 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img34 $box -C10.7c/1.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 1.94 $name34
EOF
	    fi
	    if [ -z $img35 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img35 $box -C14.1c/1.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 1.94 $name35
EOF
	    fi
	    if [ -z $img36 ]; then
		: #do nothing if variable is empty
	    else
		psimage $img36 $box -C17.5c/1.6c/BL -O -P -K >> $psfile
		pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 1.94 $name36
EOF
	    fi

            # add page number
	    num=`echo $list | awk -F "_" '{print $3}' | bc`
	    num=`echo $num + 1 | bc`
	    pstext $outline $range $font -O -P <<EOF >> $psfile
50.025 0.5 $num
EOF

            # create PDF
	    ps2raster -Tf $psfile

    fi
done < $image_files

# Combine all PDFs into one PDF
ps2raster -TF -F$pdf_name *.pdf

mv $pdf_name.pdf $pdf_dir

# Clean up files
rm -rf $image_list*.ps $image_list*.pdf "all_"$image_list gmt.* $image_list"_"* image_files.list
}



# remove any existing file lists
rm -f *_slc_images *_ifg_images *_cc_images

if [ -z $frame ]; then
    prefix=$project"_"$sensor"_"$track"_"$polar
else
    prefix=$project"_"$sensor"_"$track"_"$frame"_"$polar
fi

if [ $type == 'slc' ]; then
    while read scene; do
	slc_file_names
	image=$slc_png
	echo $image >> slc_images
    done < $scene_list
    header="SLCs"
    pdf_name=$prefix"_SLCs"
    plot_pdfs slc_images $header $pdf_name
elif [ $type == 'subset_slc' ]; then
    while read scene; do
	slc_file_names
	image=$slc_png
	echo $image >> subset_slc_images
    done < $scene_list
    header="Subsetted_SLCs"
    pdf_name=$prefix"_subsetted_SLCs"
    plot_pdfs subset_slc_images $header $pdf_name

elif [ $type == 'ifg' ]; then
    while read ifg; do
	echo $ifg
	master=`echo $ifg | awk 'BEGIN {FS=","} ; {print $1}'`
	slave=`echo $ifg | awk 'BEGIN {FS=","} ; {print $2}'`
	ifg_file_names
	if [ -e $ifg_unw_geocode_png ]; then
	    echo $ifg_unw_geocode_png >> unw_ifg_images
	fi
	if [ -e $ifg_flat_geocode_png ]; then
	    echo $ifg_flat_geocode_png >> flat_ifg_images
	fi
	if [ -e $ifg_filt_geocode_png ]; then
	    echo $ifg_filt_geocode_png >> filt_ifg_images
	fi
	if [ -e $ifg_flat_cc_geocode_png ]; then
	    echo $ifg_flat_cc_geocode_png >> flat_cc_images
	fi
	if [ -e $ifg_filt_cc_geocode_png ]; then
	    echo $ifg_filt_cc_geocode_png >> filt_cc_images
	fi
    done < $ifg_list
    if [ -e unw_ifg_images ]; then
	header="Unwrapped_Ifgs"
	pdf_name=$prefix"_"$rlks"rlks_unw_ifgs"
	plot_pdfs unw_ifg_images $header $pdf_name
    fi
    if [ -e flat_ifg_images ]; then
	header="Flattened_Ifgs"
	pdf_name=$prefix"_"$rlks"rlks_flat_ifgs"
	plot_pdfs flat_ifg_images $header $pdf_name
    fi
    if [ -e filt_ifg_images ]; then
	header="Filtered_Ifgs"
	pdf_name=$prefix"_"$rlks"rlks_filt_ifgs"
	plot_pdfs filt_ifg_images $header $pdf_name
    fi
    if [ -e flat_cc_images ]; then
	header="Flattened_Coherence"
	pdf_name=$prefix"_"$rlks"rlks_flat_cc"
	plot_pdfs flat_cc_images $header $pdf_name
    fi
    if [ -e filt_cc_images ]; then
	header="Filtered_Coherence"
	pdf_name=$prefix"_"$rlks"rlks_filt_cc"
	plot_pdfs filt_cc_images $header $pdf_name
    fi
else
    echo "type not recognised"
fi


# script end 
####################












