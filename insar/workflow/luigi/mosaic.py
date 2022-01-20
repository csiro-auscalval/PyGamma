from pathlib import Path
import luigi
import luigi.configuration
import pandas as pd
from luigi.util import requires
import shutil

from insar.constant import SCENE_DATE_FMT
from insar.project import ProcConfig
from insar.calc_multilook_values import calculate_mean_look_values
from insar.paths.stack import StackPaths
from insar.paths.slc import SlcPaths

from insar.workflow.luigi.utils import tdir, get_scenes
from insar.workflow.luigi.s1 import CreateFullSlc, ProcessSlcMosaic

@requires(CreateFullSlc)
class CreateSlcMosaic(luigi.Task):
    """
    Runs the final mosaics for all scenes, for all polarisations.
    """

    multi_look = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_createslcmosaic_status_logs.out"
        )

    def run(self):
        outdir = Path(self.outdir)

        with open(self.proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        paths = StackPaths(proc_config)
        slc_dir = outdir / proc_config.slc_dir
        slc_frames = get_scenes(paths.acquisition_csv)

        # Get all VV par files and compute range and azimuth looks
        slc_par_files = []
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)

            for _pol in _pols:
                if _pol not in self.polarization or _pol.upper() != proc_config.polarisation:
                    continue

                slc_paths = SlcPaths(proc_config, slc_scene, _pol)

                if not slc_paths.slc_par.exists():
                    raise FileNotFoundError(f"missing {slc_paths.slc_par} file")

                slc_par_files.append(slc_paths.slc_par)

        # range and azimuth looks are only computed from VV polarization
        rlks, alks, *_ = calculate_mean_look_values(
            slc_par_files,
            int(str(self.multi_look)),
        )

        # first create slc for one complete frame which will be a reference frame
        # to resize the incomplete frames.
        resize_primary_tab = None
        resize_primary_scene = None
        resize_primary_pol = None
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)

            for _pol in _pols:
                if status_frame:
                    slc_paths = SlcPaths(proc_config, slc_scene, self.polarization)

                    resize_task = ProcessSlcMosaic(
                        scene_date=slc_scene,
                        raw_path=paths.acquisition_dir,
                        polarization=_pol,
                        burst_data=paths.acquisition_csv,
                        slc_dir=paths.slc_dir,
                        workdir=self.workdir,
                        rlks=rlks,
                        alks=alks
                    )
                    yield resize_task
                    resize_primary_tab = slc_paths.slc_tab
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
        # TODO implement a method to resize a stacks to new frames definition
        # TODO Generate a new reference frame using scene that has least number of missing burst
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
                    ProcessSlcMosaic(
                        scene_date=slc_scene,
                        raw_path=paths.acquisition_dir,
                        polarization=_pol,
                        burst_data=paths.acquisition_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                        ref_primary_tab=resize_primary_tab,
                        rlks=rlks,
                        alks=alks
                    )
                )
        yield slc_tasks

        # clean up raw data directory immediately (as it's tens of GB / the sooner we delete it the better)
        if self.cleanup and paths.acquisition_dir.exists():
            shutil.rmtree(paths.acquisition_dir)

        with self.output().open("w") as out_fid:
            out_fid.write("")
