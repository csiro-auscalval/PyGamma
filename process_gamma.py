#!/usr/bin/python3

import os
from os.path import basename, dirname, exists, join as pjoin, splitext
from pathlib import Path
import datetime
import signal
import traceback
import re

import luigi
import luigi.configuration
from python_scripts import generate_slc_inputs
from python_scripts.coregister_slc import CoregisterSlc
from python_scripts.calc_baselines_new import BaselineProcess
from python_scripts.coregister_dem import CoregisterDem
from python_scripts.make_gamma_dem import create_gamma_dem
from python_scripts.calc_multilook_values import multilook, caculate_mean_look_values
from python_scripts.process_s1_slc import SlcProcess
from python_scripts.s1_slc_metadata import S1DataDownload
from python_scripts.initialize_proc_file import get_path, setup_folders
from python_scripts.proc_template import PROC_FILE_TEMPLATE
from python_scripts.subprocess_utils import environ
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


def calculate_master(scenes_list) -> str:
    with open(scenes_list, "r") as src:
        slc_dates = [
            datetime.datetime.strptime(scene.strip(), "%Y%m%d").date()
            for scene in src.readlines()
        ]
        return sorted(slc_dates, reverse=True)[int(len(slc_dates) / 2)]


class ExternalFileChecker(luigi.ExternalTask):
    """ checks the external dependencies """

    filename = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(self.filename)


