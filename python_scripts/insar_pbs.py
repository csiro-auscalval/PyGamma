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

"""
This pbs submission script divides and submits the total number of jobs 
into 'n' equally divided batches (set by 'num_batch' param.). For each batch, 
a pbs job is submitted, which controls the chainning of additional jobs from 
that batch, if a previous job is completed, if error occurs for that particular 
job, or retry count per job exceeds (which is defined by user from parameter 'retry'). 

Recommendation for INSAR end-to-end processing is to set the 'retry' to maximum of 2
with default walltime of 48hrs, and number of batch 'num_batch' to 4. For a single 
stack end-to-end run usually takes from 4-6 hrs for 50-90 scenes stack in NCI infrastructure. 
The source code, which executes GAMMA program is designed to spawn maximum of 50 NCI jobs 
depending on the tasks. Thus, to not exceed the maximum queue limit of 300 per project in  NCI, 
the 'num_batch' with maximum of 4 would spawn 200 jobs (+/- 20 jobs). 

taskfile <contains the all the 'download.list' file's path to be processed> 
    content example: /path/to/a/download/file/s1_des_download_half1.list
                     /path/to/a/download/file/s1_des_download_half2.list
                     .
                     .
                     /path/to/a/download/file/s1_des_download_half10.list
                    
usage:{
    python insar_pbs.py 
    --taskfile <path to download file list>
    --env <path to .env file to NCI> 
    --total_ncpus <number of cpus> 
    --queue <express or normal>
    --hours <walltime in hours> 
    --total_memory <total memory requied in GB> 
    --workdir <path to a working directory where nci outputs/luigi logs are generated>
    --outdir <path where processed data is to be stored> 
    --project <nci project>
    --track <track>
    --frame <frame>
    --num_batch <number batches>
    --test (if you want to mock the pbs submission)
    }
"""
PBS_SINGLE_JOB_TEMPLATE = ("""#!/bin/bash
#PBS -P {project}
#PBS -q {queue}
#PBS -l other=gdata1
#PBS -l walltime={hours}:00:00
#PBS -l mem={memory}GB
#PBS -l ncpus={ncpus}
#PBS -l jobfs=5GB
#PBS -W umask=017
#PBS -l wd
#PBS -l software=python

module load mpi4py/3.0.0-py3
module load openmpi/2.1.1

source /g/data/u46/users/pd1813/INSAR/test_bulk_pbs/insar.env

n=1
export OMP_NUM_THREADS=$n
export NUM_PROCS=$(($PBS_NCPUS / $n))

mpirun -np $(($PBS_NCPUS / $n)) -x $((OMP_NUM_THREADS)) -map-by ppr:$(($PBS_NCPUS / 2)):socket:PE=$(($OMP_NUM_THREADS)) --report-bindings --oversubscribe python3 /g/data/u46/users/pd1813/INSAR/INSAR_DEV_BULK_PROCESS/gamma_insar/python_scripts/raw_data_extract.py {proc_file}
""")

PBS_RESOURCES = ("""#!/bin/bash
#PBS -P {project}
#PBS -q {queue}
#PBS -l other=gdata1
#PBS -l walltime={hours}:00:00
#PBS -l mem={memory}GB
#PBS -l ncpus={ncpus}
#PBS -l jobfs=5GB
#PBS -W umask=017
#PBS -l wd
#PBS -v NJOBS,NJOB,JOB_IDX
#PBS -l software=python
""")

