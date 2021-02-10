#!/usr/bin/env python

"""
PBS submission scripts.
"""

from __future__ import print_function

import os
import uuid
import time
import json
import click
import warnings
import subprocess
from pathlib import Path
from os.path import join as pjoin, dirname, exists, basename

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
"""

PBS_TEMPLATE = r"""{pbs_resources}

source {env}
export OMP_NUM_THREADS={num_threads}
export TMPDIR={workdir}
gamma_insar ARD \
    --proc-file {proc_file} \
    --vector-file-list {vector_file_list} \
    --start-date {start_date} \
    --end-date {end_date} \
    --workdir {workdir} \
    --outdir {outdir} \
    --polarization '{json_polar}' \
    --workers {worker} \
    --local-scheduler \
    --cleanup {cleanup}
"""

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

FMT1 = "job{jobid}.bash"
FMT2 = "input-{jobid}.txt"
STORAGE = "+gdata/{proj}"


def scatter(iterable, n):
    """
    Evenly scatters an interable by `n` blocks.
    """

    q, r = len(iterable) // n, len(iterable) % n
    res = (iterable[i * q + min(i, r) : (i + 1) * q + min(i + 1, r)] for i in range(n))

    return list(res)


def _gen_pbs(
    proc_file,
    scattered_tasklist,
    env,
    workdir,
    outdir,
    start_date,
    end_date,
    json_polar,
    pbs_resource,
    cpu_count,
    num_workers,
    num_threads,
    cleanup
):
    """
    Generates a pbs scripts
    """
    pbs_scripts = []

    for block in scattered_tasklist:

        jobid = uuid.uuid4().hex[0:6]
        job_dir = pjoin(workdir, "jobid-{}".format(jobid))
        if not exists(job_dir):
            os.makedirs(job_dir)

        out_fname = pjoin(job_dir, FMT2.format(jobid=jobid))
        with open(out_fname, "w") as src:
            src.writelines(block)

        pbs = PBS_TEMPLATE.format(
            pbs_resources=pbs_resource,
            env=env,
            proc_file=proc_file,
            vector_file_list=basename(out_fname),
            start_date=start_date,
            end_date=end_date,
            workdir=job_dir,
            outdir=outdir,
            json_polar=json_polar,
            worker=num_workers,
            num_threads=num_threads,
            cleanup="true" if cleanup else "false"
        )

        out_fname = pjoin(job_dir, FMT1.format(jobid=jobid))
        with open(out_fname, "w") as src:
            src.writelines(pbs)

        pbs_scripts.append(out_fname)

    return pbs_scripts


def _submit_pbs(pbs_scripts, test):
    """
    Submits a pbs job or mocks if set to test
    """
    for scripts in pbs_scripts:
        print(scripts)
        if test:
            time.sleep(1)
            print("qsub {job}".format(job=basename(scripts)))
        else:
            time.sleep(1)
            os.chdir(dirname(scripts))
            subprocess.call(["qsub", basename(scripts)])


@click.command(
    "ard-insar",
    help="Equally partition a jobs into batches and submit each batch into the PBS queue.",
)
@click.option(
    "--proc-file",
    type=click.Path(exists=True, readable=True),
    help="The file containing gamma process config variables",
)
@click.option(
    "--taskfile",
    type=click.Path(exists=True, readable=True),
    help="The file containing the list of " "tasks to be performed",
)
@click.option(
    "--start-date",
    type=click.DateTime(),
    default="2016-1-1",
    help="The start date of SLC acquisition",
)
@click.option(
    "--end-date",
    type=click.DateTime(),
    default="2019-12-31",
    help="The end date of SLC acquisition",
)
@click.option(
    "--workdir",
    type=click.Path(exists=True, writable=True),
    help="The base working and scripts output directory.",
)
@click.option(
    "--outdir",
    type=click.Path(exists=True, writable=True),
    help="The output directory for processed data",
)
@click.option(
    "--polarization",
    default=["VV", "VH"],
    multiple=True,
    help="Polarizations to be processed VV or VH, arg can be specified multiple times",
)
@click.option(
    "--ncpus",
    type=click.INT,
    help="The total number of cpus per job" "required if known",
    default=48,
)
@click.option(
    "--memory", type=click.INT, help="Total memory required if per node", default=48 * 4,
)
@click.option(
    "--queue",
    type=click.STRING,
    help="Queue {express, normal, hugemem} to submit the job",
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
    "--nodes", type=click.INT, help="Number of nodes to be requested", default=1,
)
@click.option(
    "--workers", type=click.INT, help="Number of workers", default=0,
)
@click.option("--jobfs", type=click.INT, help="Jobfs required in GB per node", default=2)
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
def ard_insar(
    proc_file: click.Path,
    taskfile: click.Path,
    start_date: click.DateTime,
    end_date: click.DateTime,
    workdir: click.Path,
    outdir: click.Path,
    polarization: click.Tuple,
    ncpus: click.INT,
    memory: click.INT,
    queue: click.INT,
    hours: click.INT,
    email: click.STRING,
    nodes: click.INT,
    workers: click.INT,
    jobfs: click.INT,
    storage: click.STRING,
    project: click.STRING,
    env: click.Path,
    test: click.BOOL,
    cleanup: click.BOOL,
    num_threads: click.INT,
):
    """
    consolidates batch processing job script creation and submission of pbs jobs
    """
    # for GADI, a warning is provided in case the user
    # sets workdir or outdir to their home directory
    warn_msg = (
        "\nGADI's /home directory was specified as the {}, which "
        "may not have enough memory storarge for SLC processing"
    )
    if workdir.find("home") != -1:
        warnings.warn(warn_msg.format("workdir"))

    if outdir.find("home") != -1:
        warnings.warn(warn_msg.format("outdir"))

    if (queue != "normal") and (queue != "express") and (queue != "hugemem"):
        warnings.warn("\nqueue must either be normal, express or hugemem")
        # set queue to normal
        queue = "normal"

    # The polarization command for gamma_insar ARD is a Luigi
    # ListParameter, where the list is a <JSON string>
    # e.g.
    #    --polarization '["VV"]'
    #    --polarization '["VH"]'
    #    --polarization '["VV","VH"]'
    # The json module can achieve this by: json.dumps(polarization)
    json_pol = json.dumps(list(polarization))

    start_date = start_date.date()
    end_date = end_date.date()

    # Sanity check number of threads
    num_threads = int(num_threads)
    if num_threads <= 0:
        print("Number of threads must be greater than 0!")
        exit(1)

    with open(taskfile, "r") as src:
        tasklist = src.readlines()

    scattered_tasklist = scatter(tasklist, nodes)
    storage_names = "".join([STORAGE.format(proj=p) for p in storage])
    pbs_resources = PBS_RESOURCES.format(
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
    # add email to pbs_resources here.
    if email:
        pbs_resources += "#PBS -M {}".format(email)

    # Get the number of workers
    if workers <= 0:
        num_workers = int(ncpus / num_threads)
    else:
        num_workers = workers

    pbs_scripts = _gen_pbs(
        proc_file,
        scattered_tasklist,
        env,
        workdir,
        outdir,
        start_date,
        end_date,
        json_pol,
        pbs_resources,
        ncpus,
        num_workers,
        num_threads,
        cleanup
    )
    _submit_pbs(pbs_scripts, test)


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
    default=["VV", "VH"],
    multiple=True,
    help="Polarizations to be processed VV or VH, arg can be specified multiple times",
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
