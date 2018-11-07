#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* coregister_S1_slave_SLC: Coregisters Sentinel-1 IWS SLC to chosen master    *"
    echo "*                          SLC geometry                                       *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [slave]      slave scene ID (eg. 20120520)                          *"
    echo "*                                                                             *"
    echo "* author: Matt Garthwaite @ G    12/05/2015, v1.0                             *"
    echo "*         Sarah Lawrie @ GA      23/12/2015, v1.1                             *"
    echo "*               Change snr to cross correlation parameters (process changed   *"
    echo "*               in GAMMA version Dec 2015)                                    *"
    echo "*         Negin Moghaddam @ GA    16/05/2016, v1.2                            *"
    echo "*               Updating the code for Sentinel-1 slave coregistration         *"
    echo "*               Refinement to the azimuth offset estimation                   *"
    echo "*               Intial interferogram generation at each stage of the azimuth  *"
    echo "*               offset refinement                                             *"
    echo "*               In case of LAT package availability, S1_Coreg_TOPS is         *"
    echo "*               suggested.                                                    *"
    echo "*         Sarah Lawrie @ GA       19/09/2017, v2.0                            *"
    echo "*               To improve coregistration, re-write script to mirror GAMMA    *"
    echo "*               example scripts 'S1_coreg_TOPS' and 'S1_coreg_overlap'.       *"
    echo "*         Sarah Lawrie @ GA       13/08/2018, v2.1                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: coregister_S1_slave_SLC.bash [proc_file] [slave]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

if [ $2 -lt "10000000" ]; then
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    slave=$2
fi

