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
mpirun python3 /g/data/u46/users/pd1813/INSAR/INSAR_DEV_BULK_PROCESS/gamma_insar/python_scripts/raw_data_extract.py {proc_file}
""")


COREGISTRATION_JOB_TEMPLATE = ("""#!/bin/bash
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
#PBS -e {error_file}

export OMP_NUM_THREADS=4

#/home/547/pd1813/repo/gamma_insar/coregister_S1_slave_SLC.bash /g/data/dz56/INSAR_ARD/VV/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T45D_F19.proc {slave} {master}
sleep 1m

>&2 echo "this dummy job {master} {slave}"
>&2 echo "Segmentation fault in this dummy job {master} {slave}"
""")
