from pathlib import Path
from typing import Dict, List, Any
import luigi
import luigi.configuration
from luigi.util import requires
import structlog

from insar.constant import SCENE_DATE_FMT
from insar.coreg_utils import read_land_center_coords, create_secondary_coreg_tree
from insar.coregister_dem import CoregisterDem
# FIXME: insar.coregister_slc is mostly S1 specific, should be renamed as such
from insar.coregister_slc import CoregisterSlc
from insar.coregister_secondary import coregister_secondary, apply_coregistration
from insar.project import ProcConfig
from insar.paths.slc import SlcPaths
from insar.paths.stack import StackPaths
from insar.paths.dem import DEMPaths
from insar.paths.coregistration import CoregisteredPrimaryPaths

from insar.logs import STATUS_LOGGER

from insar.workflow.luigi.utils import read_primary_date, tdir, load_settings, read_rlks_alks, get_scenes, read_file_line, mk_clean_dir
from insar.workflow.luigi.utils import PathParameter
from insar.workflow.luigi.dem import CreateGammaDem
from insar.workflow.luigi.baseline import CalcInitialBaseline


def get_coreg_date_pairs(outdir: Path, proc_config: ProcConfig):
    list_dir = outdir / proc_config.list_dir
    primary_scene = read_primary_date(outdir).strftime(SCENE_DATE_FMT)

    pairs = []

    for secondaries_list in list_dir.glob("secondaries*.list"):
        list_index = int(secondaries_list.stem[11:])
        prev_list_idx = list_index - 1

        with secondaries_list.open("r") as file:
            list_date_strings = file.read().splitlines()

        # The first tier of the tree is always coregistered to primary ref date
        if list_index == 1:
            pairs += [(primary_scene, dt) for dt in list_date_strings]

        # All the rest coregister to the closest "end" date in the previous level of the tree
        else:
            for slc_scene in list_date_strings:
                if int(slc_scene) < int(proc_config.ref_primary_scene):
                    coreg_ref_scene = read_file_line(list_dir / f'secondaries{prev_list_idx}.list', 0)
                elif int(slc_scene) > int(proc_config.ref_primary_scene):
                    coreg_ref_scene = read_file_line(list_dir / f'secondaries{prev_list_idx}.list', -1)
                else:  # slc_scene == primary_scene
                    continue

            pairs.append((coreg_ref_scene, slc_scene))

    return pairs


def get_coreg_kwargs(proc_file: Path, scene_date=None, scene_pol=None):
    proc_config, metadata = load_settings(proc_file)
    outdir = Path(proc_config.output_path)

    stack_id = metadata["stack_id"]
    workdir = Path(proc_config.job_path)
    primary_scene = read_primary_date(outdir)

    # get range and azimuth looked values
    ml_file = tdir(workdir) / f"{stack_id}_createmultilook_status_logs.out"
    rlks, alks = read_rlks_alks(ml_file)

    primary_scene = primary_scene.strftime(SCENE_DATE_FMT)
    primary_pol = str(proc_config.polarisation).upper()

    primary_paths = SlcPaths(proc_config, primary_scene, primary_pol, rlks)
    dem_paths = DEMPaths(proc_config)
    coreg_paths = CoregisteredPrimaryPaths(proc_config)

    kwargs = {
        "proc_file": proc_file,
        "list_idx": "-",
        "slc_primary": primary_paths.slc,
        "range_looks": rlks,
        "azimuth_looks": alks,
        "ellip_pix_sigma0": dem_paths.ellip_pix_sigma0,
        "dem_pix_gamma0": dem_paths.dem_pix_gam,
        "r_dem_primary_mli": coreg_paths.r_dem_primary_mli,
        "rdc_dem": dem_paths.rdc_dem,
        "geo_dem_par": dem_paths.geo_dem_par,
        "dem_lt_fine": dem_paths.dem_lt_fine,
        "outdir": outdir,
        "workdir": workdir,
    }

    if scene_date:
        if not scene_pol:
            scene_pol = primary_pol

        secondary_paths = SlcPaths(proc_config, scene_date, scene_pol, rlks)

        kwargs["slc_secondary"] = secondary_paths.slc
        kwargs["secondary_mli"] = secondary_paths.mli

    return kwargs


