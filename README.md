## GAMMA-INSAR

A tool to process Sentinel-1 SLC to Analysis Ready Data (ARD) using GAMMA SOFTWARE.

## Installation

As of April 2020, `gamma_insar` is coupled with the NCI HPC systems and has to be installed there. Using `gamma_insar` requires membership of several NCI groups. Use [Mancini](https://my.nci.org.au/) to request membership access to the following groups:

```
dg9: InSAR research
u46: DEA Development and Science (GA internal)
fj7: Sentinel Data
```

Then, once logged into NCI, clone this repository into a dir/workspace in your NCI home dir:

```BASH
cd ~/<your project dir>
git clone git@github.com:GeoscienceAustralia/gamma_insar.git
cd gamma_insar
git checkout -b pygamma_workflow

# set up a local Python 3.6 runtime environment
source configs/insar.env  # should be error/warning free
export CUSTOM_PY_INSTALL=~/.digitalearthau/dea-env/20191127/local
mkdir -p $CUSTOM_PY_INSTALL/lib/python3.6/site-packages/
python setup.py install --prefix=$CUSTOM_PY_INSTALL
```

If the `source configs/insar.env` command does not complete cleanly (e.g. cannot find a dir of modules), check your group memberships.

## Developing GAMMA-INSAR

### Local Runtime Environment Setup

Note that the Gamma InSAR code can only be run on NCI's `Gadi` system. Only unit tests can be run with local repositories (run on Linux and Mac/OS X).

TODO: document setting up a local virtual env.

### Running unit tests & code coverage

Gamma-InSAR uses pytest for execute the unittests. Note that running `coverage.py` alone **does not accurately record coverage results!** The pytest-cov tool is required to measure this correctly.

```BASH
cd <gamma-insar project dir>
echo $PYTHONPATH  # should contain the gamma_insar dir
py.test -q  # should complete with 0 errors and some warnings

# run tests & display coverage report at the terminal
py.test -q --disable-warnings --cov=insar

# run tests & generate an interactive HTML report
py.test -q --disable-warnings --cov-report=html --cov=insar tests
```

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
    
	$module use <path/to/a/module/file/location>
	$module load <module name>

### The InSAR Workflow
Several preliminary steps are required to generate backscatter and interferometry products.
1) Extract SLC metadata from the Sentinel-1 zip files and store
   that information into yaml files. This needs to be done once
   for a given time frame of the user's choosing
   (see YAML Extraction example).

2) Generate an sqlite database from all the yamls created in (1).
   This db file is used for fast quering. This needs to be done
   (see Database Creation example)

3) Generate grids for a given time frame, region-of-interest,
   latitude width and buffer size. This step requires the
   db file from (2) and generates shp files (and kml files
   if specified - see Grid Generation example)

4) Adjust/reconfigure the grids generated in the previous step.
   This is an optional step, see,
   grid-definition grid-adjustment --help

5) Create task-files. The shp files from (3) are needed
   (see Task File Creation example)

6) Generate backscatter products (see Multi-stack packaging example)

7) Package backscatter (see Multi-stack packaging example)

### Usage
#### Example SLC Metadata to YAML Extraction

Run this step to extract the SLC acquisition details into YAML files for a single month.

Create a PBS job script on `Gadi` using this template:

```BASH
#!/bin/bash
#PBS -P u46
#PBS -q express  # for faster turnaround in the queue
#PBS -l walltime=05:00:00,mem=4GB,ncpus=1
#PBS -l wd
#PBS -l storage=gdata/v10+gdata/dg9+gdata/fj7+gdata/up71
#PBS -me
#PBS -M <your-email@some.domain>

pushd $HOME/<your-project-dir>/gamma_insar/configs
source insar.env
popd

slc-archive slc-ingestion \
    --save-yaml \
    --yaml-dir <dir-to-save-generated-yamls> \
    --year <year-to-process> \
    --month <month-to-process> \
    --slc-dir /g/data/fj7/Copernicus/Sentinel-1/C-SAR/SLC \  # change if required
    --database-name <filename-to-save-sqlite-db-to> \
    --log-pathname <filename-to-save-log-to>
```

Then submit with `qsub` from somewhere in your `$HOME` dir. If your groups are correctly set, the `source insar.env` line should complete without errors or warnings. The run time should be around 70 minutes.

#### Database Creation
Run this step to create an sqlite database (.db) file from SLC metadata stored in the yaml files

Create a PBS job script on `Gadi` using this template:

```BASH
#!/bin/bash
#PBS -P u46
#PBS -q normal
#PBS -l walltime=10:00:00,mem=4GB,ncpus=1
#PBS -l wd
#PBS -l storage=gdata/v10+gdata/dg9+gdata/fj7+gdata/up71
#PBS -me
#PBS -M <your-email@some.domain>

source <path-to-insar.env>

slc-archive slc-ingest-yaml \
        --database-name <output-sqlite-database-filename> \
        --yaml-dir <base-dir-containing-yaml-files> \
        --log-pathname <output-json-log-filename>
```
Then submit with `qsub`. The run time can be quite long depending on how many yaml files there are.

