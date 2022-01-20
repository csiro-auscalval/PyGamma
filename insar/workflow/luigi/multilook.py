import luigi
from luigi.util import inherits, common_params

from pathlib import Path

from insar.calc_multilook_values import multilook, calculate_mean_look_values
from insar.project import ProcConfig
from insar.constant import SCENE_DATE_FMT
from insar.logs import STATUS_LOGGER
from insar.paths.stack import StackPaths
from insar.paths.slc import SlcPaths

from insar.workflow.luigi.utils import tdir, get_scenes, PathParameter
from insar.workflow.luigi.stack_setup import InitialSetup

class Multilook(luigi.Task):
    """
    Produces multilooked SLC given a specified rlks/alks for multilooking
    """

    slc = PathParameter()
    slc_par = PathParameter()
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()
    workdir = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{Path(str(self.slc)).stem}_ml_logs.out"
        )

    def run(self):
        multilook(
            self.workdir,
            Path(str(self.slc)),
            Path(str(self.slc_par)),
            int(str(self.rlks)),
            int(str(self.alks)),
        )

        with self.output().open("w") as f:
            f.write("")


@inherits(InitialSetup)
class CreateMultilook(luigi.Task):
    """
    Runs creation of multi-look image task for all scenes, for all polariastions.
    """

    multi_look = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_createmultilook_status_logs.out"
        )

    def requires(self):
        with open(self.proc_file, "r") as proc_fileobj:
            proc = ProcConfig.from_file(proc_fileobj)

        deps = []

        # Require S1 mosaic'd data if we have S1 sensor data
        if proc.sensor == "S1":
            from insar.workflow.luigi.mosaic import CreateSlcMosaic
            deps.append(CreateSlcMosaic(
                # We share identical params, so just forward them
                **common_params(self, CreateSlcMosaic)
            ))

        # Require RSAT2 frames if we have RSAT2 sensor data
        if proc.sensor == "RSAT2":
            from insar.workflow.luigi.rsat2 import CreateRSAT2SlcTasks
            deps.append(CreateRSAT2SlcTasks(
                # We share identical params, so just forward them
                **common_params(self, CreateRSAT2SlcTasks)
            ))

        # Require PALSAR frames if we have PALSAR sensor data
        if proc.sensor.startswith("PALSAR"):
            from insar.workflow.luigi.process_alos import CreateALOSSlcTasks
            deps.append(CreateALOSSlcTasks(
                # We share identical params, so just forward them
                **common_params(self, CreateALOSSlcTasks)
            ))

        return deps

    def run(self):
        outdir = Path(self.outdir)

        with open(self.proc_file, "r") as proc_fileobj:
            proc = ProcConfig.from_file(proc_fileobj)

        paths = StackPaths(proc)
        primary_pol = proc.polarisation

        log = STATUS_LOGGER.bind(multi_look=self.multi_look, primary_pol=primary_pol)
        log.info("Beginning multilook")

        # calculate the mean range and azimuth look values
        slc_frames = get_scenes(paths.acquisition_csv)
        slc_par_files = []

        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)

            for _pol in _pols:
                if _pol not in self.polarization:
                    log.info(f"Skipping non-primary polarisation {_pol} in multilook for {slc_scene}")
                    continue

                slc_paths = SlcPaths(proc, slc_scene, _pol)

                if not slc_paths.slc_par.exists():
                    raise FileNotFoundError(f"missing {slc_paths.slc_par} file")

                slc_par_files.append(slc_paths.slc_par)

        # range and azimuth looks are only computed from primary polarization
        rlks, alks, *_ = calculate_mean_look_values(
            [_par for _par in slc_par_files if primary_pol in _par.stem],
            int(str(self.multi_look)),
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

        log.info("Multilook complete")

        with self.output().open("w") as out_fid:
            out_fid.write("rlks:\t {}\n".format(str(rlks)))
            out_fid.write("alks:\t {}".format(str(alks)))

