#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ifm:  Create a geocoded unwrapped interferogram from two            *"
    echo "*               coregistered SLCs.                                            *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [master]     master scene ID (eg. 20121130)                         *"
    echo "*         [slave]      slave scene ID (eg. 20121211)                          *"
    echo "*         [rlks]       range multi-look value                                 *"
    echo "*         [alks]       azimuth multi-look value                               *"
    echo "*         <beam>       beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       26/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: process_ifm.bash [proc_file] [master] [slave] [rlks] [alks] <beam>"
    }

if [ $# -lt 5 ]
then 
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" -o $3 -lt "10000000" ]; then 
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    mas=$2
    slv=$3
fi

proc_file=$1
ifm_rlks=$4
ifm_alks=$5
beam=$6

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
expon=`grep Exponent= $proc_file | cut -d "=" -f 2`
filtwin=`grep Filtering_window= $proc_file | cut -d "=" -f 2`
ccwin=`grep Coherence_window= $proc_file | cut -d "=" -f 2`
coh_thres=`grep Coherence_threshold= $proc_file | cut -d "=" -f 2`
patch_r=`grep Patches_range= $proc_file | cut -d "=" -f 2`
patch_az=`grep Patches_azimuth= $proc_file | cut -d "=" -f 2`
refrg=`grep Ref_point_range= $proc_file | cut -d "=" -f 2`
refaz=`grep Ref_point_azimuth= $proc_file | cut -d "=" -f 2`
refphs=`grep Ref_phase= $proc_file | cut -d "=" -f 2`
geotiff=`grep create_geotif= $proc_file | cut -d "=" -f 2`
begin=`grep ifm_begin= $proc_file | cut -d "=" -f 2`
finish=`grep ifm_end= $proc_file | cut -d "=" -f 2`


if [ $begin == INT -o $begin == FLAT -o $begin == FILT -o $begin == UNW -o $begin == GEOCODE ]; then 
    :
else
    echo " "
    echo "ERROR: [begin] variable is not a recognised option, update variable in *.proc file"
    echo " "
    exit 1
fi
if [ $finish == FLAT -o $finish == FILT -o $finish == UNW -o $finish == GEOCODE -o $finish == DONE ]; then 
    :
else
    echo " "
    echo "ERROR: [end] variable is not a recognised option, update variable in *.proc file"
    echo " "
    exit 1
fi

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir/$track_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $mas-$slv $ifm_rlks"rlks" $ifm_alks"alks" $beam 1>&2

## Copy output of Gamma programs to log files
GM()
{
    echo $* | tee -a command.log
    echo
    $* >> output.log 2> temp_log
    cat temp_log >> error.log
    #cat output.log (option to add output results to NCI .o file if required)
}


mas_dir=$slc_dir/$mas
slv_dir=$slc_dir/$slv
int_dir=$int_dir/$mas-$slv

#if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    mas_slc_name=$mas"_"$polar
    mas_mli_name=$mas"_"$polar"_"$ifm_rlks"rlks"
    slv_slc_name=$slv"_"$polar
    slv_mli_name=$slv"_"$polar"_"$ifm_rlks"rlks"
    mas_slv_name=$mas-$slv"_"$polar"_"$ifm_rlks"rlks"
else # beam exists
    mas_slc_name=$mas"_"$polar"_"$beam
    mas_mli_name=$mas"_"$polar"_"$beam"_"$ifm_rlks"rlks"
    slv_slc_name=$slv"_"$polar"_"$beam
    slv_mli_name=$slv"_"$polar"_"$beam"_"$ifm_rlks"rlks"
    mas_slv_name=$mas-$slv"_"$polar"_"$beam"_"$ifm_rlks"rlks"
fi

## Files located in SLC directories
    # master files
mas_slc=$mas_dir/r$mas_slc_name.slc
mas_slc_par=$mas_slc.par
mas_mli=$mas_dir/r$mas_mli_name.mli
mas_mli_par=$mas_mli.par
    # slave files
slv_slc=$slv_dir/r$slv_slc_name.slc
slv_slc_par=$slv_slc.par
slv_mli=$slv_dir/r$slv_mli_name.mli
slv_mli_par=$slv_mli.par


if [ ! -f $mas_slc ]; then 
    echo " "
    echo "ERROR: Cannot locate resampled master SLC. Please first run make_ref_master_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi
if [ ! -f $mas_mli ]; then 
    echo " "
    echo "ERROR: Cannot locate resampled master MLI. Please first run make_ref_master_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi
if [ ! -f $slv_slc ]; then 
    echo  " "
    echo "ERROR: Cannot locate resampled slave SLC. Please first run make_ref_master_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi
if [ ! -f $slv_mli ]; then 
    echo " "
    echo "ERROR: Cannot locate resampled slave MLI. Please first run make_ref_master_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi
echo " "
echo "Interferometric product range and azimuth looks: "$ifm_rlks $ifm_alks

int_width=`grep range_samples $mas_mli_par | awk '{print $2}'`

#files located in DEM directory

if [ -z $beam ]; then #no beam
    rdc_dem=$dem_dir/$master"_"$polar"_"$ifm_rlks"rlks_rdc.dem"
    diff_dem=$dem_dir/"diff_"$master"_"$polar"_"$ifm_rlks"rlks.par"
    gc_map=$dem_dir/$master"_"$polar"_"$ifm_rlks"rlks_fine_utm_to_rdc.lt"
    dem_par=$dem_dir/$master"_"$polar"_"$ifm_rlks"rlks_utm.dem.par"
else # beam exists
    rdc_dem=$dem_dir/$master"_"$polar"_"$beam"_"$ifm_rlks"rlks_rdc.dem"
    diff_dem=$dem_dir/"diff_"$master"_"$polar"_"$beam"_"$ifm_rlks"rlks.par"
    gc_map=$dem_dir/$master"_"$polar"_"$beam"_"$ifm_rlks"rlks_fine_utm_to_rdc.lt"
    dem_par=$dem_dir/$master"_"$polar"_"$beam"_"$ifm_rlks"rlks_utm.dem.par"
fi

# files located in INT directory
off=$int_dir/$mas_slv_name"_off.par"
off10=$int_dir/$mas_slv_name"_off10.par"
diff_par=$int_dir/$mas_slv_name"_diff.par"
int=$int_dir/$mas_slv_name.int
sim_unw=$int_dir/$mas_slv_name"_sim.unw"
sim_unw0=$int_dir/$mas_slv_name"_sim0.unw"
sim_unw1=$int_dir/$mas_slv_name"_sim1.unw"
int_flat=$int_dir/$mas_slv_name"_flat.int"
int_flat0=$int_dir/$mas_slv_name"_flat0.int"
int_flat1=$int_dir/$mas_slv_name"_flat1.int"
int_flat10=$int_dir/$mas_slv_name"_flat10.int"
int_filt=$int_dir/$mas_slv_name"_filt.int"
#int_filt_mask=$int_dir/$mas_slv_name"_filt_mask.int"
cc=$int_dir/$mas_slv_name"_flat.cc"
cc0=$int_dir/$mas_slv_name"_flat0.cc"
cc0_mask=$int_dir/$mas_slv_name"_flat0_cc_mask.ras"
cc10=$int_dir/$mas_slv_name"_flat10.cc"
cc10_mask=$int_dir/$mas_slv_name"_flat10_cc_mask.ras"
smcc=$int_dir/$mas_slv_name"_filt.cc"
mask=$int_dir/$mas_slv_name"_mask.ras"
mask1=$int_dir/$mas_slv_name"_mask1.ras"
mask_thin=$int_dir/$mas_slv_name"_mask_thin.ras"
int_unw=$int_dir/$mas_slv_name.unw
int_unw_mask=$int_dir/$mas_slv_name"_mask.unw"
int_unw_thin=$int_dir/$mas_slv_name"_thin.unw"
int_unw_model=$int_dir/$mas_slv_name"_model.unw"
base=$int_dir/$mas_slv_name"_base.par"
base_init=$int_dir/$mas_slv_name"_base_init.par"
base_res=$int_dir/$mas_slv_name"_base_res.par"
bperp=$int_dir/$mas_slv_name"_bperp.par"
flag=$int_dir/$mas_slv_name.flag
geocode_out=$int_dir/$mas_slv_name"_utm.unw"
geotif=$geocode_out.tif
#lv_theta=$int_dir/$mas_slv_name.lv_theta
#lv_phi=$int_dir/$mas_slv_name.lv_phi
# disp=$int_dir/$mas_slv_name.displ_vert
offs=$int_dir/$mas_slv_name.offs
snr=$int_dir/$mas_slv_name.snr
coffs=$int_dir/$mas_slv_name.coffs
coffsets=$int_dir/$mas_slv_name.coffsets
gcp=$int_dir/$mas_slv_name.gcp
gcp_ph=$int_dir/$mas_slv_name.gcp_ph
real=$int_dir/$mas_slv_name.real


### Each processing step is a 'function'. The if statement which controls start and stop is below the functions
INT()
{
    echo " "
    echo "Processing INT..."
    echo " "
    
    mkdir -p $int_dir
    cd $int_dir
    
    ## Calculate and refine offset between interferometric SLC pair
    ## Also done in offset tracking so test if this has been run
    if [ ! -e $off ]; then
	GM create_offset $mas_slc_par $slv_slc_par $off 1 $ifm_rlks $ifm_alks 0
	GM offset_pwr $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $offs $snr 64 64 - 2 64 256 7.0
	GM offset_fit $offs $snr $off $coffs $coffsets
    else
	:
    fi
    ## Calculate initial interferogram from coregistered SLCs
    GM SLC_intf $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $int $ifm_rlks $ifm_alks - - 1 1
    
    ## Estimate initial baseline using orbit state vectors, offsets, and interferogram phase
    GM base_init $mas_slc_par $slv_slc_par $off $int $base_init 2
    #GM look_vector $mas_slc_par $off $utm_dem_par $utm_dem $lv_theta $lv_phi
}

FLAT()
{
    echo " "
    echo "Processing FLAT..."
    echo " "
    if [ ! -e $int ]; then
	echo "ERROR: Cannot locate initial interferogram (*.int). Please re-run this script from INT"
	exit 1
    else
	:
    fi
    cd $int_dir

    ## Simulate the phase from the DEM and linear baseline model. linear baseline model may be inadequate for longer scenes, in which case use phase_sim_orb
    GM phase_sim $mas_slc_par $off $base_init $rdc_dem $sim_unw0 0 0 - - 1 - 0

    ## Create differential interferogram parameter file
    create_diff_par $off - $diff_par 0 0

    ## Subtract simulated phase
    GM sub_phase $int $sim_unw0 $diff_par $int_flat0 1 0

    ## Estimate residual baseline using fringe rate of differential interferogram
    GM base_init $mas_slc_par $slv_slc_par $off $int_flat0 $base_res 4

    ## Add residual baseline estimate to initial estimate
    GM base_add $base_init $base_res $base 1

    ## Simulate the phase from the DEM and refined baseline model
    GM phase_sim $mas_slc_par $off $base $rdc_dem $sim_unw1 0 0 - - 1 - 0

    ## Subtract topographic phase
    GM sub_phase $int $sim_unw1 $diff_par $int_flat1 1 0

    #######################################
    # Perform refinement of baseline model

    ## multi-look the flattened interferogram 10 times
    GM multi_cpx $int_flat1 $off $int_flat10 $off10 10 10 0 0

    width10=`grep interferogram_width: $off10 | awk '{print $2}'`

    ## Generate coherence image
    GM cc_wave $int_flat10 - - $cc10 $width10 7 7 1

    ## Generate validity mask with high coherence threshold
    GM rascc_mask $cc10 - $width10 1 1 0 1 1 0.7 0 - - - - 1 $cc10_mask

    ## Perform unwrapping
    GM mcf $int_flat10 $cc10 $cc10_mask $int_flat10.unw $width10 1 0 0 - - 1 1

    ## Oversample unwrapped interferogram to original resolution
    GM multi_real $int_flat10.unw $off10 $int_flat1.unw $off -10 -10 0 0

    ## Add full-res unwrapped phase to simulated phase
    GM sub_phase $int_flat1.unw $sim_unw1 $diff_par $int_flat"1.unw" 0 1

    ## calculate coherence of original flattened interferogram
    # WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING COHERENCE OPTIMISATION
    GM cc_wave $int_flat1 - - $cc0 $int_width $ccwin $ccwin 1

    ## generate valifity mask for GCP selection
    GM rascc_mask $cc0 - $int_width 1 1 0 1 1 0.4 0 - - - - 1 $cc0_mask

    ## select GCPs from high coherence areas
    GM extract_gcp $rdc_dem $off $gcp 100 100 $cc0_mask

    ## extract phase at GCPs
    GM gcp_phase $int_flat"1.unw" $off $gcp $gcp_ph 3

    ## Calculate precision baseline from GCP phase data
    #cp -f $base $base"1"
    GM base_ls $mas_slc_par $off $gcp_ph $base 0 1 1 1 1 1.0

    ## Calculate perpendicular baselines
    GM base_perp $base $mas_slc_par $off
    base_perp $base $mas_slc_par $off > $bperp

    ## Simulate the phase from the DEM and precision baseline model.
    GM phase_sim $mas_slc_par $off $base $rdc_dem $sim_unw 0 1

    ## subtract simulated phase
    GM sub_phase $int $sim_unw $diff_par $int_flat 1 0
}

FILT()
{
    echo " "
    echo "Processing FILT..."
    echo " "
    if [ ! -e $int_flat ]; then 
	echo "ERROR: Cannot locate flattened interferogram (*.flat). Please re-run this script from FLAT"
	exit 1
    else
	:
    fi
    cd $int_dir

    ## calculate coherence of flattened interferogram
    # WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING COHERENCE OPTIMISATION
    GM cc_wave $int_flat $mas_mli $slv_mli $cc $int_width $ccwin $ccwin 1

    ## Smooth the phase by Goldstein-Werner filter
    GM adf $int_flat $int_filt $smcc $int_width $expon $filtwin $ccwin - 0 - -
}

UNW()
{
    echo " "
    echo "Processing UNW..."
    echo " "
    if [ ! -e $int_filt ]; then
	echo "ERROR: Cannot locate filtered interferogram (*.filt). Please re-run this script from FILT"
	exit 1
    else
	:
    fi
    cd $int_dir

    #look=5

    ## multi-look the flattened interferogram 10 times
    #GM multi_cpx $int_filt $off $int_filt$look $off$look $look $look 0 0

    #width=`grep interferogram_width: $off$look | awk '{print $2}'`

    ## Generate coherence image
    #GM cc_wave $int_filt$look - - $smcc$look $width 7 7 1

    ## Generate validity mask with low coherence threshold to unwrap more area
    #GM rascc_mask $smcc$look - $width 1 1 0 1 1 0.1

    ## Perform unwrapping
    #GM mcf $int_filt$look $smcc$look $smcc$look"_mask.ras" $int_filt$look.unw $width 1 0 0 - - 1 1 - 32 45 1

    ## Oversample unwrapped interferogram to original resolution
    #GM multi_real $int_filt$look.unw $off$look $int_filt"1.unw" $off -$look -$look 0 0

    #GM unw_model $int_filt $int_filt"1.unw" $int_unw $int_width

    ## Produce unwrapping validity mask based on smoothed coherence (for Minimum Cost Flow unwrapping method)
    GM rascc_mask $smcc - $int_width 1 1 0 1 1 $coh_thres 0 - - - - 1 $mask

    ## use rascc_mask_thinning to weed the validity mask for large scenes. this can unwrap a sparser networh which can be interpoolated and then used as a model for unwrapping the full interferogram
    thres_1=`echo $coh_thres + 0.2 | bc`
    thres_max=`echo $thres_1 + 0.2 | bc`
    #if [ $thres_max -gt 1 ]; then
    #    echo " "
    #    echo "MASK THINNING MAXIMUM THRESHOLD GREATER THAN ONE. Modify coherence threshold in proc file."
    #    echo " "
    #    exit 1
    #else
    #    :
    #fi
    GM rascc_mask_thinning $mask $smcc $int_width $mask_thin 3 $coh_thres $thres_1 $thres_max

    ## Minimum cost flow unwrapping with validity mask
    #GM mcf $int_filt $smcc $mask $int_unw $int_width 1 - - - - 1 1 - $refrg $refaz 1
    GM mcf $int_filt $smcc $mask_thin $int_unw_thin $int_width 1 - - - - $patch_r $patch_az

    ## interpolate sparse unwrapped points to give unwrapping model
    GM interp_ad $int_unw_thin $int_unw_model $int_width 32 8 16 2

    ## Use model to unwrap filtered interferogram
    if [ $refrg = "-" -a $refaz = "-" ]; then
	GM unw_model $int_filt $int_unw_model $int_unw $int_width
    else
	GM unw_model $int_filt $int_unw_model $int_unw $int_width $refrg $refaz $refphs
    fi

    ## Produce coherence mask for masking of unwrapped interferogram
    #GM rascc_mask $smcc - $int_width 1 1 0 1 1 $coh_thres 0 - - - - 1 $mask1

    ## apply mask to filtered interferogram here
    #GM mask_data $int_unw $int_width $int_unw_mask $mask1 0

    ## Convert LOS signal to vertical
    #GM dispmap $int_unw $rdc_dem $mas_slc_par $off $disp 1
}

GEOCODE()
{
    echo " "
    echo "Geocoding interferogram..."
    echo " "
    width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
    width_out=`grep width: $dem_par | awk '{print $2}'`
    ## Use bicubic spline interpolation for geocoded interferogram
    GM geocode_back $int_unw $width_in $gc_map $geocode_out $width_out - 1 0 - -
    echo " "
    echo "Geocoded interferogram."
    echo " "
    ## Create geotiff (optional)

    if [ $geotiff == yes ]; then
	echo " "
	echo "Creating geotiffed interferogram..."
	echo " "
	cp $int_unw $real
	GM data2geotiff $dem_par $real 2 $geotif 0.0
	rm -rf $real
	echo " "
	echo "Created geotiffed interferogram."
	echo " "
    else
	:
    fi
    echo " "
    echo "Creating GMT files for plotting interferogram..."
    echo " "
    # Create png file of unwrapped interferogram
    cpt=/g/data/dg9/repo/gamma_bash/bcgyr.cpt
    name=`echo $geocode_out | awk -F . '{print $1}'`
    psfile=$name"_unw.ps"
    # Extract coordinates from DEM for plotting par file
    width=`grep width: $dem_par | awk '{print $2}'`
    lines=`grep nlines: $dem_par | awk '{print $2}'`
    lon=`grep corner_lon: $dem_par | awk '{print $2}'`
    post_lon=`grep post_lon: $dem_par | awk '{print $2}'`
    post_lon=`printf "%1.12f" $post_lon`
    lat=`grep corner_lat: $dem_par | awk '{print $2}'`
    post_lat=`grep post_lat: $dem_par | awk '{print $2}'`
    post_lat=`printf "%1.12f" $post_lat`
    gmt_par=unw_gmt.par
    echo WIDTH $width > $gmt_par
    echo FILE_LENGTH $lines >> $gmt_par
    echo X_FIRST $lon >> $gmt_par
    echo X_STEP $post_lon >> $gmt_par
    echo Y_FIRST $lat >> $gmt_par
    echo Y_STEP $post_lat >> $gmt_par

    # Calculate interferogram extents
    rwidth=`awk 'NR==1 {print $2}' $gmt_par`
    rlength=`awk 'NR==2 {print $2}' $gmt_par`
    rx_min=`awk 'NR==3 {print $2}' $gmt_par`
    ry_max=`awk 'NR==5 {print $2}' $gmt_par`
    rx_step=`awk 'NR==4 {print $2}' $gmt_par`
    ry_step=`awk 'NR==6 {print $2}' $gmt_par`
    ry_step=`echo "$ry_step * -1" | bc`
    rx_max=`echo "$rx_min + $rwidth * $rx_step" | bc`
    ry_min=`echo "$ry_max - $rlength * $ry_step" | bc`
    range=-R$rx_min/$rx_max/$ry_min/$ry_max
    proj=-JM8
    inc=-I$rx_step
    # Convert intefergram to one column ascii
    float2ascii $geocode_out 1 $name.txt 0 -
    # Convert ascii to grd
    xyz2grd $name.txt -N0 $range -ZTLa -r $inc -G$name.grd
    # Make colour scale
    grdinfo $name.grd | tee temp
    z_min=`grep z_min: temp | awk '{print $3}'`
    z_max=`grep z_max: temp | awk '{print $5}'`
    span=-T$z_min/$z_max/1
    makecpt -C$cpt $span -Z > $name.cpt
    # Plot ifm
    grdimage $name.grd -C$name.cpt $proj $range -Qs -P > $psfile
    # Export image to .png
    ps2raster $psfile -A -E300 -Tg -P
    # Clean up files
    #rm -f $name.txt $name.grd temp $name.cpt $psfile 
    echo " "
    echo "Created GMT files for plotting interferogram."
    echo " "
}

DONE()
{
echo " "
echo "Processing Completed for Interferogram "$mas-$slv"."
echo " "
}


## If statement controlling start and stop functions
if [ $begin == INT ]; then
    INT
    if [ $finish == FLAT ]; then
	echo "Done INT commands, finished working before FLAT."
	exit 0
    else
	FLAT
    fi
    if [ $finish == FILT ]; then
	echo "Done FLAT commands, finished working before FILT."
	exit 0
    else
	FILT
    fi
    if [ $finish == UNW ]; then
	echo "Done FILT commands, finished working before UNW."
	exit 0
    else
	UNW
    fi
    if [ $finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $begin == FLAT ]; then
    FLAT
    if [ $finish == FILT ]; then
	echo "Done FLAT commands, finished working before FILT."
	exit 0
    else
	FILT
    fi
    if [ $finish == UNW ]; then
	echo "Done FILT commands, finished working before UNW."
	exit 0
    else
	UNW
    fi
    if [ $finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $begin == FILT ]; then
    FILT
    if [ $finish == UNW ]; then
	echo "Done FILT commands, finished working before UNW."
	exit 0
    else
	UNW
    fi
    if [ $finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $begin == UNW ]; then
    UNW
    if [ $finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $begin == GEOCODE ]; then
    GEOCODE
else
    echo "Begin code not recognised, check proc file."
fi


# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
    rm temp_log
    cat error.log 1>&2
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