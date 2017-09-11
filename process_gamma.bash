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
    echo "*         Sarah Lawrie @ GA       18/06/2015, v1.3                            *"
    echo "*             - streamline auto processing and modify directory structure     *"
    echo "*         Sarah Lawrie @ GA       15/07/2015, v1.4                            *"
    echo "*             - streamline auto processing                                    *"
    echo "*         Sarah Lawrie @ GA       16/07/2015, v1.5                            *"
    echo "*             - modify coregister DEM to include external ref image           *"
    echo "*         Sarah Lawrie @ GA       29/01/2016, v1.6                            *"
    echo "*             - add ability to extract S1 data from the RDSI                  *"
    echo "*         Sarah Lawrie @ GA       28/07/2016, v1.7                            *"
    echo "*             - Add option to subset Sentinel-1 SLCs                          *"
    echo "*             - Add use of precise orbit download for Sentinel-1              *"
    echo "*         Thomas Fuhrmann @ GA    21/10/2016, v1.8                            *"
    echo "*             - corrected bug in sensor selection for ASAR/ERS                *"
    echo "*             - added query on ASAR mode for different alks value for I4      *"
    echo "*             - corrected two minor bugs: scene_list2=$proj_dir/... grep      *"
    echo "*                                         dem_jobid=sed in SUBSET_DEM()       *"
    echo "*         Sarah Lawrie @ GA       08/09/2017, v1.9                            *"
    echo "*             -  update to include cropping of Sentinel-1 to enable scenes    *"
    echo "*                to be same size and shape (auto crop)                        *"
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
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
mode=`grep Sensor_mode= $proc_file | cut -d "=" -f 2`
do_setup=`grep Setup= $proc_file | cut -d "=" -f 2`
do_raw=`grep Do_raw_data= $proc_file | cut -d "=" -f 2`
do_slc=`grep Do_SLC= $proc_file | cut -d "=" -f 2`
do_auto_crop=`grep Do_auto_crop= $proc_file | cut -d "=" -f 2`
ref_scene=`grep Ref_scene= $proc_file | cut -d "=" -f 2`
do_slc_subset=`grep Do_SLC_subset= $proc_file | cut -d "=" -f 2`
coregister_dem=`grep Coregister_DEM= $proc_file | cut -d "=" -f 2`
coregister=`grep Coregister_slaves= $proc_file | cut -d "=" -f 2`
do_ifms=`grep Process_ifms= $proc_file | cut -d "=" -f 2`
add_scenes=`grep Add_scenes_setup= $proc_file | cut -d "=" -f 2`
add_slc=`grep Add_SLC= $proc_file | cut -d "=" -f 2`
recoregister_dem=`grep Re-coregister_DEM= $proc_file | cut -d "=" -f 2`
coregister_add=`grep Coregister_add_slaves= $proc_file | cut -d "=" -f 2`
add_ifms=`grep Process_add_ifms= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
frame_list=`grep List_of_frames= $proc_file | cut -d "=" -f 2`
beam_list=`grep List_of_beams= $proc_file | cut -d "=" -f 2`
s1_list=`grep S1_file_list= $proc_file | cut -d "=" -f 2`
ext_image=`grep Landsat_image= $proc_file | cut -d "=" -f 2`
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
error_walltime=`grep error_walltime= $proc_file | cut -d "=" -f 2`
error_mem=`grep error_mem= $proc_file | cut -d "=" -f 2`
error_ncpus=`grep error_ncpus= $proc_file | cut -d "=" -f 2`
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
mosaic_walltime=`grep mosaic_walltime= $proc_file | cut -d "=" -f 2`
mosaic_mem=`grep mosaic_mem= $proc_file | cut -d "=" -f 2`
mosaic_ncpus=`grep mosaic_ncpus= $proc_file | cut -d "=" -f 2`
post_walltime=`grep post_walltime= $proc_file | cut -d "=" -f 2`
post_mem=`grep post_mem= $proc_file | cut -d "=" -f 2`
post_ncpus=`grep post_ncpus= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
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
echo "PROCESSING PROJECT: "$project $track_dir 1>&2
echo "" 1>&2

## Insert scene details top of NCI .o file
echo ""
echo ""
echo "PROCESSING PROJECT: "$project $track_dir
echo ""

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


## Determine range and azimuth looks for 'square' pixels
if [ $sensor == ASAR -o $sensor == ERS ]; then
    slc_rlks=$slc_looks
    ifm_rlks=$ifm_looks
    if [ $mode == I4 -o $mode == I7 ]; then
       slc_alks=`echo $slc_looks | awk '{print $1*3}'`
       ifm_alks=`echo $ifm_looks | awk '{print $1*3}'`
    elif [ $mode == I1 ]; then
       slc_alks=`echo $slc_looks | awk '{print $1*6}'`
       ifm_alks=`echo $ifm_looks | awk '{print $1*6}'`
    else
       slc_alks=`echo $slc_looks | awk '{print $1*5}'`
       ifm_alks=`echo $ifm_looks | awk '{print $1*5}'`
    fi
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
elif [ $sensor == RSAT2 ]; then
    if [ $mode == W ]; then
       slc_rlks=$slc_looks
       slc_alks=`echo $slc_looks | awk '{print $1*4}'`
       ifm_rlks=$ifm_looks
       ifm_alks=`echo $ifm_looks | awk '{print $1*4}'`
    elif [ $mode == F -a $slc_looks -gt 1 -a $ifm_looks -gt 1 ]; then
       slc_rlks=$slc_looks
       slc_alks=`echo $slc_looks | awk '{print $1/2*3}'`
       ifm_rlks=$ifm_looks
       ifm_alks=`echo $ifm_looks | awk '{print $1/2*3}'`
    else
       slc_rlks=$slc_looks
       slc_alks=$slc_looks
       ifm_rlks=$ifm_looks
       ifm_alks=$ifm_looks
    fi
elif [ $sensor == S1 -a $mode == IWS ]; then
    slc_alks=$slc_looks
    slc_rlks=`echo $slc_looks | awk '{print $1*5}'`
    ifm_alks=$ifm_looks
    ifm_rlks=`echo $ifm_looks | awk '{print $1*5}'`
elif [ $sensor == PALSAR1 -o $sensor == PALSAR2 ]; then
    slc_rlks=$slc_looks
    slc_alks=`echo $slc_looks | awk '{print $1*2}'`
    ifm_rlks=$ifm_looks
    ifm_alks=`echo $ifm_looks | awk '{print $1*2}'`
elif [ $sensor == CSK ]; then
    if [ $mode == HI ]; then
	if [ $slc_looks -eq 1 ]; then  #cannot have square pixels for himage data processed at full res
	    slc_rlks=$slc_looks
	    slc_alks=$slc_looks
	    ifm_rlks=$ifm_looks
	    ifm_alks=$ifm_looks
	else
	    slc_rlks=$slc_looks
	    slc_alks=`echo $slc_looks | awk '{print $1*1.5}'`
	    ifm_rlks=$ifm_looks
	    ifm_alks=`echo $ifm_looks | awk '{print $1*1.5}'`
	fi
    elif [ $mode == SP ]; then
	slc_rlks=$slc_looks
	slc_alks=$slc_looks
	ifm_rlks=$ifm_looks
	ifm_alks=$ifm_looks
    fi
else
    # TSX, S1_SM
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

    cd $proj_dir

    # if re rerunning process_gamma.bash after lists have been created
    auto=process_$track_dir"_"*"auto_rerun"
    if [ ! -f $auto ]; then

# make directories
	echo "Creating directories..."
	mkdir -p $track_dir
	mkdir -p $track_dir/error_results
	mkdir -p $track_dir/lists

# move lists if they exist
	frame_list=`grep List_of_frames= $proc_file | cut -d "=" -f 2`
	beam_list=`grep List_of_beams= $proc_file | cut -d "=" -f 2`

	if [ -f $frame_list ]; then
	    mv $frame_list $track_dir/lists/$frame_list
	    dos2unix -q $frame_list $frame_list # remove any DOS characters if list created in Windows
	    frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`
	else
	    echo "No frame list found, assume dataset has no frames." 1>&2
	fi
	if [ -f $beam_list ]; then
	    mv $beam_list $track_dir/lists/$beam_list
	    dos2unix -q $beam_list $beam_list # remove any DOS characters if list created in Windows
	    beam_list=$proj_dir/$track_dir/lists/`grep List_of_beams= $proc_file | cut -d "=" -f 2`
	else
	    echo "No beam list found, assume dataset has no beams." 1>&2
	fi
	if [ -f $s1_list ]; then
	    mv $s1_list $track_dir/lists/$s1_list
	    dos2unix -q $s1_list $s1_list # remove any DOS characters if list created in Windows
	    s1_list=$proj_dir/$track_dir/lists/`grep S1_rdsi_files= $proc_file | cut -d "=" -f 2`
	else
	    echo "No Sentinel-1 file list found, assume dataset is not Sentinel-1." 1>&2
	fi

	if [ -f $beam_list ]; then # if beams exist
	    while read beam_num; do
		mkdir -p $track_dir/batch_jobs
		mkdir -p $track_dir/batch_jobs/slc_jobs
		mkdir -p $track_dir/batch_jobs/dem_jobs
		mkdir -p $track_dir/batch_jobs/slc_coreg_jobs
		mkdir -p $track_dir/batch_jobs/ifm_jobs
		mkdir -p $track_dir/batch_jobs/slc_jobs/$beam_num
		mkdir -p $track_dir/batch_jobs/dem_jobs/$beam_num
		mkdir -p $track_dir/batch_jobs/slc_coreg_jobs/$beam_num
		mkdir -p $track_dir/batch_jobs/ifm_jobs/$beam_num
		mkdir -p $track_dir/manual_jobs
		mkdir -p $track_dir/manual_jobs/slc_jobs
		mkdir -p $track_dir/manual_jobs/dem_jobs
		mkdir -p $track_dir/manual_jobs/slc_coreg_jobs
		mkdir -p $track_dir/manual_jobs/ifm_jobs
		mkdir -p $track_dir/manual_jobs/slc_jobs/$beam_num
		mkdir -p $track_dir/manual_jobs/dem_jobs/$beam_num
		mkdir -p $track_dir/manual_jobs/slc_coreg_jobs/$beam_num
		mkdir -p $track_dir/manual_jobs/ifm_jobs/$beam_num
	    done < $beam_list
	else # no beam
	    mkdir -p $track_dir/batch_jobs
	    mkdir -p $track_dir/batch_jobs/slc_jobs
	    mkdir -p $track_dir/batch_jobs/dem_jobs
	    mkdir -p $track_dir/batch_jobs/slc_coreg_jobs
	    mkdir -p $track_dir/batch_jobs/ifm_jobs
	    mkdir -p $track_dir/manual_jobs
	    mkdir -p $track_dir/manual_jobs/slc_jobs
	    mkdir -p $track_dir/manual_jobs/dem_jobs
	    mkdir -p $track_dir/manual_jobs/slc_coreg_jobs
	    mkdir -p $track_dir/manual_jobs/ifm_jobs
	fi


# raw data directories
	mkdir -p raw_data
	mkdir -p raw_data/$track_dir
	if [ -f $frame_list ]; then
	    while read frame; do
		if [ ! -z $frame ]; then # skips any empty lines
		    mkdir -p raw_data/$track_dir/F$frame
		fi
	    done < $frame_list
	else
	    :
	fi

	scene_list2=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`

	batch_dir=$proj_dir/$track_dir/batch_jobs
	cd $batch_dir

	if [ ! -f $scene_list2 ]; then # if scene list doesn't exist
        # create scenes.list file
	    echo "Creating scenes list file..."
	    job1=scene_list_gen
	    echo \#\!/bin/bash > $job1
	    echo \#\PBS -lother=gdata1 >> $job1
	    echo \#\PBS -l walltime=$list_walltime >> $job1
	    echo \#\PBS -l mem=$list_mem >> $job1
	    echo \#\PBS -l ncpus=$list_ncpus >> $job1
	    echo \#\PBS -l wd >> $job1
	    echo \#\PBS -q copyq >> $job1
	    echo ~/repo/gamma_insar/create_scenes_list.bash $proj_dir/$proc_file 1 >> $job1
	    chmod +x $job1
	    qsub $job1 | tee scene_list_job_id

        # create slaves.list file
	    echo "Creating slaves list file..."
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
	    echo ~/repo/gamma_insar/create_slaves_list.bash $proj_dir/$proc_file 1 >> $job2
	    chmod +x $job2
	    qsub $job2 | tee slave_list_job_id

        # create ifms.list file
	    echo "Creating interferogram list file..."
	    job3=ifm_list_gen
	    echo \#\!/bin/bash > $job3
	    echo \#\PBS -lother=gdata1 >> $job3
	    echo \#\PBS -l walltime=$list_walltime >> $job3
	    echo \#\PBS -l mem=$list_mem >> $job3
	    echo \#\PBS -l ncpus=$list_ncpus >> $job3
	    echo \#\PBS -l wd >> $job3
	    echo \#\PBS -q normal >> $job3
	    echo \#\PBS -W depend=afterok:$scene_list_jobid >> $job3
	    echo ~/repo/gamma_insar/create_ifms_list.bash $proj_dir/$proc_file 1 >> $job3
	    chmod +x $job3
	    qsub $job3 | tee ifm_list_job_id

        # run setup error check
	    echo "Preparing error collation for 'do_setup'..."
	    cd $batch_dir
	    slave_list_jobid=`sed s/.r-man2// slave_list_job_id`
	    ifm_list_jobid=`sed s/.r-man2// ifm_list_job_id`
	    job=setup_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$scene_list_jobid:$slave_list_jobid:$ifm_list_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 1 >> $job
	    chmod +x $job
	    qsub $job
	else # scene list exists
	    :
	fi
    else
	:
    fi
