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
    echo "* author: Sarah Lawrie @ GA       26/05/2015, v1.0                            *"
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
subset_done=`grep Subsetting_done= $proc_file | cut -d "=" -f 2`
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

##### SETUP PROJECT DIRECTORY STRUCTURE AND LISTS FOR PROCESSING #####

## GA ##
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
## NCI ###
elif [ $do_setup == yes -a $platform == NCI ]; then
    echo "Creating project directory structure..." 1>&2
    cd $proj_dir
    mkdir -p $track_dir # GAMMA processing directory
    mkdir -p $track_dir/batch_scripts # for PBS jobs
    mkdir -p $track_dir/batch_scripts/slc_jobs # for slc creation PBS jobs
    mkdir -p $track_dir/batch_scripts/dem_jobs # for dem PBS jobs
    mkdir -p $track_dir/batch_scripts/slc_coreg_jobs # for slc coregistration PBS jobs
    mkdir -p $track_dir/batch_scripts/ifm_jobs # for ifm job_array PBS jobs
    if [ -f $beam_list ]; then # if beams exist
	while read beam; do
	    mkdir -p $track_dir/batch_scripts/slc_jobs/$beam
	    mkdir -p $track_dir/batch_scripts/dem_jobs/$beam
	    mkdir -p $track_dir/batch_scripts/slc_coreg_jobs/$beam
	    mkdir -p $track_dir/batch_scripts/ifm_jobs/$beam
	    mkdir -p $track_dir/batch_scripts/ifm_jobs/$beam/manual_ifm_jobs # for manual ifm jobs
	done < $beam_list
    else # no beams
	mkdir -p $track_dir/batch_scripts/ifm_jobs/manual_ifm_jobs # for manual ifm jobs	
    fi
    mkdir -p raw_data # raw data directory
    mkdir -p raw_data/$track_dir
    if [ -f frame.list ]; then
	while read frame; do
	    if [ ! -z $frame ]; then # skips any empty lines
		mkdir -p raw_data/$track_dir/F$frame
	    fi
	done < frame.list
    else
	:
    fi
    if [ -f frame.list ]; then
	mv frame.list $track_dir
    else
	:
    fi
    if [ -f beam.list ]; then
	mv beam.list $track_dir
    else
	:
    fi

# create scenes.list file
    echo "Creating scenes list file..." 1>&2
    cd $proj_dir/$track_dir/batch_scripts
    sc_list=sc.list_gen
    echo \#\!/bin/bash > $sc_list
    echo \#\PBS -lother=gdata1 >> $sc_list
    echo \#\PBS -l walltime=$list_walltime >> $sc_list
    echo \#\PBS -l mem=$list_mem >> $sc_list
    echo \#\PBS -l ncpus=$list_ncpus >> $sc_list
    echo \#\PBS -l wd >> $sc_list
    echo \#\PBS -q copyq >> $sc_list
    echo ~/repo/gamma_bash/create_scenes_list.bash $proj_dir/$proc_file >> $sc_list
    chmod +x $sc_list
    qsub $sc_list | tee sc_list_job_id
# create slaves.list file
    echo "Creating slaves list file..." 1>&2
    sc_list_jobid=`sed s/.r-man2// sc_list_job_id`
    slv_list=slv.list_gen
    echo \#\!/bin/bash > $slv_list
    echo \#\PBS -lother=gdata1 >> $slv_list
    echo \#\PBS -l walltime=$list_walltime >> $slv_list
    echo \#\PBS -l mem=$list_mem >> $slv_list
    echo \#\PBS -l ncpus=$list_ncpus >> $slv_list
    echo \#\PBS -l wd >> $slv_list
    echo \#\PBS -q express >> $slv_list
    echo \#\PBS -W depend=afterok:$sc_list_jobid >> $slv_list
    echo ~/repo/gamma_bash/create_slaves_list.bash $proj_dir/$proc_file >> $slv_list
    chmod +x $slv_list
    qsub $slv_list
# create ifms.list file
    echo "Creating interferogram list file..." 1>&2
    ifm_list=ifm.list_gen
    echo \#\!/bin/bash > $ifm_list
    echo \#\PBS -lother=gdata1 >> $ifm_list
    echo \#\PBS -l walltime=$list_walltime >> $ifm_list
    echo \#\PBS -l mem=$list_mem >> $ifm_list
    echo \#\PBS -l ncpus=$list_ncpus >> $ifm_list
    echo \#\PBS -l wd >> $ifm_list
    echo \#\PBS -q express >> $ifm_list
    echo \#\PBS -W depend=afterok:$sc_list_jobid >> $ifm_list
    echo ~/repo/gamma_bash/create_ifms_list.bash $proj_dir/$proc_file >> $ifm_list
    chmod +x $ifm_list
    qsub $ifm_list
