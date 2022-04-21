## Introduction ##

This document provides an overview of what a "stack" is in the `gamma_insar` project.

At a high level a "stack" is simple a collection of "scenes" whose spatial extents match up exactly, with each scene having data that was aquired on a different date. A stack there for has a geospatial extent as well as a temporal extent associated with it, and is made up from a series of data acquisitions across it's temporal extent.

A stack may be appended to, however once data is added to the stack it may not be removed.  As data is appended to the stack, the structure which associates the scenes with one another is also updated/appended-to in such a way that there are consistent coregistration properties as well as consistent interferogram pairing properties across the temporal extent of scenes.

A major property of scenes processed in `gamma_insar` stacks is the fact they're coregistered, meaning every pixel in every scene is as closely aligned to the same geocoded coordinate as possible (and thus all scenes should be directly comparable at the pixel level).  This is critically important as interferometry is sensitive to differences much smaller than the area of a pixel (which is typically meters), and poorly aligned pixel data will result in poor interferometric coherence.

## Stack Properties ##

The stack has a set of high-level properties which define how it was produced, and ultimately could be used to re-produce the same stack.

Most stack properties are immutable, with the exception of the temporal extent and data sources which may be added to (but never removed from in any way).

All timestamps are in UTC.

| Name | Description|
| --- | --- |
| ID | A human identifier associated with the stack for people to reference |
| Geospatial extent | The extent that defines the geometry of all scenes in geospatial terms.  This is used to find & subset source data for inclusion in the stack to be processed. |
| Temporal extent | The range of dates (not necessarily a singular range) in which this stack accepts data to be included from. |
| Data sources | A set of locations in which source data for the stack to process is acquired from, this may be a DB index or a series of URLs or a combination. |
| Polarisations | A set of polarisations for which the stack contains data for. |
| DEM | The digital elevation model used for terrain correction and used to assist in coregistration |
| Primary scene date | The scene date which is considered the primary reference for all other scenes, this scene is the starting/reference point of all coregistration. |
| Primary polarisation | The polarisation which is considered authoritative within the stack (other polarised products may defer to primary pol data in some circumstances like coregistration).  Interferograms are only produced for the primary polarisation. |
| Processing settings | A processing configuration file with a set of properties which define 'how' the gamma_insar project processes the stack's scenes. |

## Stack Scenes ##

