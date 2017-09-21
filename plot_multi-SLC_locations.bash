#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_multi-SLC_locations:  ID location of multiple SLCs to determing if     *"
    echo "*                            they belong on the same track.                   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*         [scene_list]  list of scenes (eg. scenes.list)                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "* author: Thomas Fuhrmann @ GA    21/10/2016, v1.1                            *"
    echo "*             added functionality to extract coordinates to file slc_coords   *"
    echo "*             if the file doesn't already exist                               *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_multi-SLC_locations.bash [proc_file] [scene_list]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

list=$2

proc_file=$1

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
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

# info needed for calculation of subset values
subset_info=$slc_dir/subset_info.txt
echo "Date         Latitude    Longitude  azimuth    range  az_spacing  rg_spacing  inc_angle" > $subset_info

if [ $sensor == RSAT2 ]; then
# no msp_par file for RSAT2 processing
# only centre lat/lon is output instead of an image
  while read file; do
    scene=$file
    scene_dir=$slc_dir/$scene
    slc_name=$scene"_"$polar
    ####
    # grep information on latitude and longitude and save into txt file to be used for offset calculations
    slc_par=$scene_dir"/"$slc_name".slc.par"
    lat=`grep center_latitude $slc_par | awk '{print $2}'`
    lon=`grep center_longitude $slc_par | awk '{print $2}'`
    az_lines=`grep azimuth_lines $slc_par | awk '{print $2}'`
    rg_samples=`grep range_samples $slc_par | awk '{print $2}'`
    az_spacing=`grep azimuth_pixel_spacing $slc_par | awk '{print $2}'`
    rg_spacing=`grep range_pixel_spacing $slc_par | awk '{print $2}'`
    inc=`grep incidence_angle $slc_par | awk '{print $2}'`

    # output to file
    printf "%8.8s  %11.6f  %11.6f  %7i  %7i  %10.6f  %10.6f  %9.4f\n" $scene $lat $lon $az_lines $rg_samples $az_spacing $rg_spacing $inc >> $subset_info
  done < $list

