#!/usr/bin/python3 
import luigi
import os
import logging
from structlog import wrap_logger
from structlog.processors import JSONRenderer
from os.path import join as pjoin, basename, dirname, exists, splitext
import subprocess
import datetime
import signal

import traceback

from python_scripts.initialize_proc_file import get_path
from python_scripts.check_status import checkrawdata, checkgammadem, checkfullslc, checkmultilook, \
     checkbaseline, checkdemmaster, checkcoregslaves, checkifgs
from python_scripts.proc_template import PROC_FILE_TEMPLATE
from python_scripts.clean_up import clean_rawdatadir, clean_slcdir, clean_ifgdir, clean_gammademdir, \
     clean_demdir, clean_checkpoints


ERROR_LOGGER = wrap_logger(logging.getLogger('errors'),
                           processors=[JSONRenderer(indent=1, sort_keys=True)])
STATUS_LOGGER = wrap_logger(logging.getLogger('status'),
                            processors=[JSONRenderer(indent=1, sort_keys=True)])


@luigi.Task.event_handler(luigi.Event.FAILURE)
def on_failure(task, exception):
    """Capture any Task Failure here."""
    ERROR_LOGGER.error(task=task.get_task_family(),
                       params=task.to_str_params(),
                       level1=getattr(task, 'level1', ''),
                       exception=exception.__str__(),
                       traceback=traceback.format_exc().splitlines())

    pid = int(os.getpid())
    os.kill(pid, signal.SIGTERM)


class ExternalFileChecker(luigi.ExternalTask):
    """ checks the external dependencies """
    filename = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(self.filename)


class InitialSetup(luigi.Task):
    """
    Runs the initial setup of insar processing workflow by
    creating required directories and file lists
    """
    proc_file_path = luigi.Parameter()
    s1_file_list = luigi.Parameter()

    def output(self):

        path_name = get_path(self.proc_file_path)
        return luigi.LocalTarget(pjoin(path_name['checkpoint_dir'], 'InitialSetup_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('initial setup task')
        args = (["bash", "initial_setup_job.bash",
                 "%s" % self.proc_file_path, "%s" % self.s1_file_list])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class RawDataExtract(luigi.Task):
    """
    Runs the Raw data extract task
    """
    proc_file_path = luigi.Parameter()
    s1_file_list = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['initialsetup'].path), 'RawDataExtract_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('raw data extract task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "extract_raw_data_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])

        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckRawData(luigi.Task):
    """
    Runs the checking task on the raw data extract task
    """

    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['rawdataextract'].path), 'Check_RawDataExtract_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check raw data task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'raw_data_path': path_name['raw_data_dir'],
                  's1_dir_path': path_name['s1_dir'],
                  'download_list_path': path_name['download_list']}
        complete_status = checkrawdata(**kwargs)

        if complete_status:
            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))
        else:
            raise ValueError('failed to download raw data')