class ListParameter(luigi.Parameter):
    """
    Converts luigi parameters separated by comma to a list.
     """
    def parse(self, arguments):
        return arguments.split(",")


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
    polarization = luigi.ListParameter(default=['VV'])

    def output(self):
        path_name = get_path(self.proc_file_path)
        return luigi.LocalTarget(
            pjoin(path_name["checkpoint_dir"], "InitialSetup_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("initial setup task")
        setup_folders(self.proc_file_path)
        path_name = get_path(self.proc_file_path)

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
            self.polarization,
        )

        # here scenes_list and download_list are overwritten for each polarization
        # IW products in conflict-free mode products VV and VH polarization over land
        for pol in self.polarization:
            generate_slc_inputs.generate_lists(
                slc_input_results,
                Path(path_name["list_dir"]).joinpath(f"slc_input_{pol}.csv"),
                Path(path_name["list_dir"]).joinpath(f"scenes_list"),
                Path(path_name["list_dir"]).joinpath(f"download_list")
            )

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
    polarization = luigi.ListParameter()

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
    polarization = luigi.ListParameter(default=['VV'])

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
        download_tasks = []

        with open(path_name["download_list"], "r") as src:
            slc_scenes = src.readlines()
            for slc_scene in slc_scenes:
                scene_date = basename(slc_scene).split("_")[5].split("T")[0]
                download_tasks.append(
                    SlcDataDownload(
                        slc_scene=slc_scene.rstrip(),
                        polarization=self.polarization,
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
    s1_file_list = luigi.Parameter()
    dem_img = luigi.Parameter()

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

        kwargs = {
            "gamma_dem_dir": path_name["gamma_dem"],
            "dem_img": self.dem_img,
            "track_frame": path_name["track_frame"],
            "shapefile": self.s1_file_list,
        }

        create_gamma_dem(**kwargs)
        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class ProcessSlc(luigi.Task):
    """
    Runs single slc processing task
    """

    scene_date = luigi.Parameter()
    raw_path = luigi.Parameter()
    polarization = luigi.Parameter()
    burst_data = luigi.Parameter()
    slc_dir = luigi.Parameter()
    slc_jobs_dir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            pjoin(self.slc_jobs_dir, f"{self.scene_date}{self.polarization}_slc_logs.out")
        )

    def run(self):
        slc_job = SlcProcess(
            self.raw_path,
            self.slc_dir,
            self.polarization,
            self.scene_date,
            self.burst_data,
        )
        slc_job.main()
        with self.output().open("w") as f:
            f.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class CreateFullSlc(luigi.Task):
    """
    Runs the create full slc tasks
    """

    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()
    polarization = luigi.ListParameter(default=['VV'])

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
        slc_tasks = []

        with open(path_name["scenes_list"], "r") as src:
            slc_scenes = [scene.rstrip() for scene in src.readlines()]
            for slc_scene in slc_scenes:
                for pol in self.polarization:
                    slc_tasks.append(
                        ProcessSlc(
                            scene_date=slc_scene,
                            raw_path=path_name["raw_data_dir"],
                            polarization=pol,
                            burst_data=Path(path_name["list_dir"]).joinpath(f"slc_input_{pol}.csv"),
                            slc_dir=path_name["slc_dir"],
                            slc_jobs_dir=path_name["slc_jobs_dir"],
                        )
                    )

        yield slc_tasks

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class Multilook(luigi.Task):
    """
    Runs single slc processing task
    """

    slc = luigi.Parameter()
    slc_par = luigi.Parameter()
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()
    ml_jobs_dir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            pjoin(self.ml_jobs_dir, "{}_ml_logs.out".format(basename(self.slc)))
        )

    def run(self):

        multilook(Path(self.slc), Path(self.slc_par), self.rlks, self.alks)
        with self.output().open("w") as f:
            f.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class CreateMultilook(luigi.Task):
    """
    Runs creation of multi-look image task
    """

    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()
    multi_look = luigi.IntParameter()
    polarization = luigi.ListParameter(default=['VV'])

    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["createfullslc"].path), "CreateMultilook_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("create multi-look task")
        path_name = get_path(self.proc_file_path)

        # calculate the mean range and azimuth look values
        slc_par_files = []
        with open(path_name["scenes_list"], "r") as src:
            slc_scenes = [scene.rstrip() for scene in src.readlines()]
            for slc_scene in slc_scenes:
                for pol in self.polarization:
                    slc_par = pjoin(
                        path_name["slc_dir"],
                        slc_scene,
                        "{}_{}.slc.par".format(slc_scene, pol),
                    )
                    if not exists(slc_par):
                        raise FileNotFoundError(f"missing {slc_par} file")
                slc_par_files.append(Path(slc_par))

        # range and azimuth looks are only computed from VV polarization
        rlks, alks, *_ = caculate_mean_look_values(
            [_par for _par in slc_par_files if "VV" in _par],
            self.multi_look
        )

        # multi-look jobs run
        ml_jobs = []
        for slc_par in slc_par_files:
            slc = slc_par.with_suffix("")
            ml_jobs.append(
                Multilook(
                    slc=slc,
                    slc_par=slc_par,
                    rlks=rlks,
                    alks=alks,
                    ml_jobs_dir=path_name["ml_slc_jobs_dir"],
                )
            )
        yield ml_jobs
        with self.output().open("w") as out_fid:
            out_fid.write("rlks:\t {}".format(str(rlks)))
            out_fid.write("alks:\t {}".format(str(alks)))
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
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
                dirname(inputs["multilook"].path), "CalcInitialBaseline_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("calculate baseline task")
        path_name = get_path(self.proc_file_path)
        polarization = 'VV'
        slc_par_files = []
        with open(path_name["scenes_list"], "r") as src:
            slc_scenes = [scene.rstrip() for scene in src.readlines()]
            for slc_scene in slc_scenes:
                slc_par = pjoin(
                    path_name["slc_dir"],
                    slc_scene,
                    "{}_{}.slc.par".format(slc_scene, polarization),
                )
                if not exists(slc_par):
                    raise FileNotFoundError(f"missing {slc_par} file")
                slc_par_files.append(Path(slc_par))

        baseline = BaselineProcess(
            slc_par_files,
            path_name["polarization"],
            outdir=Path(path_name["list_dir"]),
            master_scene=calculate_master(path_name["scenes_list"]),
        )
        baseline.sbas_list()

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class CoregisterDemMaster(luigi.Task):
    """
    Runs co-registration of DEM and master scene
    """

    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()
    master_scene_polarization = luigi.Parameter(default='VV')
    master_scene = luigi.Parameter(default=None)

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

        with open(
            pjoin(
                dirname(self.input()["calcbaseline"].path), "CreateMultilook_status_logs.out"
            ), "r"
        ) as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(':')[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(':')[1])

        master_scene = self.master_scene
        if master_scene is None:
            master_scene = calculate_master(path_name["scenes_list"])

        master_slc = pjoin(
            Path(path_name["slc_dir"]),
            master_scene.strftime("%Y%m%d"),
            "{}_{}.slc".format(
                master_scene.strftime("%Y%m%d"), self.master_scene_polarization
            ),
        )

        master_slc_par = Path(master_slc).with_suffix(".slc.par")
        dem = Path(path_name["gamma_dem"]).joinpath(f"{path_name['track_frame']}.dem")
        dem_par = dem.with_suffix(dem.suffix + ".par")

        coreg = CoregisterDem(
            rlks=rlks,
            alks=alks,
            dem=dem,
            slc=Path(master_slc),
            dem_par=dem_par,
            slc_par=master_slc_par,
            outdir=Path(path_name["dem_dir"]),
        )

        # runs with multi-threads and returns to initial setting
        with environ({'OMP_NUM_THREADS': '4'}):
            coreg.main()

        with self.output().open("w") as out_fid:
            out_fid.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class CoregisterSlave(luigi.Task):
    """
    Runs the master-slave co-registration task
    """
    slc_master = luigi.Parameter()
    slc_slave = luigi.Parameter()
    slave_mli = luigi.Parameter()
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()
    ellip_pix_sigma0 = luigi.Parameter()
    dem_pix_gamma0 = luigi.Parameter()
    r_dem_master_mli = luigi.Parameter()
    rdc_dem = luigi.Parameter()
    eqa_dem_par = luigi.Parameter()
    dem_lt_fine = luigi.Parameter()
    coreg_jobs_dir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            pjoin(self.coreg_jobs_dir, "{}_coreg_logs.out".format(basename(self.slc_slave)))
        )

    def run(self):

        CoregisterSlc(
            slc_master=Path(self.slc_master),
            slc_slave=Path(self.slc_slave),
            slave_mli=Path(self.slave_mli),
            range_looks=int(self.rlks),
            azimuth_looks=int(self.alks),
            ellip_pix_sigma0=Path(self.ellip_pix_sigma0),
            dem_pix_gamma0=Path(self.dem_pix_gamma0),
            r_dem_master_mli=Path(self.r_dem_master_mli),
            rdc_dem=Path(self.rdc_dem),
            eqa_dem_par=Path(self.eqa_dem_par),
            dem_lt_fine=Path(self.dem_lt_fine),
        )
        with self.output().open("w") as f:
            f.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
            )


