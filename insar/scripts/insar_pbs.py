#!/usr/bin/env python

"""
PBS submission scripts.
"""

from __future__ import print_function

import os
from pathlib import Path
import click
from os.path import join as pjoin, dirname, exists, basename
import subprocess
import uuid
import time


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
gamma_insar ARD --vector-file-list {vector_file_list} --start-date {start_date} --end-date {end_date} --workdir {workdir} --outdir {outdir} --workers {worker} --local-scheduler
"""

PBS_PACKAGE_TEMPLATE = r"""{pbs_resources}

source {env}
package --track {track} --frame {frame} --input-dir {indir} --pkgdir {pkgdir} --product {product} --polarization {polarization}
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
    scattered_tasklist,
    env,
    workdir,
    outdir,
    start_date,
    end_date,
    pbs_resource,
    cpu_count,
    num_threads,
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
            vector_file_list=basename(out_fname),
            start_date=start_date,
            end_date=end_date,
            workdir=job_dir,
            outdir=outdir,
            worker=int(cpu_count / num_threads),
            num_threads=num_threads,
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
    "--ncpus",
    type=click.INT,
    help="The total number of cpus per job" "required if known",
    default=48,
)
@click.option(
    "--memory",
    type=click.INT,
    help="Total memory required if per node",
    default=48 * 4,
)
@click.option(
    "--queue", type=click.STRING, help="Queue to submit the job into", default="normal",
)
@click.option("--hours", type=click.INT, help="Job walltime in hours.", default=24)
@click.option(
    "--email",
    type=click.STRING,
    help="Notification email address.",
    default="your.name@something.com",
)
@click.option(
    "--nodes", type=click.INT, help="Number of nodes to be requested", default=1,
)
@click.option("--jobfs", type=click.INT, help="Jobfs required per node", default=400)
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
def ard_insar(
    taskfile: click.Path,
    start_date: click.DateTime,
    end_date: click.DateTime,
    workdir: click.Path,
    outdir: click.Path,
    ncpus: click.INT,
    memory: click.INT,
    queue: click.INT,
    hours: click.INT,
    email: click.STRING,
    nodes: click.INT,
    jobfs: click.INT,
    storage: click.STRING,
    project: click.STRING,
    env: click.Path,
    test: click.BOOL,
):
    """
    consolidates batch processing job script creation and submission of pbs jobs
    """
    start_date = start_date.date()
    end_date = end_date.date()

    num_threads = 2
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
        email=email,
    )

    pbs_scripts = _gen_pbs(
        scattered_tasklist,
        env,
        workdir,
        outdir,
        start_date,
        end_date,
        pbs_resources,
        ncpus,
        num_threads,
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
@click.option("--hours", type=click.INT, help="Job walltime in hours.", default=24)
@click.option("--jobfs", help="jobfs required per node", default=50)
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
    type=click.Tuple([str, str]),
    default=("VV", "VH"),
    help="Polarizations used in metadata consolidations for product.",
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
    hours: click.INT,
    jobfs: click.INT,
    storage: click.STRING,
    project: click.STRING,
    env: click.Path,
    product: click.STRING,
    polarization: click.Tuple,
    test: click.BOOL,
):
    storage_names = "".join([STORAGE.format(proj=p) for p in storage])
    polarization = " ".join([p for p in polarization])
    pbs_resource = PBS_RESOURCES.format(
        project_name=project,
        queue=queue,
        walltime_hours=hours,
        mem_gb=memory,
        cpu_count=ncpus,
        jobfs_gb=jobfs,
        storages=storage_names,
    )

    with open(input_list, "r") as src:
        tasklist = [fp.rstrip() for fp in src.readlines()]

    pbs_scripts = []
    for task in tasklist:
        track, frame = Path(task).name.split("_")

        jobid = uuid.uuid4().hex[0:6]
        job_dir = Path(workdir).joinpath(f"{track}_{frame}-{jobid}")

        if not exists(job_dir):
            os.makedirs(job_dir)

        pbs = PBS_PACKAGE_TEMPLATE.format(
            pbs_resources=pbs_resource,
            env=env,
            track=track,
            frame=frame,
            indir=task,
            pkgdir=pkgdir,
            product=product,
            polarization=polarization,
        )

        out_fname = job_dir.joinpath(f"{track}{frame}{jobid}.bash")
        with open(out_fname, "w") as src:
            src.writelines(pbs)

        pbs_scripts.append(out_fname)
    _submit_pbs(pbs_scripts, test)
