#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* initial_setup: Initial setup scripts used to set up directory and files     *"
    echo "*                 used throughout processing pipeline                         *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             							                                    *"
    echo "*******************************************************************************"
    echo -e "Usage: initial_setup.bash [proc_file]"
    }

if [ $# -lt 1 ]
then
    display_usage
    exit 1
fi 

proc_file=$1

##########################   GENERIC SETUP  ##########################

# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $scene

######################################################################

pbs_job_dirs
final_file_loc
proc_file="$(basename -- $proc_file)"


if [ $coregister == yes ]; then
    slave_file_names

    if [ $sensor == S1 ]; then
	script=coregister_S1_slave_SLC.bash
        # Set up coregistration results file
	echo "SENTINEL-1 SLAVE COREGISTRATION RESULTS" > $slave_check_file
	echo "" >> $slave_check_file
    else
	script=coregister_slave_SLC.bash
        # Set up coregistration results file
	echo "SLAVE COREGISTRATION RESULTS" > $slave_check_file
	echo "" >> $slave_check_file
	echo "final model fit std. dev. (samples)" >> $slave_check_file
	echo "Ref Master" > temp1
	echo "Slave" > temp2
	echo "Range" > temp3
	echo "Azimuth" > temp4
	paste temp1 temp2 temp3 temp4 >> $slave_check_file
	rm -f temp1 temp2 temp3 temp4
    fi

    cd $co_slc_batch_dir
    if [ -e all_co_slc_job_ids ]; then
	    echo "Slave coregistration already completed."
    else
	    rm -f list # temp file used to collate all PBS job numbers to dependency list
        if [ $coreg_dem == yes ]; then
            if [ $master_scene == "auto" ]; then # ref master scene not calculated
                echo "Waiting for 'process_gamma' to restart after calculating DEM reference scene and DEM coregistration before slave coregistration can occur."
                exit
            fi
		else
		    if [ ! -e $slave_list ]; then
		        cd $proj_dir
		        exit
		    fi
		    depend_job=0
		fi
		depend_job=0
	    echo ""
	    echo "Coregistering slave SLCs to master SLC ..."

        # TF create new slave lists containing subsets only for tree-like coregistration to scene close to slave date
        if [ $sensor == S1 ]; then
            # PBS parameters
            wt1=`echo $co_slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single slc in minutes
            pbs_job_prefix=co_slc_
            script_type=-
            depend_type=afterok
            job_type=1 #1 for batch job, 2 for manual job
            j=0
            # split slave_list using a threshold for temporal difference
                #thres_days=93 # three months, S1A/B repeats 84, 90, 96, ... (90 still ok, 96 too long)
                # -> some slaves with zero averages for azimuth offset refinement
                thres_days=63 # three months, S1A/B repeats 54, 60, 66, ... (60 still ok, 66 too long)
                # -> 63 days seems to be a good compromise between runtime and coregistration success
                #thres_days=51 # maximum 7 weeks, S1A/B repeats 42, 48, 54, ... (48 still ok, 54 too long)
                # -> longer runtime compared to 63, similar number of badly coregistered scenes
                # do slaves with time difference less than thres_days
                # rn existing split slave lists
                rm -rf $list_dir/slaves*[0-9].list
                # first slave list
                slave_file=$list_dir/slaves1.list
                # write new slave list
            first_slave=`head $slave_list -n1`
            last_slave=`tail $slave_list -n1`
            # 2-branch tree: scenes before master: lower tree , scenes after master: upper tree
            if [ $first_slave -lt $master_scene ] && [ $last_slave -gt $master_scene ]; then
                lower=0
                date_diff_min=9999
                while read slave; do
                    # calculate datediff between master and slave: lower tree
                    date_diff=`echo $(( ($(date --date=$master_scene +%s) - $(date --date=$slave +%s) )/(60*60*24) ))`
                    if [ $date_diff -gt 0 ]; then
                        if [ $date_diff -lt $thres_days ]; then
                            lower=$(($lower+1))
                            echo $slave >> $slave_file
                        fi
                        if [ $date_diff -lt $date_diff_min ]; then
                            # find closest slave
                            date_diff_min=$date_diff
                            closest_slave=$slave # save in case no slave is written to file
                        fi
                    fi
                done < $slave_list
                if [ $lower -eq 0 ]; then # no scene written to lower tree
                    echo "Date difference to closest slave greater than" $date_thres "days, using closest slave only:" $closest_slave
                    echo $closest_slave >> $slave_file
                fi
                upper=0
                date_diff_max=-9999
                while read slave; do
                        # calculate datediff between master and slave: upper tree
                    date_diff=`echo $(( ($(date --date=$master_scene +%s) - $(date --date=$slave +%s) )/(60*60*24) ))`
                    if [ $date_diff -lt 0 ]; then
                        if [ $date_diff -gt -$thres_days ]; then
                            upper=$(($upper+1))
                            echo $slave >> $slave_file
                        fi
                        if [ $date_diff -gt $date_diff_max ]; then # find closest slave
                            date_diff_max=$date_diff
                            closest_slave=$slave # save in case no slave is written to file
                        fi
                    fi
                done < $slave_list
                if [ $upper -eq 0 ]; then # no scene written to upper tree
                    echo "Date difference to closest slave greater than" $date_thres "days, using closest slave only:" $closest_slave
                    echo $closest_slave >> $slave_file
                fi
                # if master_scene is the first date in the stack, only do upper tree
            elif [ $first_slave -gt $master_scene ] && [ $last_slave -gt $master_scene ]; then
                upper=0
                date_diff_max=-9999
                while read slave; do
                     # calculate datediff between master and slave: upper tree
                    date_diff=`echo $(( ($(date --date=$master_scene +%s) - $(date --date=$slave +%s) )/(60*60*24) ))`
                    if [ $date_diff -lt 0 ]; then
                        if [ $date_diff -gt -$thres_days ]; then
                            upper=$(($upper+1))
                            echo $slave >> $slave_file
                        fi
                        if [ $date_diff -gt $date_diff_max ]; then # find closest slave
                            date_diff_max=$date_diff
                            closest_slave=$slave # save in case no slave is written to file
                        fi
                    fi
                done < $slave_list
                if [ $upper -eq 0 ]; then # no scene written to upper tree
                    echo "Date difference to closest slave greater than" $date_thres "days, using closest slave only:" $closest_slave
                    echo $closest_slave >> $slave_file
                fi
            fi

            # prepare the batch jobs
            nlines=`cat $slave_file | sed '/^\s*$/d' | wc -l`
            # PBS parameters according to slave list
            jobs1=$nlines
            steps1=1
            echo Preparing to run $jobs1 jobs with $steps1 steps processing $((jobs1*steps1)) files
            {
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_batch_dir $script_type jobs1 steps1 j
            } < $slave_file

            # Create manual PBS jobs
            cd $co_slc_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            depend_job=0
            {
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_manual_dir $script_type jobs1 steps1 j
            } < $slave_list


            # continue to write slave lists until the slavesXY.list file is empty
            list_idx=1; # idx of slave lists
            while [ -s $list_dir/slaves$list_idx.list ]; do # check if previous list file contains values
                sed -i '/^$/d' $list_dir/slaves$list_idx.list # remove any blank lines in file for head & tail to work properly
                # first and last scenes in actual slave list are used to coregister adjacent scenes to
                coreg_slave1=`head $list_dir/slaves$list_idx.list -n1` # coregistration slave of lower tree
                coreg_slave2=`tail $list_dir/slaves$list_idx.list -n1` # coregistration slave of upper tree
                # new index and corresponding slave list file
                list_idx=$((list_idx+1))
                slave_file=$list_dir/slaves$list_idx.list
                if [ -f $slave_file ]; then
                    rm $slave_file
                fi
                # 2-branch tree: scenes before coregistration slave: lower tree, scenes after coregistration slave: upper tree
                if [ $coreg_slave1 -lt $master_scene ]; then # lower tree
                    lower=0
                    date_diff_min=9999
                    while read slave; do
                        # calculate datediff between master and slave: lower tree
                        date_diff=`echo $(( ($(date --date=$coreg_slave1 +%s) - $(date --date=$slave +%s) )/(60*60*24) ))`
                        if [ $date_diff -gt 0 ]; then
                            if [ $date_diff -lt $thres_days ]; then
                                lower=$(($lower+1))
                                echo $slave >> $slave_file
                            fi
                            if [ $date_diff -lt $date_diff_min ]; then # find closest slave
                                date_diff_min=$date_diff
                                closest_slave=$slave # save in case no slave is written to file
                            fi
                        fi
                    done < $slave_list
                    if [ $lower -eq 0 ]; then # no scene written to lower tree
                        if [ $date_diff_min -eq 9999 ]; then
                            echo "Lower tree: all slaves written to subfiles" # no more scenes in lower tree
                        else
                            echo "Date difference to closest slave greater than" $thres_days "days, using closest slave only:" $closest_slave
                            echo $closest_slave >> $slave_file
                        fi
                    fi
                fi # end lower tree

                if [ $coreg_slave2 -gt $master_scene ]; then # upper tree
                    upper=0
                    date_diff_max=-9999
                    while read slave; do
                        # calculate datediff between master and slave: upper tree
                        date_diff=`echo $(( ($(date --date=$coreg_slave2 +%s) - $(date --date=$slave +%s) )/(60*60*24) ))`
                        if [ $date_diff -lt 0 ]; then
                            if [ $date_diff -gt -$thres_days ]; then
                                upper=$(($upper+1))
                                echo $slave >> $slave_file
                            fi
                            if [ $date_diff -gt $date_diff_max ]; then # find closest slave
                                date_diff_max=$date_diff
                                closest_slave=$slave # save in case no slave is written to file
                            fi
                        fi
                    done < $slave_list

                    if [ $upper -eq 0 ]; then # no scene written to upper tree
                        if [ $date_diff_max -eq -9999 ]; then
                            echo "Upper tree: all slaves written to subfiles" # no more scenes in the upper tree
                        else
                            echo "Date difference to closest slave greater than" $thres_days "days, using closest slave only:" $closest_slave
                            echo $closest_slave >> $slave_file
                        fi
                    fi
                fi # end upper tree

                # start multi_jobs giving the list_idx as a parameter
                if [ -s $slave_file ]; then
                    echo ""
                    echo coregistering slaves in slave list $list_idx
                    echo ""
                    script_type=$list_idx
                    nlines=`cat $slave_file | sed '/^\s*$/d' | wc -l`
                    # PBS parameters according to slave list
                    j=$(($j+$jobs1)) # add number of previous jobs to index j
                    jobs1=$nlines
                    steps1=1
                    cd $co_slc_batch_dir
                    depend_job=`sed s/.r-man2// $co_slc_batch_dir/all_co_slc_job_ids`
                    job_type=1 #1 for batch job, 2 for manual job
                    echo Preparing to run $jobs1 jobs with $steps1 steps processing $((jobs1*steps1)) files
                    {
                        multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_batch_dir $script_type jobs1 steps1 j
                    } < $slave_file

                    # Create manual PBS jobs
                    cd $co_slc_manual_dir
                    job_type=2 #1 for batch job, 2 for manual job
                    depend_job=0
                    {
                        multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_manual_dir $script_type jobs1 steps1 j
                    } < $slave_list

                fi
            done

        else # not S1

            nlines=`cat $slave_list | sed '/^\s*$/d' | wc -l`
            echo Need to process $nlines files

            # PBS parameters
            wt1=`echo $co_slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single slc in minutes
            pbs_job_prefix=co_slc_
            script_type=-
            depend_type=afterok
            job_type=1 #1 for batch job, 2 for manual job

            # Work out number of jobs to run within maximum number of jobs allowed and create jobs
            if [ $nlines -le $maxjobs ]; then
                jobs1=$nlines
                steps1=1
                jobs2=0
                steps2=0
            else
                steps2=$((nlines/maxjobs))
                steps1=$((nlines%maxjobs))
                jobs1=$steps1
                steps1=$((steps2+1))
                jobs2=$((maxjobs-jobs1))
            fi
            echo Preparing to run $jobs1 jobs with $steps1 steps and $jobs2 jobs with $steps2 steps processing $((jobs1*steps1+jobs2*steps2)) files
            j=0
            {
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_batch_dir $script_type jobs1 steps1 j
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_batch_dir $script_type jobs2 steps2 jobs1
            } < $slave_list

               # Create manual PBS jobs
            cd $co_slc_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            depend_job=0
            j=0
            {
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_manual_dir $script_type jobs1 steps1 j
                multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $co_slc_mem $co_slc_ncpus $queue $script $depend_job $depend_type $job_type $co_slc_manual_dir $script_type jobs2 steps2 jobs1
            } < $slave_list

            fi # S1/other sensors

            # Error collation for slave SLC coregistration
        cd $co_slc_batch_dir
        echo ""
        echo "Preparing error collation for coregistering slave SLCs to master SLC ..."
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix1=co_slc_err
        err_type=10
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix1 $nci_project $co_slc_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }

            # clean up PBS job dir
        cd $co_slc_batch_dir
        rm -rf list* $pbs_job_prefix*"_job_id"
    fi
elif [ $coregister == no ]; then
    echo "Option to coregister slave SLCs to master SLC not selected."
    echo ""
else
    :
fi


