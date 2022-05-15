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

* Sentinel-1 A & B
* ALOS PALSAR 1 & 2
* RADARSAT-2

### Documentation

Various documents are available to help users and developers learn more about the project, what it does, how to use it, and it's technical structure.

User guides:
 * [Installation guide](insar/docs/Installation.md)
 * [Running the workflow](insar/docs/RunningTheWorkflow.md)
 * [Geospatial database indexing](insar/docs/DatabaseIndexing.md)
 * [Data packaging](insar/docs/Packaging.md)
 * [Example .proc file](template.proc)

Technical Documents:
 * [InSAR Stack description](insar/docs/Stack.md)
 * [Metadata documentation](insar/docs/Metadata.md)

Developer guides:
 * [InSAR workflow overview](insar/docs/Workflow.md)
 * [Running the unit tests](insar/docs/UnitTesting.md)


### Notes on shapefile creation

Usage of `gamma_insar` typically needs a shapefile to process larger datasets (to keep the area of interest small enough to fit into memory), however no standard approach exists to creation of these shapefiles as yet.  This will eventually be addressed, but for now examples exist in `tests/data/...` and it's currently up to the user to create their own.

Shapefiles should typically match data acquisition patterns for the sensor data being processed, this is because mismatches in available data across acquisitions can cause complex problems in `gamma_insar` due to requirements imposed by the coregistration & the interferogram tree linking algorithm.

Due to how coregistration & interferogram trees work - only dates that share identical "sets geographic regions" in the source data (eg: bursts in Sentinel-1) may be correlated, and thus any acquisition that does **not** share the most expansive set of data (eg: is missing a burst) will be excluded.

The reason for this largely comes down to the fact that both coregistration and interferograms are in their nature an operation between two distinct scenes, and thus if data in scene A does not exist in scene B there is nothing to coregister with nor produce an interferogram from...

For this reason it is strongly recommended that shapefiles are produced in such a way that all scenes will consistently have the same set of data.
