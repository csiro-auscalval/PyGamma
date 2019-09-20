#!/usr/bin/python3

import os
from os.path import basename, dirname, exists, join as pjoin, splitext
import shutil
import subprocess
import datetime
import signal
import traceback
import re

import numpy
import luigi
import pandas as pd
from python_scripts import generate_slc_inputs
from python_scripts.s1_slc_metadata import S1DataDownload
import python_scripts.coreg_utils as coreg_utils
from python_scripts.initialize_proc_file import get_path, setup_folders
from python_scripts.check_status import (
    checkbaseline,
    checkcoregslaves,
    checkdemmaster,
    checkfullslc,
    checkgammadem,
    checkifgs,
    checkmultilook,
)
from python_scripts.template_pbs import (
    COREGISTRATION_JOB_TEMPLATE,
    PBS_SINGLE_JOB_TEMPLATE,
)
from python_scripts.proc_template import PROC_FILE_TEMPLATE
from python_scripts.clean_up import (
    clean_checkpoints,
    clean_coreg_scene,
    clean_demdir,
    clean_gammademdir,
    clean_ifgdir,
    clean_rawdatadir,
    clean_slcdir,
)
from python_scripts.constant import COREG_JOB_ERROR_FILE_FMT, COREG_JOB_FILE_FMT
from python_scripts.logs import ERROR_LOGGER, STATUS_LOGGER