elif [ $do_setup == no -a $platform == NCI ]; then
    echo ""
    echo "Option to setup project directories and lists not selected."
    echo ""
else
    :
fi

cd $proj_dir

frame_list=$proj_dir/$track_dir/lists/`grep List_of_frames= $proc_file | cut -d "=" -f 2`
beam_list=$proj_dir/$track_dir/lists/`grep List_of_beams= $proc_file | cut -d "=" -f 2`
subset_file=$proj_dir/$track_dir/lists/`grep Subset_file= $proc_file | cut -d "=" -f 2`
scene_list=$proj_dir/$track_dir/lists/`grep List_of_scenes= $proc_file | cut -d "=" -f 2`
slave_list=$proj_dir/$track_dir/lists/`grep List_of_slaves= $proc_file | cut -d "=" -f 2`
ifm_list=$proj_dir/$track_dir/lists/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`

add_scene_list=$proj_dir/$track_dir/lists/`grep List_of_add_scenes= $proc_file | cut -d "=" -f 2`
add_slave_list=$proj_dir/$track_dir/lists/`grep List_of_add_slaves= $proc_file | cut -d "=" -f 2`
add_ifm_list=$proj_dir/$track_dir/lists/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`

batch_dir=$proj_dir/$track_dir/batch_jobs
manual_dir=$proj_dir/$track_dir/manual_jobs




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

    cd $batch_dir
    if [ -f extract_raw_dat.e* ]; then # if raw already been run
	:
    else
	echo ""
	echo "Extracting raw data..."
	cd $batch_dir
	job=extract_raw_data
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=$raw_walltime >> $job
	echo \#\PBS -l mem=$raw_mem >> $job
	echo \#\PBS -l ncpus=$raw_ncpus >> $job
	echo \#\PBS -l wd >> $job
	if [ $sensor == S1 ]; then
	    echo \#\PBS -q normal >> $job
	else
	    echo \#\PBS -q copyq >> $job
	fi
	if [ $do_setup == yes -a $platform == NCI ]; then
	    scene_list_jobid=`sed s/.r-man2// scene_list_job_id`
	    slave_list_jobid=`sed s/.r-man2// slave_list_job_id`
	    ifm_list_jobid=`sed s/.r-man2// ifm_list_job_id`
	    echo \#\PBS -W depend=afterok:$scene_list_jobid:$slave_list_jobid:$ifm_list_jobid >> $job
	else
	    :
	fi
	echo ~/repo/gamma_insar/extract_raw_data.bash $proj_dir/$proc_file 0 >> $job
	chmod +x $job
	qsub $job | tee raw_job_id

# run raw extraction error check
	cd $batch_dir
	echo "Preparing error collation for 'do_raw'..."
	raw_jobid=`sed s/.r-man2// raw_job_id`
	job=raw_err_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=$error_walltime >> $job
	echo \#\PBS -l mem=$error_mem >> $job
	echo \#\PBS -l ncpus=$error_ncpus >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterany:$raw_jobid >> $job
	echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 2 >> $job
	chmod +x $job
	qsub $job | tee raw_err_job_id
    fi

elif [ $do_raw == no -a $platform == NCI ]; then
    echo ""
    echo "Option to extract raw data not selected."
    echo ""

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
    cd $batch_dir
    slc_batch_dir=$batch_dir/slc_jobs
    slc_manual_dir=$manual_dir/slc_jobs

    # Maximum number of jobs to be run (no more than 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a single process_slc in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_job_prefix=slc_

    if [ -f $beam_list ]; then # if beam list exists
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $slc_batch_dir/$beam_num
		if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes ]; then
		    if [ ! -e $scene_list ]; then # if scene list doesn't exist
			echo ""
			echo "Scene list doesn't exist yet, preparing to rerun process_gamma.bash after list is created to create SLCs..."
		        # rerun process_gamma.bash once do setup and do raw are finished
			cd $proj_dir
			raw_jobid=`sed s/.r-man2// $batch_dir/raw_job_id`
			job=process_$track_dir"_"$beam_num"_auto_rerun"
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$list_walltime >> $job
			echo \#\PBS -l mem=$list_mem >> $job
			echo \#\PBS -l ncpus=$list_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			echo \#\PBS -W depend=afterok:$raw_jobid >> $job
			echo ~/repo/gamma_insar/process_gamma.bash $proc_file >> $job
			chmod +x $job
			qsub $job
		    else # scene list exists
			echo ""
			echo "Creating SLC data..."
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
				job=$pbs_job_prefix$i

				echo Doing job $i in $jobdir with $job

				echo \#\!/bin/bash > $job
				echo \#\PBS -l other=gdata1 >> $job
				echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
				echo \#\PBS -l mem=$slc_mem >> $job
				echo \#\PBS -l ncpus=$slc_ncpus >> $job
				echo \#\PBS -l wd >> $job
				echo \#\PBS -q normal >> $job
				echo -e "\n" >> $job

				for(( n=0; n<nsteps; n++ )); do
				    read scene
				    echo $scene
				    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
					echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
				    else
					echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
					echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
				    fi
        			done
				chmod +x $job
				qsub $job | tee $slc_batch_dir/$beam_num/"slc_"$beam_num"_"$i"_job_id"
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
			cd $slc_manual_dir/$beam_num
			while read list; do
			    scene=`echo $list | awk '{print $1}'`
			    job="slc_"$beam_num"_"$scene
			    echo \#\!/bin/bash > $job
			    echo \#\PBS -lother=gdata1 >> $job
			    echo \#\PBS -l walltime=$slc_walltime >> $job
			    echo \#\PBS -l mem=$slc_mem >> $job
			    echo \#\PBS -l ncpus=$slc_ncpus >> $job
			    echo \#\PBS -l wd >> $job
			    echo \#\PBS -q normal >> $job
			    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			    else
				echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
				echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
			    fi
			    chmod +x $job
			done < $scene_list

                        # run slc error check
			echo "Preparing error collation for 'do_slc'..."
			cd $slc_batch_dir/$beam_num
			job="slc_err_check"$beam_num
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$error_walltime >> $job
			echo \#\PBS -l mem=$error_mem >> $job
			echo \#\PBS -l ncpus=$error_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			echo \#\PBS -W depend=afterany:$dep >> $job
			echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 3 $beam_num >> $job
			chmod +x $job
			qsub $job
		    fi
		else # process as normal
		    echo ""
		    echo "Creating SLC data..."
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
			    job=$pbs_job_prefix$i

			    echo Doing job $i in $jobdir with $job

			    echo \#\!/bin/bash > $job
			    echo \#\PBS -l other=gdata1 >> $job
			    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
			    echo \#\PBS -l mem=$slc_mem >> $job
			    echo \#\PBS -l ncpus=$slc_ncpus >> $job
			    echo \#\PBS -l wd >> $job
			    echo \#\PBS -q normal >> $job
			    echo -e "\n" >> $job
			    if [ $do_raw == yes -a $platform == NCI ]; then
				raw_jobid=`sed s/.r-man2// $batch_dir/raw_job_id`
				echo \#\PBS -W depend=afterok:$raw_jobid >> $job
			    else
				:
			    fi

			    for(( n=0; n<nsteps; n++ )); do
				read scene
				echo $scene
				if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
				else
				    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
				    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
				fi
        		    done
			    chmod +x $job
			    qsub $job | tee $slc_batch_dir/$beam_num/"slc_"$beam_num"_"$i"_job_id"
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
		    cd $slc_manual_dir/$beam_num
		    while read list; do
			scene=`echo $list | awk '{print $1}'`
			job="slc_"$beam_num"_"$scene
			echo \#\!/bin/bash > $job
			echo \#\PBS -lother=gdata1 >> $job
			echo \#\PBS -l walltime=$slc_walltime >> $job
			echo \#\PBS -l mem=$slc_mem >> $job
			echo \#\PBS -l ncpus=$slc_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			else
			    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
			fi
			chmod +x $job
		    done < $scene_list

                    # run slc error check
		    echo "Preparing error collation for 'do_slc'..."
		    cd $slc_batch_dir/$beam_num
		    job="slc_err_check"$beam_num
		    echo \#\!/bin/bash > $job
		    echo \#\PBS -lother=gdata1 >> $job
		    echo \#\PBS -l walltime=$error_walltime >> $job
		    echo \#\PBS -l mem=$error_mem >> $job
		    echo \#\PBS -l ncpus=$error_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo \#\PBS -W depend=afterany:$dep >> $job
		    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 3 $beam_num >> $job
		    chmod +x $job
		    qsub $job
		fi
	    fi
	done < $beam_list
    else # no beams
	cd $slc_batch_dir
	if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes ]; then
	    if [ ! -e $scene_list ]; then # if scene list doesn't exist
		echo ""
		echo "Scene list doesn't exist yet, preparing to rerun process_gamma.bash after list is created to create SLCs..."
		# rerun process_gamma.bash once do setup and do raw are finished
		cd $proj_dir
		raw_jobid=`sed s/.r-man2// $batch_dir/raw_job_id`
		job=process_$track_dir"_auto_rerun"
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$list_walltime >> $job
		echo \#\PBS -l mem=$list_mem >> $job
		echo \#\PBS -l ncpus=$list_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterok:$raw_jobid >> $job
		echo ~/repo/gamma_insar/process_gamma.bash $proc_file >> $job
		chmod +x $job
		qsub $job
	    else # scene list exists
		echo ""
		echo "Creating SLC data..."
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
        		job=$pbs_job_prefix$i
			echo Doing job $i in $jobdir with $job
			echo \#\!/bin/bash > $job
			echo \#\PBS -l other=gdata1 >> $job
			echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
			echo \#\PBS -l mem=$slc_mem >> $job
			echo \#\PBS -l ncpus=$slc_ncpus >> $job
			echo \#\PBS -l wd >> $job
			echo \#\PBS -q normal >> $job
			echo -e "\n" >> $job

			for(( n=0; n<nsteps; n++ )); do
			    read scene
			    echo $scene
			    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			    else
				echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
				echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
			    fi
        		done
			chmod +x $job
			qsub $job | tee $slc_batch_dir/"slc_"$i"_job_id"
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
		cd $slc_manual_dir
		while read list; do
		    scene=`echo $list | awk '{print $1}'`
		    job="slc_"$scene
		    echo \#\!/bin/bash > $job
		    echo \#\PBS -lother=gdata1 >> $job
		    echo \#\PBS -l walltime=$slc_walltime >> $job
		    echo \#\PBS -l mem=$slc_mem >> $job
		    echo \#\PBS -l ncpus=$slc_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		    else
			echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		    fi
		    chmod +x $job
		done < $scene_list

                # run slc error check
		echo "Preparing error collation for 'do_slc'..."
		cd $slc_batch_dir
		job=slc_err_check
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$error_walltime >> $job
		echo \#\PBS -l mem=$error_mem >> $job
		echo \#\PBS -l ncpus=$error_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo \#\PBS -W depend=afterany:$dep >> $job
		echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 3 >> $job
		chmod +x $job
		qsub $job
	    fi
	else # process as normal
	    echo ""
	    echo "Creating SLC data..."
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
        	    job=$pbs_job_prefix$i
		    echo Doing job $i in $jobdir with $job
		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$slc_mem >> $job
		    echo \#\PBS -l ncpus=$slc_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $do_raw == yes -a $platform == NCI ]; then
			raw_jobid=`sed s/.r-man2// $batch_dir/raw_job_id`
			echo \#\PBS -W depend=afterok:$raw_jobid >> $job
		    else
			:
		    fi

		    for(( n=0; n<nsteps; n++ )); do
			read scene
			echo $scene
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			else
			    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
			fi
        	    done
		    chmod +x $job
		    qsub $job | tee $slc_batch_dir/"slc_"$i"_job_id"
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
	    cd $slc_manual_dir
	    while read list; do
		scene=`echo $list | awk '{print $1}'`
		job="slc_"$scene
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$slc_walltime >> $job
		echo \#\PBS -l mem=$slc_mem >> $job
		echo \#\PBS -l ncpus=$slc_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		else
		    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		    echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		fi
		chmod +x $job
	    done < $scene_list

            # run slc error check
	    echo "Preparing error collation for 'do_slc'..."
	    cd $slc_batch_dir
	    job=slc_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 3 >> $job
	    chmod +x $job
	    qsub $job
	fi
    fi
elif [ $do_slc == no -a $platform == NCI ]; then
    echo ""
    echo "Option to create SLC data not selected."
    echo ""
else
    :
fi




##########################   AUTO CROP SENTINEL-1 SLCS   ##########################


#### NCI ####

