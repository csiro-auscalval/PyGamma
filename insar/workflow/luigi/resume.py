from pathlib import Path
import os
import pandas as pd
import datetime
import luigi
import luigi.configuration

from insar.constant import SCENE_DATE_FMT, SlcFilenames, MliFilenames
from insar.coregister_slc import CoregisterSlc
from insar.process_ifg import validate_ifg_input_files, ProcessIfgException
from insar.project import ProcConfig, IfgFileNames, ARDWorkflow
from insar.logs import STATUS_LOGGER

from insar.workflow.luigi.utils import DateListParameter, PathParameter, read_primary_date, tdir, read_rlks_alks
from insar.workflow.luigi.stack_setup import DataDownload
from insar.workflow.luigi.mosaic import ProcessSlcMosaic
from insar.workflow.luigi.multilook import Multilook
from insar.workflow.luigi.coregistration import CreateGammaDem, CoregisterDemPrimary, get_coreg_kwargs
from insar.workflow.luigi.backscatter import CreateCoregisteredBackscatter
from insar.workflow.luigi.backscatter_nrt import CreateNRTBackscatter
from insar.workflow.luigi.interferogram import CreateProcessIFGs

from insar.workflow.luigi.s1 import ProcessSlc
from insar.workflow.luigi.rsat2 import ProcessRSAT2Slc
from insar.workflow.luigi.process_alos import ProcessALOSSlc

def _forward_kwargs(cls, kwargs):
    ids = cls.get_param_names()

    return {k:v for k,v in kwargs.items() if k in ids}