# slave list index is given to select slave to coregister to
if [ $# -eq 3 ]; then
   list_idx=$3
   echo $list_idx
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
PBS_processing_details $project $track $slave

######################################################################

## File names
dem_master_names
dem_file_names
slave_file_names
s1_slave_file_names
source ~/repo/gamma_insar/coregister_S1_slave_functions

cd $slave_dir

# make tab files
if [ ! -f $master_slc_tab ]; then
    echo $master_slc1 $master_slc_par1 $master_tops_par1 > $master_slc_tab
    echo $master_slc2 $master_slc_par1 $master_tops_par2 >> $master_slc_tab
    echo $master_slc3 $master_slc_par1 $master_tops_par3 >> $master_slc_tab
fi

echo $slave_slc1 $slave_slc_par1 $slave_tops_par1 > $slave_slc_tab
echo $slave_slc2 $slave_slc_par2 $slave_tops_par2 >> $slave_slc_tab
echo $slave_slc3 $slave_slc_par3 $slave_tops_par3 >> $slave_slc_tab

echo $r_slave_slc1 $r_slave_slc_par1 $r_slave_tops_par1 > $r_slave_slc_tab
echo $r_slave_slc2 $r_slave_slc_par2 $r_slave_tops_par2 >> $r_slave_slc_tab
echo $r_slave_slc3 $r_slave_slc_par3 $r_slave_tops_par3 >> $r_slave_slc_tab

master_slc_width=`grep range_samples: $r_dem_master_slc_par | cut -d ":" -f 2`
master_slc_nlines=`grep azimuth_lines: $r_dem_master_slc_par | cut -d ":" -f 2`
master_mli_width=`grep range_samples: $r_dem_master_mli_par | cut -d ":" -f 2`

temp_file=$slave"_temp"

echo "" > $temp_file
echo "" >> $temp_file
echo $slave >> $temp_file
echo "" >> $temp_file


##### Derived from 'S1_coreg_TOPS' example GAMMA script


### Determine lookup table based on orbit data and DEM
GM rdc_trans $r_dem_master_mli_par $rdc_dem $slave_mli_par $slave_lt

### Masking of lookup table (used for the matching refinement estimation) - does not use LAT programs as a polygon file is not provided
ln -s $slave_lt $slave_lt_masked

### Determine starting and ending rows and cols
r1=0
r2=$master_slc_width
a1=0
a2=$master_slc_nlines

# reduce offset estimation to 64 x 64 samples max
rstep1=64
rstep2=`echo $r1 $r2 | awk '{printf "%d", ($2-$1)/64}'`
if [ $rstep1 -gt $rstep2 ]; then
    rstep=$rstep1
else
    rstep=$rstep2
fi
azstep1=32
azstep2=`echo $a1 $a2 | awk '{printf "%d", ($2-$1)/64}'`
if [ $azstep1 -gt $azstep2 ]; then
    azstep=$azstep1
else
    azstep=$azstep2
fi

#########################################################################################
#########################################################################################


### Iterative improvement of refinement offsets between master SLC and resampled slave RSLC using intensity matching (offset_pwr_tracking)
echo "Iterative improvement of refinement offset using matching:" >> $temp_file
echo "" >> $temp_file

if [ -e $slave_off ]; then
    rm -rf $slave_off
fi
GM create_offset $r_dem_master_slc_par $slave_slc_par $slave_off 1 $rlks $alks 0


# iterate while azimuth correction > 0.01 SLC pixel
daz10000=10000
it=1
while [[ "$daz10000" -gt 100 || "$daz10000" -lt -100 ]] && [ "$it" -le "$slave_niter" ]; do
    cp -rf $slave_off $slave_off_start

    GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $r_dem_master_slc_par $slave_lt_masked $r_dem_master_mli_par $slave_mli_par $slave_off_start $r_slave_slc_tab $r_slave_slc $r_slave_slc_par
    if [ -e $slave_doff ]; then
	rm -rf $slave_doff
    fi

    GM create_offset $r_dem_master_slc_par $slave_slc_par $slave_doff 1 $rlks $alks 0

    # no oversampling as this is not done well because of the doppler ramp
    GM offset_pwr_tracking $r_dem_master_slc $r_slave_slc $r_dem_master_slc_par $r_slave_slc_par $slave_doff $slave_offs $slave_snr 128 64 - 1 0.2 $rstep $azstep $r1 $r2 $a1 $a2

    GM offset_fit $slave_offs $slave_snr $slave_doff - - 0.2 1 0
    grep "final model fit std. dev. (samples) range:" output.log > temp1
    grep -F 'final' temp1 | awk "NR==$it {print}" > temp2
    range_stdev=`awk '$1 == "final" {print $8}' temp2`
    azimuth_stdev=`awk '$1 == "final" {print $10}' temp2`

    daz10000=`awk '$1 == "azimuth_offset_polynomial:" {printf "%d", $2*10000}' $slave_doff`
    daz=`awk '$1 == "azimuth_offset_polynomial:" {print $2}' $slave_doff`
    daz_mli=`echo "$daz" "$alks" | awk '{printf "%f", $1/$2}'`

    # lookup table refinement
    # determine range and azimuth corrections for lookup table (in mli pixels)
    dr=`awk '$1 == "range_offset_polynomial:" {print $2}' $slave_doff`
    dr_mli=`echo $dr $rlks | awk '{printf "%f", $1/$2}'`
    daz=`awk '$1 == "azimuth_offset_polynomial:" {print $2}' $slave_doff`
    daz_mli=`echo $daz $alks | awk '{printf "%f", $1/$2}'`
    echo "dr_mli: "$dr_mli"    daz_mli: "$daz_mli > $slave_ref_iter.$it

    if [ -e $slave_diff_par ]; then
	rm -rf $slave_diff_par
    fi
    GM create_diff_par $r_dem_master_mli_par $r_dem_master_mli_par $slave_diff_par 1 0
    GM set_value $slave_diff_par $slave_diff_par "range_offset_polynomial" "${dr_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"
    GM set_value $slave_diff_par $slave_diff_par "azimuth_offset_polynomial" "${daz_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"
    cp -rf $slave_diff_par $slave_diff_par.$it

    # update unmasked lookup table
    mv -f $slave_lt $slave_lt.tmp.$it
    GM gc_map_fine $slave_lt.tmp.$it $master_mli_width $slave_diff_par $slave_lt 1

    echo "    matching_iteration_"$it": "$daz $dr $daz_mli $dr_mli" (daz dr daz_mli dr_mli)" >> $temp_file
    echo "    matching_iteration_stdev_"$it": "$azimuth_stdev $range_stdev" (azimuth_stdev range_stdev)" >> $temp_file
    it=$(($it+1))
done

#########################################################################################
#########################################################################################

# TF: commented since this results in zero phase values for most bursts and
#     results in incorrect processing for S1_COREG_OVERLAP (see below)
#     needed at all?

### Iterative improvement of azimuth refinement using spectral diversity method
    # works with IW1, IW2 and IW3 only (can be expanded to work with swaths 4 and 5)
#
#if [ -e $slave_az_ovr_poly ]; then
#    rm -rf $slave_az_ovr_poly
#fi
#POLY_OVERLAP $master_slc_tab $rlks $alks $slave_az_ovr_poly

## use LAT package here
#GM poly_math $r_dem_master_mli $slave_az_ovr $master_mli_width $slave_az_ovr_poly - 1 0.0 1.0
#GM raspwr $slave_az_ovr $master_mli_width 1 0 1 1 1.0 0.35 1 $slave_az_ovr_ras

## mask the lookup table
#GM mask_class $slave_az_ovr_ras $slave_lt $slave_lt_az_ovr 1 1 1 1 0 0.0 0.0


#########################################################################################

echo "" >> $temp_file
echo "Iterative improvement of refinement offset azimuth overlap regions:" >> $temp_file
echo "" >> $temp_file

# initialize the output text file
echo "    Burst Overlap Results" > $slave_ovr_res
echo "        thresholds applied: cc_thresh: "$slave_s1_cct",  ph_fraction_thresh: "$slave_s1_frac", ph_stdev_thresh (rad): "$slave_s1_stdev  >> $slave_ovr_res
echo "" >> $slave_ovr_res
echo "        IW  overlap  ph_mean ph_stdev ph_fraction   (cc_mean cc_stdev cc_fraction)    weight" >> $slave_ovr_res
echo "" >> $slave_ovr_res

# iterate while azimuth correction >= 0.0005 SLC pixel
daz10000=10000
it=1
while [[ "$daz10000" -gt 5 || "$daz10000" -lt -5 ]] && [ "$it" -le "$slave_niter" ]; do
    cp -rf $slave_off $slave_off_start

# TF don't use azimuth refined look-up table, but original one
    #GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $r_dem_master_slc_par $slave_lt_az_ovr $r_dem_master_mli_par $slave_mli_par $slave_off_start $r_slave_slc_tab $r_slave_slc $r_slave_slc_par
    GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $r_dem_master_slc_par $slave_lt $r_dem_master_mli_par $slave_mli_par $slave_off_start $r_slave_slc_tab $r_slave_slc $r_slave_slc_par

    # coregister to nearest slave if list_idx is given
    if [ $list_idx == "-" ]; then # coregister to master
      S1_COREG_OVERLAP $master_slc_tab $r_slave_slc_tab $slave_off_start $slave_off $slave_s1_cct $slave_s1_frac $slave_s1_stdev > $slave_off.az_ovr.$it.out
    elif [ $list_idx == "0" ]; then # coregister to adjacent slave
      # get slave position in slaves.list
      slave_pos=`grep -n $slave $slave_list | cut -f1 -d:`
      if [ $slave -lt $master_scene ]; then
        coreg_pos=$(($slave_pos+1))
        coreg_slave=`head -n $coreg_pos $slave_list | tail -1`
      elif [ $rerun_slave -gt $master_scene ]; then
        coreg_pos=$(($slave_pos-1))
        coreg_slave=`head -n $coreg_pos $slave_list | tail -1`
      fi
      r_coreg_slave_tab=$slc_dir/$coreg_slave/r$coreg_slave"_"$polar"_tab"
      S1_COREG_OVERLAP $master_slc_tab $r_slave_slc_tab $slave_off_start $slave_off $slave_s1_cct $slave_s1_frac $slave_s1_stdev $r_coreg_slave_tab > $slave_off.az_ovr.$it.out
    else # coregister to slave image with short temporal baseline
      #  take the first/last slave of the previous list for coregistration
      prev_list_idx=$(($list_idx-1))
      if [ $slave -lt $master_scene ]; then
         coreg_slave=`head $list_dir/slaves$prev_list_idx.list -n1`
      elif [ $slave -gt $master_scene ]; then
         coreg_slave=`tail $list_dir/slaves$prev_list_idx.list -n1`
      fi
      r_coreg_slave_tab=$slc_dir/$coreg_slave/r$coreg_slave"_"$polar"_tab"
      S1_COREG_OVERLAP $master_slc_tab $r_slave_slc_tab $slave_off_start $slave_off $slave_s1_cct $slave_s1_frac $slave_s1_stdev $r_coreg_slave_tab > $slave_off.az_ovr.$it.out
    fi

    daz=`awk '$1 == "azimuth_pixel_offset" {print $2}' $slave_off.az_ovr.$it.out`
    daz10000=`awk '$1 == "azimuth_pixel_offset" {printf "%d", $2*10000}' $slave_off.az_ovr.$it.out`

    cp -rf $slave_off $slave_off.az_ovr.$it

    echo "    az_ovr_iteration_"$it": "$daz" (daz in SLC pixel)" >> $temp_file
    echo "" >> $temp_file
    it=$(($it+1))
done

### Copy overlap results to overall slave coregistration check file
paste $temp_file > temp1
paste $slave_ovr_res >> temp1
paste temp1 >> $slave_check_file
rm -rf temp1 $temp_file

#########################################################################################
#########################################################################################

### Resample full data set
GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $r_dem_master_slc_par $slave_lt $r_dem_master_mli_par $slave_mli_par $slave_off $r_slave_slc_tab $r_slave_slc $r_slave_slc_par

##############################################################

### Multilook coregistered slave
GM multi_look $r_slave_slc $r_slave_slc_par $r_slave_mli $r_slave_mli_par $rlks $alks

### Full-res MLI for CR analysis 
#GM multi_look $slv_rslc $slv_rslc_par $slv_dir/r$slv_slc_name"_1rlks.mli" $slv_dir/r$slv_slc_name"_1rlks.mli.par" 1 1

## Generate Gamma0 backscatter image for slave scene according to equation in Section 10.6 of Gamma Geocoding and Image Registration Users Guide
GM float_math $r_slave_mli $ellip_pix_sigma0 temp1 $master_mli_width 2
GM float_math temp1 $dem_pix_gam $slave_gamma0 $master_mli_width 3
rm -f temp1

## Back-geocode Gamma0 backscatter product to map geometry
dem_width=`grep width: $eqa_dem_par | awk '{print $2}'`
GM geocode_back $slave_gamma0 $master_mli_width $dem_lt_fine $slave_gamma0_eqa $dem_width - 1 0 - -
# make quick-look png image
GM raspwr $slave_gamma0_eqa $dem_width 1 0 20 20 - - - $slave_gamma0_eqa_bmp
GM convert $slave_gamma0_eqa_bmp -transparent black ${slave_gamma0_eqa_bmp/.bmp}.png
name=`ls *eqa*gamma0.png`
GM kml_map $name $eqa_dem_par ${name/.png}.kml
rm -f $slave_gamma0_eqa_bmp

### Clean up temp files
#rm -rf $slave_lt.tmp.?
#rm -rf $slave_lt_masked
#rm -rf $slave_ref_iter.?
#rm -rf $slave_diff_par.?
#rm -rf $slave_lt.tmp.?
#rm -rf $slave_snr
#rm -rf $slave_offs
#rm -rf $slave_doff
#rm -rf $slave_lt
#rm -rf $slave_az_ovr_poly
#rm -rf $slave_az_ovr
#rm -rf $slave_off_start
#rm -rf $slave_lt_az_ovr
#rm -rf $slave_az_ovr_ras
#rm -rf *.off.az_ovr.?.out
#rm -rf *.off.az_ovr.?


# script end
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2














