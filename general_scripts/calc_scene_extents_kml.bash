#!/bin/bash


display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* calc_scene_extents_kml: calculate the edge coordinates for each SLC from    *"
    echo "*                         centre lat/lon, number of az/rg lines and spacing   *"
    echo "*                         given in *.slc.par files                            *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*         [list_type]  slave list type (1 = slaves.list, 2 = add_slaves.list, *"
    echo "*                      default is 1)                                          *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA    06/03/2018, v1.0                            *"
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
    echo -e "Usage: calc_scene_extents_kml.bash [proc_file] [list_type]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

if [ $# -eq 2 ]; then
    list_type=$2
else
    list_type=1
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

######################################################################


cd $proj_dir/$track

if [ $list_type -eq 1 ]; then
    list=$scene_list
    outfile=$proj_dir/$track/$track"_scene_polygons.kml"
else
    list=$add_scene_list
    outfile=$proj_dir/$track/$track"_add_scene_polygons.kml"
fi


# Constants
pi=3.1415926535
a=6378137
f=0.0033528107
#
e2=`echo "scale=12; 1/(1 - $f)^2 - 1" | bc -l`
c=`echo "scale=12; $a*sqrt(1+$e2)" | bc -l`


# Initialise the kml file
echo "Saving coordinates to kml file..."

# write the kml header
echo "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" > $outfile
echo "<kml xmlns=\"http://www.opengis.net/kml/2.2\">" >> $outfile
echo "	<Document>" >> $outfile
echo "		<name>Track "$track"</name>" >> $outfile
echo "		<description>"Sensor: $sensor, Track: $track"</description>" >> $outfile

# ascending pass scenes will be displayed in yellow
orbit=`echo $track | cut -c5`
if [ $orbit == A ]; then
echo "		<Style id=\"SwathPolygonStyle\"><LineStyle><color>ff00ffff</color><width>2</width></LineStyle><PolyStyle><color>4D00ffff</color><fill>1</fill></PolyStyle></Style>" >> $outfile
fi
# descending pass scenes will be displayed in orange
if [ $orbit == D ]; then
echo "		<Style id=\"SwathPolygonStyle\"><LineStyle><color>ff0088ff</color><width>2</width></LineStyle><PolyStyle><color>4D0088ff</color><fill>1</fill></PolyStyle></Style>" >> $outfile
fi

# initialise parameters for loop
counter=0

# loop over all SLC files in scene.list
while read file; do
    slc_file_names
    # path to slc.par file (foldername is also the scene date)
    let counter=counter+1

    # check if slc.par file exists
    if [ -f $slc_par ]; then
        # check file size of slc.par
	check=`wc -c < $slc_par`

        # calculation only possible for valid files, i.e. file size > 0
	if [ $check -gt 0 ]; then
            # grep information on centre latitude, longitude, az/rg spacing and so on from slc.par:
	    centre_lat=`grep center_latitude $slc_par | awk '{print $2}'`
	    centre_lon=`grep center_longitude $slc_par | awk '{print $2}'`
	    inc=`grep incidence_angle $slc_par | awk '{print $2}'`
	    heading=`grep heading: $slc_par | awk '{print $2}'`
	    az_lines=`grep azimuth_lines $slc_par | awk '{print $2}'`
	    rg_lines=`grep range_samples $slc_par | awk '{print $2}'`
	    az_spacing=`grep azimuth_pixel_spacing $slc_par | awk '{print $2}'`
	    rg_spacing=`grep range_pixel_spacing $slc_par | awk '{print $2}'`

            # calculate ground range spacing
	    gr_rg_spacing=`echo "scale=6; $rg_spacing/s($inc/180*$pi)" | bc -l`

            # metric distance from centre to scene edges
	    az_dist_m=`echo "scale=10; $az_lines*$az_spacing/2" | bc -l`
	    rg_dist_m=`echo "scale=10; $rg_lines*$gr_rg_spacing/2" | bc -l`

	    az_extent_km=`echo "scale=10; 2*$az_dist_m/1000" | bc -l`
	    rg_extent_km=`echo "scale=10; 2*$rg_dist_m/1000" | bc -l`
	    printf "%d: Scene extent (azimuth x range): %5.2f km x %5.2f km\n" $scene $az_extent_km $rg_extent_km

            # Local radii of Earth's curvature M and N using centre lat of the scene
	    V=`echo "scale=12; sqrt((1+($e2*(c($centre_lat/180*$pi))^2)))" | bc -l`
	    N=`echo "scale=12; $c/$V" | bc -l`
	    M=`echo "scale=12; $c/($V)^3" | bc -l`

            # calculate lat/lon for scene corners by converting metric az/rg distances to lat/lon and adding these numbers to the scene centre coordinates
            # note that the conversion from metric to lat/lon differences is techniqually only valid for the scene centre
            # the corner coordinates are hence accurate only within several hundred metres
	    lat1=`echo "scale=10; $centre_lat+(-1*$rg_dist_m*s($heading/180*$pi)+$az_dist_m*c($heading/180*$pi))*180/$pi/(sqrt($M*$N))" | bc -l`
	    lon1=`echo "scale=10; $centre_lon+($rg_dist_m*c($heading/180*$pi)+$az_dist_m*s($heading/180*$pi))*180/$pi/(c($centre_lat/180*$pi)*sqrt($M*$N))" | bc -l`
	    lat2=`echo "scale=10; $centre_lat+($rg_dist_m*s($heading/180*$pi)+$az_dist_m*c($heading/180*$pi))*180/$pi/(sqrt($M*$N))" | bc -l`
	    lon2=`echo "scale=10; $centre_lon+(-1*$rg_dist_m*c($heading/180*$pi)+$az_dist_m*s($heading/180*$pi))*180/$pi/(c($centre_lat/180*$pi)*sqrt($M*$N))" | bc -l`
	    lat3=`echo "scale=10; $centre_lat+($rg_dist_m*s($heading/180*$pi)+(-1*$az_dist_m)*c($heading/180*$pi))*180/$pi/(sqrt($M*$N))" | bc -l`
	    lon3=`echo "scale=10; $centre_lon+(-1*$rg_dist_m*c($heading/180*$pi)+(-1*$az_dist_m)*s($heading/180*$pi))*180/$pi/(c($centre_lat/180*$pi)*sqrt($M*$N))" | bc -l`
	    lat4=`echo "scale=10; $centre_lat+(-1*$rg_dist_m*s($heading/180*$pi)+(-1*$az_dist_m)*c($heading/180*$pi))*180/$pi/(sqrt($M*$N))" | bc -l`
	    lon4=`echo "scale=10; $centre_lon+($rg_dist_m*c($heading/180*$pi)+(-1*$az_dist_m)*s($heading/180*$pi))*180/$pi/(c($centre_lat/180*$pi)*sqrt($M*$N))" | bc -l`

            # output the corner coordinates to kml file
	    echo "			<Placemark>" >> $outfile
	    echo "				<name>$scene</name>" >> $outfile
	    echo "				<styleUrl>#SwathPolygonStyle</styleUrl>" >> $outfile
	    echo "				<MultiGeometry>" >> $outfile
	    echo "					<Polygon>" >> $outfile
	    echo "						<outerBoundaryIs>" >> $outfile
	    echo "							<LinearRing>" >> $outfile
	    echo "								<coordinates>" >> $outfile
	    echo "									"$lon1","$lat1",0" >> $outfile
	    echo "									"$lon2","$lat2",0" >> $outfile
	    echo "									"$lon3","$lat3",0" >> $outfile
	    echo "									"$lon4","$lat4",0" >> $outfile
	    echo "									"$lon1","$lat1",0" >> $outfile
	    echo "								</coordinates>" >> $outfile
	    echo "							</LinearRing>" >> $outfile
	    echo "						</outerBoundaryIs>" >> $outfile
	    echo "					</Polygon>" >> $outfile
	    echo "				</MultiGeometry>" >> $outfile
	    echo "			</Placemark>" >> $outfile
	else
	    echo "ERROR: slc.par has zero file size for $scene."
	fi
    else
	echo "ERROR: No slc.par file available for $scene."
    fi
done < $list

# write the end of the kml file
echo "	</Document>" >> $outfile
echo "</kml>" >> $outfile

# script end
####################
