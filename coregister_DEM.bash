#!/bin/bash

display_usage() { 
    echo ""
    echo "*******************************************************************************"
    echo "* coregister_DEM: Script generates DEM coregistered to master SLC in radar    *"
    echo "*                 geometry.                                                   *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
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
    echo "*         Sarah Lawrie @ GA       12/09/2017, v1.7                            *"
    echo "*              Update processing to reflect example 'S1_Mexico_coreg_demo',   *"
    echo "*              This gives better refined offset estimates                     *"
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
    echo -e "Usage: coregister_DEM.bash [proc_file]"
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

## File names
dem_master_names
dem_file_names

cd $dem_dir

# modify the following parameters for multi-look values greater than 1
if [ $rlks -gt 1 ]; then
    dem_win1=`echo $dem_win1a $rlks | awk '{printf "%i\n", $1/$2}'`
    if [ $dem_win1 -lt 8 ]; then
	echo "increase dem_win value to increase window size (needs to be dem_win/rlks >=8)"
    else
	if [ $((dem_win1%2)) -eq 0 ]; then # dem_win1 must be an even number for 'offset_pwrm' to work
	    :
	else
	    dem_win1=`echo "$dem_win1 +1" | bc`
	fi
    fi
    dem_win2=`echo $dem_win2a $rlks | awk '{printf "%i\n", $1/$2}'`
    if [ $dem_win2 -lt 8 ]; then
	echo "increase dem_win value to increase window size (needs to be dem_win/rlks >=8)"
    else
	if [ $((dem_win2%2)) -eq 0 ]; then # dem_win1 must be an even number for 'offset_pwrm' to work
	    :
	else
	    dem_win2=`echo "$dem_win2 + 1" | bc`
	fi
    fi
    dem_patch_win=`echo $dem_patch_win1a $rlks | awk '{printf "%i\n", $1/$2}'`

    if [ $dem_patch_win -lt 128 ]; then
        dem_patch_win=128 # minimum size for init_offsetm
    fi
    dem_noff1=`echo $dem_noff1 $rlks | awk '{printf "%i\n", $1/$2}'`
    dem_noff2=`echo $dem_noff2 $rlks | awk '{printf "%i\n", $1/$2}'`
    if [ $dem_rpos != "-" ]; then
        dem_rpos=`echo $dem_rpos $rlks | awk '{printf "%i\n", $1/$2}'`
    fi
    if [ $dem_azpos != "-" ]; then
        dem_azpos=`echo $dem_azpos $rlks | awk '{printf "%i\n", $1/$2}'`
    fi
fi



# Functions 
COPY_SLC()
{
    cd $dem_master_dir
    ## Generate subsetted SLC and MLI files using parameters from gamma.proc
    GM SLC_copy $dem_master_slc $dem_master_slc_par $r_dem_master_slc $r_dem_master_slc_par 1 - 
    #GM SLC_copy $dem_master_slc $dem_master_slc_par $r_dem_master_slc $r_dem_master_slc_par 1 - $roff $rlines $azoff $azlines

    GM multi_look $r_dem_master_slc $r_dem_master_slc_par $r_dem_master_mli $r_dem_master_mli_par $rlks $alks 0

    ## Create raster for comparison purposes
    r_dem_master_mli_width=`grep range_samples: $r_dem_master_mli_par | awk '{print $2}'`
    GM raspwr $r_dem_master_mli $r_dem_master_mli_width 1 0 20 20 1. .35 1 $r_dem_master_mli_bmp
    GM convert $r_dem_master_mli_bmp ${r_dem_master_mli_bmp/.bmp}.png
    rm -f $r_dem_master_mli_bmp
}


# Determine oversampling factor for DEM coregistration
OVER_SAMPLE()
{
    cd $dem_dir
    dem_post=`grep post_lon $dem_par | awk '{printf "%.8f\n", $2}'`
    if [ $(bc <<< "$dem_post <= 0.00011111") -eq 1 ]; then # 0.4 arc second or smaller DEMs
	dem_ovr=1
    elif [ $(bc <<< "$dem_post <= 0.00027778") -eq 1 ]; then # between 0.4 and 1 arc second DEMs
	dem_ovr=4
    elif [ $(bc <<< "$dem_post < 0.00083333") -eq 1 ]; then # between 1 and 3 arc second DEMs
	dem_ovr=4
    elif [ $(bc <<< "$dem_post >= 0.00083333") -eq 1 ]; then # 3 arc second or larger DEMs
	dem_ovr=8
    else
	:
    fi
    echo " "
    echo "DEM oversampling factor: "$dem_ovr
    echo " "
}


# Generate DEM coregistered to master SLC in rdc geometry
GEN_DEM_RDC()
{
    cd $dem_dir
    # Derivation of initial geocoding look-up table and simulated SAR intensity image
    # note: gc_map can produce looking vector grids and shadow and layover maps

    if [ -e $eqa_dem_par ]; then
	echo " "
	echo  $eqa_dem_par" exists, removing file."
	echo " "
	rm -f $eqa_dem_par
    fi
    if [ -e $eqa_dem ]; then
	echo " "
	echo  $eqa_dem" exists, removing file."
	echo " "
	rm -f $eqa_dem
    fi

    ## Generate initial geocoding look up table and simulated SAR image
    GM gc_map $r_dem_master_mli_par - $dem_par $dem $eqa_dem_par $eqa_dem $dem_lt_rough $dem_ovr $dem_ovr $dem_eqa_sim_sar - - $dem_loc_inc - pix $dem_lsmap 8 2    
    #GM gc_map $r_dem_master_mli_par - $dem_par $dem $eqa_dem_par $eqa_dem $dem_lt_rough $dem_ovr $dem_ovr $dem_eqa_sim_sar - - - - - - 8 2

    # Convert landsat float file to same coordinates as DEM
    if [ $use_ext_image == yes ]; then
 	GM map_trans $dem_par $ext_image $eqa_dem_par $ext_image_flt 1 1 1 0 -
    else
        :
    fi

    dem_width=`grep width: $eqa_dem_par | awk '{print $2}'`
    r_dem_master_mli_width=`grep range_samples: $r_dem_master_mli_par | awk '{print $2}'`
    r_dem_master_mli_length=`grep azimuth_lines: $r_dem_master_mli_par | awk '{print $2}'`
    
    # Transform simulated SAR intensity image to radar geometry
    GM geocode $dem_lt_rough $dem_eqa_sim_sar $dem_width $dem_rdc_sim_sar $r_dem_master_mli_width $r_dem_master_mli_length 1 0 - - 2 $dem_rad_max -

    if [ $use_ext_image == yes ]; then
        # Transform external image to radar geometr
	GM geocode $dem_lt_rough $ext_image_flt $dem_width $ext_image_init_sar $r_dem_master_mli_width $r_dem_master_mli_length 1 0 - - 2 4 -
    else
        :
    fi
}


# Fine coregistration of master MLI and simulated SAR image
CREATE_DIFF_PAR_FULL()
{
    cd $dem_dir
    returns=$dem_dir/returns
    echo "" > $returns #default scene title
    echo $dem_noff1 $dem_noff2 >> $returns
    echo $dem_offset_measure >> $returns
    echo $dem_win1 $dem_win2 >> $returns 
    echo $dem_snr >> $returns
    echo >> $returns

    GM create_diff_par $r_dem_master_mli_par - $dem_diff 1 < $returns
    rm -f $returns 
    # remove temporary mli files (only required to generate diff par)
    rm -f $r_dem_master_mli $r_dem_master_mli_par
}


CREATE_DIFF_PAR()
{
    cd $dem_dir
    returns=$dem_dir/returns
    echo "" > $returns #default scene title
    echo $dem_noff1 $dem_noff2 >> $returns
    echo $dem_offset_measure >> $returns
    echo $dem_win1 $dem_win2 >> $returns 
    echo $dem_snr >> $returns
    echo >> $returns 
     
    # not using 'GM' for this command as it prints a standard output to the error.log, making dependent PBS jobs fail, force output to 'null' file
    #create_diff_par $r_dem_master_mli_par - $dem_diff 1 < $returns &> null
    GM create_diff_par $r_dem_master_mli_par - $dem_diff 1 < $returns
    rm -f $returns  
}



OFFSET_CALC()
{
    cd $dem_dir
    # The high accuracy of Sentinel-1 orbits requires only a static offset fit term rather than higher order polynomial terms
    if [ $sensor == S1 ]; then
	npoly=1
    else
	npoly=4
    fi

    #GM pixel_area $r_dem_master_mli_par $eqa_dem_par $eqa_dem $dem_lt_rough $dem_lsmap $dem_loc_inc $dem_pix_sig -
    GM init_offsetm pix $r_dem_master_mli $dem_diff 1 1 $dem_rpos $dem_azpos - - $dem_snr $dem_patch_win 1
    GM offset_pwrm pix $r_dem_master_mli $dem_diff $dem_offs $dem_ccp - - $dem_offsets 2 - - -
    GM offset_fitm $dem_offs $dem_ccp $dem_diff $dem_coffs $dem_coffsets - $npoly

    # Extract offset estimates to results file
    echo "DEM COREGISTRATION RESULTS" > $dem_check_file
    echo "" >> $dem_check_file
    echo "Offset Estimates" >> $dem_check_file
    echo "" >> $dem_check_file
    grep "final solution:" output.log >> $dem_check_file
    echo "" >> $dem_check_file
    grep "final range offset poly. coeff.:" output.log >> $dem_check_file
    grep "final azimuth offset poly. coeff.:" output.log >> $dem_check_file
    echo "" >> $dem_check_file
    grep "final range offset poly. coeff. errors:" output.log >> $dem_check_file
    grep "final azimuth offset poly. coeff. errors:" output.log >> $dem_check_file
    grep "final model fit std. dev. (samples) range:" output.log >> $dem_check_file


    # Refinement of initial geocoding look up table
    if [ $use_ext_image == yes ]; then
	GM gc_map_fine $dem_lt_rough $dem_width $dem_diff $dem_lt_fine 0
    else
	GM gc_map_fine $dem_lt_rough $dem_width $dem_diff $dem_lt_fine 1
    fi

    ## Generate sigma0 and gamma0 pixel normalisation area images
    GM pixel_area $r_dem_master_mli_par $eqa_dem_par $eqa_dem $dem_lt_fine $dem_lsmap $dem_loc_inc $dem_pix_sig $dem_pix_gam

    ## create raster for comparison with master mli raster
    r_dem_master_mli_width=`grep range_samples: $r_dem_master_mli_par | awk '{print $2}'`
    #GM raspwr $dem_pix_gam $r_dem_master_mli_width 1 0 20 20 1. .35 1 $dem_pix_gam_bmp
    #GM convert $dem_pix_gam_bmp ${dem_pix_gam_bmp/.bmp}.png
    #rm -f $dem_pix_gam_bmp

    ## Make sea-mask based on DEM zero values
    GM replace_values $eqa_dem 0.0001 0 temp $dem_width 0 2 1
    GM rashgt temp - $dem_width 1 1 0 1 1 100.0 - - - $seamask

    rm -f temp $dem_lt_rough $dem_offs $snr $dem_offsets $dem_coffs $dem_coffsets test1.dat test2.dat
}


GEOCODE()
{
    cd $dem_dir
    # Geocode map geometry DEM to radar geometry
    GM geocode $dem_lt_fine $eqa_dem $dem_width $rdc_dem $r_dem_master_mli_width $r_dem_master_mli_length 1 0 - - 2 $dem_rad_max -
    GM rashgt $rdc_dem $r_dem_master_mli $r_dem_master_mli_width 1 1 0 20 20 500. 1. .35 1 $rdc_dem.bmp
    GM convert $rdc_dem.bmp ${rdc_dem/.bmp}.png
    rm -f $rdc_dem.bmp

    # Geocode simulated SAR intensity image to radar geometry
    GM geocode $dem_lt_fine $dem_eqa_sim_sar $dem_width $dem_rdc_sim_sar $r_dem_master_mli_width $r_dem_master_mli_length 1 0 - - 2 $dem_rad_max -

    # Geocode local incidence angle image to radar geometry
    GM geocode $dem_lt_fine $dem_loc_inc $dem_width $dem_rdc_inc $r_dem_master_mli_width $r_dem_master_mli_length 1 0 - - 2 $dem_rad_max -

    # Geocode external image to radar geometry
    if [ $use_ext_image == yes ]; then
	GM geocode $dem_lt_fine $ext_image_flt $dem_width $ext_image_sar $r_dem_master_mli_width $r_dem_master_mli_length 1 0 - - 2 $dem_rad_max -
    else 
	:
    fi
}


# Create look vector files
LOOK_VECTOR()
{
    cd $dem_dir
    # not using 'GM' for this command as it prints a standard output to the error.log, making dependent PBS jobs fail, force output to 'null' file
    #look_vector $r_dem_master_slc_par - $eqa_dem_par $eqa_dem $dem_lv_theta $dem_lv_phi  &> null
    GM look_vector $r_dem_master_slc_par - $eqa_dem_par $eqa_dem $dem_lv_theta $dem_lv_phi
}


# Create geotif of master mli for subsetting
GEOTIF_FULL()
{
    cd $dem_master_dir
    r_dem_master_mli_eqa=$dem_master_dir/$r_dem_master_mli_name"_eqa_full.mli"
    r_dem_master_mli_geo=$dem_master_dir/$r_dem_master_mli_name"_eqa_mli_full.tif"
    width_in=`grep range_samp_1: $dem_diff | awk '{print $2}'`
    width_out=`grep width: $eqa_dem_par | awk '{print $2}'`
    
    GM geocode_back $r_dem_master_mli $width_in $dem_lt_fine $r_dem_master_mli_eqa $width_out - 0 0 - -
    GM data2geotiff $eqa_dem_par $r_dem_master_mli_eqa 2 $r_dem_master_mli_geo 0.0
}

GEOTIF()
{
    cd $dem_master_dir
    r_dem_master_mli_eqa=$dem_master_dir/$r_dem_master_mli_name"_eqa.mli"
    r_dem_master_mli_geo=$dem_master_dir/$r_dem_master_mli_name"_eqa_mli.tif"
    width_in=`grep range_samp_1: $dem_diff | awk '{print $2}'`
    width_out=`grep width: $eqa_dem_par | awk '{print $2}'`
    
    GM geocode_back $r_dem_master_mli $width_in $dem_lt_fine $r_dem_master_mli_eqa $width_out - 0 0 - -
    GM data2geotiff $eqa_dem_par $r_dem_master_mli_eqa 2 $r_dem_master_mli_geo 0.0
}



COPY_SLC
OVER_SAMPLE
GEN_DEM_RDC
CREATE_DIFF_PAR
OFFSET_CALC
GEOCODE
LOOK_VECTOR


# script end 
####################

## Copy errors to NCI error file (.e file)
rm -rf null
cat error.log 1>&2
