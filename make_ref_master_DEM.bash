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
    echo "*         [image]       external reference image (no = 1, yes = 2)            *"
    echo "*         <roff>        offset to starting range sample                       *"
    echo "*         <rlines>      number of range samples                               *"
    echo "*         <azoff>       offset to starting line                               *"
    echo "*         <azlines>     number of lines to copy                               *"
    echo "*         <beam>        beam number (eg, F2)                                  *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       20/05/2015, v1.1                            *"
    echo "*              Add beam processing capability for wide swath data             *"
    echo "*         Sarah Lawrie @ GA       15/07/2015, v1.2                            *"
    echo "*              Add external reference image option                            *"
    echo "*         Sarah Lawrie @ GA       23/12/2015, v1.3                            *"
    echo "*              Change snr to cross correlation parameters (process changed    *"
    echo "*              in GAMMA version Dec 2015)                                     *"
    echo "*         Negin Moghaddam @ GA    29.04.2016, v1.4                            *"
    echo "*              Not using landsat image for Sentinel-1 Master-DEM coreg.       *"
    echo "*         Matt Garthwaite @ GA    19.08.2016, v1.5                            *"
    echo "*              Change order of master and rdc_dem to fix errors in coreg      *"
    echo "*         Sarah Lawrie @ GA       19/04/2017, v1.6                            *"
    echo "*              Modify method for calculating subsetting DEM                   *"
    echo "*******************************************************************************"
    echo -e "Usage: make_ref_master_DEM.bash [proc_file] [rlks] [alks] [multi-look] [subset] [image] <roff> <rlines> <azoff> <azlines> <beam>"
    }

