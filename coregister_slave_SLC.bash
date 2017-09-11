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
    echo "*         <beam>       beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       22/05/2015, v1.1                            *"
    echo "*               added functionality for wide swath beam processing            *"
    echo "*         Matt Garthwaite         29/05/2015, v1.2                            *"
    echo "*               added iterable loop to achieve required offset accuracy       *"
    echo "*         Sarah Lawrie @ GA       23/12/2015, v1.3                            *"
    echo "*               Change snr to cross correlation parameters (process changed   *"
    echo "*               in GAMMA version Dec 2015)                                    *"
    echo "*         Thomas Fuhrmann @ GA    21/10/2016, v1.4                            *"
    echo "*               resolved double usage of $cpp in func. offset_pwr/offset_fit  *"
    echo "*               changed parameter naming from snr to cc_thresh                *"
    echo "*               usage of $npoly for initial offset fit (issue with ASAR SLCs) *"
    echo "*               save statistical output of MLI to file image_stat.txt         *"
    echo "*******************************************************************************"
    echo -e "Usage: coregister_slave_SLC.bash [proc_file] [slave] [rlks] [alks] <beam>"
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
beam=$5

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
subset=`grep Subsetting= $proc_file | cut -d "=" -f 2`
subset_done=`grep Subsetting_done= $proc_file | cut -d "=" -f 2`
## MLI registration params
offset_measure=`grep slv_offset_measure= $proc_file | cut -d "=" -f 2`
slv_win=`grep slv_win= $proc_file | cut -d "=" -f 2`
slv_cct=`grep slv_cc_thresh= $proc_file | cut -d "=" -f 2`
## SLC registration params
cct=`grep coreg_cc_thresh= $proc_file | cut -d "=" -f 2`
npoly=`grep coreg_model_params= $proc_file | cut -d "=" -f 2`
win=`grep coreg_window_size= $proc_file | cut -d "=" -f 2`
nwin=`grep coreg_num_windows= $proc_file | cut -d "=" -f 2`
ovr=`grep coreg_oversampling= $proc_file | cut -d "=" -f 2`
niter=`grep coreg_num_iterations= $proc_file | cut -d "=" -f 2`

## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`

cd $proj_dir

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_SCENE: "$project $track_dir $slave $rlks"rlks" $alks"alks" $beam 1>&2
echo "" 1>&2

## Insert scene details top of NCI .0 file
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

master_dir=$slc_dir/$master
slave_dir=$slc_dir/$slave

#if WB data, need to identify beam in file name
if [ -z $beam ]; then # no beam
    master_slc_name=$master"_"$polar
    slave_slc_name=$slave"_"$polar
    master_mli_name=$master"_"$polar"_"$rlks"rlks"
    slave_mli_name=$slave"_"$polar"_"$rlks"rlks"
else # beam exists
    master_slc_name=$master"_"$polar"_"$beam
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

lt=$slave_dir/$master-$slave_mli_name.lt
off=$slave_dir/$master-$slave_mli_name.off
diff_par=$slave_dir/$master"-"$slave_mli_name"_diff.par"
ccp=$slave_dir/$master_mli_name-$slave_mli_name.ccp
coffs=$slave_dir/$master_mli_name-$slave_mli_name.coffs
offs=$slave_dir/$master_mli_name-$slave_mli_name.offs
offsets=$slave_dir/$master_mli_name-$slave_mli_name.offsets
coffsets=$slave_dir/$master_mli_name-$slave_mli_name.coffsets
stat=$slave_dir/image_stat.txt

## Coregistration results file
if [ -z $beam ]; then
    check_file=$proj_dir/$track_dir/slave_coreg_results"_"$rlks"rlks_"$alks"alks.txt"
else
    check_file=$proj_dir/$track_dir/slave_coreg_results"_"$beam"_"$rlks"rlks_"$alks"alks.txt"
fi

cd $slave_dir

## Determine range and azimuth looks in MLI
echo " "
echo "MLI range and azimuth looks: "$rlks $alks
echo " "

#-------------------------

## files located in DEM directory
rdc_dem=$dem_dir/$master_mli_name"_rdc.dem"

## Generate initial lookup table between master and slave MLI considering terrain heights from DEM coregistered to master
GM rdc_trans $master_mli_par $rdc_dem $slave_mli_par $lt"0"

slave_mli_width=`awk 'NR==11 {print $2}' $slave_mli_par`
master_mli_width=`awk 'NR==11 {print $2}' $master_mli_par`
slave_mli_length=`awk 'NR==12 {print $2}' $slave_mli_par`