else
  # other sensors

  echo > polygons.txt
  echo > labels.txt
  echo > min_max_lat.txt
  echo > min_max_lon.txt

  poly=polygons.txt
  label=labels.txt
  # used to determine overall min and max coordinates for plotting:
  min_max_lat=min_max_lat.txt
  min_max_lon=min_max_lon.txt
  echo ">" >> $poly

  psfile=SLC_Locations.ps

  az_rg=$slc_dir/az_rg_pixels
  echo "Number of pixels in range and azimuth" > $az_rg

  # Extract coordinates for polygons and labels
  while read file; do
    scene=$file
    scene_dir=$slc_dir/$scene
    slc_name=$scene"_"$polar
    msp_par=$scene_dir"/p"$slc_name".slc.par"
    coords=$scene_dir/slc_coords

    if [ ! -e $coords ]; then
        ###########
        # added TF: extract the SLC coordinates, if slc_coords doesn't exist yet
        ###########
	grep map_coordinate_4 $msp_par | awk '{print $2, $3}' > $coords
        grep map_coordinate_2 $msp_par | awk '{print $2, $3}' >> $coords
        grep map_coordinate_1 $msp_par | awk '{print $2, $3}' >> $coords
        grep map_coordinate_3 $msp_par | awk '{print $2, $3}' >> $coords
        grep map_coordinate_5 $msp_par | awk '{print $2, $3}' >> $coords
	#echo "ERROR: SLC coordinates file does not exist!"
	#exit 1
    fi

    rg=`grep range_pixels: $msp_par | awk '{print $2}'`
    az=`grep azimuth_pixels: $msp_par | awk '{print $2}'`
    echo $scene $rg $az >> $az_rg

    # coordinates for scene
    s=`awk '{print $1}' $coords | sort -n | head -1 | awk '{print $1}'`
    n=`awk '{print $1}' $coords | sort -n | tail -1 | awk '{print $1}'`
    e=`awk '{print $2}' $coords | sort -n | tail -1 | awk '{print $1}'`
    w=`awk '{print $2}' $coords | sort -n | head -1 | awk '{print $1}'`
    #centre=`awk 'NR==5 {print $2, $1}' $coords` # centre point

    # populate polygons file (x,y) for each point
    echo $s > temp1
    echo $n > temp2
    echo $e > temp3
    echo $w > temp4
    paste temp3 temp2 >> $poly # E-N coord
    paste temp4 temp2 >> $poly # W-N coord
    paste temp4 temp1 >> $poly # W-S coord
    paste temp3 temp1 >> $poly # E-S coord
    echo ">" >> $poly

    # collect overall min and max coordinate values
    echo $s >> $min_max_lat
    echo $n >> $min_max_lat
    echo $e >> $min_max_lon
    echo $w >> $min_max_lon

    # populate labels file for each scene
    #echo $centre > temp5
    # TF: use W-N edge for the labeling of scenes
    label_loc=`echo $w $n`
    echo $label_loc > temp5
    #echo "10 0 1 0" > temp6
    echo $scene > temp7
    #paste temp5 temp6 temp7 >> $label
    paste temp5 temp7 >> $label

    ####
    # grep information on latitude and longitude and save into txt file to be used for offset calculations
    slc_par=$scene_dir"/"$slc_name".slc.par"
    lat=`grep center_latitude $slc_par | awk '{print $2}'`
    lon=`grep center_longitude $slc_par | awk '{print $2}'`
    az_lines=`grep azimuth_lines $slc_par | awk '{print $2}'`
    rg_samples=`grep range_samples $slc_par | awk '{print $2}'`
    az_spacing=`grep azimuth_pixel_spacing $slc_par | awk '{print $2}'`
    rg_spacing=`grep range_pixel_spacing $slc_par | awk '{print $2}'`
    inc=`grep incidence_angle $slc_par | awk '{print $2}'`

    # output to file
    printf "%8.8s  %11.6f  %11.6f  %7i  %7i  %10.6f  %10.6f  %9.4f\n" $scene $lat $lon $az_lines $rg_samples $az_spacing $rg_spacing $inc >> $subset_info
    ####

  done < $list

  #remove any blank lines in files
  sed '/^$/d' $poly > polygons2.txt
  sed '/^$/d' $label > labels2.txt
  sed '/^$/d' $min_max_lat > min_max_lat2.txt
  sed '/^$/d' $min_max_lon > min_max_lon2.txt


  # Extract minimum and maximum coordinate values for plot boundary
  s_org=`awk '{print $1}' min_max_lat2.txt | sort -n | head -1 | awk '{print $1}'`
  n_org=`awk '{print $1}' min_max_lat2.txt | sort -n | tail -1 | awk '{print $1}'`
  e_org=`awk '{print $1}' min_max_lon2.txt | sort -n | tail -1 | awk '{print $1}'`
  w_org=`awk '{print $1}' min_max_lon2.txt | sort -n | head -1 | awk '{print $1}'`
  val=0.2 # amount to add to create plot area

  # converts any exponential numbers to decimal
  s_temp=`printf "%f\n" $s_org`
  n_temp=`printf "%f\n" $n_org`
  e_temp=`printf "%f\n" $e_org`
  w_temp=`printf "%f\n" $w_org`
  val_temp=`printf "%f\n" $val`

  s=$(expr $s_org-$val | bc)
  n=$(expr $n_org+$val | bc)
  e=$(expr $e_org+$val | bc)
  w=$(expr $w_org-$val | bc)

  # Create plot
  bounds=-R$w/$e/$s/$n
  proj=-JM10
  layout=-P

  # set some GMT parameters
  gmtset MAP_FRAME_TYPE plain FONT_LABEL 16p MAP_FRAME_PEN 1.5p

  # add political boundaries and coastlines to map
  pscoast $bounds $proj -Dh -Bf0.5a2neSW $layout -Gyellowgreen -Sdodgerblue -K -N1 -Ia -W > $psfile

  # plot out SLC frames
  psxy polygons2.txt $bounds $proj $layout -L -W0.5p,red -L -K -O >> $psfile

  # label SLC frames
  #pstext labels2.txt $bounds $proj $layout -O -K >> $psfile
  pstext labels2.txt $bounds $proj $layout -F+jLT -O >> $psfile

  ## Plot list of epoch

  #awk '{print $1}' $1 > dates

  #epoch=$output"_"$sthr"m_"$2"yr_epoch_bperp.txt"

  #awk '{print $1}' $epoch | psxy -Y-11.5c $bounds $proj -G225,225,225 -W6,black -Sc0.42c -K -O -m >> $psfile
  #awk '{print 15.5, 20-NR*0.5, "7.5 0 1 MC", NR}' $epoch |  pstext $bounds $proj -Gblack -K -O >> $psfile
  #awk '{printf "%4.0f\n", $1}' $epoch | awk '{print 16.6, 20-NR*0.5, "9 0 1 MC", $1}' |  pstext $bounds $proj -Gblack -O >> $psfile

  ps2raster $psfile -A -Tf

  evince SLC_Locations.pdf

  mv -f SLC_Locations.pdf $slc_dir

  #cp labels2.txt labels3.txt

  rm -f $psfile temp* $poly $label $min_max_lat $min_max_lon polygons2.txt labels2.txt min_max_lat2.txt min_max_lon2.txt

fi # RSAT2 sensor switch




