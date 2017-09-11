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
    echo "*         Sarah Lawrie @ GA       06/08/2015, v1.1                            *"
    echo "*           - add geocoding of cc and filt ifms for plotting.                 *"
    echo "*         Sarah Lawrie @ GA       23/12/2015, v1.2                            *"
    echo "*           - change snr to cross correlation parameters (process changed     *"
    echo "*             in GAMMA version Dec 2015)                                      *"
    echo "*           - add branch-cut unwrapping method as an option                   *"
    echo "*         Thomas Fuhrmann @ GA       21/03/2017, v1.3                         *"
    echo "*           - added iterative precision baseline estimation                   *"
    echo "*             note that initial baseline estimate uses orbital state vectors  *"
    echo "*         Sarah Lawrie @ GA       13/07/2017, v1.4                            *"
    echo "*           - add processing for CSK spotlight data                           *"
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
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
sensor_mode=`grep Sensor_mode= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
rpos=`grep rpos= $proc_file | cut -d "=" -f 2`
azpos=`grep azpos= $proc_file | cut -d "=" -f 2`
int_thres=`grep int_thres= $proc_file | cut -d "=" -f 2`
init_win=`grep init_win= $proc_file | cut -d "=" -f 2`
offset_win=`grep offset_win= $proc_file | cut -d "=" -f 2`
unwrap_type=`grep unwrap_type= $proc_file | cut -d "=" -f 2`
start_x=`grep start_x= $proc_file | cut -d "=" -f 2`
start_y=`grep start_y= $proc_file | cut -d "=" -f 2`
base_iter_flag=`grep iterative= $proc_file | cut -d "=" -f 2`
bridge_flag=`grep bridge= $proc_file | cut -d "=" -f 2`
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
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
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
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING_SCENE: "$project $track_dir $mas-$slv $ifm_rlks"rlks" $ifm_alks"alks" $beam
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


mas_dir=$slc_dir/$mas
slv_dir=$slc_dir/$slv
int_dir=$int_dir/$mas-$slv
ref_mas_dir=$slc_dir/$master

#if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    mas_slc_name=$mas"_"$polar
    mas_mli_name=$mas"_"$polar"_"$ifm_rlks"rlks"
    slv_slc_name=$slv"_"$polar
    slv_mli_name=$slv"_"$polar"_"$ifm_rlks"rlks"
    mas_slv_name=$mas-$slv"_"$polar"_"$ifm_rlks"rlks"
    ref_mas_name=$master"_"$polar
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
    # reference master
ref_mas_slc_par=$ref_mas_dir/r$ref_mas_name.slc.par


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
sim_unw_ph=$int_dir/$mas_slv_name"_sim_ph.unw"
sim_diff=$int_dir/$mas_slv_name"_sim_diff.unw"
int_flat=$int_dir/$mas_slv_name"_flat.int"
int_flat_temp=$int_dir/$mas_slv_name"_flat_temp.int"
int_flat0=$int_dir/$mas_slv_name"_flat0.int"
int_flat1=$int_dir/$mas_slv_name"_flat1.int"
int_flat10=$int_dir/$mas_slv_name"_flat10.int"
int_filt=$int_dir/$mas_slv_name"_filt.int"
int_flat_float=$int_dir/$mas_slv_name"_flat_int.flt"
int_filt_float=$int_dir/$mas_slv_name"_filt_int.flt"
#int_filt_mask=$int_dir/$mas_slv_name"_filt_mask.int"
cc=$int_dir/$mas_slv_name"_flat.cc"
cc0=$int_dir/$mas_slv_name"_flat0.cc"
cc0_mask=$int_dir/$mas_slv_name"_flat0_cc_mask.ras"
cc10=$int_dir/$mas_slv_name"_flat10.cc"
cc10_mask=$int_dir/$mas_slv_name"_flat10_cc_mask.ras"
smcc=$int_dir/$mas_slv_name"_filt.cc"
cc_flag=$int_dir/$mas_slv_name"_filt_cc.flag"
bridge=$int_dir/$mas_slv_name.bridges
mask=$int_dir/$mas_slv_name"_mask.ras"
mask1=$int_dir/$mas_slv_name"_mask1.ras"
mask_thin=$int_dir/$mas_slv_name"_mask_thin.ras"
int_unw=$int_dir/$mas_slv_name.unw
int_unw_org=$int_dir/$mas_slv_name"_bef_bridge.unw"
int_unw_mask=$int_dir/$mas_slv_name"_mask.unw"
int_unw_thin=$int_dir/$mas_slv_name"_thin.unw"
int_unw_model=$int_dir/$mas_slv_name"_model.unw"
base=$int_dir/$mas_slv_name"_base.par"
base_init=$int_dir/$mas_slv_name"_base_init.par"
base_res=$int_dir/$mas_slv_name"_base_res.par"
base_temp=$int_dir/$mas_slv_name"_base_temp.par"
bperp=$int_dir/$mas_slv_name"_bperp.par"
flag=$int_dir/$mas_slv_name.flag
unw_geocode_out=$int_dir/$mas_slv_name"_utm.unw"
flat_geocode_out=$int_dir/$mas_slv_name"_flat_int_utm.flt"
filt_geocode_out=$int_dir/$mas_slv_name"_filt_int_utm.flt"
smcc_geocode_out=$int_dir/$mas_slv_name"_filt_utm.cc"
cc_geocode_out=$int_dir/$mas_slv_name"_flat_utm.cc"
unw_geocode_bmp=$int_dir/$mas_slv_name"_utm_unw.bmp"
flat_geocode_bmp=$int_dir/$mas_slv_name"_flat_int_utm_flt.bmp"
filt_geocode_bmp=$int_dir/$mas_slv_name"_filt_int_utm_flt.bmp"
smcc_geocode_bmp=$int_dir/$mas_slv_name"_filt_utm_cc.bmp"
cc_geocode_bmp=$int_dir/$mas_slv_name"_flat_utm_cc.bmp"
geotif=$unw_geocode_out.tif
#lv_theta=$int_dir/$mas_slv_name.lv_theta
#lv_phi=$int_dir/$mas_slv_name.lv_phi
# disp=$int_dir/$mas_slv_name.displ_vert
offs=$int_dir/$mas_slv_name.offs
ccp=$int_dir/$mas_slv_name.ccp
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

        ## 2-pass differential interferometry without phase unwrapping (CSK spotlight)
	if [ $sensor = CSK ] && [ $sensor_mode = SP ]; then
            # Measure initial range and azimuth offsets using orbit information
	    GM init_offset_orbit $mas_slc_par $slv_slc_par $off $rpos $azpos 1

	    # Measure initial range and azimuth offsets using the images
	    GM init_offset $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $ifm_rlks $ifm_alks $rpos $azpos - - $int_thres $init_win 1

	    # Estimate range and azimuth offset models using correlation of image intensities
	    GM offset_pwr $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $offs $ccp $offset_win - 2 32 32 $int_thres 4
	    GM offset_fit $offs $ccp $off $coffs $coffsets $int_thres 1 0
	else
	    GM offset_pwr $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $offs $ccp 64 64 - 2 64 256 0.1
	    GM offset_fit $offs $ccp $off $coffs $coffsets
	fi
    else
	:
    fi

    ## Create differential interferogram parameter file
    GM create_diff_par $off - $diff_par 0 0
}

FLAT()
{
    echo " "
    echo "Processing FLAT..."
    echo " "

    cd $int_dir

    ## Calculate initial baseline
    GM base_orbit $mas_slc_par $slv_slc_par $base_init

    ## Simulate the phase from the DEM and linear baseline model. linear baseline model may be inadequate for longer scenes, in which case use phase_sim_orb
    GM phase_sim_orb $mas_slc_par $slv_slc_par $off $rdc_dem $sim_unw0 $ref_mas_slc_par - - 1 1

    if [ $sensor = CSK ] && [ $sensor_mode = SP ]; then
        ## also calculate simulated phase using phase_sim
	GM phase_sim $mas_slc_par $off $base_init $rdc_dem $sim_unw_ph 0 0 - - 1 - 0

        ## calculate difference between phase_sim and phase_sim_orb algorithms (quadratic ramp in azimuth)
        GM sub_phase $sim_unw0 $sim_unw_ph $diff_par $sim_diff 0 0
    fi

    ## Calculate initial flattened interferogram (baselines from orbit)
    GM SLC_diff_intf $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $sim_unw0 $int_flat0 $ifm_rlks $ifm_alks 1 1 0.25 1 1

    ## Estimate residual baseline using fringe rate of differential interferogram
    GM base_init $mas_slc_par - $off $int_flat0 $base_res 4

    ## Add residual baseline estimate to initial estimate
    GM base_add $base_init $base_res $base 1

    ## Simulate the phase from the DEM and refined baseline model
    GM phase_sim $mas_slc_par $off $base $rdc_dem $sim_unw1 0 0 - - 1 - 0

    ## Calculate second flattened interferogram (baselines refined using fringe rate)
    GM SLC_diff_intf $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $sim_unw1 $int_flat1 $ifm_rlks $ifm_alks 1 1 0.25 1 1

    if [ $base_iter_flag == yes ]; then
        ## As the initial baseline estimate maybe quite wrong for longer baselines, iterations are performed here
        ## Initialise variables for iterative baseline calculation (initial baseline)
        counter=0
        test=0
        baseC=`grep "initial_baseline(TCN):" $base_init | awk '{print $3}'`
        baseN=`grep "initial_baseline(TCN):" $base_init | awk '{print $4}'`
        cp -f $base_init $base_temp
        cp -f $int_flat0 $int_flat_temp
        ## $thresh defines the threshold in [m] at which the while loop is aborted
        thresh=0.15

        while [ $test -eq 0 -a $counter -lt 15 ]; do

            let counter=counter+1
            echo "Initial baseline refinement, Iteration:" $counter
            echo

            ## Estimate residual baseline using fringe rate of differential interferogram
            GM base_init $mas_slc_par - $off $int_flat_temp $base_res 4

	    baseC_res=`grep "initial_baseline(TCN):" $base_res | awk '{print $3}'`
	    baseN_res=`grep "initial_baseline(TCN):" $base_res | awk '{print $4}'`
	    baserateC_res=`grep "initial_baseline_rate:" $base_res | awk '{print $3}'`
	    baserateN_res=`grep "initial_baseline_rate:" $base_res | awk '{print $4}'`
	    echo "Baseline difference (C N):" $baseC_res $baseN_res
	    echo

            ## only add half of the residual estimate for better convergence of the iteration
            ## otherwise values may jump between two extreme values or even not converge at all
	    baseC_res_add=`echo "scale=7; ($baseC_res)/2" | bc`
	    baseN_res_add=`echo "scale=7; ($baseN_res)/2" | bc`
	    baserateC_add=`echo "scale=7; ($baserateC_res)/2" | bc`
	    baserateN_add=`echo "scale=7; ($baserateN_res)/2" | bc`
	    echo "initial_baseline(TCN):        0.0000000     "$baseC_res_add"     "$baseN_res_add"   m   m   m" > temp.txt
	    echo "initial_baseline_rate:        0.0000000     "$baserateC_add"     "$baserateN_add"   m/s m/s m/s" >> temp.txt
	    grep "precision_baseline(TCN):" $base_res >> temp.txt
	    grep "precision_baseline_rate:" $base_res >> temp.txt
	    grep "unwrap_phase_constant:" $base_res >> temp.txt
	    mv -f temp.txt $base_res

            ## $test equals 1 if the differences between baselines is below $thresh
            test=`echo "${baseC_res_add#-} < $thresh && ${baseN_res_add#-} < $thresh" | bc`
            #test=`echo "${baseC_res#-} < $thresh && ${baseN_res#-} < $thresh" | bc`

	    if [ $test -eq 0 -a $counter -eq 15 ]; then
	        echo "Baseline estimates did not converge after 15 iterations." >> error.log
	        echo "Initial baseline estimate using orbital state vectors is used for further processing." >> error.log
	        echo "Check baseline estimates and flattened IFG and rerun manually if necessary!" >> error.log
	        echo >> error.log
                #cp -f $base_init $base
	        GM base_init $mas_slc_par $slv_slc_par - - $base 0
	    else
                ## Add residual baseline estimate to initial estimate
	        GM base_add $base_temp $base_res $base 1
	    fi

	    baseC=`grep "initial_baseline(TCN):" $base | awk '{print $3}'`
	    baseN=`grep "initial_baseline(TCN):" $base | awk '{print $4}'`
	    echo "Baseline (C N):" $baseC $baseN

            ## Simulate the phase from the DEM and refined baseline model
	    GM phase_sim $mas_slc_par $off $base $rdc_dem $sim_unw1 0 0 - - 1 - 0

            ## Calculate flattened interferogram after baseline iteration
            GM SLC_diff_intf $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $sim_unw1 $int_flat1 $ifm_rlks $ifm_alks 1 1 0.25 1 1

            cp -f $int_flat1 $int_flat_temp
	    cp -f $base $base_temp

        done
        ### iteration

        rm -f $base_temp
        rm -f $int_flat_temp
    else
        # use original baseline estimation without iteration
        :
    fi

    ## Generate quicklook image
    GM rasmph $int_flat0 $int_width 1 0 40 40 - - - $int_flat0.bmp
    GM rasmph $int_flat1 $int_width 1 0 40 40 - - - $int_flat1.bmp

    #######################################
    if [ $sensor = CSK ] && [ $sensor_mode = SP ]; then
	## Do not perform precision baseline refinement for Cosmo Spotlight data
        ## add azimuth ramp (diff) back to simulated phase
        GM sub_phase $sim_diff $sim_unw1 $diff_par $sim_unw 0 1

    else
        ## Perform refinement of baseline model using ground control points

        ## multi-look the flattened interferogram 10 times
        GM multi_cpx $int_flat1 $off $int_flat10 $off10 10 10 0 0

        width10=`grep interferogram_width: $off10 | awk '{print $2}'`
	
        ## Generate coherence image
        GM cc_wave $int_flat10 - - $cc10 $width10 7 7 1

        ## Generate validity mask with high coherence threshold for unwrapping
        ccthr=0.7
        GM rascc_mask $cc10 - $width10 1 1 0 1 1 $ccthr 0 - $ccthr - - 1 $cc10_mask

        ## Perform unwrapping
        GM mcf $int_flat10 $cc10 $cc10_mask $int_flat10.unw $width10 1 0 0 - - 1 1

        ## Oversample unwrapped interferogram to original resolution
        GM multi_real $int_flat10.unw $off10 $int_flat1.unw $off -10 -10 0 0

        ## Add full-res unwrapped phase to simulated phase
        GM sub_phase $int_flat1.unw $sim_unw1 $diff_par $int_flat"1.unw" 0 1

        ## calculate coherence of original flattened interferogram
        # MG: WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING COHERENCE OPTIMISATION
        GM cc_wave $int_flat1 - - $cc0 $int_width $ccwin $ccwin 1

        ## generate validity mask for GCP selection
        GM rascc_mask $cc0 - $int_width 1 1 0 1 1 0.7 0 - - - - 1 $cc0_mask

        ## select GCPs from high coherence areas
        GM extract_gcp $rdc_dem $off $gcp 100 100 $cc0_mask

        ## extract phase at GCPs
        GM gcp_phase $int_flat"1.unw" $off $gcp $gcp_ph 3

        ## Calculate precision baseline from GCP phase data
        #cp -f $base $base"1"
        GM base_ls $mas_slc_par $off $gcp_ph $base 0 1 1 1 1 10

        ## Simulate the phase from the DEM and precision baseline model.
        GM phase_sim $mas_slc_par $off $base $rdc_dem refined 0 1

        ## add refined phase_sim to original differenceulated phase from initial interferogram
        GM sub_phase diff refined $diff_par $sim_unw 0 1

    fi

    ## Calculate final flattened interferogram with common band filtering (diff ifg generation from co-registered SLCs and a simulated interferogram)
    GM SLC_diff_intf $mas_slc $slv_slc $mas_slc_par $slv_slc_par $off $sim_unw $int_flat $ifm_rlks $ifm_alks 1 1 0.25 1 1

    ## Calculate perpendicular baselines
    GM base_perp $base $mas_slc_par $off
    base_perp $base $mas_slc_par $off > $bperp

    ## Generate quicklook image of final flattened interferogram
    GM rasmph $int_flat $int_width 1 0 40 40 - - - $int_flat.bmp
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

    if [ $unwrap_type == mcf ]; then

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

        ## Produce unwrapping validity mask based on smoothed coherence
        GM rascc_mask $smcc - $int_width 1 1 0 1 1 $coh_thres 0 - - - - 1 $mask

        ## Use rascc_mask_thinning to weed the validity mask for large scenes. this can unwrap a sparser network which can be interpoolated and then used as a model for unwrapping the full interferogram
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

        ## Unwrapping with validity mask
        #GM mcf $int_filt $smcc $mask $int_unw $int_width 1 - - - - 1 1 - $refrg $refaz 1
	GM mcf $int_filt $smcc $mask_thin $int_unw_thin $int_width 1 - - - - $patch_r $patch_az - $refrg $refaz 0

        ## Interpolate sparse unwrapped points to give unwrapping model
	GM interp_ad $int_unw_thin $int_unw_model $int_width 32 8 16 2

        ## Use model to unwrap filtered interferogram
	if [ $refrg = "-" -a $refaz = "-" ]; then
	   GM unw_model $int_filt $int_unw_model $int_unw $int_width
	else
	   GM unw_model $int_filt $int_unw_model $int_unw $int_width $refrg $refaz $refphs
	fi

        ## Convert LOS signal to vertical
        #GM dispmap $int_unw $rdc_dem $mas_slc_par $off $disp 1

    elif [ $unwrap_type == branch ]; then    ####### SCRIPT STILL IN DRAFT FORM, USING NEUTRON NOT WORKING PROPERLY YET

	## Mask low correlation areas
	# create correlation file
	GM cc_wave $int_filt - - $smcc $int_width $ccwin $ccwin 1
	# create flagfile
	GM corr_flag $smcc $cc_flag $int_width $coh_thres

	### without neutron:

	## Determination of residues
	GM residue_cc $int_filt $cc_flag $int_width

	## Connection of residues through neutral trees (uses marked low correlation areas and residues)
	GM tree_cc $cc_flag $int_width 32


	### with neutron:

	## Generation of neutrons (using master scene's intensity image)
	#GM neutron $mas_mli $cc_flag $int_width 6

	## Determination of residues
	#GM residue $int_filt $cc_flag $int_width

	## Connection of residues through neutral trees (uses marked low correlation areas, neutrons and residues)
	#GM tree_gzw $cc_flag $int_width 32


	## Unwrapping of interferometric phase
	GM grasses $int_filt $cc_flag $int_unw $int_width - - - - $start_x $start_y 1

        # phase unwrapping of disconnected areas using user defined bridges (done after initial unwrapping with 'grasses')
	if [ $bridge_flag == yes ]; then
	   if [ ! -e $int_unw ]; then
		echo "ERROR: Cannot locate unwrapped interferogram (*.unw). Please run this script from with bridge flag set to 'no' and then re-run with flag set to 'yes'"
		exit 1
	   else
		cp -f $int_unw $int_unw_org #save original unw ifg
		GM bridge $int_filt $cc_flag $int_unw $bridge $int_width
           fi
	else
	    :
	fi
    else
	echo "Unwrapping method not a valid type, must be branch-cut or minimum cost flow"
	exit 1
    fi
}


GEOCODE()
{
    echo " "
    echo "Geocoding interferogram..."
    echo " "
    width_in=`grep range_samp_1: $diff_dem | awk '{print $2}'`
    width_out=`grep width: $dem_par | awk '{print $2}'`

    ## Use bicubic spline interpolation for geocoded unwrapped interferogram
    GM geocode_back $int_unw $width_in $gc_map $unw_geocode_out $width_out - 1 0 - -
    # make quick-look png image 
    GM rasrmg $unw_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $unw_geocode_bmp
    GM convert $unw_geocode_bmp ${unw_geocode_bmp/.bmp}.png
    rm -f $unw_geocode_bmp

    ## Use bicubic spline interpolation for geocoded flattened interferogram
    # convert to float and extract phase
    GM cpx_to_real $int_flat $int_flat_float $width_in 4
    GM geocode_back $int_flat_float $width_in $gc_map $flat_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $flat_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $flat_geocode_bmp
    GM convert $flat_geocode_bmp ${flat_geocode_bmp/.bmp}.png
    rm -f $flat_geocode_bmp

    ## Use bicubic spline interpolation for geocoded filtered interferogram
    # convert to float and extract phase
    GM cpx_to_real $int_filt $int_filt_float $width_in 4
    GM geocode_back $int_filt_float $width_in $gc_map $filt_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $filt_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $filt_geocode_bmp
    GM convert $filt_geocode_bmp ${filt_geocode_bmp/.bmp}.png
    rm -f $filt_geocode_bmp

    ## Use bicubic spline interpolation for geocoded filt coherence file
    GM geocode_back $smcc $width_in $gc_map $smcc_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $smcc_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $smcc_geocode_bmp
    GM convert $smcc_geocode_bmp ${smcc_geocode_bmp/.bmp}.png
    rm -f $smcc_geocode_bmp

    ## Use bicubic spline interpolation for geocoded flat coherence file
    GM geocode_back $cc $width_in $gc_map $cc_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $cc_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $cc_geocode_bmp
    GM convert $cc_geocode_bmp ${cc_geocode_bmp/.bmp}.png
    rm -f $cc_geocode_bmp


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

    # Extract coordinates from DEM for plotting par file
    width=`grep width: $dem_par | awk '{print $2}'`
    lines=`grep nlines: $dem_par | awk '{print $2}'`
    lon=`grep corner_lon: $dem_par | awk '{print $2}'`
    post_lon=`grep post_lon: $dem_par | awk '{print $2}'`
    post_lon=`printf "%1.12f" $post_lon`
    lat=`grep corner_lat: $dem_par | awk '{print $2}'`
    post_lat=`grep post_lat: $dem_par | awk '{print $2}'`
    post_lat=`printf "%1.12f" $post_lat`
    gmt_par=ifg.rsc
    echo WIDTH $width > $gmt_par
    echo FILE_LENGTH $lines >> $gmt_par
    echo X_FIRST $lon >> $gmt_par
    echo X_STEP $post_lon >> $gmt_par
    echo Y_FIRST $lat >> $gmt_par
    echo Y_STEP $post_lat >> $gmt_par
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
