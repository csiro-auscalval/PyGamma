`gamma_insar` stacks have a few metadata files which contain information on the stack itself, as well as some of it's products.  These files ultimately provide enough information (when combined with the stack's .proc settings) to reproduce the whole stack from scratch.

At a high level, the two sets of metadata files in the stack are:
 * The stack metadata, named `metadata.json` in the output directory of the stack itself.
 * The SLC product metadata, named `metadata_<POL>.json` where `POL` is the polarisation of the product, and located in each SLC scene directory.

Stacks will often have multiple polarisations, so multiple SLC metadata files will exist per scene.

## Stack Metadata ##

At the top level of the stack's output directory exists `metadata.json` - this file contains the stack-wide metadata in JSON format with properties described below.

| Name | Description|
| --- | --- |
|`"stack_id"`|The human identifier of the stack / the stack's name|
|`"original_work_dir"`|The path to the original output directory when the stack was processed|
|`"original_job_dir"`|The path to the original job directory when the stack was processed|
|`"shape_file"`|The path to the shapefile that was used to define the shape's geospatial extents (if any)|
|`"database"`|The path to the geospatial temporal database that was used to query input scenes from|
|`"source_data"`|A list of additional paths to input data that was processed by the stack in addition to those from the geospatial/temporal query from the DB (if any)|
|`"stack_extent"`|The final computed geospatial stack extent, in the format `[[min lon, min lat], [max lon, max lat]]`|
|`"poeorb_path"`|The path to the Sentinel-1 precise orbit files used for processing (if any)|
|`"resorb_path"`|The path to the Sentinel-1 restitute orbit files used for processing (if any)|
|`"source_data_path"`|The most common base directory of all source data acquisitions queried from the DB that were processed by the stack.|
|`"dem_path"`|The path to the input reference DEM used for stack processing|
|`"primary_ref_scene"`|The scene date (`YYYYMMDD` format) that the stack uses as the primary scene|
|`"include_dates"`|A list of date ranges to query the DB for scenes that are to be **included** in the stack|
|`"exclude_dates"`|A list of date ranges to **exclude** from the stack (overrides `include_dates`)|
|`"burst_data"`|The path to the .csv file which holds Sentinel-1 burst data information for all acquisitions included in the stack|
|`"num_scene_dates"`|The number of scene dates the stack contains|
|`"polarisations"`|The polarisations included in stack processing|
|`"gamma_version"`|The version of GAMMA that was used to process the stack|
|`"gamma_insar_version"`|The version of `gamma_insar` that was used to process the stack|
|`"gdal_version"`|The version of GDAL that was used on the system for processing|

## SLC Metadata ##

Each SLC product also has it's own metadata JSON file, one for each polarisation.  The SLC metadata holds provenance information.

The SLC metadata JSON is split into multiple top-level dict entries.  The `"slc"` entry contains common data for all acquisitions in the scene - properties in this dict apply to all acquisitions (unless overwritten by an acquisition specific property), additionally top level dicts with sensor-specific names may exist for acquisitions that have unique properties.

Regardless of if the property is in the `"slc"` entry, or an acquisition specific entry - the SLC metadata properties are as follows:

| Name | Description|
| --- | --- |
|`"src_url"`|The path to the original acquisition data that was used to contribute to this scene|
|`"orbit_url"`|The path to the original orbit file that was used for the acquisition and/or scene processing|
