#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* make_GAMMA_DEM: Script takes an ASCII file created in ArcGIS and creates    *"
    echo "*                 a DEM and par file for use with GAMMA.                      *"
    echo "*                                                                             *"
    echo "*   Put ascii_files into 'proj_dir' location (<project>/<sensor>/GAMMA).      *" 
    echo "*                                                                             *"
    echo "* input:  [proc_file]       name of GAMMA proc file (eg. gamma.proc)          *"
    echo "*         [dem_ascii_file]  name of DEM ascii file (eg. surat_srtm_1as.txt)   *"
    echo "*         <type>            EQA or UTM (default: EQA)                         *"
    echo "*                                                                             *"
    echo "*         optional:                                                           *"
    echo "*           <utm_zone>:    utm zone number, eg 52                             *"
    echo "*           <ext_ascii>:   name of external image ascii file                  *"
    echo "*                            (eg. surat_landsat.txt)                          *"
    echo "*           <west>:        western longitude for subsetting (EQA only)        *"
    echo "*           <east>:        eastern longitude for subsetting                   *"
    echo "*           <south>:       southern latitude for subsetting                   *"
    echo "*           <north>:       northern latitude for subsetting                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       09/07/2015, v1.1                            *"
    echo "*              Add option to format Landsat image for dem coregistration      *"
    echo "*         Sarah Lawrie @ GA       18/07/2016, v1.2                            *"
    echo "*             add option to process either EQA or UTM files                   *"
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
    echo -e "Usage: make_GAMMA_DEM.bash [proc_file] [dem_ascii_file] <type> <utm_zone> <ext_ascii> <west> <east> <south> <north>"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi

