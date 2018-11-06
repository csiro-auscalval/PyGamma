#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* coregister_slave_SLC: Coregisters SLC to chosen master SLC geometry.        *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [slave]      slave scene ID (eg. 20120520)                          *"
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
    echo "*         Sarah Lawrie @ GA       13/08/2018, v2.0                            *"
    echo "*             -  Major update to streamline processing:                       *"
    echo "*                  - use functions for variables and PBS job generation       *"
    echo "*                  - add option to auto calculate multi-look values and       *"
    echo "*                      master reference scene                                 *"
    echo "*                  - add initial and precision baseline calculations          *"
    echo "*                  - add full Sentinel-1 processing, including resizing and   *"
    echo "*                     subsetting by bursts                                    *"
    echo "*                  - remove GA processing option                              *"
    echo "*******************************************************************************"
    echo -e "Usage: coregister_slave_SLC.bash [proc_file] [slave]"
    }

if [ $# -lt 2 ]
then
    display_usage
    exit 1
fi


if [ $2 -lt "10000000" ]; then
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    slave=$2
fi

proc_file=$1


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $slave

######################################################################

## File names
dem_master_names
dem_file_names
slave_file_names

cd $slave_dir



## Generate initial lookup table between master and slave MLI considering terrain heights from DEM coregistered to master
GM rdc_trans $r_dem_master_mli_par $rdc_dem $slave_mli_par $slave_lt"0"

slave_mli_width=`awk 'NR==11 {print $2}' $slave_mli_par`
r_dem_master_mli_width=`awk 'NR==11 {print $2}' $r_dem_master_mli_par`
slave_mli_length=`awk 'NR==12 {print $2}' $slave_mli_par`

GM geocode $slave_lt"0" $r_dem_master_mli $r_dem_master_mli_width $r_slave_mli $slave_mli_width $slave_mli_length 2 0

## Measure offset and estimate offset polynomials between slave MLI and resampled slave MLI
returns=$slave_dir/returns
echo "" > $returns
echo "" >> $returns
echo $slave_offset_measure >> $returns
echo $slave_win2 >> $returns
echo $slave_cct2 >> $returns

GM create_diff_par $slave_mli_par $slave_mli_par $slave_diff_par 1 < $returns
rm -f $returns

## Measure offset between slave MLI and resampled slave MLI
GM init_offsetm $r_slave_mli $slave_mli $slave_diff_par 1 1 - - - - $slave_cct2 - 1

GM offset_pwrm $r_slave_mli $slave_mli $slave_diff_par $slave_off"s0" $slave_ccp"0" - - - 2

## Fit the offset using the given number of polynomial coefficients
GM offset_fitm $slave_off"s0" $slave_ccp"0" $slave_diff_par $slave_coffs"0" - $slave_cct2 $slave_npoly

## Refinement of initial geocoding look up table
GM gc_map_fine $slave_lt"0" $r_dem_master_mli_width $slave_diff_par $slave_lt

## Resample slave SLC into geometry of master SLC using lookup table
GM SLC_interp_lt $slave_slc $r_dem_master_slc_par $slave_slc_par $slave_lt $r_dem_master_mli_par $slave_mli_par - $r_slave_slc $r_slave_slc_par

#------------------------

## set up iterable loop
i=1
while [ $i -le $slave_niter ]; do

    ioff=$slave_off$i
    rm -f $slave_offs $slave_ccp $slave_offsets $slave_coffsets
    echo "Starting Iteration "$i

## Measure offsets for refinement of lookup table using initially resampled slave SLC
    GM create_offset $r_dem_master_slc_par $r_slave_slc_par $ioff 1 $rlks $alks 0

    GM offset_pwr $r_dem_master_slc $r_slave_slc $r_dem_master_slc_par $r_slave_slc_par $ioff $slave_offs $slave_ccp $slave_win $slave_win $slave_offsets $slave_ovr $slave_nwin $slave_nwin $slave_cct

## Fit polynomial model to offsets
    GM offset_fit $slave_offs $slave_ccp $ioff - $slave_coffsets $slave_cct $slave_npoly 0

## Create blank offset file for first iteration and calculate the total estimated offset
    if [ $i == 1 ]; then
	GM create_offset $r_dem_master_slc_par $r_slave_slc_par $slave_off"0" 1 $rlks $alks 0

	GM offset_add $slave_off"0" $ioff $slave_off
    else
## Calculate the cumulative total estimated offset
	GM offset_add $slave_off $ioff $slave_off
    fi

## if estimated offsets are less than 0.2 of a pixel then break iterable loop
    azoff=`grep "final azimuth offset poly. coeff.:" output.log | tail -2 | head -1 | awk '{print $6}'`
    rgoff=`grep "final range offset poly. coeff.:" output.log | tail -2 | head -1 | awk '{print $6}'`
    test1=`echo $azoff | awk '{if ($1 < 0) $1 = -$1; printf "%i\n", $1*10}'`
    test2=`echo $rgoff | awk '{if ($1 < 0) $1 = -$1; printf "%i\n", $1*10}'`
    echo "Iteration "$i": azimuth offset is "$azoff", range offset is "$rgoff

## Perform resampling of slave SLC using lookup table and offset model
    GM SLC_interp_lt $slave_slc $r_dem_master_slc_par $slave_slc_par $slave_lt $r_dem_master_mli_par $slave_mli_par $slave_off $r_slave_slc $r_slave_slc_par

    if [ $test1 -lt 2 -a $test2 -lt 2 ]; then
	break
    fi
    i=$(($i+1))
done

#-------------------------

GM multi_look $r_slave_slc $r_slave_slc_par $r_slave_mli $r_slave_mli_par $rlks $alks

rm -f $slave_off"s0" $slave_ccp"0" $slave_coffs"0" $slave_offs $slave_ccp $slave_coffs $slave_coffsets $slave_lt"0"

## Extract final offset values to check coregistration
echo $master_scene > temp1
echo $slave > temp2
grep "final range offset poly. coeff.:" output.log | tail -1 | awk '{print $6}' > temp3
grep "final azimuth offset poly. coeff.:" output.log | tail -1 | awk '{print $6}' > temp4
paste temp1 temp2 temp3 temp4 >> $slave_check_file
rm -f temp*

# TF: save image statistics in txt file
GM image_stat $r_slave_mli $r_dem_master_mli_width - - - - $slave_stat
# non-zero samples in $slave_stat can be used to check all slaves are fully included in master

# script end
####################

## Copy errors to NCI error file (.e file)
cat error.log 1>&2

