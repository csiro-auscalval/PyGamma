#!/usr/bin/env python

import datetime
import os
import re
import signal
import traceback
from os.path import exists, join as pjoin, splitext
from pathlib import Path

import luigi
import luigi.configuration
import pandas as pd
from luigi.util import requires

from insar.generate_slc_inputs import query_slc_inputs, slc_inputs
from insar.calc_baselines_new import BaselineProcess
from insar.calc_multilook_values import multilook, calculate_mean_look_values
from insar.coregister_dem import CoregisterDem
from insar.coregister_slc import CoregisterSlc
from insar.logs import ERROR_LOGGER, STATUS_LOGGER
from insar.make_gamma_dem import create_gamma_dem
from insar.process_s1_slc import SlcProcess
from insar.s1_slc_metadata import S1DataDownload
from insar.subprocess_utils import environ


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

    return [
        datetime.datetime.strptime(_dt, "%Y-%m-%d").strftime("%Y%m%d")
        for _dt in sorted(df.date.unique())
    ]


def calculate_master(scenes_list) -> datetime:
    slc_dates = [
        datetime.datetime.strptime(scene.strip(), "%Y%m%d").date()
        for scene in scenes_list
    ]
    return sorted(slc_dates, reverse=True)[int(len(slc_dates) / 2)]


class ExternalFileChecker(luigi.ExternalTask):
    """ checks the external dependencies """

    filename = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(str(self.filename))


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
            Path(str(self.workdir)).joinpath(f"{Path(str(self.slc_scene)).stem}_slc_download.out")
        )

    def run(self):
        download_obj = S1DataDownload(
            Path(str(self.slc_scene)),
            list(self.polarization),
            Path(str(self.poeorb_path)),
            Path(str(self.resorb_path))
        )

        os.makedirs(str(self.output_dir), exist_ok=True)

        download_obj.slc_download(Path(str(self.output_dir)))
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
    polarization = luigi.ListParameter(default=["VV"])
    track = luigi.Parameter()
    frame = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()
    burst_data_csv = luigi.Parameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.workdir)).joinpath(
                f"{self.track}_{self.frame}_initialsetup_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("initial setup task")
        # get the relative orbit number, which is int value of the numeric part of the track name
        rel_orbit = int(re.findall(r"\d+", str(self.track))[0])

        # get slc input information
        slc_query_results = query_slc_inputs(
            str(self.database_name),
            str(self.vector_file),
            self.start_date,
            self.end_date,
            str(self.orbit),
            rel_orbit,
            list(self.polarization),
        )

        # here scenes_list and download_list are overwritten for each polarization
        # IW products in conflict-free mode products VV and VH polarization over land
        slc_inputs_df = pd.concat(
            [
                slc_inputs(slc_query_results[pol])
                for pol in list(self.polarization)
            ]
        )

        # download slc data
        download_dir = Path(str(self.outdir)).joinpath("RAW_DATA")

        os.makedirs(download_dir, exist_ok=True)

        download_list = slc_inputs_df.url.unique()
        download_tasks = []
        for slc_url in download_list:
            scene_date = Path(slc_url).name.split("_")[5].split("T")[0]
            download_tasks.append(
                SlcDataDownload(
                    slc_scene=slc_url.rstrip(),
                    polarization=self.polarization,
                    poeorb_path=self.poeorb_path,
                    resorb_path=self.resorb_path,
                    workdir=self.workdir,
                    output_dir=Path(download_dir).joinpath(scene_date),
                )
            )
        yield download_tasks

        # save slc burst data details which is used by different tasks
        slc_inputs_df.to_csv(self.burst_data_csv)

        with self.output().open("w") as out_fid:
            out_fid.write("")


@requires(InitialSetup)
class CreateGammaDem(luigi.Task):
    """
    Runs create gamma dem task
    """

    dem_img = luigi.Parameter()

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_creategammadem_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("create gamma dem task")
        gamma_dem_dir = Path(self.outdir).joinpath("GAMMA_DEM")

        os.makedirs(gamma_dem_dir, exist_ok=True)

        kwargs = {
            "gamma_dem_dir": gamma_dem_dir,
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
            Path(str(self.workdir)).joinpath(
                f"{self.scene_date}_{self.polarization}_slc_logs.out"
            )
        )

    def run(self):
        slc_job = SlcProcess(
            str(self.raw_path),
            str(self.slc_dir),
            str(self.polarization),
            str(self.scene_date),
            str(self.burst_data),
        )
        slc_job.main()
        with self.output().open("w") as f:
            f.write("")


@requires(InitialSetup)
class CreateFullSlc(luigi.Task):
    """
    Runs the create full slc tasks
    """

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_createfullslc_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("create full slc task")

        slc_scenes = get_scenes(self.burst_data_csv)
        slc_dir = Path(self.outdir).joinpath("SLC")

        os.makedirs(slc_dir, exist_ok=True)

        slc_tasks = []
        for slc_scene in slc_scenes:
            for pol in self.polarization:
                slc_tasks.append(
                    ProcessSlc(
                        scene_date=slc_scene,
                        raw_path=Path(self.outdir).joinpath("RAW_DATA"),
                        polarization=pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                    )
                )

        yield slc_tasks

        with self.output().open("w") as out_fid:
            out_fid.write("")


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
            Path(str(self.workdir)).joinpath(f"{Path(str(self.slc)).stem}_ml_logs.out")
        )

    def run(self):
        multilook(Path(str(self.slc)), Path(str(self.slc_par)), int(str(self.rlks)), int(str(self.alks)))
        with self.output().open("w") as f:
            f.write("")


