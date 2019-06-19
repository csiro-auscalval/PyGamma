#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_S1_zipfile_list: Creates a list of Sentinel-1 zip files stored       *"
    echo "*                         in the Regional Copernicus archive.                 *"
    echo "*                         Can compare list with an older list to identify     *"
    echo "*                         only those zip files which haven't previously had   *"
    echo "*                         metadata extracted.                                 *"
    echo "*                                                                             *"
    echo "*      Designed to be executed by 'run_S1_bursts' script only                 *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/03/2019, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: create_S1_zipfile_list.bash [config_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

config_file=$1

# Load generic variables
source ~/repo/gamma_insar/S1_FRAME_CREATION/S1_burst_functions $config_file


# create list of zip files for Sentinel-1 downloaded files
yr_list=$zip_dir/yr_dir_list
mth_list=$zip_dir/mth_dir_list
grid_list=$zip_dir/grid_dir_list
zip_list=$zip_dir/zip_list
all_list=$zip_dir/all_list


# Directory to store list of zip files 
mkdir -p $list_dir

cd $sar_dir

ls -d 2* > $yr_list # list of year directories

while read yr_dir; do
    cd $yr_dir
    ls -d 2* > $mth_list # list of month directories
    while read mth_dir; do
	cd $mth_dir
	rm -f $list_dir/$mth_dir"_S1_"$type"_zip_list.txt" 
	rm -f $list_dir/$mth_dir"_S1_"$type"_all_files.txt" 
	ls -d *-* > $grid_list # list of grid directories
	while read grid_dir; do
	    cd $grid_dir #dir not empty
	    ls S1* > $all_list # list of zip files
	    while read file; do
		echo $mth_dir $grid_dir $file >> $list_dir/$mth_dir"_S1_"$type"_all_list.txt" 
	    done < $all_list 
	    rm -f $all_list
	    ls *.zip > $zip_list # list of zip files
	    while read zip; do
		echo $mth_dir $grid_dir $zip >> $list_dir/$mth_dir"_S1_"$type"_zip_list.txt" 
	    done < $zip_list 
	    rm -f $zip_list 
	    cd ../
	done < $grid_list
	cd ../
	rm -f $grid_list
    done < $mth_list
    cd ../
    rm -f $mth_list
done < $yr_list
rm -f $yr_list


cd $list_dir

# Collate lists
all_files=$list_dir/all_files_list_$type"_"$date
all_zip_file=$list_dir/all_zip_list_$type"_"$date
name_errors=$list_dir/zip_list_name_errors_$type"_"$date
sm_files=$list_dir/zip_list_SM_$type"_"$date
iw_files=$list_dir/zip_list_IW_$type"_"$date
wv_files=$list_dir/zip_list_WV_$type"_"$date
ew_files=$list_dir/zip_list_EW_$type"_"$date


if [ -f $all_files ]; then
    rm -rf $all_files
fi
cat *"_S1_"$type"_all_list.txt" >> $all_files

if [ -f $all_zip_file ]; then
    rm -rf $all_zip_file
fi
cat *"_S1_"$type"_zip_list.txt" >> $all_zip_file

# extract file name errors (eg. *SAFE.zip)
grep -e "SAFE" $all_zip_file | sort -k3.18 > $name_errors

# create list of all excluding name errors - correctly named duplicates of these files have been added to archive
grep -v "SAFE" $all_zip_file > temp1

#split list by mode type and sort by date (not just IW exists)
grep -e "_S1_" temp1 > temp2
grep -e "_S2_" temp1 >> temp2
grep -e "_S3_" temp1 >> temp2
grep -e "_S4_" temp1 >> temp2
grep -e "_S5_" temp1 >> temp2
grep -e "_S6_" temp1 >> temp2
sort -k3.18 temp2 > $sm_files
grep -e "_IW" temp1 | sort -k3.18 > $iw_files
grep -e "_WV" temp1 | sort -k3.18 > $wv_files
grep -e "_EW" temp1 | sort -k3.18 > $ew_files

rm -f temp1 temp2 *"_S1_"$type"_zip_list.txt" *"_S1_"$type"_all_list.txt" 

# Collate list into single file for future comparison purposes 
all_file2=$list_dir/final_all_zip_list_$type"_"$date
if [ -f $all_file2 ]; then 
    rm -rf $all_file2
fi
cat $sm_files > $all_file2
cat $iw_files >> $all_file2
cat $wv_files >> $all_file2
cat $ew_files >> $all_file2

# delete empty files
find . -type f -size 0 -delete

# Compare new list of zip files with old list (subtract old from new)
if [ $compare_zip == 'yes' ]; then
    new_dir=$list_dir
    old_dir=$zip_dir/$compare_dir
    new_ziplist=$new_dir/final_all_zip_list_$type"_"$date
    old_ziplist=$old_dir/final_all_zip_list_$type"_"*

    cd $new_dir
    mv zip_list_SM_$type"_"$date all_zip_list_SM_$type"_"$date 
    mv zip_list_IW_$type"_"$date all_zip_list_IW_$type"_"$date
    mv zip_list_WV_$type"_"$date all_zip_list_WV_$type"_"$date
    mv zip_list_EW_$type"_"$date all_zip_list_EW_$type"_"$date
 
    awk 'NR==FNR{a[$0]=1;next}!a[$0]' $old_ziplist $new_ziplist > temp1

    # split list by mode type and sort by date (not just IW exists)
    grep -e "_S1_" temp1 > temp2
    grep -e "_S2_" temp1 >> temp2
    grep -e "_S3_" temp1 >> temp2
    grep -e "_S4_" temp1 >> temp2
    grep -e "_S5_" temp1 >> temp2
    grep -e "_S6_" temp1 >> temp2
    sort -k3.18 temp2 > $sm_files
    grep -e "_IW" temp1 | sort -k3.18 > $iw_files
    grep -e "_WV" temp1 | sort -k3.18 > $wv_files
    grep -e "_EW" temp1 | sort -k3.18 > $ew_files
    rm -f temp1 temp2 

    # delete empty files (no new files for a mode type)
    [ -s $sm_files ] || rm -rf $sm_files
    [ -s $iw_files ] || rm -rf $iw_files
    [ -s $wv_files ] || rm -rf $wv_files
    [ -s $ew_files ] || rm -rf $ew_files
fi
