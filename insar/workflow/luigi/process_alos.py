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
from insar.process_alos_slc import process_alos_slc

from insar.workflow.luigi.utils import tdir, get_scenes, PathParameter
from insar.workflow.luigi.stack_setup import InitialSetup

class ProcessALOSSlc(luigi.Task):
    """
    Produces an SLC product for a single date/polarisation of ALOS PALSAR data.
    """

    proc_file = PathParameter()

    raw_path = PathParameter()

    scene_date = luigi.Parameter()
    sensor = luigi.Parameter()
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
            sensor=self.sensor,
            polarization=self.polarization
        )
        log.info("Beginning SLC processing")

        with open(self.proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        scene_out_dir = Path(self.slc_dir) / str(self.scene_date)
        scene_out_dir.mkdir(parents=True, exist_ok=True)

        paths = SlcPaths(self.workdir, self.scene_date, self.polarization)

        process_alos_slc(
            proc_config,
            Path(self.raw_path),
            str(self.scene_date),
            str(self.sensor),
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
class CreateALOSSlcTasks(luigi.Task):
    """
    Runs the create full slc tasks
    """

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_create_alos_slc_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("Create ALOS SLC processing tasks")

        with open(self.proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        outdir = Path(self.outdir)
        slc_dir = outdir / proc_config.slc_dir
        raw_dir = outdir / proc_config.raw_data_dir
        os.makedirs(slc_dir, exist_ok=True)

        slc_frames = get_scenes(self.burst_data_csv)

        slc_tasks = []
        for _dt, status_frame, pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)
            raw_scene_dir = raw_dir / slc_scene

            for pol in pols:
                if pol not in self.polarization:
                    log.info(f"Skipping {pol} scene, only {pols} are enabled")
                    continue

                alos1_acquisitions = list(raw_scene_dir.glob("*/IMG-*-ALP*"))
                alos2_acquisitions = list(raw_scene_dir.glob("*/IMG-*-ALOS*"))

                if not alos1_acquisitions and not alos2_acquisitions:
                    log.error(f"Missing raw {pol} data for {slc_scene}!")
                    continue

                if (len(alos1_acquisitions) + len(alos2_acquisitions)) > 1:
                    log.error(f"Skipping {slc_scene} for {pol} due to multiple data products\nALOS mosaics not supported!")
                    continue

                alos_dir = (alos1_acquisitions or alos2_acquisitions)[0].parent
                sensor = "PALSAR1" if alos1_acquisitions else "PALSAR2"

                slc_tasks.append(
                    ProcessALOSSlc(
                        proc_file=self.proc_file,
                        scene_date=slc_scene,
                        raw_path=alos_dir,
                        sensor=sensor,
                        polarization=pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                    )
                )

        yield slc_tasks

        # Remove any failed scenes from upstream processing if SLC files fail processing
        slc_inputs_df = pd.read_csv(self.burst_data_csv, index_col=0)
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

        # rewrite the burst_data_csv with removed scenes
        if rewrite:
            log.info(
                f"re-writing the burst data csv files after removing failed slc scenes"
            )
            slc_inputs_df.to_csv(self.burst_data_csv)

        with self.output().open("w") as out_fid:
            out_fid.write("")
