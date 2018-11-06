#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_lat_lon:   calculate latitude and longitude for each SAR pixel         *"
    echo "*                 needed for the usage of GAMMA interferograms in StaMPS      *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA    21/07/2016, v1.0                            *"
    echo "*                                 07/02/2017, v1.1                            *"
    echo "*         TF: coordinate correction using full polynomial                     *"
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
    echo -e "Usage: calc_lat_lon.bash [proc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1
<<<<<<< HEAD:calc_lat_lon.bash
=======
beam=

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
echo $sensor
if [ $sensor == S1 ]; then
    platform=NCI
else
    platform=`grep Platform= $proc_file | cut -d "=" -f 2`
fi
mode=`grep Sensor_mode= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
if [ $sensor == S1 ]; then
    rlks=`grep Range_looks= $proc_file | cut -d "=" -f 2`
else
    slc_looks=`grep SLC_multi_look= $proc_file | cut -d "=" -f 2`
    rlks=$slc_looks
fi


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi
>>>>>>> remotes/origin/develop:general_scripts/calc_lat_lon.bash

##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track 

######################################################################

<<<<<<< HEAD:calc_lat_lon.bash
## File names
dem_master_names
dem_file_names
=======
## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi
>>>>>>> remotes/origin/develop:general_scripts/calc_lat_lon.bash


cd $dem_dir

if [ -e $lat_lon_pix ]; then
   rm -f $lat_lon_pix
fi


# grep the posting in lat and lon, half posting to be added to offset (pixel centre)
postlat=`grep post_lat: $dem_par | awk '{print $2}'`
postlon=`grep post_lon: $dem_par | awk '{print $2}'`
post_lat=`echo ${postlat} | sed -e 's/[eE]+*/\\*10\\^/'`
post_lon=`echo ${postlon} | sed -e 's/[eE]+*/\\*10\\^/'`

# get width and length of the coregistered master scene
master_width=`grep range_samples: $r_dem_master_mli_par | awk '{print $2}'`
master_length=`grep azimuth_lines: $r_dem_master_mli_par | awk '{print $2}'`

#####
# get the azimuth and range offset values and transform to lat/lon offset
echo "Calculation of lat/lon offset of master w.r.t. DEM"
echo " "
#####
# has to be checked what to do in case of a manual offset
# manual offset
    dem_offset1=`echo $dem_noffset | awk '{print $1}'`
    if [ $dem_offset1 -eq 0 ]; then
	dem_off1=0
    else
	dem_off1=`echo "scale=10 ; $dem_offset1/$rlks" | bc -l`
    fi
    dem_offset2=`echo $dem_noffset | awk '{print $2}'`
    if [ $dem_offset2 -eq 0 ]; then
	dem_off2=0
    else
	dem_off2=`echo "scale=10 ; $dem_offset2/$alks" | bc -l`
    fi
    echo "manual offset in range, azimuth: "$dem_off1", "$dem_off2"."
    echo " "
# polynomial offset coefficients
az_off=`grep azimuth_offset_polynomial: $dem_diff | awk '{print $2}'`
rg_off=`grep range_offset_polynomial: $dem_diff | awk '{print $2}'`
az_offset=`echo "scale=10 ; $dem_off2+$az_off" | bc -l`
rg_offset=`echo "scale=10 ; $dem_off1+$rg_off" | bc -l`
# has to be checked if the manual offset should be added to the offset polynomial
az_poly1=`grep azimuth_offset_polynomial: $dem_diff | awk '{print $3}'`
rg_poly1=`grep range_offset_polynomial: $dem_diff | awk '{print $3}'`
az_pol1=`echo ${az_poly1} | sed -e 's/[eE]+*/\\*10\\^/'`
rg_pol1=`echo ${rg_poly1} | sed -e 's/[eE]+*/\\*10\\^/'`
az_poly2=`grep azimuth_offset_polynomial: $dem_diff | awk '{print $4}'`
rg_poly2=`grep range_offset_polynomial: $dem_diff | awk '{print $4}'`
az_pol2=`echo ${az_poly2} | sed -e 's/[eE]+*/\\*10\\^/'`
rg_pol2=`echo ${rg_poly2} | sed -e 's/[eE]+*/\\*10\\^/'`
az_poly3=`grep azimuth_offset_polynomial: $dem_diff | awk '{print $5}'`
rg_poly3=`grep range_offset_polynomial: $dem_diff | awk '{print $5}'`
az_pol3=`echo ${az_poly3} | sed -e 's/[eE]+*/\\*10\\^/'`
rg_pol3=`echo ${rg_poly3} | sed -e 's/[eE]+*/\\*10\\^/'`
az_spacing=`grep az_pixel_spacing_1: $dem_diff | awk '{print $2}'`
rg_spacing=`grep range_pixel_spacing_1: $dem_diff | awk '{print $2}'`
az_spacing=`echo ${az_spacing} | sed -e 's/[eE]+*/\\*10\\^/'`
rg_spacing=`echo ${rg_spacing} | sed -e 's/[eE]+*/\\*10\\^/'`


# Constants
pi=3.1415926535
a=6378137
f=0.0033528107

# incidence angle needed to convert slant range to ground range
inc=`grep incidence_angle: $r_dem_master_mli_par | awk '{print $2}'`
# heading for rotation of az/rg geometry into lat/lon
heading=`grep heading: $r_dem_master_mli_par | awk '{print $2}'`

# centre latitude needed to convert metric into lat/lon
centre_lat=`grep center_latitude: $r_dem_master_mli_par | awk '{print $2}'`

# calculate metric offset from ground spacings
rg_gr_spacing=`echo "scale=10 ; $rg_spacing/s($inc/180*$pi)" | bc -l`
# metric offset
az_off_m=`echo "scale=10 ; $az_offset*$az_spacing" | bc -l`
rg_off_m=`echo "scale=10 ; $rg_offset*$rg_gr_spacing" | bc -l`
echo "Offset between DEM and Master scene is "
echo $az_off_m" m in azimuth direction and"
echo $rg_off_m" m in range direction"
echo " "

# convert metric azimuth/range offset to metric lat/lon offset (rotation)
# DEM has been shifted on the Master, hence we have to reverse this translation using negative offsets!
lon_off_m=`echo "scale=10 ; -1*($rg_off_m*c($heading/180*$pi)+$az_off_m*s($heading/180*$pi))" | bc -l`
lat_off_m=`echo "scale=10 ; -1*(-1*$rg_off_m*s($heading/180*$pi)+$az_off_m*c($heading/180*$pi))" | bc -l`
echo "Metric offset in latitude and longitude to be added to coordinate:"
echo "Latitude:  "$lat_off_m" m"
echo "Longitude: "$lon_off_m" m"
echo " "

# Convert metric to lat/lon using the centre lat/lon values of the master
e2=`echo "scale=10 ; 1/(1-$f)^2-1" | bc -l`
c=`echo "scale=10 ; $a*sqrt(1+$e2)" | bc -l`
V=`echo "scale=10 ; sqrt((1+($e2*c($centre_lat/180*$pi)^2)))" | bc -l`
N=`echo "scale=10 ; $c/$V" | bc -l`
M=`echo "scale=10 ; $c/($V^3)" | bc -l`
lat_off=`echo "scale=10 ; 180/$pi*$lat_off_m/(sqrt($M*$N))" | bc -l`
lon_off=`echo "scale=10 ; 180/$pi*$lon_off_m/(c($centre_lat/180*$pi)*sqrt($M*$N))" | bc -l`
echo "Offset in latitude and longitude to be added to coordinate:"
echo "Latitude:  "$lat_off" degree"
echo "Longitude: "$lon_off" degree"
echo " "
echo "This applies for a coregistration with offset only. The full polynomial for each pixel is used in the following and saved to file sar_latlon_offset.txt"
echo " "

azline=0
rgpixel=0
width=`echo $master_width-1 | bc`
while [ $azline -lt $master_length ]; do
    rgpixel=`seq 0 $width`
    printf "$azline %s\n" $rgpixel >> sar_az_rg.txt
    ((azline++))
done

# calculate the az and rg offset values per pixel (polynomial model)
awk '{printf "%.5f %.5f\n", '$az_offset'+'$az_pol1'*$2+'$az_pol2'*$1+'$az_pol3'*$2*$1, '$rg_offset'+'$rg_pol1'*$2+'$rg_pol2'*$1+'$rg_pol3'*$2*$1}' sar_az_rg.txt > sar_coord_offset.txt
rm -f sar_az_rg.txt
# convert the offset to latitude and longitude, also add offset to account for pixel centre
awk '{printf "%.8f %.8f\n", -1*(-1*$2*'$rg_gr_spacing'*sin('$heading'/180*'$pi')+$1*'$az_spacing'*cos('$heading'/180*'$pi'))*180/'$pi'/(sqrt('$M'*'$N'))+'$post_lat'/2, -1*($2*'$rg_gr_spacing'*cos('$heading'/180*'$pi')+$1*'$az_spacing'*sin('$heading'/180*'$pi'))*180/'$pi'/(cos('$centre_lat'/180*'$pi')*sqrt('$M'*'$N'))+'$post_lon'/2}' sar_coord_offset.txt > sar_latlon_offset.txt
rm -f sar_coord_offset.txt

echo "Offsets calculated and saved to file"
echo " "

# Calculation of lat and lon for all pixel positions
echo "Starting loop over $master_length azimuth lines and $master_width range pixels"
azline=0
while [ $azline -lt $master_length ]; do
    if (( $azline % 100 == 0 ))
    then
	echo "processing line $azline"
    fi

    # convert radarcoded DEM to ASCII in order to be able to extract the height values at each SAR pixel
    float2ascii $rdc_dem $master_width temp_dem.txt $azline 1 >/dev/null

    # read the heights from the temporary file temp_dem.txt (contains one line only)
    while read -a linearray; do
	printf "%s\n" "${linearray[@]}" > temp_heights.txt
    done < temp_dem.txt
    rm -f temp_dem.txt

    # create sar_coord.txt file containing three columns: az rg height
    rgpixel=`seq 0 $width`
    printf "$azline %s\n" $rgpixel >> temp_sar.txt
    paste temp_sar.txt temp_heights.txt -d" " > sar_coord.txt
    rm -f temp_sar.txt
    rm -f temp_heights.txt

    # calculate latitude and longitude for all SAR pixels and save them into $lat_lon_pix
    sarpix_coord_list $r_dem_master_mli_par - - sar_coord.txt map_coord.txt >/dev/null
    awk '{print $1 " " $2}' map_coord.txt >> sar_latlon_mli.txt
    rm -f sar_coord.txt
    rm -f map_coord.txt

    # next line
    ((azline++))
done

# add DEM coregistration offsets as a translation value to lat/lon coordinates
paste sar_latlon_mli.txt sar_latlon_offset.txt | awk '{printf "%.8f %.8f\n", ($1 + $3), ($2 + $4)}' > $lat_lon_pix
rm -f sar_latlon_offset.txt
rm -f sar_latlon_mli.txt