if [ $do_auto_crop == yes -a $platform == NCI -a $sensor == S1 ]; then
    cd $batch_dir
    mkdir -p $batch_dir/slc_crop_jobs
    mkdir -p $manual_dir/slc_crop_jobs
    crop_slc_batch_dir=$batch_dir/slc_crop_jobs
    crop_slc_manual_dir=$manual_dir/slc_crop_jobs

    cd $crop_slc_batch_dir

    # run auto crop
    echo "Auto cropping Sentinel-1 SLC data..."
    cd $crop_slc_batch_dir
    job=crop_slc
    echo \#\!/bin/bash > $job
    echo \#\PBS -l other=gdata1 >> $job
    echo \#\PBS -l walltime=$slc_walltime >> $job
    echo \#\PBS -l mem=$slc_mem >> $job
    echo \#\PBS -l ncpus=$slc_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q normal >> $job
    echo -e "\n" >> $job
    if [ $do_slc == yes -a $platform == NCI ]; then
	slc_jobid=`awk '{print $1}' $batch_dir/slc_jobs/all_slc_job_id`
	echo \#\PBS -W depend=afterok:$slc_jobid >> $job
    else
	:
    fi
    echo ~/repo/gamma_insar/"auto_crop_"$sensor"_SLCs.bash" $proj_dir/$proc_file >> $job
    chmod +x $job
    qsub $job | tee crop_job_id

    # in case future manual processing is required, create manual PBS job
    cd $crop_slc_manual_dir

    echo \#\!/bin/bash > $job
    echo \#\PBS -lother=gdata1 >> $job
    echo \#\PBS -l walltime=$slc_walltime >> $job
    echo \#\PBS -l mem=$slc_mem >> $job
    echo \#\PBS -l ncpus=$slc_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q normal >> $job
    echo -e "\n" >> $job
    echo ~/repo/gamma_insar/"auto_crop_"$sensor"_SLCs.bash" $proj_dir/$proc_file >> $job
    chmod +x $job

    # run crop slc error check
    echo "Preparing error collation for 'do_auto_crop'..."
    cd $crop_slc_batch_dir 
    crop_jobid=`sed s/.r-man2// crop_job_id`		
    job=crop_err_check
    echo \#\!/bin/bash > $job
    echo \#\PBS -lother=gdata1 >> $job
    echo \#\PBS -l walltime=$error_walltime >> $job
    echo \#\PBS -l mem=$error_mem >> $job
    echo \#\PBS -l ncpus=$error_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q normal >> $job
    echo \#\PBS -W depend=afterany:$crop_jobid >> $job
    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 4 >> $job
    chmod +x $job
    qsub $job
else
    :
fi




##########################   SUBSET SENTINEL-1 SLCS   ##########################


#### NCI ####

if [ $do_slc_subset == yes -a $platform == NCI -a $sensor == S1 ]; then
    mkdir -p $track_dir/batch_jobs/slc_subset_jobs
    mkdir -p $track_dir/manual_jobs/slc_subset_jobs
    subset_slc_batch_dir=$batch_dir/slc_subset_jobs
    subset_slc_manual_dir=$manual_dir/slc_subset_jobs

    # Maximum number of jobs to be run (no more than 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a single process_slc in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_job_prefix=sub_slc_

    cd $subset_slc_batch_dir

    echo ""
    echo "Subset Sentinel-1 SLC data..."
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
            job=$pbs_job_prefix$i
	    echo Doing job $i in $jobdir with $job
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -l other=gdata1 >> $job
	    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
	    echo \#\PBS -l mem=$slc_mem >> $job
	    echo \#\PBS -l ncpus=$slc_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo -e "\n" >> $job
	    for(( n=0; n<nsteps; n++ )); do
		read scene
		echo $scene
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/"subset_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		else
		    echo ~/repo/gamma_insar/"subset_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		    echo ~/repo/gamma_insar/"subset_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		fi
            done
	    chmod +x $job
	    qsub $job | tee $subset_slc_batch_dir/"sub_slc_"$i"_job_id"
	    cd ..
	done
    }
    # Work starts here
    cd $subset_slc_batch_dir
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
    cd $subset_slc_batch_dir
    ls "sub_slc_"*"_job_id" > list1
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
    sed s'/.$//' list5 > all_sub_slc_job_id # remove last :
    dep=`awk '{print $1}' all_sub_slc_job_id`
    rm -rf list* "sub_slc_"*"_job_id"

    # in case future manual processing is required, create manual PBS jobs for each scene
    cd $subset_slc_manual_dir
    while read list; do
	scene=`echo $list | awk '{print $1}'`
	job="slc_"$scene
	echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$slc_walltime >> $job
	    echo \#\PBS -l mem=$slc_mem >> $job
	    echo \#\PBS -l ncpus=$slc_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		echo ~/repo/gamma_insar/"subset_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
	    else
		echo ~/repo/gamma_insar/"subset_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		echo ~/repo/gamma_insar/"subset_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
	    fi
	    chmod +x $job
	done < $scene_list

        # run subset slc error check
	echo "Preparing error collation for 'do_subset_slc'..."
	cd $subset_slc_batch_dir
	job=sub_slc_err_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=$error_walltime >> $job
	echo \#\PBS -l mem=$error_mem >> $job
	echo \#\PBS -l ncpus=$error_ncpus >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterany:$dep >> $job
	echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 5 >> $job
	chmod +x $job
	qsub $job
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
    dem_batch_dir=$batch_dir/dem_jobs
    dem_manual_dir=$manual_dir/dem_jobs
    cd $dem_batch_dir

    if [ -f $beam_list ]; then # if beam list exists

	## Functions
	SUBSET_BEAM_DEM_INITIAL()
	{
            # no multi-look value - for geocoding full SLC and determining pixels for subsetting master scene
            # set up header for PBS job
	    echo "Coregistering full resolution DEM in preparation for subsetting..."
	    job="coreg_full_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    if [ $do_slc == yes -a $platform == NCI ]; then
		slc_jobid=`awk '{print $1}' $batch_dir/slc_jobs/$beam_num/"all_slc_"$beam_num"_job_id"`
		echo \#\PBS -W depend=afterok:$slc_jobid >> $job
	    else
		:
	    fi
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 2 1 - - - - $beam_num >> $job
	    else
 		echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 2 2 - - - - $beam_num >> $job
	    fi
	    chmod +x $job
	    qsub $job | tee "full_dem_"$beam_num"_job_id"

            # determine subset pixels and update proc file with values
            # set up header for PBS job
	    echo "Calculating pixel values for subsetting..."
	    full_dem_jobid=`sed s/.r-man2// "full_dem_"$beam_num"_job_id"`
	    job="calc_subset_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$list_walltime >> $job
	    echo \#\PBS -l mem=$list_mem >> $job
	    echo \#\PBS -l ncpus=$list_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterok:$full_dem_jobid >> $job
	    echo ~/repo/gamma_insar/determine_subscene_pixels.bash $proj_dir/$proc_file $subset_file $beam_num >> $job
	    chmod +x $job
	    qsub $job | tee "calc_subset_dem_"$beam_num"_job_id"

            #rerun process_gamma.bash once calc_subset has run to include subset values in coreg_sub_dem PBS job
	    echo "Preparing job to rerun 'process_gamma.bash' to coregister subsetted DEM to subsetted reference master scene..."
	    subset_jobid=`sed s/.r-man2// "calc_subset_dem_"$beam_num"_job_id"`
	    job=rerun_process_gamma
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$list_walltime >> $job
	    echo \#\PBS -l mem=$list_mem >> $job
	    echo \#\PBS -l ncpus=$list_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterok:$subset_jobid >> $job
	    echo ~/repo/gamma_insar/process_gamma.bash $proj_dir/$proc_file >> $job
	    chmod +x $job
	    qsub $job

            # in case future manual processing is required, create manual PBS jobs
	    cd $dem_manual_dir/$beam_num
	    job="coreg_full_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 2 1 - - - - $beam_num >> $job
	    else
 		echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 2 2 - - - - $beam_num >> $job
	    fi
	    chmod +x $job

	    job="calc_subset_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$list_walltime >> $job
	    echo \#\PBS -l mem=$list_mem >> $job
	    echo \#\PBS -l ncpus=$list_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo ~/repo/gamma_insar/determine_subscene_pixels.bash $proj_dir/$proc_file $subset_file $beam_num >> $job
	    chmod +x $job
	}

	SUBSET_BEAM_DEM()
	{
            # set up header for PBS job
	    echo "Coregistering subsetted DEM to subsetted reference  master scene..."
	    job="coreg_sub_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 1 $roff $rlines $azoff $azlines $beam_num >> $job
		fi
	    else
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
		fi
	    fi
	    chmod +x $job
	    qsub $job | tee "subset_dem_"$beam_num"_job_id"

            # in case future manual processing is required, create manual PBS jobs
	    cd $dem_manual_dir/$beam_num
	    job="coreg_sub_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 1 $roff $rlines $azoff $azlines $beam_num >> $job
		fi
	    else
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 2 $roff $rlines $azoff $azlines $beam_num >> $job
		fi
	    fi
	    chmod +x $job

            # run dem error check
	    echo "Preparing error collation for 'coregister_dem'..."
	    cd $dem_batch_dir/$beam_num
	    dem_jobid=`sed s/.r-man2// "subset_dem_"$beam_num"_job_id"`
	    job="dem_err_check_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 4 $beam_num >> $job
	    chmod +x $job
	    qsub $job
	}

	NO_SUBSET_BEAM_DEM()
	{
            # no multi-look value - for geocoding full SLC data
            # set up header for PBS job
	    echo ""
	    echo "Coregistering DEM to reference master scene..."

            # Set up coregistration results file
	    cd $proj_dir/$track_dir
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		check_file=$proj_dir/$track_dir/dem_coreg_results"_"$beam_num"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "DEM Coregistration Results "$beam_num" "$slc_rlks"rlks "$slc_alks"alks" > $check_file
		echo "final model fit std. dev. (samples)" >> $check_file
		echo "Range" > temp1_$beam_num
		echo "Azimuth" > temp2_$beam_num
		paste temp1_$beam_num temp2_$beam_num >> $check_file
		rm -f temp1_$beam_num temp2_$beam_num
	    else
		slc_check_file=$proj_dir/$track_dir/dem_coreg_results"_"$beam_num"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "DEM Coregistration Results "$beam_num" "$slc_rlks"rlks "$slc_alks"alks" > $slc_check_file
		echo "final model fit std. dev. (samples)" >> $slc_check_file
		echo "Range" > temp1_$beam_num
		echo "Azimuth" > temp2_$beam_num
		paste temp1_$beam_num temp2_$beam_num >> $slc_check_file
		rm -f temp1_$beam_num temp2_$beam_num

		ifm_check_file=$proj_dir/$track_dir/dem_coreg_results"_"$beam_num"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
		echo "DEM Coregistration Results "$beam_num" "$ifm_rlks"rlks "$ifm_alks"alks" > $ifm_check_file
		echo "final model fit std. dev. (samples)" >> $ifm_check_file
		echo "Range" > temp3_$beam_num
		echo "Azimuth" > temp4_$beam_num
		paste temp3_$beam_num temp4_$beam_num >> $ifm_check_file
		rm -f temp3_$beam_num temp4_$beam_num
	    fi

	    cd $dem_batch_dir/$beam_num

	    job="coreg_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    if [ $do_slc == yes -a $platform == NCI ]; then
		slc_jobid=`awk '{print $1}' $batch_dir/slc_jobs/$beam_num/"all_slc_"$beam_num"_job_id"`
		echo \#\PBS -W depend=afterok:$slc_jobid >> $job
	    else
		:
	    fi
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 1 - - - - $beam_num >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 1 - - - - $beam_num >> $job
		fi
	    else
	        # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 2 - - - - $beam_num >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 2 - - - - $beam_num >> $job
		fi
	    fi
	    chmod +x $job
	    qsub $job | tee "dem_"$beam_num"_job_id"

            # in case future manual processing is required, create manual PBS jobs
	    cd $dem_manual_dir/$beam_num
	    job="coreg_dem_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 1 - - - - $beam_num >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 1 - - - - $beam_num >> $job
		fi
	    else
	        # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 2 - - - - $beam_num >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - $beam_num >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - $beam_num >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 2 - - - - $beam_num >> $job
		fi
	    fi
	    chmod +x $job

            # run dem error check
	    echo "Preparing error collation for 'coregister_dem'..."
	    cd $dem_batch_dir/$beam_num
	    dem_jobid=`sed s/.r-man2// "dem_"$beam_num"_job_id"`
	    job="dem_err_check_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 5 $beam_num >> $job
	    chmod +x $job
	    qsub $job
	}

        # set up and submit PBS job script for each beam
	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		cd $dem_batch_dir/$beam_num
		if [ $subset == yes ]; then
		    # check if subset values have been calculated (ie. they are integers not - )
		    roff1=`[[ $roff =~ ^-?[0-9]+$ ]] && echo integer`
		    rlines1=`[[ $rlines =~ ^-?[0-9]+$ ]] && echo integer`
		    azoff1=`[[ $azoff =~ ^-?[0-9]+$ ]] && echo integer`
		    azlines1=`[[ $azlines =~ ^-?[0-9]+$ ]] && echo integer`

		    if [ $roff == "-" -a $rlines == "-" -a $azoff == "-" -a $azlines == "-" ]; then
			if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes ]; then
			    if [ ! -e $scene_list ]; then # if scene list doesn't exist
				echo ""
				echo "Scene list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
			    else # scene list exists
				SUBSET_BEAM_DEM_INITIAL
			    fi
			else # process as normal
			    SUBSET_BEAM_DEM_INITIAL
			fi
		    elif [ $roff1 == "integer" -a $rlines1 == "integer" -a $azoff1 == "integer" -a $azlines1 == "integer" ]; then
			cd $dem_batch_dir/$beam_num
			SUBSET_BEAM_DEM
		    else
			echo ""  1>&2
			echo "Subsetting values in proc file are not - . Update proc file before subsetting can occur."  1>&2
			echo ""  1>&2
		    fi
		elif [ $subset == no ]; then # no subsetting
		    if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes ]; then
			if [ ! -e $scene_list ]; then # if scene list doesn't exist
			    echo ""
			    echo "Scene list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
			else # scene list exists
			    NO_SUBSET_BEAM_DEM
			fi
		    else # process as normal
			NO_SUBSET_BEAM_DEM
  		    fi
   		else
	    	    :
		fi
 	    fi
	done < $beam_list
    else # no beams

	## Functions
	SUBSET_DEM_INITIAL()
	{
            # no multi-look value - for geocoding full SLC and determining pixels for subsetting master scene
            # set up header for PBS job
	    echo "Coregistering full resolution DEM in preparation for subsetting..."
	    echo "*** Manually calculate subset scene extent before resuming processing ***"
	    job=init_coreg_dem
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    if [ $do_slc == yes -a $platform == NCI ]; then
		slc_jobid=`awk '{print $1}' $batch_dir/slc_jobs/all_slc_job_id`
		echo \#\PBS -W depend=afterok:$slc_jobid >> $job
	    else
		:
	    fi
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - >> $job
	    else
 		echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - >> $job
	    fi
	    chmod +x $job
	    qsub $job | tee init_dem_job_id

            # in case future manual processing is required, create manual PBS jobs
	    cd $dem_manual_dir
	    job=init_coreg_dem
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - >> $job
	    else
 		echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - >> $job
	    fi
	    chmod +x $job

            # run dem error check
	    echo "Preparing error collation for initial DEM coregistration prior to subsetting..."
	    cd $dem_batch_dir
	    dem_jobid=`sed s/.r-man2// init_dem_job_id`
	    job=dem_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 6 >> $job
	    chmod +x $job
	    qsub $job
  	}

	SUBSET_PIXELS()
	{
            # determine subset pixels and update proc file with values
            # set up header for PBS job
	    echo "Calculating pixel values for subsetting..."
	    echo "*** Check proc file for updated subset pixels before resuming processing ***"
	    cd $dem_batch_dir
	    job=calc_subset
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$list_walltime >> $job
	    echo \#\PBS -l mem=$list_mem >> $job
	    echo \#\PBS -l ncpus=$list_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo ~/repo/gamma_insar/determine_subscene_pixels.bash $proj_dir/$proc_file $subset_file >> $job
	    chmod +x $job
	    qsub $job | tee calc_subset_job_id

            # in case future manual processing is required, create manual PBS jobs
	    cd $dem_manual_dir
	    job=calc_subset
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$list_walltime >> $job
	    echo \#\PBS -l mem=$list_mem >> $job
	    echo \#\PBS -l ncpus=$list_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo ~/repo/gamma_insar/determine_subscene_pixels.bash $proj_dir/$proc_file $subset_file >> $job
	    chmod +x $job

          # run error check
	    echo "Preparing error collation for subset pixel determination..."
	    cd $dem_batch_dir
	    dem_jobid=`sed s/.r-man2// calc_subset_job_id`
	    job=dem_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 6 >> $job
	    chmod +x $job
	    qsub $job
	}

	SUBSET_DEM()
	{
            # set up header for PBS job
	    echo "Coregistering subsetted DEM to subsetted reference master scene..."
	    cd $dem_batch_dir
	    job=coreg_sub_dem
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job

	    roff1=`[[ $roff =~ ^-?[0-9]+$ ]] && echo integer`
	    rlines1=`[[ $rlines =~ ^-?[0-9]+$ ]] && echo integer`
	    azoff1=`[[ $azoff =~ ^-?[0-9]+$ ]] && echo integer`
	    azlines1=`[[ $azlines =~ ^-?[0-9]+$ ]] && echo integer`

	    if [ $roff1 == "integer" -a $rlines1 == "integer" -a $azoff1 == "integer" -a $azlines1 == "integer" ]; then
  		if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # SLC and ifm multi-look value (same value)
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines >> $job
		    else
                # SLC multi-look value
			echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines >> $job
                # ifm multi-look value
			echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 1 $roff $rlines $azoff $azlines >> $job
		    fi
		else
                # SLC and ifm multi-look value (same value)
		    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines >> $job
		    else
                # SLC multi-look value
			echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines >> $job
                # ifm multi-look value
			echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 2 $roff $rlines $azoff $azlines >> $job
		    fi
		fi
	    else
		echo "pixel subset values not calculated"
	    fi
	    chmod +x $job
	    qsub $job | tee subset_dem_job_id

            # in case future manual processing is required, create manual PBS jobs
	    cd $dem_manual_dir
	    job=coreg_sub_dem
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 1 $roff $rlines $azoff $azlines >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 1 $roff $rlines $azoff $azlines >> $job
		fi
	    else
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 2 2 $roff $rlines $azoff $azlines >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 2 2 $roff $rlines $azoff $azlines >> $job
		fi
	    fi
	    chmod +x $job

            # run dem error check
	    echo "Preparing error collation for 'coregister_dem'..."
	    cd $dem_batch_dir
	    dem_jobid=`sed s/.r-man2// subset_dem_job_id`
	    job=dem_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 6 >> $job
	    chmod +x $job
	    qsub $job
	}

	NO_SUBSET_DEM()
	{
	    #if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes ]; then
		#proc=$proc_file
	    #else
		proc=$proj_dir/$proc_file
	    #fi
            # set up header for PBS job
	    echo ""
	    echo "Coregistering DEM to reference master scene..."

            # Set up coregistration results file
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		check_file=$proj_dir/$track_dir/dem_coreg_results"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "DEM Coregistration Results "$slc_rlks"rlks "$slc_alks"alks" > $check_file
		echo "final model fit std. dev. (samples)" >> $check_file
		echo "Range" > temp1
		echo "Azimuth" > temp2
		paste temp1 temp2 >> $check_file
		rm -f temp1 temp2
	    else
		slc_check_file=$proj_dir/$track_dir/dem_coreg_results"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "DEM Coregistration Results "$slc_rlks"rlks "$slc_alks"alks" > $slc_check_file
		echo "final model fit std. dev. (samples)" >> $slc_check_file
		echo "Range" > temp1
		echo "Azimuth" > temp2
		paste temp1 temp2 >> $slc_check_file
		rm -f temp1 temp2

		ifm_check_file=$proj_dir/$track_dir/dem_coreg_results"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
		echo "DEM Coregistration Results "$ifm_rlks"rlks "$ifm_alks"alks" > $ifm_check_file
		echo "final model fit std. dev. (samples)" >> $ifm_check_file
		echo "Range" > temp3
		echo "Azimuth" > temp4
		paste temp3 temp4 >> $ifm_check_file
		rm -f temp3 temp4
	    fi

	    cd $dem_batch_dir

	    job=coreg_dem
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    if [ $do_slc == yes -a $platform == NCI ]; then
		slc_jobid=`awk '{print $1}' $batch_dir/slc_jobs/all_slc_job_id`
		echo \#\PBS -W depend=afterok:$slc_jobid >> $job
	    else
		:
	    fi
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 1 - - - - >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 1 - - - - >> $job
		fi
	    else
                # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 2 - - - - >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 2 - - - - >> $job
		fi
	    fi
	    chmod +x $job
	    qsub $job | tee dem_job_id

            # in case future manual processing is required, create manual PBS jobs
	    cd $dem_manual_dir
	    job=coreg_dem
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$dem_walltime >> $job
	    echo \#\PBS -l mem=$dem_mem >> $job
	    echo \#\PBS -l ncpus=$dem_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
  	    if [ ! -f $proj_dir/gamma_dem/$ext_image ]; then # no external reference image
                # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 1 - - - - >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 1 - - - - >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 1 - - - - >> $job
		fi
	    else
                # no multi-look value - for geocoding full SLC data
		#echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file 1 1 1 1 2 - - - - >> $job
                # SLC and ifm multi-look value (same value)
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - >> $job
		else
                # SLC multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $slc_rlks $slc_alks 2 1 2 - - - - >> $job
                # ifm multi-look value
		    echo ~/repo/gamma_insar/make_ref_master_DEM.bash $proj_dir/$proc_file $ifm_rlks $ifm_alks 2 1 2 - - - - >> $job
		fi
	    fi
	    chmod +x $job

            # run dem error check
	    echo "Preparing error collation for 'coregister_dem'..."
	    cd $dem_batch_dir
	    dem_jobid=`sed s/.r-man2// dem_job_id`
	    job=dem_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dem_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 6 >> $job
	    chmod +x $job
	    qsub $job
	}

	if [ $subset == yes ]; then
	    cd $dem_batch_dir
	    # check if subset values have been calculated (ie. they are integers not - )
	    roff1=`[[ $roff =~ ^-?[0-9]+$ ]] && echo integer`
	    rlines1=`[[ $rlines =~ ^-?[0-9]+$ ]] && echo integer`
	    azoff1=`[[ $azoff =~ ^-?[0-9]+$ ]] && echo integer`
	    azlines1=`[[ $azlines =~ ^-?[0-9]+$ ]] && echo integer`

	    if [ $roff == "-" -a $rlines == "-" -a $azoff == "-" -a $azlines == "-" ]; then
		if [ ! -e $subset_file ]; then
		    if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes ]; then
			if [ ! -e $scene_list ]; then # if scene list doesn't exist
			    echo ""
			    echo "Scene list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
			else # scene list exists
			    SUBSET_DEM_INITIAL
			fi
		    else # process as normal
			SUBSET_DEM_INITIAL
		    fi
		else
		    SUBSET_PIXELS
		fi
	    elif [ $roff1 == "integer" -a $rlines1 == "integer" -a $azoff1 == "integer" -a $azlines1 == "integer" ]; then
		cd $dem_batch_dir
		SUBSET_DEM
	    else
		echo ""  1>&2
		echo "Some subsetting values in proc file are - . All values must be integers before subsetting can occur."  1>&2
		echo ""  1>&2
	    fi
	elif [ $subset == no ]; then # no subsetting
	    if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes ]; then
		if [ ! -e $scene_list ]; then # if scene list doesn't exist
		    echo ""
		    echo "Scene list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
		else # scene list exists
		    NO_SUBSET_DEM
		fi
	    else # process as normal
		NO_SUBSET_DEM
  	    fi
   	else
	    :
	fi
    fi