#### NSW and VIC S1A Grid Generation example
Run this step to create grids
Create a PBS job script on `Gadi` using this template:

```BASH
#!/bin/bash
#PBS -P u46
#PBS -q normal
#PBS -l walltime=05:00:00,mem=4GB,ncpus=1
#PBS -l wd
#PBS -l storage=gdata/v10+gdata/dg9+gdata/fj7+gdata/up71
#PBS -me
#PBS -M <your-email@some.domain>

source <path-to-insar.env>

grid-definition grid-generation-new \
    --database-path <sqlite-database-filename> \
    --out-dir <dir-to-save-shape-files> \
    --latitude-width <positive-float-for-latitude-width> \
    --latitude-buffer <positive-float-for-buffer> \
    --log-pathname <output-json-log-filename> \
    --create-kml \	# ignore if kml files are not desired
    --sensor S1A \      # ignore if S1A and S1B are required
    --start-date <YYYY-MM-DD> \
    --end-date <YYYY-MM-DD> \
    --northern-latitude -27.0 \		# decimal degrees North
    --western-longitude 138.0 \		# decimal degrees East
    --southern-latitude -39.2 \		# decimal degrees South
    --eastern-longitude 153.8		# decimal degrees West

```
Then submit with `qsub`. 

#### Australia-wide S1A and S1B Grid Generation example
Run this step to create grids
Create a PBS job script on `Gadi` using this template:

```BASH
#!/bin/bash
#PBS -P u46
#PBS -q normal
#PBS -l walltime=05:00:00,mem=4GB,ncpus=1
#PBS -l wd
#PBS -l storage=gdata/v10+gdata/dg9+gdata/fj7+gdata/up71
#PBS -me
#PBS -M <your-email@some.domain>

source <path-to-insar.env>

grid-definition grid-generation-new \
    --database-path <sqlite-database-filename> \
    --out-dir <dir-to-save-shape-files> \
    --latitude-width <positive-float-for-latitude-width> \
    --latitude-buffer <positive-float-for-buffer> \
    --log-pathname <output-json-log-filename> \
    --create-kml \      # ignore if kml files are not desired
    --start-date <YYYY-MM-DD> \
    --end-date <YYYY-MM-DD>

```
Then submit with `qsub`.

#### Task File Creation example
Run this step to create task-files needed to generate backscattering/interferometry products
Create a PBS job script on `Gadi` using this template:

```BASH
#!/bin/bash
#PBS -P u46
#PBS -q normal
#PBS -l walltime=05:00:00,mem=4GB,ncpus=1
#PBS -l wd
#PBS -l storage=gdata/v10+gdata/dg9+gdata/fj7+gdata/up71
#PBS -me
#PBS -M <your-email@some.domain>

source <path-to-insar.env>

create-task-files insar-files \
    --input-path <dir-to-shp-files> \
    --out-dir <dir-to-save-task-files>

```
Then submit with `qsub`.


#### Single Stack processing 
The workflow is managed by a luigi-scheduler and parameters can be set in `luigi.cfg` file.

Process a single stack Sentinel-1 SLC data to directly using a ARD pipeline from the command line.

	$gamma_insar ARD --help

	usage: gamma_insar ARD
		   [REQUIRED PARAMETERS]
		   --vector-file-list    PATH    A full path to a Sentinel-1 tract and frame vector-file.
		   --start-date [%Y-%m-%d]  A start-date of SLC data acquisition.
		   --end-date [%Y-%m-%d]    An end-date of SLC data acquisition.
		   --workdir    PATH    A full path to a working directory to output logs.
		   --outdir PATH    A full path to an output directory.
		   --polarization LIST      Polarizations to be processed (json strings) '["VV"|"VH"|"VV","VH"]'.	
		   --cleanup TEXT   A flag[yes|no] to specify a clean up  of intermediary files. Highly recommended to cleanup to limit storage during production.
		   --database-name  PATH   A full path to SLC-metata database with burst informations.
		   --orbit  TEXT    A Sentinel-1 orbit [A|D].
		   --dem-img PATH   A full path to a Digital Elevation Model.
		   --multi-look INTEGER A multi-look value.
		   --poeorb-path    PATH    A full path to a directory with precise orbit file.
		   --resorb-path    PATH    A full path to a directory with restitution orbit file.
		   --workers    INTEGER Number of workers assigned to a luigi scheduler.
		   --local-scheduler    TEXT    only test using a `local-scheduler`.


#### Examples 

	$gamma_insar ARD --vector-file <path-to-vector-file> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --workers <number-of-workers> --local-scheduler 
	$gamma_insar ARD --vector-file <path-to-vector-file> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --polarization '["VV"]' --workers <number-of-workers> --local-scheduler
	$gamma_insar ARD --vector-file <path-to-vector-file> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --polarization '["VV","VH"]' --workers <number-of-workers> --local-scheduler

