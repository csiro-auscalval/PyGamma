#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* extract_S1_burst_metadata: Extracts S1 burst corner coordinates using       *"
    echo "*                            GAMMA program 'S1_burstloc' and general          *"
    echo "*                            metadata.                                        *"
    echo "*                                                                             *"
    echo "* input:  [config_file]   name of config file (e.g. S1_burst_config)          *"
    echo "*         [file_list]     list of zip files                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       15/02/2019, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: extract_S1_burst_metadata.bash [config_file] [file_list]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi

config_file=$1
file_list=$2

# Load generic variables
source ~/repo/gamma_insar/S1_FRAME_CREATION/S1_burst_functions $config_file
variables

# Load GAMMA to access GAMMA programs
source $gamma_file

temp_dir=`basename $file_list`

cd $proj_dir
mkdir -p $temp_dir
cd $temp_dir

final_outfile=$proj_dir/$temp_dir/$temp_dir.burst-metadata

echo "Mission Mode ProdType Date Pass Polar AbOrbit RelOrbit Swath BurstNum UniqProdID DatatakeID ResClass ProcLevel ProdClass SceneStart SceneStop IPFVers RawFacil RawDate RawTime RawStart RawStop AzTime Angle DeltaAngle ULLon ULLat URLon URLat LRLon LRLat LLLon LLLat XMLFile GridDir ZipFile" > $final_outfile

while read input; do
    year_mth=`echo $input | awk '{print $1}'`
    year=`echo $year_mth | cut -d '-' -f 1`
    grid=`echo $input | awk '{print $2}'`
    zip=`echo $input | awk '{print $3}'`
    name=`echo $zip | cut -d '.' -f 1`
    date=`echo $name | cut -d '_' -f 6 | cut -d 'T' -f 1`
    anno_dir=$name.SAFE/annotation

    mkdir -p $name
    cd $name

    # make output file
    outfile=$proj_dir/$temp_dir/$name.ind_burst-metadata
    if [ -e $outfile ]; then
	rm -f $outfile
    fi

    # create list of annotation xml files from zip file
    unzip -l $sar_dir/$year/$year_mth/$grid/$zip | grep -E 'annotation/s1' | awk '{print $4}' | cut -d "/" -f 3 > $name"_xml_list"

    # get manifest.safe file
    unzip -j $sar_dir/$year/$year_mth/$grid/$zip $name.SAFE/manifest.safe

    while read xml; do
        ## Extract annotation xml files from zip file
	unzip -j $sar_dir/$year/$year_mth/$grid/$zip $anno_dir/$xml

	## Extract metadata from xml files 
	mission=`awk -F'[<>]' '/<missionId>/{print $3}' $xml`
	mode=`awk -F'[<>]' '/<mode>/{print $3}' $xml`
	product_type=`awk -F'[<>]' '/<productType>/{print $3}' $xml`
	pass=`awk -F'[<>]' '/<pass>/{print $3}' $xml`
	ab_orbit=`awk -F'[<>]' '/<absoluteOrbitNumber>/{print $3}' $xml`
	unique_prodID=`echo $name | cut -d '_' -f 10`
	datatakeID=`awk -F'[<>]' '/<missionDataTakeId>/{print $3}' $xml`
	res_class1=`echo $name | cut -d '_' -f 4`
	if [ -z $res_class1 ]; then
	    res_class='-'
	elif [ $res_class1 == 'F' ]; then
	    res_class='Full'
	elif [ $res_class1 == 'H' ]; then
	    res_class='High'
	elif [ $res_class1 == 'M' ]; then
	    res_class='Medium'
	fi
	processing_level=`echo $name | cut -d '_' -f 5 | cut -c1-1`
	product_class1=`echo $name | cut -d '_' -f 5 | cut -c2-2`
	if [ $product_class1 == 'S' ]; then
	    product_class='Standard'
	elif [ $product_class1 == 'A' ]; then
	    product_class='Annotation'
	fi
	start_time=`awk -F'[<>]' '/<startTime>/{print $3}' $xml`
	stop_time=`awk -F'[<>]' '/<stopTime>/{print $3}' $xml`
	IPF_version=`grep "safe:software name" manifest.safe | awk '{print $4}' | cut -d '"' -f 2`
	raw_facility=`grep "safe:facility country=" manifest.safe | sed -e "s/^            <safe:facility country=//" | sed 's/name=.*//' | sed -e 's/"//g' | awk '{$1=$1};1' | sed -e 's/ /_/g'`
	raw_date=`grep "SLC Processing" manifest.safe | awk '{print $4}' | cut -d '"' -f 2 | cut -d 'T' -f 1`
	raw_time=`grep "SLC Processing" manifest.safe | awk '{print $4}' | cut -d '"' -f 2 | cut -d 'T' -f 2`
	raw_start=`awk -F'[<>]' '/<safe:startTime>/{print $3}' manifest.safe | cut -d 'T' -f 2`
	raw_stop=`awk -F'[<>]' '/<safe:stopTime>/{print $3}' manifest.safe | cut -d 'T' -f 2`

	## Extract coordinates calculated by GAMMA
	S1_burstloc $xml > temp1
	grep '^Burst:' temp1 > temp2
	sed 's/Burst: //g' temp2 > temp3

	while read line; do
        # advised by Urs of the following headers (SL Sep 2018):
	    xml_file=`echo $line | awk '{print $1}'`
	    burst_num=`echo $line | awk '{print $2}'`
	    rel_orbit=`echo $line | awk '{print $3}'`
	    swath=`echo $line | awk '{print $4}'`
	    polar=`echo $line | awk '{print $5}'`
	    azimuth_time=`echo $line | awk '{print $6}'` 
	    angle=`echo $line | awk '{print $7}'` #angle on orbit from ascending node
	    delta_angle=`echo $line | awk '{print $8}'` #angle difference to previous burst
	    ul_lon=`echo $line | awk '{print $14}'`
	    ul_lat=`echo $line | awk '{print $13}'`
	    ur_lon=`echo $line | awk '{print $16}'`	   
	    ur_lat=`echo $line | awk '{print $15}'`
	    lr_lon=`echo $line | awk '{print $10}'`
	    lr_lat=`echo $line | awk '{print $9}'`
	    ll_lon=`echo $line | awk '{print $12}'`
	    ll_lat=`echo $line | awk '{print $11}'`
       	
	    echo $mission $mode $product_type $date $pass $polar $ab_orbit $rel_orbit $swath $burst_num $unique_prodID $datatakeID $res_class $processing_level $product_class $start_time $stop_time $IPF_version $raw_facility $raw_date $raw_time $raw_start $raw_stop $azimuth_time $angle $delta_angle $ul_lon $ul_lat $ur_lon $ur_lat $lr_lon $lr_lat $ll_lon $ll_lat $xml_file $grid $zip >> $outfile
	done < temp3
    done < $name"_xml_list"
    cd ../
done < $file_list

# append coordinates to final outfile
cd $proj_dir/$temp_dir
ls *.ind_burst-metadata > list
while read file; do
    cat $file >> $final_outfile
done < list

# move to final output directories
mv *.ind_burst-metadata $ind_burst_dir
mv *.burst-metadata $burst_dir

cd $proj_dir
rm -rf $temp_dir


