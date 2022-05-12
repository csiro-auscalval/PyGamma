This document covers how to run the `gamma_insar` workflow to produce ARD (analysis ready data) products for NRB (normalised radar backscatter) and interferometry.

The style of this guide is a step-by-step tutorial like approach, and should leave the reader having actually run the workflow and having produced products for them to use.

This guide will inform the user on how to use the "Luigi ARD workflow runner" (using the `gamma_insar ARD` command), however it largely applies to the "PBS ARD workflow runner" (which is the `pbs-insar` command) that's often used on the NCI as well which shares an identical workflow (it uses the Luigi ARD runner under the hood) but has some differences in the parameters it takes.

When running `gamma_insar ARD` the workflow is being run on the local machine, and when running `pbs-insar` the workflow will be scheduled as a PBS job to run on a different machine via PBS.

If at any point in this guide the user is needing more details on stack processing properties or settings, they should refer to the source of help which is:
1. `gamma_insar ARD --help` for the main Luigi workflow
2. `pbs-insar --help` for the PBS workflow runner (often used on NCI)
3. `template.proc` in this repo for details on the .proc settings

This guide assumes the user has a working `gamma_insar` installation to use (see: `Installation.md`), and optionally has a geospatial/temporal database of acquisitions available (see: `DatabaseIndexing.md`).

## Data Acquisition ##

Before we can get started we are going to need access to some supported SAR data for us to process.  `gamma_insar` supports many sensors but the most commonly used will be Sentinel-1 thus we will proceed using that.

For this tutorial we will be taking 4x SLC Sentinel-1 acquisitions from ESA Copernicus, the relative paths for these acquisitions are:
```
.../C-SAR/SLC/2019/2019-12/30S145E-35S150E/S1A_IW_SLC__1SDV_20191222T193141_20191222T193207_030465_037CDD_4306.zip
.../C-SAR/SLC/2019/2019-12/30S145E-35S150E/S1A_IW_SLC__1SDV_20191222T193116_20191222T193143_030465_037CDD_8F90.zip
.../C-SAR/SLC/2020/2020-01/30S145E-35S150E/S1A_IW_SLC__1SDV_20200103T193115_20200103T193142_030640_0382E6_2B5C.zip
.../C-SAR/SLC/2020/2020-01/30S145E-35S150E/S1A_IW_SLC__1SDV_20200103T193140_20200103T193207_030640_0382E6_09FB.zip
```

For users running through this tutorial on the NCI, a mirror of this data can be found at `/g/data/fj7/Copernicus/Sentinel-1/C-SAR`

In addition to this the user will need to provide a shapefile from their framing definition which covers the stack's region of interest that we want to process data for.  Examples for these shapefiles can be found in `tests/data/...`

## Defining the stack ##

To start processing we need to define "what" we intend to process.  In very concise terms, this means defining all of the stack properties in `Stack.md` but for completeness we will describe the reasoning of appropriate settings below.

The most basic details we will want to establish is what we want to name our stack, and what date range the stack is producing data for (note: if there's no immediate end date that's okay - the end date can be set to the latest date for which data is available and the stack can have new dates appended at a later date).

The user will also want to identify what sensor they want to process data for, the polarisations of interest, and 'where' they want the data to be processed on the filesystem.

All of these properties will be assigned respectively to the following runner arguments:
```
    --stack-id '{stack_id}' \
    --sensor '{sensor}' \
    --polarization '{json_polar}' \
    --include-dates {include_dates} \
    --shape-file {shape_file} \
    --workdir {workdir} \
    --outdir {outdir} \
```

Note: There are currently a few minor inconsistencies between the Luigi ARD runner `gamma_insar ARD` and the PBS runner used on NCI `pbs-insar`, specifically in the above example `--include-dates` would be `--date-range` for `pbs-insar`.  This may be addressed in future releases.

## Processing settings ##

In addition to higher level stack properties, a key property of a stack is it's processing settings - often called the .proc file.  An example .proc file exists in this repo called `template.proc` which describes every single setting and what possible values for them may look like - this example file is also valid for processing S1 data / can genuinely be used to test some S1 stack processing.

Of particular importance, the following properties MAY be left undefined (eg, with no value: `PROPERTY=`) and in these cases the values will be inferred from the command line arguments provided by the user (this is helpful when users want to share .proc settings across many stacks):

* `STACK_ID` - will inherit the `--stack-id` value if undefined
* `JOB_PATH` - will inherit the `--workdir` value if undefined
* `OUTPUT_PATH` - will inherit the `--outdir` value if undefined

The .proc file is specified to the workflow runner via the `--proc-file` parameter.

## Running the workflow ##