PBS_TEMPLATE = (r"""{pbs_resources}

# NJOBS is the total number of retry per job in a sequence of jobs (defaults to 1)

source {env}

export OMP_NUM_THREADS={omp_num_threads}
s1_download_list={s1_download_list}

# set the default NJOBS to 1 if it is not set
if [ X$NJOBS == X ]; then
    export NJOBS=1
fi

# set the default NJOB to 0 if it is not set
if [ X$NJOB == X ]; then 
    export NJOB=0
fi

# set the default JOB_IDX if it is not set 
if [ X$JOB_IDX == X ]; then 
    export JOB_IDX=0
fi
    
export njobs=$NJOBS

# read the content of files into an ARRAY
IFS=$'\n' read -d '' -r -a JOB_ARRAY < $s1_download_list

job_num=$((${{#JOB_ARRAY[@]}}))

# termination of batch job if all jobs are completed
if [ $JOB_IDX -ge $job_num ]; then 
    echo "all jobs are completed for this batch" 
    exit 0
fi 

download_file=${{JOB_ARRAY[JOB_IDX]}}
echo "processing download file $download_file" 

final_status_log="$(basename -- $download_file)"".out"

# Quick termination of job sequence if final output file is found
# in the working directory 
if [ -f $final_status_log ]; then
    echo "$final_status_log exists: terminating the $final_status_log job"
    export NJOBS=$njobs
    export NJOB=0
    export JOB_IDX=$((JOB_IDX+1))
fi

# Increment the counter to get current job number 
NJOB=$(($NJOB+1))
echo "processiing job $NJOB of $NJOBS jobs"

# check if job sequence is complete, if complete reset the variables for next jobs
if [ $NJOB -ge $NJOBS ]; then
    export NJOBS=$njobs
    export NJOB=0
    export JOB_IDX=$((JOB_IDX+1))
fi 

qsub -z -W depend=afterany:$PBS_JOBID $PBS_JOBNAME

# check the checkpoint files before commencing the next job if NJOB is greater than 1 
# Run the job
if [ $NJOB -gt 1 ]; then 
    luigi {options} --s1-file-list $download_file --track {track} --frame {frame} --workers 4 --restart-process True --workdir {workdir} --outdir {outdir} --local-scheduler

else
    luigi {options} --s1-file-list $download_file --track {track} --frame {frame} --workers 4 --workdir {workdir} --outdir {outdir} --local-scheduler
    
fi 

errstat=$?
if [ $errstat -ne 0 ]; then 
    sleep 5 
    touch $final_status_log
    export NJOBS=$njobs
    export NJOB=0
    exit $errstat
fi

    
""")

FMT1 = 'job{jobid}.bash'
FMT2 = 'level1-{jobid}.txt'
RESTART_ARD_FMT = "--module process_gamma ARD --proc-file {proc_file} --checkpoint-patterns {checkpoint_patterns}"
ARD_FMT = "--module process_gamma ARD"


def scatter(iterable, n):
    """
    Evenly scatters an interable by `n` blocks.
    """

    q, r = len(iterable) // n, len(iterable) % n
    res = (iterable[i * q + min(i, r):(i + 1) * q + min(i + 1, r)]
           for i in range(n))

    return list(res)


def _gen_pbs(scattered_tasklist, options, env, omp_num_threads, track, frame, workdir, outdir,
             pbs_resource):
    """
    Generates a pbs scripts
    """
    pbs_scripts = []

    for block in scattered_tasklist:

        jobid = uuid.uuid4().hex[0:6]

        job_dir = pjoin(workdir, 'jobid-{}'.format(jobid))
        print(job_dir)
        if not exists(job_dir):
            os.makedirs(job_dir)

        out_fname = pjoin(job_dir, FMT2.format(jobid=jobid))
        with open(out_fname, 'w') as src:
            src.writelines(block)

        pbs = PBS_TEMPLATE.format(pbs_resources=pbs_resource, options=options, omp_num_threads=omp_num_threads,
                                  env=env, s1_download_list=basename(out_fname), outdir=outdir, workdir=job_dir,
                                  track=track, frame=frame)

        out_fname = pjoin(job_dir, FMT1.format(jobid=jobid))
        with open(out_fname, 'w') as src:
            src.writelines(pbs)

        pbs_scripts.append(out_fname)

    return pbs_scripts


