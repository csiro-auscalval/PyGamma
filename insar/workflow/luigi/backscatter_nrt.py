from pathlib import Path
from typing import List
import luigi
import luigi.configuration
from luigi.util import requires
import structlog

from insar.constant import SCENE_DATE_FMT
from insar.project import ProcConfig
from insar.process_backscatter import generate_nrt_backscatter
from insar.logs import STATUS_LOGGER
from insar.paths.slc import SlcPaths
from insar.paths.stack import StackPaths

from insar.workflow.luigi.utils import PathParameter, tdir, load_settings, get_scenes, read_rlks_alks
from insar.workflow.luigi.dem import CreateGammaDem
from insar.workflow.luigi.multilook import CreateMultilook

class ProcessNRTBackscatter(luigi.Task):
    """
    Produces a quick radar backscatter product for an SLC.
    """

    proc_file = PathParameter()
    outdir = PathParameter()
    workdir = PathParameter()

    src_path = PathParameter()
    dst_stem = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir).joinpath(
                f"{Path(str(self.src_path)).stem}_nrt_nbr_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(
            slc=self.src_path,
        )

        try:
            structlog.threadlocal.clear_threadlocal()

            outdir = Path(self.outdir)
            slc_date, slc_pol = Path(self.src_path).stem.split('_')[:2]
            slc_date = slc_date.lstrip("r")

            structlog.threadlocal.bind_threadlocal(
                task="SLC backscatter (NRT)",
                slc_dir=outdir,
                slc_date=slc_date,
                slc_pol=slc_pol
            )

            proc_config, metadata = load_settings(Path(self.proc_file))
            stack_id = metadata["stack_id"]

            failed = False
            dem = outdir / proc_config.gamma_dem_dir / f"{stack_id}.dem"
            log.info("Beginning SLC backscatter (NRT)", dem=dem)

            generate_nrt_backscatter(
                Path(self.outdir),
                Path(self.src_path),
                dem,
                Path(self.dst_stem),
            )

            log.info("SLC backscatter (NRT) complete")
        except Exception as e:
            log.error("SLC backscatter (NRT) failed with exception", exc_info=True)
            failed = True
        finally:
            # We flag a task as complete no matter if the scene failed or not!
            # - however we do write if the scene failed, so it can be reprocessed
            # - later automatically if need be.
            with self.output().open("w") as f:
                f.write("FAILED" if failed else "")

            structlog.threadlocal.clear_threadlocal()


@requires(CreateGammaDem, CreateMultilook)
class CreateNRTBackscatter(luigi.Task):
    """
    Runs the backscatter tasks for all SLC scenes from their multi-looked
    images, not their coregistered/resampled images.
    """

    proc_file = PathParameter()
    polarization = luigi.ListParameter(default=None)

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir).joinpath(
                f"{self.stack_id}_nrt_nbr_status_logs.out"
            )
        )

    def trigger_resume(self, reprocess_dates: List[str], reprocess_failed_scenes: bool):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)

        # All we need to do is drop our outputs, as the backscatter
        # task can safely over-write itself...
        if self.output().exists():
            self.output().remove()

        # Remove completion status files for any failed SLC coreg tasks
        triggered_dates = []

        nbr_outfile_pattern = "*_nrt_nbr_logs.out"
        nbr_outfile_suffix_len = len(nbr_outfile_pattern)-1

        if reprocess_failed_scenes:
            for status_out in tdir(self.workdir).glob(nbr_outfile_pattern):
                mli = status_out.name[:-nbr_outfile_suffix_len] + ".mli"
                scene_date = mli.split("_")[0].lstrip("r")

                with status_out.open("r") as file:
                    contents = file.read().splitlines()

                if len(contents) > 0 and "FAILED" in contents[0]:
                    triggered_dates.append(scene_date)

                    log.info(f"Resuming SLC backscatter ({mli}) because of FAILED processing")
                    status_out.unlink()

        # Remove completion status files for any we're asked to
        for date in reprocess_dates:
            for status_out in tdir(self.workdir).glob(f"*{date}_" + nbr_outfile_pattern):
                mli = status_out.name[:-nbr_outfile_suffix_len] + ".mli"
                scene_date = mli.split("_")[0].lstrip("r")

                triggered_dates.append(scene_date)

                log.info(f"Resuming SLC backscatter ({mli}) because of dependency")
                status_out.unlink()

        return triggered_dates

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("Scheduling NRT backscatter tasks...")

        # Load the gamma proc config file
        proc_path = Path(self.proc_file)
        with proc_path.open("r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        paths = StackPaths(proc_config)

        slc_frames = get_scenes(paths.acquisition_csv)

        # get range and azimuth looked values
        ml_file = tdir(paths.job_dir) / f"{proc_config.stack_id}_createmultilook_status_logs.out"
        rlks, alks = read_rlks_alks(ml_file)

        kwargs = {
            "proc_file": proc_path,
            "outdir": paths.output_dir,
            "workdir": paths.job_dir,
        }

        jobs = []

        # Create backscatter tasks for all scenes
        for dt, _, pols in slc_frames:
            scene_date = dt.strftime(SCENE_DATE_FMT)

            for pol in pols:
                slc_paths = SlcPaths(proc_config, scene_date, pol, rlks)

                kwargs["src_path"] = slc_paths.mli
                kwargs["dst_stem"] = slc_paths.dir / f"nrt_{slc_paths.mli.stem}"

                task = ProcessNRTBackscatter(**kwargs)
                jobs.append(task)

        yield jobs

        with self.output().open("w") as f:
            f.write("")