Scenes are defined as a continuous (eg: no holes within the geometry, and no separated geometry) geospatial region which has full sensor data coverage that are acquired on the same date.  All scenes in a stack share the same geospatial region (thus it's considered a stack property), and all scenes are assigned a specific date... however if a sequence of acquisitions into a scene span two dates (eg: around midnight UTC) then the date the data acquisition 'ends' is considered the scene date of those acquisitions.

A stack may be made up of one or more source data acquisitions, such as multiple swaths or segments of a track from a satellite acquisition;  in the case a scene's source data has more data than the scene defines, that data is ultimately removed during processing leaving just the data within the stack's geospatial region interact.

Scenes have provenance for all the source data that makes up the pixels in it's region for every polarisation. This information for a scene can be found in it's respective `metadata_POL.json` file in the SLC directory of the scene, where `POL` should be replaced for the respective polarisation of interest (eg: `VV`).  Note: For some satellites there may be little to no difference between metadata of different polarisations in the same date.

A stack is made up of many of these scenes stacked temporally, thus for the whole temporal region of the stack in which scenes exist - there exists sensor data for that scene's whole region, for every polarisation, traceable back to it's provenance.

## Stack Structure ##

A stack is ultimately a data product, which means it is physically stored on a medium somewhere.  The structure and contents of the stack's files are defined below.

The stack can ultimately be broken up into the DEM, SLC, interferograms, and stack lists - each of these has it's own dedicated folder in the top level directory of the stack whose names are typically `DEM`, `SLC`, `INT`, and `lists` respectively.


The `DEM` dir contains various data files containing DEM and how it correlates to the stack (via coreistration to the primary reference date) through various offset models used by GAMMA (primarily in coregistration/georeferencing).

The `SLC` dir contains a bunch of child dirs, one for each scene in the stack, named `YYYYMMDD` of the scene's date, which contain the SLC data and backscatter for that scene.

The `INT` dir contains a bunch of child dirs, one for each date-pair in the SBAS network of the stack for which an interferogram is produced, which contain the interferogram products for that date pair.

The `lists` dir contains all of the lists which describe 'how' the scenes are linked together;  specifically the scene dates list itself, the primary reference date, the coregistration tree, SBAS networks, and any information on stack appends that have been made reside here.  These files are described below in their own section.

Additionally the top level directory itself houses a few files, the most important of which are `metadata.json` which holds the metadata of the whole stack (such as the `Stack Properties` defined in the previous section) and `config.proc` which is the `Processing settings` stack property used for producing all the products in the stack.


## Stack `lists` file details ##

The `lists` dir contains many files which describe how the scenes in the stack are used together to produce the final products, each file is described below.

When a stack is first created, a manifest of all the dates in the stack, which date is the primary reference date, as well as a coregistration tree & SBAS network are produced for those dates.  After the stack is created, it may be appended to - this append process adds additional files with a sequentially increasing index applied before the file extension suffix (eg: `scenes.list` is the original stack scenes, if appended once a `scenes1.list` will appear with the additional data, and so on increasing by 1 each append).

The simplest files to understand are the `scenes.list` which is simply a line separated list of dates for which a scene exists, each line matches the `YYYYMMDD` date format.  Similarly, `primary_ref_scene` simply has the `YYYYMMDD` for the date of the primary reference scene.  Appends will produce additional `scenesN.list` but `primary_ref_scene` is immutable / will never change.

The next structural data stored in this dir is the `secondariesN.list` files - these correlate to the Nth level in the coregistration tree.  `secondaries1.list` is currently always the primary reference date as the root, each subsequent level branches out from the primary reference date with a list of dates which are +/- roughly 2 months from the previous level's outer most dates - thus all of the `secondariesN.list` combined essentially represent a tree structure known as the "coregistration tree" which is described in it's own section.  Like all the other date lists, these also follow the `YYYYMMDD` line separated format.  Unlike all the other lists in this dir, appends don't add a single new file with the append-index as it's suffix, but simply add new levels to the tree (thus the N does continue sequentially as the tree grows, but not in a way that correlates to the append-index - in fact if enough dates are appended multiple levels could be added).

The interferogram date-pairs are also stored in this dir as the `ifgs.list` (with `ifgsN.list` for all subsequent appends).  This is very simply a line-separated list of `YYYYMMDD-YYYYMMDD` date pairs for which interferograms are made for.  These date pairs are produced by the 'baseline' process in the workflow, which is exclusiely using the SBAS algorithm at present.

Lastly, for every append made to a stack there exists an `appendN.manifest` file which describes 'what' the append added to the the stack which isn't explicitly defined in one of the `scenesN.list` or `ifgsN.list` for the append - which currently is simply what range of coregistration tree levels were added as a result of this append.


## Key stack product files ##

This section describes the products of the stack that would be considered the main outputs of interest - as well as where they reside in the stack file structure.

### SLC mosaics ###

One of the first products the workflow produces is a mosaic of all the data that makes up the scene for that date, for some satellites with small enough stack extents this may not be much different to the input SLC, but for others (like Sentinel-1) this is a mosaic of multiple data acquisitions in spatially neighbouring regions stitched together to cover the stack's geospatial extents.

These products are written to the stack's SLC directory for each scene date, eg: `SLC/<scene_date>/...`.

The SLC mosaic product paths for the date `<scene_date>` and polarisation `<pol>` are:
 * `<scene_date>_<pol>.slc` - The mosaiced SLC data itself.
 * `<scene_date>_<pol>.slc.par` - The GAMMA .par file for the mosaiced SLC.

### Coregistered SLC ###

The SLC mosaics above are then coregistered with the primary reference scene of the stack (such that each pixel in all of the scenes are as closely alinged as possible), these coregistered SLC mosaics are then also multi-looked (downsampled) into smaller products.

These products are also written to the stack's SLC directory for each scene date, eg: `SLC/<scene_date>/...`.

The coregistered SLC mosaic product paths for the date `<scene_date>`, the range-look value `<N>`, and polarisation `<pol>` are:
 * `r<scene_date>_<pol>.slc` - The coregistered mosaiced SLC data itself.
 * `r<scene_date>_<pol>.slc.par` - The GAMMA .par file for the above SLC
 * `r<scene_date>_<pol>_<N>rlks.mli` - The final mosaiced/coregistered/multi-looked SLC data product.
 * `r<scene_date>_<pol>_<N>rlks.mli.par` - The GAMMA .par file for the above SLC

The `r` prefix is intended to represent the fact they've been re-sampled (with the coregistration LUTs that align the pixels).

### Normalised radar backscatter (NRB) ###

From the coregistered and downsampled SLC data, we produce NRB (normalised radar backscatter) data as one of the final output products for each scene in the stack.

These products are also written to the stack's SLC directory for each scene date, eg: `SLC/<scene_date>/...`.

The coregistered SLC mosaic product paths for the date `<scene_date>`, the range-look value `<N>`, and polarisation `<pol>` are:
 * `<scene_date>_<pol>_<N>rlks_geo_sigma0.tif` - The sigma0 NRB product for the scene.
 * `<scene_date>_<pol>_<N>rlks_geo_gamma0.tif` - The gamma0 NRB product for the scene.

### Interferograms ###

Lastly the main output product of `gamma_insar` is the interferometry itself, which is produced for the baseline determined by the stack - most scenes will take part in multiple baseline (this can be controlled by the `MIN_CONNECT` and `MAX_CONNECT` .proc settings).
Note: Interferometry is ONLY produced for the primary stack polarisation.

These products are written to the stack's INT directory for each scene date, eg: `INT/<primary_date>-<secondary_date>/...`.

The interferogram product paths for the baseline `<primary_date>-<secondary_date>`, the range-look value `<N>`, and polarisation `<pol>` are:
 * `<primary_date>-<secondary_date>_<pol>_<N>rlks_flat_geo_int.tif` - The early flattened interferogram product, geocoded.
 * `<primary_date>-<secondary_date>_<pol>_<N>rlks_flat_geo_coh.tif` - The interferometric coherence of the flattened interferogram, geocoded.
 * `<primary_date>-<secondary_date>_<pol>_<N>rlks_filt_geo_int.tif` - The adaptively filtered (Goldstein-Werner) inferferogram product, geocoded.
 * `<primary_date>-<secondary_date>_<pol>_<N>rlks_filt_geo_coh.tif` - The interferometric coherence of the filtered interferogram, geocoded.
 * `<primary_date>-<secondary_date>_<pol>_<N>rlks_geo_unw.tif` - The unwrapped interferogram product, geocoded.

## Developer Notes ##

For `gamma_insar` developers, the paths specified in this document are defined in the `insar.paths` modules - and must match the specifications in this document.  If either changes, the other should be updated to reflect the changes where appropriate.

Further details on intermediate file paths and their descriptions may also be found in the `insar.paths` class docstrings.
