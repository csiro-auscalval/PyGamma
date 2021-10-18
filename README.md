## GAMMA-INSAR

A tool to process Sentinel-1 SLC to Analysis Ready Data (ARD) using GAMMA SOFTWARE. The ARD products are georeferenced backscatter and interferograms.

Using `gamma_insar` currentlty requires a GitHub account (& GA access permissions as it's not yet open source), as we do not currently deploy
releases any other way than via github.

#### Operating System tested

* Linux
  * CentOS Linux release 8.3.2011 (NCI's Gadi environment)
  * Ubuntu 18.04 flavours (unit tests only)
  * [osgeo/gdal docker images](https://hub.docker.com/r/osgeo/gdal) (unit tests only)
* macOS (unit tests only)
  * macOS v11.x (GDAL 3.2.2 from homebrew)

#### Supported Satellites and Sensors

* Sentinel-1A/B

## Installation

`gamma_insar` assumes some pre-existing native dependencies are installed on the system prior to installation:
 * [Python](https://www.python.org/) (3.6+)
 * [sqlite3](https://www.sqlite.org/index.html) with [spatialite](https://www.gaia-gis.it/fossil/libspatialite/index) extension
 * [GAMMA](http://www/gamma-rs.ch)
 * [GDAL](https://gdal.org/) (2.4+ and 3.0+ have been tested)
   * Note: version required is dictated by GAMMA release
 * [PROJ](https://proj.org/) (for GAMMA/GDAL)
 * [FFTW](https://www.fftw.org/) (for GAMMA)

In addition to the above native dependencies, gamma_insar has various python dependencies listed in `requirements.txt` - the
exact python package versions required is tied to the GAMMA version being used (and `requirements.txt` is as loosely
as possible frozen to the versions supported by the GAMMA version used in GA's production NCI environment).

## Installation on arbitrary platforms

In platform agnostic terms, gamma_insar should work in any environment in which
it's dependencies (both native + python) are installed and found in the `PATH`/`PYTHONPATH`/`LD_LIBRARY_PATH` (or relevant platform specific analgoues).

`gamma_insar` provides a Dockerfile (based on OSGEO/DAL ubuntu images) a a simple method for bringing up a compatible environment on
any platform which supports Docker.

`gamma_insar` also has various scripts (found under `configs/`) in which Python virtual environments are used to setup compatible environments on
platforms where native dependencies already exist (such as the NCI environment), which may be used as a reference
for those wanting to create similar venvs on other platforms.

## Installation on NCI

Using `gamma_insar` on NCI of course requires a user account (to access the NCI) & membership of several NCI groups. Use [Mancini](https://my.nci.org.au/) to request membership access to the following groups:

```
v10: DEA Operations and code repositories
up71: Storage resources for GA ARD development
dg9: InSAR research
u46: DEA Development and Science (GA internal)
fj7: Sentinel Data
```

For an introduction into NCI, their [wiki covers quite a lot](https://opus.nci.org.au/display/Help/0.+Welcome+to+Gadi).

After getting NCI access, you will need a release of the `gamma_insar` code somewhere on NCI to install, such as by cloning this github repo as follows:

```BASH
# Our examples install into your home dir, change if required.
cd ~

# Note: This gets the latest development version, you might want to get a stable release instead, eg: v0.9.0
git clone -b pygamma_workflow git@github.com:GeoscienceAustralia/gamma_insar.git
```

We use Python virtual environments on gadi (using DEA modules for native dependencies) to manage installations of `gamma_insar`.  Scripts for
creation and entering these environments are provided in `configs/createNCIenv.sh` and `configs/activateNCI.env` respectively.

Once logged into `gadi`, use the following command to create a new installation (assumes `~/gamma_insar` from above):

```BASH
bash ~/gamma_insar/configs/createNCIenv.sh ~/gamma_insar_install
```

The install step can take some time to download and install all the dependencies. If the command does not complete cleanly (e.g. cannot find a dir of modules), check your group memberships.

`configs/createNCIenv.sh` installs several dependencies into your venv directory, **including** a copy of the `gamma_insar` code from your release/repo. Any changes to files in your git repo **do not** automatically appear in the installation environment.

To "activate" the installation environment installed above (bringing all of the `gamma_insar` modules/scripts and it's dependencies into the environment) simply run:

```BASH
# Note: assumes you used paths from examples above
source ~/gamma_insar/configs/activateNCI.env ~/gamma_insar_install
```

All commands hence forth will be able to see the installation and it's dependencies, and all `python` and `pip` commands will also refer to the virtual environment of the `gamma_insar` installation.


Any time you want to update the `gamma_insar` code of an "active" installation environment (see above), simply run:

```BASH
cd ~/gamma_insar  # Or where ever your gamma_insar release/repo is
python setup.py install
```

This takes typically less than 30 seconds and will install the latest code from your `gamma_insar` release/repo into your installation environment (overriding the old version that was installed).


## GAMMA-INSAR Unit Testing

Running unit tests for `gamma_insar` is as simple as running `pytest` from the project directory on a supported platform (docker options below).  The test suite was written with the assumption that GAMMA is *unavailable*, but all other dependencies are required - this is suitable for testing on a wider range of systems (such as developers machines & CI testing environments which likely won't have GAMMA licenses).

As a result of this design decision, the *unit* tests only test the logic of the workflow - not the correctness of the processed data.

To run unit tests:
```BASH
cd ~/gamma_insar
source configs/activateNCI.env ~/gamma_insar_install
pytest --disable-warnings -q  # should be error free
```

Code coverage can be checked with pytest-cov. Note that running `coverage.py` alone with this repo **does not accurately record coverage results!** The `pytest-cov` tool is required to measure coverage correctly.

To measure code test coverage:

```BASH
# run tests & display coverage report at the terminal
pytest -q --disable-warnings --cov=insar

# run tests & generate an interactive HTML report
pytest -q --disable-warnings --cov-report=html --cov=insar
```

The report is saved to `coverage_html_report` in the project dir.

The unit tests may also be run on platforms which are unsupported, or do not have the dependencies installed - via docker (assuming the target platform can run docker images), please refer to the comments at the top of the `Dockerfile` for instructions on building the image and running `pytest` in that image.

### The InSAR Workflow

Several preliminary steps are required before the main processing workflow can be executed, these steps produce a database of data acquisitions that 'can' be processed - which is queried by the workflow to determine what data to process for a proided ESRI shapefile (to geometrically bound the area of interest) and date-range.

These steps are:
1) [Extract metadata](#Metadata-YAML-extraction) from the source data (eg: Sentinel-1 SLC zip files) and store
   that information into yaml files. This needs to be done for a time
   period any time data has been added/removed/changed.

2) [Generate a sqlite database](#Database-Creation) from all the yamls created in (1).
   This db file is used by the workflow to quickly query/filter scene information for processing.

3) [Produce a set of shapefiles](#shapefile-creation) that cover the areas of interest for processing.

4) [Process data products](#Data-processing) (eg: backscatter and/or interferograms)

5) [Package data products](#Product-packaging) for ODC indexing

### Usage
#### Metadata YAML extraction

This example extracts the SLC acquisition details into YAML files for a single month.  It takes 1-2 hours for ~5 years of Sentinel-1 acquisitions.

```BASH
slc-archive slc-ingestion \
    --save-yaml \
    --yaml-dir <dir-to-save-generated-yamls> \
    --year <year-to-process> \
    --month <month-to-process> \
    --slc-dir /g/data/fj7/Copernicus/Sentinel-1/C-SAR/SLC \  # change if required
    --database-name <filename-to-save-sqlite-db-to> \
    --log-pathname <filename-to-save-log-to>
```

#### Database Creation
This example creates an sqlite database (.db) file from SLC metadata stored in the yaml files:

```BASH
slc-archive slc-ingest-yaml \
        --database-name <output-sqlite-database-filename> \
        --yaml-dir <base-dir-containing-yaml-files> \
        --log-pathname <output-json-log-filename>
```
Note: the run time can be quite long depending on how many yaml files there are.

#### Data processing with geospatial query

The data proccessing workflow queries the DB with a date range and shapefile to determine the source data that meets those parameters, and processes them into derived products (such as backscatter or interferograms).

Most settings are set in the provided `--proc-file`, however some may be overriden via parameters (see: `gamma_insar --help` for details).

This example processes a temporal stack from Sentinel-1 source data (both VV and VH) producing backscatter + interferograms (the default) - for the date range 2016-01-01 - 2017-01-01:

```BASH
gamma_insar ARD \
    --proc-file config.proc \
    --shape-file shape_file.shp \
    --include-dates '2016-01-01-2017-01-01' \
    --polarization '["VV", "VH"]' \
    --workdir /path/to/job_logs_and_state \
    --outdir /path/to/final_output_data \
    --workers 4 \
    --local-scheduler
```

An example proc file is available in `tests/data/20151127/gamma.proc`

#### Data processing of source data directly

It is also possible to process data bypassing the spatial/temporal query DB entirely, by directly providing a set of source data products to processes into derived products (such as backscatter or interferograms).

As with standard geospatial/temporal extent processing in the previous section, most settings are set in the provided `--proc-file`, however some may be overriden via parameters (see: `gamma_insar --help` for details).

This example processes a Sentinel-1 SLC product (both VV and VH) into a backscatter product:

```BASH
gamma_insar ARD \
    --proc-file config.proc \
    --shape-file shape_file.shp \
    --source-data '["S1A_IW_SLC__1SDV_20210109T193325_20210109T193353_036065_043A21_39DA.zip", "S1A_IW_SLC__1SDV_20210109T193351_20210109T193418_036065_043A21_4E1D.zip"]' \
    --polarization '["VV", "VH"]' \
    --workflow backscatter \
    --workdir /path/to/job_logs_and_state \
    --outdir /path/to/final_output_data \
    --workers 4 \
    --local-scheduler
```

An example proc file is available in `tests/data/20151127/gamma.proc`

#### Product packaging

This example shows the packaging of a backscatter for a specific Sentinel-1 track/frame:

```BASH
package \
    --track T133D --frame F35S \
    --input-dir /path/to/workflow_output_data \
    --pkgdir /path/to/track_frame_pkg_output
```

### Running on the NCI

Running the InSAR workflow on NCI is no different to any other platform, however NCI is a distributed processing cluster and as such commands should be run in processing jobs via their job scheduler (PBS).

Scripts are provided for easily kicking off data processing and packaging on NCI, automatically handling job script creation and PBS scheduling for the user.

For all other commands, the general template for a PBS job script is:

```BASH
#!/bin/bash
#PBS -P <compute-project: u46/v10/etc>
#PBS -q normal
#PBS -l walltime=12:00:00,mem=4GB,ncpus=1
#PBS -l wd
#PBS -l storage=gdata/v10+gdata/dg9+gdata/fj7+gdata/up71
#PBS -me
#PBS -M <your-email@some.domain>

source ~/gamma_insar/configs/activateNCI.env ~/gamma_insar_install

# Run your gamma_insar command here...
```

which is then submitted with `qsub job_script.sh`

#### NCI data processing

For submitting data processing jobs to NCI, a helper script is provided which follows the same semantics/arguments of `gamma_insar ARD` but handles the job/PBS details:

```BASH
pbs-insar \
    # --env is sourced at the start of the PBS script, thus this
    # selects the gamma_insar installation to use for processing.
    --env ~/gamma_insar_install/NCI.env \
    --job-name example_job \
    --project example_proj \
    --proc-file config.proc --shape-file frame.shp \
    --date-range 2016-01-01 2017-01-01 \
    --polarization VV --polarization VH \
    --workdir /path/to/job_logs_and_state \
    --outdir /path/to/final_output_data \
    --ncpus 48 --memory 192 --queue normal --hours 48 --workers 4 \
    --jobfs 400 \
    --storage v10 --storage dg9 --storage up71 \
    --storage fj7 --storage dz56 \
    --email your.email@domain.com
```

### Unit testing on NCI

The Gadi system at NCI is a supported platform, and as such running unit tests is no different - simply enter/activate your installation (see [Installation on NCI](#Installation-on-NCI)) via `configs/activateNCI.env` and run `pytest` from the project directory.


### Shapefile creation

Shapefiles should typically match data acquisition patterns for the sensor data being processed, this is because mismatches in available data across acquisitions can cause complex problems in `gamma_insar` due to requirements imposed by the coregistration & the interferogram tree linking algorithm.

Due to how coregistration & interferogram trees work - only dates that share identical "sets geographic regions" in the source data (eg: bursts in Sentinel-1) may be correlated, and thus any acquisition that does **not** share the most expansive set of data (eg: is missing a burst) will be excluded.

The reason for this largely comes down to the fact that both coregistration and interferograms are in their nature an operation between two distinct scenes, and thus if data in scene A does not exist in scene B there is nothing to coregister with nor produce an interferogram from...

For this reason it is strongly recommended that shapefiles are produced in such a way that all scenes will consistently have the same set of data.
