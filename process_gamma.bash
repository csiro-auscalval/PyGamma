#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* process_gamma:  Script uses options in a parameter file to run the GAMMA    *"
    echo "*                 interferogram processing chain (ie. make SLCs, coregister   *"
    echo "*                 DEM, coregister slaves, make interferograms).               *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       29/05/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       11/06/2015, v1.1                            *"
    echo  "*            - add auto splitting of jobs to enable >200 job submission      *"
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.2                            *"
    echo  "*            - add auto calculation of subset values if subsetting scene     *"
    echo "*******************************************************************************"
    echo -e "Usage: process_gamma.bash [proc_file]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi


proc_file=$1

## Variables from parameter file (*.proc)
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
do_setup=`grep Setup= $proc_file | cut -d "=" -f 2`
do_raw=`grep Do_raw_data= $proc_file | cut -d "=" -f 2` 
do_slc=`grep Do_SLC= $proc_file | cut -d "=" -f 2`
coregister_dem=`grep Coregister_DEM= $proc_file | cut -d "=" -f 2`
coregister=`grep Coregister_slaves= $proc_file | cut -d "=" -f 2`
do_ifms=`grep Process_ifms= $proc_file | cut -d "=" -f 2`
add_slc=`grep Add_new_SLC= $proc_file | cut -d "=" -f 2`
recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`
coregister_add=`grep Coregister_add_slaves= $proc_file | cut -d "=" -f 2`
do_add_ifms=`grep Process_add_ifms= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
frame_list=`grep List_of_frames= $proc_file | cut -d "=" -f 2`
mas=`grep Master_scene= $proc_file | cut -d "=" -f 2`
slc_looks=`grep SLC_multi_look= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
palsar1_data=`grep PALSAR1_data= $proc_file | cut -d "=" -f 2`
subset=`grep Subsetting= $proc_file | cut -d "=" -f 2`
roff=`grep range_offset= $proc_file | cut -d "=" -f 2`
rlines=`grep range_lines= $proc_file | cut -d "=" -f 2`
azoff=`grep azimuth_offset= $proc_file | cut -d "=" -f 2`
azlines=`grep azimuth_lines= $proc_file | cut -d "=" -f 2`
raw_dir_ga=`grep Raw_data_GA= $proc_file | cut -d "=" -f 2`
raw_dir_mdss=`grep Raw_data_MDSS= $proc_file | cut -d "=" -f 2`
list_walltime=`grep list_walltime= $proc_file | cut -d "=" -f 2`
list_mem=`grep list_mem= $proc_file | cut -d "=" -f 2`
list_ncpus=`grep list_ncpus= $proc_file | cut -d "=" -f 2`
raw_walltime=`grep raw_walltime= $proc_file | cut -d "=" -f 2`
raw_mem=`grep raw_mem= $proc_file | cut -d "=" -f 2`
raw_ncpus=`grep raw_ncpus= $proc_file | cut -d "=" -f 2`
slc_walltime=`grep SLC_walltime= $proc_file | cut -d "=" -f 2`
slc_mem=`grep SLC_mem= $proc_file | cut -d "=" -f 2`
slc_ncpus=`grep SLC_ncpus= $proc_file | cut -d "=" -f 2`
dem_walltime=`grep DEM_walltime= $proc_file | cut -d "=" -f 2`
dem_mem=`grep DEM_mem= $proc_file | cut -d "=" -f 2`
dem_ncpus=`grep DEM_ncpus= $proc_file | cut -d "=" -f 2`
co_slc_walltime=`grep coreg_walltime= $proc_file | cut -d "=" -f 2`
co_slc_mem=`grep coreg_mem= $proc_file | cut -d "=" -f 2`
co_slc_ncpus=`grep coreg_ncpus= $proc_file | cut -d "=" -f 2`
ifm_walltime=`grep ifm_walltime= $proc_file | cut -d "=" -f 2`
ifm_mem=`grep ifm_mem= $proc_file | cut -d "=" -f 2`
ifm_ncpus=`grep ifm_ncpus= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
fi

cd $proj_dir

## Add carriage return to last line of frame.list file if it exists (required for loops to work)
if [ -f $frame_list ]; then
    echo >> $frame_list
else
    :
fi

## Insert scene details top of NCI .e file
echo "" 1>&2 # adds spaces at top so scene details are clear
echo "" 1>&2
echo "PROCESSING_PROJECT: "$project $track_dir 1>&2


## Load GAMMA based on platform
if [ $platform == NCI ]; then
    GAMMA=`grep GAMMA_NCI= $proc_file | cut -d "=" -f 2`
    source $GAMMA
else
    GAMMA=`grep GAMMA_GA= $proc_file | cut -d "=" -f 2`
    source $GAMMA
fi

slc_dir=$proj_dir/$track_dir/`grep SLC_dir= $proc_file | cut -d "=" -f 2`
dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
ifm_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`
frame_list=$proj_dir/$track_dir/`grep List_of_frames= $proc_file | cut -d "=" -f 2`
beam_list=$proj_dir/$track_dir/`grep List_of_beams= $proc_file | cut -d "=" -f 2`
scene_list=$proj_dir/$track_dir/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
slave_list=$proj_dir/$track_dir/`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
ifm_list=$proj_dir/$track_dir/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`
subset_file=$proj_dir/$track_dir/`grep Subset_file= $proc_file | cut -d "=" -f 2`
add_scene_list=$proj_dir/$track_dir/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
add_slave_list=$proj_dir/$track_dir/`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`
add_ifm_list=$proj_dir/$track_dir/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`

## Determine range and azimuth looks for 'square' pixels
if [ $sensor == ASAR -o $sensor = ERS ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*5}'` 
    ifm_rlks=$ifm_looks 
    ifm_alks=`echo $ifm_looks | awk '{print $1*5}'` 
elif [ $sensor == JERS1 ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*3}'` 
    ifm_rlks=$ifm_looks 
    ifm_alks=`echo $ifm_looks | awk '{print $1*3}'`
elif [ $sensor == RSAT1 ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*4}'` 
    ifm_rlks=$ifm_looks 
    ifm_alks=`echo $ifm_looks | awk '{print $1*4}'` 
elif [ $sensor == S1 ]; then
    slc_alks=$slc_looks 
    slc_rlks=`echo $slc_looks | awk '{print $1*5}'` 
    ifm_alks=$ifm_looks 
    ifm_rlks=`echo $ifm_looks | awk '{print $1*5}'` 
elif [ $sensor == PALSAR1 -o $sensor == PALSAR2 ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*2}'` 
    ifm_rlks=$ifm_looks 
    ifm_alks=`echo $ifm_looks | awk '{print $1*2}'`
else
    # CSK, RSAT2, TSX
    slc_rlks=$slc_looks
    slc_alks=$slc_looks
    ifm_rlks=$ifm_looks
    ifm_alks=$ifm_looks
fi

err_dir=$proj_dir/$track_dir/Error_Files
cd $proj_dir




##########################   SETUP PROJECT DIRECTORY STRUCTURE AND LISTS FOR PROCESSING   ##########################


#### GA ####

if [ $do_setup == yes -a $platform == GA ]; then
# create track dir
    echo " "
    echo "Creating project directory structure..."
    mkdir -p $track_dir
    mkdir -p $err_dir
    if [ -f frame.list ]; then # if multiple frames exist
	mv frame.list $track_dir
    fi
    if [ -f beam.list ]; then # if beams exist
	mv beam.list $track_dir
    fi

# create scenes.list file
    cd $raw_dir_ga
    echo "Creating scenes list file..."
    create_scenes_list.bash $proj_dir/$proc_file

# create slaves.list file
    cd $proj_dir/$track_dir
    echo "Creating slaves list file..."
    create_slaves_list.bash $proj_dir/$proc_file

# create ifms.list file
    echo "Creating interferogram list file..."
    create_ifms_list.bash $proj_dir/$proc_file
    echo "Setup complete for "$project $sensor $track_dir"."
    echo " "
elif [ $do_setup == no -a $platform == GA ]; then
    echo " "
    echo "Option to setup project directories and lists not selected."
    echo " "


#### NCI #####

elif [ $do_setup == yes -a $platform == NCI ]; then
    mkdir -p $track_dir
    mkdir -p $track_dir/batch_scripts
    batch_dir=$proj_dir/$track_dir/batch_scripts
    cd $batch_dir

# setup directory structure
    echo "Creating project directory structure..." 1>&2
    job=setup_dirs
    echo \#\!/bin/bash > $job
    echo \#\PBS -lother=gdata1 >> $job
    echo \#\PBS -l walltime=$list_walltime >> $job
    echo \#\PBS -l mem=$list_mem >> $job
    echo \#\PBS -l ncpus=$list_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q normal >> $job
    echo ~/repo/gamma_bash/setup_nci_structure.bash $proj_dir/$proc_file >> $job
    chmod +x $job
    qsub $job | tee setup_job_id

# create scenes.list file
    echo "Creating scenes list file..." 1>&2
    setup_jobid=`sed s/.r-man2// setup_job_id`
    job1=scene_list_gen
    echo \#\!/bin/bash > $job1
    echo \#\PBS -lother=gdata1 >> $job1
    echo \#\PBS -l walltime=$list_walltime >> $job1
    echo \#\PBS -l mem=$list_mem >> $job1
    echo \#\PBS -l ncpus=$list_ncpus >> $job1
    echo \#\PBS -l wd >> $job1
    echo \#\PBS -q copyq >> $job1
    echo \#\PBS -W depend=afterok:$setup_jobid >> $job1
    echo ~/repo/gamma_bash/create_scenes_list.bash $proj_dir/$proc_file >> $job1
    chmod +x $job1
    qsub $job1 | tee scene_list_job_id

# create slaves.list file
    echo "Creating slaves list file..." 1>&2
    scene_list_jobid=`sed s/.r-man2// scene_list_job_id`
    job2=slave_list_gen
    echo \#\!/bin/bash > $job2
    echo \#\PBS -lother=gdata1 >> $job2
    echo \#\PBS -l walltime=$list_walltime >> $job2
    echo \#\PBS -l mem=$list_mem >> $job2
    echo \#\PBS -l ncpus=$list_ncpus >> $job2
    echo \#\PBS -l wd >> $job2
    echo \#\PBS -q normal >> $job2
    echo \#\PBS -W depend=afterok:$scene_list_jobid >> $job2
    echo ~/repo/gamma_bash/create_slaves_list.bash $proj_dir/$proc_file 1 >> $job2
    chmod +x $job2
    qsub $job2 | tee slave_list_job_id

# create ifms.list file
    echo "Creating interferogram list file..." 1>&2
    job3=ifm_list_gen
    echo \#\!/bin/bash > $job3
    echo \#\PBS -lother=gdata1 >> $job3
    echo \#\PBS -l walltime=$list_walltime >> $job3
    echo \#\PBS -l mem=$list_mem >> $job3
    echo \#\PBS -l ncpus=$list_ncpus >> $job3
    echo \#\PBS -l wd >> $job3
    echo \#\PBS -q normal >> $job3
    echo \#\PBS -W depend=afterok:$scene_list_jobid >> $job3
    echo ~/repo/gamma_bash/create_ifms_list.bash $proj_dir/$proc_file 1 >> $job3
    chmod +x $job3
    qsub $job3 | tee ifm_list_job_id
