#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* coregister_S1_slave_rerun: read TxxxX_slave_coreg_results                   *"
    echo "*                            find poorly coregistered scenes                  *"
    echo "*                            rerun coregistration using the closest slave SLC *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Thomas Fuhrmann @ GA       03/09/2018, v1.0                         *"
    echo "*******************************************************************************"
    echo -e "Usage: coregister_s1_slave_rerun.bash [proc_file] [type]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi

proc_file=$1

if [ $# -eq 2 ]
then
    # 1: rerun slave coregistration for badly coregistered scenes
    # 0: output only, no rerun
    rerun=$2
fi


##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc
slave_file_names
pbs_job_dirs

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track

######################################################################

# in case an old results file shall be used (change lines 58 and 96):
#slave_check_file2=$results_dir/$track"_slave_coreg_results_tree63_cc06_ph08"

# slaves to be rerun are saved into new list
rerun_slave_list=$results_dir/$track"_rerun_S1_slave_coreg.list"
rerun_slave_date_list=$results_dir/$track"_rerun_S1_slave_coreg_datediff.list"
rerun_slave_batch=$results_dir/$track"_rerun_S1_slave_coreg_batch.list"
rerun_slave_temp=$results_dir/$track"_rerun_S1_slave_coreg_temp.list"
if [ -f $rerun_slave_list ]; then
  rm $rerun_slave_list
  rm $rerun_slave_date_list
  rm $rerun_slave_batch
fi

# Read TxxxX_slave_coreg_results file and check that all slaves have been processed
echo Slave date, Average and Standard Deviation of burst offsets in the three swaths:
while read slave; do
  # get the line number of current slave in slave_check_file
  start_line=`grep -n $slave $slave_check_file | cut -f1 -d:`
  iterations=0 # number of iterations given in az_ovr_iterations
  found=0 # set to 1 when the first IW3_average is read
  found_first=1 # set to 0 after first average and std are echoed
  it=0 # increased with each iteration of IW3_average
    while read -r line; do
#   if [ $found -eq 1 ]; then # read the next lines
    line1=`echo $line | cut -d " " -f1`
    line1b=`echo $line1 | cut -c1-16`
    if [ "$line1b" == "az_ovr_iteration" ]; then
      iterations=`echo $line1 | cut -c18` # read the number of iterations
    fi
    line2=`echo $line | cut -d " " -f1-2`
    if [ "$line2" == "IW1 average:" ]; then
      IW1_average=`echo $line | cut -d " " -f 3`
    fi
    if [ "$line2" == "IW2 average:" ]; then
      IW2_average=`echo $line | cut -d " " -f 3`
    fi
    if [ "$line2" == "IW3 average:" ]; then
      IW3_average=`echo $line | cut -d " " -f 3`
      found=1
      it=$(($it+1))
    fi
    # check average and standard deviation of IW1, IW2 and IW3 average for first iteration
    if [ $found_first -eq 1 -a $it -eq 1 ]; then
      average=`echo "scale=5 ; ($IW1_average + $IW2_average + $IW3_average)/3" | bc -l`
      std_dev=`echo "scale=5 ; sqrt((($IW1_average - $average)^2+($IW2_average - $average)^2+($IW3_average - $average)^2)/3)" | bc -l`
      #echo $slave $average $std_dev
      check0=`echo $std_dev'>'0.5 | bc -l`
      found_first=0
    fi
    if [ $found -eq 1 -a $it -eq $iterations ]; then
      # the last records for IW1, IW2 and IW3 are used to calculate the standard deviation:
      if [ $IW1_average == "0.0" ]; then
        echo "WARNING "$slave": Average of swath IW1 is zero, coregistration might be wrong"
      elif [ $IW2_average == "0.0" ]; then
        echo "WARNING "$slave": Average of swath IW2 is zero, coregistration might be wrong"
      elif [ $IW3_average == "0.0" ]; then
        echo "WARNING "$slave": Average of swath IW3 is zero, coregistration might be wrong"
      fi
      average=`echo "scale=5 ; ($IW1_average + $IW2_average + $IW3_average)/3" | bc -l`
      std_dev=`echo "scale=5 ; sqrt((($IW1_average - $average)^2+($IW2_average - $average)^2+($IW3_average - $average)^2)/3)" | bc -l`
      echo $slave $average $std_dev
      check1=`echo $std_dev'>'0.2 | bc -l`
      check2=`echo ${average#-}'>'0.4 | bc -l`
      if [ $check0 -eq 1 -o $check1 -eq 1 -o $check2 -eq 1 ]; then
        # calculate difference in time to master (used to prioritise jobs later)
        date_diff=`echo $(( ($(date --date=$master_scene +%s) - $(date --date=$slave +%s) )/(60*60*24) ))`
        echo $slave ${date_diff#-} >> $rerun_slave_list
      fi
      break
    fi
  done < <(tail -n +$start_line $slave_check_file)
done < $slave_list

# sort by date difference to master (slaves closer to master first)
sort -g -k 2 $rerun_slave_list > $rerun_slave_date_list
awk '{print $1}' $rerun_slave_date_list > $rerun_slave_list

# set to 1 if badly coregistered scenes shall be rerun
if [ -s $rerun_slave_list -a $rerun -eq 1 ]; then # rerun slaves, start with date closest to master date
  j=0 # initialise job parameter
  depend_job=0 # now dependencies in first iteration
  cp $rerun_slave_list temp_list
  while [ $rerun -eq 1 ]; do
    while read rerun_slave; do
      # get slave position in slaves.list
        slave_pos=`grep -n $rerun_slave $slave_list | cut -f1 -d:`
      # dependency based on position in list!
      if [ $rerun_slave -lt $master_scene ]; then
        coreg_pos=$(($slave_pos+1))
        coreg_slave=`head -n $coreg_pos $slave_list | tail -1`
      elif [ $rerun_slave -gt $master_scene ]; then
        coreg_pos=$(($slave_pos-1))
        coreg_slave=`head -n $coreg_pos $slave_list | tail -1`
      fi
      # check if there is a dependcy on another slave
      if grep -q $coreg_slave temp_list; then
        # temporary list for next iteration
        echo $rerun_slave >> $rerun_slave_temp
      else
        # batch job
        echo $rerun_slave >> $rerun_slave_batch
      fi
    done < temp_list

    # do coregistration
    echo ""
    echo rerunning coregisteration for slaves:
    more $rerun_slave_batch
    echo ""
    co_slc_rerun_batch_dir=$batch_dir/"coreg_slc_rerun_jobs"
    mkdir -p $co_slc_rerun_batch_dir
    cd $co_slc_rerun_batch_dir
    rm -f list # temp file used to collate all PBS job numbers to dependency list
    # job parameters
    script=coregister_S1_slave_SLC.bash
    wt1=`echo $co_slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single slc in minutes
    pbs_job_prefix=co_slc_
    depend_type=afterok
    job_type=1
    script_type=0
    nlines=`cat $rerun_slave_batch | sed '/^\s*$/d' | wc -l`
    # PBS parameters according to slave list
    jobs1=$nlines
    steps1=1
    echo Preparing to run $jobs1 jobs with $steps1 steps processing $((jobs1*steps1)) files
    {
       multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_rerun_batch_dir $script_type jobs1 steps1 j
    } < $rerun_slave_batch
    depend_job=`sed s/.r-man2// $co_slc_rerun_batch_dir/all_co_slc_job_ids`
    j=$(($j+$jobs1)) # add number of previous jobs to index j

    # for next iteration
    if [ -s $rerun_slave_temp ]; then
       cp $rerun_slave_temp temp_list
       # remove original lists since new data is written in the next iteration
       rm $rerun_slave_temp
       rm $rerun_slave_batch
    else
       # stop iteration
       rerun=0
    fi
  done

cd $proj_dir
rm temp_list
fi


# script end
####################

