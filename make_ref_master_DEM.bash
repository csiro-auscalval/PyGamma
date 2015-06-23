#!/bin/bash

# set enivronment variable specific to script
export OMP_NUM_THREADS=4
    
display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* make_ref_master_DEM: Generate DEM coregistered to chosen master SLC in      *"
    echo "*                      radar geometry.                                        *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*         [rlks]        range multi-look value (for SLCs: from *.mli.par file *"
    echo "*                       or for ifms: from proc file)                          *"
    echo "*         [alks]        azimuth multi-look value (for SLCs: from *.mli.par    *"
    echo "*                       file or for ifms: from proc file)                     *"
    echo "*         [multi-look]  flag for multi-looking (no multi-looks = 1,           *"
    echo "*                       multi-looks = 2)                                      *"
    echo "*         [subset]      subset scene (no = 1, yes = 2)                        *"
    echo "*         <roff>        offset to starting range sample                       *"
    echo "*         <rlines>      number of range samples                               *"
    echo "*         <azoff>       offset to starting line                               *"
    echo "*         <azlines>     number of lines to copy                               *"
    echo "*         <beam>        beam number (eg, F2)                                  *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       20/05/2015, v1.1                            *"
    echo "*              Add beam processing capability for wide swath data             *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.2                            *"
    echo "*              Refine flags to enable auto calculation of subset values       *"
    echo "*******************************************************************************"
    echo -e "Usage: make_ref_master_DEM.bash [proc_file] [rlks] [alks] [multi-look] [subset] <roff> <rlines> <azoff> <azlines> <beam>"
    }

