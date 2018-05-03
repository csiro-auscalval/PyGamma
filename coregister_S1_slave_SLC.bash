#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* coregister_S1_slave_SLC: Coregisters Sentinel-1 IWS SLC to chosen master    *"
    echo "*                          SLC geometry                                       *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [slave]      slave scene ID (eg. 20120520)                          *"
    echo "*         [rlks]       range multi-look value (for SLCs: from *.mli.par file  *"
    echo "*                      or for ifms: from proc file)                           *"
    echo "*         [alks]       azimuth multi-look value (for SLCs: from *.mli.par     *"
    echo "*                      file or for ifms: from proc file)                      *"
    echo "*                                                                             *"
    echo "* author: Matt Garthwaite @ GA       12/05/2015, v1.0                         *"
    echo "*         Sarah Lawrie @ GA          23/12/2015, v1.1                         *"
    echo "*               Change snr to cross correlation parameters (process changed   *"
    echo "*               in GAMMA version Dec 2015)                                    *"
    echo "*         Negin Moghaddam @ GA       16/05/2016, v1.2                         *"
    echo "*               Updating the code for Sentinel-1 slave coregistration         *"
    echo "*               Refinement to the azimuth offset estimation                   *"
    echo "*               Intial interferogram generation at each stage of the azimuth  *"
    echo "*               offset refinement                                             *"
    echo "*               In case of LAT package availability, S1_Coreg_TOPS is         *"
    echo "*               suggested.                                                    *"
    echo "*         Sarah Lawrie @ GA          19/09/2017, v2.0                         *"
    echo "*               To improve coregistration, re-write script to mirror GAMMA    *"
    echo "*               example scripts 'S1_coreg_TOPS' and 'S1_coreg_overlap'.       *"
    echo "*******************************************************************************"
    echo -e "Usage: coregister_S1_slave_SLC.bash [proc_file] [slave] [rlks] [alks]"
    }

