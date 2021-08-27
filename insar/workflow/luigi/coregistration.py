import datetime
from pathlib import Path
from typing import Dict, List, Any
import luigi
import luigi.configuration
from luigi.util import requires
import structlog

from insar.constant import SCENE_DATE_FMT
from insar.coreg_utils import read_land_center_coords
from insar.coregister_dem import CoregisterDem
# FIXME: insar.coregister_slc is mostly S1 specific, should be renamed as such
from insar.coregister_slc import CoregisterSlc
from insar.coregister_secondary import coregister_secondary, apply_coregistration
from insar.project import ProcConfig

from insar.logs import STATUS_LOGGER

from insar.workflow.luigi.utils import read_primary_date, tdir, load_settings, read_rlks_alks, get_scenes, read_file_line, mk_clean_dir
from insar.workflow.luigi.dem import CreateGammaDem
from insar.workflow.luigi.baseline import CalcInitialBaseline

# TBD: This doesn't have a .proc setting for some reason
__DEM_GAMMA__ = "GAMMA_DEM"

_LOG = structlog.get_logger("insar")

def find_scenes_in_range(
    primary_dt, date_list, thres_days: int, include_closest: bool = True
):
    """
    Creates a list of frame dates that within range of a primary date.

    :param primary_dt:
        The primary date in which we are searching for scenes relative to.
    :param date_list:
        The list which we're searching for dates in.
    :param thres_days:
        The number of days threshold in which scenes must be within relative to
        the primary date.
    :param include_closest:
        When true - if there exist slc frames on either side of the primary date, which are NOT
        within the threshold window then the closest date from each side will be
        used instead of no scene at all.
    """

    # We do everything with datetime.date's (can't mix and match date vs. datetime)
    if isinstance(primary_dt, datetime.datetime):
        primary_dt = primary_dt.date()
    elif not isinstance(primary_dt, datetime.date):
        primary_dt = datetime.date(primary_dt)

    thresh_dt = datetime.timedelta(days=thres_days)
    tree_lhs = []  # This was the 'lower' side in the bash...
    tree_rhs = []  # This was the 'upper' side in the bash...
    closest_lhs = None
    closest_rhs = None
    closest_lhs_diff = None
    closest_rhs_diff = None

    for dt in date_list:
        if isinstance(dt, datetime.datetime):
            dt = dt.date()
        elif not isinstance(primary_dt, datetime.date):
            dt = datetime.date(dt)

        dt_diff = dt - primary_dt

        # Skip scenes that match the primary date
        if dt_diff.days == 0:
            continue

        # Record closest scene
        if dt_diff < datetime.timedelta(0):
            is_closer = closest_lhs is None or dt_diff > closest_lhs_diff
            closest_lhs = dt if is_closer else closest_lhs
            closest_lhs_diff = dt_diff
        else:
            is_closer = closest_rhs is None or dt_diff < closest_rhs_diff
            closest_rhs = dt if is_closer else closest_rhs
            closest_rhs_diff = dt_diff

        # Skip scenes outside threshold window
        if abs(dt_diff) > thresh_dt:
            continue

        if dt_diff < datetime.timedelta(0):
            tree_lhs.append(dt)
        else:
            tree_rhs.append(dt)

    # Use closest scene if none are in threshold window
    if include_closest:
        if len(tree_lhs) == 0 and closest_lhs is not None:
            _LOG.info(
                f"Date difference to closest secondary greater than {thres_days} days, using closest secondary only: {closest_lhs}"
            )
            tree_lhs = [closest_lhs]

        if len(tree_rhs) == 0 and closest_rhs is not None:
            _LOG.info(
                f"Date difference to closest secondary greater than {thres_days} days, using closest secondary only: {closest_rhs}"
            )
            tree_rhs = [closest_rhs]

    return tree_lhs, tree_rhs