@luigi.Task.event_handler(luigi.Event.FAILURE)
def on_failure(task, exception):
    """Capture any Task Failure here."""
    ERROR_LOGGER.error(
        task=task.get_task_family(),
        params=task.to_str_params(),
        level1=getattr(task, "level1", ""),
        exception=exception.__str__(),
        traceback=traceback.format_exc().splitlines(),
    )

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
    start_date = luigi.Parameter()
    end_date = luigi.Parameter()
    s1_file_list = luigi.Parameter()
    database_name = luigi.Parameter()
    orbit = luigi.Parameter()

    def output(self):
        path_name = get_path(self.proc_file_path)
        return luigi.LocalTarget(
            pjoin(path_name["checkpoint_dir"], "InitialSetup_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("initial setup task")
        setup_folders(self.proc_file_path)

        path_name = get_path(self.proc_file_path)

        # copy the 'proc file' to a proj directory where some of InSAR workflow are hard coded to look at
        shutil.copyfile(
            self.proc_file_path,
            pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
        )

        # get the relative orbit number, which is int value of the numeric part of the track name
        rel_orbit = int(re.findall(r"\d+", path_name["track"])[0])

        # get slc input information
        slc_input_results = generate_slc_inputs.query_slc_inputs(
            self.database_name,
            self.s1_file_list,
            self.start_date,
            self.end_date,
            self.orbit,
            rel_orbit,
            path_name["polarization"],
        )

        generate_slc_inputs.generate_lists(slc_input_results, path_name)

        with self.output().open("w") as f:
            f.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class SlcDataDownload(luigi.Task):
    """
    Runs single slc scene extraction task
    """

    slc_scene = luigi.Parameter()
    download_jobs_dir = luigi.Parameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()
    output_dir = luigi.Parameter()
    polarization = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            pjoin(
                self.download_jobs_dir, "{}_logs.out".format(basename(self.slc_scene))
            )
        )

    def run(self):
        download_obj = S1DataDownload(
            self.slc_scene, self.polarization, self.poeorb_path, self.resorb_path
        )
        download_obj.slc_download(self.output_dir)

        with self.output().open("w") as f:
            f.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class RawDataExtract(luigi.Task):
    """
    Runs the Raw data extract task
    """

    proc_file_path = luigi.Parameter()
    s1_file_list = luigi.Parameter()
    upstream_task = luigi.Parameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()

    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["initialsetup"].path), "RawDataExtract_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("raw data extract task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        download_tasks = []

        with open(path_name["download_list"], "r") as src:
            slc_scenes = src.readlines()
            for slc_scene in slc_scenes:
                scene_date = basename(slc_scene).split("_")[5].split("T")[0]
                download_tasks.append(
                    SlcDataDownload(
                        slc_scene=slc_scene.rstrip(),
                        polarization=path_name["polarization"],
                        download_jobs_dir=path_name["extract_raw_jobs_dir"],
                        poeorb_path=self.poeorb_path,
                        resorb_path=self.resorb_path,
                        output_dir=pjoin(path_name["raw_data_dir"], scene_date),
                    )
                )
        yield download_tasks

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["rawdataextract"].path), "CreateGammaDem_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("create gamma dem task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        args = [
            "bash",
            "create_dem_job.bash",
            "%s" % pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
        ]
        subprocess.check_call(args)

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["creategammadem"].path), "Check_GammaDem_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("check gamma dem task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        kwargs = {
            "track_frame": path_name["track_frame"],
            "gamma_dem_path": path_name["gamma_dem"],
        }

        complete_status = checkgammadem(**kwargs)

        if complete_status:
            with self.output().open("w") as out_fid:
                out_fid.write(
                    "{dt}".format(
                        dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    )
                )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["rawdataextract"].path), "CreateFullSlc_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("create full slc task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        args = [
            "bash",
            "create_full_slc_job.bash",
            "%s" % pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
        ]
        subprocess.check_call(args)

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["createfullslc"].path),
                "Check_createfullslc_status_logs.out",
            )
        )

    def run(self):
        STATUS_LOGGER.info("check full slc task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        kwargs = {"slc_path": path_name["slc_dir"]}

        complete_status = checkfullslc(**kwargs)
        if complete_status:
            if path_name["clean_up"] == "yes":
                clean_rawdatadir(raw_data_path=path_name["raw_data_dir"])
            with self.output().open("w") as out_fid:
                out_fid.write(
                    "{dt}".format(
                        dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    )
                )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["check_fullslc"].path), "CreateMultilook_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("create multi-look task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        args = [
            "bash",
            "create_multilook_job.bash",
            "%s" % pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
        ]

        subprocess.check_call(args)

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(dirname(inputs["multilook"].path), "Check_multilook_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("check multi-look task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        kwargs = {"slc_path": path_name["slc_dir"]}

        complete_status = checkmultilook(**kwargs)
        if complete_status:
            with self.output().open("w") as out_fid:
                out_fid.write(
                    "{dt}".format(
                        dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    )
                )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["check_multilook"].path),
                "CalcInitialBaseline_status_logs.out",
            )
        )

    def run(self):
        STATUS_LOGGER.info("calculate baseline task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        args = [
            "bash",
            "calc_init_baseline_job.bash",
            "%s" % pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
        ]
        subprocess.check_call(args)

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["calcbaseline"].path), "Check_baseline_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("check baseline task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        kwargs = {"ifgs_list_path": path_name["ifgs_list"]}

        complete_status = checkbaseline(**kwargs)

        if complete_status:
            with self.output().open("w") as out_fid:
                out_fid.write(
                    "{dt}".format(
                        dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    )
                )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["calcbaseline"].path),
                "Coregister_dem_Master_status_logs.out",
            )
        )

    def run(self):
        STATUS_LOGGER.info("co-register master-dem task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        args = [
            "bash",
            "coregister_dem_to_master_job.bash",
            "%s" % pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
        ]
        subprocess.check_call(args)

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["coregmaster"].path), "Check_DemMaster_status_logs.out"
            )
        )

    def run(self):

        STATUS_LOGGER.info("check master-dem co-registration task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        kwargs = {
            "slc_path": path_name["slc_dir"],
            "master_scene": path_name["master_scene"],
            "dem_path": path_name["dem_dir"],
        }

        complete_status = checkdemmaster(**kwargs)

        if complete_status:
            if path_name["clean_up"] == "yes":
                clean_gammademdir(
                    gamma_dem_path=path_name["gamma_dem"],
                    track_frame=path_name["track_frame"],
                )

            with self.output().open("w") as out_fid:
                out_fid.write(
                    "{dt}".format(
                        dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    )
                )


