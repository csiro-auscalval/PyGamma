# Adding new sensors to GAMMA InSAR

The following guide explains the process to constructing the code required to incorporate a new sensor into the processing framework.

As of mid-2022, `GAMMA InSAR` supports several sensors in addition to `Sentinel-1`. Geoscience Australia's software is designed to handle data from multiple sensors, as long as they are supported by the `GAMMA` software package. A list of supported sensors is included in [this PDF from GAMMA](https://gamma-rs.ch/uploads/media/GAMMA_Software_information.pdf). `GAMMA InSAR` only supports a small subset of these, the PDF list is intended as an example of sensors which _could_ be supported.

Please see the `insar/sensors` directory for a list of currently supported sensors. If a sensor is not supported by `GAMMA InSAR`, user contributions are welcomed.

## Development Process

The following is a semi-detailed overview of the process, assuming a sensor called `xyz` is being added to the workflow. For live examples, the ALOS and RS2 sensors are useful templates, being simple/normal use cases. The S1 data is an exceptional case with more complicated code due to its data structure and custom coregistration process.

If you are unfamiliar with the Git/project workflow, see [the contributing guide](governance/ContributingCode.md).

### Test data setup

The `GAMMA InSAR` project relies on real, but small datasets for testing.

1. Obtain test data files/data archives (e.g. `.zip`, `.tar.gz`) for 2-3 scenes. Small areas are good as for testing and storing as unit test data. For instance, see `tests/data/TSX` for an example data structure.
2. To reduce test data cruft, manually strip out any unnecessary files in the archive such as documents, HTML, preview images (e.g. see `tests/data/TSX/20170411_TSX_T041D.tar.gz`). As a general guide, the InSAR team aims to keep to individual data files to 1 megabyte or less. You may need to decompress the data, edit and then recompress in the same format to mimic a normal data file.
3. Most of the file content ought to reside in the image data files. There are multiple ways to handle these. Obscure binary formats can be resized to 0, e.g. `truncate -s 0 some_large_data_file.ext`. Here, _obscure_ means any data format not recognised by a common tool like GDAL. For GDAL supported formats, a command like `gdal_translate --scale 0 10000 0 0 -co "COMPRESS=PACKBITS" input.tif output.tif` will scale the data to zero, apply compression & retain a valid image. Retaining a valid image is likely to only be useful if **not** using a mocked version of `GAMMA` for testing.
4. From the project root, create a directory for unittest data, e.g. `tests/data/xyz/`.
5. Copy the stripped down files to this location.

### Creating the sensor module

The sensor module extends functions defined in `insar/sensors/data.py` which form part of the data processing framework.

1. From the project root, create an `insar/sensors/xyz.py` module.
2. Add a variable `SOURCE_DATA_PATTERN` and implement a `regex` pattern to match data files for the `xyz` sensor.
3. Implement the `METADATA` structure, which requires finding satellite constellation names, sensor names, altitude details & supported polarisations. These details should be provided in a technical reference document for the satellite/sensor (see the TSX sensor module for an example). We recommend including links to source document(s) in the code comments.
4. Implement the `get_data_swath_info()` function (also in `data.py`). The `data_path` arg is path to an archive file (or possibly a dir) of data. The function needs to extract metadata from the archive, store in a `dict` and return to the caller. Typically, the details are sourced from the data file name and/or metadata file(s) contained within.
5. Next, implement `acquire_source_data()`. This function extracts data from archives (if required) and returns a _directory_ path to the data product. The returned path is later provided to the `Luigi` based `DataDownload` task (described below). The path returned is typically the first level directory in the data archive. For example, if the archive contains the files: `root_dir/example_metadata.xml`, `root_dir/example_sar_data.tiff`, `root_dir/example_content.xml`, the return path should be the `source_data_dir/root_dir`.  The `source_path` arg is typically the path to either the raw data dir or an archive file. The `dst_dir` is  typically a dir like `some/dir/path/raw_data/{scene_date}`. Note the addition of a scene date for the acquisition.

### Sensor package configuration

1. Locate `insar/sensors/__init__.py`
2. Update `__init__.py` to include details of the new sensor, following the existing pattern.

### Updating data.py

Some modifications are required so the data processing mechanism recognises new sensors.

1. In the `insar/sensors/data.py` module, import the name of the new module.
2. Update the `_sensors` dict to reference the new module.
3. Add code to `identify_data_source()` to recognise files specific to your sensor.

### Processing code

New code modules are required to encapsulate sets of `GAMMA` commands.

