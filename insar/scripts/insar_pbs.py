#!/usr/bin/env python

"""
PBS submission scripts.
"""

import os
import uuid
import time
import datetime
import json
import click
import warnings
import subprocess
import re
import geopandas
from typing import List
from pathlib import Path
from os.path import dirname, exists, basename
from insar.project import ARDWorkflow, ProcConfig

# Note that {email} is absent from PBS_RESOURCES
PBS_RESOURCES = """#!/bin/bash
#PBS -P {project_name}
#PBS -q {queue}
#PBS -l walltime={walltime_hours}:00:00,mem={mem_gb}GB,ncpus={cpu_count}
#PBS -l jobfs={jobfs_gb}GB
#PBS -l storage=scratch/{project_name}{storages}
#PBS -l wd
#PBS -j oe
#PBS -m e
#PBS -N {job_name}
"""

PBS_TEMPLATE = r"""{pbs_resources}

source {env}
export OMP_NUM_THREADS={num_threads}
export TMPDIR=$PBS_JOBFS
export TEMP=$TMPDIR
export TMP=$TMPDIR

gamma_insar ARD \
    --proc-file {proc_file} \
    --shape-file {shape_file} \
    --include-dates '{include_dates}' \
    --exclude-dates '{exclude_dates}' \
    --source-data '{source_data}' \
    --workdir {workdir} \
    --outdir {outdir} \
    --polarization '{json_polar}' \
    --workers {worker} \
    --local-scheduler \
    --cleanup {cleanup} \
    --workflow {workflow}"""

PBS_PACKAGE_TEMPLATE = r"""{pbs_resources}

source {env}
export TMPDIR={job_dir}
package \
    --track {track} \
    --frame {frame} \
    --input-dir {indir} \
    --pkgdir {pkgdir} \
    --product {product} \
    {pol_arg}
"""

STORAGE = "+gdata/{proj}"

__DATE_FMT__ = "%Y-%m-%d"


def _gen_pbs(
    job_name,
    proc_file,
    shape_file,
    env,
    job_dir,
    outdir,
    include_dates,
    exclude_dates,
    source_data,
    json_polar,
    pbs_resource,
    num_workers,
    num_threads,
    sensor,
    cleanup,
    append,
    resume,
    reprocess_failed,
    workflow,
    require_precise_orbit
):
    """
    Generates a PBS submission script for the stack processing job
    """

    with open(proc_file, "r") as proc_file_obj:
        proc_config = ProcConfig.from_file(proc_file_obj)

    # Convert dates into comma separated range strings
    include_dates = ','.join([f'{d1}-{d2}' for d1,d2 in include_dates])
    exclude_dates = ','.join([f'{d1}-{d2}' for d1,d2 in exclude_dates])

    # Convert to Luigi list syntax
    source_data = '[' + ','.join(f'"{i}"' for i in source_data) + ']'

    # Create PBS script from a template w/ all required params
    pbs = PBS_TEMPLATE.format(
        pbs_resources=pbs_resource,
        env=env,
        proc_file=proc_file,
        shape_file=shape_file or "''",
        include_dates=include_dates,
        exclude_dates=exclude_dates,
        source_data=source_data,
        workdir=job_dir,
        outdir=outdir,
        json_polar=json_polar,
        worker=num_workers,
        num_threads=num_threads,
        cleanup="true" if cleanup else "false",
        workflow=workflow
    )

    # Append onto the end of this script any optional params
    if sensor is not None and len(sensor) > 0:
        pbs += " \\\n    --sensor " + sensor

    if append:
        pbs += " \\\n    --append"

    if resume:
        pbs += " \\\n    --resume"

    if reprocess_failed:
        pbs += " \\\n    --reprocess-failed"

    if not proc_config.stack_id:
        pbs += " \\\n    --stack-id " + job_name.replace(" ", "_")

    if require_precise_orbit:
        pbs += " \\\n    --require-precise-orbit"

    # If we're resuming a job, generate the resume script
    out_fname = Path(job_dir) / f"job.bash"
    token = datetime.datetime.now().strftime("%Y%m%d_%H%M")

    if append:
        # Create resumption job
        append_fname = Path(job_dir) / f"job_append_{token}.bash"

        with append_fname.open("w") as src:
            src.writelines(pbs)
            src.write("\n")

        click.echo(f"Appending stack: {out_fname.parent}")
        return append_fname
    elif resume or reprocess_failed:
        # Create resumption job
        resume_fname = Path(job_dir) / f"job_resume_{token}.bash"

        with resume_fname.open("w") as src:
            src.writelines(pbs)
            src.write("\n")

        click.echo(f"Resuming existing job: {out_fname.parent}")
        return resume_fname

    # Otherwise, create the new fresh job script
    else:
        with out_fname.open("w") as src:
            src.writelines(pbs)
            src.write("\n")

        return out_fname


