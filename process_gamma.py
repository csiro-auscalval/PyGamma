#!/usr/bin/python3

import os
from os.path import basename, dirname, exists, join as pjoin, splitext
from pathlib import Path
import datetime
import signal
import traceback
import re
import uuid
import luigi
import luigi.configuration
from luigi.util import inherits
import pandas as pd
from python_scripts import generate_slc_inputs
from python_scripts.coregister_slc import CoregisterSlc
from python_scripts.calc_baselines_new import BaselineProcess
from python_scripts.coregister_dem import CoregisterDem
from python_scripts.make_gamma_dem import create_gamma_dem
from python_scripts.calc_multilook_values import multilook, caculate_mean_look_values
from python_scripts.process_s1_slc import SlcProcess
from python_scripts.s1_slc_metadata import S1DataDownload
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


def get_scenes(burst_data_csv):
    df = pd.read_csv(burst_data_csv)
    return [_dt.sfrftime("%Y%m%d") for _dt in sorted(df.date.unique())]

def calculate_master(scenes_list) -> str:
        slc_dates = [
            datetime.datetime.strptime(scene.strip(), "%Y%m%d").date()
            for scene in scenes_list
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


class SlcDataDownload(luigi.Task):
    """
    Runs single slc scene extraction task
    """

    slc_scene = luigi.Parameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()
    output_dir = luigi.Parameter()
    polarization = luigi.ListParameter()
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_slc_download.out"_scene)
        )

    def run(self):
        download_obj = S1DataDownload(
            self.slc_scene, self.polarization, self.poeorb_path, self.resorb_path
        )
        if not Path(self.output_dir).exists():
            os.makedirs(self.output_dir)

        download_obj.slc_download(self.output_dir)

        with self.output().open("w") as f:
            f.write("")


class InitialSetup(luigi.Task):
    """
    Runs the initial setup of insar processing workflow by
    creating required directories and file lists
    """
    start_date = luigi.Parameter()
    end_date = luigi.Parameter()
    vector_file = luigi.Parameter()
    database_name = luigi.Parameter()
    orbit = luigi.Parameter()
    polarization = luigi.ListParameter(default=['VV'])
    track = luigi.Parameter()
    frame = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()
    burst_data_csv = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_initialsetup_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("initial setup task")
        # get the relative orbit number, which is int value of the numeric part of the track name
        rel_orbit = int(re.findall(r"\d+", self.track)[0])

        # get slc input information
        slc_query_results = generate_slc_inputs.query_slc_inputs(
            self.database_name,
            self.vector_file,
            self.start_date,
            self.end_date,
            self.orbit,
            rel_orbit,
            self.polarization,
        )

        # here scenes_list and download_list are overwritten for each polarization
        # IW products in conflict-free mode products VV and VH polarization over land
        slc_inputs_df = pd.concat(
            [
                generate_slc_inputs.slc_inputs(slc_query_results[pol])
                for pol in self.polarization
            ]
        )

        # download slc data
        download_dir = Path(self.outdir).joinpath("RAW_DATA")
        if not download_dir.exists():
            os.mkdirs(download_dir)

        download_list = slc_inputs_df.url.unique()
        download_tasks = []
        for slc_url in download_list:
            scene_date = Path(slc_url).name.split("_")[5].split("T")[0]
            download_tasks.append(
                SlcDataDownload(
                    slc_scene=slc_scene.rstrip(),
                    polarization=self.polarization,
                    download_jobs_dir=self.workdir,
                    output_dir=Path(download_dir).joinpath(slc_scene),
                )
            )
        yield download_tasks

        # save slc burst data details which is used by different tasks
        slc_inputs_df.to_csv(self.burst_data_csv)

        with self.output().open("w") as out_fid:
            out_fid.write("")


@inherits(InitialSetup)
class CreateGammaDem(luigi.Task):
    """
    Runs create gamma dem task
    """

    upstream_task = luigi.Parameter()
    dem_img = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_creategammadem_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("create gamma dem task")
        kwargs = {
            "gamma_dem_dir": Path(self.outdir).joinpath("gamma_dem"),
            "dem_img": self.dem_img,
            "track_frame": f"{self.track}_{self.frame}",
            "shapefile": self.vector_file,
        }

        create_gamma_dem(**kwargs)
        with self.output().open("w") as out_fid:
            out_fid.write("")


