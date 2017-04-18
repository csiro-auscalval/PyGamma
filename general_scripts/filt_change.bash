#!/bin/bash


qsub -I -X -lwalltime=02:00:00,mem=10GB,ncpus=6,wd -q express



# modify filtering parameters

int=20121205-20121227

expon=0.4
ccwin=5 #must be odd, max 15
filtwin=256 #8, 16,32, 64, 128, 256, 512



dir=/g/data1/dg9/INSAR_ANALYSIS/SURAT/TSX/GAMMA
track=T140A

int_dir=$dir/$track/INT/$int
slc_dir=$dir/$track/SLC
dem_dir=$dir/$track/DEM
proc_file=$dir/$track.proc
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
rlks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
patch_r=`grep Patches_range= $proc_file | cut -d "=" -f 2`
patch_az=`grep Patches_azimuth= $proc_file | cut -d "=" -f 2`
coh_thres=`grep Coherence_threshold= $proc_file | cut -d "=" -f 2`
mas=`echo $int | awk -F"-" '{print $1}'`
slv=`echo $int | awk -F"-" '{print $2}'`
mas_mli_par=$slc_dir/$mas/r$mas"_"$polar"_"$rlks"rlks.mli.par"
int_width=`grep range_samples $mas_mli_par | awk '{print $2}'`
dem_par=$dem_dir/$master"_"$polar"_"$rlks"rlks_utm.dem.par"
width_out=`grep width: $dem_par | awk '{print $2}'`
thres_1=`echo $coh_thres + 0.2 | bc`
thres_max=`echo $thres_1 + 0.2 | bc`

mv $int"_"$polar"_"$rlks"rlks.unw" $int"_"$polar"_"$rlks"rlks_org.unw" 

view_unw $int"_"$polar"_"$rlks"rlks_org.unw" &



cc_wave $int_dir/$int"_"$polar"_"$rlks"rlks_flat1.int" - - $int_dir/$int"_"$polar"_"$rlks"rlks_flat0.cc" $int_width $ccwin $ccwin 1

rascc_mask $int_dir/$int"_"$polar"_"$rlks"rlks_flat0.cc" - $int_width 1 1 0 1 1 0.4 0 - - - - 1 $int_dir/$int"_"$polar"_"$rlks"rlks_flat0_cc_mask.ras"

extract_gcp $dem_dir/$master"_"$polar"_"$rlks"rlks_rdc.dem" $int_dir/$int"_"$polar"_"$rlks"rlks_off.par" $int_dir/$int"_"$polar"_"$rlks"rlks.gcp" 100 100 $int_dir/$int"_"$polar"_"$rlks"rlks_flat0_cc_mask.ras"

gcp_phase $int_dir/$int"_"$polar"_"$rlks"rlks_flat.int1.unw" $int_dir/$int"_"$polar"_"$rlks"rlks_off.par" $int_dir/$int"_"$polar"_"$rlks"rlks.gcp" $int_dir/$int"_"$polar"_"$rlks"rlks.gcp_ph" 3

base_ls $slc_dir/$mas/r$mas"_"$polar.slc.par $int_dir/$int"_"$polar"_"$rlks"rlks_off.par" $int_dir/$int"_"$polar"_"$rlks"rlks.gcp_ph" $int_dir/$int"_"$polar"_"$rlks"rlks_base.par" 0 1 1 1 1 1.0

base_perp $int_dir/$int"_"$polar"_"$rlks"rlks_base.par" $slc_dir/$mas/r$mas"_"$polar.slc.par $int_dir/$int"_"$polar"_"$rlks"rlks_off.par"

phase_sim $slc_dir/$mas/r$mas"_"$polar.slc.par $int_dir/$int"_"$polar"_"$rlks"rlks_off.par" $int_dir/$int"_"$polar"_"$rlks"rlks_base.par" $dem_dir/$master"_"$polar"_"$rlks"rlks_rdc.dem" $int_dir/$int"_"$polar"_"$rlks"rlks_sim.unw" 0 1