Taking the properties we settled on from the previous sections and applying them to `gamma_insar ARD` runner, our arguments can look like two possible configurations depending on if we want to use a geospatial/temporal database, or if we want to provide the raw source acquisitions explicitly...

Passing source acquisitions via `--src-file` explicitly, the command will look like:
```
gamma_insar ARD \
    --stack-id tutorial_stack \
    --sensor S1 \
    --polarization VV --polarization VH \
    --source-data '["/path/to/our_s1_data/S1A_IW_SLC__1SDV_20191222T193141_20191222T193207_030465_037CDD_4306.zip", \
                    "/path/to/our_s1_data/S1A_IW_SLC__1SDV_20191222T193116_20191222T193143_030465_037CDD_8F90.zip", \
                    "/path/to/our_s1_data/S1A_IW_SLC__1SDV_20200103T193115_20200103T193142_030640_0382E6_2B5C.zip", \
                    "/path/to/our_s1_data/S1A_IW_SLC__1SDV_20200103T193140_20200103T193207_030640_0382E6_09FB.zip"]' \
    --shape-file /path/to/our/shapefile.shp \
    --proc-file our_stack_settings.proc \
    --workdir /path/to/workdir \
    --outdir /path/to/outdir \
    --local-scheduler
```

Note: In the above example we don't need to provide a `--include-dates` - it's inferred by the data we provide, and if using `pbs-insar` we would use `--src-file` instead of `--source-data`.

Using the geospatial/temporal database, the command will look like:
```
gamma_insar ARD \
    --stack-id tutorial_stack \
    --sensor S1 \
    --polarization VV --polarization VH \
    --include-dates '2019-12-20-2020-01-05' \
    --shape-file /path/to/our/shapefile.shp \
    --proc-file our_stack_settings.proc \
    --workdir /path/to/workdir \
    --outdir /path/to/outdir \
    --local-scheduler
```

Note: If using `pbs-insar` to launch a PBS job, an additional parameter is required for providing an environment script that the job uses to setup the gamma environment for the job, eg: `--env /path/to/gamma_insar_install/NCI.env` - and the `--local-scheduler` parameter is not required.

## High performance computing ##

In the previous example we ran the ARD workflow on the user's local machine without specifying 'how' to use that machine, however this is not the best use of resources in all cases.

The workflow supports spreading tasks across multiple cores by specifying how many tasks are allowed to run concurrently (`--workers`), and how many threads/cores each task may use (`--num-threads`).

As an example, to process up to 4 products at a time on a 32 core machine a user may want to use: `--workers 4 --num-threads 8`

For users running on the NCI (or any other cluster using PBS for job scheduling), the above applies equally however the command is `pbs-insar` - this command is a helper that will generate a PBS job script that calls a similar `gamma_insar ARD` command on the scheduled node for the user, submitting that job to the queue specified with the resources requested.

Additional arguments for `pbs-insar` are required to specify the project/user/resources of the job:
```
    --queue normal --hours 48 \
    --ncpus 48 --memory 192 \
    --workers 4 --num-threads 12 \
    --email the_users@email.net \
    --jobfs 40 --storage my_pbs_storage_project \
    --project my_pbs_compute_project
```

The above is an example to submit a job to the `normal` PBS queue that will run for up to 48 hours, using 192GB of memory and 48 cores (with Luigi running 4x workers with 12 threads = 48 cores used).

## Analysing the status of the stack ##

Once the stack has started (or finished, success or failure) processing it's possible to report on the status of the stack with the `insar/scripts/process_nci_report.py` script, the usage is trivial (refer to it's `--help`) and lets the user get information on the state of the stack and it's products - including product error reporting & for NCI users also provides time estimates for incomplete jobs.

The script can produce detailed JSON reporting information, a CSV summary, and print out the details in a human readable format as well - below is an example of a stack report.

The following is an example of the output you should see after running this tutorial (using the geospatial/temporal database in this scenario):
```
python ~/gamma_insar/insar/scripts/process_nci_report.py work_dir/job-T118D_F32S_S1A
================================================================================
===================== gamma_insar processing summary report =====================
=== generated at 2022-02-21 15:59:42.004631 on gadi-login-06.gadi.nci.org.au ===
================================================================================
Stack ID: T118D_F32S_S1A
Shape file: /g/data/up71/projects/InSAR-ARD/S1_frames/T118D_F32S_S1A.shp
Database: /g/data/up71/projects/InSAR-ARD/generate_yaml_db/AUS_201601_to_202104.db
Polarisations: ['VV', 'VH']
Total scenes: 2

================================== Run Summary ==================================
[2022-02-21 11:07:41] Job ran for 0:29:41 using 47.49 SU from dg9

Total walltime: 0:29:41
Total SU used: 47.49


================================ Product Summary ================================
Completed 4/4 (100.000%) backscatter products!
Completed 1/1 (100.000%) IFG products!
Missing 0 backscatter products!
Missing 0 IFG products!
Failed 0 backscatter products!
Failed 0 IFG products!
```