elif [ $coregister_dem == no -a $platform == NCI ]; then
    echo ""
    echo "Option to coregister DEM to reference master scene not selected."
    echo ""

else
    :
fi




##########################   COREGISTER SLAVE SCENES TO MASTER SCENE   ##########################

if [ $sensor == S1 -a $mode == IWS ]; then
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
    co_slc_batch_dir=$batch_dir/slc_coreg_jobs
    co_slc_manual_dir=$manual_dir/slc_coreg_jobs
    cd $co_slc_batch_dir

    # Maximum number of jobs to be run (maximum number is 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $co_slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a single coreg_slc in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_job_prefix=co_slc_

    if [ -f $beam_list ]; then # if beam list exists

	## Functions
	COREG_BEAM_SLAVE()
	{
	    echo ""
	    echo "Coregistering slave scenes to reference master scene..."
            # Set up coregistration results file
	    cd $proj_dir/$track_dir
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		check_file=$proj_dir/$track_dir/slave_coreg_results"_"$beam_num"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$beam_num" "$slc_rlks"rlks "$slc_alks"alks" > $check_file
		echo "final model fit std. dev. (samples)" >> $check_file
		echo "Ref Master" > temp1_$beam_num
		echo "Slave" > temp2_$beam_num
		echo "Range" > temp3_$beam_num
		echo "Azimuth" > temp4_$beam_num
		paste temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num >> $check_file
		rm -f temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num
	    else
		slc_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$beam_num"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$beam_num" "$slc_rlks"rlks "$slc_alks"alks" > $slc_check_file
		echo "final model fit std. dev. (samples)" >> $slc_check_file
		echo "Ref Master" > temp1_$beam_num
		echo "Slave" > temp2_$beam_num
		echo "Range" > temp3_$beam_num
		echo "Azimuth" > temp4_$beam_num
		paste temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num >> $slc_check_file
		rm -f temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num

		ifm_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$beam_num"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
		echo "Slave Coregistration Results "$beam_num" "$ifm_rlks"rlks "$ifm_alks"alks" > $ifm_check_file
		echo "final model fit std. dev. (samples)" >> $ifm_check_file
		echo "Ref Master" > temp5_$beam_num
		echo "Slave" > temp6_$beam_num
		echo "Range" > temp7_$beam_num
		echo "Azimuth" > temp8_$beam_num
		paste temp5_$beam_num temp6_$beam_num temp7_$beam_num temp8_$beam_num >> $ifm_check_file
		rm -f temp5_$beam_num temp6_$beam_num temp7_$beam_num temp8_$beam_num
	    fi

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$co_slc_mem >> $job
		    echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $coregister_dem == yes -a $platform == NCI ]; then
			if [ -f $batch_dir/dem_jobs/$beam_num/"subset_dem_"$beam_num"_job_id" ]; then
			    dem_jobid=`sed s/.r-man2// $batch_dir/dem_jobs/$beam_num/"subset_dem_"$beam_num"_job_id"`
			else
			    dem_jobid=`sed s/.r-man2// $batch_dir/dem_jobs/$beam_num/"dem_"$beam_num"_job_id"`
			fi
			echo \#\PBS -W depend=afterok:$dem_jobid >> $job
		    else
			:
		    fi
        	    for(( n=0; n<nsteps; n++ )); do
                	read scene
                	echo $scene
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			else
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
			fi
		    done
		    chmod +x $job
		    qsub $job | tee $co_slc_batch_dir/$beam_num/"co_slc_"$beam_num"_"$i"_job_id"
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
	    cd $co_slc_manual_dir/$beam_num
	    while read list; do
		scene=`echo $list | awk '{print $1}'`
		job="co_slc_"$beam_num"_"$scene
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$co_slc_walltime >> $job
		echo \#\PBS -l mem=$co_slc_mem >> $job
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
		else
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
		fi
		chmod +x $job
	    done < $slave_list

            # run coreg slc error check
	    echo "Preparing error collation for 'coregister_slaves'..."
	    cd $co_slc_batch_dir/$beam_num
	    job="co_slc_err_check_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 6 $beam_num >> $job
	    chmod +x $job
	    qsub $job
	}

	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes -a $coregister_dem == yes -a $coregister == yes ]; then
		    if [ ! -e $slave_list ]; then # if slave list doesn't exist
			echo ""
			echo "Slave list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
			:
		    else # slave list exists
			COREG_BEAM_SLAVE
		    fi
		else # process as normal
		    COREG_BEAM_SLAVE
		fi
	    fi
	done < $beam_list
    else # no beams

	## Functions
	COREG_SLAVE()
	{
	    echo ""
	    echo "Coregistering slave scenes to reference master scene..."
            # Set up coregistration results file
	    cd $proj_dir/$track_dir
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		check_file=$proj_dir/$track_dir/slave_coreg_results"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$slc_rlks"rlks "$slc_alks"alks" > $check_file
		echo "final offset poly. coeff." >> $check_file
		echo "Ref Master" > temp1
		echo "Slave" > temp2
		echo "Range" > temp3
		echo "Azimuth" > temp4
		paste temp1 temp2 temp3 temp4 >> $check_file
		rm -f temp1 temp2 temp3 temp4
	    else
		slc_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$slc_rlks"rlks "$slc_alks"alks" > $slc_check_file
		echo "final offset poly. coeff." >> $slc_check_file
		echo "Ref Master" > temp1
		echo "Slave" > temp2
		echo "Range" > temp3
		echo "Azimuth" > temp4
		paste temp1 temp2 temp3 temp4 >> $slc_check_file
		rm -f temp1 temp2 temp3 temp4

		ifm_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
		echo "Slave Coregistration Results "$ifm_rlks"rlks "$ifm_alks"alks" > $ifm_check_file
		echo "final offset poly. coeff." >> $ifm_check_file
		echo "Ref Master" > temp5
		echo "Slave" > temp6
		echo "Range" > temp7
		echo "Azimuth" > temp8
		paste temp5 temp6 temp7 temp8 >> $ifm_check_file
		rm -f temp5 temp6 temp7 temp8
	    fi

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$co_slc_mem >> $job
		    echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $coregister_dem == yes -a $platform == NCI ]; then
			if [ -f $batch_dir/dem_jobs/all_dem_job_id ]; then
			    dem_jobid=`sed s/.r-man2// $batch_dir/dem_jobs/subset_dem_job_id`
			else
			    dem_jobid=`sed s/.r-man2// $batch_dir/dem_jobs/dem_job_id`
			fi
			echo \#\PBS -W depend=afterok:$dem_jobid >> $job
		    else
			:
		    fi
		    for(( n=0; n<nsteps; n++ )); do
			read scene
			echo $scene
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			else
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
			fi
        	    done
		    chmod +x $job
		    qsub $job | tee $co_slc_batch_dir/"co_slc_"$i"_job_id"
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
	    cd $co_slc_manual_dir
	    while read list; do
		scene=`echo $list | awk '{print $1}'`
		job="co_slc_"$scene
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$co_slc_walltime >> $job
		echo \#\PBS -l mem=$co_slc_mem >> $job
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		else
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		fi
		chmod +x $job
	    done < $slave_list

            # run coreg slc error check
	    echo "Preparing error collation for 'coregister_slaves'..."
	    cd $co_slc_batch_dir
	    job=co_slc_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 7 >> $job
	    chmod +x $job
	    qsub $job
	}

	if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes -a $coregister_dem == yes -a $coregister == yes ]; then
	    if [ ! -e $slave_list ]; then # if slave list doesn't exist
		echo ""
		echo "Slave list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
		:
	    else # slave list exists
		COREG_SLAVE
	    fi
	else # process as normal
	    COREG_SLAVE
	fi
    fi

    # PBS job for checking slave coregistration  - doesn't work, won't display window