if [ $# -lt 5 ]
then 
    display_usage
    exit 1
fi


rlks=$2
alks=$3
multi_look=$4
subset=$5
roff=$6
rlines=$7
azoff=$8
azlines=$9
beam=${10} # need curly bracket to get 10th variable to be recognised

proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
noffset=`grep offset= $proc_file | cut -d "=" -f 2`
offset_measure=`grep offset_measure= $proc_file | cut -d "=" -f 2`
dem_win=`grep dem_win= $proc_file | cut -d "=" -f 2`
dem_snr=`grep dem_snr= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
    dem_name_nci=`grep DEM_name_NCI= $proc_file | cut -d "=" -f 2`
    dem=$proj_dir/gamma_dem/$dem_name_nci
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    dem_dir_ga=`grep DEM_location_GA= $proc_file | cut -d "=" -f 2`
    dem_name_ga=`grep DEM_name_GA= $proc_file | cut -d "=" -f 2`
    dem=$dem_dir_ga/$dem_name_ga
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir $rlks"rlks" $alks"aks" $beam 1>&2

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

mkdir -p $dem_dir
cd $dem_dir

dem_par=$dem.par
master_dir=$slc_dir/$master

# if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    slc_name=$master"_"$polar
else # beam exists
    slc_name=$master"_"$polar"_"$beam
fi

if [ $multi_look -eq 1 -a $subset -eq 1 ]; then # full res DEM for calculating subset values or geocoding full slc
    if [ -z $beam ]; then # no beam
        mli_name=$master"_"$polar"_0rlks"
    else # beam exists
        mli_name=$master"_"$polar"_"$beam"_0rlks"
    fi
elif [ $multi_look -eq 1 -a $subset -eq 2 ]; then # full res DEM of subset
    if [ -z $beam ]; then # no beam
	mli_name=$master"_"$polar"-subset_0rlks"
    else # beam exists
	mli_name=$master"_"$polar"_"$beam"-subset_0rlks"
    fi
elif [ $multi_look -eq 2 -a $subset -eq 2 ]; then # multi-look dem and subset
    if [ -z $beam ]; then # no beam
	mli_name=$master"_"$polar"_"$rlks"rlks"	
    else # beam exists
	mli_name=$master"_"$polar"_"$beam"_"$rlks"rlks"
    fi
else # multi-look dem and no subset
    if [ -z $beam ]; then # no beam
	mli_name=$master"_"$polar"_"$rlks"rlks"
    else # beam exists
	mli_name=$master"_"$polar"_"$beam"_"$rlks"rlks"
    fi
fi

## Files located in master SLC directory
master_mli=$master_dir/$mli_name.mli
master_mli_par=$master_mli.par
master_slc=$master_dir/$slc_name.slc
master_slc_par=$master_slc.par

cd $master_dir

## Determine range and azimuth looks for multi-looking
echo " "
echo "Range and azimuth looks: "$rlks $alks
echo " "

## Generate subsetted SLC and MLI files using parameters from gamma.proc
GM SLC_copy $master_slc $master_slc_par r$slc_name.slc r$slc_name.slc.par 1 - $roff $rlines $azoff $azlines

## Reset filenames after subsetting
master_mli=$master_dir/r$mli_name.mli
master_mli_par=$master_mli.par
master_slc=$master_dir/r$slc_name.slc
master_slc_par=$master_slc.par

GM multi_look $master_slc $master_slc_par $master_mli $master_mli_par $rlks $alks 0

#--------------------------------
#DEM:

mkdir -p $dem_dir
cd $dem_dir

# files located in DEM directory
rdc_dem=$dem_dir/$mli_name"_rdc.dem"
utm_dem=$dem_dir/$mli_name"_utm.dem"
utm_dem_par=$utm_dem.par
lt_rough=$dem_dir/$mli_name"_rough_utm_to_rdc.lt"
lt_fine=$dem_dir/$mli_name"_fine_utm_to_rdc.lt"
utm_sim_sar=$dem_dir/$mli_name"_utm.sim"
rdc_sim_sar=$dem_dir/$mli_name"_rdc.sim"
diff=$dem_dir/"diff_"$mli_name.par
lsmap=$dem_dir/$mli_name"_utm.lsmap"
offs=$mli_name.offs
snr=$mli_name.snr
offsets=$mli_name.offsets
coffs=$mli_name.coffs
coffsets=$mli_name.coffsets

## Determine oversampling factor for DEM coregistration
dem_post=`grep post_lon $dem_par | awk '{printf "%.8f\n", $2}'`
if [ $(bc <<< "$dem_post <= 0.00011111") -eq 1 ]; then # 0.4 arc second or smaller DEMs
    ovr=1
elif [ $(bc <<< "$dem_post <= 0.00027778") -eq 1 ]; then # between 0.4 and 1 arc second DEMs
    ovr=4
elif [ $(bc <<< "$dem_post < 0.00083333") -eq 1 ]; then # between 1 and 3 arc second DEMs
    ovr=4
elif [ $(bc <<< "$dem_post >= 0.00083333") -eq 1 ]; then # 3 arc second or larger DEMs
    ovr=8
else
    :
fi
echo " "
echo "DEM oversampling factor: "$ovr
echo " "


##Generate DEM coregistered to master SLC in rdc geometry

## Derivation of initial geocoding look-up table and simulated SAR intensity image
# note: gc_map can produce looking vector grids and shadow and layover maps
# pre-determine segmented DEM_par by inputting constant height (necessary to avoid a bug in using gc_map)
if [ -e $utm_dem_par ]; then
    echo " "
    echo  $utm_dem_par" exists, removing file."
    echo " "
    rm -f $utm_dem_par
fi
if [ -e $utm_dem ]; then
    echo " "
    echo  $utm_dem" exists, removing file."
    echo " "
    rm -f $utm_dem
fi
GM gc_map $master_mli_par - $dem_par 10. $utm_dem_par $utm_dem $lt_rough $ovr $ovr - - - - - - - 8 1
# use predetermined dem_par to segment the full DEM
GM gc_map $master_mli_par - $dem_par $dem $utm_dem_par $utm_dem $lt_rough $ovr $ovr $utm_sim_sar - - - - - $lsmap 8 1

dem_width=`grep width: $utm_dem_par | awk '{print $2}'`
master_mli_width=`grep range_samples: $master_mli_par | awk '{print $2}'`
master_mli_length=`grep azimuth_lines: $master_mli_par | awk '{print $2}'`

## Transform simulated SAR intensity image to radar geometry
GM geocode $lt_rough $utm_sim_sar $dem_width $rdc_sim_sar $master_mli_width $master_mli_length 1 0 - - 2 4 -

## Fine coregistration of master MLI and simulated SAR image
# Make file to input user-defined values from proc file #
#for full dem:
if [ $rlks -eq 1 -a $alks -eq 1]; then
    returns=$dem_dir/returns
    echo "" > $returns #default scene title
    echo $noffset >> $returns
    echo $offset_measure >> $returns
    echo $dem_win >> $returns 
    echo $dem_snr >> $returns 
#for mli
else
    noffset1=`echo $noffset | awk '{print $1}'`
    if [ $noffset1 -eq 0 ]; then
	noff1=0
    else
	noff1=`echo $noffset1 | awk '{print $1/$rlks}'`
    fi
    noffset2=`echo $noffset | awk '{print $2}'`
    if [ $noffset2 -eq 0 ]; then
	noff2=0
    else
	noff2=`echo $noffset2 | awk '{print $1/$alks}'`
    fi
    returns=$dem_dir/returns
    echo "" > $returns #default scene title
    echo $noff1 $noff2 >> $returns
    echo $offset_measure >> $returns
    echo $dem_win >> $returns 
    echo $dem_snr >> $returns 
fi

## The high accuracy of Sentinel-1 orbits requires only an offset fit term rather than higher order polynomial terms
if [ $sensor == S1 ]; then
    npoly=1
else
    npoly=4
fi

GM create_diff_par $master_mli_par - $diff 1 < $returns
rm -f $returns

## initial offset estimate
GM init_offsetm $master_mli $rdc_sim_sar $diff $rlks $alks - - - - $dem_snr - 1 

GM offset_pwrm $master_mli $rdc_sim_sar $diff $offs $snr - - $offsets 1 - - -
#GM offset_pwrm $master_mli $rdc_sim_sar $diff $offs $snr 512 512 offsets 1 16 16 7.0

GM offset_fitm $offs $snr $diff $coffs $coffsets - $npoly

## precision estimation of the registration polynomial
rwin=`echo $dem_win | awk '{print $1/4}'`
azwin=`echo $dem_win | awk '{print $1/4}'`
nr=`echo $offset_measure | awk '{print $1*4}'`
naz=`echo $offset_measure | awk '{print $1*4}'`

GM offset_pwrm $master_mli $rdc_sim_sar $diff $offs $snr $rwin $azwin $offsets 2 $nr $naz -
#GM offset_pwrm $master_mli $rdc_sim_sar $diff $offs $snr 128 128 $offsets 2 64 64 7.0

GM offset_fitm $offs $snr $diff $coffs $coffsets - $npoly

grep "final model fit std. dev." output.log
#grep "final range offset poly. coeff.:" output.log
#grep "final azimuth offset poly. coeff.:" output.log

## Refinement of initial geocoding look up table
GM gc_map_fine $lt_rough $dem_width $diff $lt_fine 1

rm -f $lt_rough $offs $snr $offsets $coffs $coffsets test1.dat test2.dat

## Geocode map geometry DEM to radar geometry
GM geocode $lt_fine $utm_dem $dem_width $rdc_dem $master_mli_width $master_mli_length 1 0 - - 2 4 -

## Geocode simulated SAR intensity image to radar geometry
GM geocode $lt_fine $utm_sim_sar $dem_width $rdc_sim_sar $master_mli_width $master_mli_length 1 0 - - 2 4 -


# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
    cat error.log 1>&2
    rm temp_log
else
    rm temp_log
fi

## Rename log files if beam exists
if [ -z $beam ]; then # no beam
    :    
else # beam exists
    if [ -f $beam"_command.log" ]; then
	cat command.log >>$beam"_command.log"
    else
	mv command.log $beam"_command.log"
    fi
    if [ -f $beam"_output.log" ]; then
	cat output.log >>$beam"_output.log"
    else
	mv output.log $beam"_output.log"
    fi
    if [ -f $beam"_error.log" ]; then
	cat error.log >>$beam"_error.log"
    else
	mv error.log $beam"_error.log"
    fi
fi