class ListParameter(luigi.Parameter):
    """
    Converts luigi parameters separated by comma to a list.
     """

    def parse(self, arguments):
        return arguments.split(",")


class SecondaryMastersDynamicCoregistration(luigi.Task):
    """
    Runs the  co-registration task to select secondary masters.
    """

    temporal_threshold = luigi.IntParameter()
    scenes = luigi.ListParameter(default=[])
    tag = luigi.Parameter()
    proc_file = luigi.Parameter()
    coreg_slc_jobs_dir = luigi.Parameter()
    polarization = luigi.Parameter()
    range_looks = luigi.Parameter()
    slc_path = luigi.Parameter()
    project = luigi.Parameter()
    ncpus = luigi.IntParameter()
    memory = luigi.IntParameter()
    queue = luigi.Parameter()
    hours = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            pjoin(
                self.coreg_slc_jobs_dir,
                "Dynamic_Master_Coregistration_{}_logs.out".format(self.tag),
            )
        )

    def run(self):
        scenes = self.scenes
        if not scenes or len(scenes) < 2:
            ERROR_LOGGER.error("There should be more than two scenes to co-register")

        # Initial master is first scene in list
        master_idx = 0
        max_slave_idx = None
        task_complete = False
        master_list = [scenes[master_idx]]

        while not task_complete:
            task_success = False
            slave_idx, task_complete = coreg_utils.coregristration_candidates(
                scenes, master_idx, self.temporal_threshold, max_slave_idx
            )

            if not slave_idx or task_complete:
                break

            master = scenes[master_idx]
            slave = scenes[slave_idx]

            coreg_job_file = pjoin(
                self.coreg_slc_jobs_dir,
                COREG_JOB_FILE_FMT.format(master=master, slave=slave),
            )
            coreg_error_log = pjoin(
                self.coreg_slc_jobs_dir,
                COREG_JOB_ERROR_FILE_FMT.format(master=master, slave=slave),
            )
            # if primary master (scenes[0]) is selected as master to be coregistered with then
            # master is just '-' to conform with requirements in coregister_S1_slave_SLC.bash requirements
            if master == scenes[0]:
                master = "-"

            with open(coreg_job_file, "w") as fid:
                kwargs = {
                    "master": master,
                    "slave": slave,
                    "proc_file": self.proc_file,
                    "error_file": coreg_error_log,
                    "project": self.project,
                    "ncpus": self.ncpus,
                    "memory": self.memory,
                    "hours": self.hours,
                    "queue": self.queue,
                }

                pbs = COREGISTRATION_JOB_TEMPLATE.format(**kwargs)
                fid.writelines(pbs)

            task1 = ExternalFileChecker(coreg_error_log)

            if not task1.complete():
                # clean slave SLC directory before co-registration
                clean_coreg_scene(
                    self.slc_path, slave, self.polarization, self.range_looks
                )
                cmd = ["qsub", "{}".format(coreg_job_file)]
                os.chdir(dirname(coreg_job_file))
                subprocess.check_call(cmd)
                yield task1
            else:
                with task1.output().open() as in_fid:
                    lines = in_fid.readlines()
                    # TODO find better checks to determine if coregistration succeeded or not
                    seg_faults = [
                        True for line in lines if "Segmentation fault" in line
                    ]
                    if not seg_faults:
                        task_success = True

            if task_success:
                master_idx = slave_idx
                max_slave_idx = None
                master_list.append(scenes[master_idx])
            else:
                max_slave_idx = slave_idx - 1
                if max_slave_idx == master_idx:
                    break

        if not task_complete:
            ERROR_LOGGER.error(
                "Unable to perform secondary master {m} co-registration task".format(
                    m=scenes[master_idx]
                )
            )

        with self.output().open("w") as out_fid:
            for master in master_list:
                out_fid.write(master + "\n")


