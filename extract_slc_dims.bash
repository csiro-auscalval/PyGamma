#!/bin/bash

track=T366A
polar=HH
frame_list=/g/data1/dg9/INSAR_ANALYSIS/SURAT/PALSAR1/GAMMA/$track/lists/frame.list
scene_list=/g/data1/dg9/INSAR_ANALYSIS/SURAT/PALSAR1/GAMMA/$track/lists/scenes.list

file=/g/data1/dg9/INSAR_ANALYSIS/SURAT/PALSAR1/GAMMA/$track/SLC/slc_dimensions_$track.txt
echo "SLC Dimensions "$track > $file
echo "" >> $file

# frame SLCs
while read frame; do
    if [ ! -z $frame ]; then
	echo "Frame "$frame >> $file
	echo "Date" > temp1
	echo "Width" > temp2
	echo "Length" > temp3
	paste temp1 temp2 temp3 >> $file
	rm -f temp1 temp2 temp3
	while read scene; do
	    if [ ! -z $scene ]; then
		cd $scene
		fr_slc=$scene"_"$polar"_F"$frame.slc.par
		echo $scene > temp1
		grep range_samples: $fr_slc | awk '{print $2}' > temp2
		grep azimuth_lines: $fr_slc | awk '{print $2}' > temp3
		paste temp1 temp2 temp3 >> $file
		rm -f temp1 temp2 temp3
		cd ../
	    fi
	done < $scene_list
	echo "" >> $file
	echo "" >> $file
    fi
done < $frame_list


# concatenated SLCs
echo "Concatenated SLCs" >> $file
echo "Date" > temp1
echo "Width" > temp2
echo "Length" > temp3
paste temp1 temp2 temp3 >> $file
rm -f temp1 temp2 temp3
while read scene; do
    if [ ! -z $scene ]; then
	cd $scene
	slc=$scene"_"$polar.slc.par
	echo $scene > temp1
	grep range_samples: $slc | awk '{print $2}' > temp2
	grep azimuth_lines: $slc | awk '{print $2}' > temp3
	paste temp1 temp2 temp3 >> $file
	rm -f temp1 temp2 temp3
	cd ../
    fi
done < $scene_list


# concatenated MLIs
echo "" >> $file
echo "" >> $file
echo "Concatenated MLIs" >> $file
echo "Date" > temp1
echo "Width" > temp2
echo "Length" > temp3
paste temp1 temp2 temp3 >> $file
rm -f temp1 temp2 temp3
while read scene; do
    if [ ! -z $scene ]; then
	cd $scene
	mli=$scene"_"$polar"_"*.mli.par
	echo $scene > temp1
	grep range_samples: $mli | awk '{print $2}' > temp2
	grep azimuth_lines: $mli | awk '{print $2}' > temp3
	paste temp1 temp2 temp3 >> $file
	rm -f temp1 temp2 temp3
	cd ../
    fi
done < $scene_list


# coregistered SLCs
echo "" >> $file
echo "" >> $file
echo "Coregistered SLCs" >> $file
echo "Date" > temp1
echo "Width" > temp2
echo "Length" > temp3
paste temp1 temp2 temp3 >> $file
rm -f temp1 temp2 temp3
while read scene; do
    if [ ! -z $scene ]; then
	cd $scene
	slc=r$scene"_"$polar.slc.par
	echo $scene > temp1
	grep range_samples: $slc | awk '{print $2}' > temp2
	grep azimuth_lines: $slc | awk '{print $2}' > temp3
	paste temp1 temp2 temp3 >> $file
	rm -f temp1 temp2 temp3
	cd ../
    fi
done < $scene_list


# coregistered MLIs
echo "" >> $file
echo "" >> $file
echo "Coregistered MLIs" >> $file
echo "Date" > temp1
echo "Width" > temp2
echo "Length" > temp3
paste temp1 temp2 temp3 >> $file
rm -f temp1 temp2 temp3
while read scene; do
    if [ ! -z $scene ]; then
	cd $scene
	mli=r$scene"_"$polar"_"*.mli.par
	echo $scene > temp1
	grep range_samples: $mli | awk '{print $2}' > temp2
	grep azimuth_lines: $mli | awk '{print $2}' > temp3
	paste temp1 temp2 temp3 >> $file
	rm -f temp1 temp2 temp3
	cd ../
    fi
done < $scene_list

