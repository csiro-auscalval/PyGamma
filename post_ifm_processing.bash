#!/bin/bash

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* post_ifm_processing:  Copy files from each interferogram directory to a     *"
    echo "*                       central location to check processing results and for  *"
    echo "*                       Pyrate processing.                                    *"
    echo "*                                                                             *"
    echo "* input:  [proc_file]  name of GAMMA proc file (eg. gamma.proc)               *"
    echo "*         [list_type]  ifm list type (1 = ifms.list, 2 = add_ifms.list)       *"
    echo "*         [rlks]       range multi-look value                                 *"
    echo "*         [alks]       azimuth multi-look value                               *"
    echo "*         <beam>       Beam number (eg, F2)                                   *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       16/06/2015, v1.0                            *"
    echo "*         Sarah Lawrie @ GA       22/06/2015, v1.1                            *"
    echo "*           - add capture of bperp value from ifm processing                  *"
    echo "*         Sarah Lawrie @ GA       06/08/2015, v1.2                            *"
    echo "*           - add plotting of cc and filt ifms and split up plot creation     *"
    echo "*             to separate scripts.                                            *"
    echo "*******************************************************************************"
    echo -e "Usage: post_ifm_processing.bash [proc_file] [list_type] [rlks] [alks] <beam>"
    }