elif [ $do_setup == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to setup project directories and lists not selected." 1>&2
    echo "" 1>&2
else
    :
fi




##########################   EXTRACT RAW AND DEM DATA   ####################################


#### GA ####

if [ $do_raw == yes -a $platform == GA ]; then
    cd $proj_dir/$track_dir
    echo "Extracting raw data..."
    echo " "
    extract_raw_data.bash $proj_dir/$proc_file 0
    echo "Raw data extracted for" $project $sensor $track_dir"."
elif [ $do_raw == no -a $platform == GA ]; then
    echo " "
    echo "Option to extract raw data not selected."
    echo " "
else
    :
fi


#### NCI ####

if [ $do_raw == yes -a $platform == NCI ]; then
    echo "Extracting raw data..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    cd $batch_dir
    job=extract_raw_data 
    echo \#\!/bin/bash > $job
    echo \#\PBS -lother=gdata1 >> $job
    echo \#\PBS -l walltime=$raw_walltime >> $job
    echo \#\PBS -l mem=$raw_mem >> $job
    echo \#\PBS -l ncpus=$raw_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q copyq >> $job
    if [ $do_setup == yes -a $platform == NCI ]; then 
	setup_jobid=`sed s/.r-man2// $batch_dir/ifm_list_job_id`
	echo \#\PBS -W depend=afterok:$setup_jobid >> $job
    else
	:
    fi
    echo ~/repo/gamma_bash/extract_raw_data.bash $proj_dir/$proc_file 0 >> $job
    chmod +x $job
    qsub $job | tee raw_job_id
elif [ $do_raw == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to extract raw data not selected." 1>&2
    echo "" 1>&2

else
    :
fi




##########################   CREATE SLC DATA   ##########################


if [ $do_slc == yes -a $sensor == PALSAR1 ]; then
    if [ $palsar1_data == raw ]; then
	sensor=PALSAR_L0 # PALSAR L1.0 script can process PALSAR1 raw data
    elif [ $palsar1_data == slc ]; then
	sensor=PALSAR_L1 # PALSAR L1.1 script can process both PALSAR1 and PALSAR2 slc level data
    else
	:
    fi
elif [ $do_slc == yes -a $sensor == PALSAR2 ]; then
    sensor=PALSAR_L1
else
    :
fi


#### GA ####

if [ $do_slc == yes -a $platform == GA ]; then
    cd $proj_dir
# consolidate error logs into one file
    err_log=$err_dir/SLC_error.log
    echo "PROJECT: "$project"_"$sensor"_"$track_dir"_SLC_Creation_Error_Log" > $err_log
    echo " " >> $err_log
    echo "Creating SLC data..."
# SLC and ifm multi-look value (same value)
    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
	while read scene; do
	    if [ ! -z $scene ]; then
		echo " "
		echo "Creating SLC for "$scene" with "$slc_rlks" range and "$slc_alks" azimuth looks..."
		process_$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks
		cd $slc_dir/$scene
		echo " " >> $err_log
		echo "Creating SLC for "$scene" with "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
	    fi
	done < $scene_list
    else
	while read scene; do
	    if [ ! -z $scene ]; then
 # SLC multi-look value
		echo " "
		echo "Creating SLC for "$scene" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks..."
		process_$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks
		cd $slc_dir/$scene
		echo " " >> $err_log
		echo "Creating SLC for "$scene" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
# ifm multi-look value
		echo " "
		echo "Creating SLC for "$scene" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
		process_$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks
		cd $slc_dir/$scene
		echo " " >> $err_log
		echo "Creating SLC for "$scene" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
	    fi
	done < $scene_list
    fi
    echo " "
    echo "SLC processing completed."
    echo " "
elif [ $do_slc == no -a $platform == GA ]; then
    echo " "
    echo "Option to create SLC data not selected."
    echo " "


#### NCI ####

elif [ $do_slc == yes -a $platform == NCI ]; then
    echo "Creating SLC data..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    slc_batch_dir=$batch_dir/slc_jobs

    # Maximum number of jobs to be run (no more than 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a single process_slc in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_script_prefix=slc_

    if [ -f $beam_list ]; then # if beam list exists
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $slc_batch_dir/$beam_num

		function create_jobs {
		    local njobs=$1
		    local nsteps=$2
		    local i=$3
		    local wt=$(( wt1*nsteps ))
		    local hh=$(( wt/60 ))
		    local mm=$(( wt%60 ))
		    local m=0
		    local n=0

		    for(( m=0; m<njobs; m++ )); do
			i=$(( i+=1 ))
			jobdir=$job_dir_prefix$i
			mkdir -p $jobdir
			cd $jobdir
			script=$pbs_script_prefix$i

			echo Doing job $i in $jobdir with $script

			echo \#\!/bin/bash > $script 
			echo \#\PBS -l other=gdata1 >> $script
			echo \#\PBS -l walltime=$hh":"$mm":00" >> $script
			echo \#\PBS -l mem=$slc_mem >> $script
			echo \#\PBS -l ncpus=$slc_ncpus >> $script
			echo \#\PBS -l wd >> $script
			echo \#\PBS -q normal >> $script
			echo -e "\n" >> $script
			if [ $do_raw == yes -a $platform == NCI ]; then
			    raw_jobid=`sed s/.r-man2// $batch_dir/raw_job_id`
			    echo \#\PBS -W depend=afterok:$raw_jobid >> $script
			else
			    :
			fi

			for(( n=0; n<nsteps; n++ )); do
			    read scene
			    echo $scene
			    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
			    else
				echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
				echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $script
			    fi
        		done
			chmod +x $script
			qsub $script | tee $slc_batch_dir/$beam_num/"slc_"$beam_num"_"$i"_job_id"
			cd ..
		    done
		}

                # Work starts here
		cd $slc_batch_dir/$beam_num
		nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
		echo Need to process $nlines files

                # Need to run kjobs with k steps and ljobs with l steps. 
		if [ $nlines -le $maxjobs ]; then
		    kjobs=$nlines
		    k=1
		    ljobs=0
		    l=0
		else
		    l=$((nlines/maxjobs))
		    k=$((nlines%maxjobs))
		    kjobs=$k
		    k=$((l+1))
		    ljobs=$((maxjobs-kjobs))
		fi
		echo Preparing to run $kjobs jobs with $k steps and $ljobs jobs with $l steps processing $((kjobs*k+ljobs*l)) files
		j=0
		{
		    create_jobs kjobs k j 
		    create_jobs ljobs l kjobs 
		} < $scene_list

	        # create dependency list (make sure all slcs are finished before error consolidation)
		cd $slc_batch_dir/$beam_num
		ls "slc_"$beam_num"_"*"_job_id" > list1
		if [ -f list2 ]; then
		    rm -rf list2
		else
		    :
		fi
		while read id; do
		    less $id >> list2 
		done < list1
		sed s/.r-man2// list2 > list3 # leave just job numbers
		sort -n list3 > list4 # sort numbers
		tr '\n' ':' < list4 > list5 # move column to single row with numbers separated by :
		sed s'/.$//' list5 > "all_slc_"$beam_num"_job_id" # remove last :
		dep=`awk '{print $1}' "all_slc_"$beam_num"_job_id"`
		rm -rf list* "slc_"$beam_num"_"*"_job_id"
		
                # in case future manual processing is required, create manual PBS jobs for each scene
		cd $slc_batch_dir/$beam_num/manual_jobs
		while read list; do
		    scene=`echo $list | awk '{print $1}'`
		    script="slc_"$beam_num"_"$scene
		    echo \#\!/bin/bash > $script
		    echo \#\PBS -lother=gdata1 >> $script
		    echo \#\PBS -l walltime=$slc_walltime >> $script
		    echo \#\PBS -l mem=$slc_mem >> $script
		    echo \#\PBS -l ncpus=$slc_ncpus >> $script
		    echo \#\PBS -l wd >> $script
		    echo \#\PBS -q normal >> $script
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
		    else
			echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
			echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $script
		    fi
		    chmod +x $script
		done < $scene_list		

                # run slc error check
		cd $slc_batch_dir/$beam_num
		job="slc_err_"$beam_num"_check"
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=00:10:00 >> $job
		echo \#\PBS -l mem=50MB >> $job
		echo \#\PBS -l ncpus=1 >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterany:$dep >> $job
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 1 >> $job
		chmod +x $job
		qsub $job | tee slc_err_job_id
	    fi
	done < $beam_list
    else # no beams
	cd $slc_batch_dir

	function create_jobs {
	    local njobs=$1
	    local nsteps=$2
	    local i=$3
	    local wt=$(( wt1*nsteps ))
	    local hh=$(( wt/60 ))
	    local mm=$(( wt%60 ))
	    local m=0
	    local n=0

	    for(( m=0; m<njobs; m++ )); do
        	i=$(( i+=1 ))
        	jobdir=$job_dir_prefix$i
        	mkdir -p $jobdir
        	cd $jobdir
        	script=$pbs_script_prefix$i
		echo Doing job $i in $jobdir with $script
		echo \#\!/bin/bash > $script 
		echo \#\PBS -l other=gdata1 >> $script
		echo \#\PBS -l walltime=$hh":"$mm":00" >> $script
		echo \#\PBS -l mem=$slc_mem >> $script
		echo \#\PBS -l ncpus=$slc_ncpus >> $script
		echo \#\PBS -l wd >> $script
		echo \#\PBS -q normal >> $script
		echo -e "\n" >> $script
		if [ $do_raw == yes -a $platform == NCI ]; then
		    raw_jobid=`sed s/.r-man2// $batch_dir/raw_job_id`
		    echo \#\PBS -W depend=afterok:$raw_jobid >> $script
		else
		    :
		fi

		for(( n=0; n<nsteps; n++ )); do
                    read scene
                    echo $scene
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
		    else
			echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
			echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $script
		    fi
        	done
		chmod +x $script
		qsub $script | tee $slc_batch_dir/"slc_"$i"_job_id"		
		cd ..
	    done
	}
        # Work starts here
	cd $slc_batch_dir
	nlines=`cat $scene_list | sed '/^\s*$/d' | wc -l`
	echo Need to process $nlines files
	
        # Need to run kjobs with k steps and ljobs with l steps. 
	if [ $nlines -le $maxjobs ]; then
	    kjobs=$nlines
	    k=1
	    ljobs=0
	    l=0
	else
	    l=$((nlines/maxjobs))
	    k=$((nlines%maxjobs))
	    kjobs=$k
	    k=$((l+1))
	    ljobs=$((maxjobs-kjobs))
	fi
	echo Preparing to run $kjobs jobs with $k steps and $ljobs jobs with $l steps processing $((kjobs*k+ljobs*l)) files
	j=0
	{
	    create_jobs kjobs k j 
	    create_jobs ljobs l kjobs 
	} < $scene_list
	
	# create dependency list (make sure all slcs are finished before error consolidation)
	cd $slc_batch_dir
	ls "slc_"*"_job_id" > list1
	if [ -f list2 ]; then
	    rm -rf list2
	else
	    :
	fi
	while read id; do
	    less $id >> list2 
	done < list1
	sed s/.r-man2// list2 > list3 # leave just job numbers
	sort -n list3 > list4 # sort numbers
	tr '\n' ':' < list4 > list5 # move column to single row with numbers separated by :
	sed s'/.$//' list5 > all_slc_job_id # remove last :
	dep=`awk '{print $1}' all_slc_job_id`
	rm -rf list* "slc_"*"_job_id"

        # in case future manual processing is required, create manual PBS jobs for each scene
	cd $slc_batch_dir/manual_jobs
	while read list; do
	    scene=`echo $list | awk '{print $1}'`
	    script="slc_"$scene
	    echo \#\!/bin/bash > $script
	    echo \#\PBS -lother=gdata1 >> $script
	    echo \#\PBS -l walltime=$slc_walltime >> $script
	    echo \#\PBS -l mem=$slc_mem >> $script
	    echo \#\PBS -l ncpus=$slc_ncpus >> $script
	    echo \#\PBS -l wd >> $script
	    echo \#\PBS -q normal >> $script
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
	    else
		echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
		echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $script
	    fi
	    chmod +x $script
	done < $scene_list
	
        # run slc error check
	cd $slc_batch_dir
	job=slc_err_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=00:10:00 >> $job
	echo \#\PBS -l mem=50MB >> $job
	echo \#\PBS -l ncpus=1 >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterany:$dep >> $job
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 1 >> $job
	chmod +x $job
	qsub $job | tee slc_err_job_id
    fi
elif [ $do_slc == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create SLC data not selected." 1>&2
    echo "" 1>&2
else
    :
fi




##########################   COREGISTER DEM TO MASTER SCENE   ##########################


#### GA ####

if [ $coregister_dem == yes -a $platform == GA ]; then
    cd $proj_dir
# consolidate error log into one file
    err_log=$err_dir/DEM_coreg_error.log
    echo "PROJECT: "$project"_"$sensor"_"$track_dir"_Coregister_DEM_Error_Log" > $err_log
    echo " " >> $err_log
    echo " " >> $err_log
    echo "Coregistering DEM to master scene..."
    if [ $subset == yes -a $subset_done == notyet ]; then 
       # no multi-look value - for geocoding full SLC and determining pixels for subsetting master scene
       echo "Coregistering DEM to master scene with 1 range and 1 azimuth looks..."
       make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 - - - -
       cd $dem_dir
       echo "Coregistering DEM to master scene with 1 range and 1 azimuth looks" >> $err_log
       less error.log > temp
       # remove unecessary lines from error log
       sed '/^scene/ d' temp > temp2 
       sed '/^USAGE/ d' temp2 >> $err_log
       grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
       echo " " >> $err_log
       echo " " >> $err_log
       rm -f temp temp2
       echo " "
       echo "Subsetting of master scene required, run xxx.bash to determine pixel coordinates before continuing."
       echo " "
       exit 0 # allow for subsettting calculations
   elif [ $subset == yes -a $subset_done == process ]; then 
	echo " "
	echo "Subsetting master scene..."
	echo " "
        # no multi-look value - for geocoding full SLC data
	echo "Coregistering DEM to master scene with 1 range and 1 azimuth looks..."
	make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 $roff $rlines $azoff $azlines
	cd $dem_dir
	echo "Coregistering DEM to master scene with 1 range and 1 azimuth looks" >> $err_log
	less error.log > temp
        # remove unecessary lines from error log
	sed '/^scene/ d' temp > temp2 
	sed '/^USAGE/ d' temp2 >> $err_log
	grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	echo " " >> $err_log
	echo " " >> $err_log
	rm -f temp temp2
        # SLC and ifm multi-look value (same value)
	if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
	    echo "Coregistering DEM to master scene with "$slc_rlks" range and "$slc_alks" azimuth looks..."
	    cd $proj_dir
	    make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines
	    cd $dem_dir
	    echo " " >> $err_log
	    echo "Coregistering DEM to master scene with "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
	    less error.log > temp
            # remove unecessary lines from error log
	    sed '/^scene/ d' temp > temp2 
	    sed '/^USAGE/ d' temp2 >> $err_log
	    grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	    echo " " >> $err_log
	    echo " " >> $err_log
	    rm -f temp temp2
	else
            # SLC multi-look value
	    echo "Coregistering DEM to master scene with SLC "$slc_rlks" range and "$slc_alks" azimuth looks..."
	    cd $proj_dir
	    make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines
	    cd $dem_dir
	    echo " " >> $err_log
	    echo " " >> $err_log
	    echo "Coregistering DEM to master scene with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
	    less error.log > temp
            # remove unecessary lines from error log
	    sed '/^scene/ d' temp > temp2 
	    sed '/^USAGE/ d' temp2 >> $err_log
	    grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	    echo " " >> $err_log
	    echo " " >> $err_log
	    rm -f temp temp2
            # ifm multi-look value
	    echo "Coregistering DEM to master scene with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
	    cd $proj_dir
	    make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 1 $roff $rlines $azoff $azlines
	    cd $dem_dir
	    echo " " >> $err_log
	    echo " " >> $err_log
	    echo "Coregistering DEM to master scene with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks" >> $err_log
	    less error.log > temp
            # remove unecessary lines from error log
	    sed '/^scene/ d' temp > temp2 
	    sed '/^USAGE/ d' temp2 >> $err_log
	    grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	    echo " " >> $err_log
	    echo " " >> $err_log
	    rm -f temp temp2
	fi
    elif [ $subset == no ]; then # no subsetting 
        # no multi-look value - for geocoding full SLC data
	echo "Coregistering DEM to master scene with 1 range and 1 azimuth looks..."
	make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 - - - -
	cd $dem_dir
	echo "Coregistering DEM to master scene with 1 range and 1 azimuth looks" >> $err_log
	less error.log > temp
        # remove unecessary lines from error log
	sed '/^scene/ d' temp > temp2 
	sed '/^USAGE/ d' temp2 >> $err_log
	grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	echo " " >> $err_log
	echo " " >> $err_log
	rm -f temp temp2
        # SLC and ifm multi-look value (same value)
	if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
	    echo "Coregistering DEM to master scene with "$slc_rlks" range and "$slc_alks" azimuth looks..."
	    cd $proj_dir
	    make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines
	    cd $dem_dir
	    echo " " >> $err_log
	    echo "Coregistering DEM to master scene with "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
	    less error.log > temp
        # remove unecessary lines from error log
	    sed '/^scene/ d' temp > temp2 
	    sed '/^USAGE/ d' temp2 >> $err_log
	    grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	    echo " " >> $err_log
	    echo " " >> $err_log
	    rm -f temp temp2
	else
            # SLC multi-look value
	    echo "Coregistering DEM to master scene with SLC "$slc_rlks" range and "$slc_alks" azimuth looks..."
	    cd $proj_dir
	    make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines
	    cd $dem_dir
	    echo " " >> $err_log
	    echo " " >> $err_log
	    echo "Coregistering DEM to master scene with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
	    less error.log > temp
            # remove unecessary lines from error log
	    sed '/^scene/ d' temp > temp2 
	    sed '/^USAGE/ d' temp2 >> $err_log
	    grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	    echo " " >> $err_log
	    echo " " >> $err_log
	    rm -f temp temp2
            # ifm multi-look value
	    echo "Coregistering DEM to master scene with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
	    cd $proj_dir
	    make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 1 $roff $rlines $azoff $azlines
	    cd $dem_dir
	    echo " " >> $err_log
	    echo " " >> $err_log
	    echo "Coregistering DEM to master scene with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks" >> $err_log
	    less error.log > temp
        # remove unecessary lines from error log
	    sed '/^scene/ d' temp > temp2 
	    sed '/^USAGE/ d' temp2 >> $err_log
	    grep "correlation SNR:" output.log >> $err_log # a value will appear if SNR is below threshold
	    echo " " >> $err_log
	    echo " " >> $err_log
	    rm -f temp temp2
	fi
    else
	:
    fi
    echo " "
    echo "Coregistering DEM to master scene completed."
    echo " "
elif [ $coregister_dem == no -a $platform == GA ]; then
    echo " "
    echo "Option to coregister DEM to master scene not selected."
    echo " "


#### NCI ####
elif [ $coregister_dem == yes -a $platform == NCI ]; then
    echo "Coregistering DEM to master scene..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    dem_batch_dir=$batch_dir/dem_jobs
    cd $dem_batch_dir
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job script for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $dem_batch_dir/$beam_num
		if [ $subset == yes ]; then 
		    if [ $roff == "-" -a $rlines == "-" -a $azoff == "-" -a $azlines == "-" ]; then
                        # no multi-look value - for geocoding full SLC and determining pixels for subsetting master scene
                        # set up header for PBS job
			job="coreg_full_dem_"$beam_num
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$dem_walltime >> $job
			echo \#\PBS -l mem=$dem_mem >> $job
			echo \#\PBS -l ncpus=$dem_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			if [ $do_slc == yes -a $platform == NCI ]; then
			    slc_jobid=`awk 'END{print}' $batch_dir/slc_jobs/$beam_num/"all_slc_"$beam_num"_job_id" | sed s/.r-man2//`
			    echo \#\PBS -W depend=afterok:$slc_jobid >> $job
			else
			    :
			fi
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 - - - - $beam_num >> $job
			chmod +x $job
			qsub $job | tee dem_full_job_id

                        # determine subset pixels and update proc file with values
                        # set up header for PBS job
			dem_full_jobid=`sed s/.r-man2// dem_full_job_id`
			job="calc_"$beam_num"_subset"
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$list_walltime >> $job
			echo \#\PBS -l mem=$list_mem >> $job
			echo \#\PBS -l ncpus=$list_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			echo \#\PBS -W depend=afterok:$dem_full_jobid >> $job
			echo ~/repo/gamma_bash/determine_subscene_pixels.bash $proj_dir/$proc_file $subset_file $beam_num >> $job
			chmod +x $job
			qsub $job | tee subset_job_id

	        	#rerun process_gamma.bash once calc_subset has run to include subset values in coreg_sub_dem PBS job
			subset_jobid=`sed s/.r-man2// subset_job_id`
			job=rerun_process_gamma
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$list_walltime >> $job
			echo \#\PBS -l mem=$list_mem >> $job
			echo \#\PBS -l ncpus=$list_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			echo \#\PBS -W depend=afterok:$subset_jobid >> $job
			echo ~/repo/gamma_bash/process_gamma.bash $proj_dir/$proc_file >> $job
			chmod +x $job
			qsub $job

		    elif [ $roff != "-" -a $rlines != "-" -a $azoff != "-" -a $azlines != "-" ]; then
			subset_jobid=`sed s/.r-man2// subset_job_id`
			if [ -e calc_subset.e$subset_jobid ]; then
		            # subset dem
                            # set up header for PBS job
			    job="coreg_"$beam_num"_sub_dem"
			    echo \#\!/bin/bash > $job
			    echo \#\PBS -lother=gdata1 >> $job
			    echo \#\PBS -l walltime=$dem_walltime >> $job
			    echo \#\PBS -l mem=$dem_mem >> $job
			    echo \#\PBS -l ncpus=$dem_ncpus >> $job
			    echo \#\PBS -l wd >> $job
			    echo \#\PBS -q normal >> $job
                            # no multi-look value - for geocoding full subsetted SLC data
			    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 2 $roff $rlines $azoff $azlines $beam_num >> $job
                            # SLC and ifm multi-look value (same value)
			    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
			    else
                                # SLC multi-look value
				echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
                                # ifm multi-look value
				echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
			    fi	  
			    chmod +x $job
			    qsub $job | tee dem_job_id
                    
                            # run dem error check
			    dem_jobid=`sed s/.r-man2// dem_job_id`
			    job=dem_err_check
			    echo \#\!/bin/bash > $job
			    echo \#\PBS -lother=gdata1 >> $job
			    echo \#\PBS -l walltime=00:10:00 >> $job
			    echo \#\PBS -l mem=50MB >> $job
			    echo \#\PBS -l ncpus=1 >> $job
			    echo \#\PBS -l wd >> $job
			    echo \#\PBS -q normal >> $job
			    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
			    echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 2 >> $job
			    chmod +x $job
			    qsub $job
			else
			    :
			fi
		    else
			echo ""
			echo "Subsetting values in proc file are not - . Update proc file before subsetting can occur."  1>&2
			echo ""
		    fi
		elif [ $subset == no ]; then # no subsetting 
                    # no multi-look value - for geocoding full SLC data
                    # set up header for PBS job
		    job="coreg_"$beam_num"_dem"
		    echo \#\!/bin/bash > $job
		    echo \#\PBS -lother=gdata1 >> $job
		    echo \#\PBS -l walltime=$dem_walltime >> $job
		    echo \#\PBS -l mem=$dem_mem >> $job
		    echo \#\PBS -l ncpus=$dem_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    if [ $do_slc == yes -a $platform == NCI ]; then
			slc_jobid=`awk 'END{print}' $batch_dir/slc_jobs/$beam_num/"all_slc_"$beam_num"_job_id" | sed s/.r-man2//`
			echo \#\PBS -W depend=afterok:$slc_jobid >> $job
		    else
			:
		    fi
                    # no multi-look value - for geocoding full SLC data
		    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 - - - - $beam_num >> $job
                    # SLC and ifm multi-look value (same value)
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 - - - - $beam_num >> $job
		    else
                        # SLC multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 - - - - $beam_num >> $job
                        # ifm multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 - - - - $beam_num >> $job
		    fi	  
		    chmod +x $job
		    qsub $job | tee dem_job_id

                    # run dem error check
		    dem_jobid=`sed s/.r-man2// dem_job_id`
		    job="dem_err_"$beam_num"_check"
		    echo \#\!/bin/bash > $job
		    echo \#\PBS -lother=gdata1 >> $job
		    echo \#\PBS -l walltime=00:10:00 >> $job
		    echo \#\PBS -l mem=50MB >> $job
		    echo \#\PBS -l ncpus=1 >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
		    echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 2 >> $job
		    chmod +x $job
		    qsub $job
		else
		    :
		fi
	    fi
	done < $beam_list
    else # no beams
	cd $dem_batch_dir
	if [ $subset == yes ]; then 
	    if [ $roff == "-" -a $rlines == "-" -a $azoff == "-" -a $azlines == "-" ]; then
                # no multi-look value - for geocoding full SLC and determining pixels for subsetting master scene
                # set up header for PBS job
		job=coreg_full_dem
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$dem_walltime >> $job
		echo \#\PBS -l mem=$dem_mem >> $job
		echo \#\PBS -l ncpus=$dem_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $do_slc == yes -a $platform == NCI ]; then
		    slc_jobid=`awk 'END{print}' $batch_dir/slc_jobs/all_slc_job_id | sed s/.r-man2//`
		    echo \#\PBS -W depend=afterok:$slc_jobid >> $job
		else
		    :
		fi
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 - - - - >> $job
		chmod +x $job
		qsub $job | tee full_dem_job_id

                # determine subset pixels and update proc file with values
                # set up header for PBS job
		dem_full_jobid=`sed s/.r-man2// full_dem_job_id`
		job=calc_subset
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$list_walltime >> $job
		echo \#\PBS -l mem=$list_mem >> $job
		echo \#\PBS -l ncpus=$list_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterok:$dem_full_jobid >> $job
		echo ~/repo/gamma_bash/determine_subscene_pixels.bash $proj_dir/$proc_file $subset_file >> $job
		chmod +x $job
		qsub $job | tee subset_job_id

		#rerun process_gamma.bash once calc_subset has run to include subset values in coreg_sub_dem PBS job
		subset_jobid=`sed s/.r-man2// subset_job_id`
		job=rerun_process_gamma
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$list_walltime >> $job
		echo \#\PBS -l mem=$list_mem >> $job
		echo \#\PBS -l ncpus=$list_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterok:$subset_jobid >> $job
		echo ~/repo/gamma_bash/process_gamma.bash $proj_dir/$proc_file >> $job
		chmod +x $job
		qsub $job

	    elif [ $roff != "-" -a $rlines != "-" -a $azoff != "-" -a $azlines != "-" ]; then
		subset_jobid=`sed s/.r-man2// subset_job_id`
		if [ -e calc_subset.e$subset_jobid ]; then
		    # subset dem
                    # set up header for PBS job
		    job=coreg_sub_dem
		    echo \#\!/bin/bash > $job
		    echo \#\PBS -lother=gdata1 >> $job
		    echo \#\PBS -l walltime=$dem_walltime >> $job
		    echo \#\PBS -l mem=$dem_mem >> $job
		    echo \#\PBS -l ncpus=$dem_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
                    # no multi-look value - for geocoding full subsetted SLC data
		    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proc_file 1 1 1 2 $roff $rlines $azoff $azlines >> $job
                    # SLC and ifm multi-look value (same value)
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proc_file $slc_rlks $slc_alks 2 2 $roff $rlines $azoff $azlines >> $job
		    else
                        # SLC multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proc_file $slc_rlks $slc_alks 2 2 $roff $rlines $azoff $azlines >> $job
                        # ifm multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proc_file $ifm_rlks $ifm_alks 2 2 $roff $rlines $azoff $azlines >> $job
		    fi	  
		    chmod +x $job
		    qsub $job | tee dem_job_id
         
                    # run dem error check
		    dem_jobid=`sed s/.r-man2// dem_job_id`
		    job=dem_err_check
		    echo \#\!/bin/bash > $job
		    echo \#\PBS -lother=gdata1 >> $job
		    echo \#\PBS -l walltime=00:10:00 >> $job
		    echo \#\PBS -l mem=50MB >> $job
		    echo \#\PBS -l ncpus=1 >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
		    echo ~/repo/gamma_bash/collate_nci_errors.bash $proc_file 2 >> $job
		    chmod +x $job
		    qsub $job
		else
		    echo "not working"
		fi
	    else
		echo ""
		echo "Subsetting values in proc file are not -. Update proc file before subsetting can occur."  1>&2
		echo ""
	    fi
	elif [ $subset == no ]; then # no subsetting 
            # no multi-look value - for geocoding full SLC data
            # set up header for PBS job
	    job=coreg_dem
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    if [ $do_slc == yes -a $platform == NCI ]; then
		slc_jobid=`awk 'END{print}' $batch_dir/slc_jobs/all_slc_job_id | sed s/.r-man2//`
		echo \#\PBS -W depend=afterok:$slc_jobid >> $job
	    else
		:
	    fi
            # no multi-look value - for geocoding full SLC data
	    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 - - - - >> $job
            # SLC and ifm multi-look value (same value)
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 - - - - >> $job
	    else
                # SLC multi-look value
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 - - - - >> $job
                # ifm multi-look value
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 - - - - >> $job
	    fi	  
	    chmod +x $job
	    qsub $job | tee dem_job_id

            # run dem error check
	    dem_jobid=`sed s/.r-man2// dem_job_id`
	    job=dem_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=00:10:00 >> $job
	    echo \#\PBS -l mem=50MB >> $job
	    echo \#\PBS -l ncpus=1 >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
	    echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 2 >> $job
	    chmod +x $job
	    qsub $job
	else
	    :
	fi
    fi
elif [ $coregister_dem == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to coregister DEM to master scene not selected." 1>&2
    echo "" 1>&2

else
    :
fi




##########################   COREGISTER SLAVE SCENES TO MASTER SCENE   ##########################

if [ $sensor == S1 ]; then
    coreg_script=coregister_S1_slave_SLC.bash
else
    coreg_script=coregister_slave_SLC.bash
fi


#### GA ####

if [ $coregister == yes -a $platform == GA ]; then
    cd $proj_dir
# consolidate error logs into one file
    err_log=$err_dir/SLC_coreg_error.log
    echo "PROJECT: "$project"_"$sensor"_"$track_dir"_Coregister_SLC_Error_Log" > $err_log
    echo " " >> $err_log
    echo "Coregistering slave scenes to master scene..."
# SLC and ifm multi-look value (same value)
    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
	while read date; do
	    if [ ! -z $date ]; then
		slave=`echo $date | awk 'BEGIN {FS=","} ; {print $1}'`
		echo "Coregistering "$slave" to master scene with "$slc_rlks" range and "$slc_alks" azimuth looks..."
		$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
	    fi
	done < $slave_list
    else
	while read date; do
	    if [ ! -z $date ]; then
		slave=`echo $date | awk 'BEGIN {FS=","} ; {print $1}'`
 # SLC multi-look value
		echo "Coregistering "$slave" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks..."
		$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
# ifm multi-look value
		echo " "
		echo "Coregistering "$slave" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
		$coreg_script $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks" >> $err_log
		less error.log >> $err_log		
	    fi
	done < $slave_list
    fi
    echo " "
    echo "Coregistering slave scenes to master scene completed."
    echo "   Run 'check_slave_coregistration.bash' script to check results before continuing processing."
    echo " "
elif [ $coregister == no -a $platform == GA ]; then
    echo " "
    echo "Option to coregister slaves to master scene not selected."
    echo " "


#### NCI ####

elif [ $coregister == yes -a $platform == NCI ]; then
    echo "Coregistering slave scenes to master scene..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    co_slc_batch_dir=$batch_dir/slc_coreg_jobs

    # Maximum number of jobs to be run (maximum number is 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $co_slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a single coreg_slc in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_script_prefix=co_slc_

    if [ -f $beam_list ]; then # if beam list exists
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $co_slc_batch_dir/$beam_num

		function create_jobs {
		    
		    local njobs=$1
		    local nsteps=$2
		    local i=$3
		    local wt=$(( wt1*nsteps ))
		    local hh=$(( wt/60 ))
		    local mm=$(( wt%60 ))
		    local m=0
		    local n=0
		    
		    for(( m=0; m<njobs; m++ )); do
        		i=$(( i+=1 ))
        		jobdir=$job_dir_prefix$i
        		mkdir -p $jobdir
        		cd $jobdir
        		script=$pbs_script_prefix$i
			
			echo Doing job $i in $jobdir with $script
			
			echo \#\!/bin/bash > $script 
			echo \#\PBS -l other=gdata1 >> $script
			echo \#\PBS -l walltime=$hh":"$mm":00" >> $script
			echo \#\PBS -l mem=$co_slc_mem >> $script
			echo \#\PBS -l ncpus=$co_slc_ncpus >> $script
			echo \#\PBS -l wd >> $script
			echo \#\PBS -q normal >> $script
			echo -e "\n" >> $script
			if [ $coregister_dem == yes -a $platform == NCI ]; then 
			    dem_jobid=`sed s/.r-man2// $batch_dir/dem_jobs/$beam_num/dem_err_job_id`
			    echo \#\PBS -W depend=afterok:$dem_jobid >> $script
			else
			    :
			fi			
        		for(( n=0; n<nsteps; n++ )); do
                	    read scene
                	    echo $scene
			    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
			    else
				echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
				echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $script
			    fi
			done
			chmod +x $script
			qsub $script | tee $co_slc_batch_dir/$beam_num/"co_slc_"$beam_num"_"$i"_job_id"
			cd ..
		    done
		}
                # Work starts here
		cd $co_slc_batch_dir/$beam_num
		nlines=`cat $slave_list | sed '/^\s*$/d' | wc -l`
		echo Need to process $nlines files

                 # Need to run kjobs with k steps and ljobs with l steps. 
		if [ $nlines -le $maxjobs ]; then
		    kjobs=$nlines
		    k=1
		    ljobs=0
		    l=0
		else
		    l=$((nlines/maxjobs))
		    k=$((nlines%maxjobs))
		    kjobs=$k
		    k=$((l+1))
		    ljobs=$((maxjobs-kjobs))
		fi

		echo Preparing to run $kjobs jobs with $k steps and $ljobs jobs with $l steps processing $((kjobs*k+ljobs*l)) files
		
		j=0
		{
		    create_jobs kjobs k j 
		    create_jobs ljobs l kjobs 
		    
		} < $slave_list

	        # create dependency list (make sure all coreg slcs are finished before error consolidation)
		cd $co_slc_batch_dir/$beam_num
		ls "co_slc_"$beam_num"_"*"_job_id" > list1
		if [ -f list2 ]; then
		    rm -rf list2
		else
		    :
		fi
		while read id; do
		    less $id >> list2 
		done < list1
		sed s/.r-man2// list2 > list3 # leave just job numbers
		sort -n list3 > list4 # sort numbers
		tr '\n' ':' < list4 > list5 # move column to single row with numbers separated by :
		sed s'/.$//' list5 > "all_co_slc_"$beam_num"_job_id" # remove last :
		dep=`awk '{print $1}' "all_co_slc_"$beam_num"_job_id"`
		rm -rf list* "co_slc_"$beam_num"_"*"_job_id"

                # in case future manual processing is required, create manual PBS jobs for each slave
		cd $co_slc_batch_dir/$beam_num/manual_jobs
		while read list; do
		    scene=`echo $list | awk '{print $1}'`
		    script="co_slc_"$beam_num"_"$scene
		    echo \#\!/bin/bash > $script
		    echo \#\PBS -lother=gdata1 >> $script
		    echo \#\PBS -l walltime=$co_slc_walltime >> $script
		    echo \#\PBS -l mem=$co_slc_mem >> $script
		    echo \#\PBS -l ncpus=$co_slc_ncpus >> $script
		    echo \#\PBS -l wd >> $script
		    echo \#\PBS -q normal >> $script
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
		    else
			echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $script
			echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $script
		    fi
		    chmod +x $script
		done < $slave_list

                # run coreg slc error check
		cd $co_slc_batch_dir/$beam_num
		job="co_slc_err_"$beam_num"_check"
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=00:10:00 >> $job
		echo \#\PBS -l mem=50MB >> $job
		echo \#\PBS -l ncpus=1 >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterany:$dep >> $job
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 3 >> $job
		chmod +x $job
		qsub $job | tee co_slc_err_job_id
	    fi
	done < $beam_list
    else # no beams
	cd $co_slc_batch_dir

	function create_jobs {
	    
	    local njobs=$1
	    local nsteps=$2
	    local i=$3
	    local wt=$(( wt1*nsteps ))
	    local hh=$(( wt/60 ))
	    local mm=$(( wt%60 ))
	    local m=0
	    local n=0
	    
	    for(( m=0; m<njobs; m++ )); do
        	i=$(( i+=1 ))
        	jobdir=$job_dir_prefix$i
        	mkdir -p $jobdir
        	cd $jobdir
        	script=$pbs_script_prefix$i
		
		echo Doing job $i in $jobdir with $script
		
		echo \#\!/bin/bash > $script 
		echo \#\PBS -l other=gdata1 >> $script
		echo \#\PBS -l walltime=$hh":"$mm":00" >> $script
		echo \#\PBS -l mem=$co_slc_mem >> $script
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $script
		echo \#\PBS -l wd >> $script
		echo \#\PBS -q normal >> $script
		echo -e "\n" >> $script
		if [ $coregister_dem == yes -a $platform == NCI ]; then 
		    dem_jobid=`sed s/.r-man2// $batch_dir/dem_jobs/dem_err_job_id`
		    echo \#\PBS -W depend=afterok:$dem_jobid >> $script
		else
		    :
		fi
		for(( n=0; n<nsteps; n++ )); do
                    read scene
                    echo $scene
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
		    else
			echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
			echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $script
		    fi
        	done
		chmod +x $script
		qsub $script | tee $co_slc_batch_dir/"co_slc_"$i"_job_id" 		
		cd ..
	    done
	}
        # Work starts here
	cd $co_slc_batch_dir
	nlines=`cat $slave_list | sed '/^\s*$/d' | wc -l`
	echo Need to process $nlines files
	
        # Need to run kjobs with k steps and ljobs with l steps. 
	if [ $nlines -le $maxjobs ]; then
	    kjobs=$nlines
	    k=1
	    ljobs=0
	    l=0
	else
	    l=$((nlines/maxjobs))
	    k=$((nlines%maxjobs))
	    kjobs=$k
	    k=$((l+1))
	    ljobs=$((maxjobs-kjobs))
	fi
	
	echo Preparing to run $kjobs jobs with $k steps and $ljobs jobs with $l steps processing $((kjobs*k+ljobs*l)) files
	
	j=0
	{
	    create_jobs kjobs k j 
	    create_jobs ljobs l kjobs 
	    
	} < $slave_list
	
        # create dependency list (make sure all coreg slcs are finished before error consolidation)
	cd $co_slc_batch_dir
	ls "co_slc_"*"_job_id" > list1
	if [ -f list2 ]; then
	    rm -rf list2
	else
	    :
	fi
	while read id; do
	    less $id >> list2 
	done < list1
	sed s/.r-man2// list2 > list3 # leave just job numbers
	sort -n list3 > list4 # sort numbers
	tr '\n' ':' < list4 > list5 # move column to single row with numbers separated by :
	sed s'/.$//' list5 > all_co_slc_job_id # remove last :
	dep=`awk '{print $1}' all_co_slc_job_id`
	rm -rf list* "co_slc_"*"_job_id"

        # in case future manual processing is required, create manual PBS jobs for each scene
	cd $co_slc_batch_dir/manual_jobs
	while read list; do
	    scene=`echo $list | awk '{print $1}'`
	    script="slc_"$scene
	    echo \#\!/bin/bash > $script
	    echo \#\PBS -lother=gdata1 >> $script
	    echo \#\PBS -l walltime=$co_slc_walltime >> $script
	    echo \#\PBS -l mem=$co_slc_mem >> $script
	    echo \#\PBS -l ncpus=$co_slc_ncpus >> $script
	    echo \#\PBS -l wd >> $script
	    echo \#\PBS -q normal >> $script
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
	    else
		echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $script
		echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $script
	    fi
	    chmod +x $script
	done < $slave_list

        # run coreg slc error check
	cd $co_slc_batch_dir
	job=co_slc_err_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=00:10:00 >> $job
	echo \#\PBS -l mem=50MB >> $job
	echo \#\PBS -l ncpus=1 >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterany:$dep >> $job
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 3 >> $job
	chmod +x $job
	qsub $job | tee co_slc_err_job_id
    fi

    # PBS job for checking slave coregistration  - doesn't work, won't display window
#    job=check_slc_coreg
#    co_slc_jobid=`sed s/.r-man2// co_slc_err_job_id`
#    echo \#\!/bin/bash > $job
#    echo \#\PBS -lother=gdata1 >> $job
#    echo \#\PBS -l walltime=00:10:00 >> $job
#    echo \#\PBS -l mem=50MB >> $job
#    echo \#\PBS -l ncpus=1 >> $job
#    echo \#\PBS -l wd >> $job
#    echo \#\PBS -q normal >> $job
#    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $job
#    echo ~/repo/gamma_bash/check_slave_coregistration.bash $proj_dir/$proc_file 1 >> $job
#    chmod +x $job
#    qsub $job
elif [ $coregister == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to coregister slaves to master scene not selected." 1>&2
    echo "" 1>&2
else
    :
fi




##########################   PROCESS INTERFEROGRAMS AND GEOCODE UNWRAPPED FILES   ##########################


#### GA ####

if [ $do_ifms == yes -a $platform == GA ]; then
    echo "Creating interferograms..."
    echo " "
    while read list; do
	mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks
    done < $ifm_list
# consolidate ifm error logs into one file
    err_log=$err_dir/ifm_error.log
    echo "PROJECT: "$project"_"$sensor"_"$track_dir"_Interferogram_Error_Log" > $err_log
    echo " " >> $err_log
    echo " " >> $err_log
    while read ifm; do
	mas_slv_dir=$ifm_dir/$mas-$slv
	if [ ! -z $ifm ]; then
	    cd $mas_slv_dir
	    echo $mas-$slv >> $err_log
	    echo " " >> $err_log
	    less error.log >> $err_log
	fi
    done < $ifm_list
    echo " "
    echo "Processing interferograms complete."
    echo " "

# final baseline script
# plot_baseline_gamma.csh

elif [ $do_ifms == no -a $platform == GA ]; then
    echo " "
    echo "Option to create interferograms not selected."
    echo " "


#### NCI ####

elif [ $do_ifms == yes -a $platform == NCI ]; then
    echo "Creating interferograms..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    ifm_batch_dir=$batch_dir/ifm_jobs

    # Maximum number of jobs to be run (maximum is 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $ifm_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a process_ifm in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_script_prefix=ifm_

    if [ -f $beam_list ]; then # if beam list exists
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $ifm_batch_dir/$beam_num

		function create_jobs {
		    
		    local njobs=$1
		    local nsteps=$2
		    local i=$3
		    local wt=$(( wt1*nsteps ))
		    local hh=$(( wt/60 ))
		    local mm=$(( wt%60 ))
		    local m=0
		    local n=0
		    
		    for(( m=0; m<njobs; m++ )); do
        		i=$(( i+=1 ))
        		jobdir=$job_dir_prefix$i
        		mkdir -p $jobdir
        		cd $jobdir
        		script=$pbs_script_prefix$i
			
			echo Doing job $i in $jobdir with $script
			
			echo \#\!/bin/bash > $script 
			echo \#\PBS -l other=gdata1 >> $script
			echo \#\PBS -l walltime=$hh":"$mm":00" >> $script
			echo \#\PBS -l mem=$ifm_mem >> $script
			echo \#\PBS -l ncpus=$ifm_ncpus >> $script
			echo \#\PBS -l wd >> $script
			echo \#\PBS -q normal >> $script
			echo -e "\n" >> $script
			if [ $coregister == yes -a $platform == NCI ]; then
			    co_slc_jobid=`sed s/.r-man2// $batch_dir/slc_coreg_jobs/$beam_num/"all_co_slc_"$beam_num"_job_id"`
			    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $script
			else
			    :
			fi
			for(( n=0; n<nsteps; n++ )); do
                            read line
                            echo $line
                            mas=`echo $line | awk 'BEGIN {FS=","} ; {print $1}'`
                            slv=`echo $line | awk 'BEGIN {FS=","} ; {print $2}'`
			    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $script
 			done
			chmod +x $script
			qsub $script | tee $ifm_batch_dir/$beam_num/"ifm_"$beam_num"_"$i"_job_id"
			cd ..
		    done
		}
                # Work starts here
		cd $ifm_batch_dir/$beam_num
		nlines=`cat $ifm_list | sed '/^\s*$/d' | wc -l`
		echo Need to process $nlines files

                 # Need to run kjobs with k steps and ljobs with l steps. 
		if [ $nlines -le $maxjobs ]; then
		    kjobs=$nlines
		    k=1
		    ljobs=0
		    l=0
		else
		    l=$((nlines/maxjobs))
		    k=$((nlines%maxjobs))
		    kjobs=$k
		    k=$((l+1))
		    ljobs=$((maxjobs-kjobs))
		fi

		echo Preparing to run $kjobs jobs with $k steps and $ljobs jobs with $l steps processing $((kjobs*k+ljobs*l)) files
		
		j=0
		{
		    create_jobs kjobs k j 
		    create_jobs ljobs l kjobs 
		    
		} < $ifm_list

	        # create dependency list (make sure all ifms are finished before error consolidation)
		cd $ifm_batch_dir/$beam_num
		ls "ifm_"$beam_num"_"*"_job_id" > list1
		if [ -f list2 ]; then
		    rm -rf list2
		else
		    :
		fi
		while read id; do
		    less $id >> list2 
		done < list1
		sed s/.r-man2// list2 > list3 # leave just job numbers
		sort -n list3 > list4 # sort numbers
		tr '\n' ':' < list4 > list5 # move column to single row with numbers separated by :
		sed s'/.$//' list5 > "all_ifm_"$beam_num"_job_id" # remove last :
		dep=`awk '{print $1}' "all_ifm_"$beam_num"_job_id"`
		rm -rf list* "ifm_"$beam_num"_"*"_job_id"

                # in case future manual processing is required, create manual PBS jobs for each ifm
		cd $ifm_batch_dir/$beam_num/manual_jobs
		while read list; do
		    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
		    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
		    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		    script="ifm_"$beam_num"_"$mas_name-$slv_name
		    echo \#\!/bin/bash > $script
		    echo \#\PBS -lother=gdata1 >> $script
		    echo \#\PBS -l walltime=$ifm_walltime >> $script
		    echo \#\PBS -l mem=$ifm_mem >> $script
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $script
		    echo \#\PBS -l wd >> $script
		    echo \#\PBS -q normal >> $script
		    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $script
		    chmod +x $script
		done < $ifm_list

                # run ifm error check
		cd $ifm_batch_dir/$beam_num
		job="ifm_err_"$beam_num"_check"
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=00:10:00 >> $job
		echo \#\PBS -l mem=50MB >> $job
		echo \#\PBS -l ncpus=1 >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterany:$dep >> $job
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 4 >> $job
		chmod +x $job
		qsub $job | tee ifm_err_job_id

   	        # run post ifm processing
		cd $ifm_batch_dir/$beam_num
		ifm_post=post_ifm_processing
		echo \#\!/bin/bash > $ifm_post
		echo \#\PBS -lother=gdata1 >> $ifm_post
		echo \#\PBS -l walltime=$raw_walltime >> $ifm_post
		echo \#\PBS -l mem=$raw_mem >> $ifm_post
		echo \#\PBS -l ncpus=$raw_ncpus >> $ifm_post
		echo \#\PBS -l wd >> $ifm_post
		echo \#\PBS -q normal >> $ifm_post
		echo \#\PBS -W depend=afterok:$dep >> $ifm_post
		echo ~/repo/gamma_bash/post_ifm_processing.bash $proj_dir/$proc_file 1 $beam_num >> $ifm_post
		chmod +x $ifm_post
		qsub $ifm_post | tee $ifm_batch_dir/post_ifm_job_id
	    fi
	done < $beam_list

        # mosaic beam interferograms
	num_beams=`wc -l < $beam_list`
	cd $ifm_batch_dir
	if [ $num_beams -gt 1 ]; then
	    post_ifm_jobid=`sed s/.r-man2// post_ifm_job_id`
	    mosaic=mosaic_beam_ifms
	    echo \#\!/bin/bash > $mosaic
	    echo \#\PBS -lother=gdata1 >> $mosaic
	    echo \#\PBS -l walltime=$ifm_walltime >> $mosaic
	    echo \#\PBS -l mem=$ifm_mem >> $mosaic
	    echo \#\PBS -l ncpus=$ifm_ncpus >> $mosaic
	    echo \#\PBS -l wd >> $mosaic
	    echo \#\PBS -q normal >> $mosaic
	    echo \#\PBS -W depend=afterok:$dep >> $mosaic
	    echo ~/repo/gamma_bash/mosaic_beam_ifms.bash $proj_dir/$proc_file >> $mosaic
	    chmod +x $mosaic
#	    qsub $mosaic
	else
	    :
	fi
    else # no beam list
	cd $ifm_batch_dir
	
	function create_jobs {
	    
	    local njobs=$1
	    local nsteps=$2
	    local i=$3
	    local wt=$(( wt1*nsteps ))
	    local hh=$(( wt/60 ))
	    local mm=$(( wt%60 ))
	    local m=0
	    local n=0
	    
	    for(( m=0; m<njobs; m++ )); do
        	i=$(( i+=1 ))
        	jobdir=$job_dir_prefix$i
        	mkdir -p $jobdir
        	cd $jobdir
        	script=$pbs_script_prefix$i
		
		echo Doing job $i in $jobdir with $script
		
		echo \#\!/bin/bash > $script 
		echo \#\PBS -l other=gdata1 >> $script
		echo \#\PBS -l walltime=$hh":"$mm":00" >> $script
		echo \#\PBS -l mem=$ifm_mem >> $script
		echo \#\PBS -l ncpus=$ifm_ncpus >> $script
		echo \#\PBS -l wd >> $script
		echo \#\PBS -q normal >> $script
		echo -e "\n" >> $script
		if [ $coregister == yes -a $platform == NCI ]; then
		    co_slc_jobid=`sed s/.r-man2// $batch_dir/slc_coreg_jobs/all_co_slc_job_id`
		    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $script
		else
		    :
		fi
		for(( n=0; n<nsteps; n++ )); do
                    read line
                    echo $line
                    mas=`echo $line | awk 'BEGIN {FS=","} ; {print $1}'`
                    slv=`echo $line | awk 'BEGIN {FS=","} ; {print $2}'`
		    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $script
 		done
		chmod +x $script
		qsub $script | tee $ifm_batch_dir/"ifm_"$i"_job_id"
		cd ..
	    done
	}
        # Work starts here
	cd $ifm_batch_dir
	nlines=`cat $ifm_list | sed '/^\s*$/d' | wc -l`
	echo Need to process $nlines files
	
        # Need to run kjobs with k steps and ljobs with l steps. 
	if [ $nlines -le $maxjobs ]; then
	    kjobs=$nlines
	    k=1
	    ljobs=0
	    l=0
	else
	    l=$((nlines/maxjobs))
	    k=$((nlines%maxjobs))
	    kjobs=$k
	    k=$((l+1))
	    ljobs=$((maxjobs-kjobs))
	fi
	
	echo Preparing to run $kjobs jobs with $k steps and $ljobs jobs with $l steps processing $((kjobs*k+ljobs*l)) files
	
	j=0
	{
	    create_jobs kjobs k j 
	    create_jobs ljobs l kjobs 
	    
	} < $ifm_list
	
        # create dependency list (make sure all ifms are finished before error consolidation)
	cd $ifm_batch_dir
	ls "ifm_"*"_job_id" > list1
	if [ -f list2 ]; then
	    rm -rf list2
	else
	    :
	fi
	while read id; do
	    less $id >> list2 
	done < list1
	sed s/.r-man2// list2 > list3 # leave just job numbers
	sort -n list3 > list4 # sort numbers
	tr '\n' ':' < list4 > list5 # move column to single row with numbers separated by :
	sed s'/.$//' list5 > all_ifm_job_id # remove last :
	dep=`awk '{print $1}' all_ifm_job_id`
	rm -rf list* "ifm_"*"_job_id"
	
        # in case future manual processing is required, create manual PBS jobs for each ifm
	cd $ifm_batch_dir/manual_jobs
	while read list; do
	    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
	    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
	    script="ifm_"$mas_name-$slv_name
	    echo \#\!/bin/bash > $script
	    echo \#\PBS -lother=gdata1 >> $script
	    echo \#\PBS -l walltime=$ifm_walltime >> $script
	    echo \#\PBS -l mem=$ifm_mem >> $script
	    echo \#\PBS -l ncpus=$ifm_ncpus >> $script
	    echo \#\PBS -l wd >> $script
	    echo \#\PBS -q normal >> $script
	    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $script
	    chmod +x $script
	done < $ifm_list
	
        # run ifm error check
	cd $ifm_batch_dir
	job=ifm_err_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=00:10:00 >> $job
	echo \#\PBS -l mem=50MB >> $job
	echo \#\PBS -l ncpus=1 >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterany:$dep >> $job
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 4 >> $job
	chmod +x $job
	qsub $job | tee ifm_err_job_id

   	# run post ifm processing
	cd $ifm_batch_dir
	ifm_post=post_ifm_processing
	echo \#\!/bin/bash > $ifm_post
	echo \#\PBS -lother=gdata1 >> $ifm_post
	echo \#\PBS -l walltime=$raw_walltime >> $ifm_post
	echo \#\PBS -l mem=$raw_mem >> $ifm_post
	echo \#\PBS -l ncpus=$raw_ncpus >> $ifm_post
	echo \#\PBS -l wd >> $ifm_post
	echo \#\PBS -q normal >> $ifm_post
	echo \#\PBS -W depend=afterok:$dep >> $ifm_post
	echo ~/repo/gamma_bash/post_ifm_processing.bash $proj_dir/$proc_file 1 >> $ifm_post
	chmod +x $ifm_post
	qsub $ifm_post 
    fi	
elif [ $do_ifms == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create interferograms not selected." 1>&2
    echo "" 1>&2
else
    :
fi




##########################   ADD NEW SLCS TO EXISTING SLC COLLECTION   ##########################


#### GA ####

if [ $add_slc == yes -a $platform == GA ]; then
# extract raw data
    cd $proj_dir/$track_dir
    echo "Extracting raw data for additional SLC data..."
    echo " "
    extract_raw_data.bash $proj_dir/$proc_file 1
# create SLC data
    #if [ $do_slc == yes ]; then
	if [ $palsar1_data == raw -a $sensor == PALSAR1 ]; then
            sensor=PALSAR_L0 # PALSAR L1.0 script can process PALSAR1 raw data
	elif [ $palsar1_data == slc -a $sensor == PALSAR1 ]; then
            sensor=PALSAR_L1 # PALSAR L1.1 script can process both PALSAR1 and PALSAR2 slc level data
	elif [ $sensor == PALSAR2 ]; then
            sensor=PALSAR_L1
	else
            :
	fi
    #fi
echo $sensor
# consolidate error logs into one file
    err_log=$err_dir/SLC_add_error.log
    echo "PROJECT: "$project"_"$sensor"_"$track_dir"_Additional_SLC_Creation_Error_Log" > $err_log
    echo " " >> $err_log
    echo " "
    echo "Creating additional SLC data..."
    echo " "
# SLC and ifm multi-look value (same value)
    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
	while read scene; do
	    if [ ! -z $scene ]; then
		echo "Creating SLC for "$scene" with "$slc_rlks" range and "$slc_alks" azimuth looks..."
		process_$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks
		cd $slc_dir/$scene
		echo " " >> $err_log
		echo "Creating SLC for "$scene" with "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
	    else
		:
	    fi
	done < $add_scene_list
    else
	while read scene; do
	    if [ ! -z $scene ]; then
 # SLC multi-look value
		echo "Creating SLC for "$scene" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks..."
		process_$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks
		cd $slc_dir/$scene
		echo " " >> $err_log
		echo "Creating SLC for "$scene" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
# ifm multi-look value
		echo "Creating SLC for "$scene" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
		process_$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks
		cd $slc_dir/$scene
		echo " " >> $err_log
		echo "Creating SLC for "$scene" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
	    else
		:
	    fi
	done < $add_scene_list
    fi
    echo " "
    echo "Processing additional SLCs completed."
    echo " "
elif [ $add_slc == no -a $platform == GA ]; then
    echo " "
    echo "Option to create additional SLC data not selected."
    echo " "


#### NCI ####

elif [ $add_slc == yes -a $platform == NCI ]; then
# extract raw data
    echo "Extracting additional raw data..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    cd $batch_dir
    job=extract_add_raw 
    echo \#\!/bin/bash > $job
    echo \#\PBS -lother=gdata1 >> $job
    echo \#\PBS -l walltime=$raw_walltime >> $job
    echo \#\PBS -l mem=$raw_mem >> $job
    echo \#\PBS -l ncpus=$raw_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q copyq >> $job
    echo ~/repo/gamma_bash/extract_raw_data.bash $proj_dir/$proc_file 1 >> $job
    chmod +x $job
    qsub $job | tee add_raw_job_id

# create add_slaves.list file
    echo "Creating slaves list file..." 1>&2
    scene_list_jobid=`sed s/.r-man2// scene_list_job_id`
    job2=add_slave_list_gen
    echo \#\!/bin/bash > $job2
    echo \#\PBS -lother=gdata1 >> $job2
    echo \#\PBS -l walltime=$list_walltime >> $job2
    echo \#\PBS -l mem=$list_mem >> $job2
    echo \#\PBS -l ncpus=$list_ncpus >> $job2
    echo \#\PBS -l wd >> $job2
    echo \#\PBS -q normal >> $job2
    echo ~/repo/gamma_bash/create_slaves_list.bash $proj_dir/$proc_file 2 >> $job2
    chmod +x $job2
    qsub $job2 | tee slave_list_job_id

# create add_ifms.list file
    echo "Creating interferogram list file..." 1>&2
    job3=add_ifm_list_gen
    echo \#\!/bin/bash > $job3
    echo \#\PBS -lother=gdata1 >> $job3
    echo \#\PBS -l walltime=$list_walltime >> $job3
    echo \#\PBS -l mem=$list_mem >> $job3
    echo \#\PBS -l ncpus=$list_ncpus >> $job3
    echo \#\PBS -l wd >> $job3
    echo \#\PBS -q normal >> $job3
    echo ~/repo/gamma_bash/create_ifms_list.bash $proj_dir/$proc_file 2 >> $job3
    chmod +x $job3
    qsub $job3 | tee ifm_list_job_id

# create additional SLCs
    if [ $add_slc == yes -a $sensor == PALSAR1 ]; then
	if [ $palsar1_data == raw ]; then
	    sensor=PALSAR_L0 # PALSAR L1.0 script can process PALSAR1 raw data
	elif [ $palsar1_data == slc ]; then
	    sensor=PALSAR_L1 # PALSAR L1.1 script can process both PALSAR1 and PALSAR2 slc level data
	else
	    :
	fi
    elif [ $add_slc == yes -a $sensor == PALSAR2 ]; then
	sensor=PALSAR_L1
    else
	:
    fi
    echo "Creating additional SLC data..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    cd $batch_dir/slc_jobs
    mkdir -p add_slc_jobs
    slc_batch_dir=$batch_dir/slc_jobs/add_slc_jobs
    cd $slc_batch_dir
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job array for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $slc_batch_dir
		mkdir -p $beam_num
		cd $beam_num
                # create list of scenes with array number prefix
		tot_lines=`cat $add_scene_list | sed '/^\s*$/d' | wc -l`
		for ((l=1; l<=tot_lines; l++)); do 
		    echo $l >> num_list
		done
		sub_list=$beam_num"_subjob_list"
		if [ -f $sub_list ]; then
		    rm -rf $sub_list
		fi
		paste num_list $add_scene_list >> $sub_list
                # create subjobs (automatically uses the header details in the job_array script)
		while read sublist; do
		    if [ ! -z "${sublist}" ]; then
			subjob=`echo $sublist | awk '{print $1}'`
			scene=`echo $sublist | awk '{print $2}'`
			script=$subjob
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num > $script
			else
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num > $script
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $script
			fi
			chmod +x $script
		    fi
		done < $sub_list
	    	rm -rf num_list
                # make job_array PBS job
		add_raw_jobid=`sed s/.r-man2// $batch_dir/add_raw_job_id`
		array="array_"$beam_num"_slcs"
		if [ $tot_lines -eq 1 ]; then
		    num=1-2
		else
		    num=1-$tot_lines
		fi
		echo \#\!/bin/bash > $array
		echo \#\PBS -lother=gdata1 >> $array
		echo \#\PBS -l walltime=$slc_walltime >> $array
		echo \#\PBS -l mem=$slc_mem >> $array
		echo \#\PBS -l ncpus=$slc_ncpus >> $array
		echo \#\PBS -l wd >> $array
		echo \#\PBS -q normal >> $array
		echo \#\PBS -r y >> $array
		echo \#\PBS -J $num >> $array
		echo \#\PBS -W depend=afterok:$add_raw_jobid >> $array
		printf %s "$slc_batch_dir/$beam_num/$""PBS_ARRAY_INDEX" >> $array
		chmod +x $array
		qsub $array | tee add_slc_job_id
		# in case future manual processing is required, create manual PBS jobs for each slc
		cd $batch_dir/slc_jobs/$beam_num/manual_jobs
		while read scene; do
		    if [ ! -z $scene ]; then
			job=slc_$scene
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$slc_walltime >> $job
			echo \#\PBS -l mem=$slc_mem >> $job
			echo \#\PBS -l ncpus=$slc_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			else
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
			fi
			chmod +x $job
		    fi
		done < $add_scene_list
                # run slc error check
		cd $slc_batch_dir/$beam_num
		add_slc_jobid=`sed s/.r-man2// add_slc_job_id`
		job="add_slcerr_"$beam_num"_check"
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=00:10:00 >> $job
		echo \#\PBS -l mem=50MB >> $job
		echo \#\PBS -l ncpus=1 >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterok:$slc_jobid >> $job
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 5 >> $job
		chmod +x $job
		qsub $job
	    fi
	done < $beam_list
    else # no beams
        # set up and submit PBS job array
	cd $slc_batch_dir
        # create list of scenes with array number prefix
	tot_lines=`cat $add_scene_list | sed '/^\s*$/d' | wc -l`
	for ((l=1; l<=tot_lines; l++)); do 
	    echo $l >> num_list
	done
	sub_list=subjob_list
	if [ -f $sub_list ]; then
	    rm -rf $sub_list
	fi
	paste num_list $add_scene_list >> $sub_list
        # create subjobs (automatically uses the header details in the job_array script)
	while read sublist; do
	    if [ ! -z "${sublist}" ]; then
		subjob=`echo $sublist | awk '{print $1}'`
		scene=`echo $sublist | awk '{print $2}'`
		script=$subjob
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks > $script
		else
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks > $script
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $script
		fi
		chmod +x $script
	    fi
	done < $sub_list
	rm -rf num_list
        # make job_array PBS job
	raw_jobid=`sed s/.r-man2// $batch_dir/add_raw_job_id`
	array=array_slcs
	if [ $tot_lines -eq 1 ]; then
	    num=1-2
	else
	    num=1-$tot_lines
	fi
	echo \#\!/bin/bash > $array
	echo \#\PBS -lother=gdata1 >> $array
	echo \#\PBS -l walltime=$slc_walltime >> $array
	echo \#\PBS -l mem=$slc_mem >> $array
	echo \#\PBS -l ncpus=$slc_ncpus >> $array
	echo \#\PBS -l wd >> $array
	echo \#\PBS -q normal >> $array
	echo \#\PBS -r y >> $array
	echo \#\PBS -J $num >> $array
	echo \#\PBS -W depend=afterok:$add_raw_jobid >> $array
	printf %s "$slc_batch_dir/$""PBS_ARRAY_INDEX" >> $array
	chmod +x $array
	qsub $array | tee add_slc_job_id
	# in case future manual processing is required, create manual PBS jobs for each slc
	cd $batch_dir/slc_jobs/manual_jobs
	while read scene; do
	    if [ ! -z $scene ]; then
		job=slc_$scene
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$slc_walltime >> $job
		echo \#\PBS -l mem=$slc_mem >> $job
		echo \#\PBS -l ncpus=$slc_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		else
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		fi
		chmod +x $job
	    fi
	done < $add_scene_list
        # run slc error check
	cd $slc_batch_dir
	add_slc_jobid=`sed s/.r-man2// add_slc_job_id`
	job=add_slcerr_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=00:10:00 >> $job
	echo \#\PBS -l mem=50MB >> $job
	echo \#\PBS -l ncpus=1 >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterok:$add_slc_jobid >> $job
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 5 >> $job
	chmod +x $job
	qsub $job
    fi
elif [ $add_slc == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create additional SLC data not selected." 1>&2
    echo "" 1>&2
else
    :
fi




##########################   COREGISTER ADDITIONAL SLAVE SCENES TO MASTER SCENE   ##########################

if [ $sensor == S1 ]; then
    coreg_script=coregister_S1_slave_SLC.bash
else
    coreg_script=coregister_slave_SLC.bash
fi


#### GA ####

if [ $coregister_add == yes -a $platform == GA ]; then
    cd $proj_dir/$track_dir
    cp add_scenes.list add_slaves.list
    cd $proj_dir
# consolidate error logs into one file
    err_log=$err_dir/SLC_add_coreg_error.log
    echo "PROJECT: "$project"_"$sensor"_"$track_dir"_Coregister_Additional_SLC_Error_Log" > $err_log
    echo " " >> $err_log
    echo "Coregistering additional slave scenes to master scene..."
# SLC and ifm multi-look value (same value)
    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
	while read date; do
	    if [ ! -z $date ]; then
		slave=`echo $date | awk 'BEGIN {FS=","} ; {print $1}'`
		echo "Coregistering "$slave" to master scene with "$slc_rlks" range and "$slc_alks" azimuth looks..."
		$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
	    fi
	done < $add_slave_list
    else
	while read date; do
	    if [ ! -z $date ]; then
		slave=`echo $date | awk 'BEGIN {FS=","} ; {print $1}'`
 # SLC multi-look value
		echo "Coregistering "$slave" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks..."
		$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
# ifm multi-look value
		echo "Coregistering "$slave" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
		$coreg_script $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks" >> $err_log
		less error.log >> $err_log		
	    fi
	done < $add_slave_list
    fi
    echo " "
    echo "Coregister additional slave scenes to master scene completed."
    echo "   Run 'check_slave_coregistration.bash' script to check results before continuing processing."
    echo " "
elif [ $coregister_add == no -a $platform == GA ]; then
    echo " "
    echo "Option to coregister additional slaves to master scene not selected."
    echo " "


#### NCI ####

elif [ $coregister_add == yes -a $platform == NCI ]; then
    echo "Coregistering additional slave scenes to master scene..." 1>&2
    batch_dir=$proj_dir/$track_dir/batch_scripts
    cd $batch_dir/slc_coreg_jobs
    mkdir -p add_slc_coreg_jobs
    co_slc_batch_dir=$batch_dir/slc_coreg_jobs/add_slc_coreg_jobs
    cd $co_slc_batch_dir
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job array for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $co_slc_batch_dir
		mkdir -p $beam_num
		cd $beam_num
                # create list of scenes with array number prefix
		tot_lines=`cat $add_slave_list | sed '/^\s*$/d' | wc -l`
		for ((l=1; l<=tot_lines; l++)); do 
		    echo $l >> num_list
		done
		sub_list=$beam_num"_subjob_list"
		if [ -f $sub_list ]; then
		    rm -rf $sub_list
		fi
		paste num_list $add_slave_list >> $sub_list
                # create subjobs (automatically uses the header details in the job_array script)
		while read sublist; do
		    if [ ! -z "${sublist}" ]; then
			subjob=`echo $sublist | awk '{print $1}'`
			scene=`echo $sublist | awk '{print $2}'`
			script=$subjob
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num > $script
			else
			    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num > $script
			    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks $beam_num >> $script
			fi
			chmod +x $script
		    fi
		done < $sub_list
	    	rm -rf num_list
                # make job_array PBS job
		array="array_"$beam_num"_slcs"
		if [ $tot_lines -eq 1 ]; then
		    num=1-2
		else
		    num=1-$tot_lines
		fi
		echo \#\!/bin/bash > $array
		echo \#\PBS -lother=gdata1 >> $array
		echo \#\PBS -l walltime=$co_slc_walltime >> $array
		echo \#\PBS -l mem=$co_slc_mem >> $array
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $array
		echo \#\PBS -l wd >> $array
		echo \#\PBS -q normal >> $array
		echo \#\PBS -r y >> $array
		echo \#\PBS -J $num >> $array
		if [ $add_slc == yes -a $platform == NCI ]; then
		    add_slc_jobid=`sed s/.r-man2// $batch_dir/slc_jobs/add_slc_jobs/$beam_num/add_slc_job_id`
		    echo \#\PBS -W depend=afterok:$add_slc_jobid >> $array
		else
		    :
		fi
		printf %s "$co_slc_batch_dir/$beam_num/$""PBS_ARRAY_INDEX" >> $array
		chmod +x $array
		qsub $array | tee add_co_slc_job_id
		# in case future manual processing is required, create manual PBS jobs for each slc
		cd $batch_dir/slc_coreg_jobs/$beam_num/manual_jobs
		while read scene; do
		    if [ ! -z $scene ]; then
			job=slc_$scene
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$co_slc_walltime >> $job
			echo \#\PBS -l mem=$co_slc_mem >> $job
			echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num >> $job
			else
			    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num >> $job
			    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks $beam_num >> $job
			fi
			chmod +x $job
		    fi
		done < $add_slave_list
                # run slc coregistration error check
		cd $co_slc_batch_dir/$beam_num
		add_co_slc_jobid=`sed s/.r-man2// add_co_slc_job_id`
		job="add_coslcerr_"$beam_num"_check"
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=00:10:00 >> $job
		echo \#\PBS -l mem=50MB >> $job
		echo \#\PBS -l ncpus=1 >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterok:$slc_jobid >> $job
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 6 >> $job
		chmod +x $job
		qsub $job
	    fi
	done < $beam_list
    else # no beams
        # set up and submit PBS job array
	cd $co_slc_batch_dir
        # create list of scenes with array number prefix
	tot_lines=`cat $add_slave_list | sed '/^\s*$/d' | wc -l`
	for ((l=1; l<=tot_lines; l++)); do 
	    echo $l >> num_list
	done
	sub_list=subjob_list
	if [ -f $sub_list ]; then
	    rm -rf $sub_list
	fi
	paste num_list $add_slave_list >> $sub_list
        # create subjobs (automatically uses the header details in the job_array script)
	while read sublist; do
	    if [ ! -z "${sublist}" ]; then
		subjob=`echo $sublist | awk '{print $1}'`
		scene=`echo $sublist | awk '{print $2}'`
		script=$subjob
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks > $script
		else
		    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks > $script
		    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks >> $script
		fi
		chmod +x $script
	    fi
	done < $sub_list
	rm -rf num_list
        # make job_array PBS job
	array=array_slcs
	if [ $tot_lines -eq 1 ]; then
	    num=1-2
	else
	    num=1-$tot_lines
	fi
	echo \#\!/bin/bash > $array
	echo \#\PBS -lother=gdata1 >> $array
	echo \#\PBS -l walltime=$co_slc_walltime >> $array
	echo \#\PBS -l mem=$co_slc_mem >> $array
	echo \#\PBS -l ncpus=$co_slc_ncpus >> $array
	echo \#\PBS -l wd >> $array
	echo \#\PBS -q normal >> $array
	echo \#\PBS -r y >> $array
	echo \#\PBS -J $num >> $array
	if [ $add_slc == yes -a $platform == NCI ]; then
	    add_slc_jobid=`sed s/.r-man2// $batch_dir/slc_jobs/add_slc_jobs/$beam_num/add_slc_job_id`
	    echo \#\PBS -W depend=afterok:$add_slc_jobid >> $array
	else
	    :
	fi
	printf %s "$co_slc_batch_dir/$""PBS_ARRAY_INDEX" >> $array
	chmod +x $array
	qsub $array | tee add_co_slc_job_id
	# in case future manual processing is required, create manual PBS jobs for each slc
	cd $batch_dir/slc_coreg_jobs/manual_jobs
	while read scene; do
	    if [ ! -z $scene ]; then
		job=slc_$scene
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$co_slc_walltime >> $job
		echo \#\PBS -l mem=$co_slc_mem >> $job
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks >> $job
		else
		    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $slc_rlks $slc_alks >> $job
		    echo ~/repo/gamma_bash/$coreg_script $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks >> $job
		fi
		chmod +x $job
	    fi
	done < $add_slave_list
        # run slc coregistration error check
	cd $co_slc_batch_dir
	add_co_slc_jobid=`sed s/.r-man2// add_co_slc_job_id`
	job=add_coslcerr_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=00:10:00 >> $job
	echo \#\PBS -l mem=50MB >> $job
	echo \#\PBS -l ncpus=1 >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterok:$slc_jobid >> $job
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 6 >> $job
	chmod +x $job
	qsub $job
    fi
elif [ $coregister_add == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to coregister additional slaves to master scene not selected." 1>&2
    echo "" 1>&2
else
    :
fi




##########################   PROCESS ADDITIONAL INTERFEROGRAMS AND GEOCODE UNWRAPPED FILES   ##########################   


#### GA ####

if [ $do_add_ifms == yes -a $platform == GA ]; then
# create updated scenes and ifms.list file
    echo "Creating updated scene and interferogram list files..."
    create_ifms_list.bash $proj_dir/$proc_file
    echo "Creating interferograms..."
    echo " "
    while read list; do
	mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks
    done < $add_ifm_list
# consolidate ifm error logs into one file
    err_log=$err_dir/ifm_add_error.log
    echo "PROJECT: "$project"_"$sensor"_"$track_dir"_Additional_Interferogram_Error_Log" > $err_log
    echo " " >> $err_log
    echo " " >> $err_log
    while read ifm; do
	mas_slv_dir=$ifm_dir/$mas-$slv
	if [ ! -z $ifm ]; then
	    cd $mas_slv_dir
	    echo $mas-$slv >> $err_log
	    echo " " >> $err_log
	    less error.log >> $err_log
	fi
    done < $add_ifm_list
    echo " "
    echo "Processing additional interferograms complete."
    echo " "

# updated final baseline script
# plot_baseline_gamma.csh

elif [ $do_add_ifms == no -a $platform == GA ]; then
    echo " "
    echo "Option to create additional interferograms not selected."
    echo " "


#### NCI ####

elif [ $do_add_ifms == yes -a $platform == NCI ]; then
    echo "Creating additional interferograms..." 1>&2
    ifm_files=$proj_dir/$track_dir/add_ifm_files.list
    batch_dir=$proj_dir/$track_dir/batch_scripts
    cd $batch_dir/ifm_jobs
    mkdir -p add_ifm_jobs
    ifm_batch_dir=$batch_dir/ifm_jobs/add_ifm_jobs
    cd $ifm_batch_dir
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job arrays for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $ifm_batch_dir/$beam_num
		array_ids=$ifm_batch_dir/$beam_num/$beam_num"_array_jobids"
		depend_ids=$ifm_batch_dir/$beam_num/$beam_num"_depend_jobids"
		all_ids=$ifm_batch_dir/all_array_jobids
		sub_list=$beam_num"_subjob_list"
 		if [ -f $array_ids -o $depend_ids -o $all_ids ]; then
		    rm -rf $array_ids $depend_ids $all_ids
		else
		    :
		fi
                # create job_array for each list
		while read list; do
		    if [ ! -z $list ]; then
			tot_lines=`cat $proj_dir/$track_dir/$list | sed '/^\s*$/d' | wc -l`
			for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
			do
			    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
			    mkdir -p $array1
			    array_dir=$ifm_batch_dir/$beam_num/$array1
			    cd $array_dir
			    if [ -f $sub_list ]; then
				rm -rf $sub_list
			    fi
                            # create list of ifms with array number prefix
			    for ((l=1; l<=tot_lines; l++)); do 
				echo $l >> num_list
			    done
			    while read ifm_pair; do
				if [ ! -z $ifm_pair ]; then
				    mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
				    slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
				    echo $mas >> mas_list
				    echo $slv >> slv_list
				fi
			    done < $i 
			    paste num_list mas_list slv_list >> $sub_list
	                    # create subjobs (automatically uses the header details in the job_array script)
			    while read sublist; do
				if [ ! -z "${sublist}" ]; then
				    subjob=`echo $sublist | awk '{print $1}'`
				    mas=`echo $sublist | awk '{print $2}'`
				    slv=`echo $sublist | awk '{print $3}'`
				    script=$subjob
				    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num > $script
				    chmod +x $script
				fi
			    done < $sub_list
			    rm -rf num_list mas_list slv_list
			done
                        # make job_array PBS job
			array="array_"$array1
			if [ $tot_lines -eq 1 ]; then
			    num=1-2
			else
			    num=1-$tot_lines
			fi
			echo \#\!/bin/bash > $array
			echo \#\PBS -lother=gdata1 >> $array
			echo \#\PBS -l walltime=$ifm_walltime >> $array
			echo \#\PBS -l mem=$ifm_mem >> $array
			echo \#\PBS -l ncpus=$ifm_ncpus >> $array
			echo \#\PBS -l wd >> $array
			echo \#\PBS -q normal >> $array
			echo \#\PBS -r y >> $array
			echo \#\PBS -J $num >> $array
			echo \#\PBS -h >> $array
			if [ $coregister_add == yes -a $platform == NCI ]; then
			    add_co_slc_jobid=`sed s/.r-man2// $proj_dir/$track_dir/batch_scripts/slc_coreg_jobs/add_slc_coreg_jobs/$beam_num/"add_co_slc_"$beam_num"_job_id"`
			    echo \#\PBS -W depend=afterok:$add_co_slc_jobid >> $array
			else
			    :
			fi
			printf %s "$array_dir/$""PBS_ARRAY_INDEX" >> $array
			chmod +x $array
			qsub $array | tee job_id
			less job_id >> $array_ids
			less job_id >> $all_ids
			cd $ifm_batch_dir/$beam_num
		    fi
		done < $ifm_files
		cd $ifm_batch_dir/$beam_num
		
                # Release first job
		jobid=`awk 'NR==1 {print $1}' $array_ids | sed s/.r-man2//`
		qrls $jobid
		
                # Add dependencies if there is more than one job array. Adds to submitted jobs not job_array script.
		tot_files=`cat $ifm_files | sed '/^\s*$/d' | wc -l`
		if [ $tot_files -gt 1 ]; then
		    tail -n +2 $array_ids > temp1 # remove first jobid (no dependency)
		    head -n -1 $array_ids > temp2 # remove last jobid (no dependency)
		    paste temp1 temp2 >> $depend_ids
		    while read set; do
			jobid=`echo $set | awk '{print $1}' | sed s/.r-man2//`
			depend=`echo $set | awk '{print $2}' | sed s/.r-man2//`
			qalter -W depend=afterany:$depend $jobid
		    done < $depend_ids
	            # Release remaining jobs
		    while read job; do
			jobid=`echo $job | sed s/.r-man2//`
			qrls $jobid
		    done < temp1
		else
		    :
		fi
                # Clean up files
		rm -rf temp*
		
                # in case future manual processing is required, create manual PBS jobs for each ifm
		cd $batch_dir/ifm_jobs/manual_jobs
		while read list; do
		    for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
		    do
			array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
			array_dir=$ifm_batch_dir/$beam_num/$array1
			cd $array_dir
			while read ifm; do
			    mas=`echo $ifm | awk '{print $2}'`
			    slv=`echo $ifm | awk '{print $3}'`
			    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
			    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
			    script="ifm_"$beam_num"_"$mas_name-$slv_name
			    echo \#\!/bin/bash > $script
			    echo \#\PBS -lother=gdata1 >> $script
			    echo \#\PBS -l walltime=$ifm_walltime >> $script
			    echo \#\PBS -l mem=$ifm_mem >> $script
			    echo \#\PBS -l ncpus=$ifm_ncpus >> $script
			    echo \#\PBS -l wd >> $script
			    echo \#\PBS -q normal >> $script
			    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $script
			    chmod +x $script
			    mv $script $batch_dir/ifm_jobs/$beam_num/manual_jobs
			done < $sub_list
		    done
		done < $ifm_files
	
                # run ifm error check
		cd $ifm_batch_dir
		ifm_jobid=`awk 'END{print}' $array_ids | sed s/.r-man2//` # last job_array ID
		ifm_errors="add_ifm_"$beam_num"err_check"
		echo \#\!/bin/bash > $ifm_errors
		echo \#\PBS -lother=gdata1 >> $ifm_errors
		echo \#\PBS -l walltime=00:10:00 >> $ifm_errors
		echo \#\PBS -l mem=50MB >> $ifm_errors
		echo \#\PBS -l ncpus=1 >> $ifm_errors
		echo \#\PBS -l wd >> $ifm_errors
		echo \#\PBS -q normal >> $ifm_errors
		echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_errors
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 7 >> $ifm_errors
		chmod +x $ifm_errors
		qsub $ifm_errors
	    fi	
	done < $beam_list

        # run post ifm processing
	cd $ifm_batch_dir
	ifm_jobid=`awk 'END{print}' $array_ids | sed s/.r-man2//` # last job_array ID
	ifm_post=post_ifm_processing
	echo \#\!/bin/bash > $ifm_post
	echo \#\PBS -lother=gdata1 >> $ifm_post
	echo \#\PBS -l walltime=$raw_walltime >> $ifm_post
	echo \#\PBS -l mem=$raw_mem >> $ifm_post
	echo \#\PBS -l ncpus=$raw_ncpus >> $ifm_post
	echo \#\PBS -l wd >> $ifm_post
	echo \#\PBS -q normal >> $ifm_post
	echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_post
	echo ~/repo/gamma_bash/post_ifm_processing.bash $proj_dir/$proc_file 2 >> $ifm_post
	chmod +x $ifm_post
	qsub $ifm_post

        # mosaic beam interferograms
	num_beams=`wc -l < $beam_list`
	if [ $num_beams -gt 1 ]; then
	    ifm_jobid=`awk 'END{print}' $all_ids | sed s/.r-man2//` # last job_array ID from all beam processing
	    cd $ifm_batch_dir
	    mosaic=mosaic_beam_ifms
	    echo \#\!/bin/bash > $mosaic
	    echo \#\PBS -lother=gdata1 >> $mosaic
	    echo \#\PBS -l walltime=$ifm_walltime >> $mosaic
	    echo \#\PBS -l mem=$ifm_mem >> $mosaic
	    echo \#\PBS -l ncpus=$ifm_ncpus >> $mosaic
	    echo \#\PBS -l wd >> $mosaic
	    echo \#\PBS -q normal >> $mosaic
	    echo \#\PBS -W depend=afterok:$ifm_jobid >> $mosaic
	    echo ~/repo/gamma_bash/mosaic_beam_ifms.bash $proj_dir/$proc_file >> $mosaic
	    chmod +x $mosaic
#	    qsub $mosaic
	else
	    :
	fi
    else # no beam list
	cd $ifm_batch_dir
	array_ids=$ifm_batch_dir/array_jobids
	depend_ids=$ifm_batch_dir/depend_jobids
	sub_list=subjob_list
 	if [ -f $array_ids -o $depend_ids ]; then
	    rm -rf $array_ids $depend_ids
	else
	    :
	fi
	# create job_array for each list
	while read list; do
	    if [ ! -z $list ]; then
		tot_lines=`cat $proj_dir/$track_dir/$list | sed '/^\s*$/d' | wc -l`
		for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
		do
		    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
		    mkdir -p $array1
		    array_dir=$ifm_batch_dir/$array1
		    cd $array_dir
		    if [ -f $sub_list ]; then
			rm -rf $sub_list
		    fi
                    # create list of ifms with array number prefix
		    for ((l=1; l<=tot_lines; l++)); do 
			echo $l >> num_list
		    done
		    while read ifm_pair; do
			if [ ! -z $ifm_pair ]; then
			    mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
			    slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
			    echo $mas >> mas_list
			    echo $slv >> slv_list
			fi
		    done < $i 
		    paste num_list mas_list slv_list >> $sub_list
	            # create subjobs (automatically uses the header details in the job_array script)
		    while read sublist; do
			if [ ! -z "${sublist}" ]; then
			    subjob=`echo $sublist | awk '{print $1}'`
			    mas=`echo $sublist | awk '{print $2}'`
			    slv=`echo $sublist | awk '{print $3}'`
			    script=$subjob
			    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks > $script
			    chmod +x $script
			fi
		    done < $sub_list
		    rm -rf num_list mas_list slv_list
		done
                # make job_array PBS job
		array="array_"$array1
		if [ $tot_lines -eq 1 ]; then
		    num=1-2
		else
		    num=1-$tot_lines
		fi
		echo \#\!/bin/bash > $array
		echo \#\PBS -lother=gdata1 >> $array
		echo \#\PBS -l walltime=$ifm_walltime >> $array
		echo \#\PBS -l mem=$ifm_mem >> $array
		echo \#\PBS -l ncpus=$ifm_ncpus >> $array
		echo \#\PBS -l wd >> $array
		echo \#\PBS -q normal >> $array
		echo \#\PBS -r y >> $array
		echo \#\PBS -J $num >> $array
		echo \#\PBS -h >> $array
		if [ $coregister == yes -a $platform == NCI ]; then
		    add_co_slc_jobid=`sed s/.r-man2// $proj_dir/$track_dir/batch_scripts/slc_coreg_jobs/add_slc_coreg_jobs/add_co_slc_job_id`
		    echo \#\PBS -W depend=afterok:$add_co_slc_jobid >> $array
		else
		    :
		fi
		printf %s "$array_dir/$""PBS_ARRAY_INDEX" >> $array
		chmod +x $array
		qsub $array | tee job_id
		less job_id >> $array_ids
		cd $ifm_batch_dir
	    fi
	done < $ifm_files
	cd $ifm_batch_dir
	# Release first job
	jobid=`awk 'NR==1 {print $1}' $array_ids | sed s/.r-man2//`
	qrls $jobid
	# Add dependencies if there is more than one job array. Adds to submitted jobs not job_array script.
	tot_files=`cat $ifm_files | sed '/^\s*$/d' | wc -l`
	if [ $tot_files -gt 1 ]; then
	    tail -n +2 $array_ids > temp1 # remove first jobid (no dependency)
	    head -n -1 $array_ids > temp2 # remove last jobid (no dependency)
	    paste temp1 temp2 >> $depend_ids
	    while read set; do
		jobid=`echo $set | awk '{print $1}' | sed s/.r-man2//`
		depend=`echo $set | awk '{print $2}' | sed s/.r-man2//`
		qalter -W depend=afterany:$depend $jobid
	    done < $depend_ids
	    # Release remaining jobs
	    while read job; do
		jobid=`echo $job | sed s/.r-man2//`
		qrls $jobid
	    done < temp1
	else
	    :
	fi
        # Clean up files
	rm -rf temp*
        # in case future manual processing is required, create manual PBS jobs for each ifm
	cd $batch_dir/ifm_jobs/manual_jobs
	while read list; do
	    for i in $proj_dir/$track_dir/$list # eg. ifms.list_00
	    do
		array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
		array_dir=$ifm_batch_dir/$array1
		cd $array_dir
		while read ifm; do
		    mas=`echo $ifm | awk '{print $2}'`
		    slv=`echo $ifm | awk '{print $3}'`
		    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		    script="ifm_"$mas_name-$slv_name
		    echo \#\!/bin/bash > $script
		    echo \#\PBS -lother=gdata1 >> $script
		    echo \#\PBS -l walltime=$ifm_walltime >> $script
		    echo \#\PBS -l mem=$ifm_mem >> $script
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $script
		    echo \#\PBS -l wd >> $script
		    echo \#\PBS -q normal >> $script
		    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $script
		    chmod +x $script
		    mv $script $batch_dir/ifm_jobs/manual_jobs
		done < $sub_list
	    done
	done < $ifm_files

	# run ifm error check
	cd $batch_dir/ifm_jobs
	ifm_jobid=`awk 'END{print}' $array_ids | sed s/.r-man2//` # last job_array ID
	ifm_errors=add_ifm_err_check
	echo \#\!/bin/bash > $ifm_errors
	echo \#\PBS -lother=gdata1 >> $ifm_errors
	echo \#\PBS -l walltime=00:10:00 >> $ifm_errors
	echo \#\PBS -l mem=50MB >> $ifm_errors
	echo \#\PBS -l ncpus=1 >> $ifm_errors
	echo \#\PBS -l wd >> $ifm_errors
	echo \#\PBS -q normal >> $ifm_errors
	echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_errors
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file 7 >> $ifm_errors
	chmod +x $ifm_errors
	qsub $ifm_errors

	# run post ifm processing
	cd $batch_dir/ifm_jobs
	ifm_jobid=`awk 'END{print}' $array_ids | sed s/.r-man2//` # last job_array ID
	ifm_post=post_add_ifm_processing
	echo \#\!/bin/bash > $ifm_post
	echo \#\PBS -lother=gdata1 >> $ifm_post
	echo \#\PBS -l walltime=$raw_walltime >> $ifm_post
	echo \#\PBS -l mem=$raw_mem >> $ifm_post
	echo \#\PBS -l ncpus=$raw_ncpus >> $ifm_post
	echo \#\PBS -l wd >> $ifm_post
	echo \#\PBS -q normal >> $ifm_post
	echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_post
	echo ~/repo/gamma_bash/post_ifm_processing.bash $proj_dir/$proc_file 2 >> $ifm_post
	chmod +x $ifm_post
	qsub $ifm_post
    fi
elif [ $do_add_ifms == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create additional interferograms not selected." 1>&2
    echo "" 1>&2
else
    :
fi


##########################   RE-COREGISTER DEM WITH MODIFIED MULTI-LOOK VALUE   ##########################

#recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`




##########################   RE-COREGISTER SLAVE SCENES TO MASTER SCENE WITH MODIFIED MULTI-LOOK VALUE   ##########################

#recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`




##########################   RE-PROCESS INTERFEROGRAMS WITH MODIFIED MULTI-LOOK VALUE   ##########################

#recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`




##########################   CLEAN UP FILES   ##########################   






# script end 
####################



