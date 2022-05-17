import os
import re
from pathlib import Path

from insar.logs import STATUS_LOGGER
from insar.project import ProcConfig
from insar.paths.slc import SlcPaths
from insar.paths.stack import StackPaths
from insar.constant import SCENE_DATE_FMT

from insar.process_tsx_slc import process_tsx_slc
from insar.workflow.luigi.stack_setup import InitialSetup
from insar.workflow.luigi.utils import tdir, get_scenes, PathParameter

import luigi
from luigi.util import requires
import pandas as pd


class ProcessTSXSlc(luigi.Task):
    """
    Produces an SLC product for a single date/polarisation of TSX/TDX data.
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
        log = STATUS_LOGGER.bind(
            scene_date=self.scene_date,
            polarisation=self.polarization
        )

        scene_out_dir = Path(self.slc_dir) / str(self.scene_date)
        scene_out_dir.mkdir(parents=True, exist_ok=True)
        raw_path = Path(str(self.raw_path))
        paths = SlcPaths(self.workdir, self.scene_date, self.polarization)

        log.info("Beginning TSX SLC processing", raw_path=raw_path, scene_out_dir=scene_out_dir)

        process_tsx_slc(
            raw_path,  # NB: needs to be extracted scene_date / long TSX dir
            self.polarization,
            paths.slc
        )

        log.info("TSX SLC processing complete")

        with self.output().open("w") as f:
            f.write("")


# TODO: Should we have a single "CreateSLCTasks" that supports all sensors instead?
# lots of duplicate code here and race condition working with local files to remove
# failed scenes if we ever decided to support multi-sensor stacks (currently we do not
# so this isn't a concern)
@requires(InitialSetup)
class CreateTSXSlcTasks(luigi.Task):
    """
    Creates Luigi tasks required to process TSX/TDX data.
    """

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_create_tsx_slc_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("Create TSX/TDX SLC processing tasks")

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

                raw_data_dir = raw_dir / slc_scene / slc_scene  # NB: double scene date dir
                tsx_dirs = list(raw_data_dir.glob("T[DS]X*"))

                if not tsx_dirs:
                    msg = f"Missing raw data for {slc_scene}!"
                    log.error(msg, outdir=outdir, slc_dir=slc_dir, raw_dir=raw_dir, tsx_dirs=tsx_dirs)
                    raise RuntimeError(msg)

                # NB: it is assumed that only 1 scene dir exists for each date
                if len(tsx_dirs) > 1:
                    log.error(f"2+ scene dirs found for {slc_scene}")
                    continue

                slc_tasks.append(
                    ProcessTSXSlc(
                        scene_date=slc_scene,
                        raw_path=tsx_dirs[0],
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