@requires(CreateFullSlc)
class CreateMultilook(luigi.Task):
    """
    Runs creation of multi-look image task
    """

    multi_look = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_createmultilook_status_logs.out"
            )
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
        rlks, alks, *_ = calculate_mean_look_values(
            [_par for _par in slc_par_files if "VV" in _par.stem], int(str(self.multi_look))
        )

        # multi-look jobs run
        ml_jobs = []
        for slc_par in slc_par_files:
            slc = slc_par.with_suffix("")
            ml_jobs.append(
                Multilook(
                    slc=slc, slc_par=slc_par, rlks=rlks, alks=alks, workdir=self.workdir
                )
            )
        yield ml_jobs
        with self.output().open("w") as out_fid:
            out_fid.write("rlks:\t {}\n".format(str(rlks)))
            out_fid.write("alks:\t {}".format(str(alks)))


@requires(CreateMultilook)
class CalcInitialBaseline(luigi.Task):
    """
    Runs calculation of initial baseline task
    """

    master_scene_polarization = luigi.Parameter(default="VV")

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_calcinitialbaseline_status_logs.out"
            )
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
            str(self.master_scene_polarization),
            master_scene=calculate_master(slc_scenes),
            outdir=Path(self.outdir),
        )
        baseline.sbas_list()

        with self.output().open("w") as out_fid:
            out_fid.write("")


