This document attempts to introduce the `gamma_insar` project to developers who are completely new to it.  It covers the general code structure, concepts, and common foundational classes that they may need to understand before diving into specific parts of the project.

As a warning, the current state of the code base is not yet perfectly structured or final & as such some classes aren't necessarily in the most obvious files and some attributes aren't documented perfectly with docstrings as of yet - this document points these inconsistencies out and will be updated as the project matures.

## Code Structure ##

| Location | Description |
| ------------------------------- | --- |
| gamma_insar/config/...          | This folder contains scripts used to create and setup `gamma_insar` environments for Linux-like operating systems, these are used at the NCI and by our Dockerfile |
| gamma_insar/docs/...            | This folder contains an older attempt to create Sphinx docs for the project (this is not maintained/used/up-to-date). |
| gamma_insar/insar/docs/...      | This folder contains the user and technical documentation for the project. |
| gamma_insar/insar/scripts/...   | This folder contains the user level scripts that are used to run the `gamma_insar` processing/packaging/etc. |
| gamma_insar/insar/paths/...     | This folder contains classes that are used to define the filesystem structure of the stack in a definitive way which can then be re-used by the rest of the code base, this is described in further detail in a later section of this document. |
| gamma_insar/insar/meta_data/... | This folder holds all of the Sentinel-1 metadata handling and nosql database/spatialite logic for creating the geospatial/temporal database files. |
| gamma_insar/insar/sensors/...   | This folder contains modules for each supported satellite sensor which abstracts querying of acquisition metadata, and loading of acquisitions. |
| gamma_insar/insar/workflow/...  | This folder contains all the modules for the data processing workflow. |
| gamma_insar/insar/...           | This folder is the top-level module directory, it holds all the other dirs, but also holds all the data processing .py files. |
| gamma_insar/tests/...           | This folder holds all of the python unit tests for the whole code base, `fixtures.py` contains a lot of test fixtures used by the tests & the `data` directory contains all of the test data used by those tests (such as example .proc files, fake satellite data, etc). |

## Processing modules ##

Each stage of the data processing workflow is separated into it's own processing module in the `gamma_insar/insar/` folder, these are broken down as follows:

| Product | Module                                      | Description                                                                                         |
| ------- |---------------------------------------------|-----------------------------------------------------------------------------------------------------|
| SLC | `gamma_insar/insar/process_s1_slc.py`       | This module processes Sentinel-1 satellite acquisitions into `gamma_insar` SLC "scenes"             |
| SLC | `gamma_insar/insar/process_rsat2_slc.py`    | This module processes RADARSAT-2 satellite acquisitions into `gamma_insar` SLC "scenes"             |
| SLC | `gamma_insar/insar/process_alos_slc.py`     | This module processes ALOS PALSAR (1 & 2) satellite acquisitions into `gamma_insar` SLC "scenes"    |
| SLC | `gamma_insar/insar/process_tsx_slc.py`      | This module processes TSX / TDX satellite acquisitions into `gamma_insar` SLC "scenes"              |
| SLC | `gamma_insar/insar/coregister_dem.py`       | This module coregisters the primary scene to the DEM                                                |
| SLC | `gamma_insar/insar/coregister_slc.py`       | This module coregisters Sentinel-1 secondary scenes to the primary scene                            |
| SLC | `gamma_insar/insar/coregister_secondary.py` | This module coregisters secondary scenes to the primary scene (for other sensors except Sentinel-1) |
| NRB | `gamma_insar/insar/process_backscatter.py`  | This module processes the NRB (normalised radar backscatter) from SLC scenes.                       |
| IFG | `gamma_insar/insar/process_ifg.py`          | This module processes interferometry from two SLC scenes.                                           |

## File path classes ##

The `gamma_insar/insar/paths` module contains all of the classes that manage the file structure of the products being produced.
Classes exist for each product type, and one for the general stack structure.

For the DEM and related products (used for primary scene <-> DEM coreg) are contained within the `DEMPaths` class.  It's very rare these get used in day-to-day development and there's quite a few so this guide won't go over them in detail so refer to the docstrings for related information if you're modifying the primary scene coregistration code.

For intermediate SLC products, the `SlcPaths` class contains members for the paths for:
* The `.slc` files themselves (this holds the single-look complex image data)
* The `.par` files for each respective .slc file (this holds general GAMMA parameters/metadata about the .slc data)
* The `.TOPS_par` files for each respective .slc file (this holds S1 specific GAMMA parameters/metadata about the .slc data)
* The `.mli` files (these are multi-looked versions of the .slc files)

If data is being coregistered (this is the default, but can be disabled in NRT workflows), classes exist for the coregistered data in `CoregisteredPrimaryPaths` for the stack's primary scene (which is coregistered to the DEM, not another scene) and `CoregisteredSlcPaths` for every other scene - these classes have paths for:
* Properties with `primary` in the name refer to the respective coregistration's primary scene
* Properties with `secondary` in the name refer to the respective coregistration's secondary scene
* Properties with the `r_` prefix are the final "resampled"/coregistered data products.
* `.slc` / `.par` / `.mli` concepts are identical to and shared with `SlcPaths` documented above.
* As an example, `CoregisteredSlcPaths`'s `r_secondary_mli` property is the final resampled multi-look intensity image for the secondary scene being coregistered.

