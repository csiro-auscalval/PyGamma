## GAMMA-INSAR

A tool to process Sentinel-1 SLC to Analysis Ready Data using GAMMA SOFTWARE.

## Installation

    python setup.py install --prefix=<prefix> 

Python 3.6+ is supported.

## Operating System tested
Linux

## Supported Satellites and Sensors
* Sentinel-1A/B

## Requirements
* [attrs>=17.4.0]
* [Click>=7.0]
* [GDAL>=2.4]
* [geopandas>=0.4.1]
* [luigi>=2.8.3]
* [matplotlib>=3.0.3]
* [numpy>=1.8]
* [pandas>-0.24.2]
* [pyyaml>=3.11]
* [rasterio>=1,!=1.0.3.post1,!=1.0.3]
* [structlog>=16.1.0]
* [shapely>=1.5.13]
* [spatialist==0.4]
* [eodatasets3]
* [GAMMA-SOFTWARE >= June 2019 release]


## NCI Module
	$module use -a /g/data/v10/public/modules/modulefiles /g/data/v10/private/modules/modulefiles 
	$module load gamma-insar

## Usage

The workflow is managed by a luigi-scheduler and parameters can be set in `luigi.cfg` file.


Process a single stack Sentinel-1 SLC data to directly using a ARD pipeline from the command line.

	$gamma_insar ARD --help

	usage: gamma_insar ARD
		   [REQUIRED PARAMETERS]
		   --vector-file VECTOR_FILE        A full path to a Sentinel-1 tract and frame vector-file.
		   --start-date START_DATE		    A start-date['YYYY-MM-DD'] of SLC data acquisition.
		   --end-date END_DATE			    An end-date['YYYY-MM-DD'] of SLC data acquisition.
		   --workdir WORKDIR			    A full path to a working directory to output logs.
	       --outdir OUTDIR                  A full path to an output directory.
		   --polarization POLARIZATION      Polarizations to be processed [VV|VH|VV,VH].	
		   --cleanup CLEANUP			    A flag[yes|no] to specify a clean up  of intermediary files. 
							                Highly recommended to cleanup to limit storage during production.
		   --database-name DATABASE_NAME    A full path to SLC-metata database with burst informations.
		   --orbit ORBIT			        A Sentinel-1 orbit [A|D].
		   --dem-img DEM_IMG			    A full path to a Digital Elevation Model.
		   --multi-look MULTI_LOOK		    A multi-look value.
		   --poeorb-path POEORB_PATH		A full path to a directory with precise orbit file.
		   --resorb-path RESORB_PATH		A full path to a directory with restitution orbit file.
		   --workers WORKERS			    Number of workers assigned to a luigi scheduler.
		   --local-scheduler SCHEDULER		Use only local-scheduler.


### Example 

	$gamma_insar ARD --vector-file <path-to-vector-file> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --workers <number-of-workers> --local-scheduler 


Batch processing of multiple stacks Sentinel-1 SLC data to ARD using PBS module in NCI

    $pbs-insar --help 
    
    usage:  pbs-insar
            [REQUIRED PARAMETERS]
             --taskfile PATH    The file containing the list of tasks (full paths to vector-files) to beperformed
              --start-date  [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]  The start date of SLC acquisition
              --end-date    [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]  The end date of SLC acquisition
              --workdir PATH    The base working and scripts output directory.
              --outdir  PATH    The output directory for processed data
              --ncpus   INTEGER The total number of cpus per job required if known(default=48)
              --memory  INTEGER Total memory required if per node
              --queue   TEXT    Queue to submit the job into (default=normal)
              --hours   INTEGER Job walltime in hours (default=48)
              --email   TEXT    Notification email address.
              --nodes   INTEGER Number of nodes to be requested(default=1)
              --jobfs   INTEGER Jobfs required per node (default=400)
              -s, --storage TEXT    Project storage you wish to use in PBS jobs
              --project TEXT        Project to compute under
              --env PATH            Environment script to source.
              --test                Mock the job submission to PBS queue