GM geocode $lt"0" $master_mli $master_mli_width $rmli $slave_mli_width $slave_mli_length 2 0

## Measure offset and estimate offset polynomials between slave MLI and resampled slave MLI
returns=$slave_dir/returns
echo "" > $returns
echo "" >> $returns
echo $offset_measure >> $returns
echo $slv_win >> $returns
echo $slv_cct >> $returns

GM create_diff_par $slave_mli_par $slave_mli_par $diff_par 1 < $returns
rm -f $returns

## Measure offset between slave MLI and resampled slave MLI
GM init_offsetm $rmli $slave_mli $diff_par 1 1 - - - - $slv_cct - 1

GM offset_pwrm $rmli $slave_mli $diff_par $off"s0" $ccp"0" - - - 2

## Fit the offset using the given number of polynomial coefficients
GM offset_fitm $off"s0" $ccp"0" $diff_par $coffs"0" - $slv_cct $npoly

## Refinement of initial geocoding look up table
GM gc_map_fine $lt"0" $master_mli_width $diff_par $lt

## Resample slave SLC into geometry of master SLC using lookup table
GM SLC_interp_lt $slave_slc $master_slc_par $slave_slc_par $lt $master_mli_par $slave_mli_par - $rslc $rslc_par

#------------------------

## set up iterable loop
i=1
while [ $i -le $niter ]; do

    ioff=$off$i
    rm -f $offs $ccp $offsets $coffsets
    echo "Starting Iteration "$i

## Measure offsets for refinement of lookup table using initially resampled slave SLC
    GM create_offset $master_slc_par $rslc_par $ioff 1 $rlks $alks 0

    GM offset_pwr $master_slc $rslc $master_slc_par $rslc_par $ioff $offs $ccp $win $win $offsets $ovr $nwin $nwin $cct

## Fit polynomial model to offsets
    GM offset_fit $offs $ccp $ioff - $coffsets $cct $npoly 0

## Create blank offset file for first iteration and calculate the total estimated offset
    if [ $i == 1 ]; then
	GM create_offset $master_slc_par $rslc_par $off"0" 1 $rlks $alks 0

	GM offset_add $off"0" $ioff $off
    else
## Calculate the cumulative total estimated offset
	GM offset_add $off $ioff $off
    fi

## if estimated offsets are less than 0.2 of a pixel then break iterable loop
    azoff=`grep "final azimuth offset poly. coeff.:" output.log | tail -2 | head -1 | awk '{print $6}'`
    rgoff=`grep "final range offset poly. coeff.:" output.log | tail -2 | head -1 | awk '{print $6}'`
    test1=`echo $azoff | awk '{if ($1 < 0) $1 = -$1; printf "%i\n", $1*10}'`
    test2=`echo $rgoff | awk '{if ($1 < 0) $1 = -$1; printf "%i\n", $1*10}'`
    echo "Iteration "$i": azimuth offset is "$azoff", range offset is "$rgoff

## Perform resampling of slave SLC using lookup table and offset model
    GM SLC_interp_lt $slave_slc $master_slc_par $slave_slc_par $lt $master_mli_par $slave_mli_par $off $rslc $rslc_par

    if [ $test1 -lt 2 -a $test2 -lt 2 ]; then
	break
    fi
    i=$(($i+1))
done

#-------------------------

GM multi_look $rslc $rslc_par $rmli $rmli_par $rlks $alks

rm -f $off"s0" $ccp"0" $coffs"0" $offs $ccp $coffs $coffsets $lt"0"

## Extract final offset values to check coregistration
echo $master > temp1_$rlks
echo $slave > temp2_$rlks
grep "final range offset poly. coeff.:" output.log | tail -1 | awk '{print $6}' > temp3_$rlks
grep "final azimuth offset poly. coeff.:" output.log | tail -1 | awk '{print $6}' > temp4_$rlks
paste temp1_$rlks temp2_$rlks temp3_$rlks temp4_$rlks >> $check_file
rm -f temp*

# TF: save image statistics in txt file
image_stat $rmli $master_mli_width - - - - $stat
# non-zero samples in $stat can be used to check all slaves are fully included in master

# script end
####################

## Copy errors to NCI error file (.e file)
if [ $platform == NCI ]; then
    cat error.log 1>&2
#    rm temp_log
#else
#    rm temp_log
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

