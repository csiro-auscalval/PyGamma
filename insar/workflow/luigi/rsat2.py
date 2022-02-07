import os
import re
from pathlib import Path
import luigi
import luigi.configuration
import pandas as pd
from luigi.util import requires

from insar.constant import SCENE_DATE_FMT
from insar.paths.slc import SlcPaths
from insar.project import ProcConfig
from insar.logs import STATUS_LOGGER
from insar.process_rsat2_slc import process_rsat2_slc
from insar.paths.stack import StackPaths

from insar.workflow.luigi.utils import tdir, get_scenes, PathParameter
from insar.workflow.luigi.stack_setup import InitialSetup

class ProcessRSAT2Slc(luigi.Task):
    """
    Produces an SLC product for a single date/polarisation of RSAT2 data.
    """

    raw_path = PathParameter()

    scene_date = luigi.Parameter()
    polarization = luigi.Parameter()

    burst_data = PathParameter()

    slc_dir = PathParameter()
    workdir = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.scene_date}_{self.polarization}_slc_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(sensor="RSAT2", scene_date=self.scene_date, polarisation=self.polarization)
        log.info("Beginning SLC processing")

        scene_out_dir = Path(self.slc_dir) / str(self.scene_date)
        scene_out_dir.mkdir(parents=True, exist_ok=True)

        paths = SlcPaths(self.workdir, self.scene_date, self.polarization)

        process_rsat2_slc(
            Path(self.raw_path),
            str(self.polarization),
            paths.slc
        )

        log.info("SLC processing complete")

        with self.output().open("w") as f:
            f.write("")


# TODO: Should we have a single "CreateSLCTasks" that supports all sensors instead?
# lots of duplicate code here and race condition working with local files to remove
# failed scenes if we ever decided to support multi-sensor stacks (currently we do not
# so this isn't a concern)
@requires(InitialSetup)
class CreateRSAT2SlcTasks(luigi.Task):
    """
    Runs the create full slc tasks
    """

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_creatersat2slc_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("Create RSAT2 SLC processing tasks")

        with open(self.proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        paths = StackPaths(proc_config)
        outdir = Path(self.outdir)
        slc_dir = outdir / proc_config.slc_dir
        raw_dir = outdir / proc_config.raw_data_dir
        os.makedirs(slc_dir, exist_ok=True)

        slc_frames = get_scenes(paths.acquisition_csv)

        slc_tasks = []
        for _dt, status_frame, pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)
            for pol in pols:
                if pol not in self.polarization:
                    log.info(f"Skipping {pol} scene, only {pols} are enabled")
                    continue

                rs2_dirs = list((raw_dir / slc_scene).glob("RS2_*"))
                if not rs2_dirs:
                    log.error(f"Missing raw {pol} data for {slc_scene}!")
                    continue

                if len(rs2_dirs) > 1:
                    log.error(f"Skipping {slc_scene} for {pol} due to multiple data products\nRSAT2 mosaics not supported!")
                    continue

                slc_tasks.append(
                    ProcessRSAT2Slc(
                        scene_date=slc_scene,
                        raw_path=rs2_dirs[0],
                        polarization=pol,
                        burst_data=paths.acquisition_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                    )
                )

        yield slc_tasks

        # Remove any failed scenes from upstream processing if SLC files fail processing
        slc_inputs_df = pd.read_csv(paths.acquisition_csv, index_col=0)
        rewrite = False

        for _slc_task in slc_tasks:
            with open(_slc_task.output().path) as fid:
                slc_date = fid.readline().rstrip()
                if re.match(r"^[0-9]{8}", slc_date):
                    slc_date = f"{slc_date[0:4]}-{slc_date[4:6]}-{slc_date[6:8]}"
                    log.info(
                        f"slc processing failed for scene for {slc_date}: removed from further processing"
                    )
                    indexes = slc_inputs_df[slc_inputs_df["date"] == slc_date].index
                    slc_inputs_df.drop(indexes, inplace=True)
                    rewrite = True

        # rewrite the csv with removed scenes
        if rewrite:
            log.info(
                f"re-writing the burst data csv files after removing failed slc scenes"
            )
            slc_inputs_df.to_csv(paths.acquisition_csv)

        with self.output().open("w") as out_fid:
            out_fid.write("")