def _submit_pbs(job_path, test):
    """
    Submits a pbs job or mocks if set to test
    """
    click.echo(job_path)
    if test:
        time.sleep(1)
        click.echo("qsub", job_path)
    else:
        time.sleep(1)
        os.chdir(dirname(job_path))

        for retry in range(11):
            ret = subprocess.call(["qsub", basename(job_path)])
            if ret == 0:
                break

            click.echo(f"qsub failed, retrying ({retry+1}/10) in 10 seconds...")
            time.sleep(10)


def fatal_error(msg: str, exit_code: int = 1):
    click.echo(msg, err=True)
    exit(exit_code)


@click.command(
    "ard-insar",
    help="Equally partition a jobs into batches and submit each batch into the PBS queue.",
)
@click.option(
    "--proc-file",
    type=click.Path(exists=True, readable=True, file_okay=True, dir_okay=False),
    help="The file containing gamma process config variables",
)
@click.option(
    "--shape-file",
    type=click.Path(exists=True, readable=True, file_okay=True, dir_okay=False),
    help="The path to the shapefile for SLC acquisition",
)
@click.option(
    "--date-range",
    type=click.DateTime(), nargs=2,
    multiple=True,
    help="Includes the specified date range to be processed",
)
@click.option(
    "--date",
    type=click.DateTime(),
    multiple=True,
    help="Includes the specified date to be processed",
)
@click.option(
    "--exclude-date-range",
    type=click.DateTime(), nargs=2,
    multiple=True,
    help="Excludes the specified date range from being processed",
)
@click.option(
    "--exclude-date",
    type=click.DateTime(),
    multiple=True,
    help="Excludes the specified date from being processed",
)
@click.option(
    "--src-file",
    type=click.Path(exists=True, readable=True, file_okay=True, dir_okay=True),
    multiple=True,
    help="A path to source data file to process explicitly (in addition to any found from the query parameters)",
)
@click.option(
    "--workdir",
    type=click.Path(exists=False, writable=True, file_okay=False, dir_okay=True),
    help="The base working and scripts output directory.",
)
@click.option(
    "--outdir",
    type=click.Path(exists=False, writable=True, file_okay=False, dir_okay=True),
    help="The output directory for processed data",
)
@click.option(
    "--polarization",
    type=click.Choice(["VV", "VH", "HH", "HV"], case_sensitive=False),
    multiple=True,
    help="Polarizations to be processed, arg can be specified multiple times",
)
@click.option(
    "--ncpus",
    type=click.IntRange(min=1, max=48),
    help="The total number of cpus per job" "required if known",
    default=48,
)
@click.option(
    "--memory",
    type=click.IntRange(min=4, max=192),
    help="Total memory required if per node", default=48 * 4,
)
@click.option(
    "--queue",
    type=click.Choice(["normal", "express"], case_sensitive=False),
    help="Queue {express, normal} to submit the job",
    default="normal",
)
@click.option("--hours", type=click.INT, help="Job walltime in hours.", default=24)
@click.option(
    "--email",
    type=click.STRING,
    help="Notification email address.",
    default=None,
)
@click.option(
    "--workers", type=click.INT, help="Number of workers", default=0,
)
@click.option(
    "--jobfs",
    type=click.IntRange(min=2, max=400),
    help="Jobfs required in GB per node",
    default=2
)
@click.option(
    "--storage",
    "-s",
    multiple=True,
    type=click.STRING,
    help="Project storage you wish to use in PBS jobs",
)
@click.option(
    "--project", type=click.STRING, help="Project to compute under",
)
@click.option(
    "--env", type=click.Path(exists=True), help="Environment script to source.",
)
@click.option(
    "--test",
    type=click.BOOL,
    is_flag=True,
    help="mock the job submission to PBS queue",
    default=False,
)
@click.option(
    "--cleanup",
    type=click.BOOL,
    is_flag=False,
    help="If the job should cleanup the DEM/SLC directories after completion or not.",
    default=False
)
@click.option("--num-threads", type=click.INT, help="The number of threads to use for each Luigi worker.", default=2)
@click.option(
    "--sensor",
    type=click.Choice(["S1A", "S1B", "ALL", "MAJORITY"], case_sensitive=False),
    help="The sensor to use for processing (or 'MAJORITY' to use the sensor with the most data for the date range)",
    required=False
)
@click.option(
    "--append",
    type=click.BOOL,
    is_flag=True,
    help="Indicates the job is appending new dates to an existing stack.",
    default=False
)
@click.option(
    "--resume",
    type=click.BOOL,
    is_flag=True,
    help="If we are resuming an existing job, or if this is a brand new job otherwise.",
    default=False
)
@click.option(
    "--reprocess-failed",
    type=click.BOOL,
    is_flag=True,
    help="If enabled, failed scenes will be reprocessed when resuming a job.",
    default=False
)
@click.option(
    "--job-name",
    type=click.STRING,
    help="An optional name to assign to the job (defaults to the stack id of the job)",
    required=False
)
@click.option(
    "--workflow",
    type=click.Choice([o.name for o in ARDWorkflow], case_sensitive=False),
    help="The workflow to run",
    required=False,
    default="interferogram"
)
@click.option(
    "--require-precise-orbit",
    type=click.BOOL,
    is_flag=True,
    help="If enabled, only scenes with precise orbit files will be considered for processing.",
    default=False
)
def ard_insar(
    proc_file: click.Path,
    shape_file: click.Path,
    date_range: List[click.DateTime],
    date: List[click.DateTime],
    exclude_date_range: List[click.DateTime],
    exclude_date: List[click.DateTime],
    src_file: List[click.Path],
    workdir: click.Path,
    outdir: click.Path,
    polarization: click.Tuple,
    ncpus: click.INT,
    memory: click.INT,
    queue: click.STRING,
    hours: click.INT,
    email: click.STRING,
    workers: click.INT,
    jobfs: click.INT,
    storage: click.STRING,
    project: click.STRING,
    env: click.Path,
    test: click.BOOL,
    cleanup: click.BOOL,
    num_threads: click.INT,
    sensor: click.STRING,
    append: click.BOOL,
    resume: click.BOOL,
    reprocess_failed: click.BOOL,
    job_name: click.STRING,
    workflow: click.STRING,
    require_precise_orbit: click.BOOL
):
    """
    Consolidates creation of PBS job scripts and their submission.
    """

    # Validate .proc file
    with open(proc_file, "r") as proc_file_obj:
        proc_config = ProcConfig.from_file(proc_file_obj)

    proc_valid_error = proc_config.validate()
    if proc_valid_error:
        click.echo(f"Provided .proc configuration file is invalid:\n{proc_valid_error}", err=True)
        exit(1)

    # Convert to absolute path
    proc_file = Path(proc_file).absolute()

    # Validate we have a way to identify the stack
    if not (job_name or proc_config.stack_id):
        click.echo("No identifier for the job can be determined!", err=True)
        click.echo("Either set a STACK_ID in the .proc config, or pass in a --job-name", err=True)
        exit(1)

    # for GADI, a warning is provided in case the user
    # sets workdir or outdir to their home directory
    warn_msg = (
        "\nGADI's /home directory was specified as the {}, which "
        "may not have enough memory storage for SLC processing"
    )
    if workdir.find("home") != -1:
        warnings.warn(warn_msg.format("workdir"))

    if outdir.find("home") != -1:
        warnings.warn(warn_msg.format("outdir"))

    workpath = Path(workdir)
    outpath = Path(outdir)

    if resume or append:
        if not workpath.exists() or not any(workpath.iterdir()):
            click.echo("Error: Provided job work directory has no existing job!", err=True)
            exit(1)
    else:
        if workpath.exists() and any(workpath.iterdir()):
            click.echo(f"Error: Provided job work directory already exists: {workpath}", err=True)
            exit(1)

        if outpath.exists() and any(outpath.iterdir()):
            click.echo(f"Error: Provided job output directory already exists: {outpath}", err=True)
            exit(1)

        workpath.mkdir(parents=True, exist_ok=True)
        outpath.mkdir(parents=True, exist_ok=True)

    # Convert workflow into correct case, as we allow insensitve
    # casing to help usability, but Luigi requires sensitive.
    workflows = [o.name.lower() for o in ARDWorkflow]
    workflow_idx = workflows.index(workflow.lower())
    workflow = [o.name for o in ARDWorkflow][workflow_idx]

    # The polarization command for gamma_insar ARD is a Luigi
    # ListParameter, where the list is a <JSON string>
    # e.g.
    #    --polarization '["VV"]'
    #    --polarization '["VH"]'
    #    --polarization '["VV","VH"]'
    # The json module can achieve this by: json.dumps(polarization)
    json_pol = json.dumps(list(polarization))

    # Sanity check number of threads
    num_threads = int(num_threads)
    if num_threads <= 0:
        click.echo("Number of threads must be greater than 0!", err=True)
        exit(1)

    if not (shape_file and Path(shape_file).exists()) and not src_file:
        click.echo(f"Shape file does not exist: {shape_file}", err=True)
        exit(1)

    storage_names = "".join([STORAGE.format(proj=p) for p in storage])
    pbs_resources = PBS_RESOURCES.format(
        project_name=project,
        queue=queue,
        walltime_hours=hours,
        mem_gb=memory,
        cpu_count=ncpus,
        jobfs_gb=jobfs,
        storages=storage_names,
        job_name=job_name or proc_config.stack_id
    )
    # for some reason {email} is absent in PBS_RESOURCES.
    # Thus no email will be sent, even if specified.
    # add email to pbs_resources here.
    if email:
        pbs_resources += "#PBS -M {}".format(email)

    # Get the number of workers
    if workers <= 0:
        num_workers = int(ncpus / num_threads)
    else:
        num_workers = workers

    # Convert input params into consistent date ranges
    include_dates = list(date_range)
    for d in date:
        include_dates.append((d,d))

    exclude_dates = list(exclude_date_range)
    for d in exclude_date:
        exclude_dates.append((d,d))

    # Validate date range
    for from_date, to_date in include_dates:
        if from_date.year < 2016 or to_date.year < 2016:
            click.echo("[WARNING] Dates prior to 2016 are well not supported due to poor sensor data.", err=True)

    # TODO: Would be good to query the database for the latest date available, to use as an end-date bound

    # Validate shapefile if it conforms to a known framing definition
    if shape_file:
        shape_file = Path(shape_file)

        __TRACK_FRAME__ = r"^T[0-9][0-9]?[0-9]?[A|D]_F[0-9][0-9]?"

        # TODO: We should make this validation optional (this is specific to our framing definition)
        # - we probably want to define a framing definition as a first-class concept
        # - and allow it to validate extents / stack IDs / etc itself...

        # Match <track>_<frame> prefix syntax
        # Note: this doesn't match _<sensor> suffix which is unstructured
        if not re.match(__TRACK_FRAME__, shape_file.stem):
            msg = f"{shape_file.stem} should be of {__TRACK_FRAME__} format"
            fatal_error(msg)

        # Extract info from shape file
        vec_file_parts = shape_file.stem.split("_")
        if len(vec_file_parts) != 3:
            msg = f"File '{shape_file}' does not match <track>_<frame>_<sensor>"
            fatal_error(msg)

        # Extract <track>_<frame>_<sensor> from shape file (eg: T118D_F32S_S1A.shp)
        track, frame, shp_sensor = vec_file_parts

        # Ensure shape file is for a single track/frame IF it specifies such info
        # and that it matches the specified track/frame intended for the job.
        #
        # Note: Ideally we don't get track/frame/sensor from shape file at all,
        # these should be task parameters (still need to validate shape file against that though)
        shape_file_dbf = geopandas.GeoDataFrame.from_file(shape_file.with_suffix(".dbf"))

        if hasattr(shape_file_dbf, "frame_ID") and hasattr(shape_file_dbf, "track"):
            dbf_frames = shape_file_dbf.frame_ID.unique()
            dbf_tracks = shape_file_dbf.track.unique()

            if len(dbf_frames) != 1:
                fatal_error("Supplied shape file contains more than one frame!")

            if len(dbf_tracks) != 1:
                fatal_error("Supplied shape file contains more than one track!")

            if dbf_frames[0].strip().lower() != frame.lower():  # dbf has full TxxD track definition
                fatal_error("Supplied shape file frame does not match job frame")

            if dbf_tracks[0].strip() != track[1:-1]:  # dbf only has track number
                fatal_error("Supplied shape file track does not match job track")

    # Convert dates into string format
    def fmtdate(dt):
        return dt.strftime(__DATE_FMT__)

    include_dates = [(fmtdate(d1), fmtdate(d2)) for d1, d2 in include_dates]
    exclude_dates = [(fmtdate(d1), fmtdate(d2)) for d1, d2 in exclude_dates]

    # Generate and submit the PBS script to run the job
    pbs_script = _gen_pbs(
        job_name,
        proc_file,
        shape_file,
        env,
        workdir,
        outdir,
        include_dates,
        exclude_dates,
        src_file,
        json_pol,
        pbs_resources,
        num_workers,
        num_threads,
        sensor,
        cleanup,
        append,
        resume,
        reprocess_failed,
        workflow,
        require_precise_orbit
    )

    _submit_pbs(pbs_script, test)


