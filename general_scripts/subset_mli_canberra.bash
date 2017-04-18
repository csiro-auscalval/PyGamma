#!/bin/bash

## Subset TSX canberra scenes for dgal presentation

SLC_dir=/g/data1/dg9/INSAR_ANALYSIS/CANBERRA/TSX/GAMMA/T041D/SLC
slv_list=$SLC_dir/slv_slc_list
list=$SLC_dir/slc_list

rlks=8
alks=8


# Coregister SLCs to master SLC
mas=20110926
mas_slc=$SLC_dir/$mas/$mas"_HH.slc"
mas_slc_par=$SLC_dir/$mas/$mas"_HH.slc.par"

while read date; do
    slc=$SLC_dir/$date/$date"_HH.slc"
    slc_par=$SLC_dir/$date/$date"_HH.slc.par"
    rslc=$SLC_dir/$date/r$date"_HH.slc"
    rslc_par=$SLC_dir/$date/r$date"_HH.slc.par"
    rmli=$SLC_dir/$date/r$date"_HH_"$rlks.mli
    rmli_par=$SLC_dir/$date/r$date"_HH_"$rlks.mli.par
    cd $SLC_dir/$date
    create_offset $mas_slc_par $slc_par slc.off 1 - - 0
    init_offset_orbit $mas_slc_par $slc_par slc.off - - 1
    offset_pwr $mas_slc $slc $mas_slc_par $slc_par slc.off offs snr - - offsets 2 - - - 
    offset_fit offs snr slc.off coffs coffsets 
    SLC_interp $slc $mas_slc_par $slc_par slc.off $rslc $rslc_par
    multi_look $rslc $rslc_par $rmli $rmli_par $rlks $alks 0
    cd ../
done < $slv_list


# Subset SLCs
roff=853
rlines=626
azoff=1056
azlines=539

#subset master
cd $SLC_dir/$mas
mas_mli=$SLC_dir/$mas/$mas"_HH_"$rlks.mli
mas_mli_par=$SLC_dir/$mas/$mas"_HH_"$rlks.mli.par
smas_mli=$SLC_dir/$mas/s$mas"_HH_"$rlks.mli
smas_mli_par=$SLC_dir/$mas/s$mas"_HH_"$rlks.mli.par
MLI_copy $mas_mli $mas_mli_par $smas_mli $smas_mli_par $roff $rlines $azoff $azlines
cd ../

#subset slaves
while read date; do
    rmli=$SLC_dir/$date/r$date"_HH_"$rlks.mli
    rmli_par=$SLC_dir/$date/r$date"_HH_"$rlks.mli.par
    smli=$SLC_dir/$date/s$date"_HH_"$rlks.mli
    smli_par=$SLC_dir/$date/s$date"_HH_"$rlks.mli.par
    cd $SLC_dir/$date
    MLI_copy $rmli $rmli_par $smli $smli_par $roff $rlines $azoff $azlines
    cd ../
done < $slv_list


# Create *.bmp files
out_dir=$SLC_dir/bmp_files
while read date; do
    smli=$SLC_dir/$date/s$date"_HH_"$rlks.mli
    smli_par=$SLC_dir/$date/s$date"_HH_"$rlks.mli.par
    out=$date"_canberra.bmp"
    cd $SLC_dir/$date
    width=`grep range_samples: $smli_par | awk '{print $2}'`
    raspwr $smli $width 1 0 1 1 1 0.35 -1 $out
    mv $out $out_dir
    cd ../
done < $list


# Create tif files
dir=$SLC_dir/bmp_files
cd $dir

while read date; do
    psfile=$date"_canberra.ps"
    image=$date"_canberra.bmp"

    psimage $image -E300 -P -F -V > $psfile

    # Export to .tif
    ps2raster $psfile -A -E300 -Tt -V
    
    rm -f $psfile
done < $list