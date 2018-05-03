#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* coregister_master_DEMs: Coregisters master SLCs for different DEMs to a     *"
    echo "*                         master DEM geometry.                                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [mas_proj]   name of master project to resample to                  *"
    echo "*         [rlks]       range multi-look value (for SLCs: from *.mli.par file  *"
    echo "*                      or for ifms: from proc file)                           *"
    echo "*         [alks]       azimuth multi-look value (for SLCs: from *.mli.par     *"
    echo "*                      file or for ifms: from proc file)                      *"
    echo "*         <beam>       beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Matt Garthwaite         01/06/2015, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: coregister_slave_SLC.bash [proc_file] [mas_proj] [rlks] [alks] <beam>"
    }

if [ $# -lt 4 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
master_proj=$2
rlks=$3
alks=$4
beam=$5

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
#subset=`grep Subsetting= $proc_file | cut -d "=" -f 2`
#subset_done=`grep Subsetting_done= $proc_file | cut -d "=" -f 2`
## MLI registration params
#offset_measure=`grep slv_offset_measure= $proc_file | cut -d "=" -f 2`
#slv_win=`grep slv_win= $proc_file | cut -d "=" -f 2`
#slv_snr=`grep slv_snr= $proc_file | cut -d "=" -f 2`
## SLC registration params
#snr=`grep coreg_snr_thresh= $proc_file | cut -d "=" -f 2`
#npoly=`grep coreg_model_params= $proc_file | cut -d "=" -f 2`
#win=`grep coreg_window_size= $proc_file | cut -d "=" -f 2`
#nwin=`grep coreg_num_windows= $proc_file | cut -d "=" -f 2`
#ovr=`grep coreg_oversampling= $proc_file | cut -d "=" -f 2`
#niter=`grep coreg_num_iterations= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
    master_proj_dir=$nci_path/INSAR_ANALYSIS/$master_proj/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
    master_proj_dir=$nci_path/INSAR_ANALYSIS/$master_proj/$sensor/GAMMA
fi

master_slc_dir=$master_proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
master_dem_dir=$master_proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $slave $rlks"rlks" $alks"alks" $beam 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING_SCENE: "$project $track_dir $slave $rlks"rlks" $alks"alks" $beam
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

master_dir=$master_slc_dir/$master
slave_dir=$slc_dir/$master

#if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    master_slc_name=$master"_"$polar
    slave_slc_name=$master"_"$polar
    master_mli_name=$master"_"$polar"_"$rlks"rlks"
    slave_mli_name=$master"_"$polar"_"$rlks"rlks"
else # beam exists
    master_slc_name=$master"_"$polar"_"$beam
    slave_slc_name=$master"_"$polar"_"$beam
    master_mli_name=$master"_"$polar"_"$beam"_"$rlks"rlks"
    slave_mli_name=$master"_"$polar"_"$beam"_"$rlks"rlks"
fi

## files located in SLC directories
master_mli=$master_dir/r$master_mli_name.mli
master_mli_par=$master_mli.par
master_slc=$master_dir/r$master_slc_name.slc
master_slc_par=$master_slc.par

tmli=$slave_dir/p$slave_mli_name.mli
tmli_par=$tmli.par
tslc=$slave_dir/p$slave_slc_name.slc
tslc_par=$tslc.par

rslc=$slave_dir/r$slave_slc_name.slc 
rslc_par=$rslc.par
rmli=$slave_dir/r$slave_mli_name.mli 
rmli_par=$rmli.par

## files located in DEM directory
mrdc_dem=$master_dem_dir/$master_mli_name"_rdc.dem"
rdc_dem=$dem_dir/$master_mli_name"_rdc.dem"
trdc_dem=$dem_dir/t$master_mli_name"_rdc.dem"
#rdc_sim=$dem_dir/$master_mli_name"_rdc.sim"

# preserve original slcs aligned to 'local' DEM
cp -f $rslc $tslc
cp -f $rslc_par $tslc_par
cp -f $rmli $tmli
cp -f $rmli_par $tmli_par
cp -f $rdc_dem $trdc_dem

lt=$slave_dir/$master_proj-$project.lt
off=$slave_dir/$master_proj-$project.off
diff_par=$slave_dir/$master_proj-$project"_diff.par"

cd $slave_dir

## Determine range and azimuth looks in MLI
echo " "
echo "MLI range and azimuth looks: "$rlks $alks
echo " "

#echo $master_mli
#echo $master_slc
#echo $tmli
#echo $tslc
#echo $rmli
#echo $rslc
#echo $trdc_dem

#-------------------------

## measure offset to master SLC geometry

## Measure offset 
GM create_offset $master_slc_par $tslc_par $off 1 $rlks $alks 0

GM offset_pwr $master_slc $tslc $master_slc_par $tslc_par $off offs snr 512 512 offsets 2 32 32 -

## Fit offset
GM offset_fit offs snr $off - coffsets - 1 0

## Resample SLC
GM SLC_interp $tslc $master_slc_par $tslc_par $off $rslc $rslc_par 0 0

#-------------------------

## Determine the offset between resampled slave MLI and the original slave RDC DEM

## Generate initial lookup table between master and slave MLI considering terrain heights from DEM coregistered to master
GM rdc_trans $master_mli_par $mrdc_dem $tmli_par lt0

pmli_width=`awk 'NR==11 {print $2}' $tmli_par`
master_mli_width=`awk 'NR==11 {print $2}' $master_mli_par`
pmli_length=`awk 'NR==12 {print $2}' $tmli_par`

GM geocode lt0 $master_mli $master_mli_width $rmli $tmli_width $tmli_length 2 0

GM create_diff_par $master_mli_par $tmli_par $diff_par 1 0

## Measure offset between slave MLI and resampled slave MLI
GM init_offsetm $master_mli $rmli $diff_par 1 1 - - - - $slv_snr - 1

GM offset_pwrm $master_rmli $rmli $diff_par offs0 snr0 128 128 - 2 16 16

## Fit the offset only
GM offset_fitm offs0 snr0 $diff_par coffs0 - - 1 0

## Refinement of initial geocoding look up table
GM gc_map_fine lt0 $master_mli_width $diff_par $lt

## Resample slave MLI into geometry of master MLI using lookup table
GM MLI_interp_lt $tmli $master_mli_par $tmli_par $lt $master_mli_par $tmli_par $diff_par $rmli $rmli_par

GM MLI_interp_lt $trdc_dem $master_mli_par $tmli_par $lt $master_mli_par $tmli_par $diff_par $rdc_dem $rdc_dem.par

#GM multi_look $rslc $rslc_par $rmli $rmli_par $rlks $alks

#GM MLI_interp_lt p$rdc_sim $master_mli_par $pmli_par $lt $master_mli_par $pmli_par $diff_par $rdc_sim $rdc_sim.par

#rm -f offs0 snr0 coffs0 offs snr coffs coffsets lt0

## Extract final model fit values to check coregistration
#echo $master > temp1_$rlks
#echo $slave > temp2_$rlks
#grep "final" temp2 > temp3_$rlks
#awk '{print $8}' temp3_$rlks > temp4_$rlks
#awk '{print $10}' temp3_$rlks > temp5_$rlks
#paste temp1_$rlks temp2_$rlks temp4_$rlks temp5_$rlks >> $check_file
#rm -f temp*


# script end 
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
    cat error.log 1>&2
    rm temp_log
else
    rm temp_log
fi

## Rename log files if beam exists
if [ -z $beam ]; then # no beam
    :    
else # beam exists
    if [ -f $beam"_command.log" ]; then
	cat command.log >>$beam"_command.log"
    else
	mv command.log $beam"_command.log"
    fi
    if [ -f $beam"_output.log" ]; then
	cat output.log >>$beam"_output.log"
    else
	mv output.log $beam"_output.log"
    fi
    if [ -f $beam"_error.log" ]; then
	cat error.log >>$beam"_error.log"
    else
	mv error.log $beam"_error.log"
    fi
fi