def _submit_pbs(pbs_scripts, retry, test):
    """
    Submits a pbs job or mocks if set to test
    """
    for scripts in pbs_scripts:
        print(scripts)
        if test:
            time.sleep(1)
            print("qsub -v NJOBS={retry} {job}".format(retry=retry, job=basename(scripts)))
        else:
            time.sleep(1)
            os.chdir(dirname(scripts))
            subprocess.call(['qsub', '-v', 'NJOBS={retry}'.format(retry=retry), basename(scripts)])


def run(taskfile, proc_file, track, frame, checkpoint_patterns, workdir, outdir, env, total_ncpus, total_memory,
        omp_num_threads, project, queue, hours, email, retry, num_batch, test):
    """
    colsolidates batch processing job script creation and submission of pbs jobs
    """
    with open(taskfile, 'r') as src:
        tasklist = src.readlines()

    num_batch = num_batch

    scattered_tasklist = scatter(tasklist, num_batch)

    pbs_resources = PBS_RESOURCES.format(project=project, queue=queue, hours=hours, memory=total_memory,
                                         ncpus=total_ncpus, email=email)
    if proc_file:
        options = RESTART_ARD_FMT.format(proc_file=proc_file, checkpoint_patterns=checkpoint_patterns)
    else:
        options = ARD_FMT

    pbs_scripts = _gen_pbs(scattered_tasklist, options, env, omp_num_threads, track, frame,
                           workdir, outdir, pbs_resources)
    _submit_pbs(pbs_scripts, retry, test)


def _parser():
    """ Argument parser. """
    description = ("Equally partition a jobs into batches and submit each batch"
                   "into the PBS queue.")

    formatter = argparse.ArgumentDefaultsHelpFormatter
    parser = argparse.ArgumentParser(description=description,
                                     formatter_class=formatter)

    parser.add_argument("--taskfile", help="The file containing the list of "
                                           "tasks to be performed",
                        required=True)

    parser.add_argument('--proc_file', help="The proc file containing the insar "
                                            "processing details",
                        required=False)
    parser.add_argument('--track', help="The track number of Sentinel-1", required=True)

    parser.add_argument('--frame', help="The frame number of Sentinel-1", required=True)

    parser.add_argument("--checkpoint_patterns", help="The wildcard patterns used "
                                                      "in cleanup of check point files",
                        required=False, default=None)

    parser.add_argument("--workdir", help="The base working and scripts output directory.",
                        required=True)

    parser.add_argument("--outdir", help="The output directory for processed data",
                        required=True)

    parser.add_argument("--env", help="Environment script to source.",
                        required=True)

    parser.add_argument("--total_ncpus", type=int, help="The total number of cpus per job"
                                                        "required if known",
                        default=1, required=False)

    parser.add_argument("--total_memory", type=int, help="Total memory required if known",
                        default=8, required=False)

    parser.add_argument("--omp_num_threads", type=int,
                        help="The number of threads for each job",
                        default=4, required=False)

    parser.add_argument("--project", help="Project code to run under.",
                        required=True)

    parser.add_argument("--queue", help="Queue to submit the job into",
                        default="normal", required=False)

    parser.add_argument("--hours", help="Job walltime in hours.",
                        default=48, required=False)

    parser.add_argument("--email", help="Notification email address.",
                        default="your.name@something.com")

    parser.add_argument("--retry", type=int, help="How many retry to be performed before per job"
                                                  "terminating the job",
                        default=2, required=False)

    parser.add_argument("--num_batch", type=int, help="Number of batch jobs to be generated",
                        default=3, required=False)

    parser.add_argument("--test", action='store_true', help="mock the job submission to PBS queue")

    return parser


def main():
    """ Main execution. """
    parser = _parser()
    args = parser.parse_args()
    run(args.taskfile, args.proc_file, args.track, args.frame, args.checkpoint_patterns, args.workdir, args.outdir,
        args.env, args.total_ncpus, args.total_memory, args.omp_num_threads,
        args.project, args.queue, args.hours, args.email, args.retry, args.num_batch, args.test)


if __name__ == '__main__':
    main()