if [ $# -lt 6 ]
then 
    display_usage
    exit 1
fi


rlks=$2
alks=$3
multi_look=$4
subset=$5
ext_image=$6
roff=$7
rlines=$8
azoff=$9
azlines=${10}
beam=${11} # need curly bracket to get 10th variable onwards to be recognised

proc_file=$1

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
noffset=`grep dem_offset= $proc_file | cut -d "=" -f 2`
offset_measure=`grep dem_offset_measure= $proc_file | cut -d "=" -f 2`
dem_patch_win=`grep dem_patch_window= $proc_file | cut -d "=" -f 2`
dem_win=`grep dem_win= $proc_file | cut -d "=" -f 2`
dem_snr=`grep dem_snr= $proc_file | cut -d "=" -f 2`
dem_rad_max=`grep dem_rad_max= $proc_file | cut -d "=" -f 2`
rpos=`grep rpos= $proc_file | cut -d "=" -f 2`
azpos=`grep azpos= $proc_file | cut -d "=" -f 2`
subset=`grep Subsetting= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
    subset_file=$proj_dir/$track_dir/lists/`grep Subset_file= $proc_file | cut -d "=" -f 2`
    dem_name_nci=`grep DEM_name_NCI= $proc_file | cut -d "=" -f 2`
    dem=$proj_dir/gamma_dem/$dem_name_nci
    dem_par=$proj_dir/gamma_dem/$dem_name_nci.par
    dem_par2=$dem.par

    if [ $ext_image -eq 2 ]; then
	image1=`grep Landsat_image= $proc_file | cut -d "=" -f 2`
	image=$proj_dir/gamma_dem/$image1
    else
	:
    fi
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
echo "PROCESSING_PROJECT: "$project $track_dir $rlks"rlks" $alks"alks" $beam 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir $rlks"rlks" $alks"alks" $beam
echo ""

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

master_dir=$slc_dir/$master

# if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    slc_name=$master"_"$polar
else # beam exists
    slc_name=$master"_"$polar"_"$beam
fi


# Coregistration results file
if [ -z $beam ]; then
    check_file=$proj_dir/$track_dir/dem_coreg_results"_"$rlks"rlks_"$alks"alks.txt"
else
    check_file=$proj_dir/$track_dir/dem_coreg_results"_"$beam"_"$rlks"rlks_"$alks"alks.txt"
fi


# Copy SLC and subset if required
COPY_SLC_FULL()
{
    if [ -z $beam ]; then # no beam
        mli_name=$master"_"$polar"_0rlks"
    else # beam exists
        mli_name=$master"_"$polar"_"$beam"_0rlks"
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
    GM SLC_copy $master_slc $master_slc_par r$slc_name.slc r$slc_name.slc.par 1 - - - - - 

    ## Reset filenames after subsetting
    master_mli=$master_dir/r$mli_name.mli
    master_mli_par=$master_mli.par
    master_slc=$master_dir/r$slc_name.slc
    master_slc_par=$master_slc.par

    GM multi_look $master_slc $master_slc_par $master_mli $master_mli_par 1 1 0
}


COPY_SLC()
{
    if [ -z $beam ]; then # no beam
	mli_name=$master"_"$polar"_"$rlks"rlks"	
    else # beam exists
	mli_name=$master"_"$polar"_"$beam"_"$rlks"rlks"
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
}


# Files located in DEM directory
DEM_FILES()
{
    rdc_dem=$dem_dir/$mli_name"_rdc.dem"
    utm_dem=$dem_dir/$mli_name"_utm.dem"
    utm_dem_par=$utm_dem.par
    lt_rough=$dem_dir/$mli_name"_rough_utm_to_rdc.lt"
    lt_fine=$dem_dir/$mli_name"_fine_utm_to_rdc.lt"
    utm_sim_sar=$dem_dir/$mli_name"_utm.sim"
    rdc_sim_sar=$dem_dir/$mli_name"_rdc.sim"
    loc_inc=$dem_dir/$mli_name"_local_inc.ang"
    diff=$dem_dir/"diff_"$mli_name.par
    lsmap=$dem_dir/$mli_name"_utm.lsmap"
    off=$dem_dir/$mli_name.off
    offs=$dem_dir/$mli_name.offs
    ccp=$dem_dir/$mli_name.ccp
    offsets=$dem_dir/$mli_name.offsets
    coffs=$dem_dir/$mli_name.coffs
    coffsets=$dem_dir/$mli_name.coffsets
    ##lsat_flt=$dem_dir/$mli_name"_lsat_sar.flt" 
    ##lsat_init_sar=$dem_dir/$mli_name"_lsat_init.sar" 
    ##lsat_sar=$dem_dir/$mli_name"_lsat.sar"
    lv_theta=$dem_dir/$mli_name"_utm.lv_theta"
    lv_phi=$dem_dir/$mli_name"_utm.lv_phi"
}


# Determine oversampling factor for DEM coregistration
OVER_SAMPLE()
{
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
}


# Generate DEM coregistered to master SLC in rdc geometry
GEN_DEM_RDC()
{
    # Derivation of initial geocoding look-up table and simulated SAR intensity image
    # note: gc_map can produce looking vector grids and shadow and layover maps

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
    
    # pre-determine segmented DEM_par by inputting constant height (necessary to avoid a bug in using gc_map)
    GM gc_map $master_mli_par - $dem_par 10. $utm_dem_par $utm_dem $lt_rough $ovr $ovr - - - - - - - 8 1
    # use predetermined dem_par to segment the full DEM
    GM gc_map $master_mli_par - $dem_par $dem $utm_dem_par $utm_dem $lt_rough $ovr $ovr $utm_sim_sar - - $loc_inc - - $lsmap 8 1
    
    # Convert landsat float file to same coordinates as DEM
    #if [ $ext_image -eq 2 ]; then
	#GM map_trans $dem_par $image $utm_dem_par $lsat_flt 1 1 1 0 -
    #else
        #:
    #fi

    dem_width=`grep width: $utm_dem_par | awk '{print $2}'`
    master_mli_width=`grep range_samples: $master_mli_par | awk '{print $2}'`
    master_mli_length=`grep azimuth_lines: $master_mli_par | awk '{print $2}'`
    
    # Transform simulated SAR intensity image to radar geometry
    GM geocode $lt_rough $utm_sim_sar $dem_width $rdc_sim_sar $master_mli_width $master_mli_length 1 0 - - 2 $dem_rad_max -

    #if [ $ext_image -eq 2 ]; then
    # Transform landsat image to radar geometr
	#GM geocode $lt_rough $lsat_flt $dem_width $lsat_init_sar $master_mli_width $master_mli_length 1 0 - - 2 4 -
    #else
        #:
    #fi
}


# Fine coregistration of master MLI and simulated SAR image
# Make file to input user-defined values from proc file #
CREATE_DIFF_PAR_FULL()
{
    cd $dem_dir
    returns=$dem_dir/returns
    echo "" > $returns #default scene title
    echo $noffset >> $returns
    echo $offset_measure >> $returns
    echo $dem_win >> $returns 
    echo $dem_snr >> $returns 

    GM create_diff_par $master_mli_par - $diff 1 < $returns
    rm -f $returns 
    # remove temporary mli files (only required to generate diff par)
    rm -f $master_mli $master_mli_par
}


CREATE_DIFF_PAR()
{
    cd $dem_dir
    noffset1=`echo $noffset | awk '{print $1}'`
    if [ $noffset1 -eq 0 ]; then
	noff1=0
    else
	#noff1=`echo $noffset1 | awk '{print $1/$rlks}'`
	noff1=$noffset1
    fi
    noffset2=`echo $noffset | awk '{print $2}'`
    if [ $noffset2 -eq 0 ]; then
	noff2=0
    else
	#noff2=`echo $noffset2 | awk '{print $1/$alks}'`
	noff2=$noffset2
    fi
    returns=$dem_dir/returns
    echo "" > $returns #default scene title
    echo $noff1 $noff2 >> $returns
    echo $offset_measure >> $returns
    echo $dem_win >> $returns 
    echo $dem_snr >> $returns 
        
    GM create_diff_par $master_mli_par - $diff 1 < $returns
    rm -f $returns  
}


OFFSET_CALC()
{
    # The high accuracy of Sentinel-1 orbits requires only a static offset fit term rather than higher order polynomial terms
    if [ $sensor == S1 ]; then
	npoly=1
    else
	npoly=4
    fi

    # initial offset estimate
    ##if [ $ext_image -eq 1 ]; then
    # MCG: following testing, rlks and azlks refer to FURTHER multi-looking. Should be set to 1 when using a multi-looked MLI for coreg.
    # MCG: set rdc_sim_sar as reference image for robust coreg 
    GM init_offsetm $rdc_sim_sar $master_mli $diff 1 1 $rpos $azpos - - $dem_snr $dem_patch_win 1

    GM offset_pwrm $rdc_sim_sar $master_mli $diff $offs $ccp - - $offsets 1 - - -
    ##else
    ##GM init_offsetm $master_mli $lsat_init_sar $diff $rlks $alks $rpos $azpos - - $dem_snr $dem_patch_win 1
    ##GM offset_pwrm $master_mli $lsat_init_sar $diff $offs $ccp - - $offsets 1 - - - 
    ##fi
    # if image patch extends beyond input MLI-1 (init_offsetm), an error is generated but not automatically put into error.log file
    grep "ERROR" output.log  1>&2

    GM offset_fitm $offs $ccp $diff $coffs $coffsets - $npoly

    # precision estimation of the registration polynomial
    rwin=`echo $dem_win | awk '{print $1/4}'`
    azwin=`echo $dem_win | awk '{print $1/4}'`
    nr=`echo $offset_measure | awk '{print $1*4}'`
    naz=`echo $offset_measure | awk '{print $1*4}'`

    ##if [ $ext_image -eq 1 ]; then
    GM offset_pwrm $rdc_sim_sar $master_mli $diff $offs $ccp $rwin $azwin $offsets 2 $nr $naz -
    #GM offset_pwrm $master_mli $rdc_sim_sar $diff $offs $ccp $rwin $azwin $offsets 2 $nr $naz -
    ##else
    ##  GM offset_pwrm $master_mli $lsat_init_sar $diff $offs $ccp $rwin $azwin $offsets 2 $nr $naz - 
    ##fi

    ## range and azimuth offset polynomial estimation 
    GM offset_fitm $offs $ccp $diff $coffs $coffsets - $npoly
    
    grep "final model fit std. dev." output.log
    #grep "final range offset poly. coeff.:" output.log
    #grep "final azimuth offset poly. coeff.:" output.log


    # Refinement of initial geocoding look up table
    if [ $ext_image -eq 1 ]; then
	GM gc_map_fine $lt_rough $dem_width $diff $lt_fine 1
    else
	GM gc_map_fine $lt_rough $dem_width $diff $lt_fine 0
    fi

    rm -f $lt_rough $offs $snr $offsets $coffs $coffsets test1.dat test2.dat
}


GEOCODE()
{
    # Geocode map geometry DEM to radar geometry
    GM geocode $lt_fine $utm_dem $dem_width $rdc_dem $master_mli_width $master_mli_length 1 0 - - 2 $dem_rad_max -

    # Geocode simulated SAR intensity image to radar geometry
    GM geocode $lt_fine $utm_sim_sar $dem_width $rdc_sim_sar $master_mli_width $master_mli_length 1 0 - - 2 $dem_rad_max -

    # Geocode landsat image to radar geometry
    ##if [ $ext_image -eq 2 ]; then
    ##  GM geocode $lt_fine $lsat_flt $dem_width $lsat_sar $master_mli_width $master_mli_length 1 0 - - 2 $dem_rad_max -
    ##else 
    ##   :
    ##fi

    # Extract final model fit values to check coregistration
    grep "final model fit std. dev. (samples)" output.log > temp1
    awk '{print $8}' temp1 > temp2
    awk '{print $10}' temp1 > temp3
    paste temp2 temp3 >> $check_file
    rm -f temp1 temp2 temp3
}


# Create look vector files
LOOK_VECTOR()
{
    GM look_vector $master_slc_par - $utm_dem_par $utm_dem $lv_theta $lv_phi
}


# Create geotif of master mli for subsetting
GEOTIF_FULL()
{
    cd $master_dir
    master_mli_utm=$master_dir/r$mli_name"_utm_full.mli"
    master_mli_geo=$master_dir/r$mli_name"_utm_mli_full.tif"
    width_in=`grep range_samp_1: $diff | awk '{print $2}'`
    width_out=`grep width: $utm_dem_par | awk '{print $2}'`
    
    GM geocode_back $master_mli $width_in $lt_fine $master_mli_utm $width_out - 0 0 - -
    GM data2geotiff $utm_dem_par $master_mli_utm 2 $master_mli_geo 0.0
}

GEOTIF()
{
    cd $master_dir
    master_mli_utm=$master_dir/r$mli_name"_utm_subset.mli"
    master_mli_geo=$master_dir/r$mli_name"_utm_mli_subset.tif"
    width_in=`grep range_samp_1: $diff | awk '{print $2}'`
    width_out=`grep width: $utm_dem_par | awk '{print $2}'`
    
    GM geocode_back $master_mli $width_in $lt_fine $master_mli_utm $width_out - 0 0 - -
    GM data2geotiff $utm_dem_par $master_mli_utm 2 $master_mli_geo 0.0
}



# Subsetting DEM option
if [ $subset == yes ]; then
    roff1=`[[ $roff =~ ^-?[0-9]+$ ]] && echo integer`
    rlines1=`[[ $rlines =~ ^-?[0-9]+$ ]] && echo integer`
    azoff1=`[[ $azoff =~ ^-?[0-9]+$ ]] && echo integer`
    azlines1=`[[ $azlines =~ ^-?[0-9]+$ ]] && echo integer`
    
    # subset region not calculated
    if [ $roff == "-" -a $rlines == "-" -a $azoff == "-" -a $azlines == "-" ]; then
	if [ ! -e $subset_file ]; then #subset hasn't been calculated yet
	    # generate diff par at full resolution
	    COPY_SLC_FULL
	    DEM_FILES
	    CREATE_DIFF_PAR_FULL
	    #generate full multi-looked dem for geotiffing so subset area can be determined in ArcGIS
	    COPY_SLC
	    DEM_FILES
	    OVER_SAMPLE
	    GEN_DEM_RDC
	    CREATE_DIFF_PAR
	    OFFSET_CALC
	    GEOCODE
	    GEOTIF_FULL
	fi
    # subset file exists and proc file has been updated
    elif [ $roff1 == "integer" -a $rlines1 == "integer" -a $azoff1 == "integer" -a $azlines1 == "integer" ]; then
	COPY_SLC
	DEM_FILES
	OVER_SAMPLE
	GEN_DEM_RDC
	CREATE_DIFF_PAR
	OFFSET_CALC
	GEOCODE
	LOOK_VECTOR
	GEOTIF
    else
	:
    fi
else # if no subsetting
    COPY_SLC
    DEM_FILES
    OVER_SAMPLE
    GEN_DEM_RDC
    CREATE_DIFF_PAR
    OFFSET_CALC
    GEOCODE
    LOOK_VECTOR
fi


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