class ProcessSlc(luigi.Task):
    """
    Runs single slc processing task
    """

    scene_date = luigi.Parameter()
    raw_path = luigi.Parameter()
    polarization = luigi.Parameter()
    burst_data = luigi.Parameter()
    slc_dir = luigi.Parameter()
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_slc_logs.out")
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
            f.write("")


@inherits(InitialSetup)
class CreateFullSlc(luigi.Task):
    """
    Runs the create full slc tasks
    """

    upstream_task = luigi.Parameter()

    def requires(self):

        return self.upstream_task

    def output(self):

        inputs = self.input()
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_createfullslc_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("create full slc task")

        slc_scenes = get_scenes(self.burst_data_csv)
        slc_tasks = []
        for slc_scene in slc_scenes:
            for pol in self.polarization:
                slc_tasks.append(
                    ProcessSlc(
                        scene_date=slc_scene,
                        raw_path=Path(self.outdir).joinpath("RAW_DATA"),
                        polarization=pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=Path(self.outdir).joinpath("SLC"),
                        workdir=self.workdir,
                    )
                )

        yield slc_tasks

        with self.output().open("w") as out_fid:
            outdir.write("")


class Multilook(luigi.Task):
    """
    Runs single slc processing task
    """

    slc = luigi.Parameter()
    slc_par = luigi.Parameter()
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_ml_logs.out")
        )

    def run(self):

        multilook(Path(self.slc), Path(self.slc_par), self.rlks, self.alks)
        with self.output().open("w") as f:
            f.write("")


@inherits(InitialSetup)
class CreateMultilook(luigi.Task):
    """
    Runs creation of multi-look image task
    """

    upstream_task = luigi.Parameter()
    multi_look = luigi.IntParameter()

    def requires(self):
        return self.upstream_task

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdiir).joinpath(f"{uuid.uuid4()_createmultilook_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("create multi-look task")

        # calculate the mean range and azimuth look values
        slc_scenes = get_scenes(self.burst_data_csv)
        slc_par_files = []
        for slc_scene in slc_scenes:
            for pol in self.polarization:
                slc_par = pjoin(
                    self.outdir,
                    "SLC",
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
                    workdir=self.workdir,
                )
            )
        yield ml_jobs
        with self.output().open("w") as out_fid:
            out_fid.write("rlks:\t {}".format(str(rlks)))
            out_fid.write("alks:\t {}".format(str(alks)))


@inherits(InitialSetup)
class CalcInitialBaseline(luigi.Task):
    """
    Runs calculation of initial baseline task
    """
    upstream_task = luigi.Parameter()
    master_scene_polarization = luigi.Parameter(default="VV")

    def requires(self):

        return self.upstream_task

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_calcinitialbaseline_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("calculate baseline task")

        slc_scenes = get_scenes(self.burst_data_csv)
        slc_par_files = []
        for slc_scene in slc_scenes:
            slc_par = pjoin(
                self.outdir,
                "SLC",
                slc_scene,
                "{}_{}.slc.par".format(slc_scene, self.master_scene_polarization),
            )
            if not exists(slc_par):
                raise FileNotFoundError(f"missing {slc_par} file")
            slc_par_files.append(Path(slc_par))

        baseline = BaselineProcess(
            slc_par_files,
            self.master_scene_polarization,
            outdir=Path(self.outdir),
            master_scene=calculate_master(slc_scenes),
        )
        baseline.sbas_list()

        with self.output().open("w") as out_fid:
            out_fid.write("")