if [ $# -lt 4 ]
then 
    display_usage
    exit 1
fi

proc_file=$1
list_type=$2
ifm_rlks=$3
ifm_alks=$4
beam=$5

## Variables from parameter file (*.proc)
nci_path=`grep NCI_PATH= $proc_file | cut -d "=" -f 2`
platform=`grep Platform= $proc_file | cut -d "=" -f 2`
project=`grep Project= $proc_file | cut -d "=" -f 2`
track_dir=`grep Track= $proc_file | cut -d "=" -f 2`
polar=`grep Polarisation= $proc_file | cut -d "=" -f 2`
sensor=`grep Sensor= $proc_file | cut -d "=" -f 2`
ifm_looks=`grep ifm_multi_look= $proc_file | cut -d "=" -f 2`
master=`grep Master_scene= $proc_file | cut -d "=" -f 2`
plot_walltime=`grep plot_walltime= $proc_file | cut -d "=" -f 2`
plot_mem=`grep plot_mem= $proc_file | cut -d "=" -f 2`
plot_ncpus=`grep plot_ncpus= $proc_file | cut -d "=" -f 2`
error_walltime=`grep error_walltime= $proc_file | cut -d "=" -f 2`
error_mem=`grep error_mem= $proc_file | cut -d "=" -f 2`
error_ncpus=`grep error_ncpus= $proc_file | cut -d "=" -f 2`


## Identify project directory based on platform
if [ $platform == NCI ]; then
    proj_dir=$nci_path/INSAR_ANALYSIS/$project/$sensor/GAMMA
else
    proj_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/GAMMA
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

dem_dir=$proj_dir/$track_dir/`grep DEM_dir= $proc_file | cut -d "=" -f 2`
int_dir=$proj_dir/$track_dir/`grep INT_dir= $proc_file | cut -d "=" -f 2`

if [ $list_type -eq 1 ]; then
    ifm_list=$proj_dir/$track_dir/lists/`grep List_of_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Copying files for Pyrate and creating plots..."
else
    ifm_list=$proj_dir/$track_dir/lists/`grep List_of_add_ifms= $proc_file | cut -d "=" -f 2`
    echo " "
    echo "Copying files for Pyrate and creating plots..."
fi

cd $proj_dir/$track_dir


# Create directories
mkdir -p png_images
png_dir=$proj_dir/$track_dir/png_images
mkdir -p $png_dir/png_unw_ifms
mkdir -p $png_dir/png_filt_ifms
mkdir -p $png_dir/png_filt_cc_files
mkdir -p $png_dir/png_flat_cc_files


mkdir -p bperp_files
bperp_dir=$proj_dir/$track_dir/bperp_files

mkdir -p pyrate_files
pyrate_dir=$proj_dir/$track_dir/pyrate_files
mkdir -p $pyrate_dir/unw_ifms
mkdir -p $pyrate_dir/dem_files
mkdir -p $pyrate_dir/filt_ifms
mkdir -p $pyrate_dir/filt_cc_files
mkdir -p $pyrate_dir/flat_cc_files

## Copy dem and bperp files to central directories
if [ -z $beam ]; then #no beam
    while read list; do
	if [ ! -z $list ]; then
	    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifm_dir=$int_dir/$mas-$slv
	    bperp=$mas-$slv"_"$polar"_"$ifm_looks"rlks_bperp.par"
	    cp $ifm_dir/$bperp $bperp_dir
	    cd $bperp_dir
	    ls *.par > bperp_list
	fi
    done < $ifm_list
    dem=$master"_"$polar"_"$ifm_looks"rlks_utm.dem"
    dem_par=$dem.par
    lv_theta=$master"_"$polar"_"$ifm_looks"rlks_utm.lv_theta"
    lv_phi=$master"_"$polar"_"$ifm_looks"rlks_utm.lv_phi"
    cp $dem_dir/$dem $pyrate_dir/dem_files
    cp $dem_dir/$dem_par $pyrate_dir/dem_files
    cp $dem_dir/$lv_theta $pyrate_dir/dem_files
    cp $dem_dir/$lv_phi $pyrate_dir/dem_files
    cd $pyrate_dir/dem_files
    ls *.dem > dem_list
    ls *.par >> dem_list
    ls *.lv_theta >> dem_list
    ls *.lv_phi >> dem_list
else #beam exists
    while read list; do
	if [ ! -z $list ]; then
	    mas=`echo $list | awk 'BEGIN {FS=","} ; {print $1}'`
	    slv=`echo $list | awk 'BEGIN {FS=","} ; {print $2}'`
	    ifm_dir=$int_dir/$mas-$slv
	    bperp=$mas-$slv"_"$polar"_"$beam"_"$ifm_looks"rlks_bperp.par"
	    cp $ifm_dir/$bperp $bperp_dir
	    cd $bperp_dir
	    ls *.par > bperp_list
	fi
    done < $ifm_list
    dem=$master"_"$polar"_"$beam"_"$ifm_looks"rlks_utm.dem"
    dem_par=$dem.par
    lv_theta=$master"_"$polar"_"$beam"_"$ifm_looks"_utm.lv_theta"
    lv_phi=$master"_"$polar"_"$beam"_"$ifm_looks"_utm.lv_phi"
    cp $dem_dir/$dem $pyrate_dir/dem_files
    cp $dem_dir/$dem_par $pyrate_dir/dem_files
    cp $dem_dir/$lv_theta $pyrate_dir/dem_files
    cp $dem_dir/$lv_phi $pyrate_dir/dem_files
    cd $pyrate_dir/dem_files
    ls *.dem > dem_list
    ls *.par >> dem_list
    ls *.lv_theta >> dem_list
    ls *.lv_phi >> dem_list
fi

# Run PBS jobs for plot creation
ifm_batch_dir=$proj_dir/$track_dir/batch_jobs/ifm_jobs

if [ -z $beam ]; then #no beam
    # run unw ifm plotting
    echo "Running unw ifm plotting..."
    cd $ifm_batch_dir
    plot=plot_unw_ifms
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_unw_ifms.bash $proc_file $list_type $ifm_rlks $ifm_alks >> $plot
    chmod +x $plot
    qsub $plot | tee unw_ifm_job_id

    # run filt ifm plotting
    echo "Running filt ifm plotting..."
    cd $ifm_batch_dir
    plot=plot_filt_ifms
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_filt_ifms.bash $proc_file $list_type $ifm_rlks $ifm_alks >> $plot
    chmod +x $plot 
    qsub $plot | tee filt_ifm_job_id

    # run filt cc file plotting
    echo "Running filtered cc file plotting..."
    cd $ifm_batch_dir
    plot=plot_filt_cc_files
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_filt_cc_files.bash $proc_file $list_type $ifm_rlks $ifm_alks >> $plot
    chmod +x $plot
    qsub $plot | tee filt_cc_job_id

    # run flat cc file plotting
    echo "Running flattened cc file plotting..."
    cd $ifm_batch_dir
    plot=plot_flat_cc_files
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_flat_cc_files.bash $proc_file $list_type $ifm_rlks $ifm_alks >> $plot
    chmod +x $plot
    qsub $plot | tee flat_cc_job_id

    # Check plot errors
    echo "Preparing error collation for ifm plots..."
    cd $ifm_batch_dir
    unw_ifm_jobid=`sed s/.r-man2// unw_ifm_job_id`
    filt_ifm_jobid=`sed s/.r-man2// filt_ifm_job_id`
    filt_cc_jobid=`sed s/.r-man2// filt_cc_job_id`
    flat_cc_jobid=`sed s/.r-man2// flat_cc_job_id`
    job=plot_err_check
    echo \#\!/bin/bash > $job
    echo \#\PBS -lother=gdata1 >> $job
    echo \#\PBS -l walltime=$error_walltime >> $job
    echo \#\PBS -l mem=$error_mem >> $job
    echo \#\PBS -l ncpus=$error_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q normal >> $job
    echo \#\PBS -W depend=afterany:$unw_ifm_jobid:$filt_ifm_jobid:$filt_cc_jobid:$flat_cc_jobid >> $job
    echo ~/repo/gamma_insar/collate_nci_errors.bash $proc_file 8 >> $job
    chmod +x $job
    qsub $job
    
else #beam exists
    # run unw ifm plotting
    echo "Running unw ifm plotting..."
    cd $ifm_batch_dir/$beam
    plot="plot_unw_ifms_"$beam
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_unw_ifms.bash $proc_file $list_type $ifm_rlks $ifm_alks $beam >> $plot
    chmod +x $plot
    qsub $plot | tee unw_ifm_job_id

    # run filt ifm plotting
    echo "Running filt ifm plotting..."
    cd $ifm_batch_dir/$beam
    plot="plot_filt_ifms_"$beam
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_filt_ifms.bash $proc_file $list_type $ifm_rlks $ifm_alks $beam >> $plot
    chmod +x $plot
    qsub $plot | tee filt_ifm_job_id

    # run filt cc file plotting
    echo "Running filtered cc file plotting..."
    cd $ifm_batch_dir/$beam
    plot="plot_filt_cc_files_"$beam
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_filt_cc_files.bash $proc_file $list_type $ifm_rlks $ifm_alks $beam >> $plot
    chmod +x $plot
    qsub $plot | tee filt_cc_job_id

    # run flat cc file plotting
    echo "Running flattened cc file plotting..."
    cd $ifm_batch_dir/$beam
    plot="plot_flat_cc_files_"$beam
    echo \#\!/bin/bash > $plot
    echo \#\PBS -lother=gdata1 >> $plot
    echo \#\PBS -l walltime=$plot_walltime >> $plot
    echo \#\PBS -l mem=$plot_mem >> $plot
    echo \#\PBS -l ncpus=$plot_ncpus >> $plot
    echo \#\PBS -l wd >> $plot
    echo \#\PBS -q normal >> $plot
    echo ~/repo/gamma_insar/plot_flat_cc_files.bash $proc_file $list_type $ifm_rlks $ifm_alks $beam >> $plot
    chmod +x $plot
    qsub $plot | tee flat_cc_job_id

    # Check plot errors
    echo "Preparing error collation for ifm plots..."
    cd $ifm_batch_dir/$beam
    unw_ifm_jobid=`sed s/.r-man2// unw_ifm_job_id`
    filt_ifm_jobid=`sed s/.r-man2// filt_ifm_job_id`
    filt_cc_jobid=`sed s/.r-man2// filt_cc_job_id`
    flat_cc_jobid=`sed s/.r-man2// flat_cc_job_id`
    job="plot_err_check_"$beam
    echo \#\!/bin/bash > $job
    echo \#\PBS -lother=gdata1 >> $job
    echo \#\PBS -l walltime=$error_walltime >> $job
    echo \#\PBS -l mem=$error_mem >> $job
    echo \#\PBS -l ncpus=$error_ncpus >> $job
    echo \#\PBS -l wd >> $job
    echo \#\PBS -q normal >> $job
    echo \#\PBS -W depend=afterany:$unw_ifm_jobid:$filt_ifm_jobid:$filt_cc_jobid:$flat_cc_jobid >> $job
    echo ~/repo/gamma_insar/collate_nci_errors.bash $proc_file 8 $beam >> $job
    chmod +x $job
    qsub $job

fi


# Plot bperp values
#plot_bperp.bash


echo " "
echo "Files copied and plots created."
echo " "