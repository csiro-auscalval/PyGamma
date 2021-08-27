import re
from pathlib import Path
import luigi
import luigi.configuration
from luigi.util import requires

from insar.process_ifg import run_workflow, get_ifg_width, TempFileConfig
from insar.project import ProcConfig, DEMFileNames, IfgFileNames
from insar.coreg_utils import read_land_center_coords
from insar.logs import STATUS_LOGGER

from insar.workflow.luigi.utils import tdir, mk_clean_dir
from insar.workflow.luigi.backscatter import CreateCoregisteredBackscatter


class ProcessIFG(luigi.Task):
    """
    Runs the interferogram processing tasks for primary polarisation.
    """

    proc_file = luigi.Parameter()
    shape_file = luigi.Parameter()
    stack_id = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()

    primary_date = luigi.Parameter()
    secondary_date = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_ifg_{self.primary_date}-{self.secondary_date}_status_logs.out"
        )

    def run(self):
        # Load the gamma proc config file
        with open(str(self.proc_file), 'r') as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        log = STATUS_LOGGER.bind(
            outdir=self.outdir,
            polarization=proc_config.polarisation,
            primary_date=self.primary_date,
            secondary_date=self.secondary_date
        )
        log.info("Beginning interferogram processing")

        # Run IFG processing in an exception handler that doesn't propagate exception into Luigi
        # This is to allow processing to fail without stopping the Luigi pipeline, and thus
        # allows as many scenes as possible to fully process even if some scenes fail.
        failed = False
        try:
            ic = IfgFileNames(proc_config, self.primary_date, self.secondary_date, self.outdir)
            dc = DEMFileNames(proc_config, self.outdir)
            tc = TempFileConfig(ic)

            # Run interferogram processing workflow w/ ifg width specified in r_primary_mli par file
            with open(Path(self.outdir) / ic.r_primary_mli_par, 'r') as fileobj:
                ifg_width = get_ifg_width(fileobj)

            # Read land center coordinates from shape file (if it exists)
            land_center = None
            if proc_config.land_center:
                land_center = proc_config.land_center
            elif self.shape_file:
                land_center = read_land_center_coords(Path(self.shape_file))

            # Make sure output IFG dir is clean/empty, in case
            # we're resuming an incomplete/partial job.
            mk_clean_dir(ic.ifg_dir)

            run_workflow(
                proc_config,
                ic,
                dc,
                tc,
                ifg_width,
                land_center=land_center)

            log.info("Interferogram complete")
        except Exception as e:
            log.error("Interferogram failed with exception", exc_info=True)
            failed = True
        finally:
            # We flag a task as complete no matter if the scene failed or not!
            with self.output().open("w") as f:
                f.write("FAILED" if failed else "")


@requires(CreateCoregisteredBackscatter)
class CreateProcessIFGs(luigi.Task):
    """
    Runs the interferogram processing tasks.
    """

    proc_file = luigi.Parameter()
    shape_file = luigi.Parameter()
    stack_id = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_create_ifgs_status_logs.out"
        )

    def trigger_resume(self, reprocess_failed_scenes=True):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)

        # Load the gamma proc config file
        with open(str(self.proc_file), 'r') as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        # Remove our output to re-trigger this job, which will trigger ProcessIFGs
        # for all date pairs, however only those missing IFG outputs will run.
        output = self.output()

        if output.exists():
            output.remove()

        # Remove completion status files for IFGs tasks that are missing outputs
        # - this is distinct from those that raised errors explicitly, to handle
        # - cases people have manually deleted outputs (accidentally or intentionally)
        # - and cases where jobs have been terminated mid processing.
        reprocess_pairs = []

        ifgs_list = Path(self.outdir) / proc_config.list_dir / proc_config.ifg_list
        if ifgs_list.exists():
            with open(ifgs_list) as ifg_list_file:
                ifgs_list = [dates.split(",") for dates in ifg_list_file.read().splitlines()]

            for primary_date, secondary_date in ifgs_list:
                ic = IfgFileNames(proc_config, primary_date, secondary_date, self.outdir)

                # Check for existence of filtered coh geocode files, if neither exist we need to re-run.
                ifg_filt_coh_geo_out = ic.ifg_dir / ic.ifg_filt_coh_geocode_out
                ifg_filt_coh_geo_out_tiff = ic.ifg_dir / ic.ifg_filt_coh_geocode_out_tiff

                if not ic.ifg_filt_coh_geocode_out.exists() and not ifg_filt_coh_geo_out_tiff.exists():
                    log.info(f"Resuming IFG ({primary_date},{secondary_date}) because of missing geocode outputs")
                    reprocess_pairs.append((primary_date, secondary_date))

        # Remove completion status files for any failed SLC coreg tasks.
        # This is probably slightly redundant, but we 'do' write FAILED to status outs
        # in the error handler, thus for cases this occurs but the above logic doesn't
        # apply, we have this as well just in case.
        if reprocess_failed_scenes:
            for status_out in tdir(self.workdir).glob("*_ifg_*_status_logs.out"):
                with status_out.open("r") as file:
                    contents = file.read().splitlines()

                if len(contents) > 0 and "FAILED" in contents[0]:
                    primary_date, secondary_date = re.split("[-_]", status_out.stem)[3:5]

                    log.info(f"Resuming IFG ({primary_date},{secondary_date}) because of FAILED processing")
                    reprocess_pairs.append((primary_date, secondary_date))

        reprocess_pairs = set(reprocess_pairs)

        # Any pairs that need reprocessing, we remove the status file of + clean the tree
        for primary_date, secondary_date in reprocess_pairs:
            status_file = self.workdir / f"{self.stack_id}_ifg_{primary_date}-{secondary_date}_status_logs.out"

            # Remove Luigi status file
            if status_file.exists():
                status_file.unlink()

        return reprocess_pairs

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("Process interferograms task")

        # Load the gamma proc config file
        with open(str(self.proc_file), 'r') as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        # Parse ifg_list to schedule jobs for each interferogram
        with open(Path(self.outdir) / proc_config.list_dir / proc_config.ifg_list) as ifg_list_file:
            ifgs_list = [dates.split(",") for dates in ifg_list_file.read().splitlines()]

        jobs = []
        for primary_date, secondary_date in ifgs_list:
            jobs.append(
                ProcessIFG(
                    proc_file=self.proc_file,
                    shape_file=self.shape_file,
                    stack_id=self.stack_id,
                    outdir=self.outdir,
                    workdir=self.workdir,
                    primary_date=primary_date,
                    secondary_date=secondary_date
                )
            )

        yield jobs

        with self.output().open("w") as f:
            f.write("")
