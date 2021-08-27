import luigi
import luigi.configuration
import datetime
import os
import os.path
from pathlib import Path

from insar.project import ProcConfig, ARDWorkflow
from insar.logs import STATUS_LOGGER

from insar.workflow.luigi.utils import DateListParameter

from insar.workflow.luigi.resume import TriggerResume
from insar.workflow.luigi.backscatter import CreateCoregisteredBackscatter
from insar.workflow.luigi.interferogram import CreateProcessIFGs
from insar.workflow.luigi.backscatter_nrt import CreateNRTBackscatter

class ARD(luigi.WrapperTask):
    """
    Runs the InSAR ARD pipeline using GAMMA software.

    -----------------------------------------------------------------------------
    minimum parameter required to run using default luigi Parameter set in luigi.cfg
    ------------------------------------------------------------------------------
    usage:{
        luigi --module process_gamma ARD
        --proc-file <path to the .proc config file>
        --shape-file <path to an ESRI shape file (.shp)>
        --start-date <start date of SLC acquisition>
        --end-date <end date of SLC acquisition>
        --workdir <base working directory where luigi logs will be stored>
        --outdir <output directory where processed data will be stored>
        --local-scheduler (use only local-scheduler)
        --workers <number of workers>
    }
    """

    # .proc config path (holds all settings except query)
    proc_file = luigi.Parameter()

    # Query params (to find source data for processing)
    shape_file = luigi.Parameter(default="")
    include_dates = DateListParameter(default=[])
    exclude_dates = DateListParameter(default=[])

    # Explicit source data (in addition to that found via DB query)
    source_data = luigi.ListParameter(default=[])

    # Overridable query params (can come from .proc, or task)
    stack_id = luigi.Parameter(default=None)
    sensor = luigi.Parameter(default=None)
    polarization = luigi.ListParameter(default=None)
    orbit = luigi.Parameter(default=None)

    # .proc overrides
    cleanup = luigi.BoolParameter(
        default=None, significant=False, parsing=luigi.BoolParameter.EXPLICIT_PARSING
    )
    outdir = luigi.Parameter(default=None)
    workdir = luigi.Parameter(default=None)
    database_path = luigi.Parameter(default=None)
    primary_dem_image = luigi.Parameter(default=None)
    multi_look = luigi.IntParameter(default=None)
    poeorb_path = luigi.Parameter(default=None)
    resorb_path = luigi.Parameter(default=None)
    workflow = luigi.EnumParameter(
        enum=ARDWorkflow, default=None
    )

    # Job resume triggers
    resume = luigi.BoolParameter()
    reprocess_failed = luigi.BoolParameter()

    def requires(self):
        log = STATUS_LOGGER.bind(shape_file=self.shape_file)

        pols = self.polarization

        with open(str(self.proc_file), "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        orbit = str(self.orbit or proc_config.orbit)[:1].upper()
        stack_id = str(self.stack_id or proc_config.stack_id)

        if not stack_id:
            raise Exception("Missing attribute: stack_id!")

        # Override input proc settings as required...
        # - map luigi params to compatible names

        self.output_path = Path(self.outdir).as_posix() if self.outdir else None
        self.job_path = Path(self.workdir).as_posix() if self.workdir else None

        override_params = [
            # Note: "sensor" is NOT over-written...
            # ARD sensor parameter (satellite selector, eg: S1A vs. S1B) is not
            # the same a .proc sensor (selects between constellations such as
            # Sentinel-1 vs. RADARSAT)
            # TODO: we probably want to rename these in the future... will need
            # a review w/ InSAR team on their preferred terminology soon.

            "stack_id",
            "multi_look",
            "cleanup",
            "output_path",
            "job_path",
            "database_path",
            "primary_dem_image",
            "poeorb_path",
            "resorb_path"
        ]

        for name in override_params:
            if hasattr(self, name) and getattr(self, name) is not None:
                override_value = getattr(self, name)
                log.info("Overriding .proc setting",
                    setting=name,
                    old_value=getattr(proc_config, name),
                    value=override_value
                )
                setattr(proc_config, name, override_value)

        # Explicitly handle workflow enum
        workflow = self.workflow
        if workflow:
            proc_config.workflow = str(workflow)

        else:
            matching_workflow = [name for name in ARDWorkflow if name.lower() == proc_config.workflow.lower()]
            if not matching_workflow:
                raise Exception(f"Failed to match .proc workflow {proc_config.workflow} to ARDWorkflow enum!")

            workflow = matching_workflow[0]

        if pols:
            # Note: proc_config only takes the primary polarisation
            # - this is the polarisation used for IFGs, not secondary.
            #
            # We assume first polarisation is the primary.
            proc_config.polarisation = pols[0]
        else:
            pols = [proc_config.polarisation or "VV"]

        # Infer key variables from it
        self.output_path = Path(proc_config.output_path)
        self.job_path = Path(proc_config.job_path)
        orbit = proc_config.orbit[:1].upper()
        proc_file = self.output_path / "config.proc"

        # Create dirs
        os.makedirs(self.output_path / proc_config.list_dir, exist_ok=True)
        os.makedirs(self.job_path, exist_ok=True)

        # If proc_file already exists (eg: because this is a resume), assert that
        # this job has identical settings to the last one, so we don't produce
        # inconsistent data.
        #
        # In this process we also re-inherit any auto/blank settings.
        # Note: This is only required due to the less than ideal design we
        # have where we have had to put a fair bit of logic into requires()
        # which is in fact called multiple times (even after InitialSetup!)

        if proc_file.exists():
            with proc_file.open("r") as proc_fileobj:
                existing_config = ProcConfig.from_file(proc_fileobj)

            assert(existing_config.__slots__ == proc_config.__slots__)

            conflicts = []
            for name in proc_config.__slots__:
                # special case for cleanup, which we allow to change
                if name == "cleanup":
                    continue

                new_val = getattr(proc_config, name)
                old_val = getattr(existing_config, name)

                # If there's no such new value or it's "auto", inherit old.
                no_new_val = new_val is None or not str(new_val)
                if no_new_val or str(new_val) == "auto":
                    setattr(proc_config, name, old_val)

                # Otherwise, ensure values match / haven't changed.
                elif str(new_val) != str(old_val):
                    conflicts.append((name, new_val, old_val))

            if conflicts:
                msg = f"New .proc settings do not match existing {proc_file}"
                error = Exception(msg)
                error.state = { "conflicts": conflicts }
                log.info(msg, **error.state)
                raise error

        # Finally save final config and
        with open(proc_file, "w") as proc_fileobj:
            proc_config.save(proc_fileobj)

        # generate (just once) a unique token for tasks that need to re-run
        if self.resume:
            if not hasattr(self, 'resume_token'):
                self.resume_token = datetime.datetime.now().strftime("%Y%m%d-%H%M")

        # Coregistration processing
        ard_tasks = []
        self.output_dirs = [self.output_path]

        kwargs = {
            "proc_file": proc_file,
            "shape_file": self.shape_file,
            "include_dates": self.include_dates,
            "exclude_dates": self.exclude_dates,
            "source_data": self.source_data,
            "sensor": self.sensor,
            "polarization": pols,
            "stack_id": stack_id,
            "outdir": self.output_path,
            "workdir": self.job_path,
            "orbit": orbit,
            "dem_img": proc_config.primary_dem_image,
            "poeorb_path": proc_config.poeorb_path,
            "resorb_path": proc_config.resorb_path,
            "multi_look": int(proc_config.multi_look),
            "burst_data_csv": self.output_path / f"{stack_id}_burst_data.csv",
            "cleanup": bool(proc_config.cleanup),
        }

        # Yield appropriate workflow
        if self.resume:
            ard_tasks.append(TriggerResume(resume_token=self.resume_token, reprocess_failed=self.reprocess_failed, workflow=workflow, **kwargs))
        elif workflow == ARDWorkflow.Backscatter:
            ard_tasks.append(CreateCoregisteredBackscatter(**kwargs))
        elif workflow == ARDWorkflow.Interferogram:
            ard_tasks.append(CreateProcessIFGs(**kwargs))
        elif workflow == ARDWorkflow.BackscatterNRT:
            ard_tasks.append(CreateNRTBackscatter(**kwargs))
        else:
            raise Exception(f'Unsupported workflow provided: {workflow}')

        yield ard_tasks

    def run(self):
        log = STATUS_LOGGER

        # Load final .proc config
        proc_file = self.output_path / "config.proc"
        with open(proc_file, "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        # Finally once all ARD pipeline dependencies are complete (eg: data processing is complete)
        # - we cleanup files that are no longer required as outputs.
        if not proc_config.cleanup:
            log.info("Cleanup of unused files skipped, all files being kept")
            return

        log.info("Cleaning up unused files")

        required_files = [
            # IFG files
            "INT/**/*_geo_unw.tif",
            "INT/**/*_flat_geo_coh.tif",
            "INT/**/*_flat_geo_int.tif",
            "INT/**/*_filt_geo_coh.tif",
            "INT/**/*_filt_geo_int.tif",
            "INT/**/*_base.par",
            "INT/**/*_bperp.par",
            "INT/**/*_geo_unw*.png",
            "INT/**/*_flat_geo_int.png",
            "INT/**/*_flat_int",

            # SLC files
            "SLC/**/r*rlks.mli",
            "SLC/**/r*rlks.mli.par",
            "SLC/**/r*.slc.par",
            "SLC/**/*sigma0*.tif",
            "SLC/**/*gamma0*.tif",
            "SLC/**/*sigma0*.png",
            "SLC/**/*gamma0*.png",
            "SLC/**/ACCURACY_WARNING",

            # DEM files
            "DEM/**/*rlks_geo_to_rdc.lt",
            "DEM/**/*_geo_dem.tif",
            "DEM/**/*_geo.dem.par",
            "DEM/**/diff_*rlks.par",
            "DEM/**/*_geo_lv_phi.tif",
            "DEM/**/*_geo_lv_theta.tif",
            "DEM/**/*_rdc.dem",
            "DEM/**/*lsmap*",

            # Keep all lists, metadata, and top level files
            "lists/*",
            "**/metadata*.json",
            "*"
        ]

        # Generate a list of required files we want to keep
        keep_files = []

        for outdir in self.output_dirs:
            for pattern in required_files:
                keep_files += outdir.glob(pattern)

        # Iterate every single output dir, and remove any file that's not required
        for outdir in self.output_dirs:
            for file in outdir.rglob("*"):
                if file.is_dir():
                    continue

                is_required = any([file.samefile(i) for i in keep_files])

                if not is_required:
                    log.info("Cleaning up file", file=file)
                    file.unlink()
                else:
                    log.info("Keeping required file", file=file)