class CreateCoregisterSlaves(luigi.Task):
    """
    Runs the master-slaves co-registration tasks
    """

    proc_file_path = luigi.Parameter()
    upstream_task = luigi.Parameter()
    master_scene_polarization = luigi.Parameter(default='VV')
    polarization = luigi.ListParameter(default=['VV'])
    master_scene = luigi.Parameter(default=None)

    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            pjoin(
                dirname(inputs["coregmaster"].path), "Coregister_slaves_status_logs.out"
            )
        )

    def run(self):

        STATUS_LOGGER.info("co-register master-slaves task")
        path_name = get_path(self.proc_file_path)

        master_scene = self.master_scene
        if master_scene is None:
            master_scene = calculate_master(path_name["scenes_list"])

        with open(
            pjoin(
                dirname(self.input()["coregmaster"].path), "CreateMultilook_status_logs.out"
            ), "r"
        ) as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(':')[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(':')[1])

        master_scene = master_scene.strftime('%Y%m%d')
        master_slc_prefix = f"{master_scene}_{self.master_scene_polarization.upper()}"
        master_slc_rlks_prefix = f"{master_slc_prefix}_{rlks}rlks"
        r_dem_master_slc_prefix = f"r{master_slc_prefix}"

        dem_dir = Path(path_name["dem_dir"])
        dem_filenames = CoregisterDem.dem_filenames(
            dem_prefix=master_slc_rlks_prefix,
            outdir=dem_dir
        )
        slc_master_dir = Path(pjoin(path_name['slc_dir'], master_scene))
        dem_master_names = CoregisterDem.dem_master_names(
            slc_prefix=master_slc_rlks_prefix,
            r_slc_prefix=r_dem_master_slc_prefix,
            outdir=slc_master_dir
        )
        kwargs = {
            'slc_master': slc_master_dir.joinpath(f"{master_slc_prefix}.slc"),
            'rlk': rlks,
            'alks': alks,
            'ellip_pix_sigma0': dem_filenames['ellip_pix_sigma0'],
            'dem_pix_gamma0': dem_filenames['dem_pix_gam'],
            'r_dem_master_mli': dem_master_names['r_dem_master_mli'],
            'rdc_dem': dem_filenames['rdc_dem'],
            'eqa_dem_par': dem_filenames['eqa_dem_par'],
            'dem_lt_fine': dem_filenames['dem_lt_fine'],
            'coreg_jobs_dir': Path(path_name['coreg_slc_jobs_dir'])
        }

        slave_coreg_jobs = []
        with open(path_name["scenes_list"], "r") as src:
            slc_scenes = [scene.rstrip() for scene in src.readlines()]
            slc_scenes.remove(master_scene)
            for slc_scene in slc_scenes:
                slave_dir = Path(path_name["slc_dir"]).joinpath(slc_scene)
                for pol in self.polarization:
                    slave_slc_prefix = f"{slc_scene}_{pol.upper()}"
                    kwargs['slc_slave'] = slave_dir.joinpath(f"{slave_slc_prefix}.slc")
                    kwargs['slave_mli'] = slave_dir.joinpath(f"{slave_slc_prefix}_{rlks}rlks.mli")
                    slave_coreg_jobs.append(CoregisterSlc(**kwargs))

        yield slave_coreg_jobs

        with self.output().open("w") as f:
            f.write(
                "{dt}".format(dt=datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"))
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
                dirname(inputs["coregslaves"].path), "Process_Complete_status_logs.out"
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
    polarization = luigi.ListParameter(default=['VV'])

    def requires(self):
        # upstream tasks
        initialsetup = InitialSetup(
            proc_file_path=self.proc_file_path,
            s1_file_list=self.s1_file_list,
            start_date=self.start_date,
            end_date=self.end_date,
            polarization=self.polarization
        )

        rawdataextract = RawDataExtract(
            proc_file_path=self.proc_file_path,
            s1_file_list=self.s1_file_list,
            upstream_task={"initialsetup": initialsetup},
            polarization=self.polarization
        )

        createfullslc = CreateFullSlc(
            proc_file_path=self.proc_file_path,
            upstream_task={"rawdataextract": rawdataextract},
            polarization=self.polarization
        )

        creategammadem = CreateGammaDem(
            proc_file_path=self.proc_file_path,
            upstream_task={"rawdataextract": rawdataextract},
            s1_file_list=self.s1_file_list,
        )

        multilook = CreateMultilook(
            proc_file_path=self.proc_file_path,
            upstream_task={"createfullslc": createfullslc},
            polarization=self.polarization
        )

        calcbaseline = CalcInitialBaseline(
            proc_file_path=self.proc_file_path, upstream_task={"multilook": multilook}
        )

        coregmaster = CoregisterDemMaster(
            proc_file_path=self.proc_file_path,
            upstream_task={
                "calcbaseline": calcbaseline,
                "creategammadem": creategammadem,
            },
        )

        coregslaves = CreateCoregisterSlaves(
            proc_file_path=self.proc_file_path,
            upstream_task={"coregmaster": coregmaster},
        )

        completioncheck = CompletionCheck(upstream_task={"coregslaves": coregslaves})

        yield completioncheck

    def output(self):
        path_name = get_path(self.proc_file_path)
        return luigi.LocalTarget(
            pjoin(path_name["checkpoint_dir"], "final_status_logs.out")
        )

    def run(self):

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
    polarization = luigi.ListParameter(default=["VV"], significant=False)
    multi_look = luigi.IntParameter(default=1, significant=False)
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
            "polarization": "VV",
            "multi_look": self.multi_look,
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

        yield Workflow(
            proc_file_path=filename_proc,
            s1_file_list=self.s1_file_list,
            start_date=self.start_date,
            end_date=self.end_date,
            polarization=self.polarization
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