#    job=check_slc_coreg
#    co_slc_jobid=`sed s/.r-man2// co_slc_err_job_id`
#    echo \#\!/bin/bash > $job
#    echo \#\PBS -lother=gdata1 >> $job
#    echo \#\PBS -l walltime=$error_walltime >> $job
#    echo \#\PBS -l mem=$error_mem >> $job
#    echo \#\PBS -l ncpus=$error_ncpus >> $job
#    echo \#\PBS -l wd >> $job
#    echo \#\PBS -q normal >> $job
#    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $job
#    echo ~/repo/gamma_insar/check_slave_coregistration.bash $proj_dir/$proc_file 1 >> $job
#    chmod +x $job
#    qsub $job

elif [ $coregister == no -a $platform == NCI ]; then
    echo ""
    echo "Option to coregister slaves to master scene not selected."
    echo ""
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
    ifm_batch_dir=$batch_dir/ifm_jobs
    ifm_manual_dir=$manual_dir/ifm_jobs

    # Maximum number of jobs to be run (maximum is 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $ifm_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a process_ifm in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_job_prefix=ifm_

    if [ -f $beam_list ]; then # if beam list exists

	CREATE_BEAM_IFMS()
	{
	    echo ""
	    echo "Creating interferograms..."
            # Set up bperp results file
	    cd $proj_dir/$track_dir
	    results_file=$proj_dir/$track_dir/ifm_bperp_results"_"$beam_num"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
	    echo "Interferogram bperp & btemp Results "$beam_num" "$ifm_rlks"rlks "$ifm_alks"alks" > $results_file
	    echo "" >> $results_file
	    echo "Interferogram_Pair" > temp1
	    echo "bperp_Value" > temp2
	    echo "btemp_Value" > temp3
	    paste temp1 temp2 temp3 >> $results_file
	    rm -f temp1 temp2 temp3

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$ifm_mem >> $job
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $coregister == yes -a $platform == NCI ]; then
			co_slc_jobid=`awk '{print $1}' $batch_dir/slc_coreg_jobs/$beam_num/"all_co_slc_"$beam_num"_job_id"`
			echo \#\PBS -W depend=afterok:$co_slc_jobid >> $job
		    else
			:
		    fi
		    for(( n=0; n<nsteps; n++ )); do
			read line
			echo $line
			mas=`echo $line | awk 'BEGIN {FS=","} ; {print $1}'`
			slv=`echo $line | awk 'BEGIN {FS=","} ; {print $2}'`
			echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $job
 		    done
		    chmod +x $job
		    qsub $job | tee $ifm_batch_dir/$beam_num/"ifm_"$beam_num"_"$i"_job_id"
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
	    cd $ifm_manual_dir/$beam_num
	    while read list; do
		mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
		slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
		mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		job="ifm_"$beam_num"_"$mas_name-$slv_name
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$ifm_walltime >> $job
		echo \#\PBS -l mem=$ifm_mem >> $job
		echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $job
		chmod +x $job
	    done < $ifm_list

            # run ifm error check
	    echo "Preparing error collation for 'create_ifms'..."
	    cd $ifm_batch_dir/$beam_num
	    job="ifm_err_check_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 8 $beam_num >> $job
	    chmod +x $job
	    qsub $job

   	    # run post ifm processing
	    echo "Running post interferogram processing..."
	    cd $ifm_batch_dir/$beam_num
	    ifm_post="post_ifm_"$beam_num"_processing"
	    echo \#\!/bin/bash > $ifm_post
	    echo \#\PBS -lother=gdata1 >> $ifm_post
	    echo \#\PBS -l walltime=$post_walltime >> $ifm_post
	    echo \#\PBS -l mem=$post_mem >> $ifm_post
	    echo \#\PBS -l ncpus=$post_ncpus >> $ifm_post
	    echo \#\PBS -l wd >> $ifm_post
	    echo \#\PBS -q normal >> $ifm_post
	    echo \#\PBS -W depend=afterok:$dep >> $ifm_post
	    echo ~/repo/gamma_insar/post_ifm_processing.bash $proj_dir/$proc_file 1 $ifm_rlks $ifm_alks $beam_num >> $ifm_post
	    chmod +x $ifm_post
	    qsub $ifm_post
	}

	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes -a $coregister_dem == yes -a $coregister == yes -a $do_ifms == yes ]; then
		    if [ ! -e $ifm_list ]; then # if ifm list doesn't exist
			echo ""
			echo "Interferogram list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
			:
		    else # ifm list exists
			CREATE_BEAM_IFMS
		    fi
		else # process as normal
		    CREATE_BEAM_IFMS
		fi
	    fi
	done < $beam_list

        # create dependency list (make sure all post ifm processing is finished before mosaicing)
	cd $ifm_batch_dir
	ls post_ifm_*_job_id > list1
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
	sed s'/.$//' list5 > all_post_ifm_job_id # remove last :
	dep=`awk '{print $1}' all_post_ifm_job_id`
	rm -rf list* post_ifm_*_job_id

        # mosaic beam interferograms
	num_beams=`wc -l < $beam_list`
	cd $ifm_batch_dir
	if [ $num_beams -gt 1 ]; then
	    mosaic=mosaic_beam_ifms
	    echo \#\!/bin/bash > $mosaic
	    echo \#\PBS -lother=gdata1 >> $mosaic
	    echo \#\PBS -l walltime=$mosaic_walltime >> $mosaic
	    echo \#\PBS -l mem=$mosaic_mem >> $mosaic
	    echo \#\PBS -l ncpus=$mosaic_ncpus >> $mosaic
	    echo \#\PBS -l wd >> $mosaic
	    echo \#\PBS -q normal >> $mosaic
	    echo \#\PBS -W depend=afterok:$dep >> $mosaic
	    echo ~/repo/gamma_insar/mosaic_beam_ifms.bash $proj_dir/$proc_file >> $mosaic
	    chmod +x $mosaic
#	    qsub $mosaic | tee mosaic_job_id

            # run mosaic ifm error check
	    cd $ifm_batch_dir
	    mosaic_jobid=`sed s/.r-man2// mosaic_job_id`
	    job=mosaic_ifm_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$mosaic_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 8 >> $job
	    chmod +x $job
#	    qsub $job
	else
	    :
	fi
    else # no beam list

	## Functions
	CREATE_IFMS()
	{
	    echo ""
	    echo "Creating interferograms..."
            # Set up bperp results file
	    cd $proj_dir/$track_dir
	    results_file=$proj_dir/$track_dir/ifm_bperp_results"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
	    echo "Interferogram bperp & btemp Results "$ifm_rlks"rlks "$ifm_alks"alks" > $results_file
	    echo "" >> $results_file
	    echo "Interferogram_Pair" > temp1
	    echo "bperp_Value" > temp2
	    echo "btemp_Value" > temp3
	    paste temp1 temp2 temp3 >> $results_file
	    rm -f temp1 temp2 temp3

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$ifm_mem >> $job
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $coregister == yes -a $platform == NCI ]; then
			co_slc_jobid=`awk '{print $1}' $batch_dir/slc_coreg_jobs/all_co_slc_job_id`
			echo \#\PBS -W depend=afterok:$co_slc_jobid >> $job
		    else
			:
		    fi
		    for(( n=0; n<nsteps; n++ )); do
			read line
			echo $line
			mas=`echo $line | awk 'BEGIN {FS=","} ; {print $1}'`
			slv=`echo $line | awk 'BEGIN {FS=","} ; {print $2}'`
			echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $job
 		    done
		    chmod +x $job
		    qsub $job | tee $ifm_batch_dir/"ifm_"$i"_job_id"
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
	    cd $ifm_manual_dir
	    while read list; do
		mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
		slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
		mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		job="ifm_"$mas_name-$slv_name
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$ifm_walltime >> $job
		echo \#\PBS -l mem=$ifm_mem >> $job
		echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $job
		chmod +x $job
	    done < $ifm_list

            # run ifm error check
	    echo "Preparing error collation for 'create_ifms'..."
	    cd $ifm_batch_dir
	    job=ifm_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 8 >> $job
	    chmod +x $job
	    qsub $job

            # run post ifm processing
	    echo "Running post interferogram processing..."
	    cd $ifm_batch_dir
	    ifm_post=post_ifm_processing
	    echo \#\!/bin/bash > $ifm_post
	    echo \#\PBS -lother=gdata1 >> $ifm_post
	    echo \#\PBS -l walltime=$post_walltime >> $ifm_post
	    echo \#\PBS -l mem=$post_mem >> $ifm_post
	    echo \#\PBS -l ncpus=$post_ncpus >> $ifm_post
	    echo \#\PBS -l wd >> $ifm_post
	    echo \#\PBS -q normal >> $ifm_post
	    echo \#\PBS -W depend=afterok:$dep >> $ifm_post
	    echo ~/repo/gamma_insar/post_ifm_processing.bash $proj_dir/$proc_file 1 $ifm_rlks $ifm_alks >> $ifm_post
	    chmod +x $ifm_post
	    qsub $ifm_post
	}

	if [ $do_setup == yes -a $do_raw == yes -a $do_slc == yes -a $coregister_dem == yes -a $coregister == yes -a $do_ifms == yes ]; then
	    if [ ! -e $ifm_list ]; then # if ifm list doesn't exist
		echo ""
		echo "Interferogram list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
		:
	    else # ifm list exists
		CREATE_IFMS
	    fi
	else # process as normal
	    CREATE_IFMS
	fi
    fi
elif [ $do_ifms == no -a $platform == NCI ]; then
    echo ""
    echo "Option to create interferograms not selected."
    echo ""
else
    :
fi




##########################   SETUP TO ADD NEW DATA TO EXISTING COLLECTION   ##########################


#### GA ####
#if [ $add_scenes == yes -a $platform == GA ]; then
#elif [ $add_scenes == no -a $platform == GA ]; then

#### NCI ####

