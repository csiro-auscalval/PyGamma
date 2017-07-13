#!/bin/bash


# mask unw ifms with flat coherence data for pyrate
# run from GAMMA's 'pyrate_files' dir


cc_thres=0.25
#flat or filt
cc_type=flat

pyrate_dir=$PWD

dem_par=../DEM/*utm.dem.par
width=`grep width: $dem_par | awk '{print $2}'`

cc_dir=$pyrate_dir/$cc_type"_cc_files"
cc_list=$cc_dir/$cc_type"_cc_list"
mkdir -p $cc_dir/$cc_type"_cc_mask"
mask_dir=$cc_dir/$cc_type"_cc_mask"
mask_list=$mask_dir/mask_list
unw_dir=$pyrate_dir/unw_ifms
unw_list=$unw_dir/unw_list
mkdir -p $unw_dir/unw_$cc_type"_cc_"$cc_thres"_masked"
unw_mask_dir=$unw_dir/unw_$cc_type"_cc_"$cc_thres"_masked"
unw_mask_list=$unw_mask_dir/unw_mask_list

#create mask
cd $cc_dir
while read file; do
    cc=$file
    mask=$file.bmp
    rascc_mask $cc - $width 1 1 0 1 1 $cc_thres 0 0.1 0.9 1 0.35 1 $mask
    mv $mask $mask_dir
done < $cc_list

cd $mask_dir
ls *.bmp > $mask_list

cd $pyrate_dir

#apply mask
cd $unw_dir
paste $unw_list $mask_list > temp
while read file; do
    unw=`echo $file | awk '{print $1}'`
    cc=`echo $file | awk '{print $2}'`
    mask=$mask_dir/$cc
    masked=$unw.masked
    mask_data $unw $width $masked $mask 0
    mv $masked $unw_mask_dir
done < temp
rm -f temp

#rename masked unw back to original names
cd $unw_mask_dir
ls *.masked > $unw_mask_list
while read masked; do
    unw="${masked%.*}"
    mv $masked $unw
done < $unw_mask_list