if [ $# -lt 4 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
slv=$2
rlks=$3
alks=$4

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
mas=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`

#ccp=`grep slv_snr= $proc_file | cut -d "=" -f 2`
#npoly=`grep coreg_model_params= $proc_file | cut -d "=" -f 2`
#win=`grep coreg_window_size= $proc_file | cut -d "=" -f 2`
#nwin=`grep coreg_num_windows= $proc_file | cut -d "=" -f 2`
#ovr=`grep coreg_oversampling= $proc_file | cut -d "=" -f 2`
niter=`grep coreg_num_iterations= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $slv $rlks"rlks" $alks"alks" 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING_SCENE: "$project $track_dir $slv $rlks"rlks" $alks"alks"
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

mas_dir=$slc_dir/$mas
slv_dir=$slc_dir/$slv

## files located in SLC directories
mas_slc_name=$mas"_"$polar
mas_mli_name=$mas"_"$polar"_"$rlks"rlks"

mas_slc=$mas_dir/$mas_slc_name.slc
mas_slc_par=$mas_slc.par
mas_slc_tab=$mas_dir/$mas_slc_name"_tab"

mas_slc1=$mas_slc_name"_IW1.slc"
mas_slc1_par=$mas_slc1.par
mas_tops_par1=$mas_slc1.TOPS_par
mas_slc2=$mas_slc_name"_IW2.slc"
mas_slc2_par=$mas_slc2.par
mas_tops_par2=$mas_slc2.TOPS_par
mas_slc3=$mas_slc_name"_IW3.slc"
mas_slc3_par=$mas_slc3.par
mas_tops_par3=$mas_slc3.TOPS_par
mas_mli=$mas_dir/$mas_mli_name.mli
mas_mli_par=$mas_mli.par

mas_rslc=$mas_dir/r$mas_slc_name.slc 
mas_rslc_par=$mas_rslc.par
mas_rmli=$mas_dir/r$mas_mli_name.mli
mas_rmli_par=$mas_rmli.par

slv_slc_name=$slv"_"$polar
slv_mli_name=$slv"_"$polar"_"$rlks"rlks"

slv_slc=$slv_dir/$slv_slc_name.slc
slv_slc_par=$slv_slc.par
slv_slc_tab=$slv_dir/$slv_slc_name"_tab"

slv_slc1=$slv_slc_name"_IW1.slc"
slv_slc1_par=$slv_slc1.par
slv_tops_par1=$slv_slc1.TOPS_par
slv_slc2=$slv_slc_name"_IW2.slc"
slv_slc2_par=$slv_slc2.par
slv_tops_par2=$slv_slc2.TOPS_par
slv_slc3=$slv_slc_name"_IW3.slc"
slv_slc3_par=$slv_slc3.par
slv_tops_par3=$slv_slc3.TOPS_par
slv_mli=$slv_dir/$slv_mli_name.mli
slv_mli_par=$slv_mli.par

slv_rslc=$slv_dir/r$slv_slc_name.slc 
slv_rslc_par=$slv_rslc.par
slv_rslc_tab=$slv_dir/r$slv_slc_name"_tab"
slv_rmli=$slv_dir/r$slv_mli_name.mli
slv_rmli_par=$slv_rmli.par

slv_rslc1=r$slv_slc_name"_IW1.slc"
slv_rslc1_par=$slv_rslc1.par
slv_rtops_par1=$slv_rslc1.TOPS_par
slv_rslc2=r$slv_slc_name"_IW2.slc"
slv_rslc2_par=$slv_rslc2.par
slv_rtops_par2=$slv_rslc2.TOPS_par
slv_rslc3=r$slv_slc_name"_IW3.slc"
slv_rslc3_par=$slv_rslc3.par
slv_rtops_par3=$slv_rslc3.TOPS_par

lt=$slv_dir/$mas-$slv_mli_name.lt
off=$slv_dir/$mas-$slv_mli_name.off
offs=$slv_dir/$mas-$slv_mli_name.offs
snr=$slv_dir/$mas-$slv_mli_name.snr
doff=$slv_dir/$mas-$slv_mli_name.doff
ref_iter=$slv_dir/$mas-$slv_mli_name.ref_iter
diff_par=$slv_dir/$mas-$slv_mli_name.diff_par
ovr_res=$slv_dir/$mas-$slv_mli_name.ovr_results


## files located in DEM directory
rdc_dem=$dem_dir/$mas_mli_name"_rdc.dem"

## Coregistration results file
check_file=$proj_dir/$track_dir/slave_coreg_results"_"$rlks"rlks_"$alks"alks.txt"

cd $slv_dir

## Determine range and azimuth looks in MLI
echo " "
echo "MLI range and azimuth looks: "$rlks $alks
echo " "

#-------------------------

# make tab files
echo $mas_dir/$mas_slc1 $mas_dir/$mas_slc1_par $mas_dir/$mas_tops_par1 > $mas_slc_tab
echo $mas_dir/$mas_slc2 $mas_dir/$mas_slc2_par $mas_dir/$mas_tops_par2 >> $mas_slc_tab
echo $mas_dir/$mas_slc3 $mas_dir/$mas_slc3_par $mas_dir/$mas_tops_par3 >> $mas_slc_tab

echo $slv_dir/$slv_slc1 $slv_dir/$slv_slc1_par $slv_dir/$slv_tops_par1 > $slv_slc_tab
echo $slv_dir/$slv_slc2 $slv_dir/$slv_slc2_par $slv_dir/$slv_tops_par2 >> $slv_slc_tab
echo $slv_dir/$slv_slc3 $slv_dir/$slv_slc3_par $slv_dir/$slv_tops_par3 >> $slv_slc_tab

echo $slv_dir/$slv_rslc1 $slv_dir/$slv_rslc1_par $slv_dir/$slv_rtops_par1 > $slv_rslc_tab
echo $slv_dir/$slv_rslc2 $slv_dir/$slv_rslc2_par $slv_dir/$slv_rtops_par2 >> $slv_rslc_tab
echo $slv_dir/$slv_rslc3 $slv_dir/$slv_rslc3_par $slv_dir/$slv_rtops_par3 >> $slv_rslc_tab

mas_rmli_width=`grep range_samples: $mas_rmli_par | cut -d ":" -f 2`
mas_rmli_nlines=`grep azimuth_lines: $mas_rmli_par | cut -d ":" -f 2`
mas_rslc_width=`grep range_samples: $mas_rslc_par | cut -d ":" -f 2`
mas_rslc_nlines=`grep azimuth_lines: $mas_rslc_par | cut -d ":" -f 2`

echo "Sentinel-1 TOPS coregistration quality file" > $check_file
echo "###########################################" >> $check_file
echo " " >> $check_file
echo $slv >> $check_file
echo "" >> $check_file


#### function for determining phase offsets for sub-swath overlap regions of first/second sub-swaths
OFFSET()
{
    # extract SLC sections for overlap region i (i=1 --> overlap between bursts 1 and 2)
    mas_name="mas_"$1"_slc"
    mas_par=$mas_name.par
    mas1=$mas_name.$2.1
    mas2=$mas_name.$2.2
    mas1_par=$mas1.par
    mas2_par=$mas2.par
    slv_name="slv_"$1"_slc"
    slv_par=$slv_name.par
    slv1=$slv_name.$2.1
    slv2=$slv_name.$2.2
    slv1_par=$slv1.par
    slv2_par=$slv2.par
    eval "GM SLC_copy \$$mas_name \$$mas_par \$$mas1 \$$mas1_par - 1. 0 $range_samples $starting_line1 $lines_overlap"
    eval "GM SLC_copy \$$mas_name \$$mas_par \$$mas2 \$$mas2_par - 1. 0 $range_samples $starting_line1 $lines_overlap"
    eval "GM SLC_copy \$$slv_name \$$mas_par \$$slv1 \$$slv1_par - 1. 0 $range_samples $starting_line1 $lines_overlap"
    eval "GM SLC_copy \$$slv_name \$$mas_par \$$slv2 \$$slv2_par - 1. 0 $range_samples $starting_line1 $lines_overlap"

    # calculate the 2 single look interferograms for the burst overlap region i
    # using the earlier burst --> *.int1, using the later burst --> *.int2
    off1=$mas-$slv.$1.$2.off1 
    int1=$mas-$slv.$1.$2.int1
    if [ -e $off1 ]; then
	rm -f $off1
    fi
    eval "GM create_offset \$$mas1_par \$$mas1_par \$$off1 1 1 1 0"
    eval "GM SLC_intf \$$mas1 \$$slv1 \$$mas1_par \$$mas1_par \$$off1 \$$int1 1 1 0 - 0 0"
    off2=$mas-$slv.$1.$2.off2
    int2=$mas-$slv.$1.$2.int2
    if [ -e $off2 ]; then
	rm -f $off2
    fi
    eval "GM create_offset \$$mas2_par \$$mas2_par \$$off2 1 1 1 0"
    eval "GM SLC_intf \$$mas2 \$$slv2 \$$mas2_par \$$mas2_par \$$off2 \$$int2 1 1 0 - 0 0"

    # calculate the single look double difference interferogram for the burst overlap region i
    # insar phase of earlier burst is subtracted from interferogram of later burst
    diff_par1=$mas-$slv.$1.$2.diff_par
    diff1=$mas-$slv.$1.$2.diff
    if [ -e $diff_par1 ]; then
	rm -f $diff_par1
    fi
    eval "GM create_diff_par \$$off1 \$$off2 \$$diff_par1 0 0"
    eval "GM cpx_to_real \$$int1 tmp $range_samples 4"
    eval "GM sub_phase \$$int2 tmp \$$diff_par1 \$$diff1 1 0"

    # multi-look the double difference interferogram (200 range x 4 azimuth looks)
    diff20=$mas-$slv.$1.$2.diff20
    off20=$mas-$slv.$1.$2.off20
    eval "GM multi_cpx \$$diff1 \$$off1 \$$diff20 \$$off20 200 4"
    eval "grep interferogram_width: \$$off20 | cut -d ":" -f 2 > temp1"
    eval "grep interferogram_azimuth_lines: \$$off20 | cut -d ":" -f 2 > temp2"
    range_samples20=`awk '{print}' temp1`
    azimuth_lines20=`awk '{print}' temp2`
    range_samples20_half=`awk '{printf "%d", $1/2}' temp1`
    azimuth_lines20_half=`awk '{printf "%d", $1/2}' temp2`
    rm -f temp1 temp2

    # determine coherence and coherence mask based on unfiltered double differential interferogram
    diff20cc=$mas-$slv.$1.$2.diff20.cc
    diff20cc_bmp=$mas-$slv.$1.$2.diff20.cc.bmp
    eval "GM cc_wave \$$diff20  - - \$$diff20cc $range_samples20 5 5 0"
    eval "GM rascc_mask \$$diff20cc - $range_samples20 1 1 0 1 1 $cc_thresh - 0.0 1.0 1. .35 1 \$$diff20cc_bmp"

    # adf filtering of double differential interferogram
    diff20adf=$mas-$slv.$1.$2.diff20.adf
    diff20adfcc=$mas-$slv.$1.$2.diff20.adf.cc
    eval "GM adf \$$diff20 \$$diff20adf \$$diff20adfcc $range_samples20 0.4 16 7 2"
    if [ -e $diff20adfcc ]; then
	rm -f $diff20adfcc
    fi

    # unwrapping of filtered phase considering coherence and mask determined from unfiltered double differential interferogram
    diff20cc=$mas-$slv.$1.$2.diff20.cc
    diff20cc_bmp=$mas-$slv.$1.$2.diff20.cc.bmp
    diff20phase=$mas-$slv.$1.$2.diff20.phase
    diff20phase_bmp=$mas-$slv.$1.$2.diff20.phase.bmp
    diff20_bmp=$mas-$slv.$1.$2.diff20.bmp
    diff20adf_bmp=$mas-$slv.$1.$2.diff20.adf.bmp
    eval "GM mcf \$$diff20adf \$$diff20cc \$$diff20cc_bmp \$$diff20phase $range_samples20 0 0 0 - - 1 1 512 $range_samples20_half $azimuth_lines20_half"
    eval "ls -l \$$diff20phase > temp1"
    size=`awk '{print $5}' temp1`
    rm -f temp1
    eval "GM rasmph \$$diff20 $range_samples20 1 0 1 1 1. .35 1 \$$diff20_bmp"
    eval "GM rasmph \$$diff20adf $range_samples20 1 0 1 1 1. .35 1 \$$diff20adf_bmp"
    if [[ -e "$diff20phase" && "$size" -gt 0 ]]; then
	eval "GM rasrmg \$$diff20phase - $range_samples20 1 1 0 1 1 0.333 1.0 0.35 0.0 1 \$$diff20phase_bmp"
    fi

    # determine overlap phase average (in radian), standard deviation (in radian), and valid data fraction
    if [ -e $diff20cc ]; then
	diff20ccstat=$mas-$slv.$1.$2.diff20.cc.stat
	diff20phasestat=$mas-$slv.$1.$2.diff20.phase.stat
	eval "GM image_stat \$$diff20cc $range_samples20 - - - - \$$diff20ccstat"
	eval "grep mean: \$$diff20ccstat | cut -d ":" -f 2 > temp1"
	eval "grep stdev: \$$diff20ccstat | cut -d ":" -f 2 > temp2"
	eval "grep fraction_valid: \$$diff20ccstat | cut -d ":" -f 2 > temp3"
	rm -f temp1 temp2 temp3
	cc_mean=`awk '{print}' temp1`
	cc_stdev=`awk '{print}' temp2`
	cc_fraction=`awk '{print}' temp3`
	cc_fraction1000=`echo $cc_fraction | awk '{printf "%d", $1*1000.}'`
    else
	cc_mean=0      
	cc_stdev=0      
	cc_fraction=0      
	cc_fraction1000=0
    fi
    if [[ -e "$diff20phase" && "$size" -gt 0 ]]; then
	eval "GM image_stat \$$diff20phase $range_samples20 - - - - \$$diff20phasestat"
	eval "grep mean: \$$diff20phasestat | cut -d ":" -f 2 > temp1"
	eval "grep stdev: \$$diff20phasestat | cut -d ":" -f 2 > temp2"
	eval "grep fraction_valid: \$$diff20phasestat | cut -d ":" -f 2 > temp3"
	mean=`awk '{print}' temp1`
	stdev=`awk '{print}' temp2`
	fraction=`awk '{print}' temp3`
	fraction1000=`echo $fraction | awk '{printf "%d", $1*1000.}'`
	rm -f temp1 temp2 temp3
    else
	mean=0       
	stdev=0       
	fraction=0     
	fraction1000=0
    fi

    # determine fraction10000 and stdev10000 to be used for integer comparisons
    if [ $cc_fraction1000 -eq 0 ]; then
	fraction10000=0
    else
	fraction10000=`echo $fraction $cc_fraction | awk '{printf "%d", $1*10000./$2}'`
    fi
    stdev10000=`echo $stdev | awk '{printf "%d", $1*10000.}'`

    # only for overlap regions with a significant area with high coherence and phase standard deviation < stdev10000_thresh
    if [[ "$fraction10000" -gt "$fraction10000_thresh" && "$stdev10000" -lt "$stdev10000_thresh" ]]; then   
	weight=`echo $fraction $stdev | awk '{printf "%f", $1/($2+0.1)/($2+0.1)}'`    # +0.1 to limit maximum weights for very low stdev
	sum=`echo $sum $mean $fraction | awk '{printf "%f", $1+($2*$3)}'`
	samples=`echo $samples | awk '{printf "%d", $1+1}'`
	sum_weight=`echo $sum_weight $fraction | awk '{printf "%f", $1+$2}'`
	sum_all=`echo $sum_all $mean $fraction | awk '{printf "%f", $1+($2*$3)}'`
	samples_all=`echo $samples_all | awk '{printf "%d", $1+1}'`
	sum_weight_all=`echo $sum_weight_all $fraction | awk '{printf "%f", $1+$2}'`
    else
	weight=0.000000
    fi

    # calculate average over the first sub-swath and print it out to output text file
    if [ $fraction1000 -gt 0 ]; then
	echo $1 $2 $mean $stdev $fraction" ("$cc_mean $cc_stdev $cc_fraction") "$weight >> $ovr_res
    else
	echo $1 $2" 0.00000 0.00000 0.00000 ("$cc_mean $cc_stdev $cc_fraction") "$weight >> $ovr_res
    fi
}



### Determine lookup table based on orbit data and DEM
GM rdc_trans $mas_rmli_par $rdc_dem $slv_mli_par $slv_mli.lt

### Masking of lookup table (used for the matching refinement estimation)
ln -s $slv_mli.lt $slv_mli.lt.masked

### Determine starting and ending rows and cols
r1=0
r2=$mas_rslc_width
a1=0
a2=$mas_rslc_nlines
  
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

### Iterative improvement of refinement offsets between master SLC and resampled slave RSLC using intensity matching (offset_pwr_tracking)
# Remarks: here only a section of the data is used if a polygon is indicated the lookup table is iteratively refined refined with the estimated offsets 
# only a constant offset in range and azimuth (along all burst and swaths) is considered 

echo "Iterative improvement of refinement offset using matching:" >> $check_file
if [ -e $off ]; then
    rm -rf $off
fi
GM create_offset $mas_rslc_par $slv_slc_par $off 1 $rlks $alks 0


# iterate while azimuth correction > 0.01 SLC pixel
daz10000=10000
it=1
while [[ "$daz10000" -gt 100 || "$daz10000" -lt -100 ]] && [ "$it" -le "$niter" ]; do
    cp -rf $off $off.start

    GM SLC_interp_lt_S1_TOPS $slv_slc_tab $slv_slc_par $mas_slc_tab $mas_rslc_par $slv_mli.lt.masked $mas_rmli_par $slv_mli_par $off.start $slv_rslc_tab $slv_rslc $slv_rslc_par
    if [ -e $doff ]; then
	rm -rf $doff
    fi

    GM create_offset $mas_rslc_par $slv_slc_par $doff 1 $rlks $alks 0

    # no oversampling as this is not done well because of the doppler ramp
    GM offset_pwr_tracking $mas_rslc $slv_rslc $mas_rslc_par $slv_rslc_par $doff $offs $snr 128 64 - 1 0.2 $rstep $azstep $r1 $r2 $a1 $a2

    GM offset_fit $offs $snr $doff - - 0.2 1 0
    grep "final model fit std. dev. (samples) range:" output.log > temp1
    grep -F 'final' temp1 | awk "NR==$it {print}" > temp2
    range_stdev=`awk '$1 == "final" {print $8}' temp2`
    azimuth_stdev=`awk '$1 == "final" {print $10}' temp2`
    rm -rf temp1 temp2

    daz10000=`awk '$1 == "azimuth_offset_polynomial:" {printf "%d", $2*10000}' $doff`
    daz=`awk '$1 == "azimuth_offset_polynomial:" {print $2}' $doff`
    daz_mli=`echo "$daz" "$alks" | awk '{printf "%f", $1/$2}'`
  
    # lookup table refinement
    # determine range and azimuth corrections for lookup table (in mli pixels)
    dr=`awk '$1 == "range_offset_polynomial:" {print $2}' $doff`      
    dr_mli=`echo $dr $rlks | awk '{printf "%f", $1/$2}'`
    daz=`awk '$1 == "azimuth_offset_polynomial:" {print $2}' $doff`      
    daz_mli=`echo $daz $alks | awk '{printf "%f", $1/$2}'`
    echo "dr_mli: "$dr_mli"    daz_mli: "$daz_mli > $ref_iter.$it

    if [ -e $diff_par ]; then
	rm -rf $diff_par
    fi
    GM create_diff_par $mas_rmli_par $mas_rmli_par $diff_par 1 0
    GM set_value $diff_par $diff_par "range_offset_polynomial" "${dr_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"
    GM set_value $diff_par $diff_par "azimuth_offset_polynomial" "${daz_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"
    cp -rf $diff_par $diff_par.$it

    # update unmasked lookup table
    mv -f $slv_mli.lt $slv_mli.lt.tmp.$it
    GM gc_map_fine $slv_mli.lt.tmp.$it $mas_rmli_width $diff_par $slv_mli.lt 1

    echo "matching_iteration_"$it": "$daz $dr $daz_mli $dr_mli" (daz dr daz_mli dr_mli)" >> $check_file
    echo "matching_iteration_stdev_"$it": "$azimuth_stdev $range_stdev" (azimuth_stdev range_stdev)" >> $check_file
    it=$(($it+1))
done


### Iterative improvement of azimuth refinement using spectral diversity method   
ln -s $slv_mli.lt $slv_mli.lt.az_ovr 

echo "" >> $check_file
echo "Iterative improvement of refinement offset azimuth overlap regions:" >> $check_file

# iterate while azimuth correction >= 0.0005 SLC pixel
daz10000=10000
it=1
while [[ "$daz10000" -gt 5 || "$daz10000" -lt -5 ]] && [ "$it" -le "$niter" ]; do
    cp -rf $off $off.start

    GM SLC_interp_lt_S1_TOPS $slv_slc_tab $slv_slc_par $mas_slc_tab $mas_rslc_par $slv_mli.lt.az_ovr $mas_rmli_par $slv_mli_par $off.start $slv_rslc_tab $slv_rslc $slv_rslc_par

    ###### Converted from GAMMA script 'S1_coreg_overlap': - works with IW1, IW2 and IW3 only (can be expanded to work with IW4 and IW5)
    samples=0
    sum=0.0
    samples_all=0
    sum_all=0.0
    sum_weight_all=0.0
    cc_thresh=0.6
    fraction_thresh=0.001
    stdev_thresh=0.8
    fraction10000_thresh=`echo $fraction_thresh | awk '{printf "%d", $1*10000}'`
    stdev10000_thresh=`echo $stdev_thresh | awk '{printf "%d", $1*10000}'`

    # initialize the output text file
    echo "Burst Overlap Results" > $ovr_res
    echo "thresholds applied: cc_thresh: "$cc_thresh",  ph_fraction_thresh: "$fraction_thresh", ph_stdev_thresh (rad): "$stdev_thresh  >> $ovr_res
    echo "" >> $ovr_res
    echo "IW  overlap  ph_mean ph_stdev ph_fraction   (cc_mean cc_stdev cc_fraction)    weight" >> $ovr_res
    echo "" >> $ovr_res

    # determine number of rows and columns of master tab file
    nrows=`sed '/^\s*$/d' $mas_slc_tab | wc -l`
    ncols=`head -1 $mas_slc_tab | wc -w`

    # read burst SLC filenames from first line tab files
    mas_IW1_slc=`awk '(NR==1){print $1}' $mas_slc_tab`
    mas_IW1_par=`awk '(NR==1){print $2}' $mas_slc_tab`
    mas_IW1_TOPS=`awk '(NR==1){print $3}' $mas_slc_tab`
    slv_IW1_slc=`awk '(NR==1){print $1}' $slv_slc_tab`
    slv_IW1_par=`awk '(NR==1){print $2}' $slv_slc_tab`
    slv_IW1_TOPS=`awk '(NR==1){print $3}' $slv_slc_tab`

    rmas_IW1_slc=`awk '(NR==1){print $1}' $mas_slc_tab`
    rmas_IW1_par=`awk '(NR==1){print $2}' $mas_slc_tab`
    rmas_IW1_TOPS=`awk '(NR==1){print $3}' $mas_slc_tab`

    # read burst SLC filenames from second line of tab files
    if [ $nrows -gt 1 ]; then
	mas_IW2_slc=`awk '(NR==2){print $1}' $mas_slc_tab`
	mas_IW2_par=`awk '(NR==2){print $2}' $mas_slc_tab`
	mas_IW2_TOPS=`awk '(NR==2){print $3}' $mas_slc_tab`
	slv_IW2_slc=`awk '(NR==2){print $1}' $slv_slc_tab`
	slv_IW2_par=`awk '(NR==2){print $2}' $slv_slc_tab`
	slv_IW2_TOPS=`awk '(NR==2){print $3}' $slv_slc_tab`

	rmas_IW2_slc=`awk '(NR==2){print $1}' $mas_slc_tab`
	rmas_IW2_par=`awk '(NR==2){print $2}' $mas_slc_tab`
	rmas_IW2_TOPS=`awk '(NR==2){print $3}' $mas_slc_tab`
    fi

    # read burst SLC filenames from third line of tab files
    if [ $nrows -gt 2 ]; then
	mas_IW3_slc=`awk '(NR==3){print $1}' $mas_slc_tab`
	mas_IW3_par=`awk '(NR==3){print $2}' $mas_slc_tab`
	mas_IW3_TOPS=`awk '(NR==3){print $3}' $mas_slc_tab`
	slv_IW3_slc=`awk '(NR==3){print $1}' $slv_slc_tab`
	slv_IW3_par=`awk '(NR==3){print $2}' $slv_slc_tab`
	slv_IW3_TOPS=`awk '(NR==3){print $3}' $slv_slc_tab`

	rmas_IW3_slc=`awk '(NR==3){print $1}' $mas_slc_tab`
	rmas_IW3_par=`awk '(NR==3){print $2}' $mas_slc_tab`
	rmas_IW3_TOPS=`awk '(NR==3){print $3}' $mas_slc_tab`
    fi

    # determine lines offset between start of burst1 and start of burst2
    azimuth_line_time=`awk '$1 == "azimuth_line_time:" {print $2}' $mas_IW1_par`      
    burst_start_time_1=`awk '$1 == "burst_start_time_1:" {print $2}' $mas_IW1_TOPS`      
    burst_start_time_2=`awk '$1 == "burst_start_time_2:" {print $2}' $mas_IW1_TOPS`      
    lines_offset_float=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%f", (($2-$1)/$3)}'`
    lines_offset_IW1=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
    if [ $nrows -gt 1 ]; then
	azimuth_line_time=`awk '$1 == "azimuth_line_time:" {print $2}' $mas_IW2_par`      
	burst_start_time_1=`awk '$1 == "burst_start_time_1:" {print $2}' $mas_IW2_TOPS`      
	burst_start_time_2=`awk '$1 == "burst_start_time_2:" {print $2}' $mas_IW2_TOPS`      
	lines_offset_float=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%f", (($2-$1)/$3)}'`
	lines_offset_IW2=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
    fi
    if [ $nrows -gt 2 ]; then
	azimuth_line_time=`awk '$1 == "azimuth_line_time:" {print $2}' $mas_IW3_par`      
	burst_start_time_1=`awk '$1 == "burst_start_time_1:" {print $2}' $mas_IW3_TOPS`      
	burst_start_time_2=`awk '$1 == "burst_start_time_2:" {print $2}' $mas_IW3_TOPS`      
	lines_offset_float=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%f", (($2-$1)/$3)}'`
	lines_offset_IW3=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
    fi

    # calculate lines_offset for the second scene (for compariosn)
    azimuth_line_time=`awk '$1 == "azimuth_line_time:" {print $2}' $slv_IW1_par`      
    burst_start_time_1=`awk '$1 == "burst_start_time_1:" {print $2}' $slv_IW1_TOPS`      
    burst_start_time_2=`awk '$1 == "burst_start_time_2:" {print $2}' $slv_IW1_TOPS`      
    lines_offset_float=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%f", (($2-$1)/$3)}'`
    lines_offset=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
    if [ $nrows -gt 1 ]; then
	azimuth_line_time=`awk '$1 == "azimuth_line_time:" {print $2}' $slv_IW2_par`      
	burst_start_time_1=`awk '$1 == "burst_start_time_1:" {print $2}' $slv_IW2_TOPS`      
	burst_start_time_2=`awk '$1 == "burst_start_time_2:" {print $2}' $slv_IW2_TOPS`      
	lines_offset_float=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%f", (($2-$1)/$3)}'`
	lines_offset=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
    fi
    if [ $nrows -gt 2 ]; then
	azimuth_line_time=`awk '$1 == "azimuth_line_time:" {print $2}' $slv_IW3_par`      
	burst_start_time_1=`awk '$1 == "burst_start_time_1:" {print $2}' $slv_IW3_TOPS`      
	burst_start_time_2=`awk '$1 == "burst_start_time_2:" {print $2}' $slv_IW3_TOPS`      
	lines_offset_float=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%f", (($2-$1)/$3)}'`
	lines_offset=`echo $burst_start_time_1 $burst_start_time_2 $azimuth_line_time | awk '{printf "%d", (0.5+($2-$1)/$3)}'`  
    fi

    # set some parameters used
    azimuth_line_time=`awk '$1 == "azimuth_line_time:" {print $2}' $mas_IW1_par`      
    dDC=`echo $azimuth_line_time $lines_offset_IW1 | awk '{printf "%f", 1739.43*$1*$2}'`
    dt=`echo $dDC | awk '{printf "%f", 0.159154/$1}'`
    dpix_factor=`echo $dt $azimuth_line_time | awk '{printf "%f", $1/$2}'`


    ## Determine phase offsets for sub-swath overlap regions of first/second sub-swaths
    # IW1: 
    number_of_bursts_IW1=`awk '$1 == "number_of_bursts:" {print $2}' $mas_IW1_TOPS`      
    lines_per_burst=`awk '$1 == "lines_per_burst:" {print $2}' $mas_IW1_TOPS`      
    lines_offset=$lines_offset_IW1 
    lines_overlap=`echo $lines_per_burst $lines_offset | awk '{printf "%d", $1-$2}'`
    range_samples=`awk '$1 == "range_samples:" {print $2}' $mas_IW1_par`      
    samples=0
    sum=0.0
    sum_weight=0.0
    i=1
    while [ $i -lt $number_of_bursts_IW1 ]; do
	starting_line1=`echo $i $lines_offset $lines_per_burst | awk '{printf "%d", $2+($1-1)*$3}'`
	starting_line2=`echo $i $lines_offset $lines_per_burst | awk '{printf "%d", $1*$3}'`
	OFFSET IW1 $i
        # increase overlap region counter
	i=`echo $i | awk '{printf "%d", $1+1}'`
    done

    # IW2: 
    number_of_bursts_IW2=`awk '$1 == "number_of_bursts:" {print $2}' $mas_IW2_TOPS`      
    lines_per_burst=`awk '$1 == "lines_per_burst:" {print $2}' $mas_IW2_TOPS`      
    lines_offset=$lines_offset_IW2 
    lines_overlap=`echo $lines_per_burst $lines_offset | awk '{printf "%d", $1-$2}'`
    range_samples=`awk '$1 == "range_samples:" {print $2}' $mas_IW2_par`      
    samples=0
    sum=0.0
    sum_weight=0.0
    i=1
    while [ $i -lt $number_of_bursts_IW2 ]; do
	starting_line1=`echo $i $lines_offset $lines_per_burst | awk '{printf "%d", $2+($1-1)*$3}'`
	starting_line2=`echo $i $lines_offset $lines_per_burst | awk '{printf "%d", $1*$3}'`
	OFFSET IW2 $i
        # increase overlap region counter
	i=`echo $i | awk '{printf "%d", $1+1}'`
    done

   # IW3: 
    number_of_bursts_IW3=`awk '$1 == "number_of_bursts:" {print $2}' $mas_IW3_TOPS`      
    lines_per_burst=`awk '$1 == "lines_per_burst:" {print $2}' $mas_IW3_TOPS`      
    lines_offset=$lines_offset_IW3 
    lines_overlap=`echo $lines_per_burst $lines_offset | awk '{printf "%d", $1-$2}'`
    range_samples=`awk '$1 == "range_samples:" {print $2}' $mas_IW3_par`      
    samples=0
    sum=0.0
    sum_weight=0.0
    i=1
    while [ $i -lt $number_of_bursts_IW3 ]; do
	starting_line1=`echo $i $lines_offset $lines_per_burst | awk '{printf "%d", $2+($1-1)*$3}'`
	starting_line2=`echo $i $lines_offset $lines_per_burst | awk '{printf "%d", $1*$3}'`
	OFFSET IW3 $i
        # increase overlap region counter
	i=`echo $i | awk '{printf "%d", $1+1}'`
    done

    daz=`awk '$1 == "azimuth_pixel_offset" {print $2}' $ovr_res`      
    daz10000=`awk '$1 == "azimuth_pixel_offset" {printf "%d", $2*10000}' $ovr_res` 

    cp -rf $off $off.az_ovr.$it

    echo "az_ovr_iteration_"$it": "$daz" (daz in SLC pixel)" >> $check_file
    it=$(($it+1))
done

paste $ovr_res >> $check_file


### Resample full data set
GM SLC_interp_lt_S1_TOPS $slv_slc_tab $slv_slc_par $mas_slc_tab $mas_rslc_par $slv_mli.lt $mas_rmli_par $slv_mli_par $off $slv_rslc_tab $slv_rslc $slv_rslc_par

### Multilook coregistered slave
GM multi_look $slv_rslc $slv_rslc_par $slv_rmli $slv_rmli_par $rlks $alks 


# clean up temp files
rm -f temp1
rm -f tmp
rm -f $slv_mli.lt.masked
rm -f $slv_mli.lt.masked.tmp.?
rm -f $slv_mli.lt.tmp.?
rm -f $slv_mli.lt.az_ovr   
rm -f $doff
rm -f $off.?
rm -f $off.az_ovr.?
rm -f $off.out.?
rm -f $off.start 

rm -f *diff20*.bmp
rm -f $mas-$slv.IW?.?.*
rm -f $mas_IW1_slc.?.?
rm -f $mas_IW1_slc.?.?.par
rm -f $slv_IW1_slc.?.?
rm -f $slv_IW1_slc.?.?.par
if [ $number_of_bursts_IW1 -gt 9 ]; then
    rm -f $mas_IW1_slc.??.?
    rm -f $mas_IW1_slc.??.?.par
    rm -f $slv_IW1_slc.??.?
    rm -f $slv_IW1_slc.??.?.par
fi
if [ $nrows -gt 1 ]; then
    rm -f $mas_IW2_slc.?.?
    rm -f $mas_IW2_slc.?.?.par
    rm -f $slv_IW2_slc.?.?
    rm -f $slv_IW2_slc.?.?.par
    if [ $number_of_bursts_IW2 -gt 9 ]; then
	rm -f $mas_IW2_slc.??.?
	rm -f $mas_IW2_slc.??.?.par
	rm -f $slv_IW2_slc.??.?
	rm -f $slv_IW2_slc.??.?.par
    fi
fi
if [ $nrows -gt 2 ]; then
    rm -f $mas_IW3_slc.?.?
    rm -f $mas_IW3_slc.?.?.par
    rm -f $slv_IW3_slc.?.?
    rm -f $slv_IW3_slc.?.?.par
    if [ $number_of_bursts_IW3 -gt 9 ]; then
	rm -f $mas_IW3_slc.??.?
	rm -f $mas_IW3_slc.??.?.par
	rm -f $slv_IW3_slc.??.?
	rm -f $slv_IW3_slc.??.?.par
    fi
fi






# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
   cat error.log 1>&2
#   rm temp_log
else
    $slv_dir/temp_log
fi


exit



#######################################################################################################################






### OLD SCRIPT:

## From this point, For S1 with  S1_coreg_TOPS command processing can be eliminated.
## Generate initial lookup table between master and slave MLI considering terrain heights from DEM coregistered to master
GM rdc_trans $master_mli_par $rdc_dem $slave_mli_par lt0

slave_mli_width=`awk 'NR==11 {print $2}' $slave_mli_par`
master_mli_width=`awk 'NR==11 {print $2}' $master_mli_par`
slave_mli_length=`awk 'NR==12 {print $2}' $slave_mli_par`

GM geocode lt0 $master_mli $master_mli_width $rmli $slave_mli_width $slave_mli_length 2 0

GM create_diff_par $slave_mli_par $slave_mli_par diff.par 1 0

## Measure offset between slave MLI and resampled slave MLI
GM init_offsetm $rmli $slave_mli diff.par 1 1

GM offset_pwrm $rmli $slave_mli diff.par offs0 ccp0 - - - 2

## Fit the offset only
GM offset_fitm offs0 ccp0 diff.par coffs0 - - 1

## Refinement of initial geocoding look up table
GM gc_map_fine lt0 $master_mli_width diff.par $lt

## Create table for resampled burst SLCs
rm -f $rslc_tab
for swath in 1 2 3; do
    bslc="slc$swath"
    bslc_par=${!bslc}.par
    btops="tops_par$swath"
    echo $slave_dir/${!bslc} $slave_dir/$bslc_par $slave_dir/${!btops} >> $rslc_tab
done

## Resample slave SLC into geometry of master SLC using lookup table and generate mosaic SLC    
GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $master_slc_par $lt $master_mli_par $slave_mli_par - $rslc_tab $rslc $rslc_par

#------------------------

## set up iterable loop
i=1
while [ $i -le $niter ]; do

    ioff=$off$i
    rm -f offs ccp offsets coffsets
    echo "Starting Iteration "$i

## Measure offsets for refinement of lookup table using initially resampled slave SLC
    GM create_offset $master_slc_par $rslc_par $ioff 1 $rlks $alks 0

## No SLC oversampling for S1 due to strong Doppler centroid variation in azimuth
    GM offset_pwr $master_slc $rslc $master_slc_par $rslc_par $ioff offs ccp 256 64 offsets $ovr $nwin $nwin $ccp 

##In the S1_coreg_TOPS, this command was replaced by "offset_pwr_trackingm" that uses the master and slave mli and other parameters"

## Fit constant offset term only for S1 due to short length orbital baselines
    GM offset_fit offs ccp $ioff - coffsets 10.0 $npoly 0

## Create blank offset file for first iteration and calculate the total estimated offset
    if [ $i == 1 ]; then
	GM create_offset $master_slc_par $rslc_par $off"0" 1 $rlks $alks 0

	GM offset_add $off"0" $ioff $off
    else
## Calculate the cumulative total estimated offset
	GM offset_add $off $ioff $off
    fi

## if azimuth offset is less than 0.02 and range offset is less than 0.2 then break iterable loop. Precision azimuth coregistration is essential for S1 IWS mode interferometry
    azoff=`grep "final azimuth offset poly. coeff." output.log | tail -2 | head -1 | awk '{print $6}'`
    rgoff=`grep "final range offset poly. coeff." output.log | tail -2 | head -1 | awk '{print $6}'`  
    test1=`echo $azoff | awk '{if ($1 < 0) $1 = -$1; printf "%i\n", $1*100}'`
    test2=`echo $rgoff | awk '{if ($1 < 0) $1 = -$1; printf "%i\n", $1*10}'`
    echo "Iteration "$i": azimuth offset is "$azoff", range offset is "$rgoff
    azcorr=`grep "azimuth_pixel_offset." output.log | tail -2 |head -1 | awk '{print $6}'`
    test3=`echo $azcorr | awk '{if ($1 < 0) $1 = -$1; printf "%i\n", $1*1000}'`

## Perform resampling of slave SLC using lookup table and offset model, and generate mosaic SLC
    GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $master_slc_par $lt $master_mli_par $slave_mli_par $off $rslc_tab $rslc $rslc_par

    if [ $test1 -lt 2 -a $test2 -lt 2 ]; then
	break
    fi
    i=$(($i+1))
done

#-------------------------
#Multilooking should be done before azimuth offset estimation 
GM multi_look $rslc $rslc_par $rmli $rmli_par $rlks $alks

##Preparing initial simulated topographic phase
GM phase_sim_orb $master_slc_par $rslc_par $off $rdc_dem $master-$slave".sim0_unw" $master_slc_par - - 1 1 

##preparing initial interferogram 
GM SLC_diff_intf $master_o_slc $rslc $master_o_slc_par $rslc_par $off $master-$slave".sim0_unw" $master-$slave.diff.test0 10 2 0 0 0.2 1 1

#-------------------------
## Determine a refinement to the azimuth offset estimation in the burst overlap regions at first stage to get the quality result output(@negin)
GM S1_coreg_overlap $master_slc_tab $rslc_tab $master-$slave $off $off".corrected" 0.8 0.01 0.8 1 
GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $master_slc_par $lt $master_mli_par $slave_mli_par $off".corrected" $rslc_tab $rslc $rslc_par

##Preparing initial simulated topographic phase
GM phase_sim_orb $master_slc_par $rslc_par $off".corrected" $rdc_dem $master-$slave".sim1_unw" $master_slc_par - - 1 1 

##preparing initial interferogram 
GM SLC_diff_intf $master_o_slc $rslc $master_o_slc_par $rslc_par $off".corrected" $master-$slave".sim1_unw" $master-$slave.diff.test1 10 2 0 0 0.2 1 1 

## Automating code(GAMMA suggestion)(in case of LAT package )(Note: There is no need to use the above "S1_coreg_overlap" and "SLC_interp_lt_S1_TOPS")
#GM S1_coreg_TOPS $master_slc_tab $master $slave_slc_tab $slave $rslc_tab $rdc_dem 10 2 - - 0.6 0.02 0.8 1 0

## Determine a refinement to the azimuth offset estimation in the burst overlap regions in case that there is a jump(@negin) 
GM S1_coreg_overlap $master_slc_tab $rslc_tab $master-$slave $off".corrected" $off".corrected2" 0.8 100

##Perform fifth resampling of slave SLC using lookup table and corrected offset information
##   GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $master_slc_par $lt $master_mli_par $slave_mli_par  $icorrected $rslc_tab $rslc $rslc_par
GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $master_slc_par $lt $master_mli_par $slave_mli_par $off".corrected2" $rslc_tab $rslc $rslc_par

##Preparing initial simulated topographic phase
GM phase_sim_orb $master_slc_par $rslc_par $off".corrected2" $rdc_dem $master-$slave".sim2_unw" $master_slc_par - - 1 1 

##preparing initial interferogram 
GM SLC_diff_intf $master_o_slc $rslc $master_o_slc_par $rslc_par $off".corrected2" $master-$slave".sim2_unw" $master-$slave.diff.test2 10 2 0 0 0.2 1 1 

#-------------------------

rm -rf offs0 ccp ccp0 coffs0 coffsets lt0 offs offs0 offsets tmp -

## Extract final model fit values to check coregistration
echo $master > temp1_$rlks
echo $slave > temp2_$rlks
grep "final model fit" output.log > temp3_$rlks
awk '{print $8}' temp3_$rlks > temp4_$rlks
awk '{print $10}' temp3_$rlks > temp5_$rlks
paste temp1_$rlks temp2_$rlks temp4_$rlks temp5_$rlks >> $check_file
rm -f temp*


# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
   cat error.log 1>&2
#   rm temp_log
else
    $slave_dir/temp_log
fi
