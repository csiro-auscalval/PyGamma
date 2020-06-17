#!/bin/bash


# create a list of zip-files from available S1 data in /g/data1/fj7/Copernicus/Sentinel-1/C-SAR/SLC/
# e.g. using:
# ls {./*/*/25S150E-30S155E/*T1920*T1921*.zip,./*/*/25S150E-30S155E/*T1921*T1921*.zip,./*/*/25S150E-30S155E/*T1921*T1922*.zip,,./*/*/25S150E-30S155E/*T1922*T1922*.zip} > /g/data1/dg9/INSAR_ANALYSIS/SURAT/S1/T174D_zipfiles.txt


input_list="T045D_zipfiles.txt"
output_temp="temp.list"
output_list="s1_download.list"
pol="V_"

frame=1
date_prev=0
time_prev=0

# loop through list of zip files
if [[ $pol == *"V"* ]]; then
    echo "Creating S1-vertical(VV) polarization list"
else
    echo "Creating S1-horizonal(HH) polarization list"
fi

while read zip; do

    # read information from zip file name
    grid_dir=`echo $zip | cut -d "/" -f 4`
    zip_file=`echo $zip | cut -d "/" -f 5`
    datetime=`echo $zip_file | cut -d "_" -f 6`
    date=`echo $datetime | head -c8`
    time=`echo $datetime | tail -c8`
    #echo $date
    #echo $grid_dir
    #echo $time
    
    if grep -q "$pol" <<< "$zip_file"; then
	
	# check if frame number needs to be increased or reset
	if [ $date == $date_prev ]; then
	    # increase frame number
	    ((frame++))
	    if [ $time == $time_prev ]; then
		print=0
		((frame--))
	    else
		print=1
	    fi
	else
	    frame=1
	    print=1
	fi
	
	
	# save previous date and time
	date_prev=`echo $date`
	time_prev=`echo $time`
	
	
	# don't print dates before 20151126
	if [ $date -lt 20151101 ]; then
	    print=0
	fi
	
	
	if [ $print == 1 ]; then
	    echo "$date $grid_dir $zip_file $frame" >> $output_temp
	fi
	
    else
	echo $zip_file "NOT" $pol "polarization"	
    fi
    
done < $input_list


sort -k 1 $output_temp > $output_list
rm -f $output_temp