As you can see it gives a simple summary of the stack, it's processing, and product outcomes.

## Checking the data outputs ##

After a stack has finished processing one of the first things you're likely to want is to verify the processing worked, and if not what products were impacted and why...

The reporting script from the previous can also report on product errors to achieve this very goal and is used just as it was before, below is an example of the report details from a stack with an error.

```
================================================================================
===================== gamma_insar processing summary report =====================
=== generated at 2022-02-22 13:47:34.435212 on gadi-login-01.gadi.nci.org.au ===
================================================================================
Stack ID: T118D_F32S_S1A
Shape file: /g/data/up71/projects/InSAR-ARD/S1_frames/T118D_F32S_S1A.shp
Database: /g/data/up71/projects/InSAR-ARD/generate_yaml_db/AUS_201601_to_202104.db
Polarisations: ['VV', 'VH']
Total scenes: 2

================================== Run Summary ==================================
[2022-02-22 13:42:24] Job ran for 0:28:22 using 45.39 SU from dg9

Total walltime: 0:28:22
Total SU used: 45.39


================================= Ifg failures =================================
[2022-02-22T02:41:42.687190Z | IFG processing | primary_date: 20191222 | secondary_date: 20200103] Failed to execute gamma command: mcf
ERROR: number of path nodes and arcs exceeds maximum length 2000000: 2000001

================================ Product Summary ================================
Completed 4/4 (100.000%) backscatter products!
Completed 0/1 (0.000%) IFG products!
Missing 0 backscatter products!
Missing 0 IFG products!
Failed 0 backscatter products!
Failed 1 IFG products!

Estimated walltime to complete: 0:03:45
Estimated SU to complete: 6.000
```

As you can see above, this stack had an error processing the interferogram product due to a GAMMA `mcf` failure.  In this case we've been given the products impacted, the time of error, the error text (a common GAMMA mcf failure) & the summary reflects our missing IFG indicating we need to address issues before we can consider the stack complete.

## Checking the logs ##

Finally, if something obscure happens it's possible to investigate the log files in the stack's job directory.

Specifically at a high level the `status-log.jsonl` log has per-product overviews of how things went, and `insar-log.jsonl` has lower level information about every single GAMMA command that was executed (including full command line outputs) plus ancillary logged events.

An existing document already exists that is best placed to help users understand these logs: `Logging.md`

## Recovering from an incomplete job/stack ##

Sometimes a job will be interrupted before it can finish processing for some reason such as a system/power related failure.  In this scenario the processed data already computed is not wasted or lost, as a stack can be "resumed" at any time to continue processing any missing products in the stack.

This process is as simple as running the **exact** same command as you did to process your original stack, with the **exact** same settings (any deviation will raise an error stating the stack is not the same) using the `--resume` flag.

To copy the geospatial-DB example from the start of this guide, the equivalent resume command would be:
```
gamma_insar ARD \
    --stack-id tutorial_stack \
    --sensor S1 \
    --polarization VV --polarization VH \
    --include-dates '2019-12-20-2020-01-05' \
    --shape-file /path/to/our/shapefile.shp \
    --proc-file our_stack_settings.proc \
    --workdir /path/to/workdir \
    --outdir /path/to/outdir \
    --local-scheduler \
    --resume
```

The status log will have events indicating what products were detected as missing, and that they have been resumed for processing.

## Recovering from products with errors ##

In some circumstances errors will occur in products as a result of complexity issues in the scene that GAMMA can not handle, or environmental issues in the thirdparty libraries being used, or possibly a `gamma_insar` bug.  These errors can be identified using the reporting scripts already described in prior sections of this guide.

Alternatively if there is **any* other reason at all the user needs to re-process a specific product it can be deleted and re-processed with this method.

Once scenes have been identified, simply deleting their respective product date directories in the stack and `--resume` 'ing them with the the recovery of an incomplete stack described above can be applied (as deleting the products essentially makes the stack incomplete and ready for resuming).

## Appending new data to a stack ##

If users have a need to extend the temporal period of their stack, `gamma_insar` does support adding dates **after** the current end date of a stack (a.k.a. extending the end date of a stack).  Like much of the post-initial-stack processing, this is largely supported by simply adding a single extra flag to a standard stack processing command - namely `--append`.

Unlike `--resume` which requires that the stack properties for the command match the existing stack **exactly**, `--append` allows that the end-date of the stack to change as well as for extra source files to be provided past the original end date.
