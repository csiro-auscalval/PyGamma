#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_ifg:  Create a geocoded unwrapped interferogram from two            *"
    echo "*               coregistered SLCs.                                            *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [master]     master scene ID (eg. 20170423)                         *"
    echo "*         [slave]      slave scene ID (eg. 20180423)                          *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       26/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       06/08/2015, v1.1                            *"
    echo "*           - add geocoding of cc and filt ifms for plotting.                 *"
    echo "*         Sarah Lawrie @ GA       23/12/2015, v1.2                            *"
    echo "*           - change snr to cross correlation parameters (process changed     *"
    echo "*             in GAMMA version Dec 2015)                                      *"
    echo "*           - add branch-cut unwrapping method as an option                   *"
    echo "*         Thomas Fuhrmann @ GA    21/03/2017, v1.3                            *"
    echo "*           - added iterative precision baseline estimation                   *"
    echo "*             note that initial baseline estimate uses orbital state vectors  *"
    echo "*         Sarah Lawrie @ GA       13/07/2017, v1.4                            *"
    echo "*           - add processing for CSK spotlight data                           *"
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
    echo -e "Usage: process_ifg.bash [proc_file] [master] [slave]"
    }

if [ $# -lt 3 ]
then
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" -o $3 -lt "10000000" ]; then
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    master=$2
    slave=$3
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
PBS_processing_details $project $track $master-$slave

######################################################################

# File names
dem_master_names
dem_file_names
ifg_file_names

mkdir -p $ifg_dir
cd $ifg_dir


if [ $ifg_begin == INT -o $ifg_begin == FLAT -o $ifg_begin == FILT -o $ifg_begin == UNW -o $ifg_begin == GEOCODE ]; then
    :
else
    echo " "
    echo "ERROR: [begin] variable is not a recognised option, update variable in *.proc file"
    echo " "
    exit 1
fi
if [ $ifg_finish == FLAT -o $ifg_finish == FILT -o $ifg_finish == UNW -o $ifg_finish == GEOCODE -o $ifg_finish == DONE ]; then
    :
else
    echo " "
    echo "ERROR: [end] variable is not a recognised option, update variable in *.proc file"
    echo " "
    exit 1
fi

if [ ! -f $r_master_slc ]; then
    echo " "
    echo "ERROR: Cannot locate resampled master SLC. Please first run coregister_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi
if [ ! -f $r_master_mli ]; then
    echo " "
    echo "ERROR: Cannot locate resampled master MLI. Please first run coregister_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi
if [ ! -f $r_slave_slc ]; then
    echo  " "
    echo "ERROR: Cannot locate resampled slave SLC. Please first run coregister_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi
if [ ! -f $r_slave_mli ]; then
    echo " "
    echo "ERROR: Cannot locate resampled slave MLI. Please first run coregister_DEM.bash' followed by 'coregister_slave SLC.bash' for each acquisition"
    exit 1
else
    :
fi

ifg_width=`grep range_samples $r_master_mli_par | awk '{print $2}'`

### Each processing step is a 'function'. The if statement which controls start and stop is below the functions
INT()
{
    echo " "
    echo "Processing INT..."
    echo " "
    cd $ifg_dir

    ## Calculate and refine offset between interferometric SLC pair
    ## Also done in offset tracking so test if this has been run
    if [ ! -e $ifg_off ]; then
	GM create_offset $r_master_slc_par $r_slave_slc_par $ifg_off 1 $rlks $alks 0

        ## 2-pass differential interferometry without phase unwrapping (CSK spotlight)
	if [ $sensor = CSK ] && [ $sensor_mode = SP ]; then
            # Measure initial range and azimuth offsets using orbit information
	    GM init_offset_orbit $r_master_slc_par $r_slave_slc_par $ifg_off $ifg_rpos $ifg_azpos 1

	    # Measure initial range and azimuth offsets using the images
	    GM init_offset $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off $rlks $alks $ifg_rpos $ifg_azpos - - $ifg_int_thres $ifg_init_win 1

	    # Estimate range and azimuth offset models using correlation of image intensities
	    GM offset_pwr $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off $ifg_offs $ifg_ccp $ifg_offset_win - 2 32 32 $ifg_int_thres 5
	    GM offset_fit $ifg_offs $ifg_ccp $ifg_off $ifg_coffs $ifg_coffsets $ifg_int_thres 1 0
	else
	    GM offset_pwr $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off $ifg_offs $ifg_ccp 64 64 - 2 64 256 0.1
	    GM offset_fit $ifg_offs $ifg_ccp $ifg_off $ifg_coffs $ifg_coffsets
	fi
    else
	:
    fi
    ## Create differential interferogram parameter file
    GM create_diff_par $ifg_off - $ifg_diff_par 0 0
}

FLAT()
{
    echo " "
    echo "Processing FLAT..."
    echo " "

    cd $ifg_dir

    ## Calculate initial baseline
    GM base_orbit $r_master_slc_par $r_slave_slc_par $ifg_base_init

    ## Simulate the phase from the DEM and linear baseline model. linear baseline model may be inadequate for longer scenes, in which case use phase_sim_orb
    GM phase_sim_orb $r_master_slc_par $r_slave_slc_par $ifg_off $rdc_dem $ifg_sim_unw0 $r_master_slc_par - - 1 1

    if [ $sensor = CSK ] && [ $sensor_mode = SP ]; then
        ## also calculate simulated phase using phase_sim
	GM phase_sim $r_master_slc_par $ifg_off $ifg_base_init $rdc_dem $ifg_sim_unw_ph 0 0 - - 1 - 0

        ## calculate difference between phase_sim and phase_sim_orb algorithms (quadratic ramp in azimuth)
        GM sub_phase $ifg_sim_unw0 $ifg_sim_unw_ph $ifg_diff_par $ifg_sim_diff 0 0
    fi

    ## Calculate initial flattened interferogram (baselines from orbit)
    GM SLC_diff_intf $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off $ifg_sim_unw0 $ifg_flat0 $rlks $alks 1 0 0.25 1 1

    ## Estimate residual baseline using fringe rate of differential interferogram
    GM base_init $r_master_slc_par - $ifg_off $ifg_flat0 $ifg_base_res 4

    ## Add residual baseline estimate to initial estimate
    GM base_add $ifg_base_init $ifg_base_res $ifg_base 1

    ## Simulate the phase from the DEM and refined baseline model
    GM phase_sim $r_master_slc_par $ifg_off $ifg_base $rdc_dem $ifg_sim_unw1 0 0 - - 1 - 0

    ## Calculate second flattened interferogram (baselines refined using fringe rate)
    GM SLC_diff_intf $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off $ifg_sim_unw1 $ifg_flat1 $rlks $alks 1 0 0.25 1 1

    if [ $ifg_base_iter_flag == yes ]; then
        ## As the initial baseline estimate maybe quite wrong for longer baselines, iterations are performed here
        ## Initialise variables for iterative baseline calculation (initial baseline)
        counter=0
        test=0
        baseC=`grep "initial_baseline(TCN):" $ifg_base_init | awk '{print $3}'`
        baseN=`grep "initial_baseline(TCN):" $ifg_base_init | awk '{print $4}'`
        cp -f $ifg_base_init $ifg_base_temp
        cp -f $ifg_flat0 $ifg_flat_temp
        ## $thresh defines the threshold in [m] at which the while loop is aborted
        thresh=0.15

        while [ $test -eq 0 -a $counter -lt 15 ]; do

            let counter=counter+1
            echo "Initial baseline refinement, Iteration:" $counter
            echo

            ## Estimate residual baseline using fringe rate of differential interferogram
            GM base_init $r_master_slc_par - $ifg_off $ifg_flat_temp $ifg_base_res 4

	    baseC_res=`grep "initial_baseline(TCN):" $ifg_base_res | awk '{print $3}'`
	    baseN_res=`grep "initial_baseline(TCN):" $ifg_base_res | awk '{print $4}'`
	    baserateC_res=`grep "initial_baseline_rate:" $ifg_base_res | awk '{print $3}'`
	    baserateN_res=`grep "initial_baseline_rate:" $ifg_base_res | awk '{print $4}'`
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
	    grep "precision_baseline(TCN):" $ifg_base_res >> temp.txt
	    grep "precision_baseline_rate:" $ifg_base_res >> temp.txt
	    grep "unwrap_phase_constant:" $ifg_base_res >> temp.txt
	    mv -f temp.txt $ifg_base_res

            ## $test equals 1 if the differences between baselines is below $thresh
            test=`echo "${baseC_res_add#-} < $thresh && ${baseN_res_add#-} < $thresh" | bc`

	    if [ $test -eq 0 -a $counter -eq 15 ]; then
	        echo "Baseline estimates did not converge after 15 iterations." >> error.log
	        echo "Initial baseline estimate using orbital state vectors is used for further processing." >> error.log
	        echo "Check baseline estimates and flattened IFG and rerun manually if necessary!" >> error.log
	        echo >> error.log
	        GM base_init $r_master_slc_par $r_slave_slc_par - - $ifg_base 0
	    else
                ## Add residual baseline estimate to initial estimate
	        GM base_add $ifg_base_temp $ifg_base_res $ifg_base 1
	    fi

	    baseC=`grep "initial_baseline(TCN):" $ifg_base | awk '{print $3}'`
	    baseN=`grep "initial_baseline(TCN):" $ifg_base | awk '{print $4}'`
	    echo "Baseline (C N):" $baseC $baseN

            ## Simulate the phase from the DEM and refined baseline model
	    GM phase_sim $r_master_slc_par $ifg_off $ifg_base $rdc_dem $ifg_sim_unw1 0 0 - - 1 - 0

            ## Calculate flattened interferogram after baseline iteration
            GM SLC_diff_intf $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off $ifg_sim_unw1 $ifg_flat1 $rlks $alks 1 0 0.25 1 1

            cp -f $ifg_flat1 $ifg_flat_temp
	    cp -f $ifg_base $ifg_base_temp

        done
        ### iteration

        rm -f $ifg_base_temp
        rm -f $ifg_flat_temp
    else
        # use original baseline estimation without iteration
        :
    fi

    #######################################
    if [ $sensor = CSK ] && [ $sensor_mode = SP ]; then
	## Do not perform precision baseline refinement for Cosmo Spotlight data
        ## add azimuth ramp (diff) back to simulated phase
        GM sub_phase $ifg_sim_diff $ifg_sim_unw1 $ifg_diff_par $ifg_sim_unw 0 1

    else
        ## Perform refinement of baseline model using ground control points

        ## multi-look the flattened interferogram 10 times
        GM multi_cpx $ifg_flat1 $ifg_off $ifg_flat10 $ifg_off10 10 10 0 0

        width10=`grep interferogram_width: $ifg_off10 | awk '{print $2}'`
	
        ## Generate coherence image
        GM cc_wave $ifg_flat10 - - $ifg_flat_cc10 $width10 7 7 1

        ## Generate validity mask with high coherence threshold for unwrapping
        ccthr=0.7
        GM rascc_mask $ifg_flat_cc10 - $width10 1 1 0 1 1 $ccthr 0 - $ccthr - - 1 $ifg_flat_cc10_mask

        ## Perform unwrapping
        GM mcf $ifg_flat10 $ifg_flat_cc10 $ifg_flat_cc10_mask $ifg_flat10.unw $width10 1 0 0 - - 1 1

        ## Oversample unwrapped interferogram to original resolution
        GM multi_real $ifg_flat10.unw $ifg_off10 $ifg_flat1.unw $ifg_off -10 -10 0 0

        ## Add full-res unwrapped phase to simulated phase
        GM sub_phase $ifg_flat1.unw $ifg_sim_unw1 $ifg_diff_par $ifg_flat"1.unw" 0 1

        ## calculate coherence of original flattened interferogram
        # MG: WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING COHERENCE OPTIMISATION
        GM cc_wave $ifg_flat1 - - $ifg_flat_cc0 $ifg_width $ifg_ccwin $ifg_ccwin 1

        ## generate validity mask for GCP selection
        GM rascc_mask $ifg_flat_cc0 - $ifg_width 1 1 0 1 1 0.7 0 - - - - 1 $ifg_flat_cc0_mask

        ## select GCPs from high coherence areas
        GM extract_gcp $rdc_dem $ifg_off $ifg_gcp 100 100 $ifg_flat_cc0_mask

        ## extract phase at GCPs
        GM gcp_phase $ifg_flat"1.unw" $ifg_off $ifg_gcp $ifg_gcp_ph 3

        ## Calculate precision baseline from GCP phase data
        GM base_ls $r_master_slc_par $ifg_off $ifg_gcp_ph $ifg_base 0 1 1 1 1 10
 
	##### CODE BELOW DOESN'T LINK PROPERLY TO REST OF FLOW, NOT SURE WHAT 'DIFF' SHOULD BE
        ## Simulate the phase from the DEM and precision baseline model.
        #GM phase_sim $r_master_slc_par $ifg_off $ifg_base $rdc_dem refined 0 1

        ## add refined phase_sim to original simulated phase from initial interferogram 
        #GM sub_phase diff refined $ifg_diff_par $ifg_sim_unw 0 1

	#### USE OLD CODE FOR NOW
        ## Simulate the phase from the DEM and precision baseline model.
	GM phase_sim $r_master_slc_par $ifg_off $ifg_base $rdc_dem $ifg_sim_unw 0 1
 
        ## subtract simulated phase ('ifg_flat1' was originally 'ifg', but this file is no longer created)
	GM sub_phase $ifg_flat1 $ifg_sim_unw $ifg_diff_par $ifg_flat 1 0
    fi

    ## Calculate final flattened interferogram with common band filtering (diff ifg generation from co-registered SLCs and a simulated interferogram)
    GM SLC_diff_intf $r_master_slc $r_slave_slc $r_master_slc_par $r_slave_slc_par $ifg_off $ifg_sim_unw $ifg_flat $rlks $alks 1 0 0.25 1 1

    ## Calculate perpendicular baselines
    GM base_perp $ifg_base $r_master_slc_par $ifg_off
    base_perp $ifg_base $r_master_slc_par $ifg_off > $ifg_bperp
}

FILT()
{
    echo " "
    echo "Processing FILT..."
    echo " "
    if [ ! -e $ifg_flat ]; then
       echo "ERROR: Cannot locate flattened interferogram (*.flat). Please re-run this script from FLAT"
       exit 1
    else
       :
    fi
    cd $ifg_dir

    ## calculate coherence of flattened interferogram
    # WE SHOULD THINK CAREFULLY ABOUT THE WINDOW AND WEIGHTING PARAMETERS, PERHAPS BY PERFORMING COHERENCE OPTIMISATION
    GM cc_wave $ifg_flat $r_master_mli $r_slave_mli $ifg_flat_cc $ifg_width $ifg_ccwin $ifg_ccwin 1

    ## Smooth the phase by Goldstein-Werner filter
    GM adf $ifg_flat $ifg_filt $ifg_filt_cc $ifg_width $ifg_expon $ifg_filtwin $ifg_ccwin - 0 - -
}

UNW()
{
    echo " "
    echo "Processing UNW..."
    echo " "
    if [ ! -e $ifg_filt ]; then
	echo "ERROR: Cannot locate filtered interferogram (*.filt). Please re-run this script from FILT"
	exit 1
    else
        :
    fi
    cd $ifg_dir

    ## Produce unwrapping validity mask based on smoothed coherence
    GM rascc_mask $ifg_filt_cc - $ifg_width 1 1 0 1 1 $ifg_coh_thres 0 - - - - 1 $ifg_mask

    ## Use arbitrary mlook threshold of 4 to decide whether to thin data for unwrapping or not
    if [ $rlks -le 4 ]; then

         ## Use rascc_mask_thinning to weed the validity mask for large scenes. this can unwrap a sparser network which can be interpoolated and then used as a model for unwrapping the full interferogram
	thres_1=`echo $ifg_coh_thres + 0.2 | bc`
	thres_max=`echo $thres_1 + 0.2 | bc`
        #if [ $thres_max -gt 1 ]; then
        #    echo " "
        #    echo "MASK THINNING MAXIMUM THRESHOLD GREATER THAN ONE. Modify coherence threshold in proc file."
        #    echo " "
        #    exit 1
        #else
        #    :
        #fi
	GM rascc_mask_thinning $ifg_mask $ifg_filt_cc $ifg_width $ifg_mask_thin 3 $ifg_coh_thres $thres_1 $thres_max

        ## Unwrapping with validity mask
	GM mcf $ifg_filt $ifg_filt_cc $ifg_mask_thin $ifg_unw_thin $ifg_width 1 - - - - $ifg_patch_r $ifg_patch_az - $ifg_refrg $ifg_refaz 0

        ## Interpolate sparse unwrapped points to give unwrapping model
	GM interp_ad $ifg_unw_thin $ifg_unw_model $ifg_width 32 8 16 2

        ## Use model to unwrap filtered interferogram
	#if [ $ifg_refrg = "-" -a $ifg_refaz = "-" ]; then
	#    GM unw_model $ifg_filt $ifg_unw_model temp $ifg_width
	#else
	GM unw_model $ifg_filt $ifg_unw_model temp $ifg_width $ifg_refrg $ifg_refaz 0.0
	#fi

        # mask unwrapped interferogram for low coherence areas below threshold
        GM mask_data temp $ifg_width $ifg_unw $ifg_mask 0
        rm -f temp
    else
	#if [ $ifg_refrg = "-" -a $ifg_refaz = "-" ]; then
        #    GM mcf $ifg_filt $ifg_filt_cc $ifg_mask $ifg_unw $ifg_width 1 - - - - $ifg_patch_r $ifg_patch_az - - - 0
        #else
        GM mcf $ifg_filt $ifg_filt_cc $ifg_mask $ifg_unw $ifg_width 1 - - - - $ifg_patch_r $ifg_patch_az - $ifg_refrg $ifg_refaz 1
        #fi
    fi

    ## Convert LOS signal to vertical
    #GM dispmap $ifg_unw $rdc_dem $r_master_slc_par $ifg_off $disp 1
}


GEOCODE()
{
    echo " "
    echo "Geocoding interferogram..."
    echo " "
    width_in=`grep range_samp_1: $dem_diff | awk '{print $2}'`
    width_out=`grep width: $eqa_dem_par | awk '{print $2}'`

    ## Use bicubic spline interpolation for geocoded unwrapped interferogram
    GM geocode_back $ifg_unw $width_in $dem_lt_fine $ifg_unw_geocode_out $width_out - 1 0 - -
    # make quick-look png image 
    GM rasrmg $ifg_unw_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $ifg_unw_geocode_bmp
    GM convert $ifg_unw_geocode_bmp ${ifg_unw_geocode_bmp/.bmp}.png
    rm -f $ifg_unw_geocode_bmp

    ## Use bicubic spline interpolation for geocoded flattened interferogram
    # convert to float and extract phase
    GM cpx_to_real $ifg_flat $ifg_flat_float $width_in 4
    GM geocode_back $ifg_flat_float $width_in $dem_lt_fine $ifg_flat_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $ifg_flat_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $ifg_flat_geocode_bmp
    GM convert $ifg_flat_geocode_bmp ${ifg_flat_geocode_bmp/.bmp}.png
    rm -f $ifg_flat_geocode_bmp

    ## Use bicubic spline interpolation for geocoded filtered interferogram
    # convert to float and extract phase
    GM cpx_to_real $ifg_filt $ifg_filt_float $width_in 4
    GM geocode_back $ifg_filt_float $width_in $dem_lt_fine $ifg_filt_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $ifg_filt_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $ifg_filt_geocode_bmp
    GM convert $ifg_filt_geocode_bmp ${ifg_filt_geocode_bmp/.bmp}.png
    rm -f $ifg_filt_geocode_bmp

    ## Use bicubic spline interpolation for geocoded flat coherence file
    GM geocode_back $ifg_flat_cc $width_in $dem_lt_fine $ifg_flat_cc_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $ifg_flat_cc_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $ifg_flat_cc_geocode_bmp
    GM convert $ifg_flat_cc_geocode_bmp ${ifg_flat_cc_geocode_bmp/.bmp}.png
    rm -f $ifg_flat_cc_geocode_bmp

    ## Use bicubic spline interpolation for geocoded filt coherence file
    GM geocode_back $ifg_filt_cc $width_in $dem_lt_fine $ifg_filt_cc_geocode_out $width_out - 1 0 - -
    # make quick-look png image
    GM rasrmg $ifg_filt_cc_geocode_out - $width_out 1 1 0 10 10 1 1 0.35 0 1 $ifg_filt_cc_geocode_bmp
    GM convert $ifg_filt_cc_geocode_bmp ${ifg_filt_cc_geocode_bmp/.bmp}.png
    rm -f $ifg_filt_cc_geocode_bmp

    echo " "
    echo "Geocoded interferogram."
    echo " "

    ## Geotiff geocoded outputs
    if [ $ifg_geotiff == yes ]; then
	# unw
	GM data2geotiff $eqa_dem_par $ifg_unw_geocode_out 2 $ifg_unw_geocode_out.tif
	# flat ifg
	GM data2geotiff $eqa_dem_par $ifg_flat_geocode_out 2 $ifg_flat_geocode_out.tif
	# filt ifg
	GM data2geotiff $eqa_dem_par $ifg_filt_geocode_out 2 $ifg_filt_geocode_out.tif
	# flat cc
	GM data2geotiff $eqa_dem_par $ifg_flat_cc_geocode_out 2 $ifg_flat_cc_geocode_out.tif
	# filt cc
	GM data2geotiff $eqa_dem_par $ifg_filt_cc_geocode_out 2 $ifg_filt_cc_geocode_out.tif
    else
	:
    fi


    # Extract coordinates from DEM for plotting par file
    width=`grep width: $eqa_dem_par | awk '{print $2}'`
    lines=`grep nlines: $eqa_dem_par | awk '{print $2}'`
    lon=`grep corner_lon: $eqa_dem_par | awk '{print $2}'`
    post_lon=`grep post_lon: $eqa_dem_par | awk '{print $2}'`
    post_lon=`printf "%1.12f" $post_lon`
    lat=`grep corner_lat: $eqa_dem_par | awk '{print $2}'`
    post_lat=`grep post_lat: $eqa_dem_par | awk '{print $2}'`
    post_lat=`printf "%1.12f" $post_lat`
    gmt_par=ifg.rsc
    echo WIDTH $width > $gmt_par
    echo FILE_LENGTH $lines >> $gmt_par
    echo X_FIRST $lon >> $gmt_par
    echo X_STEP $post_lon >> $gmt_par
    echo Y_FIRST $lat >> $gmt_par
    echo Y_STEP $post_lat >> $gmt_par

    ## remove unnecessary files
    rm -f *flat0*
    rm -f *flat1*
    rm -f *sim0* *sim1*
    rm -f *int1*
}

DONE()
{
echo " "
echo "Processing Completed for Interferogram "$master-$slave"."
echo " "
}


## If statement controlling start and stop functions
if [ $ifg_begin == INT ]; then
    INT
    if [ $ifg_finish == FLAT ]; then
	echo "Done INT commands, finished working before FLAT."
	exit 0
    else
	FLAT
    fi
    if [ $ifg_finish == FILT ]; then
	echo "Done FLAT commands, finished working before FILT."
	exit 0
    else
	FILT
    fi
    if [ $ifg_finish == UNW ]; then
	echo "Done FILT commands, finished working before UNW."
	exit 0
    else
	UNW
    fi
    if [ $ifg_finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $ifg_finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $ifg_begin == FLAT ]; then
    FLAT
    if [ $ifg_finish == FILT ]; then
	echo "Done FLAT commands, finished working before FILT."
	exit 0
    else
	FILT
    fi
    if [ $ifg_finish == UNW ]; then
	echo "Done FILT commands, finished working before UNW."
	exit 0
    else
	UNW
    fi
    if [ $ifg_finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $ifg_finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $ifg_begin == FILT ]; then
    FILT
    if [ $ifg_finish == UNW ]; then
	echo "Done FILT commands, finished working before UNW."
	exit 0
    else
	UNW
    fi
    if [ $ifg_finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $ifg_finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $ifg_begin == UNW ]; then
    UNW
    if [ $ifg_finish == GEOCODE ]; then
	echo "Done UNW commands, finished working before GEOCODE."
	exit 0
    else
	GEOCODE
    fi
    if [ $ifg_finish == DONE ]; then
	DONE
    else
	:
    fi
elif [ $ifg_begin == GEOCODE ]; then
    GEOCODE
else
    echo "Begin code not recognised, check proc file."
fi


# script end
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2

