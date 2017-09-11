#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ERS_SLC_metadata.bash:  Script takes Level 1.0 (raw) ERS fine beam  *"
    echo "*                                 data and produces sigma0 calibrated SLC.    *"
    echo "*                                                                             *"
    echo "* Script used for extracting metadata from SLCs for ERS coverage maps and     *"
    echo "* creating tar files for ERS SLC distribution.                                *"
    echo "*                                                                             *"
    echo "* input:  [zip]         zip file name                                         *"
    echo "*         [scene]       scene ID (eg. 20070112)                               *"
    echo "*         [ers_sensor]  ERS1 or ERS2                                          *"
    echo "*         [year]        year scene was acquired in (eg. 2007)                 *"
    echo "*         [polarity]    eg. VV                                                *"
    echo "*         [raw_dir]     location of raw data                                  *"
    echo "*         [proj_dir]    project directory                                     *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       01/05/2014, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: process_ERS_SLC_metadata.bash [zip] [scene] [ers_sensor] [year] [polarity] [raw_dir] [proj_dir]"
    }

if [ $# -lt 7 ]
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

zip=$1
ers_sensor=$3
year=$4
polar=$5
raw_dir=$6
proj_dir=$7
slc_looks=6
SLC_dir=$proj_dir/SLC
scene_dir=$SLC_dir/$scene

mkdir -p $SLC_dir
mkdir -p $scene_dir
cd $scene_dir

source /short/dg9/insar/dg9-apps/GAMMA/GAMMA_CONFIG

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$zip 1>&2

## Copy output of Gamma programs to log files
GM()
{
    echo $* | tee -a command.log
    echo
    $* >> output.log 2> temp_log
    cat temp_log >> error.log
    #cat output.log (option to add output results to NCI .o file if required)
}

## ERS square pixels are 1 range look by 5 azimuth looks
rlks=$slc_looks 
alks=`echo $slc_looks | awk '{print $1*5}'` 
echo "MLI range and azimuth looks: "$rlks $alks

## Make dummy file to accept default values for the parameter file
echo "$ers_sensor $scene" > returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns
echo "" >> returns

## Set up sensor parameters
if [ $ers_sensor == ERS1 ]; then
    sensor_par=ERS1_ESA_sensor.par
    cp -f $MSP_HOME/sensors/ERS1_ESA.par $sensor_par
    cp -f $MSP_HOME/sensors/ERS1_antenna.gain .
    ## calibration constant from MSP/sensors/sensor_cal_MSP.dat file: 
    if [ $scene -le "19961231" ]; then # ERS1 19910717-19961231 = -10.3
	cal_const=-10.3
    else # ERS1 19970101-20000310 = -12.5
	cal_const=-12.5
    fi
elif [ $ers_sensor == ERS2 ]; then
    sensor_par=ERS2_ESA_sensor.par
    cp -f $MSP_HOME/sensors/ERS2_ESA.par $sensor_par
    cp -f $MSP_HOME/sensors/ERS2_antenna.gain .
    ## calibration constant from MSP/sensors/sensor_cal_MSP.dat file: ERS2 = -2.8
    cal_const=-2.8
   
else
    echo "ERROR: Must be ERS1 or ERS2"
    exit 1
fi

## set directory of DELFT orbits
if [ $ers_sensor == ERS1 ]; then
    if [ $scene -le "19961231" ]; then
	orb_dir=/g/data1/dg9/SAR_ORBITS/ERS_ODR_UPDATED/ERS1
    else
	orb_dir=/g/data1/dg9/SAR_ORBITS/ERS_ODR_UPDATED/ERS1_1999-2000 # different orbit files for ERS1 data collected post 1996.
    fi
else
    orb_dir=/g/data1/dg9/SAR_ORBITS/ERS_ODR_UPDATED/ERS2
fi

## File names
slc_name=$scene"_"$polar
mli_name=$scene"_"$polar"_"$rlks"rlks"
msp_par="p"$slc_name".slc.par"
raw=$slc_name".raw"
slc=$slc_name".slc"
slc_par=$slc".par"
mli=$mli_name".mli"
mli_par=$mli".par"
tiff=$mli_name".tif"
ras_out=$mli_name".ras"

## Produce raw data files
LED=`ls $raw_dir/scene01/lea_01.001`
IMG=`ls $raw_dir/scene01/dat_01.001`

## Copy raw data metadata report file
cp $raw_dir/scene01/report.txt .
raw_report=$scene_dir/report.txt

## Generate the MSP processing parameter file
if [ $scene -le "19971231" ]; then # CEOS leader format is different before and after 1998
    format=0 # before 1998
else
    format=1 # after 1998
fi
GM ERS_proc_ACRES $LED $msp_par $format < returns

## Condition the raw data and produce raw file in GAMMA format; check for missing lines
GM ERS_fix ACRES $sensor_par $msp_par 1 $IMG $raw

## Update orbital state vectors in MSP processing parameter file
## Note that Delft orbits are believed to be more precise than D-PAF orbits (PRC files). See Scharoo and Visser and Delft Orbits website
## Four 10-second state vectors should cover one 100km long ERS frame. More are required at either end of the scene. Providing more than necessary cannot hurt.
GM DELFT_proc2 $msp_par $orb_dir 21 10

## Determine the Doppler Ambiguity
## This is required for southern hemisphere data due to error in ERS pointing algorithm that introduces an ambiguity outside of the +/-(PRF/2) baseband
GM dop_ambig $sensor_par $msp_par $raw 2 - $slc_name.mlbf
## Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
#GM dop_mlcc $sensor_par $msp_par $raw $name.mlcc

#plot_mlcc.csh $slc_name.mlcc
#plot_mlbf.csh $slc_name.mlbf

## Determine the fractional Doppler centroid using the azimuth spectrum
GM azsp_IQ $sensor_par $msp_par $raw $slc_name.azsp

plot_azsp.csh $slc_name.azsp

## Estimate the doppler centroid across the swath
## Should be negligible (near constant) for ERS since yaw steering was employed to maintain the doppler centroid within +/-(PRF/2) 
GM doppler $sensor_par $msp_par $raw $slc_name.dop

plot_dop.csh $slc_name.dop

## Estimate the range power spectrum
## Look for potential radio frequency interference (RFI) to the SAR signal
GM rspec_IQ $sensor_par $msp_par $raw $slc_name.rspec

## Check range spectrum for spikes indicating RFI. If they exist can be suppresed during range compression 'pre_rc'
plot_rspec.csh $slc_name.rspec

## Range compression
## second to last parameter is for RFI suppression.
GM pre_rc $sensor_par $msp_par $raw $slc_name.rc - - - - - - - - 0 -

## REMOVE RAW IMAGE FILE HERE
rm -f $raw

## Azimuth autofocus
## run 'autof' twice for good estimate fo along-track velocity
GM autof $sensor_par $msp_par $slc_name.rc $slc_name.autof 2.0
GM autof $sensor_par $msp_par $slc_name.rc $slc_name.autof 2.0

## if correlation function peak is centred on zero azimuth then the focus is good
plot_autof.csh $slc_name.autof

##Azimuth compression to produce Single Look Complex (SLC)
## slc calibrated as sigma0
GM az_proc $sensor_par $msp_par $slc_name.rc $slc 4096 0 $cal_const 0

## REMOVE RC FILE HERE
rm -f $slc_name.rc

## Generate ISP SLC parameter file from MSP SLC parameter file (for full SLC)
GM par_MSP $sensor_par $msp_par $slc_par 0

## Add details from ISP parameter file to MSP parameter file
#temp1=`grep sensor: $slc_par | awk '{print $2}'`
#sed -i '4i sensor:     $temp1' $msp_par 
#temp2=`echo $raw_dir | cut -d "_" -f7` ## change value based on dir name when track has been added
#sed -i '6i track: $temp2' $msp_par 
#temp3=`echo $raw_dir | cut -d "_" -f7`
#sed -i '7i frame: $temp3' $msp_par 
#temp4=`grep Orbit: $raw_report | awk '{print $4}'`
#sed -i '8i orbit:$temp4' $msp_par 
#temp5=`grep "Sensor Configuration:" $raw_report | awk '{print $3}'`
#sed -i '9i orientation:$temp5' $msp_par 
#temp6=`ls -ltrh $slc | awk '{print $5}'`
#sed -i '10i slc_size:$temp6' $msp_par 
#temp7=`grep start_time: $slc_par | awk '{print $2}'`
#sed -i '12i start_time:$temp7' $msp_par 
#temp8=`grep center_time: $slc_par | awk '{print $2}'`
#sed -i '13i center_time:$temp8' $msp_par 
#temp9=`grep end_time: $slc_par | awk '{print $2}'`
#sed -i '14i end_time:$temp9' $msp_par 
#temp10=`grep incidence_angle: $slc_par | awk '{print $2}'`
#sed -i '16i incidence_angle:$temp10' $msp_par 
#temp11=`grep radar_frequency: $slc_par | awk '{print $2}'`
#sed -i '17i radar_frequency:$temp11' $msp_par 
#temp12=`grep "Sar band:" $raw_report | awk '{print $7}'`
#sed -i '18i sar_band:$temp12' $msp_par 
#temp13=`grep sar_to_earth_center: $slc_par | awk '{print $2}'`
#sed -i '21i sar_to_earth_center:$temp13' $msp_par 
#temp14=`grep earth_radius_below_sensor: $slc_par | awk '{print $2}'`
#sed -i '22i earth_radius_below_sensor:$temp14' $msp_par 
#temp15=`grep first_slant_range_polynomial: $slc_par | awk '{print $2}'`
#sed -i '42i first_slant_range_polynomial:$temp15' $msp_par 
#temp16=`grep center_slant_range_polynomial: $slc_par | awk '{print $2}'`
#sed -i '43i center_slant_range_polynomial:$temp16' $msp_par 
#temp17=`grep last_slant_range_polynomial: $slc_par | awk '{print $2}'`
#sed -i '44i last_slant_range_polynomial:$temp17' $msp_par 
#temp18=`grep azimuth_line_time: $slc_par | awk '{print $2}'`
#sed -i '75i azimuth_line_time:$temp18' $msp_par 
#temp19=`grep azimuth_angle: $slc_par | awk '{print $2}'`
#sed -i '76i azimuth_angle:$temp19' $msp_par 
#temp20=`grep azimuth_scale_factor: $slc_par | awk '{print $2}'`
#sed -i '77i azimuth_scale_factor:$temp20' $msp_par 
#temp21=`grep range_scale_factor: $slc_par | awk '{print $2}'`
#sed -i '78i range_scale_factor:$temp21' $msp_par 
#temp22=`grep line_header_size: $slc_par | awk '{print $2}'`
#sed -i '81i line_header_size:$temp22' $msp_par 
#temp23=`grep adc_sampling_rate: $slc_par | awk '{print $2}'`
#sed -i '82i adc_sampling_rate:$temp23' $msp_par 
#temp24=`grep chirp_bandwidth: $slc_par | awk '{print $2}'`
#sed -i '83i chirp_bandwidth:$temp24' $msp_par 
#temp25=`grep image_geometry: $slc_par | awk '{print $2}'`
#sed -i '85i image_geometry:$temp25' $msp_par 

## Multi-look SLC
GM multi_look $slc $slc_par $mli $mli_par $rlks $alks 0

## Create low-res preview tiff
mli_width=`grep range_samples: $mli_par | awk '{print $2}'`
GM data2tiff $mli $mli_width 2 $tiff

## Create low-res ras image (for location plot)
GM raspwr $mli $mli_width 1 0 1 1 1 0.35 1 $ras_out 0 0

## Make SLC location plot
plot_SLC_loc_ers_metadata.csh $scene $msp_par $ers_sensor $ras_out



# script end 
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2
rm temp_log