if [ $add_scenes == yes -a $platform == NCI ]; then
    echo "Creating lists for addtional scenes and extracting data..."
    echo " "
    cd $proj_dir

    cd $batch_dir
    rm -rf add_* #remove any 'add' directories that may exist from previous 'add additional scenes' processing

# create new working directories
    if [ -f $beam_list ]; then # if beams exist
	while read beam_num; do
	    mkdir -p $proj_dir/$track_dir/batch_jobs/add_slc_jobs
	    mkdir -p $proj_dir/$track_dir/batch_jobs/add_slc_coreg_jobs
	    mkdir -p $proj_dir/$track_dir/batch_jobs/add_ifm_jobs
	    mkdir -p $proj_dir/$track_dir/batch_jobs/add_slc_jobs/$beam_num
	    mkdir -p $proj_dir/$track_dir/batch_jobs/add_slc_coreg_jobs/$beam_num
	    mkdir -p $proj_dir/$track_dir/batch_jobs/add_ifm_jobs/$beam_num
	done < $beam_list
    else # no beam
	mkdir -p $proj_dir/$track_dir/batch_jobs/add_slc_jobs
	mkdir -p $proj_dir/$track_dir/batch_jobs/add_slc_coreg_jobs
	mkdir -p $proj_dir/$track_dir/batch_jobs/add_ifm_jobs
    fi

    if [ ! -f $add_scene_list ]; then # if additional scene list doesn't exist
# create add_scenes.list file
	echo "Creating additional scenes list file..."
	job1=add_scene_list_gen
	echo \#\!/bin/bash > $job1
	echo \#\PBS -lother=gdata1 >> $job1
	echo \#\PBS -l walltime=$list_walltime >> $job1
	echo \#\PBS -l mem=$list_mem >> $job1
	echo \#\PBS -l ncpus=$list_ncpus >> $job1
	echo \#\PBS -l wd >> $job1
	echo \#\PBS -q copyq >> $job1
	echo ~/repo/gamma_insar/create_scenes_list.bash $proj_dir/$proc_file 2 >> $job1
	chmod +x $job1
	qsub $job1 | tee add_scene_list_job_id

# extract raw data
	echo "Extracting additional raw data..."
	add_scene_list_jobid=`sed s/.r-man2// $batch_dir/add_scene_list_job_id`
	cd $batch_dir
	job=add_extract_raw
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=$raw_walltime >> $job
	echo \#\PBS -l mem=$raw_mem >> $job
	echo \#\PBS -l ncpus=$raw_ncpus >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q copyq >> $job
	echo \#\PBS -W depend=afterok:$add_scene_list_jobid >> $job
	echo ~/repo/gamma_insar/extract_raw_data.bash $proj_dir/$proc_file 2 >> $job
	chmod +x $job
	qsub $job | tee add_raw_job_id

# create add_slaves.list file
	echo "Creating additional slaves list file..."
	job2=add_slave_list_gen
	echo \#\!/bin/bash > $job2
	echo \#\PBS -lother=gdata1 >> $job2
	echo \#\PBS -l walltime=$list_walltime >> $job2
	echo \#\PBS -l mem=$list_mem >> $job2
	echo \#\PBS -l ncpus=$list_ncpus >> $job2
	echo \#\PBS -l wd >> $job2
	echo \#\PBS -q normal >> $job2
	echo \#\PBS -W depend=afterok:$add_scene_list_jobid >> $job2
	echo ~/repo/gamma_insar/create_slaves_list.bash $proj_dir/$proc_file 2 >> $job2
	chmod +x $job2
	qsub $job2 | tee add_slave_list_job_id

# create add_ifms.list file
	echo "Creating additional interferogram list file..."
	job3=add_ifm_list_gen
	echo \#\!/bin/bash > $job3
	echo \#\PBS -lother=gdata1 >> $job3
	echo \#\PBS -l walltime=$list_walltime >> $job3
	echo \#\PBS -l mem=$list_mem >> $job3
	echo \#\PBS -l ncpus=$list_ncpus >> $job3
	echo \#\PBS -l wd >> $job3
	echo \#\PBS -q normal >> $job3
	echo \#\PBS -W depend=afterok:$add_scene_list_jobid >> $job3
	echo ~/repo/gamma_insar/create_ifms_list.bash $proj_dir/$proc_file 2 >> $job3
	chmod +x $job3
	qsub $job3 | tee add_ifm_list_job_id


# run setup error check
	echo "Preparing error collation for 'add_scenes'..."
	cd $batch_dir
	add_slave_list_jobid=`sed s/.r-man2// add_slave_list_job_id`
	add_ifm_list_jobid=`sed s/.r-man2// add_ifm_list_job_id`
	job=add_setup_err_check
	echo \#\!/bin/bash > $job
	echo \#\PBS -lother=gdata1 >> $job
	echo \#\PBS -l walltime=$error_walltime >> $job
	echo \#\PBS -l mem=$error_mem >> $job
	echo \#\PBS -l ncpus=$error_ncpus >> $job
	echo \#\PBS -l wd >> $job
	echo \#\PBS -q normal >> $job
	echo \#\PBS -W depend=afterany:$add_scene_list_jobid:$add_slave_list_jobid:$add_ifm_list_jobid >> $job
	echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 11 >> $job
	chmod +x $job
	qsub $job
    else # add scene list exists
	:
    fi
elif [ $add_scenes == no -a $platform == NCI ]; then
    echo ""
    echo "Option to setup directories and lists for additional scenes not selected."
    echo ""
else
    :
fi




##########################   ADD SLCS TO EXISTING SLC COLLECTION   ##########################


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

#if [ $add_slc == yes -a $platform == GA ]; then

if [ $add_slc == yes -a $platform == NCI ]; then

# create additional SLCs
     slc_batch_dir=$batch_dir/add_slc_jobs
     slc_manual_dir=$manual_dir/slc_jobs

    # Maximum number of jobs to be run (no more than 50)
     maxjobs=50

    # PBS parameters
     wt1=`echo $slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a single process_slc in minutes

    # Parameters for a set of jobs
     job_dir_prefix=job_
     pbs_job_prefix=add_slc_

     if [ -f $beam_list ]; then # if beam list exists
	 while read beam_num; do
	     if [ ! -z $beam_num ]; then
		 cd $slc_batch_dir/$beam_num
		 if [ $add_scenes == yes -a $add_slc == yes ]; then
		     if [ ! -e $add_scene_list ]; then # if additional scene list doesn't exist
			 echo ""
			 echo "Additional scene list doesn't exist yet, preparing to rerun process_gamma.bash after list is created to create additional SLCs..."
		         # rerun process_gamma.bash once additional SLC list is created
			 cd $proj_dir
			 add_raw_jobid=`sed s/.r-man2// $batch_dir/add_raw_job_id`
			 job=process_$track_dir"_"$beam_num"_auto_rerun"
			 echo \#\!/bin/bash > $job
			 echo \#\PBS -lother=gdata1 >> $job
			 echo \#\PBS -l walltime=$list_walltime >> $job
			 echo \#\PBS -l mem=$list_mem >> $job
			 echo \#\PBS -l ncpus=$list_ncpus >> $job
			 echo \#\PBS -l wd >> $job
			 echo \#\PBS -q normal >> $job
			 echo \#\PBS -W depend=afterok:$add_raw_jobid >> $job
			 echo ~/repo/gamma_insar/process_gamma.bash $proc_file >> $job
			 chmod +x $job
			 qsub $job
		     else # additional scene list exists
			 echo ""
			 echo "Creating additional SLC data..."
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
				 job=$pbs_job_prefix$i

				 echo Doing job $i in $jobdir with $job

				 echo \#\!/bin/bash > $job
				 echo \#\PBS -l other=gdata1 >> $job
				 echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
				 echo \#\PBS -l mem=$slc_mem >> $job
				 echo \#\PBS -l ncpus=$slc_ncpus >> $job
				 echo \#\PBS -l wd >> $job
				 echo \#\PBS -q normal >> $job
				 echo -e "\n" >> $job
				 for(( n=0; n<nsteps; n++ )); do
				     read scene
				     echo $scene
				     if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
					 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
				     else
					 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
					 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
				     fi
        			 done
				 chmod +x $job
				 qsub $job | tee $slc_batch_dir/$beam_num/"add_slc_"$beam_num"_"$i"_job_id"
				 cd ..
			     done
			 }

                        # Work starts here
			 cd $slc_batch_dir/$beam_num
			 nlines=`cat $add_scene_list | sed '/^\s*$/d' | wc -l`
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
			 } < $add_scene_list

	                # create dependency list (make sure all slcs are finished before error consolidation)
			 cd $slc_batch_dir/$beam_num
			 ls "add_slc_"$beam_num"_"*"_job_id" > list1
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
			 sed s'/.$//' list5 > "all_add_slc_"$beam_num"_job_id" # remove last :
			 dep=`awk '{print $1}' "all_add_slc_"$beam_num"_job_id"`
			 rm -rf list* "add_slc_"$beam_num"_"*"_job_id"

                        # in case future manual processing is required, create manual PBS jobs for each scene
			 cd $slc_manual_dir/$beam_num
			 while read list; do
			     scene=`echo $list | awk '{print $1}'`
			     job="slc_"$beam_num"_"$scene
			     echo \#\!/bin/bash > $job
			     echo \#\PBS -lother=gdata1 >> $job
			     echo \#\PBS -l walltime=$slc_walltime >> $job
			     echo \#\PBS -l mem=$slc_mem >> $job
			     echo \#\PBS -l ncpus=$slc_ncpus >> $job
			     echo \#\PBS -l wd >> $job
			     echo \#\PBS -q normal >> $job
			     if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			     else
				 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
				 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
			     fi
			     chmod +x $job
			 done < $add_scene_list

                        # run slc error check
			 cd $slc_batch_dir/$beam_num
			 job="add_slc_err_"$beam_num"_check"
			 echo \#\!/bin/bash > $job
			 echo \#\PBS -lother=gdata1 >> $job
			 echo \#\PBS -l walltime=$error_walltime >> $job
			 echo \#\PBS -l mem=$error_mem >> $job
			 echo \#\PBS -l ncpus=$error_ncpus >> $job
			 echo \#\PBS -l wd >> $job
			 echo \#\PBS -q normal >> $job
			 echo \#\PBS -W depend=afterany:$dep >> $job
			 echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 12 $beam_num >> $job
			 chmod +x $job
			 qsub $job | tee "add_slc_err_"$beam_num"_job_id"
		     fi
		 fi
	     fi
	 done < $beam_list
     else # no beams
	 cd $slc_batch_dir
	 if [ $add_scenes == yes -a $add_slc == yes ]; then
	     if [ ! -e $add_scene_list ]; then # if additional scene list doesn't exist
		 echo ""
		 echo "Additional scene list doesn't exist yet, preparing to rerun process_gamma.bash after list is created to create additional SLCs..."
		         # rerun process_gamma.bash once additional SLC list is created
		 cd $proj_dir
		 add_raw_jobid=`sed s/.r-man2// $batch_dir/add_raw_job_id`
		 job=process_$track_dir"_auto_rerun"
		 echo \#\!/bin/bash > $job
		 echo \#\PBS -lother=gdata1 >> $job
		 echo \#\PBS -l walltime=$list_walltime >> $job
		 echo \#\PBS -l mem=$list_mem >> $job
		 echo \#\PBS -l ncpus=$list_ncpus >> $job
		 echo \#\PBS -l wd >> $job
		 echo \#\PBS -q normal >> $job
		 echo \#\PBS -W depend=afterok:$add_raw_jobid >> $job
		 echo ~/repo/gamma_insar/process_gamma.bash $proc_file >> $job
		 chmod +x $job
		 qsub $job
	     else # additional scene list exists
		 echo ""
		 echo "Creating additional SLC data..."
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
        		 job=$pbs_job_prefix$i
			 echo Doing job $i in $jobdir with $job
			 echo \#\!/bin/bash > $job
			 echo \#\PBS -l other=gdata1 >> $job
			 echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
			 echo \#\PBS -l mem=$slc_mem >> $job
			 echo \#\PBS -l ncpus=$slc_ncpus >> $job
			 echo \#\PBS -l wd >> $job
			 echo \#\PBS -q normal >> $job
			 echo -e "\n" >> $job

			 for(( n=0; n<nsteps; n++ )); do
			     read scene
			     echo $scene
			     if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
				 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			     else
				 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
				 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
			     fi
        		 done
			 chmod +x $job
			 qsub $job | tee $slc_batch_dir/"add_slc_"$i"_job_id"
			 cd ..
		     done
		 }
                # Work starts here
		 cd $slc_batch_dir
		 nlines=`cat $add_scene_list | sed '/^\s*$/d' | wc -l`
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
		 } < $add_scene_list

    	        # create dependency list (make sure all slcs are finished before error consolidation)
		 cd $slc_batch_dir
		 ls "add_slc_"*"_job_id" > list1
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
		 sed s'/.$//' list5 > all_add_slc_job_id # remove last :
		 dep=`awk '{print $1}' all_add_slc_job_id`
		 rm -rf list* "add_slc_"*"_job_id"

                # in case future manual processing is required, create manual PBS jobs for each scene
		 cd $slc_manual_dir
		 while read list; do
		     scene=`echo $list | awk '{print $1}'`
		     job="slc_"$scene
		     echo \#\!/bin/bash > $job
		     echo \#\PBS -lother=gdata1 >> $job
		     echo \#\PBS -l walltime=$slc_walltime >> $job
		     echo \#\PBS -l mem=$slc_mem >> $job
		     echo \#\PBS -l ncpus=$slc_ncpus >> $job
		     echo \#\PBS -l wd >> $job
		     echo \#\PBS -q normal >> $job
		     if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		     else
			 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			 echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		     fi
		     chmod +x $job
		 done < $add_scene_list

                # run slc error check
		 cd $slc_batch_dir
		 job=add_slc_err_check
		 echo \#\!/bin/bash > $job
		 echo \#\PBS -lother=gdata1 >> $job
		 echo \#\PBS -l walltime=$error_walltime >> $job
		 echo \#\PBS -l mem=$error_mem >> $job
		 echo \#\PBS -l ncpus=$error_ncpus >> $job
		 echo \#\PBS -l wd >> $job
		 echo \#\PBS -q normal >> $job
		 echo \#\PBS -W depend=afterany:$dep >> $job
		 echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 12 >> $job
		 chmod +x $job
		 qsub $job
	     fi
	 else # process as normal
	     echo ""
	     echo "Creating additional SLC data..."
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
        	     job=$pbs_job_prefix$i
		     echo Doing job $i in $jobdir with $job
		     echo \#\!/bin/bash > $job
		     echo \#\PBS -l other=gdata1 >> $job
		     echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		     echo \#\PBS -l mem=$slc_mem >> $job
		     echo \#\PBS -l ncpus=$slc_ncpus >> $job
		     echo \#\PBS -l wd >> $job
		     echo \#\PBS -q normal >> $job
		     echo -e "\n" >> $job

		     for(( n=0; n<nsteps; n++ )); do
			 read scene
			 echo $scene
			 if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			     echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			 else
			     echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			     echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
			 fi
        	     done
		     chmod +x $job
		     qsub $job | tee $slc_batch_dir/"add_slc_"$i"_job_id"
		     cd ..
		 done
	     }

            # Work starts here
	     cd $slc_batch_dir
	     nlines=`cat $add_scene_list | sed '/^\s*$/d' | wc -l`
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
	     } < $add_scene_list

            # create dependency list (make sure all slcs are finished before error consolidation)
	     cd $slc_batch_dir
	     ls "add_slc_"*"_job_id" > list1
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
	     sed s'/.$//' list5 > all_add_slc_job_id # remove last :
	     dep=`awk '{print $1}' all_add_slc_job_id`
	     rm -rf list* "add_slc_"*"_job_id"

            # in case future manual processing is required, create manual PBS jobs for each scene
	     cd $slc_manual_dir
	     while read list; do
		 scene=`echo $list | awk '{print $1}'`
		 job="slc_"$scene
		 echo \#\!/bin/bash > $job
		 echo \#\PBS -lother=gdata1 >> $job
		 echo \#\PBS -l walltime=$slc_walltime >> $job
		 echo \#\PBS -l mem=$slc_mem >> $job
		 echo \#\PBS -l ncpus=$slc_ncpus >> $job
		 echo \#\PBS -l wd >> $job
		 echo \#\PBS -q normal >> $job
		 if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		     echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		 else
		     echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		     echo ~/repo/gamma_insar/"process_"$sensor"_SLC.bash" $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		 fi
		 chmod +x $job
	     done < $add_scene_list

            # run slc error check
	     echo "Preparing error collation for 'add_slc'..."
	     cd $slc_batch_dir
	     job=add_slc_err_check
	     echo \#\!/bin/bash > $job
	     echo \#\PBS -lother=gdata1 >> $job
	     echo \#\PBS -l walltime=$error_walltime >> $job
	     echo \#\PBS -l mem=$error_mem >> $job
	     echo \#\PBS -l ncpus=$error_ncpus >> $job
	     echo \#\PBS -l wd >> $job
	     echo \#\PBS -q normal >> $job
	     echo \#\PBS -W depend=afterany:$dep >> $job
	     echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 11 >> $job
	     chmod +x $job
	     qsub $job
	     fi
	     fi