@requires(CreateGammaDem, CalcInitialBaseline)
class CoregisterDemPrimary(luigi.Task):
    """
    Runs co-registration of DEM and primary scene
    """

    multi_look = luigi.IntParameter()
    primary_scene = luigi.OptionalParameter(default=None)

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_coregisterdemprimary_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        outdir = Path(self.outdir)
        failed = False

        try:
            # Load the gamma proc config file
            with open(self.proc_file, "r") as proc_fileobj:
                proc_config = ProcConfig.from_file(proc_fileobj)

            primary_scene = read_primary_date(outdir).strftime(SCENE_DATE_FMT)
            primary_pol = proc_config.polarisation

            structlog.threadlocal.clear_threadlocal()
            structlog.threadlocal.bind_threadlocal(
                task="DEM primary coregistration",
                scene_dir=self.outdir,
                scene_date=primary_scene,
                polarisation=primary_pol
            )

            log.info("Beginning DEM primary coregistration")

            # Read rlks/alks from multilook status
            ml_file = f"{self.stack_id}_createmultilook_status_logs.out"
            rlks, alks = read_rlks_alks(tdir(self.workdir) / ml_file)

            slc_paths = SlcPaths(proc_config, primary_scene, primary_pol, rlks)
            dem_paths = DEMPaths(proc_config)

            dem_outdir = outdir / proc_config.dem_dir
            mk_clean_dir(dem_outdir)

            # Read land center coordinates from shape file (if it exists)
            land_center = None
            if proc_config.land_center:
                land_center = proc_config.land_center
                log.info("Read land center from .proc config", land_center=land_center)
            elif self.shape_file:
                land_center = read_land_center_coords(Path(self.shape_file))
                log.info("Read land center from shapefile", land_center=land_center)

            coreg = CoregisterDem(
                rlks=rlks,
                alks=alks,
                dem=dem_paths.dem,
                slc=slc_paths.slc,
                dem_par=dem_paths.dem_par,
                slc_par=slc_paths.slc_par,
                multi_look=self.multi_look,
                land_center=land_center
            )

            coreg.main()

            log.info("DEM primary coregistration complete")
        except Exception as e:
            log.error("DEM primary coregistration failed with exception", exc_info=True)
            failed = True
        finally:
            with self.output().open("w") as f:
                f.write("FAILED" if failed else "")

            structlog.threadlocal.clear_threadlocal()


# This is just a wrapper class so coregister_secondary can act like
# coregister_slc / minimise code changes for review.  This should be
# temporary code, until coregister_slc is also refactored to functional
# style & we can unify the functional coreg API then.
#
# TODO: This will need revision when coregister_slc.py is refactored into
# process_ifg.py style functional code.
class CoregisterSecondaryProcessor:
    kwargs: Dict[str, Any]

    def __init__(self, **kwargs):
        self.kwargs = kwargs

        slc_secondary = self.kwargs["slc_secondary"]
        secondary_mli = self.kwargs["secondary_mli"]

        self.r_secondary_slc_path = slc_secondary.parent / f"r{slc_secondary.name}"
        self.r_secondary_mli_path = secondary_mli.parent / f"r{secondary_mli.name}"

    @property
    def secondary_off(self):
        return self.r_secondary_slc_path.with_suffix(".off")

    @property
    def secondary_lt(self):
        return self.r_secondary_slc_path.with_suffix(".lt")

    def main(self):
        coregister_secondary(
            self.kwargs["proc"],
            self.kwargs["slc_primary"],
            self.kwargs["r_dem_primary_mli"],
            self.kwargs["rdc_dem"],
            self.kwargs["slc_secondary"],
            self.kwargs["secondary_mli"],
            self.r_secondary_slc_path,
            self.r_secondary_mli_path,
            self.kwargs["range_looks"],
            self.kwargs["azimuth_looks"],
        )

    def apply_coregistration(self, secondary_off: Path, secondary_lt: Path):
        apply_coregistration(
            self.kwargs["slc_primary"],
            self.kwargs["r_dem_primary_mli"],
            self.kwargs["slc_secondary"],
            self.kwargs["secondary_mli"],
            self.r_secondary_slc_path,
            self.r_secondary_mli_path,
            secondary_lt,
            secondary_off,
            self.kwargs["range_looks"],
            self.kwargs["azimuth_looks"],
        )


