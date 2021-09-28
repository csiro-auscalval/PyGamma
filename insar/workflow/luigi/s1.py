import os
import re
from pathlib import Path
import luigi
import luigi.configuration
import pandas as pd
from luigi.util import requires

from insar.constant import SCENE_DATE_FMT
from insar.project import ProcConfig
from insar.logs import STATUS_LOGGER
from insar.process_s1_slc import SlcProcess

from insar.workflow.luigi.utils import tdir, get_scenes, PathParameter
from insar.workflow.luigi.stack_setup import InitialSetup

class ProcessSlc(luigi.Task):
    """
    Runs single slc processing task for a single polarisation.
    """

    scene_date = luigi.Parameter()
    raw_path = PathParameter()
    polarization = luigi.Parameter()
    burst_data = PathParameter()
    slc_dir = PathParameter()
    workdir = PathParameter()
    ref_primary_tab = PathParameter(default=None)

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.scene_date}_{self.polarization}_slc_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(scene_date=self.scene_date, polarization=self.polarization)
        log.info("Beginning SLC processing")

        (Path(self.slc_dir) / str(self.scene_date)).mkdir(parents=True, exist_ok=True)

        slc_job = SlcProcess(
            str(self.raw_path),
            str(self.slc_dir),
            str(self.polarization),
            str(self.scene_date),
            str(self.burst_data),
            self.ref_primary_tab,
        )

        slc_job.main()

        log.info("SLC processing complete")

        with self.output().open("w") as f:
            f.write("")


@requires(InitialSetup)
class CreateFullSlc(luigi.Task):
    """
    Runs the create full slc tasks
    """

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_createfullslc_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("create full slc task")

        with open(self.proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        outdir = Path(self.outdir)
        slc_dir = outdir / proc_config.slc_dir
        os.makedirs(slc_dir, exist_ok=True)

        slc_frames = get_scenes(self.burst_data_csv)

        # first create slc for one complete frame which will be a reference frame
        # to resize the incomplete frames.
        resize_primary_tab = None
        resize_primary_scene = None
        resize_primary_pol = None
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)
            for _pol in _pols:
                if status_frame:
                    resize_task = ProcessSlc(
                        scene_date=slc_scene,
                        raw_path=outdir / proc_config.raw_data_dir,
                        polarization=_pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                    )
                    yield resize_task
                    resize_primary_tab = slc_dir / slc_scene / f"{slc_scene}_{_pol.upper()}_tab"
                    break
            if resize_primary_tab is not None:
                if resize_primary_tab.exists():
                    resize_primary_scene = slc_scene
                    resize_primary_pol = _pol
                    break

        # need at least one complete frame to enable further processing of the stacks
        # The frame definition were generated using all sentinel-1 acquisition dataset, thus
        # only processing a temporal subset might encounter stacks with all scene's frame
        # not forming a complete primary frame.
        # TODO: Generate a new reference frame using scene that has least number of bursts
        # (as we can't subset smaller scenes to larger)
        if resize_primary_tab is None:
            raise ValueError(
                f"Failed to find a single 'complete' scene to use as a subsetting reference for stack: {self.stack_id}"
            )

        slc_tasks = []
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)
            for _pol in _pols:
                if _pol not in self.polarization:
                    continue
                if slc_scene == resize_primary_scene and _pol == resize_primary_pol:
                    continue
                slc_tasks.append(
                    ProcessSlc(
                        scene_date=slc_scene,
                        raw_path=outdir / proc_config.raw_data_dir,
                        polarization=_pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                        ref_primary_tab=resize_primary_tab,
                    )
                )
        yield slc_tasks

        # Remove any failed scenes from upstream processing if SLC files fail processing
        slc_inputs_df = pd.read_csv(self.burst_data_csv)
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


class ProcessSlcMosaic(luigi.Task):
    """
    This task runs the final SLC mosaic step using the mean rlks/alks values for
    a single polarisation.
    """

    scene_date = luigi.Parameter()
    raw_path = PathParameter()
    polarization = luigi.Parameter()
    burst_data = PathParameter()
    slc_dir = PathParameter()
    outdir = PathParameter()
    workdir = PathParameter()
    ref_primary_tab = PathParameter(default=None)
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.scene_date}_{self.polarization}_slc_subset_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(scene_date=self.scene_date, polarization=self.polarization)
        log.info("Beginning SLC mosaic")

        slc_job = SlcProcess(
            str(self.raw_path),
            str(self.slc_dir),
            str(self.polarization),
            str(self.scene_date),
            str(self.burst_data),
            self.ref_primary_tab,
        )

        slc_job.main_mosaic(int(self.rlks), int(self.alks))

        log.info("SLC mosaic complete")

        with self.output().open("w") as f:
            f.write("")