@requires(CreateGammaDem, CalcInitialBaseline)
class CoregisterDemMaster(luigi.Task):
    """
    Runs co-registration of DEM and master scene
    """

    master_scene_polarization = luigi.Parameter(default="VV")
    master_scene = luigi.Parameter(default=None)
    num_threads = luigi.Parameter()

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_coregisterdemmaster_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("co-register master-dem task")

        # glob a multi-look file and read range and azimuth values computed before
        # TODO need better mechanism to pass parameter between tasks
        ml_file = Path(self.workdir).joinpath(
            f"{self.track}_{self.frame}_createmultilook_status_logs.out"
        )
        with open(ml_file, "r") as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(":")[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(":")[1])

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
        dem = (
            Path(self.outdir)
            .joinpath("GAMMA_DEM")
            .joinpath(f"{self.track}_{self.frame}.dem")
        )
        dem_par = dem.with_suffix(dem.suffix + ".par")

        coreg = CoregisterDem(
            rlks=rlks,
            alks=alks,
            dem=dem,
            slc=Path(master_slc),
            dem_par=dem_par,
            slc_par=master_slc_par,
            dem_outdir=Path(self.outdir).joinpath("DEM"),
        )

        # runs with multi-threads and returns to initial setting
        with environ({"OMP_NUM_THREADS": self.num_threads}):
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
    range_looks = luigi.IntParameter()
    azimuth_looks = luigi.IntParameter()
    ellip_pix_sigma0 = luigi.Parameter()
    dem_pix_gamma0 = luigi.Parameter()
    r_dem_master_mli = luigi.Parameter()
    rdc_dem = luigi.Parameter()
    eqa_dem_par = luigi.Parameter()
    dem_lt_fine = luigi.Parameter()
    work_dir = luigi.Parameter()
    num_threads = luigi.Parameter() 

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.work_dir)).joinpath(
                f"{Path(str(self.slc_master)).stem}_{Path(str(self.slc_slave)).stem}_coreg_logs.out"
            )
        )

    def run(self):

        coreg_slave = CoregisterSlc(
            slc_master=Path(str(self.slc_master)),
            slc_slave=Path(str(self.slc_slave)),
            slave_mli=Path(str(self.slave_mli)),
            range_looks=int(str(self.range_looks)),
            azimuth_looks=int(str(self.azimuth_looks)),
            ellip_pix_sigma0=Path(str(self.ellip_pix_sigma0)),
            dem_pix_gamma0=Path(str(self.dem_pix_gamma0)),
            r_dem_master_mli=Path(str(self.r_dem_master_mli)),
            rdc_dem=Path(str(self.rdc_dem)),
            eqa_dem_par=Path(str(self.eqa_dem_par)),
            dem_lt_fine=Path(str(self.dem_lt_fine)),
        )

        # runs with multi-threads and returns to initial setting
        with environ({"OMP_NUM_THREADS": self.num_threads}):
            coreg_slave.main()

        with self.output().open("w") as f:
            f.write("")


