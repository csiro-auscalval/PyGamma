#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_multi-look_values: Script takes full SLCs and determines               *"
    echo "*                         multi-looking factor from pixel spacing and         *"
    echo "*                         incidence angle in *.slc.par files. The multi-look  *"
    echo "*                         values are then added to the *.proc file.           *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA    27/02/2018, v0.1                            *"
    echo "*         Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: calc_multi-look_values.bash [proc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
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
PBS_processing_details $project $track

######################################################################

#file names
multilook


cd $proj_dir/$track

## Calculate multi-looking factor

# Constants
pi=3.1415926535

if [ $rlks == "auto" -a $alks == "auto" ]; then
  # Initialise parameters for loop
  counter=0
  azspsum=0
  rgspsum=0
  incsum=0
  # Loop over all SLC files in scene.list
  while read scene; do
  	slc_file_names
	  let counter=counter+1

    # Grep information on latitude and longitude and save into txt file to be used for offset calculations
	  azsp=`grep azimuth_pixel_spacing $slc_par | awk '{print $2}'`
	  rgsp=`grep range_pixel_spacing $slc_par | awk '{print $2}'`
	  rg=`grep center_range_slc $slc_par | awk '{print $2}'`
	  se=`grep sar_to_earth_center $slc_par | awk '{print $2}'`
    re=`grep earth_radius_below_sensor $slc_par | awk '{print $2}'`

    # calculate incidence angle using law of cosine
	  inc_a=`echo "scale=6; ($se^2-$re^2-$rg^2)/(2*$re*$rg)" | bc -l`

    # calculate arccos
  	if (( $(echo "$inc_a == 0" | bc -l) )); then
	    inc=`echo "a(1)*2" | bc -l`
	  elif (( $(echo "(-1 <= $inc_a) && ($inc_a < 0)" | bc -l) )); then
	    inc=`echo "scale=6; a(1)*4 - a(sqrt((1/($inc_a^2))-1))" | bc -l`
	  elif (( $(echo "(0 < $inc_a) && ($inc_a <= 1)" | bc -l) )); then
	    inc=`echo "scale=6; a(sqrt((1/($inc_a^2))-1))" | bc -l`
	  else
	    echo "input out of range"
	  fi
    # Sum up for mean value calculation
	  azspsum=`echo "$azspsum + $azsp" | bc`
	  rgspsum=`echo "$rgspsum + $rgsp" | bc`
	  incsum=`echo "$incsum + $inc" | bc`
  done < $scene_list

  # Mean az/rg spacing and incidence angle
  azspmean=`echo "scale=6; $azspsum/$counter" | bc`
  rgspmean=`echo "scale=6; $rgspsum/$counter" | bc`
  incmean=`echo "scale=6; $incsum/$counter" | bc`
  grrgspmean=`echo "scale=6; $rgspmean/s($incmean)" | bc -l`
  inc_deg=`echo "scale=6; $incmean*180/$pi" | bc`

  # check is 1 if ground rg spacing is greater than az spacing (usual case)
  check=`echo $grrgspmean'>'$azspmean | bc -l`
  if [ $check -eq 1 ]; then
    # Calculate azimuth multi-look factor to retrieve square pixels
	  az_ml_factor=`printf %.0f $(echo "$grrgspmean/$azspmean" | bc -l)`
    # note that printf %.0f is used to round to the nearest integer
	  rlks=$looks
	  alks=`echo "$looks*$az_ml_factor" | bc`
	  rg_ml_factor=-
  else
	  #echo "Azimuth spacing is greater than range spacing."
	  rg_ml_factor=`printf %.0f $(echo "$azspmean/$grrgspmean" | bc -l)`
    # note that printf %.0f is used to round to the nearest integer
	  rlks=`echo "$looks*$rg_ml_factor" | bc`
	  alks=$looks
	  az_ml_factor=-
  fi

  # update proc file with ref scene
  cp $proc_file temp1
  sed -i "s/RANGE_LOOKS=auto/RANGE_LOOKS=$rlks/g" temp1
  sed -i "s/AZIMUTH_LOOKS=auto/AZIMUTH_LOOKS=$alks/g" temp1
  cp $proc_file $pre_proc_dir/$track".proc_pre_ml"
  mv temp1 $proc_file
  rm -rf temp1
  echo "MULTI-LOOKING VALUE RESULTS" > $multi_results
  echo "" >> $multi_results
  echo "Input multi-look value: "$looks >> $multi_results
  echo "Mean azimuth spacing [m]: "$azspmean >> $multi_results
  echo "Mean range spacing (ground) [m]: "$grrgspmean >> $multi_results
  echo "Azimuth multi-looking factor to obtain square pixels: "$az_ml_factor >> $multi_results
  echo "Range multi-looking factor to obtain square pixels: "$rg_ml_factor >> $multi_results
  echo "" >> $multi_results
  echo "MLI range and azimuth looks: "$rlks $alks >> $multi_results
  echo "" >> $multi_results
    
    
  ### calculate DEM oversampling factor that fits the resolution of mulit-looked SAR data
  
  # load DEM file names from gamma_functions
  dem_file_names
  # grep the posting in lat and lon, half posting to be added to offset (pixel centre)
  postlat=`grep post_lat: $dem_par | awk '{print $2}'`
  postlon=`grep post_lon: $dem_par | awk '{print $2}'`
  post_lat=`echo ${postlat} | sed -e 's/[eE]+*/\\*10\\^/'`
  post_lon=`echo ${postlon} | sed -e 's/[eE]+*/\\*10\\^/'`
  # also get the centre latitude
  corner_lat=`grep corner_lat: $dem_par | awk '{print $2}'`
  nlines=`grep nlines: $dem_par | awk '{print $2}'`
  centre_lat=`echo "scale=10 ; $corner_lat+($nlines/2*$post_lat)" | bc -l`
  
  # convert lat/lon posting to metric
  # ellipsoid constants (as given in DEM.par file)
  a=`grep ellipsoid_ra: $dem_par | awk '{print $2}'`
  rep_f=`grep ellipsoid_reciprocal_flattening: $dem_par | awk '{print $2}'`
  f=`echo "scale=10 ; 1/$rep_f" | bc -l`
  # calculate radii of curvature for degree -> metric conversion
  e2=`echo "scale=10 ; 1/(1-$f)^2-1" | bc -l`
  c=`echo "scale=10 ; $a*sqrt(1+$e2)" | bc -l`
  V=`echo "scale=10 ; sqrt((1+($e2*c($centre_lat/180*$pi)^2)))" | bc -l`
  N=`echo "scale=10 ; $c/$V" | bc -l`
  M=`echo "scale=10 ; $c/($V^3)" | bc -l`
  post_lat_m=`echo "scale=10 ; $post_lat/180*$pi*(sqrt($M*$N))" | bc -l`
  post_lon_m=`echo "scale=10 ; $post_lon/180*$pi*c($centre_lat/180*$pi)*sqrt($M*$N)" | bc -l`
  dem_post_m=`echo "scale=10 ; (${post_lat_m#-}+${post_lon_m#-})/2" | bc -l`
  echo "DEM spacing latitude [m]: "$post_lat_m >> $multi_results   
  echo "DEM spacing longitude [m]: "$post_lon_m >> $multi_results
  echo "Average DEM spacing [m]: "$dem_post_m >> $multi_results
  
  # calculate DEM oversampling factor from average spacing of SAR data and DEM
  ml_sar_sp_mean=`echo "scale=6 ; (($alks*$azspmean)+($rlks*$grrgspmean))/2" | bc -l`
  dem_ovr=`echo "scale=6 ; $dem_post_m/$ml_sar_sp_mean" | bc -l` 
  echo "Average spacing of multi-looked SAR images [m]: "$ml_sar_sp_mean >> $multi_results
  echo "DEM oversampling factor suiting resolution of multi-looked SAR data: "$dem_ovr >> $multi_results 
    
else
    :
fi
# script end
####################