sub_phase $int_dir/$int"_"$polar"_"$rlks"rlks.int" $int_dir/$int"_"$polar"_"$rlks"rlks_sim.unw" $int_dir/$int"_"$polar"_"$rlks"rlks_diff.par" $int_dir/$int"_"$polar"_"$rlks"rlks_flat.int" 1 0




cc_wave $int_dir/$int"_"$polar"_"$rlks"rlks_flat.int" $slc_dir/$mas/r$mas"_"$polar"_"$rlks"rlks.mli" $slc_dir/$slv/r$slv"_"$polar"_"$rlks"rlks.mli" $int_dir/$int"_"$polar"_"$rlks"rlks_flat.cc" $int_width $ccwin $ccwin 1

adf $int_dir/$int"_"$polar"_"$rlks"rlks_flat.int" $int_dir/$int"_"$polar"_"$rlks"rlks_filt.int" $int_dir/$int"_"$polar"_"$rlks"rlks_filt.cc" $int_width $expon $filtwin $ccwin - 0 - -




rascc_mask $int_dir/$int"_"$polar"_"$rlks"rlks_filt.cc" - $int_width 1 1 0 1 1 $coh_thres 0 - - - - 1 $int_dir/$int"_"$polar"_"$rlks"rlks_mask.ras"

rascc_mask_thinning $int_dir/$int"_"$polar"_"$rlks"rlks_mask.ras" $int_dir/$int"_"$polar"_"$rlks"rlks_filt.cc" $int_width $int_dir/$int"_"$polar"_"$rlks"rlks_mask_thin.ras" 3 $coh_thres $thres_1 $thres_max

mcf $int_dir/$int"_"$polar"_"$rlks"rlks_filt.int" $int_dir/$int"_"$polar"_"$rlks"rlks_filt.cc" $int_dir/$int"_"$polar"_"$rlks"rlks_mask_thin.ras" $int_dir/$int"_"$polar"_"$rlks"rlks_thin.unw" $int_width 1 - - - - $patch_r $patch_az

interp_ad $int_dir/$int"_"$polar"_"$rlks"rlks_thin.unw" $int_dir/$int"_"$polar"_"$rlks"rlks_model.unw" $int_width 32 8 16 2

unw_model $int_dir/$int"_"$polar"_"$rlks"rlks_filt.int" $int_dir/$int"_"$polar"_"$rlks"rlks_model.unw" $int_dir/$int"_"$polar"_"$rlks"rlks.unw" $int_width

view_unw $int"_"$polar"_"$rlks"rlks.unw" & 



geocode_back $int_dir/$int"_"$polar"_"$rlks"rlks.unw" $int_width $dem_dir/$master"_"$polar"_"$rlks"rlks_fine_utm_to_rdc.lt" $int_dir/$int"_"$polar"_"$rlks"rlks_utm.unw" $width_out - 1 0 - -

cpx_to_real $int_dir/$int"_"$polar"_"$rlks"rlks_filt.int" $int_dir/$int"_"$polar"_"$rlks"rlks_filt_int.flt" $int_width 4

geocode_back $int_dir/$int"_"$polar"_"$rlks"rlks_filt_int.flt" $int_width $dem_dir/$master"_"$polar"_"$rlks"rlks_fine_utm_to_rdc.lt" $int_dir/$int"_"$polar"_"$rlks"rlks_filt_int_utm.flt" $width_out - 1 0 - -

geocode_back $int_dir/$int"_"$polar"_"$rlks"rlks_filt.cc" $int_width $dem_dir/$master"_"$polar"_"$rlks"rlks_fine_utm_to_rdc.lt" $int_dir/$int"_"$polar"_"$rlks"rlks_filt_utm.cc" $width_out - 1 0 - -

geocode_back $int_dir/$int"_"$polar"_"$rlks"rlks_flat.cc" $int_width $dem_dir/$master"_"$polar"_"$rlks"rlks_fine_utm_to_rdc.lt" $int_dir/$int"_"$polar"_"$rlks"rlks_flat_utm.cc" $width_out - 1 0 - -