class CreateGammaDem(luigi.Task):
    """
    Runs create gamma dem task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['check_rawdata'].path), 'CreateGammaDem_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('create gamma dem task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "create_dem_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckGammaDem(luigi.Task):
    """
    Runs the checking task on the create gamma dem task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['creategammadem'].path), 'Check_GammaDem_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check gamma dem task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'track_frame': path_name['track_frame'],
                  'gamma_dem_path': path_name['gamma_dem']}

        complete_status = checkgammadem(**kwargs)

        if complete_status:
            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CreateFullSlc(luigi.Task):
    """
    Runs the create full slc tasks
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['check_rawdata'].path), 'CreateFullSlc_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('create full slc task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "create_full_slc_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckFullSlc(luigi.Task):
    """
    Runs the checking task on the create full slc task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['createfullslc'].path), 'Check_createfullslc_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check full slc task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'slc_path': path_name['slc_dir']}

        complete_status = checkfullslc(**kwargs)

        if complete_status:

            if path_name['clean_up'] == 'yes':
                clean_rawdatadir(raw_data_path=path_name['raw_data_dir'])

            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CreateMultilook(luigi.Task):
    """
    Runs creation of multi-look image task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['check_fullslc'].path), 'CreateMultilook_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('create multi-look task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "create_multilook_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckMultilook(luigi.Task):
    """
    Runs the checking task on the multilook task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['multilook'].path), 'Check_multilook_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check multi-look task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'slc_path': path_name['slc_dir']}

        complete_status = checkmultilook(**kwargs)

        if complete_status:

            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CalcInitialBaseline(luigi.Task):
    """
    Runs calculation of initial baseline task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['check_multilook'].path), 'CalcInitialBaseline_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('calculate baseline task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "calc_init_baseline_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckBaseline(luigi.Task):
    """
    Runs the checking task on the calc baseline task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['calcbaseline'].path), 'Check_baseline_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check baseline task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'ifgs_list_path': path_name['ifgs_list']}

        complete_status = checkbaseline(**kwargs)

        if complete_status:
            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CalcResizeScene(luigi.Task):
    """
    Calculates resize scenes
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['calcbaseline'].path), 'Calc_resize_scene_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('calculate resize scene task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "calc_resize_sentinel_scene_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class ResizeSLC(luigi.Task):
    """
    Runs resizing of sentinel 1 SLC
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['calc_resize_scene'].path), 'Slc_resize_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('resize sentinel1 task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "resize_slc_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckResize(luigi.Task):
    """
    Runs the checking task on the resize sentinel task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['resizesentinel'].path), 'Check_resize_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check resize sentinel1 task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'slc_path': path_name['slc_dir']}

        complete_status = checkresize(**kwargs)

        if complete_status:
            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class SubsetByBursts(luigi.Task):
    """
    Runs sub-setting by bursts on sentinel1
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['resize_s1_slc'].path), 'subset_brusts_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('subset by brusts sentinel1 task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "subset_by_brusts_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckSubsetByBursts(luigi.Task):
    """
    Runs the checking task on the subset by brusts task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['subsetbybursts'].path), 'Check_subset_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check resize sentinel1 task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'slc_path': path_name['slc_dir']}

        complete_status = checksubset(**kwargs)

        if complete_status:
            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CoregisterDemMaster(luigi.Task):
    """
    Runs co-registration of DEM and master scene
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['calcbaseline'].path),
                                       'Coregister_dem_Master_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('co-register master-dem task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "coregister_dem_to_master_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckDemMaster(luigi.Task):
    """
    Runs the checking task on the dem-master scene co-registration task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['coregmaster'].path), 'Check_DemMaster_status_logs.out'))

    def run(self):

        STATUS_LOGGER.info('check master-dem co-registration task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'slc_path': path_name['slc_dir'],
                  'master_scene': path_name['master_scene'],
                  'dem_path': path_name['dem_dir']}

        complete_status = checkdemmaster(**kwargs)

        if complete_status:
            if path_name['clean_up'] == 'yes':
                clean_gammademdir(gamma_dem_path=path_name['gamma_dem'], track=path_name['track'])

            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CoregisterSlaves(luigi.Task):
    """
    Runs the master-slaves co-registration task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['check_coregmaster'].path), 'Coregister_slaves_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('co-register master-slaves task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "coregister_slave_to_master_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckCoregSlave(luigi.Task):
    """
    Runs the checking task on the master-slaves scene co-registration task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['coregslaves'].path), 'Check_coreg_slaves_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check co-register master-slaves task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'slc_path': path_name['slc_dir'],
                  'master_scene': path_name['master_scene']}

        complete_status = checkcoregslaves(**kwargs)

        if complete_status:
            if path_name['clean_up'] == 'yes':
                clean_slcdir(slc_path=kwargs['slc_path'])

            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class ProcessInterFerograms(luigi.Task):
    """
    Runs processing of inter-ferograms task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['check_coregslaves'].path), 'Process_IFGs_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('processing inter-ferograms task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        args = (["bash", "process_interferograms_job.bash",
                 "%s" % pjoin(path_name['proj_dir'], basename(self.proc_file_path))])
        subprocess.check_call(args)

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CheckInterFerograms(luigi.Task):
    """
    Runs the checking task on the process interferograms task
    """
    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['processifgs'].path), 'Check_interferograms_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check inter-ferogram task')
        path_name = get_path(self.proc_file_path)
        path_name = get_path(pjoin(path_name['proj_dir'], basename(self.proc_file_path)))

        kwargs = {'ifg_path': path_name['ifg_dir']}

        complete_status = checkifgs(**kwargs)

        if complete_status:
            if path_name['clean_up'] == 'yes':
                clean_ifgdir(ifg_path=kwargs['ifg_path'])
                clean_demdir(dem_path=path_name['dem_dir'])

            with self.output().open('w') as f:
                f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class CompletionCheck(luigi.Task):
    """
    Runs checking of task completion for full workflow
    for a single stack
    """
    upstream_task = luigi.Parameter()

    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(pjoin(dirname(inputs['check_processifgs'].path), 'Process_Complete_status_logs.out'))

    def run(self):
        STATUS_LOGGER.info('check full stack job completion')
        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class Workflow(luigi.Task):
    """
    A workflow that orchestrates insar procesing pipelines
    for a single stack
    """
    proc_file_path = luigi.Parameter()
    s1_file_list = luigi.Parameter()

    def requires(self):

        path_name = get_path(self.proc_file_path)

        # external file checker tasks
        scenes_list = ExternalFileChecker(path_name['scenes_list'])
        extract_raw_errors = ExternalFileChecker(path_name['extract_raw_errors'])
        slc_creation_errors = ExternalFileChecker(path_name['slc_creation_errors'])
        multi_look_slc_errors = ExternalFileChecker(path_name['multi-look_slc_errors'])
        init_baseline_errors = ExternalFileChecker(path_name['init_baseline_errors'])
        create_dem_errors = ExternalFileChecker(path_name['create_dem_errors'])
        coreg_dem_errors = ExternalFileChecker(path_name['coreg_dem_errors'])
        coreg_slc_errors = ExternalFileChecker(path_name['coreg_slc_errors'])
        ifg_errors = ExternalFileChecker(path_name['ifg_errors'])

        # upstream tasks

        initialsetup = InitialSetup(proc_file_path=self.proc_file_path, s1_file_list=self.s1_file_list)

        rawdataextract = RawDataExtract(proc_file_path=self.proc_file_path,
                                        s1_file_list=self.s1_file_list,
                                        upstream_task={'initialsetup': initialsetup,
                                                       'scene_list': scenes_list})

        check_rawdata = CheckRawData(proc_file_path=self.proc_file_path,
                                     upstream_task={'rawdataextract': rawdataextract,
                                                    'extract_raw_error': extract_raw_errors})

        createfullslc = CreateFullSlc(proc_file_path=self.proc_file_path,
                                      upstream_task={'check_rawdata': check_rawdata})

        check_fullslc = CheckFullSlc(proc_file_path=self.proc_file_path,
                                     upstream_task={'createfullslc': createfullslc,
                                                    'slc_creation_errors': slc_creation_errors})

        creategammadem = CreateGammaDem(proc_file_path=self.proc_file_path,
                                        upstream_task={'check_rawdata': check_rawdata})

        check_creategammadem = CheckGammaDem(proc_file_path=self.proc_file_path,
                                             upstream_task={'creategammadem': creategammadem,
                                                            'create_dem_errors': create_dem_errors})

        multilook = CreateMultilook(proc_file_path=self.proc_file_path,
                                    upstream_task={'check_fullslc': check_fullslc})

        check_multilook = CheckMultilook(proc_file_path=self.proc_file_path,
                                         upstream_task={'multilook': multilook,
                                                        'multi-look_slc_errors': multi_look_slc_errors})

        calcbaseline = CalcInitialBaseline(proc_file_path=self.proc_file_path,
                                           upstream_task={'check_multilook': check_multilook})

        coregmaster = CoregisterDemMaster(proc_file_path=self.proc_file_path,
                                          upstream_task={'calcbaseline': calcbaseline,
                                                         'init_baseline_errors': init_baseline_errors,
                                                         'check_creategammadem': check_creategammadem})

        check_coregmaster = CheckDemMaster(proc_file_path=self.proc_file_path,
                                           upstream_task={'coregmaster': coregmaster,
                                                          'coreg_dem_error': coreg_dem_errors})

        coregslaves = CoregisterSlaves(proc_file_path=self.proc_file_path,
                                       upstream_task={'check_coregmaster': check_coregmaster})

        check_coregslaves = CheckCoregSlave(proc_file_path=self.proc_file_path,
                                            upstream_task={'coregslaves': coregslaves,
                                                           'coreg_slc_errors': coreg_slc_errors})

        processifgs = ProcessInterFerograms(proc_file_path=self.proc_file_path,
                                            upstream_task={'check_coregslaves': check_coregslaves})

        check_processifgs = CheckInterFerograms(proc_file_path=self.proc_file_path,
                                                upstream_task={'processifgs': processifgs,
                                                               'ifg_errors': ifg_errors})

        completioncheck = CompletionCheck(upstream_task={'check_processifgs': check_processifgs})

        yield completioncheck

    def output(self):
        path_name = get_path(self.proc_file_path)
        return luigi.LocalTarget(pjoin(path_name['checkpoint_dir'], 'final_status_logs.out'))

    def run(self):

        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