elif [ $add_slc == no -a $platform == NCI ]; then
    echo ""
    echo "Option to create additional SLC data not selected."
    echo ""
else
    :
fi





##########################   COREGISTER ADDITIONAL SLAVE SCENES TO MASTER SCENE   ##########################

if [ $sensor == S1 -a $mode == IWS ]; then
    coreg_script=coregister_S1_slave_SLC.bash
else
    coreg_script=coregister_slave_SLC.bash
fi


#### GA ####

if [ $coregister_add == yes -a $platform == GA ]; then
    :

#### NCI ####

elif [ $coregister_add == yes -a $platform == NCI ]; then
    echo "Coregistering additional slave scenes to master scene..."
    co_slc_batch_dir=$batch_dir/add_slc_coreg_jobs
    co_slc_manual_dir=$manual_dir/slc_coreg_jobs

    # Maximum number of jobs to be run (maximum number is 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $co_slc_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a single coreg_slc in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_job_prefix=add_co_slc_

    if [ -f $beam_list ]; then # if beam list exists

	## Functions
	ADD_COREG_BEAM_SLAVE()
	{
	    echo ""
	    echo "Coregistering additional slave scenes to reference master scene..."
            # Set up coregistration results file
	    cd $proj_dir/$track_dir
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		check_file=$proj_dir/$track_dir/slave_coreg_results"_"$beam_num"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$beam_num" "$slc_rlks"rlks "$slc_alks"alks" > $check_file
		echo "final model fit std. dev. (samples)" >> $check_file
		echo "Ref Master" > temp1_$beam_num
		echo "Slave" > temp2_$beam_num
		echo "Range" > temp3_$beam_num
		echo "Azimuth" > temp4_$beam_num
		paste temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num >> $check_file
		rm -f temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num
	    else
		slc_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$beam_num"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$beam_num" "$slc_rlks"rlks "$slc_alks"alks" > $slc_check_file
		echo "final model fit std. dev. (samples)" >> $slc_check_file
		echo "Ref Master" > temp1_$beam_num
		echo "Slave" > temp2_$beam_num
		echo "Range" > temp3_$beam_num
		echo "Azimuth" > temp4_$beam_num
		paste temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num >> $slc_check_file
		rm -f temp1_$beam_num temp2_$beam_num temp3_$beam_num temp4_$beam_num

		ifm_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$beam_num"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
		echo "Slave Coregistration Results "$beam_num" "$ifm_rlks"rlks "$ifm_alks"alks" > $ifm_check_file
		echo "final model fit std. dev. (samples)" >> $ifm_check_file
		echo "Ref Master" > temp5_$beam_num
		echo "Slave" > temp6_$beam_num
		echo "Range" > temp7_$beam_num
		echo "Azimuth" > temp8_$beam_num
		paste temp5_$beam_num temp6_$beam_num temp7_$beam_num temp8_$beam_num >> $ifm_check_file
		rm -f temp5_$beam_num temp6_$beam_num temp7_$beam_num temp8_$beam_num
	    fi

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$co_slc_mem >> $job
		    echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $add_slc == yes -a $platform == NCI ]; then
			add_slc_jobid=`awk '{print $1}' all_add_slc_job_id`
			echo \#\PBS -W depend=afterok:$add_slc_jobid >> $job
		    else
			:
		    fi
        	    for(( n=0; n<nsteps; n++ )); do
                	read scene
                	echo $scene
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			else
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
			fi
		    done
		    chmod +x $job
		    qsub $job | tee $co_slc_batch_dir/$beam_num/"add_co_slc_"$beam_num"_"$i"_job_id"
		    cd ..
		done
	    }
            # Work starts here
	    cd $co_slc_batch_dir/$beam_num
	    nlines=`cat $add_slave_list | sed '/^\s*$/d' | wc -l`
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

	    } < $add_slave_list

	    # create dependency list (make sure all coreg slcs are finished before error consolidation)
	    cd $co_slc_batch_dir/$beam_num
	    ls "add_co_slc_"$beam_num"_"*"_job_id" > list1
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
	    sed s'/.$//' list5 > "all_add_co_slc_"$beam_num"_job_id" # remove last :
	    dep=`awk '{print $1}' "all_add_co_slc_"$beam_num"_job_id"`
	    rm -rf list* "add_co_slc_"$beam_num"_"*"_job_id"

            # in case future manual processing is required, create manual PBS jobs for each slave
	    cd $co_slc_manual_dir/$beam_num
	    while read list; do
		scene=`echo $list | awk '{print $1}'`
		job="co_slc_"$beam_num"_"$scene
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$co_slc_walltime >> $job
		echo \#\PBS -l mem=$co_slc_mem >> $job
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
		else
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks $beam_num >> $job
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks $beam_num >> $job
		fi
		chmod +x $job
	    done < $add_slave_list

            # run coreg slc error check
	    echo "Preparing error collation for 'additional coregister_slaves'..."
	    cd $co_slc_batch_dir/$beam_num
	    job="add_co_slc_err_check_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 13 $beam_num >> $job
	    chmod +x $job
	    qsub $job
	}

	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		if [ $add_scenes == yes -a $add_slc == yes -a $coregister_add == yes ]; then
		    if [ ! -e $add_slave_list ]; then # if slave list doesn't exist
			echo ""
			echo "Additional slave list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
			:
		    else # slave list exists
			ADD_COREG_BEAM_SLAVE
		    fi
		else # process as normal
		    ADD_COREG_BEAM_SLAVE
		fi
	    fi
	done < $beam_list
    else # no beams

	## Functions
	ADD_COREG_SLAVE()
	{
	    echo ""
	    echo "Coregistering additional slave scenes to reference master scene..."
            # Set up coregistration results file
	    cd $proj_dir/$track_dir
	    if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		check_file=$proj_dir/$track_dir/slave_coreg_results"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$slc_rlks"rlks "$slc_alks"alks" > $check_file
		echo "final offset poly. coeff." >> $check_file
		echo "Ref Master" > temp1
		echo "Slave" > temp2
		echo "Range" > temp3
		echo "Azimuth" > temp4
		paste temp1 temp2 temp3 temp4 >> $check_file
		rm -f temp1 temp2 temp3 temp4
	    else
		slc_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$slc_rlks"rlks_"$slc_alks"alks.txt"
		echo "Slave Coregistration Results "$slc_rlks"rlks "$slc_alks"alks" > $slc_check_file
		echo "final offset poly. coeff." >> $slc_check_file
		echo "Ref Master" > temp1
		echo "Slave" > temp2
		echo "Range" > temp3
		echo "Azimuth" > temp4
		paste temp1 temp2 temp3 temp4 >> $slc_check_file
		rm -f temp1 temp2 temp3 temp4

		ifm_check_file=$proj_dir/$track_dir/slave_coreg_results"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
		echo "Slave Coregistration Results "$ifm_rlks"rlks "$ifm_alks"alks" > $ifm_check_file
		echo "final offset poly. coeff." >> $ifm_check_file
		echo "Ref Master" > temp5
		echo "Slave" > temp6
		echo "Range" > temp7
		echo "Azimuth" > temp8
		paste temp5 temp6 temp7 temp8 >> $ifm_check_file
		rm -f temp5 temp6 temp7 temp8
	    fi

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$co_slc_mem >> $job
		    echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $add_slc == yes -a $platform == NCI ]; then
			add_slc_jobid=`awk '{print $1}' $batch_dir/add_slc_jobs/all_add_slc_job_id`
			echo \#\PBS -W depend=afterok:$add_slc_jobid >> $job
		    else
			:
		    fi
		    for(( n=0; n<nsteps; n++ )); do
			read scene
			echo $scene
			if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			else
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
			    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
			fi
        	    done
		    chmod +x $job
		    qsub $job | tee $co_slc_batch_dir/"add_co_slc_"$i"_job_id"
		    cd ..
		done
	    }
            # Work starts here
	    cd $co_slc_batch_dir
	    nlines=`cat $add_slave_list | sed '/^\s*$/d' | wc -l`
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

	    } < $add_slave_list

            # create dependency list (make sure all coreg slcs are finished before error consolidation)
	    cd $co_slc_batch_dir
	    ls "add_co_slc_"*"_job_id" > list1
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
	    sed s'/.$//' list5 > all_add_co_slc_job_id # remove last :
	    dep=`awk '{print $1}' all_add_co_slc_job_id`
	    rm -rf list* "add_co_slc_"*"_job_id"

            # in case future manual processing is required, create manual PBS jobs for each scene
	    cd $co_slc_manual_dir
	    while read list; do
		scene=`echo $list | awk '{print $1}'`
		job="co_slc_"$scene
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$co_slc_walltime >> $job
		echo \#\PBS -l mem=$co_slc_mem >> $job
		echo \#\PBS -l ncpus=$co_slc_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		if [ $slc_rlks -eq $ifm_rlks -a $slc_alks -eq $ifm_alks ]; then
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		else
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $slc_rlks $slc_alks >> $job
		    echo ~/repo/gamma_insar/$coreg_script $proj_dir/$proc_file $scene $ifm_rlks $ifm_alks >> $job
		fi
		chmod +x $job
	    done < $add_slave_list

            # run coreg slc error check
	    echo "Preparing error collation for additional 'coregister_slaves'..."
	    cd $co_slc_batch_dir
	    job=add_co_slc_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 13 >> $job
	    chmod +x $job
	    qsub $job
	}
	if [ $add_scenes == yes -a $add_slc == yes -a $coregister_add == yes ]; then
	    if [ ! -e $add_slave_list ]; then # if slave list doesn't exist
		echo ""
		echo "Additional slave list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
		:
	    else # slave list exists
		ADD_COREG_SLAVE
	    fi
	else # process as normal
	    ADD_COREG_SLAVE
	fi
    fi

    # PBS job for checking slave coregistration  - doesn't work, won't display window