def create_secondary_coreg_tree(primary_dt, date_list, thres_days=63):
    """
    Creates a set of co-registration lists containing subsets of the prior set, to create a tree-like co-registration structure.

    Notes from the bash on :thres_days: parameter:
        #thres_days=93 # three months, S1A/B repeats 84, 90, 96, ... (90 still ok, 96 too long)
        # -> some secondaries with zero averages for azimuth offset refinement
        thres_days=63 # three months, S1A/B repeats 54, 60, 66, ... (60 still ok, 66 too long)
         -> 63 days seems to be a good compromise between runtime and coregistration success
        #thres_days=51 # maximum 7 weeks, S1A/B repeats 42, 48, 54, ... (48 still ok, 54 too long)
        # -> longer runtime compared to 63, similar number of badly coregistered scenes
        # do secondaries with time difference less than thres_days
    """

    # We do everything with datetime.date's (can't mix and match date vs. datetime)
    if isinstance(primary_dt, datetime.datetime):
        primary_dt = primary_dt.date()
    elif not isinstance(primary_dt, datetime.date):
        primary_dt = datetime.date(primary_dt)

    lists = []

    # Note: when compositing the lists, rhs comes first because the bash puts the rhs as
    # the "lower" part of the tree, which seems to appear first in the list file...
    #
    # I've opted for rhs vs. lhs because it's more obvious, newer scenes are to the right
    # in sequence as they're greater than, older scenes are to the left / less than.

    # Initial Primary<->Secondary coreg list
    lhs, rhs = find_scenes_in_range(primary_dt, date_list, thres_days)
    last_list = lhs + rhs

    while len(last_list) > 0:
        lists.append(last_list)

        if last_list[0] < primary_dt:
            lhs, rhs = find_scenes_in_range(last_list[0], date_list, thres_days)
            sub_list1 = lhs
        else:
            sub_list1 = []

        if last_list[-1] > primary_dt:
            lhs, rhs = find_scenes_in_range(last_list[-1], date_list, thres_days)
            sub_list2 = rhs
        else:
            sub_list2 = []

        last_list = sub_list1 + sub_list2

    return lists


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

        # All the rest coregister to
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

    primary_slc_prefix = (f"{primary_scene}_{primary_pol}")
    primary_slc_rlks_prefix = f"{primary_slc_prefix}_{rlks}rlks"
    r_dem_primary_slc_prefix = f"r{primary_slc_prefix}"

    dem_dir = outdir / proc_config.dem_dir
    dem_filenames = CoregisterDem.dem_filenames(
        dem_prefix=primary_slc_rlks_prefix,
        outdir=dem_dir
    )

    slc_primary_dir = outdir / proc_config.slc_dir / primary_scene
    dem_primary_names = CoregisterDem.dem_primary_names(
        slc_prefix=primary_slc_rlks_prefix,
        r_slc_prefix=r_dem_primary_slc_prefix,
        outdir=slc_primary_dir,
    )

    kwargs = {
        "proc_file": proc_file,
        "list_idx": "-",
        "slc_primary": slc_primary_dir / f"{primary_slc_prefix}.slc",
        "range_looks": rlks,
        "azimuth_looks": alks,
        "ellip_pix_sigma0": dem_filenames["ellip_pix_sigma0"],
        "dem_pix_gamma0": dem_filenames["dem_pix_gam"],
        "r_dem_primary_mli": dem_primary_names["r_dem_primary_mli"],
        "rdc_dem": dem_filenames["rdc_dem"],
        "geo_dem_par": dem_filenames["geo_dem_par"],
        "dem_lt_fine": dem_filenames["dem_lt_fine"],
        "outdir": outdir,
        "workdir": workdir,
    }

    if scene_date:
        if not scene_pol:
            scene_pol = primary_pol

        secondary_dir = outdir / proc_config.slc_dir / scene_date

        secondary_slc_prefix = f"{scene_date}_{scene_pol}"
        kwargs["slc_secondary"] = secondary_dir / f"{secondary_slc_prefix}.slc"
        kwargs["secondary_mli"] = secondary_dir / f"{secondary_slc_prefix}_{rlks}rlks.mli"

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
                slc_dir=self.outdir,
                slc_date=primary_scene,
                slc_pol=primary_pol
            )

            log.info("Beginning DEM primary coregistration")

            # Read rlks/alks from multilook status
            ml_file = f"{self.stack_id}_createmultilook_status_logs.out"
            rlks, alks = read_rlks_alks(tdir(self.workdir) / ml_file)

            primary_dir = outdir / proc_config.slc_dir / primary_scene
            primary_slc = primary_dir / f"{primary_scene}_{primary_pol}.slc"

            primary_slc_par = Path(primary_slc).with_suffix(".slc.par")
            dem = outdir / __DEM_GAMMA__ / f"{self.stack_id}.dem"
            dem_par = dem.with_suffix(dem.suffix + ".par")

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
                dem=dem,
                slc=Path(primary_slc),
                dem_par=dem_par,
                slc_par=primary_slc_par,
                dem_outdir=dem_outdir,
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

    proc_file = luigi.Parameter()
    list_idx = luigi.Parameter()
    slc_primary = luigi.Parameter()
    slc_secondary = luigi.Parameter()
    secondary_mli = luigi.Parameter()
    range_looks = luigi.IntParameter()
    azimuth_looks = luigi.IntParameter()
    ellip_pix_sigma0 = luigi.Parameter()
    dem_pix_gamma0 = luigi.Parameter()
    r_dem_primary_mli = luigi.Parameter()
    rdc_dem = luigi.Parameter()
    geo_dem_par = luigi.Parameter()
    dem_lt_fine = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()

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
            return CoregisterSlc(**kwargs)

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
            polarization=secondary_pol,
            secondary_date=secondary_date,
            slc_secondary=self.slc_secondary,
            primary_date=primary_date,
            slc_primary=self.slc_primary
        )
        log.info("Beginning SLC coregistration")

        # Load the gamma proc config file
        proc_path = Path(self.proc_file)
        with proc_path.open("r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

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
                primary_task = get_coreg_kwargs(proc_path, secondary_date, primary_pol)
                primary_task = CoregisterSecondary(**primary_task)
                processor = primary_task.get_processor()

                coreg_secondary.apply_coregistration(processor.secondary_off, processor.secondary_lt)

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

    proc_file = luigi.Parameter()
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

        slc_frames = get_scenes(self.burst_data_csv)

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

                secondary_dir = outdir / proc_config.slc_dir / slc_scene

                # Process coreg for all polarisations, the secondary polarisations will
                # simply apply primary LUTs to secondary products.
                for pol in _pols:
                    secondary_slc_prefix = f"{slc_scene}_{pol}"
                    kwargs["slc_secondary"] = secondary_dir / f"{secondary_slc_prefix}.slc"
                    kwargs["secondary_mli"] = secondary_dir / f"{secondary_slc_prefix}_{rlks}rlks.mli"
                    secondary_coreg_jobs.append(CoregisterSecondary(**kwargs))

        yield secondary_coreg_jobs

        with self.output().open("w") as f:
            f.write("")
