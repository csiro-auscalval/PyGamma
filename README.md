## PyGamma

PyGamma is a tool to process Sentinel-1 SLC data into Analysis Ready Data (ARD) using the [GAMMA](http://www.gamma-rs.ch/) software, specifically ARD products for georeferenced backscatter and interferograms.

This project is intended to be generic and reusable, __however__... it should be noted to adopters that this project at the time of writing has only been used by Geoscience Australia on specific Sentinel-1, RADARSAT-2, and ALOS datasets - as such there are certain assumptions still being made in some areas of the code with respect to things like GAMMA program settings being hard-coded in some cases.

It is strongly recommended that adopters review the logs of their processing results to check the parameters being passed to GAMMA and confirm the workflow runs with the values they expect.  If they find there are undesirable paramters being used that are not configurable with the .proc settings file, we are more than [open to receiving PRs](insar/docs/governance/PullRequests.md) to fix any identified issues and/or [bug requests](insar/docs/governance/ContributingGeneral.md) for the impacted settings.

#### Operating System tested

* Linux
  * CentOS Linux release 8.3.2011 (NCI's Gadi environment)
  * Ubuntu 18.04 flavours (unit tests only)
  * [osgeo/gdal docker images](https://hub.docker.com/r/osgeo/gdal) (unit tests only)
* macOS (unit tests only)
  * macOS 11.x and 12.x (GDAL 3.2.2 from homebrew)

#### Supported Satellites and Sensors

* Sentinel-1 A & B
* ALOS PALSAR 1 & 2
* RADARSAT-2
* TerraSAR-X/TanDEM-X

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
 * [PyGamma logging information](insar/docs/Logging.md)
 * [Metadata documentation](insar/docs/Metadata.md)

Developer guides:
 * [New developer introduction](insar/docs/dev/ProjectOverview.md)
 * [InSAR workflow overview](insar/docs/Workflow.md)
   * [InSAR workflow technical (Luigi DAG) design](insar/docs/dev/LuigiWorkflowDAG.md)
 * [Running the unit tests](insar/docs/UnitTesting.md)
 * [Adding support for new sensors](insar/docs/AddNewSensors.md)
 * [Support for multiple GAMMA versions](insar/docs/dev/MultiVersionGAMMASupport.md)

### Notes on shapefile creation

Usage of `PyGamma` typically needs a shapefile to process larger datasets (to keep the area of interest small enough to fit into memory), however no standard approach exists to creation of these shapefiles as yet.  This will eventually be addressed, but for now examples exist in `tests/data/...` and it's currently up to the user to create their own.

Shapefiles should typically match data acquisition patterns for the sensor data being processed, this is because mismatches in available data across acquisitions can cause complex problems in `PyGamma` due to requirements imposed by the coregistration & the interferogram tree linking algorithm.

Due to how coregistration & interferogram trees work - only dates that share identical "sets geographic regions" in the source data (eg: bursts in Sentinel-1) may be correlated, and thus any acquisition that does **not** share the most expansive set of data will be excluded (in other words, any scene which is missing data that exists in even just one other acquisition will be excluded).  This is especially critical in scenarios where you have 1 scene which has a burst no other scene has, and that scene is missing a burst that others do - in this highlighted case, not a single scene will contain the most expensive set of data and the stack will be considered empty as not a single scene will be considered complete.

The reason for this largely comes down to the fact that both coregistration and interferograms are in their nature an operation between two distinct scenes, and thus if data in scene A does not exist in scene B there is nothing to coregister with nor produce an interferogram from... thus we require all scenes to share data.  PyGamma chose the requirement of only including the most expansive scenes, as the alternative of only processing the least common denominator of data will often result in geospatial holes in the products (from one or two bad acquisitions missing a burst) - with this approach the bad acquisitions are instead excluded, and the products that are considered complete will be processed in full producing the best quality and most complete product.

This subtle but very important detail highlights the importance of the stack's shapefile, and for this reason it is strongly recommended that shapefiles are produced in such a way that maximises how many scenes will consistently have the most expansive set of data for the whole temporal extent of the stack, to avoid this issue.
