#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_slc_data: script used to set up pipeline for create slc data         *"
    echo "*                                        	                                *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       13/08/2018, v1.0                            *"
    echo "*             							        *"
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
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $scene

######################################################################
pbs_job_dirs
final_file_loc
echo "This is slc batch dir"
echo $slc_batch_dir

if [ $do_slc == yes ]; then
    cd $slc_batch_dir
    if [ -e all_slc_job_ids ]; then
        echo "SLC data already created."
        echo ""
    else
        echo ""
        echo "Processing full SLCs ..."
        rm -f list # temp file used to collate all PBS job numbers to dependency list

        nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
        echo Need to process $nlines files

        if [ $sensor == PALSAR1 -o $sensor == PALSAR2 ]; then
            sensor=PALSAR
        elif [ $sensor == ERS1 -o $sensor == ERS2 ]; then
            sensor=ERS
        else
            :
        fi

        # PBS parameters
        wt1=`echo $slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single process_slc in minutes
        pbs_job_prefix=slc_
        script="process_"$sensor"_SLC.bash"
        script_type=slc #slc for full SLCs (all sensors), subset for subset Sentinel-1 SLCs
        if [ $do_raw == yes ]; then
            depend_job=`sed s/.r-man2// $extract_raw_batch_dir/all_raw_job_ids`
        else
            depend_job=0  # if no dependency, needs to zero
        fi
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
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_batch_dir $script_type jobs1 steps1 j
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_batch_dir $script_type jobs2 steps2 jobs1
        } < $scene_list

        # Create manual PBS jobs
        cd $slc_manual_dir
        job_type=2 #1 for batch job, 2 for manual job
        depend_job=0
        j=0
        {
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_manual_dir $script_type jobs1 steps1 j
            multi_jobs $pbs_run_loc $pbs_job_prefix $nci_project $slc_mem $slc_ncpus $queue $script $depend_job $depend_type $job_type $slc_manual_dir $script_type jobs2 steps2 jobs1
        } < $scene_list

        # Create preview PDF of SLCs
        cd $slc_batch_dir
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterok
        job_type=1
        echo ""
        echo "Plotting preview of full SLCs ..."
        pbs_job_prefix1=plot_full_slc
        plot_type=full_slc
        script=plot_preview_pdfs.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix1 $nci_project $slc_batch_dir $img_walltime $img_mem $img_ncpus $exp_queue $depend_job $depend_type $job_type $plot_type $script
        }

        # Error collation for full SLC creation
        echo ""
        echo "Preparing error collation for full SLC creation ..."
        depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
        depend_type=afterany
        job_type=1
        pbs_job_prefix2=slc_err
        err_type=3
        script=collate_nci_errors.bash
        {
            single_job $pbs_run_loc $pbs_job_prefix2 $nci_project $slc_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
        }

        # Calculate multi-looking values
        if [ $rlks == "auto" -a $alks == "auto" ]; then
            depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
            depend_type=afterok
            job_type=1 #1 for batch job, 2 for manual job
            pbs_job_prefix3=ml_values
            echo ""
            echo "Calculating multi-looking values ..."
            script_type=-
            script=calc_multi-look_values.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $slc_batch_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
            }

            # Create manual PBS jobs
            cd $slc_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            depend_job=0
            {
                single_job $pbs_run_loc $pbs_job_prefix3 $nci_project $slc_manual_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
            }

            # Error collation for calculating multi-looking values
            cd $slc_batch_dir
            echo ""
            echo "Preparing error collation for calculating multi-looking values ..."
            depend_job=`sed s/.r-man2// $pbs_job_prefix3"_job_id"`
            depend_type=afterany
            job_type=1
            pbs_job_prefix4=ml_values_err
            err_type=4
            script=collate_nci_errors.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix4 $nci_project $slc_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
            }

        elif [[ $rlks =~ ^-?[0-9]+$ ]] && [[ $alks =~ ^-?[0-9]+$ ]]; then
            echo "Multi-looking values already calculated."
        else
            echo "Multi-look values not valid, check and re-process."
        fi

        # Multi-look full SLCs
        cd $ml_batch_dir

        if [ -e all_ml_slc_job_ids ]; then
            echo "SLCs already multi-looked."
            echo ""
        else
            echo ""
            echo "Multi-looking SLCs ..."
            rm -f list # temp file used to collate all PBS job numbers to dependency list

            nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
            echo Need to process $nlines files
            # PBS parameters
            wt1=`echo $ml_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` # walltime for a single slc in minutes
            pbs_job_prefix5=ml_slc_
            script=multi-look_SLCs.bash
            script_type=-
            if [ $rlks == "auto" -a $alks == "auto" ]; then
                depend_job=`sed s/.r-man2// $slc_batch_dir/$pbs_job_prefix3"_job_id"`
                depend_type=afterok
            elif [[ $rlks =~ ^-?[0-9]+$ ]] && [[ $alks =~ ^-?[0-9]+$ ]]; then
                depend_job=`sed s/.r-man2// $slc_batch_dir/"all_"$pbs_job_prefix"job_ids"`
                depend_type=afterok
            else
                :
            fi
            job_type=1 #1 for batch job, 2 for manual job

            # Work out number of jobs to run within maximum number of jobs allowed and create jobs
            if [ $nlines -le $minjobs ]; then
                jobs1=$nlines
                steps1=1
                jobs2=0
                steps2=0
            else
                steps2=$((nlines/minjobs))
                steps1=$((nlines%minjobs))
                jobs1=$steps1
                steps1=$((steps2+1))
                jobs2=$((minjobs-jobs1))
            fi
            echo Preparing to run $jobs1 jobs with $steps1 steps and $jobs2 jobs with $steps2 steps processing $((jobs1*steps1+jobs2*steps2)) files
            j=0
            {
                multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_batch_dir $script_type jobs1 steps1 j
                multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_batch_dir $script_type jobs2 steps2 jobs1
            } < $scene_list

            # Create manual PBS jobs
            cd $ml_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            depend_job=0
            j=0
            {
                multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_manual_dir $script_type jobs1 steps1 j
                multi_jobs $pbs_run_loc $pbs_job_prefix5 $nci_project $ml_mem $ml_ncpus $queue $script $depend_job $depend_type $job_type $ml_manual_dir $script_type jobs2 steps2 jobs1
            } < $scene_list

            # Error collation
            cd $ml_batch_dir
            echo ""
            echo "Preparing error collation for multi-looking SLCs ..."
            depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix5"job_ids"`
            depend_type=afterany
            job_type=1
            pbs_job_prefix6=multi_err
            err_type=5
            script=collate_nci_errors.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix6 $nci_project $ml_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
            }
                # clean up PBS job dir
            cd $ml_batch_dir
            rm -rf list* $pbs_job_prefix5*"job_id"
        fi

        # Calculate intital baselines
        cd $base_batch_dir
        if [ -e init_base_job_id ]; then
            echo "Initial baselines already calculated ."
            echo ""
        else
            depend_job=`sed s/.r-man2// $slc_batch_dir/"all_"$pbs_job_prefix"job_ids"`
            depend_type=afterok
            job_type=1 #1 for batch job, 2 for manual job
            pbs_job_prefix7=init_base
            echo ""
            echo "Calculating initial baselines ..."
            script_type=initial
            script=calc_baselines.py
            {
                single_job $pbs_run_loc $pbs_job_prefix7 $nci_project $base_batch_dir $base_walltime $base_mem $base_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
            }

            # Create manual PBS jobs
            cd $base_manual_dir
            job_type=2 #1 for batch job, 2 for manual job
            depend_job=0
            {
                single_job $pbs_run_loc $pbs_job_prefix7 $nci_project $base_manual_dir $base_walltime $base_mem $base_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
            }

            # Error collation for calculating initial baselines
            cd $base_batch_dir
            echo ""
            echo "Preparing error collation for calculating initial baselines ..."
            depend_job=`sed s/.r-man2// $pbs_job_prefix7"_job_id"`
            depend_type=afterany
            job_type=1
            pbs_job_prefix8=init_base_err
            err_type=6
            script=collate_nci_errors.bash
            {
                single_job $pbs_run_loc $pbs_job_prefix8 $nci_project $base_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
            }
        fi

        # Calculate Sentinel-1 resizing reference scene
        if [ $do_s1_resize == 'yes' ]; then
            if [ $s1_resize_ref == "auto" ]; then # ref scene not calculated
                cd $slc_batch_dir
                depend_job=`sed s/.r-man2// "all_"$pbs_job_prefix"job_ids"`
                depend_type=afterok
                job_type=1 #1 for batch job, 2 for manual job
                pbs_job_prefix4=s1_resize_ref
                echo ""
                echo "Calculating Sentinel-1 resizing reference scene ..."
                script_type=-
                script=calc_resize_S1_ref_scene.bash
                {
                    single_job $pbs_run_loc $pbs_job_prefix4 $nci_project $slc_batch_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
                }

                # Create manual PBS jobs
                cd $slc_manual_dir
                job_type=2 #1 for batch job, 2 for manual job
                depend_job=0
                {
                    single_job $pbs_run_loc $pbs_job_prefix4 $nci_project $slc_manual_dir $calc_walltime $calc_mem $calc_ncpus $exp_queue $depend_job $depend_type $job_type $script_type $script
                }

                # Error collation for calculating Sentinel-1 resizing reference scene
                cd $slc_batch_dir
                echo ""
                echo "Preparing error collation for calculating Sentinel-1 resizing reference scene ..."
                depend_job=`sed s/.r-man2// $pbs_job_prefix4"_job_id"`
                depend_type=afterany
                job_type=1
                pbs_job_prefix5=s1_ref_err
                err_type=7
                script=collate_nci_errors.bash
                {
                    single_job $pbs_run_loc $pbs_job_prefix5 $nci_project $slc_batch_dir $err_walltime $err_mem $err_ncpus $exp_queue $depend_job $depend_type $job_type $err_type $script
                }

            elif [[ $s1_resize_ref =~ ^-?[0-9]+$ ]]; then
                echo ""
                echo "Sentinel-1 resizing reference scene already calculated."
            else
                echo ""
                echo "Sentinel-1 resizing reference scene not valid, check and re-process."
            fi

            # clean up PBS job dir
            cd $slc_batch_dir
            rm -rf list* $pbs_job_prefix*"_job_id"
        else
            :
        fi
    fi
elif [ $do_slc == no ]; then
    echo "Option to create SLC data not selected."
    echo ""
else
    :
fi

