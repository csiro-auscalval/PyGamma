#!/usr/bin/python3

"""
PBS submission scripts.
"""

from __future__ import print_function

import os
from os.path import join as pjoin, dirname, exists, basename
import subprocess
import uuid
import argparse
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

gamma_insar ARD --vector-file-list {vector_file_list} --start-date {start_date} --end-date {end_date} --workdir {workdir} --outdir {outdir} --workers {cpu_count} --local-scheduler
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
            cpu_count=cpu_count
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
            print(
                "qsub {job}".format(job=basename(scripts))
            )
        else:
            time.sleep(1)
            os.chdir(dirname(scripts))
            subprocess.call(
                ["qsub", basename(scripts)]
            )


def run(
    taskfile,
    start_date,
    end_date,
    workdir,
    outdir,
    ncpus,
    memory,
    queue,
    hours,
    email,
    nodes,
    jobfs,
    storage,
    project,
    env,
    test,
):
    """
    consolidates batch processing job script creation and submission of pbs jobs
    """
    with open(taskfile, "r") as src:
        tasklist = src.readlines()
    

    scattered_tasklist = scatter(tasklist, nodes)
    storage_names = ''.join([STORAGE.format(proj=p) for p in storage]) 
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
        ncpus
    )
    _submit_pbs(pbs_scripts, test)


def _parser():
    """ Argument parser. """
    description = (
        "Equally partition a jobs into batches and submit each batch"
        "into the PBS queue."
    )

    formatter = argparse.ArgumentDefaultsHelpFormatter
    parser = argparse.ArgumentParser(description=description, formatter_class=formatter)

    parser.add_argument(
        "--taskfile",
        help="The file containing the list of " "tasks to be performed",
        required=True,
    )
    parser.add_argument(
        "--start-date",
        help="The start date of SLC acquisition",
        required=True,
    )
    parser.add_argument(
        "--end-date",
        help="The end date of SLC acquisition",
        required=True
    )
    parser.add_argument(
        "--workdir",
        help="The base working and scripts output directory.",
        required=True,
    )

    parser.add_argument(
        "--outdir", help="The output directory for processed data", required=True
    )

    parser.add_argument(
        "--ncpus",
        type=int,
        help="The total number of cpus per job" "required if known",
        default=48,
        required=False,
    )

    parser.add_argument(
        "--memory",
        type=int,
        help="Total memory required if per node",
        default=48*4,
        required=False,
    )


    parser.add_argument(
        "--queue",
        help="Queue to submit the job into",
        default="normal",
        required=False,
    )

    parser.add_argument(
        "--hours", help="Job walltime in hours.", default=24, required=False
    )

    parser.add_argument(
        "--email", help="Notification email address.", default="your.name@something.com"
    )

    parser.add_argument(
        "--nodes",
        type=int,
        help="Number of nodes to be requested",
        default=1,
        required=False,
    )

    parser.add_argument(
        "--jobfs",
        help="Jobfs required per node",
        default=400,
        required=False
    )
    
    parser.add_argument(
        "--storage",
        nargs='*',
        help="Project storage you wish to use in PBS jobs",
        required=True,
    )
    
    parser.add_argument(
        "--project",
        help="Project to compute under",
        required=True,
    )
    parser.add_argument(
        "--env",
        help="Environment script to source.",
        required=True,
    )
    parser.add_argument(
        "--test", action="store_true", help="mock the job submission to PBS queue"
    )

    return parser


def main():
    """ Main execution. """
    parser = _parser()
    args = parser.parse_args()
    run(
        args.taskfile,
        args.start_date,
        args.end_date,
        args.workdir,
        args.outdir,
        args.ncpus,
        args.memory,
        args.queue,
        args.hours,
        args.email,
        args.nodes,
        args.jobfs,
        args.storage,
        args.project,
        args.env,
        args.test,
    )


if __name__ == "__main__":
    main()