#### Single stack packaging 
The packaging of a single stack Sentinel-1 ARD processed using `gamma_insar ARD` workflow.

    $package --help
    
    usage: package 
          [REQUIRED PARAMETERS]
          --track TEXT                   track name of the grid definition: `T001D`
          --frame TEXT                   Frame name of the grid definition: `F02S`
          --input-dir PATH               The base directory of InSAR datasets
          --pkgdir PATH                  The base output packaged directory.
          --product TEXT                 The product to be packaged: sar|insar
          --polarization TEXT            Polarizations used in metadata consolidations
                                         for product.

#### Example 

	$package --track <track-name> --frame <frame-name> --input-dir <path-to-stack-folder> --pkgdir <path-to-pkg-output-dir> --product sar --polarization VV
	$package --track <track-name> --frame <frame-name> --input-dir <path-to-stack-folder> --pkgdir <path-to-pkg-output-dir> --product sar --polarization VV --polarization VH


#### Multi-stack processing using PBS system
Batch processing of multiple stacks Sentinel-1 SLC data to ARD using PBS module in NCI.
The list of the full-path-to-vector-files in a `taskfile` is divided into number of batches (nodes)
and submitted to NCI queue with parameters specified in a `required parameters`

    $pbs-insar --help 
    
    usage:  pbs-insar
            [REQUIRED PARAMETERS]
             --taskfile PATH      The file containing the list of tasks (full
                                  paths to vector-files) to be performed
             --start-date  [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]  The start date of SLC acquisition
             --end-date    [%Y-%m-%d|%Y-%m-%dT%H:%M:%S|%Y-%m-%d %H:%M:%S]  The end date of SLC acquisition
             --workdir PATH       The base working and scripts output directory.
             --outdir  PATH       The output directory for processed data
             --polarization TEXT  Polarizations to be processed VV or VH, arg
                                  can be specified multiple times
             --ncpus   INTEGER    The total number of cpus per job required if known (default=48)
             --memory  INTEGER    Total memory in GB required if per node - recommend to use 700
             --queue   TEXT       Queue {express, normal, hugemem} to submit
                                  the job (default=normal) - recommend to use hugemem
             --hours   INTEGER    Job walltime in hours (default=48)
             --email   TEXT       Notification email address.
             --nodes   INTEGER    Number of nodes to be requested (default=1)
             --workers INTEGER    Number of workers
             --jobfs   INTEGER    Jobfs required in GB per node (default=2)
             -s, --storage TEXT   Project storage you wish to use in PBS jobs
             --project TEXT       Project to compute under
             --env PATH           Environment script to source.
             --test               Mock the job submission to PBS queue

#### Example 

	$pbs-insar --taskfile <path-to-taskfile> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --ncpus 48 --memory 700 --queue hugemem --nodes 2 --jobfs 2 -s <project1> -s <project2> --project <project-name> --env <path-to-envfile> 
	$pbs-insar --taskfile <path-to-taskfile> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --polarization VV --ncpus 48 --memory 700 --queue hugemem --nodes 2 --workers 6 --jobfs 2 -s <project1> -s <project2> --project <project-name> --env <path-to-envfile> 
	$pbs-insar --taskfile <path-to-taskfile> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --polarization VV --polarization VH --ncpus 48 --memory 700 --queue hugemem --nodes 2 --workers 10 --jobfs 2 -s <project1> -s <project2> --project <project-name> --env <path-to-envfile> 

#### Multi-stack packaging of InSAR ARD using PBS system
Batch processing of packaging of InSAR ARD to be indexed using Open Data Cube tools eo-datasets. 
The `input-list` containing the full path to stack processed can be submitted to NCI PBS system 
to be packaged to be indexed into a data-cube. 

    $pbs-package --help 
    
    usage pbs-package
       [REQUIRED PARAMETERS]
      --input-list PATH     full path to a file with list of track and
                            frames to be packaged
      --workdir PATH        The base working and scripts output directory.
      --pkgdir PATH         The output directory for packaged data
      --ncpus INTEGER       The total number of cpus per node required if known
      --memory INTEGER      Total memory required per node
      --queue TEXT          Queue to submit the job into
      --hours INTEGER       Job walltime in hours.
      --jobfs INTEGER       jobfs required per node
      -s, --storage TEXT    Project storage you wish to use in PBS jobs
      --project TEXT        Project to compute under  [required]
      --env PATH            Environment script to source.  [required]
      --product TEXT        The product to be packaged: sar| insar
      --polarization TEXT   Polarizations to be processed VV or VH, arg can be
                            specified multiple times
      --test                mock the job submission to PBS queue

#### Example 

	$pbs-package --input-list <path-to-input-list> --workdir <path-to-workdir> --pkgdir <path-to-pkgdir> --ncpus 8--memory 32 --product sar --polarization VV --queue normal --nodes 2 --jobfs 2 -s <project1> -s <project2> --project <project-name> --env <path-to-envfile> 
	$pbs-package --input-list <path-to-input-list> --workdir <path-to-workdir> --pkgdir <path-to-pkgdir> --ncpus 8--memory 32 --product sar --polarization VV --polarization VH --queue normal --nodes 2 --jobfs 2 -s <project1> -s <project2> --project <project-name> --env <path-to-envfile> 