if [ $# -eq 3 ]; then
    type=$3
else
    type=EQA
fi
if [ $# -eq 4 ]; then
    utm_zone=$4
else
    utm_zone=-
fi
if [ $# -eq 5 ]; then
    ext_ascii_file=$5
else
    ext_ascii_file=-
fi

proc_file=$1
dem_ascii_file=$2


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

######################################################################

cd $proj_dir


## Subset DEM
if [ $type == 'EQA' -a $# -gt 6 -a $# -lt 9 ]; then
    echo "ERROR: enter west, east, south and north parameters for subsetting, in that order"
elif [ $# -eq 9 ]; then
    cut=1
    subset=-R$6/$7/$8/$9
else
    :
fi

## Copy dem data from MDSS and convert to GAMMA format
mkdir -p $gamma_dem_dir
mv $dem_ascii_file $gamma_dem_dir
dem_name=`echo $dem_ascii_file | sed 's/\.[^.]*$//'`

if [ -e $ext_ascii_file ]; then
    mv $ext_ascii_file $gamma_dem_dir
    ext_image_name=`echo $ext_ascii_file | sed 's/\.[^.]*$//'`
fi

cd $gamma_dem_dir

## Convert ArcGIS ascii text file to grd format
# get ascii header information
dos2unix $dem_ascii_file #need to convert file to extract values properly

ncols=`grep ^ncols $dem_ascii_file | awk '{print $2}'`
nrows=`grep ^nrows $dem_ascii_file | awk '{print $2}'`
xll=`grep ^xllcorner $dem_ascii_file | awk '{print $2}'`
yll=`grep ^yllcorner $dem_ascii_file | awk '{print $2}'`
xinc=`grep ^cellsize $dem_ascii_file | awk '{print $2}'`

## Determine if latitude is negative or positive
yll_int=`awk "BEGIN {printf \"%.0f\n\", $yll}"`
if [ $yll_int -lt 0 ]; then
    xmin=$xll
    xmax=`echo "($ncols * $xinc) + $xll" | bc -l`
    ymin=$yll
    ymax=`echo "($nrows * $xinc) + $yll" | bc -l`
else
    xmin=$xll
    xmax=`echo "($ncols * $xinc) + $xll" | bc -l`
    ymin=$yll
    ymax=`echo "($nrows * $xinc) + $yll" | bc -l`
fi

## Convert single column ascii to xyz format
gdal_translate -of XYZ $dem_name.txt $dem_name.xyz

## Extract extents from xyz for input into creatin grd file
grdinfo $dem_name.xyz > temp1
xmin=`grep x_min: temp1 | awk '{print $3}'`
xmax=`grep x_max: temp1 | awk '{print $5}'`
ymin=`grep y_min: temp1 | awk '{print $3}'`
ymax=`grep y_max: temp1 | awk '{print $5}'`
xinc=`grep x_inc: temp1 | awk '{print $7}'`
yinc=`grep x_inc: temp1 | awk '{print $7}'`
rm -f temp1

## Create GMT grd from xyz file
xyz2grd $dem_name.xyz -G$dem_name.grd -I$xinc/$yinc -R$xmin/$xmax/$ymin/$ymax 

## Optionally subset the DEM
#if [ $cut -eq 1 ]; then
#    mv $dem_name.grd temp.grd
#    grdcut temp.grd -G$dem_name.grd $subset 
#    rm -f temp.grd
#else
#    :
#if

## Convert GMT grd format to GAMMA format (4 byte floating point)
grdreformat $dem_name.grd $dem_name"_org.dem"=bf -N

## Change to big endian
swap_bytes $dem_name"_org.dem" $dem_name.dem 4

## Extract grd information for inclusion into DEM parameter file
grdinfo $dem_name.grd > temp1
offset=`awk 'NR==9 {print $5}' temp1` #add_offset
scale=`awk 'NR==9 {print $3}' temp1` #scale_factor
width=`awk 'NR==6 {print $11}' temp1` #nx
length=`awk 'NR==7 {print $11}' temp1` #ny
lat_post=-`awk 'NR==7 {print $7}' temp1` #y_inc (negative)
lon_post=`awk 'NR==6 {print $7}' temp1 ` #x_inc
lat=`awk 'NR==7 {print $5}' temp1` #y_max
lon=`awk 'NR==6 {print $3}' temp1` #x_min
rm -f temp1

## Create parameter file
if [ $type == 'EQA' ]; then
    echo "EQA" > temp2
    echo "WGS84" >> temp2
    echo "1" >> temp2
    echo $dem_name.dem >> temp2
    echo "REAL*4" >> temp2
    echo $offset >> temp2
    echo $scale >> temp2
    echo $width >> temp2
    echo $length >> temp2
    echo $lat_post $lon_post >> temp2
    echo $lat $lon >> temp2
elif [ $type == 'UTM' ]; then
    echo "UTM" > temp2
    echo "WGS84" >> temp2
    echo "1" >> temp2
    echo $utm_zone >> temp2
    echo "10000000." >> temp2
    echo $dem_name.dem >> temp2
    echo "REAL*4" >> temp2
    echo $offset >> temp2
    echo $scale >> temp2
    echo $width >> temp2
    echo $length >> temp2
    echo $lat_post $lon_post >> temp2
    echo $lat $lon >> temp2
else
    echo "dem type not recognised, needs to be 'EQA' or 'UTM'"
fi
create_dem_par $dem_name.dem.par < temp2
rm -f temp2

## Correct missing values in DEM
replace_values $dem_name.dem 0 0.0001 temp_dem $width 0 2
replace_values temp_dem -32768 0 temp_dem2 $width 0 2
interp_ad temp_dem2 $dem_name.dem $width 9 40 81 2 2 1 

## External image Processing
if [ -e $ext_ascii_file ]; then
    ext_image_width=`grep ncols $ext_image_name.txt | awk '{print $2}'`
    ascii2float $ext_image_name.txt $ext_image_width $ext_image_name.flt 6 - - -
fi

## Temp file clean up
rm -f $dem_name"_org.dem" $dem_name.xyz temp_dem temp_dem2 gmt.history 

## Create MDSS files
cd  $proj_dir
tar -cvzf $dem_name.tar.gz gamma_dem

## Move files to MDSS
echo ""
echo "Please manually copy dem tar file to MDSS."


# script end 
####################