class CoregisterSecondary(luigi.Task):
    """
    Runs the primary-secondary co-registration task, followed by backscatter.

    Optionally, just runs backscattter if provided with a coreg_offset and
    coreg_lut parameter to use.
    """

    proc_file = PathParameter()
    list_idx = luigi.Parameter()
    slc_primary = PathParameter()
    slc_secondary = PathParameter()
    secondary_mli = PathParameter()
    range_looks = luigi.IntParameter()
    azimuth_looks = luigi.IntParameter()
    ellip_pix_sigma0 = PathParameter()
    dem_pix_gamma0 = PathParameter()
    r_dem_primary_mli = PathParameter()
    rdc_dem = PathParameter()
    geo_dem_par = PathParameter()
    dem_lt_fine = PathParameter()
    outdir = PathParameter()
    workdir = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{Path(str(self.slc_primary)).stem}_{Path(str(self.slc_secondary)).stem}_coreg_logs.out"
        )

    def get_processor(self):
        proc_path = Path(self.proc_file)
        with proc_path.open("r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        secondary_date, secondary_pol = Path(self.slc_secondary).stem.split('_')
        kwargs = get_coreg_kwargs(proc_path, secondary_date, secondary_pol)

        # kwargs takes ProcConfig, not a path
        kwargs["proc"] = proc_config
        del kwargs["proc_file"]

        # Remove unused args
        del kwargs["outdir"]
        del kwargs["workdir"]

        # Sentinel-1 uses a special coregistration module
        if proc_config.sensor == "S1":
            # Note: This mess is temporary (will dissapear when we drop OOP / move to functional
            # - it'll take a primary/secondary date, pol, and multilooks and that's it...)
            return CoregisterSlc(
                proc_config,
                "-",
                kwargs["slc_primary"],
                kwargs["slc_secondary"],
                kwargs["range_looks"],
                kwargs["azimuth_looks"],
                kwargs["rdc_dem"],
            )

        return CoregisterSecondaryProcessor(**kwargs)

    def requires(self):
        proc_path = Path(self.proc_file)
        with proc_path.open("r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        primary_pol = proc_config.polarisation
        secondary_date, secondary_pol = Path(self.slc_secondary).stem.split('_')

        # Non-primary polarised products depend on polarised coregistration
        if secondary_pol != primary_pol:
            yield CoregisterSecondary(**get_coreg_kwargs(proc_path, secondary_date, primary_pol))

    def run(self):
        secondary_date, secondary_pol = Path(self.slc_secondary).stem.split('_')
        primary_date, primary_pol = Path(self.slc_primary).stem.split('_')

        is_secondary_pol = secondary_pol != primary_pol

        log = STATUS_LOGGER.bind(
            outdir=self.outdir,
            polarisation=secondary_pol,
            secondary_date=secondary_date,
            secondary_scene=self.slc_secondary,
            primary_date=primary_date,
            primary_scene=self.slc_primary
        )
        log.info("Beginning SLC coregistration")

        failed = False

        # Run SLC coreg in an exception handler that doesn't propagate exception into Luigi
        # This is to allow processing to fail without stopping the Luigi pipeline, and thus
        # allows as many scenes as possible to fully process even if some scenes fail.
        try:
            coreg_secondary = self.get_processor()

            # Full coregistration for primary pol
            if not is_secondary_pol:
                coreg_secondary.main()
            # But just application (of primary pol's coregistration LUTs) for secondary pol
            else:
                primary_task = get_coreg_kwargs(Path(self.proc_file), secondary_date, primary_pol)
                primary_task = CoregisterSecondary(**primary_task)
                processor = primary_task.get_processor()

                coreg_secondary.apply_coregistration(processor.ctx.paths.secondary_off, processor.ctx.paths.secondary_lt)

            log.info("SLC coregistration complete")
        except Exception as e:
            log.error("SLC coregistration failed with exception", exc_info=True)
            failed = True
        finally:
            # We flag a task as complete no matter if the scene failed or not!
            # - however we do write if the scene failed, so it can be reprocessed
            # - later automatically if need be.
            with self.output().open("w") as f:
                f.write("FAILED" if failed else "")


@requires(CoregisterDemPrimary)
class CreateCoregisterSecondaries(luigi.Task):
    """
    Runs the co-registration tasks.

    The first batch of tasks produced is the primary-secondary coregistration, followed
    up by each sub-tree of secondary-secondary coregistrations in the coregistration network.
    """

    proc_file = PathParameter()
    primary_scene = luigi.OptionalParameter(default=None)

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_coregister_secondarys_status_logs.out"
        )

    def trigger_resume(self, reprocess_dates: List[str], reprocess_failed_scenes: bool):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)

        # Remove our output to re-trigger this job, which will trigger CoregisterSecondary
        # for all dates, however only those missing outputs will run.
        output = self.output()

        if output.exists():
            output.remove()

        # Remove completion status files for any failed SLC coreg tasks
        triggered_pairs = []

        if reprocess_failed_scenes:
            for status_out in tdir(self.workdir).glob("*_coreg_logs.out"):
                with status_out.open("r") as file:
                    contents = file.read().splitlines()

                if len(contents) > 0 and "FAILED" in contents[0]:
                    parts = status_out.name.split("_")
                    primary_date, secondary_date = parts[0], parts[2]

                    triggered_pairs.append((primary_date, secondary_date))

                    log.info(f"Resuming SLC coregistration ({primary_date}, {secondary_date}) because of FAILED processing")
                    status_out.unlink()

        # Remove completion status files for any we're asked to
        for date in reprocess_dates:
            for status_out in tdir(self.workdir).glob(f"*_*_{date}_*_coreg_logs.out"):
                parts = status_out.name.split("_")
                primary_date, secondary_date = parts[0], parts[2]

                triggered_pairs.append((primary_date, secondary_date))

                log.info(f"Resuming SLC coregistration ({primary_date}, {secondary_date}) because of dependency")
                status_out.unlink()

        return triggered_pairs

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("co-register primary-secondaries task")

        outdir = Path(self.outdir)

        # Load the gamma proc config file
        proc_path = Path(self.proc_file)
        with proc_path.open("r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        paths = StackPaths(proc_config)

        slc_frames = get_scenes(paths.acquisition_csv)

        primary_scene = read_primary_date(outdir)
        primary_pol = proc_config.polarisation

        coreg_tree = create_secondary_coreg_tree(
            primary_scene, [dt for dt, _, _ in slc_frames]
        )

        primary_polarizations = [
            pols for dt, _, pols in slc_frames if dt.date() == primary_scene
        ]
        assert len(primary_polarizations) == 1

        if primary_pol not in primary_polarizations[0]:
            raise ValueError(
                f"{primary_pol} not available in SLC data for {primary_scene}"
            )

        # get range and azimuth looked values
        ml_file = tdir(self.workdir) / f"{self.stack_id}_createmultilook_status_logs.out"
        rlks, alks = read_rlks_alks(ml_file)

        primary_scene = primary_scene.strftime(SCENE_DATE_FMT)

        kwargs = get_coreg_kwargs(proc_path)

        secondary_coreg_jobs = []

        for list_index, list_dates in enumerate(coreg_tree):
            list_index += 1  # list index is 1-based
            list_frames = [i for i in slc_frames if i[0].date() in list_dates]

            # Write list file
            list_file_path = outdir / proc_config.list_dir / f"secondaries{list_index}.list"
            if not list_file_path.parent.exists():
                list_file_path.parent.mkdir(parents=True)

            with open(list_file_path, "w") as listfile:
                list_date_strings = [
                    dt.strftime(SCENE_DATE_FMT) for dt, _, _ in list_frames
                ]
                listfile.write("\n".join(list_date_strings))

            # Bash passes '-' for secondaries1.list, and list_index there after.
            if list_index > 1:
                kwargs["list_idx"] = list_index

            for _dt, _, _pols in list_frames:
                slc_scene = _dt.strftime(SCENE_DATE_FMT)
                if slc_scene == primary_scene:
                    continue

                if primary_pol not in _pols:
                    log.warning(
                        f"Skipping SLC coregistration due to missing primary polarisation data for that date",
                        primary_pol=primary_pol,
                        pols=_pols,
                        slc_scene=slc_scene
                    )
                    continue

                # Process coreg for all polarisations, the secondary polarisations will
                # simply apply primary LUTs to secondary products.
                for pol in _pols:
                    slc_paths = SlcPaths(proc_config, slc_scene, pol, rlks)

                    kwargs["slc_secondary"] = slc_paths.slc
                    kwargs["secondary_mli"] = slc_paths.mli

                    secondary_coreg_jobs.append(CoregisterSecondary(**kwargs))

        yield secondary_coreg_jobs

        with self.output().open("w") as f:
            f.write("")
