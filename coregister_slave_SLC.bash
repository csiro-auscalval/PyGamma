#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* coregister_slave_SLC: Coregisters SLC to chosen master SLC geometry.        *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [slave]      slave scene ID (eg. 20120520)                          *"
    echo "*         [rlks]       range multi-look value (for SLCs: from *.mli.par file  *"
    echo "*                      or for ifms: from proc file)                           *"
    echo "*         [alks]       azimuth multi-look value (for SLCs: from *.mli.par     *"
    echo "*                      file or for ifms: from proc file)                      *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       19/05/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: coregister_slave_SLC.bash [proc_file] [slave] [rlks] [alks]"
    }

if [ $# -lt 4 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
slave=$2
rlks=$3
alks=$4

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
beam=`grep Beam= $proc_file | cut -d "=" -f 2`
subset=`grep Subsetting= $proc_file | cut -d "=" -f 2`
subset_done=`grep Subsetting_done= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $slave $rlks"rlks" $alks"alks" 1>&2

## Copy output of Gamma programs to log files
#if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    command_log=command.log
    output_log=output.log
    temp_log=temp_log
else # beam exists
    command_log=$beam"_command.log"
    output_log=$beam"_output.log"
    temp_log=$beam"_temp_log"
fi
GM()
{
    echo $* | tee -a $command_log
    echo
    $* >> $output_log 2> $temp_log
    cat $temp_log >> $error_log
    #cat $output_log (option to add output results to NCI .o file if required)
}


## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

master_dir=$slc_dir/$master
slave_dir=$slc_dir/$slave

#if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    master_slc_name=$scene"_"$polar
    slave_slc_name=$slave"_"$polar
    master_mli_name=$master"_"$polar"_"$rlks"rlks"
    slave_mli_name=$slave"_"$polar"_"$rlks"rlks"
else # beam exists
    master_slc_name=$scene"_"$polar"_"$beam
    slave_slc_name=$slave"_"$polar"_"$beam
    master_mli_name=$master"_"$polar"_"$beam"_"$rlks"rlks"
    slave_mli_name=$slave"_"$polar"_"$beam"_"$rlks"rlks"
fi

## files located in SLC directories
master_mli=$master_dir/r$master_mli_name.mli
master_mli_par=$master_mli.par
master_slc=$master_dir/r$master_slc_name.slc
master_slc_par=$master_slc.par

slave_mli=$slave_dir/$slave_mli_name.mli
slave_mli_par=$slave_mli.par
slave_slc=$slave_dir/$slave_slc_name.slc
slave_slc_par=$slave_slc.par

rslc=$slave_dir/r$slave_slc_name.slc 
rslc_par=$rslc.par
rmli=$slave_dir/r$slave_mli_name.mli 
rmli_par=$rmli.par

tslc=$slave_dir/t$slave_slc_name.slc 
tslc_par=$tslc.par
tmli=$slave_dir/t$slave_mli_name.mli 
tmli_par=$tmli.par

lt=$slave_dir/$master_mli_name-$slave_mli_name.lt
off1=$slave_dir/$master_mli_name-$slave_mli_name"_1.off"
off2=$slave_dir/$master_mli_name-$slave_mli_name"_2.off"
#off3=$slave_dir/$master_mli_name-$slave_mli_name"_3.off"
#off=$slave_dir/$master_mli_name-$slave_mli_name.off
lt0=$master_mli_name-$slave_mli_name.lt0
diff_par=$master_mli_name-$slave_mli_name_"diff.par"
offs0=$master_mli_name-$slave_mli_name.offs0
snr=$master_mli_name-$slave_mli_name.snr
coffs0=$master_mli_name-$slave_mli_name.coffs0
offs1=$master_mli_name-$slave_mli_name.offs1
snr1=$master_mli_name-$slave_mli_name.snr1
offsets1=$master_mli_name-$slave_mli_name.offsets1
offs2=$master_mli_name-$slave_mli_name.offs2
snr2=$master_mli_name-$slave_mli_name.snr2
offsets2=$master_mli_name-$slave_mli_name.offsets2

## Set up coregistration results file
#check_file=$slave_dir/slave_coregistration_results"_"$rlks"_rlks_"$alks"_alks.txt"
#if [ -f $check_file ]; then
#    rm -f $check_file 
#else
#    :
#fi
#echo "Slave_Coregistration_Results_"$rlks"_rlks_"$alks"_alks" > $check_file
#echo "final model fit std. dev. (samples)" >> $check_file
#echo "Ref Master" > temp1_$rlks
#echo "Slave" > temp2_$rlks
#echo "Range" > temp3_$rlks
#echo "Azimuth" > temp4_$rlks
#paste temp1_$rlks temp2_$rlks temp3_$rlks temp4_$rlks >> $check_file
#rm -f temp1_$rlks temp2_$rlks temp3_$rlks temp4_$rlks

cd $slave_dir

## Determine range and azimuth looks in MLI
echo " "
echo "MLI range and azimuth looks: "$rlks $alks
echo " "

#-------------------------

## files located in DEM directory
rdc_dem=$dem_dir/$master_mli_name"_rdc.dem"

##Generate initial lookup table between master and slave MLI considering terrain heights from DEM coregistered to master
GM rdc_trans $master_mli_par $rdc_dem $slave_mli_par $lt0

slave_mli_width=`awk 'NR==11 {print $2}' $slave_mli_par`
master_mli_width=`awk 'NR==11 {print $2}' $master_mli_par`
slave_mli_length=`awk 'NR==12 {print $2}' $slave_mli_par`

GM geocode $lt0 $master_mli $master_mli_width $tmli $slave_mli_width $slave_mli_length 2 0

## Measure offset and estimate offset polynomials between slave MLI and resampled slave MLI
GM create_diff_par $slave_mli_par $slave_mli_par $diff_par 1 0

GM init_offsetm $tmli $slave_mli $diff_par 1 1

GM offset_pwrm $tmli $slave_mli $diff_par $offs0 $sr0 - - - 2

GM offset_fitm $offs0 $snr0 $diff_par $coffs0 - - 4

## Refinement of initial geocoding look up table
GM gc_map_fine $lt0 $master_mli_width $diff_par $lt

## Resample slave SLC into geometry of master SLC using lookup table
GM SLC_interp_lt $slave_slc $master_slc_par $slave_slc_par $lt $master_mli_par $slave_mli_par - $tslc $tslc_par

#------------------------

## Measure offsets for second refinement of lookup table using initially resampled slave SLC

GM create_offset $master_slc_par $tslc_par $off1 1 - - 0

GM offset_pwr $master_slc $tslc $master_slc_par $tslc_par $off1 $offs1 $snr1 - - $offsets1 2 

GM offset_fit $offs1 $snr1 $off1 - $coffsets1

#-------------------------

##Perform second resampling of slave SLC using lookup table and offset information

GM SLC_interp_lt $slave_slc $master_slc_par $slave_slc_par $lt $master_mli_par $slave_mli_par $off1 $rslc $rslc_par

GM multi_look $rslc $rslc_par $rmli $rmli_par $rlks $alks

#-------------------------

## Compute final residual offsets
GM create_offset $master_slc_par $rslc_par $off2 1 - - 0

GM offset_pwr $master_slc $rslc $master_slc_par $rslc_par $off2 $offs2 $snr2 - - $offsets2 2 

GM offset_fit $offs2 $snr2 $off2 - $coffsets2

#grep "final model fit std. dev." output.log > temp1
#tail -1 temp1 > temp2
#grep "final range offset poly. coeff.:" output.log > temp3
#tail -1 temp3 > temp4
#grep "final azimuth offset poly. coeff.:" output.log > temp5
#tail -1 temp5 > temp6

rm -f $offs $snr $coffs $coffsets $off1 $off2 $tslc $tslc_par $tmli $lt0

## Extract final model fit values to check coregistration
#echo $master > temp1_$rlks
#echo $slave > temp2_$rlks
#grep "final model fit std. dev." temp2 > temp3_$rlks
#awk '{print $8}' temp3_$rlks > temp4_$rlks
#awk '{print $10}' temp3_$rlks > temp5_$rlks
#paste temp1_$rlks temp2_$rlks temp4_$rlks temp5_$rlks >> $check_file
#rm -f temp*


# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
    cat $error_log 1>&2
    rm $temp_log
else
   rm $temp_log
fi