@requires(CoregisterDemMaster)
class CreateCoregisterSlaves(luigi.Task):
    """
    Runs the master-slaves co-registration tasks
    """

    master_scene_polarization = luigi.Parameter(default="VV")
    master_scene = luigi.Parameter(default=None)
    num_threads = luigi.Parameter() 

    def output(self):
        inputs = self.input()
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_coregister_slaves_status_logs.out"
            )
        )

    def run(self):
        STATUS_LOGGER.info("co-register master-slaves task")

        slc_scenes = get_scenes(self.burst_data_csv)
        master_scene = self.master_scene
        if master_scene is None:
            master_scene = calculate_master(slc_scenes)

        # get range and azimuth looked values
        ml_file = Path(self.workdir).joinpath(
            f"{self.track}_{self.frame}_createmultilook_status_logs.out"
        )
        with open(ml_file, "r") as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(":")[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(":")[1])

        master_scene = master_scene.strftime("%Y%m%d")
        master_slc_prefix = f"{master_scene}_{str(self.master_scene_polarization).upper()}"
        master_slc_rlks_prefix = f"{master_slc_prefix}_{rlks}rlks"
        r_dem_master_slc_prefix = f"r{master_slc_prefix}"

        dem_dir = Path(self.outdir).joinpath("DEM")
        dem_filenames = CoregisterDem.dem_filenames(
            dem_prefix=master_slc_rlks_prefix, outdir=dem_dir
        )
        slc_master_dir = Path(pjoin(self.outdir, "SLC", master_scene))
        dem_master_names = CoregisterDem.dem_master_names(
            slc_prefix=master_slc_rlks_prefix,
            r_slc_prefix=r_dem_master_slc_prefix,
            outdir=slc_master_dir,
        )
        kwargs = {
            "slc_master": slc_master_dir.joinpath(f"{master_slc_prefix}.slc"),
            "range_looks": rlks,
            "azimuth_looks": alks,
            "ellip_pix_sigma0": dem_filenames["ellip_pix_sigma0"],
            "dem_pix_gamma0": dem_filenames["dem_pix_gam"],
            "r_dem_master_mli": dem_master_names["r_dem_master_mli"],
            "rdc_dem": dem_filenames["rdc_dem"],
            "eqa_dem_par": dem_filenames["eqa_dem_par"],
            "dem_lt_fine": dem_filenames["dem_lt_fine"],
            "work_dir": Path(self.outdir),
            "num_threads": self.num_threads,
        }

        slave_coreg_jobs = []

        # need to account for master scene with polarization different than
        # the one used in coregistration of dem and master scene
        master_pol_coreg = set(list(self.polarization)) - {
            str(self.master_scene_polarization).upper()
        }
        for pol in master_pol_coreg:
            master_slc_prefix = f"{master_scene}_{pol.upper()}"
            kwargs["slc_slave"] = slc_master_dir.joinpath(f"{master_slc_prefix}.slc")
            kwargs["slave_mli"] = slc_master_dir.joinpath(
                f"{master_slc_prefix}_{rlks}rlks.mli"
            )
            slave_coreg_jobs.append(CoregisterSlave(**kwargs))

        # slave coregisration
        slc_scenes.remove(master_scene)
        for slc_scene in slc_scenes:
            slave_dir = Path(self.outdir).joinpath("SLC").joinpath(slc_scene)
            for pol in self.polarization:
                slave_slc_prefix = f"{slc_scene}_{pol.upper()}"
                kwargs["slc_slave"] = slave_dir.joinpath(f"{slave_slc_prefix}.slc")
                kwargs["slave_mli"] = slave_dir.joinpath(
                    f"{slave_slc_prefix}_{rlks}rlks.mli"
                )
                slave_coreg_jobs.append(CoregisterSlave(**kwargs))

        yield slave_coreg_jobs

        with self.output().open("w") as f:
            f.write("")


class ARD(luigi.WrapperTask):
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
    polarization = luigi.ListParameter(default=["VV", "VH"], significant=False)
    cleanup = luigi.Parameter(default="no", significant=False)
    outdir = luigi.Parameter(significant=False)
    workdir = luigi.Parameter(significant=False)
    database_name = luigi.Parameter()
    orbit = luigi.Parameter()
    dem_img = luigi.Parameter()
    multi_look = luigi.Parameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()
    num_threads = luigi.Parameter() 

    def requires(self):
        if not Path(str(self.vector_file)).exists():
            ERROR_LOGGER.error(f"{self.vector_file} does not exist")
            raise FileNotFoundError

        track_frame = Path(str(self.vector_file)).stem
        file_strings = track_frame.split("_")
        track, frame = (file_strings[0], splitext(file_strings[1])[0])

        outdir = Path(str(self.outdir)).joinpath(track_frame)
        workdir = Path(str(self.workdir)).joinpath(track_frame)

        os.makedirs(outdir, exist_ok=True)
        os.makedirs(workdir, exist_ok=True)

        kwargs = {
            "vector_file": self.vector_file,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "database_name": self.database_name,
            "polarization": self.polarization,
            "track": track,
            "frame": frame,
            "outdir": outdir,
            "workdir": workdir,
            "orbit": self.orbit,
            "dem_img": self.dem_img,
            "poeorb_path": self.poeorb_path,
            "resorb_path": self.resorb_path,
            "multi_look": self.multi_look,
            "burst_data_csv": pjoin(outdir, f"{track_frame}_burst_data.csv"),
            "num_threads": self.num_threads,
        }

        yield CreateCoregisterSlaves(**kwargs)


def run():
    luigi.run()


if __name__ == "__name__":
    run()
