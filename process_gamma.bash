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
    echo "* author: Sarah Lawrie @ GA       06/05/2015, v1.0                            *"
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

## Copy output of Gamma programs to log files
#GM()
#{
#    echo $* | tee -a command.log
#    echo
#    $* >> output.log 2> temp_log
#    cat temp_log >> error.log
    #cat output.log (option to add output results to NCI .o file if required)
#}

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
scene_list=$proj_dir/$track_dir/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
slave_list=$proj_dir/$track_dir/`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
ifm_list=$proj_dir/$track_dir/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`
add_scene_list=$proj_dir/$track_dir/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
add_slave_list=$proj_dir/$track_dir/`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`
add_ifm_list=$proj_dir/$track_dir/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`

## Determine range and azimuth looks
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
elif [ $sensor == PALSAR1 -o $sensor == PALSAR2 ]; then
    slc_rlks=$slc_looks 
    slc_alks=`echo $slc_looks | awk '{print $1*2}'` 
    ifm_rlks=$ifm_looks 
    ifm_alks=`echo $ifm_looks | awk '{print $1*2}'`
else
    # CSK, RSAT2, S1, TSX
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

## GA ##
if [ $do_slc == yes ]; then
    if [ $palsar1_data == raw -a $sensor == PALSAR1 ]; then
	sensor=PALSAR_L0 # PALSAR L1.0 script can process PALSAR1 raw data
    elif [ $palsar1_data == slc -a $sensor == PALSAR1 ]; then
	sensor=PALSAR_L1 # PALSAR L1.1 script can process both PALSAR1 and PALSAR2 slc level data
    elif [ $sensor == PALSAR2 ]; then
        sensor=PALSAR_L1
    else
	:
    fi
fi
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
    cd $proj_dir/$track_dir/batch_scripts
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
    qsub $slc_errors | tee slc_errors_job_id
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
    cd $proj_dir/$track_dir/batch_scripts
    slc_jobid=`sed s/.r-man2// slc_job_id`
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
	qsub $sub_dem | tee sub_dem_job_id
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
    cd $proj_dir/$track_dir/batch_scripts
    if [ -f sub_dem_job_id ]; then
	dem_jobid=`sed s/.r-man2// sub_dem_job_id`
    else
	dem_jobid=`sed s/.r-man2// dem_job_id`
    fi
    # set up header for PBS jobs for slave coregistration
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
    slc_errors=co_slc_err_check
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
    # PBS job for checking slave coregistration
    check_slc=check_slc_coreg
    echo \#\!/bin/bash > $check_slc
    echo \#\PBS -lother=gdata1 >> $check_slc
    echo \#\PBS -l walltime=00:10:00 >> $check_slc
    echo \#\PBS -l mem=50MB >> $check_slc
    echo \#\PBS -l ncpus=1 >> $check_slc
    echo \#\PBS -l wd >> $check_slc
    echo \#\PBS -q normal >> $check_slc
    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $check_slc
    echo ~/repo/gamma_bash/check_slave_coregistration.bash $proj_dir/$proc_file 1 >> $check_slc
    chmod +x $check_slc
    qsub $check_slc | tee check_co_slc_job_id
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
    check_co_slc_jobid=`sed s/.r-man2// check_co_slc_job_id`
    ifm_files=$proj_dir/$track_dir/ifm_files.list
    cd $proj_dir/$track_dir/batch_scripts
    # set up header for PBS jobs for ifm creation
    if [ ! -e $ifm_files ]; then ## 190 or less ifms
	while read ifm_pair; do
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
		    echo \#\PBS -W depend=afterok:$check_co_slc_jobid >> $ifm
		else
		    :
		fi
		echo ~/repo/gamma_bash/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $ifm
		chmod +x $ifm
#		qsub $ifm | ifm_job_id
	    fi
	done < $ifm_list
	ifm_jobid=`sed s/.r-man2// ifm_job_id`
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
	printf %s "qsub $""job | ifm_job_id" >> $script
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
	    echo \#\PBS -W depend=afterok:$check_co_slc_jobid >> $run_script
	else
	    :
	fi
	echo $proj_dir/$track_dir/batch_scripts/$first_list.bash >> $run_script
	chmod +x $run_script
#	qsub $run_script | tee $first_list"_job_id"
	# second list (ifm.list_01) ifms: 191 - 381
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
	    printf %s "qsub $""job | ifm_job_id" >> $script
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
	    echo \#\PBS -W depend=afterok:$first_list_jobid >> $run_script
	    echo $proj_dir/$track_dir/batch_scripts/$second_list.bash >> $run_script
	    chmod +x $run_script
#	    qsub $run_script | tee $second_list"_job_id"
	# third list (ifm.list_02) ifms: 382 - 570
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
	    printf %s "qsub $""job | ifm_job_id" >> $script
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
	    echo \#\PBS -W depend=afterok:$second_list_jobid >> $run_script
	    echo $proj_dir/$track_dir/batch_scripts/$third_list.bash >> $run_script
	    chmod +x $run_script
#	    qsub $run_script
	else
	    :
	fi
    if [ -f sub_dem_job_id ]; then
	dem_jobid=`sed s/.r-man2// sub_dem_job_id`
    else
	dem_jobid=`sed s/.r-man2// dem_job_id`
    fi


	ifm_jobid=`sed s/.r-man2// ifm_job_id`
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

    else
	:
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
	    echo \#\PBS -W depend=afterok:$add_raw_jobid >> $slc_script
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $slc_script
	    else
		echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $slc_script
		echo ~/repo/gamma_bash/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $slc_script
	    fi
	    chmod +x $slc_script
            qsub $slc_script | tee add_slc_job_id
	fi
    done < $add_scene_list
    slc_jobid=`sed s/.r-man2// add_slc_job_id`
    slc_errors=slc_err_check
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
    # set up header for PBS jobs for slave coregistration
    while read slave; do
	if [ ! -z $slave ]; then
	    co_slc=co_slc_$slave
	    echo \#\!/bin/bash > $co_slc
	    echo \#\PBS -lother=gdata1 >> $co_slc
	    echo \#\PBS -l walltime=$coreg_walltime >> $co_slc
	    echo \#\PBS -l mem=$coreg_mem >> $co_slc
	    echo \#\PBS -l ncpus=$coreg_ncpus >> $co_slc
	    echo \#\PBS -l wd >> $co_slc
	    echo \#\PBS -q normal >> $co_slc
	    if [ $add_slc == yes -a $platform == NCI ]; then
		echo \#\PBS -W depend=afterok:$add_slc_jobid >> $co_slc
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
#	    qsub $co_slc | tee add_co_slc_job_id
	else	
	    :
	fi
    done < $add_slave_list
    # PBS job for checking slave coregistration          ###### modify times etc with 1st check coregistration
    co_slc_jobid=`sed s/.r-man2// add_co_slc_job_id`
    check_slc=check_add_slc_coreg
    echo \#\!/bin/bash > $check_slc
    echo \#\PBS -lother=gdata1 >> $check_slc
    echo \#\PBS -l walltime=$coreg_walltime >> $check_slc
    echo \#\PBS -l mem=$coreg_mem >> $check_slc
    echo \#\PBS -l ncpus=$coreg_ncpus >> $check_slc
    echo \#\PBS -l wd >> $check_slc
    echo \#\PBS -q normal >> $check_slc
    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $check_slc
    echo ~/repo/gamma_bash/check_slave_coregistration.bash $proj_dir/$proc_file 2 >> $check_slc
    chmod +x $check_slc
#    qsub $check_slc | tee check_add_slc_job_id
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
    :
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