class ReprocessSingleSLC(luigi.Task):
    """
    This task reprocesses a single SLC scene (including multilook) from scratch.

    This task is completely self-sufficient, it will download it's own raw data.

    This task assumes it is re-processing a partially completed job, and as such
    assumes this task would only be used if SLC processing had succeeded earlier,
    thus assumes the existence of multilook status output containing rlks/alks.
    """

    proc_file = PathParameter()
    stack_id = luigi.Parameter()
    polarization = luigi.Parameter()

    burst_data_csv = PathParameter()

    poeorb_path = PathParameter()
    resorb_path = PathParameter()

    scene_date = luigi.Parameter()
    ref_primary_tab = PathParameter()

    outdir = PathParameter()
    workdir = PathParameter()

    resume_token = luigi.Parameter()

    def output_path(self):
        fname = f"{self.stack_id}_reprocess_{self.scene_date}_{self.polarization}_{self.resume_token}_status.out"
        return tdir(self.workdir) / fname

    def progress_path(self):
        return tdir(self.workdir) / self.output_path().with_suffix(".progress")

    def output(self):
        return luigi.LocalTarget(self.output_path())

    def progress(self):
        if not self.progress_path().exists():
            return None

        with self.progress_path().open() as file:
            return file.read().strip()

    def set_progress(self, value):
        with self.progress_path().open("w") as file:
            return file.write(value)

    def get_key_outputs(self):
        workdir = tdir(self.workdir)

        with open(self.proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        # Read rlks/alks from multilook status
        mlk_status = workdir / f"{self.stack_id}_createmultilook_status_logs.out"
        if not mlk_status.exists():
            raise ValueError(f"Failed to reprocess SLC, missing multilook status: {mlk_status}")

        rlks, alks = read_rlks_alks(mlk_status)

        pol = self.polarization.upper()

        slc_dir = Path(self.outdir) / proc_config.slc_dir / self.scene_date
        slc = slc_dir / SlcFilenames.SLC_FILENAME.value.format(self.scene_date, pol)
        slc_par = slc_dir / SlcFilenames.SLC_PAR_FILENAME.value.format(self.scene_date, pol)

        mli = slc_dir / MliFilenames.MLI_FILENAME.value.format(scene_date=self.scene_date, pol=pol, rlks=str(rlks))
        mli_par = slc_dir / MliFilenames.MLI_PAR_FILENAME.value.format(scene_date=self.scene_date, pol=pol, rlks=str(rlks))

        return [slc, slc_par, mli, mli_par]

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id, resume_token=self.resume_token)

        workdir = tdir(self.workdir)
        outdir = Path(self.outdir)

        with open(self.proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        raw_data_path = outdir / proc_config.raw_data_dir

        # Read rlks/alks from multilook status
        mlk_status = workdir / f"{self.stack_id}_createmultilook_status_logs.out"
        if not mlk_status.exists():
            raise ValueError(f"Failed to reprocess SLC, missing multilook status: {mlk_status}")

        rlks, alks = read_rlks_alks(mlk_status)

        # Read scenes CSV and schedule SLC download via URLs
        slc_inputs_df = pd.read_csv(self.burst_data_csv, index_col=0)

        os.makedirs(raw_data_path, exist_ok=True)

        download_list = slc_inputs_df.url.unique()
        download_tasks = []

        for slc_url in download_list:
            url_scene_date = Path(slc_url).name.split("_")[5].split("T")[0]

            if url_scene_date == self.scene_date:
                download_task = DataDownload(
                    data_path=slc_url.rstrip(),
                    polarization=[self.polarization],
                    poeorb_path=self.poeorb_path,
                    resorb_path=self.resorb_path,
                    workdir=self.workdir,
                    output_dir=raw_data_path / url_scene_date,
                )

                download_tasks.append(download_task)

        if self.progress() is None:
            self.set_progress("download_tasks")

            for download_task in download_tasks:
                # Force re-download, we clean raw data so the output status file is a lie...
                status_path = Path(download_task.output().path)
                if status_path.exists():
                    status_path.unlink()

            yield download_tasks

        for task in download_tasks:
            failed_file = Path(task.output().path).read_text().strip()
            if failed_file:
                Path(self.output().path).write_text(failed_file)
                return

        slc_dir = outdir / proc_config.slc_dir
        slc = slc_dir / self.scene_date / SlcFilenames.SLC_FILENAME.value.format(self.scene_date, self.polarization.upper())
        slc_par = slc_dir / self.scene_date / SlcFilenames.SLC_PAR_FILENAME.value.format(self.scene_date, self.polarization.upper())

        if proc_config.sensor == "S1":
            slc_task = ProcessSlc(
                scene_date=self.scene_date,
                raw_path=raw_data_path,
                polarization=self.polarization,
                burst_data=self.burst_data_csv,
                slc_dir=slc_dir,
                workdir=self.workdir,
                ref_primary_tab=self.ref_primary_tab,
            )

        if proc_config.sensor == "RSAT2":
            rs2_dirs = list((raw_data_path / self.scene_date).glob("RS2_*"))
            if not rs2_dirs:
                msg = f"Missing raw {self.polarization} data for {self.scene_date}!"
                log.error(msg)
                raise RuntimeError(msg)

            if len(rs2_dirs) > 1:
                msg = f"Skipping {self.scene_date} for {self.polarization} due to multiple data products\nRSAT2 mosaics not supported!"
                log.error(msg)
                raise RuntimeError(msg)

            slc_task = ProcessRSAT2Slc(
                scene_date=self.scene_date,
                raw_path=rs2_dirs[0],
                polarization=self.polarization,
                burst_data=self.burst_data_csv,
                slc_dir=slc_dir,
                workdir=self.workdir,
            )

        if proc_config.sensor.startswith("PALSAR"):
            alos1_acquisitions = list((raw_data_path / self.scene_date).glob("*/IMG-*-ALP*"))
            alos2_acquisitions = list((raw_data_path / self.scene_date).glob("*/IMG-*-ALOS*"))

            if not alos1_acquisitions and not alos2_acquisitions:
                msg = f"Missing raw {self.polarization} data for {self.scene_date}!"
                log.error(msg)
                raise RuntimeError(msg)

            if (len(alos1_acquisitions) + len(alos2_acquisitions)) > 1:
                msg = f"Skipping {self.scene_date} for {self.polarization} due to multiple data products\nALOS mosaics not supported!"
                log.error(msg)
                raise RuntimeError(msg)

            alos_dir = (alos1_acquisitions or alos2_acquisitions)[0].parent
            sensor = "PALSAR1" if alos1_acquisitions else "PALSAR2"

            slc_task = ProcessALOSSlc(
                proc_file=self.proc_file,
                scene_date=self.scene_date,
                raw_path=alos_dir,
                sensor=sensor,
                polarization=self.polarization,
                burst_data=self.burst_data_csv,
                slc_dir=slc_dir,
                workdir=self.workdir,
            )

        if self.progress() == "download_tasks":
            if slc_task.output().exists():
                slc_task.output().remove()

            self.set_progress("slc_task")
            yield slc_task

        failed_file = Path(task.output().path).read_text().strip()
        if failed_file:
            Path(self.output().path).write_text(failed_file)
            return

        if not slc.exists():
            raise ValueError(f'Critical failure reprocessing, SLC file not found: {slc}')

        if self.progress() == "slc_task":
            self.set_progress("mosaic_task")

            if proc_config.sensor == "S1":
                mosaic_task = ProcessSlcMosaic(
                    scene_date=self.scene_date,
                    raw_path=raw_data_path,
                    polarization=self.polarization,
                    burst_data=self.burst_data_csv,
                    slc_dir=slc_dir,
                    outdir=self.outdir,
                    workdir=self.workdir,
                    ref_primary_tab=self.ref_primary_tab,
                    rlks=rlks,
                    alks=alks,
                )

                if mosaic_task.output().exists():
                    mosaic_task.output().remove()

                yield mosaic_task

        if self.progress() == "mosaic_task":
            mli_task = Multilook(
                slc=slc,
                slc_par=slc_par,
                rlks=rlks,
                alks=alks,
                workdir=self.workdir,
            )

            if mli_task.output().exists():
                mli_task.output().remove()

            self.set_progress("mli_task")
            yield mli_task

        # Quick sanity check, we shouldn't get this far unless mli_task was scheduled
        if self.progress() != "mli_task":
            raise RuntimeError("Unexpected dynamic dependency error in ReprocessSingleSLC task")

        with self.output().open("w") as f:
            f.write("")


class TriggerResume(luigi.Task):
    """
    This job triggers resumption of processing for a specific stack over a date range
    """

    stack_id = luigi.Parameter()

    primary_scene = luigi.OptionalParameter(default=None)

    # Note: This task needs to take all the parameters the others do,
    # so we can re-create the other tasks for resuming
    proc_file = PathParameter()
    shape_file = PathParameter()
    source_data = luigi.ListParameter()
    burst_data_csv = PathParameter()
    include_dates = DateListParameter()
    exclude_dates = DateListParameter()
    sensor = luigi.OptionalParameter()
    polarization = luigi.ListParameter()
    cleanup = luigi.BoolParameter()
    outdir = PathParameter()
    workdir = PathParameter()
    orbit = luigi.Parameter()
    dem_img = PathParameter()
    multi_look = luigi.IntParameter()
    poeorb_path = PathParameter()
    resorb_path = PathParameter()

    reprocess_failed = luigi.BoolParameter()
    resume_token = luigi.Parameter()

    workflow = luigi.EnumParameter(
        enum=ARDWorkflow, default=ARDWorkflow.Interferogram
    )

    def output_path(self):
        return Path(f"{self.stack_id}_resume_pipeline_{self.resume_token}_status.out")

    def output(self):
        return luigi.LocalTarget(tdir(self.workdir) / self.output_path())

    def triggered_path(self):
        return tdir(self.workdir) / self.output_path().with_suffix(".triggered")

    def run(self):
        log = STATUS_LOGGER.bind(outdir=self.outdir, workdir=self.workdir)

        #kwargs = {k:v for k,v in self.get_params()}

        # Remove args that are just for this task
        #for arg in ["resume", "reprocess_failed", "resume_token"]:
        #    del kwargs[arg]

        # Note: The above doesn't work, and I'm not too sure why... so we're
        # manually re-creating kwargs just like the ARD task does...
        kwargs = {
            "proc_file": self.proc_file,
            "shape_file": self.shape_file,
            "include_dates": self.include_dates,
            "exclude_dates": self.exclude_dates,
            "source_data": self.source_data,
            "sensor": self.sensor,
            "polarization": self.polarization,
            "stack_id": self.stack_id,
            "outdir": self.outdir,
            "workdir": self.workdir,
            "orbit": self.orbit,
            "dem_img": self.dem_img,
            "poeorb_path": self.poeorb_path,
            "resorb_path": self.resorb_path,
            "multi_look": self.multi_look,
            "burst_data_csv": self.burst_data_csv,
            "cleanup": self.cleanup,
        }

        outdir = Path(self.outdir)

        # Load the gamma proc config file
        proc_path = Path(self.proc_file)
        with proc_path.open('r') as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        # Get appropriate task objects
        coreg_task = None
        ifgs_task = None

        if self.workflow == ARDWorkflow.BackscatterNRT:
            backscatter_task = CreateNRTBackscatter(**kwargs)
        else:
            backscatter_task = CreateCoregisteredBackscatter(**kwargs)
            coreg_task = backscatter_task.get_create_coreg_task()
            ifgs_task = CreateProcessIFGs(**kwargs)

        if self.workflow == ARDWorkflow.Interferogram:
            workflow_task = ifgs_task
        elif self.workflow == ARDWorkflow.Backscatter:
            workflow_task = backscatter_task
        elif self.workflow == ARDWorkflow.BackscatterNRT:
            workflow_task = backscatter_task
        else:
            raise Exception(f"Unsupported ARD workflow: {self.workflow}")

        # Note: the following logic does NOT detect/resume bad SLCs or DEM, it only handles
        # reprocessing of bad/missing coregs and IFGs currently.

        # Count number of completed products
        num_completed_coregs = len(list(tdir(self.workdir).glob("*_coreg_logs.out")))
        num_completed_ifgs = len(list(tdir(self.workdir).glob("*_ifg_*_status_logs.out")))

        log.info(
            f"TriggerResume of workflow {self.workflow} from {num_completed_coregs}x coreg and {num_completed_ifgs}x IFGs",
            num_completed_coregs=num_completed_coregs,
            num_completed_ifgs=num_completed_ifgs
        )

        # If we have no products, just resume the normal pipeline
        if num_completed_coregs == 0 and num_completed_ifgs == 0:
            log.info("No products need resuming, continuing w/ normal pipeline...")

            if coreg_task and coreg_task.output().exists():
                coreg_task.output().remove()

            if backscatter_task and backscatter_task.output().exists():
                backscatter_task.output().remove()

            if ifgs_task and ifgs_task.output().exists():
                ifgs_task.output().remove()

            self.triggered_path().touch()

        # Read rlks/alks
        ml_file = tdir(self.workdir) / f"{self.stack_id}_createmultilook_status_logs.out"
        if ml_file.exists():
            rlks, alks = read_rlks_alks(ml_file)

        # But if multilook hasn't been run, we never did IFGs/SLC coreg...
        # thus we should simply resume the normal pipeline.
        else:
            log.info("Multi-look never ran, continuing w/ normal pipeline...")
            self.triggered_path().touch()

        if not self.triggered_path().exists():
            prerequisite_tasks = []

            tfs = outdir.name
            log.info(f"Resuming {tfs}")

            # We need to verify the SLC inputs still exist for these IFGs... if not, reprocess
            reprocessed_single_slcs = []
            reprocessed_slc_coregs = []
            reprocessed_slc_backscatter = []

            if self.workflow == ARDWorkflow.Interferogram:
                # Trigger IFGs resume, this will tell us what pairs are being reprocessed
                reprocessed_ifgs = ifgs_task.trigger_resume(self.reprocess_failed)
                log.info("Re-processing IFGs", list=reprocessed_ifgs)

                for primary_date, secondary_date in reprocessed_ifgs:
                    ic = IfgFileNames(proc_config, primary_date, secondary_date, outdir)

                    # We re-use ifg's own input handling to detect this
                    try:
                        validate_ifg_input_files(ic)
                    except ProcessIfgException as e:
                        pol = proc_config.polarisation
                        status_out = f"{primary_date}_{pol}_{secondary_date}_{pol}_coreg_logs.out"
                        status_out = tdir(self.workdir) / status_out

                        log.info("Triggering SLC reprocessing as coregistrations missing", missing=e.missing_files)

                        if status_out.exists():
                            status_out.unlink()

                        # Note: We intentionally don't clean primary/secondary SLC dirs as they
                        # contain files besides coreg we don't want to remove. SLC coreg
                        # can be safely re-run over it's existing files deterministically.

                        reprocessed_slc_coregs.append(primary_date)
                        reprocessed_slc_coregs.append(secondary_date)

                        # Add tertiary scene (if any)
                        for slc_scene in [primary_date, secondary_date]:
                            # Re-use slc coreg task for parameter acquisition
                            coreg_kwargs = get_coreg_kwargs(proc_path, slc_scene, pol)
                            del coreg_kwargs["proc_file"]
                            del coreg_kwargs["outdir"]
                            del coreg_kwargs["workdir"]
                            list_idx = "-"

                            for list_file_path in (outdir / proc_config.list_dir).glob("secondaries*.list"):
                                list_file_idx = int(list_file_path.stem[11:])

                                with list_file_path.open('r') as file:
                                    list_dates = file.read().splitlines()

                                if slc_scene in list_dates:
                                    if list_file_idx > 1:
                                        list_idx = list_file_idx

                                    break

                            coreg_kwargs["list_idx"] = list_idx
                            tertiary_task = CoregisterSlc(proc=proc_config, **coreg_kwargs)
                            tertiary_date = tertiary_task.get_tertiary_coreg_scene()

                            if tertiary_date:
                                reprocessed_single_slcs.append(tertiary_date)

            # Finally trigger SLC coreg & backscatter resumption
            # given the scenes from the missing IFG pairs
            if coreg_task:
                triggered_slc_coregs = coreg_task.trigger_resume(reprocessed_slc_coregs, self.reprocess_failed)
                for primary_date, secondary_date in triggered_slc_coregs:
                    reprocessed_slc_coregs.append(secondary_date)

                    reprocessed_single_slcs.append(primary_date)
                    reprocessed_single_slcs.append(secondary_date)

            triggered_slc_backscatter = backscatter_task.trigger_resume(reprocessed_slc_coregs, self.reprocess_failed)
            for scene_date in triggered_slc_backscatter:
                reprocessed_slc_backscatter.append(scene_date)

            reprocessed_slc_coregs = set(reprocessed_slc_coregs)
            reprocessed_single_slcs = set(reprocessed_single_slcs) | reprocessed_slc_coregs | set(reprocessed_single_slcs)
            reprocessed_slc_backscatter = set(reprocessed_slc_backscatter) | reprocessed_single_slcs

            if len(reprocessed_single_slcs) > 0:
                # Unfortunately if we're missing SLC coregs, we may also need to reprocess the SLC
                #
                # Note: As the ARD task really only supports all-or-nothing for SLC processing,
                # the fact we have ifgs that need reprocessing implies we got well and truly past SLC
                # processing successfully in previous run(s) as the (ifgs list / sbas baseline can't
                # exist without having completed SLC processing...
                #
                # so we literally just need to reproduce the DEM+SLC files for coreg again.

                # Compute primary scene
                primary_scene = read_primary_date(outdir)

                # Trigger SLC processing for primary scene (for primary DEM coreg)
                reprocessed_single_slcs.add(primary_scene.strftime(SCENE_DATE_FMT))

                # Trigger SLC processing for other scenes (for SLC coreg)
                existing_single_slcs = set()

                for date in reprocessed_single_slcs:
                    slc_reprocess = ReprocessSingleSLC(
                        proc_file = self.proc_file,
                        stack_id = self.stack_id,
                        polarization = proc_config.polarisation,
                        burst_data_csv = self.burst_data_csv,
                        poeorb_path = self.poeorb_path,
                        resorb_path = self.resorb_path,
                        scene_date = date,
                        ref_primary_tab = None,  # FIXME: GH issue #200
                        outdir = self.outdir,
                        workdir = self.workdir,
                        # This is to prevent tasks from prior resumes from clashing with
                        # future resumes.
                        resume_token = self.resume_token
                    )

                    slc_files_exist = all([i.exists() for i in slc_reprocess.get_key_outputs()])

                    if slc_files_exist:
                        log.info(
                            f"SLC for {date} already processed",
                            files=slc_reprocess.get_key_outputs()
                        )
                        existing_single_slcs.add(date)
                        continue

                    prerequisite_tasks.append(slc_reprocess)

                reprocessed_single_slcs -= existing_single_slcs

                # Trigger DEM tasks if we're re-processing SLC coreg as well
                #
                # Note: We don't add this to pre-requisite tasks, it's implied by
                # CreateCoregisterSecondaries's @requires
                dem_task = CreateGammaDem(**_forward_kwargs(CreateGammaDem, kwargs))
                coreg_dem_task = CoregisterDemPrimary(**_forward_kwargs(CoregisterDemPrimary, kwargs))

                if dem_task.output().exists():
                    dem_task.output().remove()

                if coreg_dem_task.output().exists():
                    coreg_dem_task.output().remove()

            self.triggered_path().touch()
            log.info("Re-processing singular SLCs", list=reprocessed_single_slcs)
            log.info("Re-processing SLC coregistrations", list=reprocessed_slc_coregs)
            log.info("Re-processing SLC backscatter", list=reprocessed_slc_backscatter)

            # Yield pre-requisite tasks first
            if prerequisite_tasks:
                log.info("Issuing pre-requisite reprocessing tasks")
                yield prerequisite_tasks

        if not workflow_task.output().exists():
            # and then finally resume the normal processing pipeline
            log.info("Issuing resumption of standard pipeline tasks")
            yield workflow_task

        with self.output().open("w") as f:
            f.write("")