For backscatter products, the `BackscatterPaths` class holds the coregistered backscatter product paths:
* Properties starting with `sigma0` are for the non-terrain corrected backscatter, known as sigma0.
* Properties starting with `gamma0` are for the terrain corrected (using dem DEM) backscatter, known as gamma0.
* The `_geo` properties are the same products in geo coords.
* The `_geo_tif` properties are for the .tif versions of the `_geo` equivalent file.

For interferogram products, the `InterferogramPaths` class holds all of the interferogram product paths (this includes a LOT of intermediate products), unlike the SLC/MLI data these products have a few different terms:
* `ifg` is the common shortening of "Interferogram".
* `base` products are the initial interferogram before any refinement is applied.
* `flat` products are the refined interferograms (if any refinement is applied) with more precisely simulated interferometry.
* `filt` products are the smoothed/filtered interferograms, derived from the `flat` products.
* The other product files are complicated implementation details that are more relevant to the InSAR team who work with the data directly and aren't covered in this guide.

Finally the stack as a whole also has a bunch of paths defined in `StackPaths` (refer to their docstrings and relevant documentation in [insar/docs/Stack.md](../Logging.md) which covers these in detail).

## Project configuration (.proc) file class ##

A lot of the code base is configurable in various ways (file locations, algorithmic settings, feature flags, ancillary data locations, etc).  These configuration settings mostly come from a single processing settings file (often referred to as the ".proc" or settings file).

The `ProcConfig` class currently lives in `insar/project.py` and has functions for loading/validating .proc files, and a list of all of the settings attributes - however for some documentation on what these attributes are for `insar/template.proc` is the current reference file which documents these settings best.

## User facing CLI scripts ##

The `insar/scripts/` directory holds all the CLI scripts used by users to run the `gamma_insar` processing pipeline, however 3 specifically are the most important:
1. `insar/scripts/insar_pbs.py` - this script is the PBS job launcher, for users on the NCI or any other system using PBS for scheduling/running jobs.  It's the main script our current users are using to process their data.
It essentially takes in the user's stack properties & PBS details, validates them, sets up a PBS bash script for the processing, and then `qsub`'s it for them.
2. `insar/scripts/package_insar.py` - this script uses the `eodatasets3` module to package a `gamma_insar` stack ready for use by ODC (open data cube).
3. `insar/scripts/process_nci_report.py` - this script will analyse an existing stack (complete or not) and give a summary of the state of the stack, any missing or failed products, etc.

## Logging Infrastructure ##

The logging infrastructure for the project is relatively trivial, we use `structlog` for writing JSON-L logs for the various logs defined in [the logging documentation](insar/docs/Logging.md).

`insar.logs` has 4 logging variables:
1. `TASK_LOGGER` - a logging interface used by tasks to log their success/failure (and nothing else).
2. `INTERFACE_LOGGER` - the primary logging file used by the luigi workflow / tasks.
3. `STATUS_LOGGER` - the logger where higher-level concise logging information is provided to users, this is probably the most important log for 'most' code.
4. `INSAR_LOG` - the logger where low-level details and all GAMMA calls are logged, this log can grow to gigabytes in size in production stacks & includes all important low level details about every single step in the processing pipeline (for debugging and reproducibility use cases).

## Project Constants ##

For a variety of reasons there are constant numbers/names/etc that are used throughout the project.
All of these constants are found in the `insar/constant.py` file.

As work is done on the project it's ideal if we can identify and move any magic/constant values like this into that file, and maintain their usage instead of spreading magic numbers throughout the code base.

## GAMMA python interface ##

Most of the processing done by `gamma_insar` is done by thirdparty software called GAMMA, which is primarily a suite of command line tools intended to be used directly by humans in a console.

We use these programs programmatically through a simple command line wrapper called `GammaInterface` in `insar/py_gamma_ga.py` which identifies the GAMMA executables available at runtime which:
* exposes them as attribute functions which automatically forward the function's parameters as command line arguments
* automatically converts appropriate argument types (eg: `None` and `Path` types)
* automatically logs the GAMMA call (success or fail) to the appropriate log
* automatically detects failures and converts that into a runtime exception.

`insar/py_gamma_ga.py` is a drop in replacement for the GAMMA supplied `py_gamma.py` module. GAMMA's module is intended to handle interactive use and contains asynchronous/non-blocking code. In practice, this is more complex and not required for `gamma_insar`. GA uses `insar/py_gamma_ga.py` as its single-threaded design results in shorter processing runtimes.

This interface is often given the `pg` variable name in processing modules, instantiated at the module level as `pg = GammaInterface(...)` thus all `pg.abc()` calls are calls into GAMMA.

