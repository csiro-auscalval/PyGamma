import itertools
import luigi
from luigi.util import common_params
import luigi.configuration
import datetime
import os
import os.path
from pathlib import Path

from insar.project import ProcConfig, ARDWorkflow
from insar.logs import STATUS_LOGGER

from insar.stack import load_stack_config, load_stack_scenes, resolve_stack_scene_query, load_stack_scene_dates

from insar.workflow.luigi.stack_setup import InitialSetup
from insar.workflow.luigi.resume import TriggerResume
from insar.workflow.luigi.backscatter import CreateCoregisteredBackscatter
from insar.workflow.luigi.interferogram import CreateProcessIFGs
from insar.workflow.luigi.backscatter_nrt import CreateNRTBackscatter
from insar.workflow.luigi.append import AppendDatesToStack
from insar.workflow.luigi.utils import DateListParameter, PathParameter, simplify_dates, one_day

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
    proc_file = PathParameter()

    # Query params (to find source data for processing)
    shape_file = PathParameter(default=None)
    include_dates = DateListParameter(default=[])
    exclude_dates = DateListParameter(default=[])

    # Explicit source data (in addition to that found via DB query)
    source_data = luigi.ListParameter(default=[])

    # Stack modification params
    append = luigi.BoolParameter(default=False)

    # Overridable query params (can come from .proc, or task)
    stack_id = luigi.OptionalParameter(default=None)
    sensor = luigi.OptionalParameter(default=None)
    polarization = luigi.ListParameter(default=None)
    orbit = luigi.OptionalParameter(default=None)

    # .proc overrides
    cleanup = luigi.BoolParameter(
        default=None, significant=False, parsing=luigi.BoolParameter.EXPLICIT_PARSING
    )
    outdir = PathParameter(default=None)
    workdir = PathParameter(default=None)
    database_path = PathParameter(default=None)
    primary_dem_image = PathParameter(default=None)
    multi_look = luigi.IntParameter(default=None)
    poeorb_path = luigi.OptionalParameter(default=None)
    resorb_path = luigi.OptionalParameter(default=None)
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
            # - this is the polarisation used for IFGs (not secondary pols).
            #
            # We assume first polarisation is the primary.
            proc_config.polarisation = pols[0]
        else:
            pols = [proc_config.polarisation or "VV"]

        # Infer key variables from the config
        self.output_path = Path(proc_config.output_path)
        self.job_path = Path(proc_config.job_path)
        orbit = proc_config.orbit[:1].upper()
        proc_file = self.output_path / "config.proc"
        existing_stack = False
        append = bool(self.append)

        # Check if this stack already exists (eg: has a config.proc and scenes.list)
        if proc_file.exists():
            existing_config = load_stack_config(proc_file)

            # Determine what scenes have already been added to the stack
            # - this is from prior include date queries + explicit source data
            existing_scenes = load_stack_scenes(existing_config)
            existing_stack = bool(existing_scenes)

        # If the stack DOES already exist...
        if existing_stack:
            # Determine what scenes we're now asking to be in the stack...
            include_date_spec = [(d.date_a, d.date_b + one_day) for d in self.include_dates or []]
            exclude_date_spec = [(d.date_a, d.date_b + one_day) for d in self.exclude_dates or []]

            new_scenes_query = sorted(simplify_dates(include_date_spec, exclude_date_spec))
            new_scenes, _ = resolve_stack_scene_query(
                existing_config,
                new_scenes_query + list(self.source_data),
                [proc_config.sensor],
                self.orbit,
                pols,
                [self.sensor],
                Path(self.shape_file) if self.shape_file else None
            )

            # Note: We're actually throwing away information here, by assuming existing dates never get
            # retrospectively updated (eg: database might get an update w/ no-longer-missing/un-corrupted data)
            new_append_idx = len(load_stack_scene_dates(proc_config))
            existing_urls = set(itertools.chain(*[urls for _, urls in existing_scenes]))
            new_urls = set(itertools.chain(*[urls for _, urls in new_scenes]))

            # Check if the specified dates are DIFFERENT from the existing stack
            added_urls = new_urls - existing_urls
            removed_urls = existing_urls - (new_urls - added_urls)
            urls_differ = bool(added_urls or removed_urls)

            if removed_urls:
                # This is not currently a use case we require (thus do not support)
                # - supporting it gets complicated (makes the whole stack mutable)
                # - our current approach is append-only and much simpler as a result.
                raise RuntimeError("Can not remove dates from a stack")

            if append:
                append = added_urls

                # If we were supposed to be appending data, but there's in fact no new
                # data to append (eg: the stack already had it all) - early exit... no-op
                if not append:
                    log.info("No new data to append to stack, processing already completed.")
                    return

                if not hasattr(self, 'append_idx'):
                    # existing_scenes = original scenes.list + all the appended scenesN.list
                    # where N is 1 base for all appends, eg: scenes1.list is the first append
                    # thus... the current 'N' we're creating the baseline for is simple len()
                    self.append_idx = new_append_idx

            elif self.resume:
                # Note: resume works w/ dates, not data... resume could occur due to source data
                # corruption being fixed (which means source data may indeed be removed / replaced
                # with a new data file for the same date).
                existing_dates = set([date for date, _ in existing_scenes])
                new_dates = set([date for date, _ in new_scenes])

                added_dates = new_dates - existing_dates
                removed_dates = existing_dates - (new_dates - added_dates)

                # Resume could 'add' dates that were removed, but must never remove anything.
                if removed_dates:
                    raise RuntimeError("Provided dates do not match existing stack's dates with no --append specified")

            elif urls_differ:
                raise RuntimeError("Provided source data does not match existing stack's data with no --append specified")

            log.info(
                "Updating existing stack",
                new_query=new_scenes_query,
                new_source_data=self.source_data,
                adding_data=added_urls,
                removing_data=removed_urls,
                append=bool(append),
                resume=bool(self.resume)
            )

        # If proc_file already exists (eg: because this is an append or resume),
        # assert that this job has identical settings to the last one, so we don't
        # produce inconsistent data.
        #
        # In this process we also re-inherit any auto/blank settings.
        # Note: This is only required due to the less than ideal design we
        # have where we have had to put a fair bit of logic into requires()
        # which is in fact called multiple times (even after InitialSetup!)
        if proc_file.exists():
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

        # Create dirs
        os.makedirs(self.output_path / proc_config.list_dir, exist_ok=True)
        os.makedirs(self.job_path, exist_ok=True)

        # Save final config w/ any newly supplied or inferred settings.
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
            "multi_look": int(proc_config.multi_look),
            "cleanup": bool(proc_config.cleanup),
        }

        # Need to make an instance of anything that can hold all of kwargs, for common param
        # calculations via luigi's util function
        temp = CreateProcessIFGs(**kwargs)

        # Yield stack setup first (so we can determine if there is any data to process at all)
        yield InitialSetup(**common_params(temp, InitialSetup))

        # Check if any input even exists (and skip yielding workflow if not)
        scenes_list = self.output_path / proc_config.list_dir / "scenes.list"
        if not scenes_list.exists() or not scenes_list.read_text().strip():
            log.info("Stack processing aborted, no scenes provided or match query.")
            return

        # Yield appropriate workflow
        if self.resume:
            ard_tasks.append(TriggerResume(resume_token=self.resume_token, reprocess_failed=self.reprocess_failed, workflow=workflow, **kwargs))
        elif append:
            ard_tasks.append(AppendDatesToStack(
                append_idx=self.append_idx,
                append_scenes=[str(i) for i in append],
                workflow=workflow,
                **common_params(temp, AppendDatesToStack)
            ))
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