@inherits(InitialSetup)
class CoregisterDemMaster(luigi.Task):
    """
    Runs co-registration of DEM and master scene
    """

    upstream_task = luigi.Parameter()
    master_scene_polarization = luigi.Parameter(default='VV')
    master_scene = luigi.Parameter(default=None)

    def requires(self):

        return self.upstream_task

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()_coregisterdemmaster_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("co-register master-dem task")

        # glob a multi-look file and read range and azimuth values computed before
        # TODO need better mechanism to pass parameter between tasks
        ml_file = Path(self.input()["calcbaseline"].path).glob('**/*_createmultilook_status_logs.out')[0]
        with open(ml_file, "r") as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(':')[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(':')[1])

        master_scene = self.master_scene
        if master_scene is None:
            slc_scenes = get_scenes(self.burst_data_csv)
            master_scene = calculate_master(slc_scenes)

        master_slc = pjoin(
            Path(self.outdir),
            "SLC",
            master_scene.strftime("%Y%m%d"),
            "{}_{}.slc".format(
                master_scene.strftime("%Y%m%d"), self.master_scene_polarization
            ),
        )

        master_slc_par = Path(master_slc).with_suffix(".slc.par")
        dem = Path(self.outdir).joinpath("gamma_dem").joinpath(f"{self.track}_{self.frame}.dem")
        dem_par = dem.with_suffix(dem.suffix + ".par")

        coreg = CoregisterDem(
            rlks=rlks,
            alks=alks,
            dem=dem,
            slc=Path(master_slc),
            dem_par=dem_par,
            slc_par=master_slc_par,
            outdir=Path(self.outdir).joinpath("DEM"),
        )

        # runs with multi-threads and returns to initial setting
        with environ({'OMP_NUM_THREADS': '4'}):
            coreg.main()

        with self.output().open("w") as out_fid:
            out_fid.write("")


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
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f "{uuid.uuid4()}_coreg_logs.out")
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
            f.write("")


@inherits(InitialSetup)
class CreateCoregisterSlaves(luigi.Task):
    """
    Runs the master-slaves co-registration tasks
    """

    upstream_task = luigi.Parameter()
    master_scene_polarization = luigi.Parameter(default='VV')
    master_scene = luigi.Parameter(default=None)

    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()_coregister_slaves_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("co-register master-slaves task")

        slc_scenes = get_scenes(self.burst_data_csv)
        master_scene = self.master_scene
        if master_scene is None:
            master_scene = calculate_master(slc_scenes)

        # get range and azimuth looked values
        ml_file = Path(self.input()["calcbaseline"].path).glob('**/*_createmultilook_status_logs.out')[0]
        with open(ml_file, "r") as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(':')[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(':')[1])

        master_scene = master_scene.strftime('%Y%m%d')
        master_slc_prefix = f"{master_scene}_{self.master_scene_polarization.upper()}"
        master_slc_rlks_prefix = f"{master_slc_prefix}_{rlks}rlks"
        r_dem_master_slc_prefix = f"r{master_slc_prefix}"

        dem_dir = Path(self.outdir).joinpath("DEM")
        dem_filenames = CoregisterDem.dem_filenames(
            dem_prefix=master_slc_rlks_prefix,
            outdir=dem_dir
        )
        slc_master_dir = Path(pjoin(self.outdir, "SLC", master_scene))
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
            'workdir': Path(self.outdir)
        }

        slave_coreg_jobs = []
        slc_scenes.remove(master_scene)
        for slc_scene in slc_scenes:
            slave_dir = Path(self.outdir).joinpath("SLC").joinpath(slc_scene)
            for pol in self.polarization:
                slave_slc_prefix = f"{slc_scene}_{pol.upper()}"
                kwargs['slc_slave'] = slave_dir.joinpath(f"{slave_slc_prefix}.slc")
                kwargs['slave_mli'] = slave_dir.joinpath(f"{slave_slc_prefix}_{rlks}rlks.mli")
                slave_coreg_jobs.append(CoregisterSlc(**kwargs))

        yield slave_coreg_jobs

        with self.output().open("w") as f:
            f.write("")