class ARD(luigi.Task):
    """
    Runs the insar ARD pipeline for a single stack (min. of 5 scenes are
    required (due to the 'issues' in a baseline calculation method in source code).
    A 'download_list' contains a list of scenes for a given stack. if a 'proc_file'
    is supplied as a luigi input parameter then the supplied 'proc_file' will be used,
    if not, a 'proc_file' will be automatically generated using luigi parameter
    supplied in run time, or configured in the 'luigi.cfg' file under ARD profile.

    Luigi parameter 'restart_process' is present to facilitate the
    restart/continuation of luigi-workflow either manually (if there is a need).

    To manually implement the restart_process function, you will have to set a
    'checkpoint patterns' (eq wildcard, '*') to delete all checkpoint files in a
    luigi parameter to match files to be deleted from checkpoint directory,
    so that the luigi workflow can start from last successfully completed task.

    The automatic restart are triggered if luigi scheduler exceeds the wall time
    or errors occurs with the source code. In the later case, luigi-workflow will
    resume, but same recurring errors will continue until retry for that jobs runs
    out, then next job in the batch will be initiated. For jobs exceeding the wall
    time the clean up of checkpoint files are done first, then luigi workflow process
    is re-initiated from last  available successful checkpoint (which is inferred
    from the available checkpoint files available in 'checkpoint' directory'.
    Default, clean up of 'checkpoint' files is set to clean only the
    latest checkpoint file, which is assumed to have caused the failure.

    -----------------------------------------------------------------------------
    minimum parameter required to run using default luigi Parameter set in luigi.cfg
    ------------------------------------------------------------------------------
    usage:{
        luigi --module process_gamma ARD
        --s1-file-list <path to a s1 file list>
        --restart-process <True if resuming from previously completed state>
        --track <S1 track number A/D>
        --frame <frame number>
        --workdir <working directory, nci outputs and luigi logs will be stored>
        --outdir <output directory where processed data will be stored>
        --local-scheduler (use only local-scheduler)
        --workers <number of workers>
    }

    """
    s1_file_list = luigi.Parameter(significant=False)
    project = luigi.Parameter(significant=False)
    track = luigi.Parameter(significant=False)
    frame = luigi.Parameter(significant=False)
    polarization = luigi.Parameter(default='VV', significant=False)
    multilook = luigi.IntParameter(default=1, significant=False)
    extract_raw_data = luigi.Parameter(default='yes', significant=False)
    do_slc = luigi.Parameter(default='yes', significant=False)
    coregister_dem = luigi.Parameter(default='yes', significant=False)
    coregister_slaves = luigi.Parameter(default='yes', significant=False)
    process_ifgs = luigi.Parameter(default='yes', significant=False)
    process_geotiff = luigi.Parameter(default='yes', significant=False)
    clean_up = luigi.Parameter(default='no', significant=False)
    proc_file = luigi.Parameter(default='', significant=False)
    restart_process = luigi.Parameter(default=False, significant=False)
    checkpoint_patterns = luigi.Parameter(default=None, significant=False)
    outdir = luigi.Parameter(significant=False)
    workdir = luigi.Parameter(significant=False)

    def requires(self):

        if exists(self.s1_file_list):

            if not self.proc_file:
                kwargs = {'s1_file_list': basename(self.s1_file_list),
                          'outdir': pjoin(self.outdir, '{}_{}'.format(self.track, self.frame)),
                          'project': self.project,
                          'track': self.track,
                          'frame': self.frame,
                          'polarization': self.polarization,
                          'multilook': self.multilook,
                          'extract_raw_data': self.extract_raw_data,
                          'do_slc': self.do_slc,
                          'coregister_dem': self.coregister_dem,
                          'coregister_slaves': self.coregister_slaves,
                          'process_ifgs': self.process_ifgs,
                          'process_geotiff': self.process_geotiff,
                          'clean_up': self.clean_up}

                proc_data = PROC_FILE_TEMPLATE.format(**kwargs)
                proc_file1 = pjoin(self.workdir, '{}_{}.proc'.format(self.track, self.frame))

                with open(proc_file1, 'w') as src:
                    src.writelines(proc_data)

            else:
                proc_file1 = self.proc_file

            if self.restart_process:

                path_name = get_path(proc_file1)
                proc_file1 = pjoin(path_name['proj_dir'], '{}_{}.proc'.format(self.track, self.frame))
                path_name = get_path(proc_file1)

                if not exists(pjoin(path_name['checkpoint_dir'], 'final_status_logs.out')):
                    clean_checkpoints(checkpoint_path=path_name['checkpoint_dir'], patterns=self.checkpoint_patterns)

                yield Workflow(proc_file_path=proc_file1, s1_file_list=self.s1_file_list)
            else:
                yield Workflow(proc_file_path=proc_file1, s1_file_list=self.s1_file_list)

    def output(self):
        out_name = pjoin(self.workdir, '{f}.out'.format(f=basename(self.s1_file_list)))
        return luigi.LocalTarget(out_name)

    def run(self):
        with self.output().open('w') as f:
            f.write('{dt}'.format(dt=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')))


if __name__ == '__name__':
    luigi.run()