#    job=check_slc_coreg
#    co_slc_jobid=`sed s/.r-man2// co_slc_err_job_id`
#    echo \#\!/bin/bash > $job
#    echo \#\PBS -lother=gdata1 >> $job
#    echo \#\PBS -l walltime=$error_walltime >> $job
#    echo \#\PBS -l mem=$error_mem >> $job
#    echo \#\PBS -l ncpus=$error_ncpus >> $job
#    echo \#\PBS -l wd >> $job
#    echo \#\PBS -q normal >> $job
#    echo \#\PBS -W depend=afterok:$co_slc_jobid >> $job
#    echo ~/repo/gamma_insar/check_slave_coregistration.bash $proj_dir/$proc_file 1 >> $job
#    chmod +x $job
#    qsub $job
elif [ $coregister_add == no -a $platform == NCI ]; then
    echo ""
    echo "Option to coregister additional slaves to master scene not selected."
    echo ""
else
    :
fi




##########################   PROCESS ADDITIONAL INTERFEROGRAMS AND GEOCODE UNWRAPPED FILES   ##########################


#### GA ####

if [ $add_ifms == yes -a $platform == GA ]; then
    :

#### NCI ####

elif [ $add_ifms == yes -a $platform == NCI ]; then
    ifm_batch_dir=$batch_dir/add_ifm_jobs
    ifm_manual_dir=$manual_dir/ifm_jobs

    # Maximum number of jobs to be run (maximum is 50)
    maxjobs=50

    # PBS parameters
    wt1=`echo $ifm_walltime | awk -F: '{print ($1*60) + $2 + ($3/60)}'` #walltime for a process_ifm in minutes

    # Parameters for a set of jobs
    job_dir_prefix=job_
    pbs_job_prefix=add_ifm_

    if [ -f $beam_list ]; then # if beam list exists

	CREATE_ADD_BEAM_IFMS()
	{
	    echo ""
	    echo "Creating additional interferograms..."
            # Set up bperp results file
	    cd $proj_dir/$track_dir
	    results_file=$proj_dir/$track_dir/ifm_bperp_results"_"$beam_num"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
	    echo "Interferogram bperp & btemp Results "$beam_num" "$ifm_rlks"rlks "$ifm_alks"alks" > $results_file
	    echo "" >> $results_file
	    echo "Interferogram_Pair" > temp1
	    echo "bperp_Value" > temp2
	    echo "btemp_Value" > temp3
	    paste temp1 temp2 temp3 >> $results_file
	    rm -f temp1 temp2 temp3

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$ifm_mem >> $job
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $coregister_add == yes -a $platform == NCI ]; then
			add_co_slc_jobid=`awk '{print $1}' $batch_dir/add_slc_coreg_jobs/$beam_num/"all_add_co_slc_"$beam_num"_job_id"`
			echo \#\PBS -W depend=afterok:$add_co_slc_jobid >> $job
		    else
			:
		    fi
		    for(( n=0; n<nsteps; n++ )); do
			read line
			echo $line
			mas=`echo $line | awk 'BEGIN {FS=","} ; {print $1}'`
			slv=`echo $line | awk 'BEGIN {FS=","} ; {print $2}'`
			echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $job
 		    done
		    chmod +x $job
		    qsub $job | tee $ifm_batch_dir/$beam_num/"add_ifm_"$beam_num"_"$i"_job_id"
		    cd ..
		done
	    }
            # Work starts here
	    cd $ifm_batch_dir/$beam_num
	    nlines=`cat $add_ifm_list | sed '/^\s*$/d' | wc -l`
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

	    } < $add_ifm_list

	    # create dependency list (make sure all ifms are finished before error consolidation)
	    cd $ifm_batch_dir/$beam_num
	    ls "add_ifm_"$beam_num"_"*"_job_id" > list1
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
	    sed s'/.$//' list5 > "all_add_ifm_"$beam_num"_job_id" # remove last :
	    dep=`awk '{print $1}' "all_add_ifm_"$beam_num"_job_id"`
	    rm -rf list* "add_ifm_"$beam_num"_"*"_job_id"

            # in case future manual processing is required, create manual PBS jobs for each ifm
	    cd $ifm_manual_dir/$beam_num
	    while read list; do
		mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
		slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
		mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		job="ifm_"$beam_num"_"$mas_name-$slv_name
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$ifm_walltime >> $job
		echo \#\PBS -l mem=$ifm_mem >> $job
		echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks $beam_num >> $job
		chmod +x $job
	    done < $ifm_list

            # run ifm error check
	    echo "Preparing error collation for additional 'create_ifms'..."
	    cd $ifm_batch_dir/$beam_num
	    job="add_ifm_err_check_"$beam_num
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 14 $beam_num >> $job
	    chmod +x $job
	    qsub $job

   	    # run post ifm processing
	    echo "Running post additional interferogram processing..."
	    cd $ifm_batch_dir/$beam_num
	    ifm_post="add_post_ifm_"$beam_num"_processing"
	    echo \#\!/bin/bash > $ifm_post
	    echo \#\PBS -lother=gdata1 >> $ifm_post
	    echo \#\PBS -l walltime=$post_walltime >> $ifm_post
	    echo \#\PBS -l mem=$post_mem >> $ifm_post
	    echo \#\PBS -l ncpus=$post_ncpus >> $ifm_post
	    echo \#\PBS -l wd >> $ifm_post
	    echo \#\PBS -q normal >> $ifm_post
	    echo \#\PBS -W depend=afterok:$dep >> $ifm_post
	    echo ~/repo/gamma_insar/post_ifm_processing.bash $proj_dir/$proc_file 2 $ifm_rlks $ifm_alks $beam_num >> $ifm_post
	    chmod +x $ifm_post
	    qsub $ifm_post
	}

	while read beam_num; do
	    if [ ! -z $beam_num ]; then
		if [ $add_scenes == yes -a $add_slc == yes -a $coregister_add == yes -a $add_ifms == yes ]; then
		    if [ ! -e $_addifm_list ]; then # if ifm list doesn't exist
			echo ""
			echo "Additional interferogram list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
			:
		    else # ifm list exists
			CREATE_ADD_BEAM_IFMS
		    fi
		else # process as normal
		    CREATE_ADD_BEAM_IFMS
		fi
	    fi
	done < $beam_list

        # create dependency list (make sure all post ifm processing is finished before mosaicing)
	cd $ifm_batch_dir
	ls add_post_ifm_*_job_id > list1
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
	sed s'/.$//' list5 > all_add_post_ifm_job_id # remove last :
	dep=`awk '{print $1}' all_add_post_ifm_job_id`
	rm -rf list* add_post_ifm_*_job_id

        # mosaic beam interferograms
	num_beams=`wc -l < $beam_list`
	cd $ifm_batch_dir
	if [ $num_beams -gt 1 ]; then
	    mosaic=add_mosaic_beam_ifms
	    echo \#\!/bin/bash > $mosaic
	    echo \#\PBS -lother=gdata1 >> $mosaic
	    echo \#\PBS -l walltime=$mosaic_walltime >> $mosaic
	    echo \#\PBS -l mem=$mosaic_mem >> $mosaic
	    echo \#\PBS -l ncpus=$mosaic_ncpus >> $mosaic
	    echo \#\PBS -l wd >> $mosaic
	    echo \#\PBS -q normal >> $mosaic
	    echo \#\PBS -W depend=afterok:$dep >> $mosaic
	    echo ~/repo/gamma_insar/mosaic_beam_ifms.bash $proj_dir/$proc_file >> $mosaic
	    chmod +x $mosaic
#	    qsub $mosaic | tee add_mosaic_job_id

            # run mosaic ifm error check
	    cd $ifm_batch_dir
	    add_mosaic_jobid=`sed s/.r-man2// add_mosaic_job_id`
	    job=add_mosaic_ifm_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$add_mosaic_jobid >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 7 >> $job
	    chmod +x $job
#	    qsub $job
	else
	    :
	fi
    else # no beam list
	cd $ifm_batch_dir

	## Functions
	CREATE_ADD_IFMS()
	{
	    echo ""
	    echo "Creating additional interferograms..."
            # Set up bperp results file
	    cd $proj_dir/$track_dir
	    results_file=$proj_dir/$track_dir/ifm_bperp_results"_"$ifm_rlks"rlks_"$ifm_alks"alks.txt"
	    echo "Interferogram bperp & btemp Results "$ifm_rlks"rlks "$ifm_alks"alks" > $results_file
	    echo "" >> $results_file
	    echo "Interferogram_Pair" > temp1
	    echo "bperp_Value" > temp2
	    echo "btemp_Value" > temp3
	    paste temp1 temp2 temp3 >> $results_file
	    rm -f temp1 temp2 temp3

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
        	    job=$pbs_job_prefix$i

		    echo Doing job $i in $jobdir with $job

		    echo \#\!/bin/bash > $job
		    echo \#\PBS -l other=gdata1 >> $job
		    echo \#\PBS -l walltime=$hh":"$mm":00" >> $job
		    echo \#\PBS -l mem=$ifm_mem >> $job
		    echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		    echo \#\PBS -l wd >> $job
		    echo \#\PBS -q normal >> $job
		    echo -e "\n" >> $job
		    if [ $coregister_add == yes -a $platform == NCI ]; then
			add_co_slc_jobid=`awk '{print $1}' $batch_dir/add_slc_coreg_jobs/all_add_co_slc_job_id`
			echo \#\PBS -W depend=afterok:$add_co_slc_jobid >> $job
		    else
			:
		    fi
		    for(( n=0; n<nsteps; n++ )); do
			read line
			echo $line
			mas=`echo $line | awk 'BEGIN {FS=","} ; {print $1}'`
			slv=`echo $line | awk 'BEGIN {FS=","} ; {print $2}'`
			echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $job
 		    done
		    chmod +x $job
		    qsub $job | tee $ifm_batch_dir/"add_ifm_"$i"_job_id"
		    cd ..
		done
	    }
            # Work starts here
	    cd $ifm_batch_dir
	    nlines=`cat $add_ifm_list | sed '/^\s*$/d' | wc -l`
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

	    } < $add_ifm_list

            # create dependency list (make sure all ifms are finished before error consolidation)
	    cd $ifm_batch_dir
	    ls "add_ifm_"*"_job_id" > list1
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
	    sed s'/.$//' list5 > all_add_ifm_job_id # remove last :
	    dep=`awk '{print $1}' all_add_ifm_job_id`
	    rm -rf list* "add_ifm_"*"_job_id"

            # in case future manual processing is required, create manual PBS jobs for each ifm
	    cd $ifm_manual_dir
	    while read list; do
		mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
		slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
		mas_name=`echo $mas | awk '{print substr($1,3,6)}'`
		slv_name=`echo $slv | awk '{print substr($1,3,6)}'`
		job="ifm_"$mas_name-$slv_name
		echo \#\!/bin/bash > $job
		echo \#\PBS -lother=gdata1 >> $job
		echo \#\PBS -l walltime=$ifm_walltime >> $job
		echo \#\PBS -l mem=$ifm_mem >> $job
		echo \#\PBS -l ncpus=$ifm_ncpus >> $job
		echo \#\PBS -l wd >> $job
		echo \#\PBS -q normal >> $job
		echo ~/repo/gamma_insar/process_ifm.bash $proj_dir/$proc_file $mas $slv $ifm_rlks $ifm_alks >> $job
		chmod +x $job
	    done < $ifm_list

            # run ifm error check
	    echo "Preparing error collation for additional 'create_ifms'..."
	    cd $ifm_batch_dir
	    job=add_ifm_err_check
	    echo \#\!/bin/bash > $job
	    echo \#\PBS -lother=gdata1 >> $job
	    echo \#\PBS -l walltime=$error_walltime >> $job
	    echo \#\PBS -l mem=$error_mem >> $job
	    echo \#\PBS -l ncpus=$error_ncpus >> $job
	    echo \#\PBS -l wd >> $job
	    echo \#\PBS -q normal >> $job
	    echo \#\PBS -W depend=afterany:$dep >> $job
	    echo ~/repo/gamma_insar/collate_nci_errors.bash $proj_dir/$proc_file 14 >> $job
	    chmod +x $job
	    qsub $job

            # run post ifm processing
	    echo "Running post additional interferogram processing..."
	    cd $ifm_batch_dir
	    ifm_post=add_post_ifm_processing
	    echo \#\!/bin/bash > $ifm_post
	    echo \#\PBS -lother=gdata1 >> $ifm_post
	    echo \#\PBS -l walltime=$post_walltime >> $ifm_post
	    echo \#\PBS -l mem=$post_mem >> $ifm_post
	    echo \#\PBS -l ncpus=$post_ncpus >> $ifm_post
	    echo \#\PBS -l wd >> $ifm_post
	    echo \#\PBS -q normal >> $ifm_post
	    echo \#\PBS -W depend=afterok:$dep >> $ifm_post
	    echo ~/repo/gamma_insar/post_ifm_processing.bash $proj_dir/$proc_file 2 $ifm_rlks $ifm_alks >> $ifm_post
	    chmod +x $ifm_post
	    qsub $ifm_post
	}

	if [ $add_scenes == yes -a $add_slc == yes -a $coregister_add == yes -a $add_ifms == yes ]; then
	    if [ ! -e $add_ifm_list ]; then # if ifm list doesn't exist
		echo ""
		echo "Interferogram list doesn't exist yet, waiting for process_gamma.bash to be rerun once list is created."
		:
	    else # ifm list exists
		CREATE_ADD_IFMS
	    fi
	else # process as normal
	    CREATE_ADD_IFMS
	fi
    fi
elif [ $add_ifms == no -a $platform == NCI ]; then
    echo ""
    echo "Option to create additional interferograms not selected."
    echo ""
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