class CoregisterSecondaryMasters(luigi.Task):
    """
    Runs the secondary master co-registration task.
    """

    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["check_coregmaster"].path),
                "Secondary_Masters_Coregistration_logs.out",
            )
        )

    def run(self):

        STATUS_LOGGER.info("Co-registering secondary masters")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        # get master scene name from the proc file
        primary_master = path_name["master_scene"]

        # read scenes list for the stack
        with open(path_name["scenes_list"], "r") as in_fid:
            scenes = [
                line.rstrip() for line in in_fid.readlines() if not line.isspace()
            ]

        scenes_datetime = [coreg_utils.parse_date(scene) for scene in scenes]
        primary_master_date = coreg_utils.parse_date(primary_master)

        # set scenes before master scenes in descending order with master scene as a starting scene
        before_master = [
            scenes[idx]
            for idx, scene in enumerate(scenes_datetime)
            if scene < primary_master_date
        ]
        before_master.reverse()
        before_master.insert(0, primary_master)

        # set scenes after master scenes in ascending order with master scene as a starting scene
        after_master = [
            scenes[idx]
            for idx, scene in enumerate(scenes_datetime)
            if scene > primary_master_date
        ]
        after_master.insert(0, primary_master)

        # create two dynamic tasks which can be run simultaneously
        tasks = [
            SecondaryMastersDynamicCoregistration(
                scenes=before_master,
                tag="before",
                proc_file=pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
                coreg_slc_jobs_dir=path_name["coreg_slc_jobs_dir"],
                polarization=path_name["polarization"],
                range_looks=path_name["range_looks"],
                slc_path=path_name["slc_dir"],
            ),
            SecondaryMastersDynamicCoregistration(
                scenes=after_master,
                tag="after",
                proc_file=pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
                coreg_slc_jobs_dir=path_name["coreg_slc_jobs_dir"],
                polarization=path_name["polarization"],
                range_looks=path_name["range_looks"],
                slc_path=path_name["slc_dir"],
            ),
        ]
        yield tasks

        master_list = []
        for task in tasks:
            if not task.complete():
                ERROR_LOGGER.error("Master co-registration task not complete")
            with task.output().open() as in_fid:
                for line in in_fid:
                    if not line.isspace():
                        master_list.append(line.rstrip())

        with self.output().open("w") as out_fid:
            for master in master_list:
                out_fid.write(master + "\n")