class CompletionCheck(luigi.Task):
    """
    Runs checking of task completion for full workflow
    for a single stack
    """

    upstream_task = luigi.Parameter()
    workdir = luigi.Parameter()
    def requires(self):
        return self.upstream_task

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(f"{uuid.uuid4()}_processcomplete_status_logs.out")
        )

    def run(self):
        STATUS_LOGGER.info("check full stack job completion")
        with self.output().open("w") as out_fid:
            out_fid.write("")


class Workflow(luigi.Task):
    """
    A workflow that orchestrates insar procesing pipelines
    for a single stack
    """
    track_frame_vector = luigi.Parameter()
    start_date = luigi.DateParameter()
    end_date = luigi.DateParameter()
    polarization = luigi.ListParameter(default=['VV'])
    track = luigi.Parameter()
    frame = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()

    def requires(self):
        # upstream tasks
        initialsetup = InitialSetup(
            vector_file=self.track_frame_vector,
            start_date=self.start_date,
            end_date=self.end_date,
            polarization=self.polarization,
            track=self.track,
            frame=self.frame,
            outdir=self.outdir,
            workdir=self.workdir,
            burst_data_csv=pjoin(self.outdir, f"{self.track}_{self.frame}_burst_data.csv")
        )

        createfullslc = CreateFullSlc(
            upstream_task={"initialsetup": initialsetup},
        )

        creategammadem = CreateGammaDem(
            upstream_task={"initial_setup": initialsetup},
        )

        multilook = CreateMultilook(
            upstream_task={"createfullslc": createfullslc},
        )

        calcbaseline = CalcInitialBaseline(
            upstream_task={"multilook": multilook}
        )

        coregmaster = CoregisterDemMaster(
            upstream_task={
                "calcbaseline": calcbaseline,
                "creategammadem": creategammadem,
            },
        )

        coregslaves = CreateCoregisterSlaves(
            upstream_task={"coregmaster": coregmaster},
        )

        completioncheck = CompletionCheck(
            upstream_task={"coregslaves": coregslaves},
            workdir=self.workdir
        )

        yield completioncheck

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir, f"{uuid.uuid4()_final_status_logs.out")
        )

    def run(self):
        with self.output().open("w") as out_fid:
            out_fid.write("")


class ARD(luigi.Task):
    """
    Runs the InSAR ARD pipeline using GAMMA software.

    -----------------------------------------------------------------------------
    minimum parameter required to run using default luigi Parameter set in luigi.cfg
    ------------------------------------------------------------------------------
    usage:{
        luigi --module process_gamma ARD
        --vector-file <path to a vector file (.shp)>
        --start-date <start date of SLC acquisition>
        --end-date <end date of SLC acquisition>
        --workdir <base working directory where luigi logs will be stored>
        --outdir <output directory where processed data will be stored>
        --local-scheduler (use only local-scheduler)
        --workers <number of workers>
    }
    """

    vector_file = luigi.Parameter(significant=False)
    start_date = luigi.DateParameter(significant=False)
    end_date = luigi.DateParameter(significant=False)
    polarization = luigi.ListParameter(default=["VV"], significant=False)
    clean_up = luigi.Parameter(default="no", significant=False)
    outdir = luigi.Parameter(significant=False)
    workdir = luigi.Parameter(significant=False)

    def requires(self):
        if not exists(self.vector_file):
            ERROR_LOGGER.error(f"{self.vector_file} does not exist")
            raise FileNotFoundError

        if not exists(self.outdir):
            os.makedirs(self.outdir)
        if not exists(self.workdir):
            os.makedirs(self.workdir)

        s1_file = basename(self.s1_file_list)
        file_strings = s1_file.split("_")
        track, frame = (file_strings[0], splitext(file_strings[1])[0])

        yield Workflow(
            vector_file=self.vector_file,
            start_date=self.start_date,
            end_date=self.end_date,
            polarization=self.polarization,
            track=track,
            frame=frame,
            outdir=self.outdir,
            workdir=self.workdir,
            cleanup=self.clean_up
        )

    def output(self):
        return luigi.LocalTarget(Path(self.workdir).joinpath(f"{self.vector_file.name}.out"))

    def run(self):
        with self.output().open("w") as f:
            f.write("")

if __name__ == "__name__":
    luigi.run()
