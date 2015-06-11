#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* post_ifm_processing:  Copy files from each interferogram directory to a     *"
    echo "*                       central location to check processing results and for  *"
    echo "*                       Pyrate processing.                                    *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [list_type]  ifm list type (1 = ifms.list, 2 = add_ifms.list)       *"
    echo "*         <beam>       Beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       29/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: post_ifm_processing.bash [proc_file] [list_type] <beam>"
    }

if [ $# -lt 2 ]
then 
    display_usage
    exit 1
fi


proc_file=$1
list_type=$2
beam=$3

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`

if [ $list_type -eq 1 ]; then
    ifm_list=`grep List_of_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Creating plots for unwrapped interferograms..."
else
    ifm_list=`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Creating plots for additional unwrapped interferograms..."
fi

cd $proj_dir/$track_dir
mkdir -p png_images
png_dir=$proj_dir/$track_dir/png_images
mkdir -p pyrate_files
pyrate_dir=$proj_dir/$track_dir/pyrate_files
mkdir -p $pyrate_dir/unw_files
mkdir -p $pyrate_dir/dem_files
mkdir -p $pyrate_dir/cc_files

## Copy files to central directories
if [ -z $beam ]; then #no beam
    while read list; do
	if [ ! -z $list ]; then
	    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifm_dir=$int_dir/$mas-$slv
	    png=$mas-$slv"_"$polar"_"$ifm_looks"rlks_utm_unw.png"
	    unw=$mas-$slv"_"$polar"_"$ifm_looks"rlks_utm.unw"
	    cc=$mas-$slv"_"$polar"_"$ifm_looks"rlks_filt.cc"
	    dem=$master"_"$polar"_"$ifm_looks"rlks_utm.dem"
	    dem_par=$dem.par
	    cp $ifm_dir/$png $png_dir
	    cp $ifm_dir/unw_gmt.par $png_dir
	    cp $ifm_dir/$unw $pyrate_files/unw_files
	    cp $ifm_dir/$cc $pyrate_files/cc_files
	    cp $dem_dir/$dem $pyrate_files/dem_files
	    cp $dem_dir/$dem_par $pyrate_files/dem_files
	fi
    done < $ifm_list
else #beam exists
    while read list; do
	if [ ! -z $list ]; then
	    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifm_dir=$int_dir/$mas-$slv
	    png=$mas-$slv"_"$polar"_"$beam"_"$ifm_looks"rlks_utm_unw.png"
	    unw=$mas-$slv"_"$polar"_"$beam"_"$ifm_looks"rlks_utm.unw"
	    cc=$mas-$slv"_"$polar"_"$beam"_"$ifm_looks"rlks_filt.cc"
	    dem=$master"_"$polar"_"$beam"_"$ifm_looks"rlks_utm.dem"
	    dem_par=$dem.par
	    cp $ifm_dir/$png $png_dir
	    cp $ifm_dir/unw_gmt.par $png_dir
	    cp $ifm_dir/$unw $pyrate_files/unw_files
	    cp $ifm_dir/$cc $pyrate_files/cc_files
	    cp $dem_dir/$dem $pyrate_files/dem_files
	    cp $dem_dir/$dem_par $pyrate_files/dem_files
	fi
    done < $ifm_list
fi

## Plot unwrapped interferograms with png files
cd $png_dir
ls *.png > png_files

# Split image_files into 36 ifm chunks
num_ifms=`cat image_files | sed '/^\s*$/d' | wc -l`
split -dl 36 png_files png_files_
mv png_files all_png_files
echo png_files_* > temp
cat temp | tr " " "\n" > png_files.list
rm -rf temp

# Plot png files
image_files=$png_dir/png_files.list
while read list; do
    for ((i=1;; i++)); do
	read "d$i" || break;
    done < $list
    png1=$d1
    name1=`echo $png1 | awk -F "_" '{print $1}'`
    png2=$d2
    name2=`echo $png2 | awk -F "_" '{print $1}'`
    png3=$d3
    name3=`echo $png3 | awk -F "_" '{print $1}'`
    png4=$d4
    name4=`echo $png4 | awk -F "_" '{print $1}'`
    png5=$d5
    name5=`echo $png5 | awk -F "_" '{print $1}'`
    png6=$d6
    name6=`echo $png6 | awk -F "_" '{print $1}'`
    png7=$d7
    name7=`echo $png7 | awk -F "_" '{print $1}'`
    png8=$d8
    name8=`echo $png8 | awk -F "_" '{print $1}'`
    png9=$d9
    name9=`echo $png9 | awk -F "_" '{print $1}'`
    png10=$d10
    name10=`echo $png10 | awk -F "_" '{print $1}'`
    png11=$d11
    name11=`echo $png11 | awk -F "_" '{print $1}'`
    png12=$d12
    name12=`echo $png12 | awk -F "_" '{print $1}'`
    png13=$d13
    name13=`echo $png13 | awk -F "_" '{print $1}'`
    png14=$d14
    name14=`echo $png14 | awk -F "_" '{print $1}'`
    png15=$d15
    name15=`echo $png15 | awk -F "_" '{print $1}'`
    png16=$d16
    name16=`echo $png16 | awk -F "_" '{print $1}'`
    png17=$d17
    name17=`echo $png17 | awk -F "_" '{print $1}'`
    png18=$d18
    name18=`echo $png18 | awk -F "_" '{print $1}'`
    png19=$d19
    name19=`echo $png19 | awk -F "_" '{print $1}'`
    png20=$d20
    name20=`echo $png20 | awk -F "_" '{print $1}'`
    png21=$d21
    name21=`echo $png21 | awk -F "_" '{print $1}'`
    png22=$d22
    name22=`echo $png22 | awk -F "_" '{print $1}'`
    png23=$d23
    name23=`echo $png23 | awk -F "_" '{print $1}'`
    png24=$d24
    name24=`echo $png24 | awk -F "_" '{print $1}'`
    png25=$d25
    name25=`echo $png25 | awk -F "_" '{print $1}'`
    png26=$d26
    name26=`echo $png26 | awk -F "_" '{print $1}'`
    png27=$d27
    name27=`echo $png27 | awk -F "_" '{print $1}'`
    png28=$d28
    name28=`echo $png28 | awk -F "_" '{print $1}'`
    png29=$d29
    name29=`echo $png29 | awk -F "_" '{print $1}'`
    png30=$d30
    name30=`echo $png30 | awk -F "_" '{print $1}'`
    png31=$d31
    name31=`echo $png31 | awk -F "_" '{print $1}'`
    png32=$d32
    name32=`echo $png32 | awk -F "_" '{print $1}'`
    png33=$d33
    name33=`echo $png33 | awk -F "_" '{print $1}'`
    png34=$d34
    name34=`echo $png34 | awk -F "_" '{print $1}'`
    png35=$d35
    name35=`echo $png35 | awk -F "_" '{print $1}'`
    png36=$d36
    name36=`echo $png36 | awk -F "_" '{print $1}'`

    gmtset PS_MEDIA A4
    outline="-JX21c/29.7c"
    range="-R0/100/0/10"
    box="-W3c/4c -Fthin"
    font="-F+f8p"

    psfile=$list.ps

psbasemap $outline $range -X0c -Y-1c -Bnesw -P -K > $psfile

pstext $outline $range -F+cTC+f15p -O -P -K <<EOF >> $psfile
$project $sensor $track_dir $polar $ifm_looks"rlks" Unwrapped Interferograms
EOF

# 1st row
psimage $png1 $box -C0.5c/24.1c -O -P -K >> $psfile # top left left corner
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 9.515 $name1 
EOF
psimage $png2 $box -C3.9c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 9.515 $name2
EOF
psimage $png3 $box -C7.3c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 9.515 $name3
EOF
psimage $png4 $box -C10.7c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 9.515 $name4
EOF
psimage $png5 $box -C14.1c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 9.515 $name5
EOF
psimage $png6 $box -C17.5c/24.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 9.515 $name6
EOF

# 2nd row
psimage $png7 $box -C0.5c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 8 $name7
EOF
psimage $png8 $box -C3.9c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 8 $name8
EOF
psimage $png9 $box -C7.3c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 8 $name9
EOF
psimage $png10 $box -C10.7c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 8 $name10
EOF
psimage $png11 $box -C14.1c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 8 $name11
EOF
psimage $png12 $box -C17.5c/19.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 8 $name12
EOF

# 3rd row
psimage $png13 $box -C0.5c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 6.485 $name13
EOF
psimage $png14 $box -C3.9c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 6.485 $name14
EOF
psimage $png15 $box -C7.3c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 6.485 $name15
EOF
psimage $png16 $box -C10.7c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 6.485 $name16
EOF
psimage $png17 $box -C14.1c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 6.485 $name17
EOF
psimage $png18 $box -C17.5c/15.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 6.485 $name18
EOF

# 4th row
psimage $png19 $box -C0.5c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 4.97 $name19
EOF
psimage $png20 $box -C3.9c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 4.97 $name20
EOF
psimage $png21 $box -C7.3c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 4.97 $name21
EOF
psimage $png22 $box -C10.7c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 4.97 $name22
EOF
psimage $png23 $box -C14.1c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 4.97 $name23
EOF
psimage $png24 $box -C17.5c/10.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 4.97 $name24
EOF

# 5th row
psimage $png25 $box -C0.5c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 3.455 $name25
EOF
psimage $png26 $box -C3.9c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 3.455 $name26
EOF
psimage $png27 $box -C7.3c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 3.455 $name27
EOF
psimage $png28 $box -C10.7c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 3.455 $name28
EOF
psimage $png29 $box -C14.1c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 3.455 $name29
EOF
psimage $png30 $box -C17.5c/6.1c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
90.3 3.455 $name30
EOF

# 6th row
psimage $png31 $box -C0.5c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
9.5 1.94 $name31
EOF
psimage $png32 $box -C3.9c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
25.85 1.94 $name32
EOF
psimage $png33 $box -C7.3c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
41.95 1.94 $name33
EOF
psimage $png34 $box -C10.7c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
58.1 1.94 $name34
EOF
psimage $png35 $box -C14.1c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P -K <<EOF >> $psfile
74.4 1.94 $name35
EOF
psimage $png36 $box -C17.5c/1.6c/BL -O -P -K >> $psfile
pstext $outline $range $font -O -P <<EOF >> $psfile
90.3 1.94 $name36
EOF

done < $image_files

# Combine all psfiles into one PDF
pdf=$project"_"$sensor"_"$track_dir"_"$polar"_"$ifm_looks"rlks_Interferograms"
ps2raster -TF -F$pdf *.ps

echo " "
echo "Plots created for unwrapped geocoded interferograms."
echo " "