class SlavesDynamicCoregistration(luigi.Task):
    """
    Runs the slave co-registration task using secondary masters.
    """

    scenes = luigi.ListParameter(default=[])
    primary_master = luigi.Parameter()
    master = luigi.Parameter()
    tag = luigi.Parameter()
    proc_file = luigi.Parameter()
    coreg_slc_jobs_dir = luigi.Parameter()
    polarization = luigi.Parameter()
    range_looks = luigi.Parameter()
    slc_path = luigi.Parameter()
    project = luigi.Parameter()
    ncpus = luigi.IntParameter()
    memory = luigi.IntParameter()
    queue = luigi.Parameter()
    hours = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            pjoin(
                self.coreg_slc_jobs_dir,
                "Dynamic_Slave_Coregistration_{}_logs.out".format(self.tag),
            )
        )

    def run(self):
        scenes_list = self.scenes
        master = self.master
        used_masters = []
        failed_scenes = None

        def __slave_coregistration(master_scene, slave_scene):
            job_file = pjoin(
                self.coreg_slc_jobs_dir,
                COREG_JOB_FILE_FMT.format(master=master_scene, slave=slave_scene),
            )
            error_log = pjoin(
                self.coreg_slc_jobs_dir,
                COREG_JOB_ERROR_FILE_FMT.format(master=master_scene, slave=slave_scene),
            )

            if master_scene == self.primary_master:
                master_scene = "-"

            if not exists(job_file):
                # clean files for slave_scene from SLC directory
                clean_coreg_scene(
                    self.slc_path, slave_scene, self.polarization, self.range_looks
                )

                with open(job_file, "w") as job_fid:
                    kwargs = {
                        "master": master_scene,
                        "slave": slave_scene,
                        "proc_file": self.proc_file,
                        "error_file": error_log,
                        "project": self.project,
                        "ncpus": self.ncpus,
                        "memory": self.memory,
                        "hours": self.hours,
                        "queue": self.queue,
                    }

                    pbs = COREGISTRATION_JOB_TEMPLATE.format(**kwargs)
                    job_fid.write(pbs)

                STATUS_LOGGER.info(
                    "submitting slave co-registration task with  master: {} and slave: {}".format(
                        master_scene, slave_scene
                    )
                )

                cmd = ["qsub", "{}".format(job_file)]
                os.chdir(dirname(job_file))
                subprocess.check_call(cmd)
            return ExternalFileChecker(error_log)

        while True:
            # add every new master to used_masters to exclude while selecting new master
            used_masters.append(master)
            slave_tasks = [
                __slave_coregistration(master, scene) for scene in scenes_list
            ]

            if not slave_tasks:
                STATUS_LOGGER.info(
                    "No slaves co-register with master {} {}".format(
                        self.tag, self.master
                    )
                )
                break

            if not all([task.complete() for task in slave_tasks]):
                yield slave_tasks
            else:
                failed_tasks = []
                for coreg_task in slave_tasks:
                    with coreg_task.output().open() as in_fid:
                        lines = in_fid.readlines()
                        # TODO find better checks to determine if coregistration succeeded or not
                        seg_faults = [
                            True for line in lines if "Segmentation fault" in line
                        ]
                        if seg_faults:
                            failed_tasks.append(coreg_task)

                if not failed_tasks:
                    break

                # new scene_list(failed scenes) and master(closest to previous master) are computed
                failed_scenes_list = [
                    basename(task.filename).split(".")[0].split("_")[1]
                    for task in failed_tasks
                ]

                # co-register the failed scenes with the successful scenes closet to the master
                masters = [
                    scene
                    for scene in self.scenes
                    if scene not in failed_scenes_list + used_masters
                ]
                if not masters:
                    failed_scenes = failed_scenes_list
                    STATUS_LOGGER.info(
                        "failed to co-register slaves {}".format(str(failed_scenes))
                    )
                    break

                diff = [
                    abs(coreg_utils.parse_date(ms) - coreg_utils.parse_date(master))
                    for ms in masters
                ]
                master = masters[diff.index(min(diff))]
                scenes_list = failed_scenes_list

        with self.output().open("w") as out_fid:
            if failed_scenes:
                for failed_scene in failed_scenes:
                    out_fid.write(failed_scene + "\n")