1. Create a new module for the GAMMA processing commands, e.g. `insar/process_xyz_slc.py`.
2. Implement a `process_xyz_slc()` function in this module. This provides the `product_path` (mentioned above), which specifies the dir containing a path from `acquire_source_data()`. The processing function needs to use this dir to locate relevant data files, providing these as args to `GAMMA` command(s) to convert and process to GAMMA SLCs. Limited sensors are included the retired `BASH` version of `GAMMA InSAR`, from which example processing workflows may be available. See the master branch for details (usually `process_SENSOR_NAME_SLC.bash`).
3. Incorporate metadata processing. A copy of [this code block](https://github.com/GeoscienceAustralia/gamma_insar/blob/pygamma_workflow/insar/process_rsat2_slc.py#L61-L80) needs to be included at the end of the `process_xyz_slc()` function. This is not ideal, but is a workaround until the processing mechanism is refactored.
4. It is recommended that the GAMMA commands are run to generate real outputs from the test data.

### Processing unit tests

This section explains how to write unittests for the sensor processing code.

1. From the project root, create `tests/test_process_xyz_slc.py`.
2. Some test fixtures should be created in `tests/fixtures.py` to simulate data provided by the system. Several examples exist for the sensors already implemented.
3. As a guide, it is recommended to write tests for:
  - A default "success" case.
  - Confirmation of failure if a source input is missing.
  - Confirmation of failure if a data archive lacks a key file.
  - Confirmation of failure if a data archive lacks a key directory.
  - It may also be possible to test with a corrupted data archive.
4. Ensure the unittests pass.

### Sensor unit tests

1. Locate `tests/test_sensors.py`.
2. Implement sensor specific tests for:
  - `test_xyz_source_data_identification()`.
  - `test_xyz_swath_data_for_known_input()`.
  - `test_xyz_swath_data_fails_for_missing_input()`.
  - `test_xyz_swath_data_fails_for_invalid_input()`.
  - `test_xyz_acquisition_for_good_input()`.
  - `test_xyz_acquisition_for_corrupt_tar_gz()`.
  - `test_xyz_acquisition_missing_input()`.
3. Ensure the unittests pass.

### Project configuration

1. Locate `insar/project.py`.
2. Update the `sensor_caps` variable to list the new sensor in `ProcConfig.validate()`. This provides `GAMMA InSAR` recognition of the new sensor.

### Luigi workflow configuration

The workflow requires custom code to enable the new sensor processing steps.

1. From the project root, create `insar/workflow/luigi/xyz.py` module.
2. Create a `class` named `ProcessXYZSlc`, inheriting from `luigi.task`. This can potentially be cut and pasted from another sensor example, and tweaked for use. The task needs to call the `process_xyz_slc()` function implemented earlier, adapting the input args as required.
3. Secondly, create a `CreateXYZSlcTasks` class, also inheriting from `luigi.task` and with the `@requires(InitialSetup)` decorator. For the time being (mid 2022), the main body of this can be copied from existing sensor implementations (e.g. RSAT or TSX). The core of the function needs to be modified for the new sensor, including:
  - Ensure the polarisation is valid.
  - The raw data exists.
  - There is only one dir source of raw data.
  - A new `ProcessXYZSlc` task is created with appropriate args.

### Luigi stack setup

1. Locate `insar/workflow/luigi/stack_setup.py`
2. Update the `DataDownload` class to add a handler for the new sensor. This may be as simple as a `pass` statement to skip further processing.
3. (Likely optional step) if some form of custom setup is required, it can be placed in this handler. This handler is not ideal and may be changed in the future.

### Multilook configuration

The multilook feature needs to be tweaked to allow down-sampling of images. Multilooking depends on sensor-specific SLC processing tasks:

1. Locate the `insar/workflow/luigi/multilook.py` module.
2. Update the `CreateMultilook.requires()` function with a case to handle the new sensor. This is where naming needs to be consistent, otherwise the lookups will fail. The function also needs to use the `CreateXYZSlcTasks` from above.

### Resume configuration

The resume after crash/failure feature also needs to be made aware of the new sensor.

1. Locate `insar/workflow/luigi/resume.py`.
2. Update `ReprocessSingleSLC.run()` to include a handler block for the new sensor. Ensure the block correctly handles the data paths for the `ProcessXYZSlc` task.

### Final tasks

1. Run the code on a GAMMA enabled system (see documentation for running the workflow). Some run/debug/fix cycles may be required to bring the production code up to a working standard.
2. Update the relevant README docs for the new sensor (TODO: list specific files).
3. Ensure the unittests pass.
4. Create a pull request with all the changes (see contributing documentation).
5. Contact the InSAR team who can assist with verifying the results of a real data run & merging the changes.

## Troubleshooting

Testing and debugging the workflow can be a tricky process (especially on HPC systems accessed with PBS systems). The following is an incomplete list of problems that can occur:

* If the file path search regexes or mechanics are wrong in `get_data_swath_info()`, `GAMMA InSAR` will not be able to find the data. This should be logged as an error in the sensor code (see `RSAT` for an example).
* If your sensor's `acquire_source_data()` file handling/regex code doesn't correctly handle path args, this can also cause failures due to data not being found.
* In the event of missing errors, unclear debugging data etc, please raise an issue.