elif [ $do_setup == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to setup project directories and lists not selected." 1>&2
    echo "" 1>&2
else
    :
fi


##### EXTRACT RAW AND DEM DATA #####

## GA 
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
## NCI ##
if [ $do_raw == yes -a $platform == NCI ]; then
    echo "Extracting raw data..." 1>&2
    cd $proj_dir/$track_dir/batch_scripts
    raw=extract_raw 
    echo \#\!/bin/bash > $raw
    echo \#\PBS -lother=gdata1 >> $raw
    echo \#\PBS -l walltime=$raw_walltime >> $raw
    echo \#\PBS -l mem=$raw_mem >> $raw
    echo \#\PBS -l ncpus=$raw_ncpus >> $raw
    echo \#\PBS -l wd >> $raw
    echo \#\PBS -q copyq >> $raw
    if [ $do_setup == yes -a $platform == NCI ]; then # needs scene.list to be created first if it doesn't exist
	echo \#\PBS -W depend=afterok:$sc_list_jobid >> $raw
    else
	:
    fi
    echo ~/repo/gamma_bash/extract_raw_data.bash $proj_dir/$proc_file 0 >> $raw
    chmod +x $raw
    qsub $raw | tee raw_job_id
elif [ $do_raw == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to extract raw data not selected." 1>&2
    echo "" 1>&2

else
    :
fi


##### CREATE SLC DATA #####

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

## GA ##
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
## NCI ##
elif [ $do_slc == yes -a $platform == NCI ]; then
    echo "Creating SLC data..." 1>&2
    slcjob_dir=$proj_dir/$track_dir/batch_scripts/slc_jobs
    cd $slcjob_dir
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job script for each SLC per beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $beam_num
		while read scene; do
		    if [ ! -z $scene ]; then
			raw_jobid=`sed s/.r-man2// raw_job_id`
			slc_script=slc_$beam_num"_"$scene
			echo \#\!/bin/bash > $slc_script
			echo \#\PBS -lother=gdata1 >> $slc_script
			echo \#\PBS -l walltime=$slc_walltime >> $slc_script
			echo \#\PBS -l mem=$slc_mem >> $slc_script
			echo \#\PBS -l ncpus=$slc_ncpus >> $slc_script
			echo \#\PBS -l wd >> $slc_script
			echo \#\PBS -q normal >> $slc_script
			if [ $do_raw == yes -a $platform == NCI ]; then # needs raw data extracted first if it hasn't already
			    echo \#\PBS -W depend=afterok:$raw_jobid >> $slc_script
			else
			    :
			fi
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $slc_script
			else
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $slc_script
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $slc_script
			fi
			chmod +x $slc_script
			qsub $slc_script | tee "slc_"$beam_num"_job_id"
		    fi
		done < $scene_list
		slc_jobid=`sed s/.r-man2// "slc_"$beam_num"_job_id"`
		slc_errors="slcerr_"$beam_num"_check"
		echo \#\!/bin/bash > $slc_errors
		echo \#\PBS -lother=gdata1 >> $slc_errors
		echo \#\PBS -l walltime=00:10:00 >> $slc_errors
		echo \#\PBS -l mem=50MB >> $slc_errors
		echo \#\PBS -l ncpus=1 >> $slc_errors
		echo \#\PBS -l wd >> $slc_errors
		echo \#\PBS -q normal >> $slc_errors
		echo \#\PBS -W depend=afterok:$slc_jobid >> $slc_errors
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $slc_errors
		chmod +x $slc_errors
		qsub $slc_errors 
	    fi
	done < $beam_list
    else # no beams
        # set up and submit PBS job script for each SLC
	while read scene; do
	    if [ ! -z $scene ]; then
		raw_jobid=`sed s/.r-man2// raw_job_id`
		slc_script=slc_$scene
		echo \#\!/bin/bash > $slc_script
		echo \#\PBS -lother=gdata1 >> $slc_script
		echo \#\PBS -l walltime=$slc_walltime >> $slc_script
		echo \#\PBS -l mem=$slc_mem >> $slc_script
		echo \#\PBS -l ncpus=$slc_ncpus >> $slc_script
		echo \#\PBS -l wd >> $slc_script
		echo \#\PBS -q normal >> $slc_script
		if [ $do_raw == yes -a $platform == NCI ]; then # needs raw data extracted first if it hasn't already
		    echo \#\PBS -W depend=afterok:$raw_jobid >> $slc_script
		else
		    :
		fi
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $slc_script
		else
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $slc_script
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $slc_script
		fi
		chmod +x $slc_script
		qsub $slc_script | tee slc_job_id
	    fi
	done < $scene_list
	slc_jobid=`sed s/.r-man2// slc_job_id`
	slc_errors=slcerr_check
	echo \#\!/bin/bash > $slc_errors
	echo \#\PBS -lother=gdata1 >> $slc_errors
	echo \#\PBS -l walltime=00:10:00 >> $slc_errors
	echo \#\PBS -l mem=50MB >> $slc_errors
	echo \#\PBS -l ncpus=1 >> $slc_errors
	echo \#\PBS -l wd >> $slc_errors
	echo \#\PBS -q normal >> $slc_errors
	echo \#\PBS -W depend=afterok:$slc_jobid >> $slc_errors
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $slc_errors
	chmod +x $slc_errors
	qsub $slc_errors 
    fi
elif [ $do_slc == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create SLC data not selected." 1>&2
    echo "" 1>&2
else
    :
fi


##### COREGISTER DEM TO MASTER SCENE #####

## GA ##
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
## NCI ##
elif [ $coregister_dem == yes -a $platform == NCI ]; then
    echo "Coregistering DEM to master scene..." 1>&2
    demjob_dir=$proj_dir/$track_dir/batch_scripts/dem_jobs
    cd $demjob_dir
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job script for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $beam_num
		slc_jobid=`sed s/.r-man2// $slcjob_dir/"slc_"$beam_num"_job_id"`
		if [ $subset == yes -a $subset_done == notyet ]; then 
                    # no multi-look value - for geocoding full SLC and determining pixels for subsetting master scene
                    # set up header for PBS job
		    full_dem="coreg_"$beam_num"_full_dem"
		    echo \#\!/bin/bash > $full_dem
		    echo \#\PBS -lother=gdata1 >> $full_dem
		    echo \#\PBS -l walltime=$dem_walltime >> $full_dem
		    echo \#\PBS -l mem=$dem_mem >> $full_dem
		    echo \#\PBS -l ncpus=$dem_ncpus >> $full_dem
		    echo \#\PBS -l wd >> $full_dem
		    echo \#\PBS -q normal >> $full_dem
		    if [ $do_slc == yes -a $platform == NCI ]; then
			echo \#\PBS -W depend=afterok:$slc_jobid >> $full_dem
		    else
			:
		    fi
		    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 - - - - $beam_num >> $full_dem
		    chmod +x $full_dem
		    qsub $full_dem
		elif [ $subset == yes -a $subset_done == process ]; then 
		    echo "" 1>&2
		    echo "Subsetting master scene..." 1>&2
                    # set up header for PBS job
		    sub_dem="coreg_"$beam_num"_sub_dem"
		    echo \#\!/bin/bash > $sub_dem
		    echo \#\PBS -lother=gdata1 >> $sub_dem
		    echo \#\PBS -l walltime=$dem_walltime >> $sub_dem
		    echo \#\PBS -l mem=$dem_mem >> $sub_dem
		    echo \#\PBS -l ncpus=$dem_ncpus >> $sub_dem
		    echo \#\PBS -l wd >> $sub_dem
		    echo \#\PBS -q normal >> $sub_dem
                    # no multi-look value - for geocoding full subsetted SLC data
		    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 $roff $rlines $azoff $azlines $beam_num >> $sub_dem
                    # SLC and ifm multi-look value (same value)
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines $beam_num >> $sub_dem
		    else
                        # SLC multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines $beam_num >> $sub_dem
                        # ifm multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 1 $roff $rlines $azoff $azlines $beam_num >> $sub_dem
		    fi	  
		    chmod +x $sub_dem
		    qsub $sub_dem | tee "dem_"$beam_num"_job_id"
		elif [ $subset == no ]; then # no subsetting 
                    # no multi-look value - for geocoding full SLC data
                    # set up header for PBS job
		    dem="coreg_"$beam_num"_dem"
		    echo \#\!/bin/bash > $dem
		    echo \#\PBS -lother=gdata1 >> $dem
		    echo \#\PBS -l walltime=$dem_walltime >> $dem
		    echo \#\PBS -l mem=$dem_mem >> $dem
		    echo \#\PBS -l ncpus=$dem_ncpus >> $dem
		    echo \#\PBS -l wd >> $dem
		    echo \#\PBS -q normal >> $dem
		    if [ $do_slc == yes -a $platform == NCI ]; then
			echo \#\PBS -W depend=afterok:$slc_jobid >> $dem
		    else
			:
		    fi
                    # no multi-look value - for geocoding full SLC data
		    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 - - - - $beam_num >> $dem
                    # SLC and ifm multi-look value (same value)
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines $beam_num >> $dem
		    else
                        # SLC multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines $beam_num >> $dem
                        # ifm multi-look value
			echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 1 $roff $rlines $azoff $azlines $beam_num >> $dem
		    fi	  
		    chmod +x $dem
		    qsub $dem | tee "dem_"$beam_num"_job_id"
		else
		    :
		fi
		dem_jobid=`sed s/.r-man2// "dem_"$beam_num"_job_id"`
		dem_errors="demerr_"$beam_num"_check"
		echo \#\!/bin/bash > $dem_errors
		echo \#\PBS -lother=gdata1 >> $dem_errors
		echo \#\PBS -l walltime=00:10:00 >> $dem_errors
		echo \#\PBS -l mem=50MB >> $dem_errors
		echo \#\PBS -l ncpus=1 >> $dem_errors
		echo \#\PBS -l wd >> $dem_errors
		echo \#\PBS -q normal >> $dem_errors
		echo \#\PBS -W depend=afterok:$dem_jobid >> $dem_errors
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $dem_errors
		chmod +x $dem_errors
		qsub $dem_errors
	    fi
	done < $beam_list
    else # no beams
	slc_jobid=`sed s/.r-man2// $slcjob_dir/slc_job_id`
	if [ $subset == yes -a $subset_done == notyet ]; then 
            # no multi-look value - for geocoding full SLC and determining pixels for subsetting master scene
            # set up header for PBS job
	    full_dem=coreg_full_dem
	    echo \#\!/bin/bash > $full_dem
	    echo \#\PBS -lother=gdata1 >> $full_dem
	    echo \#\PBS -l walltime=$dem_walltime >> $full_dem
	    echo \#\PBS -l mem=$dem_mem >> $full_dem
	    echo \#\PBS -l ncpus=$dem_ncpus >> $full_dem
	    echo \#\PBS -l wd >> $full_dem
	    echo \#\PBS -q normal >> $full_dem
	    if [ $do_slc == yes -a $platform == NCI ]; then
		echo \#\PBS -W depend=afterok:$slc_jobid >> $full_dem
	    else
		:
	    fi
	    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 - - - - >> $full_dem
	    chmod +x $full_dem
	    qsub $full_dem
	elif [ $subset == yes -a $subset_done == process ]; then 
	    echo "" 1>&2
	    echo "Subsetting master scene..." 1>&2
            # set up header for PBS job
	    sub_dem=coreg_sub_dem
	    echo \#\!/bin/bash > $sub_dem
	    echo \#\PBS -lother=gdata1 >> $sub_dem
	    echo \#\PBS -l walltime=$dem_walltime >> $sub_dem
	    echo \#\PBS -l mem=$dem_mem >> $sub_dem
	    echo \#\PBS -l ncpus=$dem_ncpus >> $sub_dem
	    echo \#\PBS -l wd >> $sub_dem
	    echo \#\PBS -q normal >> $sub_dem
            # no multi-look value - for geocoding full subsetted SLC data
	    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 $roff $rlines $azoff $azlines >> $sub_dem
            # SLC and ifm multi-look value (same value)
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines >> $sub_dem
	    else
            # SLC multi-look value
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines >> $sub_dem
            # ifm multi-look value
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 1 $roff $rlines $azoff $azlines >> $sub_dem
	    fi	  
	    chmod +x $sub_dem
	    qsub $sub_dem | tee dem_job_id
	elif [ $subset == no ]; then # no subsetting 
            # no multi-look value - for geocoding full SLC data
            # set up header for PBS job
	    dem=coreg_dem
	    echo \#\!/bin/bash > $dem
	    echo \#\PBS -lother=gdata1 >> $dem
	    echo \#\PBS -l walltime=$dem_walltime >> $dem
	    echo \#\PBS -l mem=$dem_mem >> $dem
	    echo \#\PBS -l ncpus=$dem_ncpus >> $dem
	    echo \#\PBS -l wd >> $dem
	    echo \#\PBS -q normal >> $dem
	    if [ $do_slc == yes -a $platform == NCI ]; then
		echo \#\PBS -W depend=afterok:$slc_jobid >> $dem
	    else
		:
	    fi
            # no multi-look value - for geocoding full SLC data
	    echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 2 - - - - >> $dem
            # SLC and ifm multi-look value (same value)
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines >> $dem
	    else
            # SLC multi-look value
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 1 $roff $rlines $azoff $azlines >> $dem
            # ifm multi-look value
		echo ~/repo/gamma_bash/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 1 $roff $rlines $azoff $azlines >> $dem
	    fi	  
	    chmod +x $dem
	    qsub $dem | tee dem_job_id
	else
	    :
	fi
	dem_jobid=`sed s/.r-man2// dem_job_id`
	dem_errors=demerr_check
	echo \#\!/bin/bash > $dem_errors
	echo \#\PBS -lother=gdata1 >> $dem_errors
	echo \#\PBS -l walltime=00:10:00 >> $dem_errors
	echo \#\PBS -l mem=50MB >> $dem_errors
	echo \#\PBS -l ncpus=1 >> $dem_errors
	echo \#\PBS -l wd >> $dem_errors
	echo \#\PBS -q normal >> $dem_errors
	echo \#\PBS -W depend=afterok:$dem_jobid >> $dem_errors
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $dem_errors
	chmod +x $dem_errors
	qsub $dem_errors
    fi
elif [ $coregister_dem == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to coregister DEM to master scene not selected." 1>&2
    echo "" 1>&2

else
    :
fi


##### COREGISTER SLAVE SCENES TO MASTER SCENE #####

## GA ##
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
		coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks
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
		coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
# ifm multi-look value
		echo " "
		echo "Coregistering "$slave" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
		coregister_slave_SLC.bash $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks
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
## NCI ##
elif [ $coregister == yes -a $platform == NCI ]; then
    echo "Coregistering slave scenes to master scene..." 1>&2
    coslcjob_dir=$proj_dir/$track_dir/batch_scripts/coreg_slc_jobs
    cd $coslcjob_dir
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job script for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $beam_num
		dem_jobid=`sed s/.r-man2// $demjob_dir/"dem_"$beam_num"_job_id"`
		while read slave; do
		    if [ ! -z $slave ]; then
			co_slc="co_slc_"$beam_num"_"$slave
			echo \#\!/bin/bash > $co_slc
			echo \#\PBS -lother=gdata1 >> $co_slc
			echo \#\PBS -l walltime=$co_slc_walltime >> $co_slc
			echo \#\PBS -l mem=$co_slc_mem >> $co_slc
			echo \#\PBS -l ncpus=$co_slc_ncpus >> $co_slc
			echo \#\PBS -l wd >> $co_slc
			echo \#\PBS -q normal >> $co_slc
			if [ $coregister_dem == yes -a $platform == NCI ]; then
			    echo \#\PBS -W depend=afterok:$dem_jobid >> $co_slc
			else
			    :
			fi
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num>> $co_slc
			else
			    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num >> $co_slc
			    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks $beam_num >> $co_slc
			fi
			chmod +x $co_slc
			qsub $co_slc | tee "co_slc_"$beam_num"_job_id"
		    else	
			:
		    fi
		done < $slave_list
		co_slc_jobid=`sed s/.r-man2// "co_slc_"$beam_num"_job_id"`
		slc_errors="co_slcerr_"$beam_num"_check"
		echo \#\!/bin/bash > $slc_errors
		echo \#\PBS -lother=gdata1 >> $slc_errors
		echo \#\PBS -l walltime=00:10:00 >> $slc_errors
		echo \#\PBS -l mem=50MB >> $slc_errors
		echo \#\PBS -l ncpus=1 >> $slc_errors
		echo \#\PBS -l wd >> $slc_errors
		echo \#\PBS -q normal >> $slc_errors
		echo \#\PBS -W depend=afterok:$co_slc_jobid >> $slc_errors
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $slc_errors
		chmod +x $slc_errors
		qsub $slc_errors 
	    fi
	done < $beam_list
    else # no beams
	dem_jobid=`sed s/.r-man2// $demjob_dir/dem_job_id`
	while read slave; do
	    if [ ! -z $slave ]; then
		co_slc=co_slc_$slave
		echo \#\!/bin/bash > $co_slc
		echo \#\PBS -lother=gdata1 >> $co_slc
		echo \#\PBS -l walltime=$co_slc_walltime >> $co_slc
		echo \#\PBS -l mem=$co_slc_mem >> $co_slc
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $co_slc
		echo \#\PBS -l wd >> $co_slc
		echo \#\PBS -q normal >> $co_slc
		if [ $coregister_dem == yes -a $platform == NCI ]; then
		    echo \#\PBS -W depend=afterok:$dem_jobid >> $co_slc
		else
		    :
		fi
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks >> $co_slc
		else
		    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks >> $co_slc
		    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks >> $co_slc
		fi
		chmod +x $co_slc
		qsub $co_slc | tee co_slc_job_id
	    else	
		:
	    fi
	done < $slave_list
	co_slc_jobid=`sed s/.r-man2// co_slc_job_id`
	slc_errors=co_slcerr_check
	echo \#\!/bin/bash > $slc_errors
	echo \#\PBS -lother=gdata1 >> $slc_errors
	echo \#\PBS -l walltime=00:10:00 >> $slc_errors
	echo \#\PBS -l mem=50MB >> $slc_errors
	echo \#\PBS -l ncpus=1 >> $slc_errors
	echo \#\PBS -l wd >> $slc_errors
	echo \#\PBS -q normal >> $slc_errors
	echo \#\PBS -W depend=afterok:$co_slc_jobid >> $slc_errors
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $slc_errors
	chmod +x $slc_errors
	qsub $slc_errors 
    fi

    # PBS job for checking slave coregistration  - doesn't work, won't display window
#    check_slc=check_slc_coreg
#    echo \#\!/bin/bash > $check_slc
#    echo \#\PBS -lother=gdata1 >> $check_slc
#    echo \#\PBS -l walltime=00:10:00 >> $check_slc
#    echo \#\PBS -l mem=50MB >> $check_slc
#    echo \#\PBS -l ncpus=1 >> $check_slc
#    echo \#\PBS -l wd >> $check_slc
#    echo \#\PBS -q normal >> $check_slc
#    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $check_slc
#    echo ~/repo/gamma_bash/check_slave_coregistration.bash $proj_dir/$proc_file 1 >> $check_slc
#    chmod +x $check_slc
#    qsub $check_slc | tee check_co_slc_job_id
elif [ $coregister == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to coregister slaves to master scene not selected." 1>&2
    echo "" 1>&2
else
    :
fi

##### PROCESS INTERFEROGRAMS AND GEOCODE UNWRAPPED FILES #####

## GA ##
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
## NCI ##
elif [ $do_ifms == yes -a $platform == NCI ]; then
    echo "Creating interferograms..." 1>&2
    ifm_files=$proj_dir/$track_dir/ifm_files.list
    ifm_jobs=$proj_dir/$track_dir/batch_scripts/ifm_jobs
    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job arrays for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		co_slc_jobid=`sed s/.r-man2// $coslcjob_dir/"co_slc_"$beam_num"_job_id"`
		cd $ifm_jobs/$beam_num
		array_ids=$ifm_jobs/$beam_num/$beam_num"_array_jobids"
		depend_ids=$ifm_jobs/$beam_num/$beam_num"_depend_jobids"
		all_ids=$ifm_jobs/all_array_jobids
		sub_list=$beam_num"_subjob_list"
 		if [ -f $array_ids -o $depend_ids -o $all_ids ]; then
		    rm -rf $array_ids $depend_ids $all_ids
		else
		    :
		fi
                # create job_array for each list
		while read list; do
		    if [ ! -z $list ]; then
			tot_lines=`cat $list | sed '/^\s*$/d' | wc -l`
			for i in $list # eg. ifms.list_00
			do
			    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
			    mkdir -p $array1
			    array_dir=$ifm_jobs/$beam_num/$array1
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
				subjob=`echo $sublist | awk '{print $1}'`
				mas=`echo $sublist | awk '{print $2}'`
				slv=`echo $sublist | awk '{print $3}'`
				script=$subjob
				echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num > $script
				chmod +x $script
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
			    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $array
			else
			    :
			fi
			printf %s "$array_dir/$""PBS_ARRAY_INDEX" >> $array
			chmod +x $array
		    qsub $array | tee job_id
		    less job_id >> $array_ids
		    less job_id >> $all_ids
		    cd $ifm_jobs/$beam_num
		    fi
		done < $ifm_files
		cd $ifm_jobs/$beam_num
		
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
		cd $ifm_jobs/$beam_num/manual_ifm_jobs
		while read list; do
		    for i in $list # eg. ifms.list_00
		    do
			array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
			array_dir=$ifm_jobs/$beam_num/$array1
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
			    mv $script $ifm_jobs/$beam_num/manual_ifm_jobs
			done < $sub_list
		    done
		done < $ifm_files
	    fi
	done < $beam_list
        # run ifm errror check
	cd $ifm_jobs
	ifm_jobid=`awk 'END{print}' $array_ids | sed s/.r-man2//` # last job_array ID
	ifm_errors=ifm_err_check
	echo \#\!/bin/bash > $ifm_errors
	echo \#\PBS -lother=gdata1 >> $ifm_errors
	echo \#\PBS -l walltime=00:10:00 >> $ifm_errors
	echo \#\PBS -l mem=50MB >> $ifm_errors
	echo \#\PBS -l ncpus=1 >> $ifm_errors
	echo \#\PBS -l wd >> $ifm_errors
	echo \#\PBS -q normal >> $ifm_errors
	echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_errors
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $ifm_errors
	chmod +x $ifm_errors
#	qsub $ifm_errors
        # mosaic beam interferograms
	num_beams=`wc -l < $beam_list`
	if [ $num_beams -gt 1 ]; then
	    ifm_jobid=`awk 'END{print}' $all_ids | sed s/.r-man2//` # last job_array ID from all beam processing
	    cd $proj_dir/$track_dir/batch_scripts
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
	co_slc_jobid=`sed s/.r-man2// $coslcjob_dir/co_slc_job_id`
	cd $ifm_jobs
	array_ids=$ifm_jobs/array_jobids
	depend_ids=$ifm_jobs/depend_jobids
	sub_list=subjob_list
	if [ -f $array_ids -o $depend_ids ]; then
	    rm -rf $array_ids $depend_ids
	else
	    :
	fi
	# create job_array for each list
	while read list; do
	    if [ ! -z $list ]; then
		tot_lines=`cat $list | sed '/^\s*$/d' | wc -l`
		for i in $list # eg. ifms.list_00
		do
		    array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
		    mkdir -p $array1
		    array_dir=$ifm_jobs/$array1
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
			subjob=`echo $sublist | awk '{print $1}'`
			mas=`echo $sublist | awk '{print $2}'`
			slv=`echo $sublist | awk '{print $3}'`
			script=$subjob
			echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks > $script
			chmod +x $script
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
		    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $array
		else
		    :
		fi
		printf %s "$array_dir/$""PBS_ARRAY_INDEX" >> $array
		chmod +x $array
		qsub $array
		less job_id >> $array_ids
		cd $ifm_jobs
	    fi
	done < $ifm_files
	cd $ifm_jobs
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
	cd $ifm_jobs/manual_ifm_jobs
	while read list; do
	    for i in $list # eg. ifms.list_00
	    do
		array1=`echo $i | awk 'BEGIN {FS="."} ; {print $2}'`
		array_dir=$ifm_jobs/$array1
		cd $array_dir
		while read ifm; do
		    mas=`echo $ifm | awk '{print $2}'`
		    slv=`echo $ifm | awk '{print $3}'`
		    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		    script="ifm_"$mas_name-$slv_name
		    echo \#\!/bin/bash > $script
		    echo \#\PBS -lother=gdata1 >> $script
		    echo \#\PBS -l walltime=00:15:00 >> $script
		    echo \#\PBS -l mem=50MB >> $script
		    echo \#\PBS -l ncpus=1 >> $script
		    echo \#\PBS -l wd >> $script
		    echo \#\PBS -q normal >> $script
		    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $script
		    chmod +x $script
		    mv $script $ifm_jobs/manual_ifm_jobs
		done < $sub_list
	    done
	done < $ifm_files
	# run ifm errror check
	cd $ifm_jobs
	ifm_jobid=`awk 'END{print}' $array_ids | sed s/.r-man2//` # last job_array ID
	ifm_errors=ifm_err_check
	echo \#\!/bin/bash > $ifm_errors
	echo \#\PBS -lother=gdata1 >> $ifm_errors
	echo \#\PBS -l walltime=00:10:00 >> $ifm_errors
	echo \#\PBS -l mem=50MB >> $ifm_errors
	echo \#\PBS -l ncpus=1 >> $ifm_errors
	echo \#\PBS -l wd >> $ifm_errors
	echo \#\PBS -q normal >> $ifm_errors
	echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_errors
	echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $ifm_errors
	chmod +x $ifm_errors
#	qsub $ifm_errors
    fi
elif [ $do_ifms == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create interferograms not selected." 1>&2
    echo "" 1>&2
else
    :
fi



##### ADD NEW SLCS TO EXISTING SLC COLLECTION #####

## GA ##
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
elif [ $add_slc == yes -a $platform == NCI ]; then
    cd $proj_dir/$track_dir/batch_scripts
    # extract raw data
    add_raw=extract_add_raw 
    echo \#\!/bin/bash > $add_raw
    echo \#\PBS -lother=gdata1 >> $add_raw
    echo \#\PBS -l walltime=$raw_walltime >> $add_raw
    echo \#\PBS -l mem=$raw_mem >> $add_raw
    echo \#\PBS -l ncpus=$raw_ncpus >> $add_raw
    echo \#\PBS -l wd >> $add_raw
    echo \#\PBS -q copyq >> $add_raw
    echo ~/repo/gamma_bash/extract_raw_data.bash $proj_dir/$proc_file 1 >> $add_raw
    chmod +x $add_raw
    qsub $add_raw | tee add_raw_job_id
    # set up and submit PBS job script for each SLC

    if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job script for each SLC per beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		while read scene; do
		    if [ ! -z $scene ]; then
			add_raw_jobid=`sed s/.r-man2// add_raw_job_id`
			slc_script=slc_$beam_num"_"$scene
			echo \#\!/bin/bash > $slc_script
			echo \#\PBS -lother=gdata1 >> $slc_script
			echo \#\PBS -l walltime=$slc_walltime >> $slc_script
			echo \#\PBS -l mem=$slc_mem >> $slc_script
			echo \#\PBS -l ncpus=$slc_ncpus >> $slc_script
			echo \#\PBS -l wd >> $slc_script
			echo \#\PBS -q normal >> $slc_script
			if [ $do_raw == yes -a $platform == NCI ]; then # needs raw data extracted first if it hasn't already
			    echo \#\PBS -W depend=afterok:$raw_jobid >> $slc_script
			else
			    :
			fi
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $slc_script
			else
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $slc_script
			    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $slc_script
			fi
			chmod +x $slc_script
			qsub $slc_script | tee add_slc_job_id
		    fi
		done < $scene_list
	    fi
	done < $beam_list
    else # no beams
        # set up and submit PBS job script for each SLC
	while read scene; do
	    if [ ! -z $scene ]; then
		add_raw_jobid=`sed s/.r-man2// add_raw_job_id`
		slc_script=slc_$scene
		echo \#\!/bin/bash > $slc_script
		echo \#\PBS -lother=gdata1 >> $slc_script
		echo \#\PBS -l walltime=$slc_walltime >> $slc_script
		echo \#\PBS -l mem=$slc_mem >> $slc_script
		echo \#\PBS -l ncpus=$slc_ncpus >> $slc_script
		echo \#\PBS -l wd >> $slc_script
		echo \#\PBS -q normal >> $slc_script
		if [ $do_raw == yes -a $platform == NCI ]; then # needs raw data extracted first if it hasn't already
		    echo \#\PBS -W depend=afterok:$raw_jobid >> $slc_script
		else
		    :
		fi
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $slc_script
		else
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $slc_script
		    echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $slc_script
		fi
		chmod +x $slc_script
		qsub $slc_script | tee add_slc_job_id
	    fi
	done < $scene_list
    fi
    slc_jobid=`sed s/.r-man2// add_slc_job_id`
    slc_errors=slcerr_check
    echo \#\!/bin/bash > $slc_errors
    echo \#\PBS -lother=gdata1 >> $slc_errors
    echo \#\PBS -l walltime=00:10:00 >> $slc_errors
    echo \#\PBS -l mem=50MB >> $slc_errors
    echo \#\PBS -l ncpus=1 >> $slc_errors
    echo \#\PBS -l wd >> $slc_errors
    echo \#\PBS -q normal >> $slc_errors
    echo \#\PBS -W depend=afterok:$slc_jobid >> $slc_errors
    echo ~/repo/gamma_bash/collate_nci_slc_errors.bash $proj_dir/$proc_file >> $slc_errors
    chmod +x $slc_errors
    qsub $slc_errors | tee add_slc_errors_job_id
elif [ $add_slc == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create additional SLC data not selected." 1>&2
    echo "" 1>&2
else
    :
fi


##### COREGISTER ADDITIONAL SLAVE SCENES TO MASTER SCENE #####


## GA ##
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
		coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks
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
		coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks
		cd $slc_dir/$slave
		echo " " >> $err_log
		echo "Coregistering "$slave" with SLC "$slc_rlks" range and "$slc_alks" azimuth looks" >> $err_log
		less error.log >> $err_log
# ifm multi-look value
		echo "Coregistering "$slave" with ifm "$ifm_rlks" range and "$ifm_alks" azimuth looks..."
		coregister_slave_SLC.bash $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks
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
## NCI ##
elif [ $coregister_add == yes -a $platform == NCI ]; then
    cd $proj_dir/$track_dir
    cp add_scenes.list add_slaves.list
    cd $proj_dir/$track_dir/batch_scripts
    add_slc_jobid=`sed s/.r-man2// add_slc_errors_job_id`
    if [ -f $beam_list ]; then # if beam list exists
    # set up header for PBS jobs for slave coregistration
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		while read slave; do
		    if [ ! -z $slave ]; then
			co_slc="co_slc_"$beam_num"_"$slave
			echo \#\!/bin/bash > $co_slc
			echo \#\PBS -lother=gdata1 >> $co_slc
			echo \#\PBS -l walltime=$co_slc_walltime >> $co_slc
			echo \#\PBS -l mem=$co_slc_mem >> $co_slc
			echo \#\PBS -l ncpus=$co_slc_ncpus >> $co_slc
			echo \#\PBS -l wd >> $co_slc
			echo \#\PBS -q normal >> $co_slc
			if [ $coregister_dem == yes -a $platform == NCI ]; then
			    echo \#\PBS -W depend=afterok:$dem_jobid >> $co_slc
			else
			    :
			fi
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num>> $co_slc
			else
			    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks $beam_num >> $co_slc
			    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks $beam_num >> $co_slc
			fi
			chmod +x $co_slc
			qsub $co_slc | tee add_co_slc_job_id
		    else	
			:
		    fi
		done < $slave_list
	    fi
	done < $beam_list
    else # no beams
	while read slave; do
	    if [ ! -z $slave ]; then
		co_slc=co_slc_$slave
		echo \#\!/bin/bash > $co_slc
		echo \#\PBS -lother=gdata1 >> $co_slc
		echo \#\PBS -l walltime=$co_slc_walltime >> $co_slc
		echo \#\PBS -l mem=$co_slc_mem >> $co_slc
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $co_slc
		echo \#\PBS -l wd >> $co_slc
		echo \#\PBS -q normal >> $co_slc
		if [ $coregister_dem == yes -a $platform == NCI ]; then
		    echo \#\PBS -W depend=afterok:$dem_jobid >> $co_slc
		else
		    :
		fi
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks >> $co_slc
		else
		    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $slc_rlks $slc_alks >> $co_slc
		    echo ~/repo/gamma_bash/coregister_slave_SLC.bash $proj_dir/$proc_file $slave $ifm_rlks $ifm_alks >> $co_slc
		fi
		chmod +x $co_slc
		qsub $co_slc | tee add_co_slc_job_id
	    else	
		:
	    fi
	done < $add_slave_list
    fi
    co_slc_jobid=`sed s/.r-man2// add_co_slc_job_id`
    slc_errors=co_slcerr_check
    echo \#\!/bin/bash > $slc_errors
    echo \#\PBS -lother=gdata1 >> $slc_errors
    echo \#\PBS -l walltime=00:10:00 >> $slc_errors
    echo \#\PBS -l mem=50MB >> $slc_errors
    echo \#\PBS -l ncpus=1 >> $slc_errors
    echo \#\PBS -l wd >> $slc_errors
    echo \#\PBS -q normal >> $slc_errors
    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $slc_errors
    echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $slc_errors
    chmod +x $slc_errors
    qsub $slc_errors 


    # PBS job for checking slave coregistration          ###### modify times etc with 1st check coregistration
#    check_slc=check_add_slc_coreg
#    echo \#\!/bin/bash > $check_slc
#    echo \#\PBS -lother=gdata1 >> $check_slc
#    echo \#\PBS -l walltime=$coreg_walltime >> $check_slc
#    echo \#\PBS -l mem=$coreg_mem >> $check_slc
#    echo \#\PBS -l ncpus=$coreg_ncpus >> $check_slc
#    echo \#\PBS -l wd >> $check_slc
#    echo \#\PBS -q normal >> $check_slc
#    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $check_slc
#    echo ~/repo/gamma_bash/check_slave_coregistration.bash $proj_dir/$proc_file 2 >> $check_slc
#    chmod +x $check_slc
##    qsub $check_slc | tee check_add_slc_job_id
elif [ $coregister_add == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to coregister additional slaves to master scene not selected." 1>&2
    echo "" 1>&2
else
    :
fi


##### PROCESS ADDITIONAL INTERFEROGRAMS AND GEOCODE UNWRAPPED FILES #####

## GA ##
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
## NCI ##
elif [ $do_add_ifms == yes -a $platform == NCI ]; then
    echo "Creating interferograms..." 1>&2
    co_slc_jobid=`sed s/.r-man2// add_co_slc_job_id`
    ifm_files=$proj_dir/$track_dir/ifm_files.list
    cd $proj_dir/$track_dir/batch_scripts
    num_list=`wc -l < $ifm_files`
    if [ ! -e $file_files ]; then ## 190 or less ifms
	if [ -f $beam_list ]; then # if beam list exists
        # set up and submit PBS job script for each beam
	    while read beam_num; do
		while read ifm_pair; do
		    if [ ! -z $ifm_pair ]; then
			mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
			slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
			mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
			slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
			ifm="ifm_"$beam_num"_"$mas_name-$slv_name
			echo \#\!/bin/bash > $ifm
			echo \#\PBS -lother=gdata1 >> $ifm
			echo \#\PBS -l walltime=$ifm_walltime >> $ifm
			echo \#\PBS -l mem=$ifm_mem >> $ifm
			echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
			echo \#\PBS -l wd >> $ifm
			echo \#\PBS -q normal >> $ifm
			if [ $coregister == yes -a $platform == NCI ]; then
			    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $ifm
			else
			    :
			fi
			echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $ifm
			chmod +x $ifm
#			qsub $ifm | tee add_ifm_job_id
		    fi
		done < $ifm_list
		ifm_jobid=`sed s/.r-man2// add_ifm_job_id`
		ifm_errors=ifm_err_check
		echo \#\!/bin/bash > $ifm_errors
		echo \#\PBS -lother=gdata1 >> $ifm_errors
		echo \#\PBS -l walltime=00:15:00 >> $ifm_errors
		echo \#\PBS -l mem=50MB >> $ifm_errors
		echo \#\PBS -l ncpus=1 >> $ifm_errors
		echo \#\PBS -l wd >> $ifm_errors
		echo \#\PBS -q normal >> $ifm_errors
		echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_errors
		echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $ifm_errors
		chmod +x $ifm_errors
#		qsub $ifm_errors
		if [ -e $ifm_files ]; then # 191 or more ifms
	    # first list (ifm.list_00) ifms: 1 - 190
		    first_list=`awk 'NR==1 {print $1}' $ifm_files`
		    rm -rf $first_list"_"$beam_num"_jobs_listing"
		    while read ifm_pair; do # create PBS jobs for each ifm in first list
			if [ ! -z $ifm_pair ]; then
			    mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
			    slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
			    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
			    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
			    ifm="ifm_"$beam_num"_"$mas_name-$slv_name
			    echo \#\!/bin/bash > $ifm
			    echo \#\PBS -lother=gdata1 >> $ifm
			    echo \#\PBS -l walltime=$ifm_walltime >> $ifm
			    echo \#\PBS -l mem=$ifm_mem >> $ifm
			    echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
			    echo \#\PBS -l wd >> $ifm
			    echo \#\PBS -q normal >> $ifm
			    if [ $coregister == yes -a $platform == NCI ]; then
				echo \#\PBS -W depend=afterok:$co_slc_jobid >> $ifm
			    else
				:
			    fi
			    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $ifm
			    chmod +x $ifm
			    echo $ifm >> $first_list"_"$beam_num"_jobs_listing"
			fi
		    done < $proj_dir/$track_dir/$first_list
            # create script to qsub each PBS job
		    script=$first_list"_"$beam_num.bash 
		    printf '%s\n' "#!/bin/bash" > $script
		    printf '%s\n' "dir=$proj_dir/$track_dir/batch_scripts" >> $script
		    printf %s "list=$first_list"_jobs_listing"" >> $script
		    printf %s "cd $""dir" >> $script
		    printf '%s\n' "" >> $script
		    printf '%s\n' "while read job; do" >> $script
		    printf %s "qsub $""job | tee ifm1_job_id" >> $script
		    printf '%s\n' "" >> $script
		    printf %s "done < $""list" >> $script
		    chmod +x $script
            # create PBS job to run script
		    run_script=$first_list"_"$beam_num"_bulk"
		    echo \#\!/bin/bash > $run_script
		    echo \#\PBS -lother=gdata1 >> $run_script
		    echo \#\PBS -l walltime=$list_walltime >> $run_script
		    echo \#\PBS -l mem=$list_mem >> $run_script
		    echo \#\PBS -l ncpus=$list_ncpus >> $run_script
		    echo \#\PBS -l wd >> $run_script
		    echo \#\PBS -q express >> $run_script
		    if [ $coregister == yes -a $platform == NCI ]; then
			echo \#\PBS -W depend=afterok:$co_slc_jobid >> $run_script
		    else
			:
		    fi
		    echo $proj_dir/$track_dir/batch_scripts/$first_list >> $run_script
		    chmod +x $run_script
#	    qsub $run_script | tee $first_list"_add_job_id"
	    # second list (ifm.list_01) ifms: 191 - 381
		    ifm1_jobid=`sed s/.r-man2// ifm1_job_id`
		    second_list=`awk 'NR==2 {print $1}' $ifm_files`
		    if [ -e $proj_dir/$track_dir/$second_list ]; then
			first_list_jobid=`sed s/.r-man2// $first_list"_job_id"`
			rm -rf $second_list"_jobs_listing"
			while read ifm_pair; do # create PBS jobs for each ifm in second list
			    if [ ! -z $ifm_pair ]; then
				mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
				slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
				mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
				slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
				ifm=ifm_$mas_name-$slv_name
				echo \#\!/bin/bash > $ifm
				echo \#\PBS -lother=gdata1 >> $ifm
				echo \#\PBS -l walltime=$ifm_walltime >> $ifm
				echo \#\PBS -l mem=$ifm_mem >> $ifm
				echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
				echo \#\PBS -l wd >> $ifm
				echo \#\PBS -q normal >> $ifm
				echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $ifm
				chmod +x $ifm
				echo $ifm >> $second_list"_jobs_listing"
			    fi
			done < $proj_dir/$track_dir/$second_list
            # create script to qsub each PBS job
			script=$second_list.bash 
			printf '%s\n' "#!/bin/bash" > $script
			printf '%s\n' "dir=$proj_dir/$track_dir/batch_scripts" >> $script
			printf '%s\n' "list=$second_list"_jobs_listing"" >> $script
			printf %s "cd $""dir" >> $script
			printf '%s\n' "" >> $script
			printf '%s\n' "while read job; do" >> $script
			printf %s "qsub $""job | tee ifm2_job_id" >> $script
			printf '%s\n' "" >> $script
			printf %s "done < $""list" >> $script
			chmod +x $script
            # create PBS job to run script
			run_script=$second_list"_bulk"
			echo \#\!/bin/bash > $run_script
			echo \#\PBS -lother=gdata1 >> $run_script
			echo \#\PBS -l walltime=$list_walltime >> $run_script
			echo \#\PBS -l mem=$list_mem >> $run_script
			echo \#\PBS -l ncpus=$list_ncpus >> $run_script
			echo \#\PBS -l wd >> $run_script
			echo \#\PBS -q express >> $run_script
			echo \#\PBS -W depend=afterok:$ifm1_jobid >> $run_script
			echo $proj_dir/$track_dir/batch_scripts/$second_list.bash >> $run_script
			chmod +x $run_script
#		qsub $run_script | tee $second_list"_add_job_id"
	# third list (ifm.list_02) ifms: 382 - 570
			ifm2_jobid=`sed s/.r-man2// ifm2_job_id`
			third_list=`awk 'NR==3 {print $1}' $ifm_files`
		    elif [ -e $proj_dir/$track_dir/$third_list ]; then
			second_list_jobid=`sed s/.r-man2// $second_list"_job_id"`
			rm -rf $third_list"_jobs_listing"
			while read ifm_pair; do # create PBS jobs for each ifm in third list
			    if [ ! -z $ifm_pair ]; then
				mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
				slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
				mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
				slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
				ifm=ifm_$mas_name-$slv_name
				echo \#\!/bin/bash > $ifm
				echo \#\PBS -lother=gdata1 >> $ifm
				echo \#\PBS -l walltime=$ifm_walltime >> $ifm
				echo \#\PBS -l mem=$ifm_mem >> $ifm
				echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
				echo \#\PBS -l wd >> $ifm
				echo \#\PBS -q normal >> $ifm
				echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $ifm
				chmod +x $ifm
				paste $ifm >> $third_list"_jobs_listing"
			    fi
      			done < $proj_dir/$track_dir/$third_list
            # create script to qsub each PBS job
			script=$third_list.bash 
			printf '%s\n' "#!/bin/bash" > $script
			printf '%s\n' "dir=$proj_dir/$track_dir/batch_scripts" >> $script
			printf '%s\n' "list=$third_list"_jobs_listing"" >> $script
			printf %s "cd $""dir" >> $script
			printf '%s\n' "" >> $script
			printf '%s\n' "while read job; do" >> $script
			printf %s "qsub $""job | tee ifm3_job_id" >> $script
			printf '%s\n' "" >> $script
			printf %s "done < $""list" >> $script
			chmod +x $script
	    # create PBS job to run script
			run_script=$third_list"_bulk"
			echo \#\!/bin/bash > $run_script
			echo \#\PBS -lother=gdata1 >> $run_script
			echo \#\PBS -l walltime=$list_walltime >> $run_script
			echo \#\PBS -l mem=$list_mem >> $run_script
			echo \#\PBS -l ncpus=$list_ncpus >> $run_script
			echo \#\PBS -l wd >> $run_script
			echo \#\PBS -q express >> $run_script
			echo \#\PBS -W depend=afterok:$ifm2_jobid >> $run_script
			echo $proj_dir/$track_dir/batch_scripts/$third_list.bash >> $run_script
			chmod +x $run_script
#	    qsub $run_script | tee $third_list"_add_job_id"
		    else
			:
		    fi
		    if [ -f ifm3_job_id ]; then
			ifm_jobid=`sed s/.r-man2// ifm3_job_id`
		    else
			ifm_jobid=`sed s/.r-man2// ifm2_job_id`
		    fi
		else
		    :
		fi
	    done < $beam_list
	fi
    else # no beam list
	if [ ! -e $ifm_files ]; then ## 190 or less ifms
	    while read ifm_pair; do
		mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
		slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
		mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		ifm="ifm_"$mas_name-$slv_name
		echo \#\!/bin/bash > $ifm
		echo \#\PBS -lother=gdata1 >> $ifm
		echo \#\PBS -l walltime=$ifm_walltime >> $ifm
		echo \#\PBS -l mem=$ifm_mem >> $ifm
		echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
		echo \#\PBS -l wd >> $ifm
		echo \#\PBS -q normal >> $ifm
		if [ $coregister == yes -a $platform == NCI ]; then
		    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $ifm
		else
		    :
		fi
		echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $ifm
		chmod +x $ifm
		qsub $ifm | tee ifm_job_id
	    done < $ifm_list
	elif [ -e $ifm_files ]; then ## more than 190 ifms (ifms list split into multiple lists of 190 lots)
	# first list (ifm.list_00) ifms: 1 - 190
	    first_list=`awk 'NR==1 {print $1}' $ifm_files`
	    rm -rf $first_list"_jobs_listing"
	    while read ifm_pair; do # create PBS jobs for each ifm in first list
		if [ ! -z $ifm_pair ]; then
		    mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
		    slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
		    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		    ifm=ifm_$mas_name-$slv_name
		    echo \#\!/bin/bash > $ifm
		    echo \#\PBS -lother=gdata1 >> $ifm
		    echo \#\PBS -l walltime=$ifm_walltime >> $ifm
		    echo \#\PBS -l mem=$ifm_mem >> $ifm
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
		    echo \#\PBS -l wd >> $ifm
		    echo \#\PBS -q normal >> $ifm
		    if [ $coregister == yes -a $platform == NCI ]; then
			echo \#\PBS -W depend=afterok:$co_slc_jobid >> $ifm
		    else
			:
		    fi
		    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $ifm
		    chmod +x $ifm
		    echo $ifm >> $first_list"_jobs_listing"
		fi
	    done < $proj_dir/$track_dir/$first_list
        # create script to qsub each PBS job
	    script=$first_list.bash 
	    printf '%s\n' "#!/bin/bash" > $script
	    printf '%s\n' "dir=$proj_dir/$track_dir/batch_scripts" >> $script
	    printf '%s\n' "list=$first_list"_jobs_listing"" >> $script
	    printf %s "cd $""dir" >> $script
	    printf '%s\n' "" >> $script
	    printf '%s\n' "while read job; do" >> $script
	    printf %s "qsub $""job | tee ifm1_job_id" >> $script
	    printf '%s\n' "" >> $script
	    printf %s "done < $""list" >> $script
	    chmod +x $script
	# create PBS job to run script
	    run_script=$first_list"_bulk"
	    echo \#\!/bin/bash > $run_script
	    echo \#\PBS -lother=gdata1 >> $run_script
	    echo \#\PBS -l walltime=$list_walltime >> $run_script
	    echo \#\PBS -l mem=$list_mem >> $run_script
	    echo \#\PBS -l ncpus=$list_ncpus >> $run_script
	    echo \#\PBS -l wd >> $run_script
	    echo \#\PBS -q express >> $run_script
	    if [ $coregister == yes -a $platform == NCI ]; then
		echo \#\PBS -W depend=afterok:$co_slc_jobid >> $run_script
	    else
		:
	    fi
	    echo $proj_dir/$track_dir/batch_scripts/$first_list.bash >> $run_script
	    chmod +x $run_script
#	qsub $run_script | tee $first_list"_job_id"
	# second list (ifm.list_01) ifms: 191 - 381
	    ifm1_jobid=`sed s/.r-man2// ifm1_job_id`
	    second_list=`awk 'NR==2 {print $1}' $ifm_files`
	    if [ -e $proj_dir/$track_dir/$second_list ]; then
		first_list_jobid=`sed s/.r-man2// $first_list"_job_id"`
		rm -rf $second_list"_jobs_listing"
		while read ifm_pair; do # create PBS jobs for each ifm in second list
		if [ ! -z $ifm_pair ]; then
		    mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
		    slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
		    mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		    slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		    ifm=ifm_$mas_name-$slv_name
		    echo \#\!/bin/bash > $ifm
		    echo \#\PBS -lother=gdata1 >> $ifm
		    echo \#\PBS -l walltime=$ifm_walltime >> $ifm
		    echo \#\PBS -l mem=$ifm_mem >> $ifm
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
		    echo \#\PBS -l wd >> $ifm
		    echo \#\PBS -q normal >> $ifm
		    echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $ifm
		    chmod +x $ifm
		    echo $ifm >> $second_list"_jobs_listing"
		fi
	    done < $proj_dir/$track_dir/$second_list
            # create script to qsub each PBS job
		script=$second_list.bash 
		printf '%s\n' "#!/bin/bash" > $script
		printf '%s\n' "dir=$proj_dir/$track_dir/batch_scripts" >> $script
		printf '%s\n' "list=$second_list"_jobs_listing"" >> $script
		printf %s "cd $""dir" >> $script
		printf '%s\n' "" >> $script
		printf '%s\n' "while read job; do" >> $script
		printf %s "qsub $""job | tee ifm2_job_id" >> $script
	    printf '%s\n' "" >> $script
	    printf %s "done < $""list" >> $script
	    chmod +x $script
            # create PBS job to run script
	    run_script=$second_list"_bulk"
	    echo \#\!/bin/bash > $run_script
	    echo \#\PBS -lother=gdata1 >> $run_script
	    echo \#\PBS -l walltime=$list_walltime >> $run_script
	    echo \#\PBS -l mem=$list_mem >> $run_script
	    echo \#\PBS -l ncpus=$list_ncpus >> $run_script
	    echo \#\PBS -l wd >> $run_script
	    echo \#\PBS -q express >> $run_script
	    echo \#\PBS -W depend=afterok:$ifm1_jobid >> $run_script
	    echo $proj_dir/$track_dir/batch_scripts/$second_list.bash >> $run_script
	    chmod +x $run_script
#	    qsub $run_script | tee $second_list"_job_id"
	# third list (ifm.list_02) ifms: 382 - 570
	    ifm2_jobid=`sed s/.r-man2// ifm2_job_id`
	    third_list=`awk 'NR==3 {print $1}' $ifm_files`
	    elif [ -e $proj_dir/$track_dir/$third_list ]; then
		second_list_jobid=`sed s/.r-man2// $second_list"_job_id"`
		rm -rf $third_list"_jobs_listing"
		while read ifm_pair; do # create PBS jobs for each ifm in third list
		    if [ ! -z $ifm_pair ]; then
			mas=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $1}'`
			slv=`echo $ifm_pair | awk 'BEGIN {FS=","} ; {print $2}'`
			mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
			slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
			ifm=ifm_$mas_name-$slv_name
			echo \#\!/bin/bash > $ifm
			echo \#\PBS -lother=gdata1 >> $ifm
			echo \#\PBS -l walltime=$ifm_walltime >> $ifm
			echo \#\PBS -l mem=$ifm_mem >> $ifm
			echo \#\PBS -l ncpus=$ifm_ncpus >> $ifm
			echo \#\PBS -l wd >> $ifm
			echo \#\PBS -q normal >> $ifm
			echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $ifm
			chmod +x $ifm
			paste $ifm >> $third_list"_jobs_listing"
		    fi
      		done < $proj_dir/$track_dir/$third_list
            # create script to qsub each PBS job
		script=$third_list.bash 
		printf '%s\n' "#!/bin/bash" > $script
		printf '%s\n' "dir=$proj_dir/$track_dir/batch_scripts" >> $script
		printf '%s\n' "list=$third_list"_jobs_listing"" >> $script
		printf %s "cd $""dir" >> $script
		printf '%s\n' "" >> $script
		printf '%s\n' "while read job; do" >> $script
		printf %s "qsub $""job | tee ifm3_job_id" >> $script
		printf '%s\n' "" >> $script
		printf %s "done < $""list" >> $script
		chmod +x $script
	    # create PBS job to run script
		run_script=$third_list"_bulk"
		echo \#\!/bin/bash > $run_script
		echo \#\PBS -lother=gdata1 >> $run_script
		echo \#\PBS -l walltime=$list_walltime >> $run_script
		echo \#\PBS -l mem=$list_mem >> $run_script
		echo \#\PBS -l ncpus=$list_ncpus >> $run_script
		echo \#\PBS -l wd >> $run_script
		echo \#\PBS -q express >> $run_script
		echo \#\PBS -W depend=afterok:$ifm2_jobid >> $run_script
		echo $proj_dir/$track_dir/batch_scripts/$third_list.bash >> $run_script
		chmod +x $run_script
#	    qsub $run_script | tee $third_list"_job_id"
	    else
		:
	    fi
	    if [ -f ifm3_job_id ]; then
		ifm_jobid=`sed s/.r-man2// ifm3_job_id`
	    else
		ifm_jobid=`sed s/.r-man2// ifm2_job_id`
	    fi
	else
	    :
	fi
    fi
    ifm_errors=ifm_err_check
    echo \#\!/bin/bash > $ifm_errors
    echo \#\PBS -lother=gdata1 >> $ifm_errors
    echo \#\PBS -l walltime=00:10:00 >> $ifm_errors
    echo \#\PBS -l mem=50MB >> $ifm_errors
    echo \#\PBS -l ncpus=1 >> $ifm_errors
    echo \#\PBS -l wd >> $ifm_errors
    echo \#\PBS -q normal >> $ifm_errors
    echo \#\PBS -W depend=afterok:$ifm_jobid >> $ifm_errors
    echo ~/repo/gamma_bash/collate_nci_errors.bash $proj_dir/$proc_file >> $ifm_errors
    chmod +x $ifm_errors
#    qsub $ifm_errors
elif [ $do_add_ifms == no -a $platform == NCI ]; then
    echo "" 1>&2
    echo "Option to create additional interferograms not selected." 1>&2
    echo "" 1>&2
else
    :
fi


##### RE-COREGISTER DEM WITH MODIFIED MULTI-LOOK VALUE #####

#recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`




##### RE-COREGISTER SLAVE SCENES TO MASTER SCENE WITH MODIFIED MULTI-LOOK VALUE #####

#recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`




##### RE-PROCESS INTERFEROGRAMS WITH MODIFIED MULTI-LOOK VALUE #####

#recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`




##### CLEAN UP FILES #####






# script end 
####################

## Copy errors to NCI error file (.e file)
#if [ $platform == NCI ]; then
#   cat error.log 1>&2
#   rm temp_log
#else
#   :
#fi