class CoregisterSlaves(luigi.Task):
    """
    Runs co-registration of slaves tasks.
    """

    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()

    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["coreg_secondary_masters"].path),
                "Slave_Coregistration_logs.out",
            )
        )

    def run(self):

        STATUS_LOGGER.info("Co-registering master-slave")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        # get master scene name from the proc file
        primary_master = path_name["master_scene"]
        # read scenes list for the stack
        with open(path_name["scenes_list"], "r") as in_fid:
            scenes = [
                line.rstrip() for line in in_fid.readlines() if not line.isspace()
            ]

        if primary_master in scenes:
            scenes.remove(primary_master)

        # read secondary master lists from upstream tasks
        with self.input()["coreg_secondary_masters"].open() as in_fid:
            secondary_masters_list = list(
                {line.rstrip() for line in in_fid.readlines() if not line.isspace()}
            )

        # get a dict with secondary master as a key and scenes to be co-registered as values
        # for secondary masters before and after primary master
        before_master_slaves = coreg_utils.coreg_candidates_before_master_scene(
            scenes, secondary_masters_list, primary_master
        )
        after_master_slaves = coreg_utils.coreg_candidates_after_master_scene(
            scenes, secondary_masters_list, primary_master
        )

        slave_tasks = []
        for secondary_master in before_master_slaves:
            slave_tasks.append(
                SlavesDynamicCoregistration(
                    scenes=before_master_slaves[secondary_master],
                    primary_master=primary_master,
                    master=secondary_master,
                    tag="before_{}".format(secondary_master),
                    proc_file=pjoin(
                        path_name["proj_dir"], basename(self.proc_file_path)
                    ),
                    coreg_slc_jobs_dir=path_name["coreg_slc_jobs_dir"],
                    polarization=path_name["polarization"],
                    range_looks=path_name["range_looks"],
                    slc_path=path_name["slc_dir"],
                )
            )
        for secondary_master in after_master_slaves:
            slave_tasks.append(
                SlavesDynamicCoregistration(
                    scenes=after_master_slaves[secondary_master],
                    primary_master=primary_master,
                    master=secondary_master,
                    tag="after_{}".format(secondary_master),
                    proc_file=pjoin(
                        path_name["proj_dir"], basename(self.proc_file_path)
                    ),
                    coreg_slc_jobs_dir=path_name["coreg_slc_jobs_dir"],
                    polarization=path_name["polarization"],
                    range_looks=path_name["range_looks"],
                    slc_path=path_name["slc_dir"],
                )
            )

        yield slave_tasks

        # collect failed scenes from tasks in slave_task_list
        failed_scenes = []
        for task in slave_tasks:
            with task.output().open() as in_fid:
                for line in in_fid:
                    if re.match(r"[0-9]{8}", line):
                        failed_scenes.append(line.rstrip())

        if not exists(path_name["ifgs_list"]):
            ERROR_LOGGER.error("ifg list does not exist")

        if failed_scenes:
            # keep a copy of old ifg list for the record
            old_ifg_list = pjoin(dirname(path_name["ifgs_list"]), "old_ifgs.list")
            if exists(old_ifg_list):
                os.remove(old_ifg_list)
            os.rename(path_name["ifgs_list"], old_ifg_list)

            # get ifg connections lists computed during baseline computation
            with open(old_ifg_list, "r") as in_fid:
                ifg_list = [line.rstrip().split(",") for line in in_fid.readlines()]

            # remove scenes failed at co-registration from ifg list and clean
            # slc directory for that failed scenes
            for scene in failed_scenes:
                shutil.rmtree(pjoin(path_name["slc_dir"], scene))
                for ifg in ifg_list:
                    if scene in ifg:
                        ifg_list.remove(ifg)

            # write ifg list with failed scenes removed
            with open(path_name["ifgs_list"], "w") as out_fid:
                for ifg in ifg_list:
                    out_fid.write("{},{}".format(ifg[0], ifg[1]))
                    out_fid.write("\n")

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["coregslaves"].path),
                "Check_coreg_slaves_status_logs.out",
            )
        )

    def run(self):
        STATUS_LOGGER.info("check co-register master-slaves task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        kwargs = {
            "slc_path": path_name["slc_dir"],
            "master_scene": path_name["master_scene"],
        }

        complete_status = checkcoregslaves(**kwargs)

        if complete_status:
            if path_name["clean_up"] == "yes":
                clean_slcdir(slc_path=kwargs["slc_path"])

            with self.output().open("w") as out_fid:
                out_fid.write(
                    "{dt}".format(
                        dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    )
                )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["check_coregslaves"].path),
                "Process_IFGs_status_logs.out",
            )
        )

    def run(self):
        STATUS_LOGGER.info("processing interferogram task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        args = [
            "bash",
            "process_interferograms_job.bash",
            "%s" % pjoin(path_name["proj_dir"], basename(self.proc_file_path)),
        ]
        subprocess.check_call(args)

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["processifgs"].path),
                "Check_interferograms_status_logs.out",
            )
        )

    def run(self):
        STATUS_LOGGER.info("check inter-ferogram task")
        path_name = get_path(self.proc_file_path)
        path_name = get_path(
            pjoin(path_name["proj_dir"], basename(self.proc_file_path))
        )

        kwargs = {"ifg_path": path_name["ifg_dir"]}

        complete_status = checkifgs(**kwargs)

        if complete_status:
            if path_name["clean_up"] == "yes":
                clean_ifgdir(ifg_path=kwargs["ifg_path"])
                clean_demdir(dem_path=path_name["dem_dir"])

            with self.output().open("w") as out_fid:
                out_fid.write(
                    "{dt}".format(
                        dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    )
                )


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
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["processifgs"].path), "Process_Complete_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("check full stack job completion")
        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class Workflow(luigi.Task):
    """
    A workflow that orchestrates insar procesing pipelines
    for a single stack
    """

    proc_file_path = luigi.Parameter()
    s1_file_list = luigi.Parameter()
    start_date = luigi.DateParameter()
    end_date = luigi.DateParameter()

    def requires(self):

        path_name = get_path(self.proc_file_path)

        # external file checker tasks
        # scenes_list = ExternalFileChecker(path_name["scenes_list"])
        # extract_raw_errors = ExternalFileChecker(path_name["extract_raw_errors"])
        slc_creation_errors = ExternalFileChecker(path_name["slc_creation_errors"])
        multi_look_slc_errors = ExternalFileChecker(path_name["multi-look_slc_errors"])
        init_baseline_errors = ExternalFileChecker(path_name["init_baseline_errors"])
        create_dem_errors = ExternalFileChecker(path_name["create_dem_errors"])
        coreg_dem_errors = ExternalFileChecker(path_name["coreg_dem_errors"])
        ifg_errors = ExternalFileChecker(path_name["ifg_errors"])

        # upstream tasks

        initialsetup = InitialSetup(
            proc_file_path=self.proc_file_path,
            s1_file_list=self.s1_file_list,
            start_date=self.start_date,
            end_date=self.end_date,
        )

        rawdataextract = RawDataExtract(
            proc_file_path=self.proc_file_path,
            s1_file_list=self.s1_file_list,
            upstream_task={"initialsetup": initialsetup},
        )

        createfullslc = CreateFullSlc(
            proc_file_path=self.proc_file_path,
            upstream_task={"rawdataextract": rawdataextract},
        )

        check_fullslc = CheckFullSlc(
            proc_file_path=self.proc_file_path,
            upstream_task={
                "createfullslc": createfullslc,
                "slc_creation_errors": slc_creation_errors,
            },
        )

        creategammadem = CreateGammaDem(
            proc_file_path=self.proc_file_path,
            upstream_task={"rawdataextract": rawdataextract},
        )

        check_creategammadem = CheckGammaDem(
            proc_file_path=self.proc_file_path,
            upstream_task={
                "creategammadem": creategammadem,
                "create_dem_errors": create_dem_errors,
            },
        )

        multilook = CreateMultilook(
            proc_file_path=self.proc_file_path,
            upstream_task={"check_fullslc": check_fullslc},
        )

        check_multilook = CheckMultilook(
            proc_file_path=self.proc_file_path,
            upstream_task={
                "multilook": multilook,
                "multi-look_slc_errors": multi_look_slc_errors,
            },
        )

        calcbaseline = CalcInitialBaseline(
            proc_file_path=self.proc_file_path,
            upstream_task={"check_multilook": check_multilook},
        )

        coregmaster = CoregisterDemMaster(
            proc_file_path=self.proc_file_path,
            upstream_task={
                "calcbaseline": calcbaseline,
                "init_baseline_errors": init_baseline_errors,
                "check_creategammadem": check_creategammadem,
            },
        )

        check_coregmaster = CheckDemMaster(
            proc_file_path=self.proc_file_path,
            upstream_task={
                "coregmaster": coregmaster,
                "coreg_dem_error": coreg_dem_errors,
            },
        )

        coreg_secondary_masters = CoregisterSecondaryMasters(
            proc_file_path=self.proc_file_path,
            upstream_task={"check_coregmaster": check_coregmaster},
        )

        coregslaves = CoregisterSlaves(
            proc_file_path=self.proc_file_path,
            upstream_task={"coreg_secondary_masters": coreg_secondary_masters},
        )

        check_coregslaves = CheckCoregSlave(
            proc_file_path=self.proc_file_path,
            upstream_task={"coregslaves": coregslaves},
        )

        processifgs = ProcessInterFerograms(
            proc_file_path=self.proc_file_path,
            upstream_task={"check_coregslaves": check_coregslaves},
        )

        completioncheck = CompletionCheck(
            upstream_task={"processifgs": processifgs, "ifg_errors": ifg_errors}
        )

        yield rawdataextract

    def output(self):
        path_name = get_path(self.proc_file_path)
        return luigi.LocalTarget(
            pjoin(path_name["checkpoint_dir"], "final_status_logs.out")
        )

    def run(self):
        path_name = get_path(self.proc_file_path)
        if path_name["clean_up"] == "yes":
            clean_ifgdir(ifg_path=path_name["ifg_dir"])
            clean_demdir(dem_path=path_name["dem_dir"])

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


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
        --workdir <working directory, nci outputs and luigi logs will be stored>
        --outdir <output directory where processed data will be stored>
        --local-scheduler (use only local-scheduler)
        --workers <number of workers>
    }

    """

    s1_file_list = luigi.Parameter(significant=False)
    start_date = luigi.DateParameter(significant=False)
    end_date = luigi.DateParameter(significant=False)
    project = luigi.Parameter(significant=False)
    gamma_config = luigi.Parameter(significant=False)
    polarization = luigi.Parameter(default="VV", significant=False)
    multilook = luigi.IntParameter(default=1, significant=False)
    extract_raw_data = luigi.Parameter(default="yes", significant=False)
    do_slc = luigi.Parameter(default="yes", significant=False)
    coregister_dem = luigi.Parameter(default="yes", significant=False)
    coregister_slaves = luigi.Parameter(default="yes", significant=False)
    process_ifgs = luigi.Parameter(default="yes", significant=False)
    process_geotiff = luigi.Parameter(default="yes", significant=False)
    clean_up = luigi.Parameter(default="no", significant=False)
    restart_process = luigi.Parameter(default=False, significant=False)
    checkpoint_patterns = luigi.Parameter(default=None, significant=False)
    outdir = luigi.Parameter(significant=False)
    workdir = luigi.Parameter(significant=False)
    proc_dir = luigi.Parameter(significant=False)

    def requires(self):

        if not exists(self.s1_file_list):
            ERROR_LOGGER.error("{} does not exist".format(self.s1_file_list))
            raise FileNotFoundError

        if not exists(self.outdir):
            os.makedirs(self.outdir)
        if not exists(self.workdir):
            os.makedirs(self.workdir)

        s1_file = basename(self.s1_file_list)
        file_strings = s1_file.split("_")
        track, frame = (file_strings[0], splitext(file_strings[1])[0])

        kwargs = {
            "s1_file_list": s1_file,
            "outdir": self.outdir,
            "project": self.project,
            "track": track,
            "gamma_config": self.gamma_config,
            "frame": frame,
            "polarization": self.polarization,
            "multilook": self.multilook,
            "extract_raw_data": self.extract_raw_data,
            "do_slc": self.do_slc,
            "coregister_dem": self.coregister_dem,
            "coregister_slaves": self.coregister_slaves,
            "process_ifgs": self.process_ifgs,
            "process_geotiff": self.process_geotiff,
            "clean_up": self.clean_up,
        }

        filename_proc = pjoin(self.workdir, "{}_{}.proc".format(track, frame))
        proc_data = PROC_FILE_TEMPLATE.format(**kwargs)

        with open(filename_proc, "w") as src:
            src.writelines(proc_data)

        if self.restart_process:
            path_name = get_path(filename_proc)
            proc_file1 = pjoin(path_name["proj_dir"], filename_proc)
            path_name = get_path(proc_file1)

            if not exists(pjoin(path_name["checkpoint_dir"], "final_status_logs.out")):
                clean_checkpoints(
                    checkpoint_path=path_name["checkpoint_dir"],
                    patterns=self.checkpoint_patterns,
                )

        yield Workflow(
            proc_file_path=filename_proc,
            s1_file_list=self.s1_file_list,
            start_date=self.start_date,
            end_date=self.end_date,
        )

    def output(self):
        out_name = pjoin(self.workdir, "{f}.out".format(f=basename(self.s1_file_list)))
        return luigi.LocalTarget(out_name)

    def run(self):
        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


if __name__ == "__name__":
    luigi.run()
