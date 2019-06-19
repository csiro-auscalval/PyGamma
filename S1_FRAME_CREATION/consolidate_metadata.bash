#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* consolidate_metadata: Consolidates extracted S1 metadata and then splits    *"
    echo "*                       list by pass and track.                               *"
    echo "*                                                                             *"
    echo "*      Designed to be executed by 'run_S1_bursts' script only                 *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/03/2019, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: consolidate_metadata.bash [config_file]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

config_file=$1


# Load generic variables
source ~/repo/gamma_insar/S1_FRAME_CREATION/S1_burst_functions $config_file


## Remove individual burst metadata files, no longer needed
rm -rf $ind_burst_dir

cd $burst_dir

## Merge lists into single file
merged_file=$burst_dir/"S1_"$mode"_"$type"_"$date".burst-metadata"

rm -rf temp
while read file; do
    cat $burst_dir/$file.burst-metadata >> temp
done < $split_list

# remove repeated headers
sed '1!{/^Mission/ d;}' temp > $merged_file
rm -rf temp
header=`head -n 1 $merged_file`

## Remove input files lists, no longer needed
while read file; do
    rm -rf $file.burst-metadata
done < $split_list

## Combine with previous lists to get full archive metadata
all_data_file=$burst_dir/"S1_"$mode"_"$type"_all_data_up_to_"$date".burst-metadata"
if [ $compare_zip == 'yes' ]; then
    compare_date=`echo $compare_dir | cut -d "_" -f 1`
    compare_file=$burst_dir/"S1_"$mode"_"$type"_"$compare_date".burst-metadata"

    # all data file already exists
    if [ -e $all_data_file  ]; then # will contain data from compare file already, just add new data
	# remove header from new merged file 
	sed '{/^Mission/ d;}' $merged_file > temp
	# add new data to all data file
	cat temp >> $all_data_file
	rm -rf temp

    # all data file doesn't exist
    else
	cp -r $compare_file $all_data_file
        # remove header from new merged file 
	sed '{/^Mission/ d;}' $merged_file > temp
        # add new data to all data file
	cat temp >> $all_data_file
	rm -rf temp
    fi
else
    cp -r $merged_file $all_data_file
fi

## Split list by pass value
echo "Ascending" > pass_names
echo "Descending" >> pass_names

rm -rf pass_list
while read pass; do
    awk -v var="$pass" -F' ' '$5 == var { print }' $all_data_file > $mode"_"$type"_"$pass"_burst-metadata"
    ls $mode"_"$type"_"$pass"_burst-metadata" >> pass_list
    mkdir -p $archive_dir/$pass"_track_data"
done < pass_names

## Split pass files by track for frame archive
while read file; do
    pass=`echo $file | cut -d '_' -f 3`
    if [ $pass == "Ascending" ]; then 
	pass1=A
    elif [ $pass == "Descending" ]; then
	pass1=D
    fi
    awk '{ a[$8]++ } END { for (b in a) { print b } }' $file > $pass"_tracks"
    while read track; do
	file="S1_"$mode"_"$type"_T"$track$pass1"_burst-metadata"
	echo $header > $file
        awk -v var="$track" -F' ' '$8 == var { print }' $mode"_"$type"_"$pass"_burst-metadata" >> $file
	mv -f $file $archive_dir/$pass"_track_data" # replace existing text files with new updated one
    done < $pass"_tracks"
    rm -rf $pass"_tracks"
done < pass_list
rm -rf pass_list IW_SLC_Ascending_burst-metadata IW_SLC_Descending_burst-metadata

## create list of burst-metadata tracks
while read pass; do
    cd $archive_dir/$pass"_track_data"
    ls *_burst-metadata > $pass"_list"
done < $burst_dir/pass_names









