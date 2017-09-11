#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* plot_filt_cc_files:  Copy coherence files from each interferogram directory *"
    echo "*                      to a central location and check processing results.    *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [list_type]  ifm list type (1 = ifms.list, 2 = add_ifms.list)       *"
    echo "*         [rlks]       range multi-look value                                 *"
    echo "*         [alks]       azimuth multi-look value                               *"
    echo "*         <beam>       Beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/08/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: plot_filt_cc_files.bash [proc_file] [list_type] [rlks] [alks] <beam>"
    }

if [ $# -lt 4 ]
then 
    display_usage
    exit 1
fi


proc_file=$1
list_type=$2
ifm_rlks=$3
ifm_alks=$4
beam=$5

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING PROJECT: "$project $track_dir 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir
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

int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`

if [ $list_type -eq 1 ]; then
    ifm_list=$proj_dir/$track_dir/lists/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Creating plots for filtered coherence files..."
else
    ifm_list=$proj_dir/$track_dir/lists/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Creating plots for additional filtered coherence files..."
fi


png_dir=$proj_dir/$track_dir/png_images/png_filt_cc_files
pyrate_dir=$proj_dir/$track_dir/pyrate_files/filt_cc_files

## Copy unw files to central directory
if [ -z $beam ]; then #no beam
    while read list; do
	if [ ! -z $list ]; then
	    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifm_dir=$int_dir/$mas-$slv
	    file=$mas-$slv"_"$polar"_"$ifm_looks"rlks_filt_utm.cc"
	    png=$mas-$slv"_"$polar"_"$ifm_looks"rlks_filt_utm_cc.png"
	    cp $ifm_dir/$file $pyrate_dir
	    cp $ifm_dir/ifg.rsc $pyrate_dir
	    cp $ifm_dir/$png $png_dir
	fi
    done < $ifm_list

cd $pyrate_dir
ls *.cc > filt_cc_list

else #beam exists
    while read list; do
	if [ ! -z $list ]; then
	    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifm_dir=$int_dir/$mas-$slv
	    file=$mas-$slv"_"$polar"_"$beam"_"$ifm_looks"rlks_filt_utm.cc"
	    png=$mas-$slv"_"$polar"_"$beam"_"$ifm_looks"rlks_filt_utm_cc.png"
	    cp $ifm_dir/$file $pyrate_dir
	    cp $ifm_dir/ifg.rsc $pyrate_dir
	    cp $ifm_dir/$png $png_dir
	fi
    done < $ifm_list

cd $pyrate_dir
ls *.cc > filt_cc_list

fi

cd $png_dir

# remove any existing ps and pdf files
rm -rf *.pdf *.ps

ls *.png > png_files

# Split image_files into 36 image chunks
num_ifms=`cat png_files | sed '/^\s*$/d' | wc -l`
split -dl 36 png_files png_files_
mv png_files all_png_files
echo png_files_* > temp
cat temp | tr " " "\n" > png_files.list
rm -rf temp

# Plot png files
image_files=$png_dir/png_files.list
while read list; do
    if [ ! -z $list ]; then
	old_IFS=$IFS
	IFS=$'\n'
	lines=($(cat $list))
	IFS=$old_IFS
	
    png1=`echo ${lines[0]}`
    name1=`echo $png1 | awk -F "_" '{print $1}'`
    png2=`echo ${lines[1]}`
    name2=`echo $png2 | awk -F "_" '{print $1}'`
    png3=`echo ${lines[2]}`
    name3=`echo $png3 | awk -F "_" '{print $1}'`
    png4=`echo ${lines[3]}`
    name4=`echo $png4 | awk -F "_" '{print $1}'`
    png5=`echo ${lines[4]}`
    name5=`echo $png5 | awk -F "_" '{print $1}'`
    png6=`echo ${lines[5]}`
    name6=`echo $png6 | awk -F "_" '{print $1}'`
    png7=`echo ${lines[6]}`
    name7=`echo $png7 | awk -F "_" '{print $1}'`
    png8=`echo ${lines[7]}`
    name8=`echo $png8 | awk -F "_" '{print $1}'`
    png9=`echo ${lines[8]}`
    name9=`echo $png9 | awk -F "_" '{print $1}'`
    png10=`echo ${lines[9]}`
    name10=`echo $png10 | awk -F "_" '{print $1}'`
    png11=`echo ${lines[10]}`
    name11=`echo $png11 | awk -F "_" '{print $1}'`
    png12=`echo ${lines[11]}`
    name12=`echo $png12 | awk -F "_" '{print $1}'`
    png13=`echo ${lines[12]}`
    name13=`echo $png13 | awk -F "_" '{print $1}'`
    png14=`echo ${lines[13]}`
    name14=`echo $png14 | awk -F "_" '{print $1}'`
    png15=`echo ${lines[14]}`
    name15=`echo $png15 | awk -F "_" '{print $1}'`
    png16=`echo ${lines[15]}`
    name16=`echo $png16 | awk -F "_" '{print $1}'`
    png17=`echo ${lines[16]}`
    name17=`echo $png17 | awk -F "_" '{print $1}'`
    png18=`echo ${lines[17]}`
    name18=`echo $png18 | awk -F "_" '{print $1}'`
    png19=`echo ${lines[18]}`
    name19=`echo $png19 | awk -F "_" '{print $1}'`
    png20=`echo ${lines[19]}`
    name20=`echo $png20 | awk -F "_" '{print $1}'`
    png21=`echo ${lines[20]}`
    name21=`echo $png21 | awk -F "_" '{print $1}'`
    png22=`echo ${lines[21]}`
    name22=`echo $png22 | awk -F "_" '{print $1}'`
    png23=`echo ${lines[22]}`
    name23=`echo $png23 | awk -F "_" '{print $1}'`
    png24=`echo ${lines[23]}`
    name24=`echo $png24 | awk -F "_" '{print $1}'`
    png25=`echo ${lines[24]}`
    name25=`echo $png25 | awk -F "_" '{print $1}'`
    png26=`echo ${lines[25]}`
    name26=`echo $png26 | awk -F "_" '{print $1}'`
    png27=`echo ${lines[26]}`
    name27=`echo $png27 | awk -F "_" '{print $1}'`
    png28=`echo ${lines[27]}`
    name28=`echo $png28 | awk -F "_" '{print $1}'`
    png29=`echo ${lines[28]}`
    name29=`echo $png29 | awk -F "_" '{print $1}'`
    png30=`echo ${lines[29]}`
    name30=`echo $png30 | awk -F "_" '{print $1}'`
    png31=`echo ${lines[30]}`
    name31=`echo $png31 | awk -F "_" '{print $1}'`
    png32=`echo ${lines[31]}`
    name32=`echo $png32 | awk -F "_" '{print $1}'`
    png33=`echo ${lines[32]}`
    name33=`echo $png33 | awk -F "_" '{print $1}'`
    png34=`echo ${lines[33]}`
    name34=`echo $png34 | awk -F "_" '{print $1}'`
    png35=`echo ${lines[34]}`
    name35=`echo $png35 | awk -F "_" '{print $1}'`
    png36=`echo ${lines[35]}`
    name36=`echo $png36 | awk -F "_" '{print $1}'`

    gmtset PS_MEDIA A4
    outline="-JX21c/29.7c"
    range="-R0/100/0/10"
    box="-W3c/4c -Fthin"
    font="-F+f8p"

    psfile=$list.ps

psbasemap $outline $range -X0c -Y-1c -Bnesw -P -K > $psfile

pstext $outline $range -F+cTC+f15p -O -P -K <<EOF >> $psfile
$project $sensor $track_dir $polar $ifm_looks rlks Filtered Coherence
EOF

# 1st row
psimage $png1 $box -C0.5c/24.1c -O -P -K >> $psfile # top left left corner
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 9.515 $name1 
EOF
if [ -z $png2 ]; then
     : #do nothing if variable is empty
else
psimage $png2 $box -C3.9c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 9.515 $name2
EOF
fi
if [ -z $png3 ]; then
     : #do nothing if variable is empty
else
psimage $png3 $box -C7.3c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 9.515 $name3
EOF
fi
if [ -z $png4 ]; then
     : #do nothing if variable is empty
else
psimage $png4 $box -C10.7c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 9.515 $name4
EOF
fi
if [ -z $png5 ]; then
     : #do nothing if variable is empty
else
psimage $png5 $box -C14.1c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 9.515 $name5
EOF
fi
if [ -z $png6 ]; then
     : #do nothing if variable is empty
else
psimage $png6 $box -C17.5c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 9.515 $name6
EOF
fi

# 2nd row
if [ -z $png7 ]; then
     : #do nothing if variable is empty
else
psimage $png7 $box -C0.5c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 8 $name7
EOF
fi
if [ -z $png8 ]; then
     : #do nothing if variable is empty
else
psimage $png8 $box -C3.9c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 8 $name8
EOF
fi
if [ -z $png9 ]; then
     : #do nothing if variable is empty
else
psimage $png9 $box -C7.3c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 8 $name9
EOF
fi
if [ -z $png10 ]; then
     : #do nothing if variable is empty
else
psimage $png10 $box -C10.7c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 8 $name10
EOF
fi
if [ -z $png11 ]; then
     : #do nothing if variable is empty
else
psimage $png11 $box -C14.1c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 8 $name11
EOF
fi
if [ -z $png12 ]; then
     : #do nothing if variable is empty
else
psimage $png12 $box -C17.5c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 8 $name12
EOF
fi

# 3rd row
if [ -z $png13 ]; then
     : #do nothing if variable is empty
else
psimage $png13 $box -C0.5c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 6.485 $name13
EOF
fi
if [ -z $png14 ]; then
     : #do nothing if variable is empty
else
psimage $png14 $box -C3.9c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 6.485 $name14
EOF
fi
if [ -z $png15 ]; then
     : #do nothing if variable is empty
else
psimage $png15 $box -C7.3c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 6.485 $name15
EOF
fi
if [ -z $png16 ]; then
     : #do nothing if variable is empty
else
psimage $png16 $box -C10.7c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 6.485 $name16
EOF
fi
if [ -z $png17 ]; then
     : #do nothing if variable is empty
else
psimage $png17 $box -C14.1c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 6.485 $name17
EOF
fi
if [ -z $png18 ]; then
     : #do nothing if variable is empty
else
psimage $png18 $box -C17.5c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 6.485 $name18
EOF
fi

# 4th row
if [ -z $png19 ]; then
     : #do nothing if variable is empty
else
psimage $png19 $box -C0.5c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 4.97 $name19
EOF
fi
if [ -z $png20 ]; then
     : #do nothing if variable is empty
else
psimage $png20 $box -C3.9c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 4.97 $name20
EOF
fi
if [ -z $png21 ]; then
     : #do nothing if variable is empty
else
psimage $png21 $box -C7.3c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 4.97 $name21
EOF
fi
if [ -z $png22 ]; then
     : #do nothing if variable is empty
else
psimage $png22 $box -C10.7c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 4.97 $name22
EOF
fi
if [ -z $png23 ]; then
     : #do nothing if variable is empty
else
psimage $png23 $box -C14.1c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 4.97 $name23
EOF
fi
if [ -z $png24 ]; then
     : #do nothing if variable is empty
else
psimage $png24 $box -C17.5c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 4.97 $name24
EOF
fi

# 5th row
if [ -z $png25 ]; then
     : #do nothing if variable is empty
else
psimage $png25 $box -C0.5c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 3.455 $name25
EOF
fi
if [ -z $png26 ]; then
     : #do nothing if variable is empty
else
psimage $png26 $box -C3.9c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 3.455 $name26
EOF
fi
if [ -z $png27 ]; then
     : #do nothing if variable is empty
else
psimage $png27 $box -C7.3c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 3.455 $name27
EOF
fi
if [ -z $png28 ]; then
     : #do nothing if variable is empty
else
psimage $png28 $box -C10.7c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 3.455 $name28
EOF
fi
if [ -z $png29 ]; then
     : #do nothing if variable is empty
else
psimage $png29 $box -C14.1c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 3.455 $name29
EOF
fi
if [ -z $png30 ]; then
     : #do nothing if variable is empty
else
psimage $png30 $box -C17.5c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 3.455 $name30
EOF
fi

# 6th row
if [ -z $png31 ]; then
     : #do nothing if variable is empty
else
psimage $png31 $box -C0.5c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 1.94 $name31
EOF
fi
if [ -z $png32 ]; then
     : #do nothing if variable is empty
else
psimage $png32 $box -C3.9c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 1.94 $name32
EOF
fi
if [ -z $png33 ]; then
     : #do nothing if variable is empty
else
psimage $png33 $box -C7.3c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 1.94 $name33
EOF
fi
if [ -z $png34 ]; then
     : #do nothing if variable is empty
else
psimage $png34 $box -C10.7c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 1.94 $name34
EOF
fi
if [ -z $png35 ]; then
     : #do nothing if variable is empty
else
psimage $png35 $box -C14.1c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 1.94 $name35
EOF
fi
if [ -z $png36 ]; then
     : #do nothing if variable is empty
else
psimage $png36 $box -C17.5c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 1.94 $name36
EOF
fi

# add page number
num=`echo $list | awk -F "_" '{print $3}' | bc`
num=`echo $num + 1 | bc`
pstext $outline $range $font -O -P <<EOF >> $psfile
50.025 0.5 $num
EOF

# create PDF
ps2raster -Tf $psfile

    fi
done < $image_files

# Combine all PDFs into one PDF
if [ -z $beam ]; then
    pdf=$project"_"$sensor"_"$track_dir"_"$polar"_"$ifm_looks"rlks_filt_cc"
else
    pdf=$project"_"$sensor"_"$track_dir"_"$polar"_"$beam"_"$ifm_looks"rlks_filt_cc"
fi

ps2raster -TF -F$pdf *.pdf

mv $pdf.pdf $proj_dir/$track_dir

echo " "
echo "Plots created for filtered coherence files."
echo " "

# Clean up files
rm -rf *.ps *.pdf