@click.command("ard-package", help="sar/insar analysis product packaging")
@click.option(
    "--input-list",
    type=click.Path(exists=True, readable=True),
    help="full path to a file with list of track and frames to be packaged",
)
@click.option(
    "--workdir",
    type=click.Path(exists=True, writable=True),
    help="The base working and scripts output directory.",
)
@click.option(
    "--pkgdir",
    type=click.Path(exists=True, writable=True),
    help="The output directory for packaged data",
)
@click.option(
    "--ncpus",
    type=click.INT,
    help="The total number of cpus per node" "required if known",
    default=8,
)
@click.option(
    "--memory", type=click.INT, help="Total memory required per node", default=32,
)
@click.option(
    "--queue", type=click.STRING, help="Queue to submit the job into", default="normal",
)
@click.option(
    "--email",
    type=click.STRING,
    help="Notification email address.",
    default=None,
)
@click.option("--hours", type=click.INT, help="Job walltime in hours.", default=24)
@click.option("--jobfs", help="jobfs required in GB per node", default=2)
@click.option(
    "--storage",
    "-s",
    type=click.STRING,
    multiple=True,
    help="Project storage you wish to use in PBS jobs",
)
@click.option(
    "--project", type=click.STRING, help="Project to compute under", required=True,
)
@click.option(
    "--env",
    type=click.Path(exists=True),
    help="Environment script to source.",
    required=True,
)
@click.option(
    "--product",
    type=click.STRING,
    default="sar",
    help="The product to be packaged: sar| insar",
)
@click.option(
    "--polarization",
    default=["VV", "VH", "HH", "HV"],
    multiple=True,
    help="Polarizations to be processed, arg can be specified multiple times",
)
@click.option(
    "--test",
    type=click.BOOL,
    default=False,
    is_flag=True,
    help="mock the job submission to PBS queue",
)
def ard_package(
    input_list: click.Path,
    workdir: click.Path,
    pkgdir: click.Path,
    ncpus: click.INT,
    memory: click.INT,
    queue: click.STRING,
    email: click.STRING,
    hours: click.INT,
    jobfs: click.INT,
    storage: click.STRING,
    project: click.STRING,
    env: click.Path,
    product: click.STRING,
    polarization: click.Tuple,
    test: click.BOOL,
):

    # for GADI, a warning is provided in case the user
    # sets workdir and pkgdir to their home directory
    warn_msg = (
        "\nGADI's /home directory was specified as the {}, which "
        "may not have enough memory storarge for packaging"
    )
    if workdir.find("home") != -1:
        warnings.warn(warn_msg.format("workdir"))

    if pkgdir.find("home") != -1:
        warnings.warn(warn_msg.format("pkgdir"))

    storage_names = "".join([STORAGE.format(proj=p) for p in storage])

    pol_arg = " ".join(["--polarization "+p for p in polarization])

    pbs_resource = PBS_RESOURCES.format(
        project_name=project,
        queue=queue,
        walltime_hours=hours,
        mem_gb=memory,
        cpu_count=ncpus,
        jobfs_gb=jobfs,
        storages=storage_names,
    )
    # for some reason {email} is absent in PBS_RESOURCES.
    # Thus no email will be sent, even if specified.
    # add email to pbs_resource here.
    if email:
        pbs_resource += "#PBS -M {}".format(email)

    with open(input_list, "r") as src:
        # get a list of shapefiles as Path objects
        tasklist = [Path(fp.rstrip()) for fp in src.readlines()]

    pbs_scripts = []
    for shp_task in tasklist:
        # new code -> frame = FXX, e.g. F04
        track, frame, sensor = shp_task.stem.split("_")

        jobid = uuid.uuid4().hex[0:6]
        in_dir = Path(workdir).joinpath(f"{track}_{frame}")
        job_dir = Path(workdir).joinpath(f"{track}_{frame}-pkg-{jobid}")

        # In the old code, indir=task, where task is the shapefile.
        # However, indir is meant to be the base directory of InSAR
        # datasets. This leads to errors as the package command as
        # it expects the gamma outputs to be located there, e.g.
        # /shp_dir/T147D_F03.shp/SLC, /shp_dir/T147D_F03.shp/DEM
        # In the new code,
        # indir = in_dir

        if not exists(job_dir):
            os.makedirs(job_dir)

        pbs = PBS_PACKAGE_TEMPLATE.format(
            pbs_resources=pbs_resource,
            env=env,
            track=track,
            frame=frame,
            indir=in_dir,
            pkgdir=pkgdir,
            job_dir=job_dir,
            product=product,
            pol_arg=pol_arg,
        )

        out_fname = job_dir.joinpath(f"pkg_{track}_{frame}_{jobid}.bash")
        with open(out_fname, "w") as src:
            src.writelines(pbs)

        pbs_scripts.append(out_fname)
    _submit_pbs(pbs_scripts, test)
