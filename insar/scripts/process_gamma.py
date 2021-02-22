#!/usr/bin/env python

import datetime
import os
import re
import traceback
from os.path import exists, join as pjoin
from pathlib import Path
import zipfile
import luigi
import luigi.configuration
import pandas as pd
from luigi.util import requires
import zlib
import structlog

from insar.constant import SCENE_DATE_FMT
from insar.generate_slc_inputs import query_slc_inputs, slc_inputs
from insar.calc_baselines_new import BaselineProcess
from insar.calc_multilook_values import multilook, calculate_mean_look_values
from insar.coregister_dem import CoregisterDem
from insar.coregister_slc import CoregisterSlc
from insar.make_gamma_dem import create_gamma_dem
from insar.process_s1_slc import SlcProcess
from insar.process_ifg import run_workflow, get_ifg_width, TempFileConfig
from insar.project import ProcConfig, DEMFileNames, IfgFileNames

from insar.meta_data.s1_slc import S1DataDownload
from insar.clean_up import (
    clean_rawdatadir,
    clean_slcdir,
    clean_gammademdir,
    clean_demdir,
)
from insar.logs import TASK_LOGGER, STATUS_LOGGER, COMMON_PROCESSORS

structlog.configure(processors=COMMON_PROCESSORS)
_LOG = structlog.get_logger("insar")

__RAW__ = "RAW_DATA"
__SLC__ = "SLC"
__DEM_GAMMA__ = "GAMMA_DEM"
__DEM__ = "DEM"
__IFG__ = "IFG"
__DATE_FMT__ = "%Y%m%d"
__TRACK_FRAME__ = r"^T[0-9]{3}[A|D]_F[0-9]{2}"

SLC_PATTERN = (
    r"^(?P<sensor>S1[AB])_"
    r"(?P<beam>S1|S2|S3|S4|S5|S6|IW|EW|WV|EN|N1|N2|N3|N4|N5|N6|IM)_"
    r"(?P<product>SLC|GRD|OCN)(?:F|H|M|_)_"
    r"(?:1|2)"
    r"(?P<category>S|A)"
    r"(?P<pols>SH|SV|DH|DV|VV|HH|HV|VH)_"
    r"(?P<start>[0-9]{8}T[0-9]{6})_"
    r"(?P<stop>[0-9]{8}T[0-9]{6})_"
    r"(?P<orbitNumber>[0-9]{6})_"
    r"(?P<dataTakeID>[0-9A-F]{6})_"
    r"(?P<productIdentifier>[0-9A-F]{4})"
    r"(?P<extension>.SAFE|.zip)$"
)


@luigi.Task.event_handler(luigi.Event.FAILURE)
def on_failure(task, exception):
    """Capture any Task Failure here."""
    TASK_LOGGER.exception(
        task=task.get_task_family(),
        params=task.to_str_params(),
        track=getattr(task, "track", ""),
        frame=getattr(task, "frame", ""),
        stack_info=True,
        status="failure",
        exception=exception.__str__(),
        traceback=traceback.format_exc().splitlines(),
    )


@luigi.Task.event_handler(luigi.Event.SUCCESS)
def on_success(task):
    """Capture any Task Succes here."""
    TASK_LOGGER.info(
        task=task.get_task_family(),
        params=task.to_str_params(),
        track=getattr(task, "track", ""),
        frame=getattr(task, "frame", ""),
        status="success",
    )


def get_scenes(burst_data_csv):
    df = pd.read_csv(burst_data_csv)
    scene_dates = [_dt for _dt in sorted(df.date.unique())]

    frames_data = []

    for _date in scene_dates:
        df_subset = df[df["date"] == _date]
        polarizations = df_subset.polarization.unique()
        df_subset_new = df_subset[df_subset["polarization"] == polarizations[0]]

        complete_frame = True
        for swath in [1, 2, 3]:
            swath_df = df_subset_new[df_subset_new.swath == "IW{}".format(swath)]
            swath_df = swath_df.sort_values(by="acquistion_datetime", ascending=True)
            for row in swath_df.itertuples():
                missing_bursts = row.missing_master_bursts.strip("][")
                if missing_bursts:
                    complete_frame = False
        dt = datetime.datetime.strptime(_date, "%Y-%m-%d")
        frames_data.append((dt, complete_frame, polarizations))

    return frames_data


def find_scenes_in_range(
    master_dt, date_list, thres_days: int, include_closest: bool = True
):
    """
    Creates a list of frame dates that within range of a master date.

    :param master_dt:
        The master date in which we are searching for scenes relative to.
    :param date_list:
        The list which we're searching for dates in.
    :param thres_days:
        The number of days threshold in which scenes must be within relative to
        the master date.
    :param include_closest:
        When true - if there exist slc frames on either side of the master date, which are NOT
        within the threshold window then the closest date from each side will be
        used instead of no scene at all.
    """

    # We do everything with datetime.date's (can't mix and match date vs. datetime)
    if isinstance(master_dt, datetime.datetime):
        master_dt = master_dt.date()
    elif not isinstance(master_dt, datetime.date):
        master_dt = datetime.date(master_dt)

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
        elif not isinstance(master_dt, datetime.date):
            dt = datetime.date(dt)

        dt_diff = dt - master_dt

        # Skip scenes that match the master date
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
                f"Date difference to closest slave greater than {thres_days} days, using closest slave only: {closest_lhs}"
            )
            tree_lhs = [closest_lhs]

        if len(tree_rhs) == 0 and closest_rhs is not None:
            _LOG.info(
                f"Date difference to closest slave greater than {thres_days} days, using closest slave only: {closest_rhs}"
            )
            tree_rhs = [closest_rhs]

    return tree_lhs, tree_rhs


def create_slave_coreg_tree(master_dt, date_list, thres_days=63):
    """
    Creates a set of co-registration lists containing subsets of the prior set, to create a tree-like co-registration structure.

    Notes from the bash on :thres_days: parameter:
        #thres_days=93 # three months, S1A/B repeats 84, 90, 96, ... (90 still ok, 96 too long)
        # -> some slaves with zero averages for azimuth offset refinement
        thres_days=63 # three months, S1A/B repeats 54, 60, 66, ... (60 still ok, 66 too long)
         -> 63 days seems to be a good compromise between runtime and coregistration success
        #thres_days=51 # maximum 7 weeks, S1A/B repeats 42, 48, 54, ... (48 still ok, 54 too long)
        # -> longer runtime compared to 63, similar number of badly coregistered scenes
        # do slaves with time difference less than thres_days
    """

    # We do everything with datetime.date's (can't mix and match date vs. datetime)
    if isinstance(master_dt, datetime.datetime):
        master_dt = master_dt.date()
    elif not isinstance(master_dt, datetime.date):
        master_dt = datetime.date(master_dt)

    lists = []

    # Note: when compositing the lists, rhs comes first because the bash puts the rhs as
    # the "lower" part of the tree, which seems to appear first in the list file...
    #
    # I've opted for rhs vs. lhs because it's more obvious, newer scenes are to the right
    # in sequence as they're greater than, older scenes are to the left / less than.

    # Initial Master<->Slave coreg list
    lhs, rhs = find_scenes_in_range(master_dt, date_list, thres_days)
    last_list = lhs + rhs

    while len(last_list) > 0:
        lists.append(last_list)

        if last_list[0] < master_dt:
            lhs, rhs = find_scenes_in_range(last_list[0], date_list, thres_days)
            sub_list1 = lhs
        else:
            sub_list1 = []

        if last_list[-1] > master_dt:
            lhs, rhs = find_scenes_in_range(last_list[-1], date_list, thres_days)
            sub_list2 = rhs
        else:
            sub_list2 = []

        last_list = sub_list1 + sub_list2

    return lists


def calculate_master(scenes_list) -> datetime:

    slc_dates = [
        datetime.datetime.strptime(scene.strip(), __DATE_FMT__).date()
        for scene in scenes_list
    ]
    return sorted(slc_dates, reverse=True)[int(len(slc_dates) / 2)]


class ExternalFileChecker(luigi.ExternalTask):
    """checks the external dependencies."""

    filename = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(str(self.filename))


class ListParameter(luigi.Parameter):
    """Converts luigi parameters separated by comma to a list."""

    def parse(self, arguments):
        return arguments.split(",")


class SlcDataDownload(luigi.Task):
    """
    Runs single slc scene extraction task
    """

    slc_scene = luigi.Parameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()
    output_dir = luigi.Parameter()
    polarization = luigi.ListParameter()
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.workdir)).joinpath(
                f"{Path(str(self.slc_scene)).stem}_slc_download.out"
            )
        )

    def run(self):
        download_obj = S1DataDownload(
            Path(str(self.slc_scene)),
            list(self.polarization),
            Path(str(self.poeorb_path)),
            Path(str(self.resorb_path)),
        )
        failed = False
        os.makedirs(str(self.output_dir), exist_ok=True)
        try:
            download_obj.slc_download(Path(str(self.output_dir)))
        except (zipfile.BadZipFile, zlib.error):
            failed = True
        finally:
            with self.output().open("w") as f:
                if failed:
                    f.write(f"{Path(self.slc_scene).name}")
                else:
                    f.write("")


class InitialSetup(luigi.Task):
    """
    Runs the initial setup of insar processing workflow by
    creating required directories and file lists
    """

    proc_file = luigi.Parameter()
    start_date = luigi.Parameter()
    end_date = luigi.Parameter()
    vector_file = luigi.Parameter()
    database_name = luigi.Parameter()
    orbit = luigi.Parameter()
    polarization = luigi.ListParameter(default=["VV"])
    track = luigi.Parameter()
    frame = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()
    burst_data_csv = luigi.Parameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()
    cleanup = luigi.BoolParameter()

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.workdir)).joinpath(
                f"{self.track}_{self.frame}_initialsetup_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("initial setup task")
        # get the relative orbit number, which is int value of the numeric part of the track name
        rel_orbit = int(re.findall(r"\d+", str(self.track))[0])

        # get slc input information
        slc_query_results = query_slc_inputs(
            str(self.database_name),
            str(self.vector_file),
            self.start_date,
            self.end_date,
            str(self.orbit),
            rel_orbit,
            list(self.polarization),
        )

        if slc_query_results is None:
            raise ValueError(
                f"Nothing was returned for {self.track}_{self.frame} "
                f"start_date: {self.start_date} "
                f"end_date: {self.end_date} "
                f"orbit: {self.orbit}"
            )

        # here scenes_list and download_list are overwritten for each polarization
        # IW products in conflict-free mode products VV and VH polarization over land
        slc_inputs_df = pd.concat(
            [slc_inputs(slc_query_results[pol]) for pol in list(self.polarization)]
        )

        # download slc data
        download_dir = Path(str(self.outdir)).joinpath(__RAW__)

        os.makedirs(download_dir, exist_ok=True)

        download_list = slc_inputs_df.url.unique()
        download_tasks = []
        for slc_url in download_list:
            scene_date = Path(slc_url).name.split("_")[5].split("T")[0]
            download_tasks.append(
                SlcDataDownload(
                    slc_scene=slc_url.rstrip(),
                    polarization=self.polarization,
                    poeorb_path=self.poeorb_path,
                    resorb_path=self.resorb_path,
                    workdir=self.workdir,
                    output_dir=Path(download_dir).joinpath(scene_date),
                )
            )
        yield download_tasks

        # TODO decide if we terminate if scenes in a stack fails to extract
        # TODO or continue to processing after removing a failed scenes
        # currently processing removing failed scenes
        for _task in download_tasks:
            with open(_task.output().path) as fid:
                out_name = fid.readline().rstrip()
                if re.match(SLC_PATTERN, out_name):
                    log.info(
                        f"corrupted zip file {out_name} removed from further processing"
                    )
                    indexes = slc_inputs_df[
                        slc_inputs_df["url"].map(lambda x: Path(x).name) == out_name
                    ].index
                    slc_inputs_df.drop(indexes, inplace=True)

        # save slc burst data details which is used by different tasks
        slc_inputs_df.to_csv(self.burst_data_csv)

        with self.output().open("w") as out_fid:
            out_fid.write("")


@requires(InitialSetup)
class CreateGammaDem(luigi.Task):
    """
    Runs create gamma dem task
    """

    dem_img = luigi.Parameter()

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_creategammadem_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("create gamma dem task")

        gamma_dem_dir = Path(self.outdir).joinpath(__DEM_GAMMA__)

        os.makedirs(gamma_dem_dir, exist_ok=True)

        kwargs = {
            "gamma_dem_dir": gamma_dem_dir,
            "dem_img": self.dem_img,
            "track_frame": f"{self.track}_{self.frame}",
            "shapefile": self.vector_file,
        }

        create_gamma_dem(**kwargs)
        with self.output().open("w") as out_fid:
            out_fid.write("")


class ProcessSlc(luigi.Task):
    """
    Runs single slc processing task
    """

    scene_date = luigi.Parameter()
    raw_path = luigi.Parameter()
    polarization = luigi.Parameter()
    burst_data = luigi.Parameter()
    slc_dir = luigi.Parameter()
    workdir = luigi.Parameter()
    ref_master_tab = luigi.Parameter(default=None)

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.workdir)).joinpath(
                f"{self.scene_date}_{self.polarization}_slc_logs.out"
            )
        )

    def run(self):
        slc_job = SlcProcess(
            str(self.raw_path),
            str(self.slc_dir),
            str(self.polarization),
            str(self.scene_date),
            str(self.burst_data),
            self.ref_master_tab,
        )

        slc_job.main()

        with self.output().open("w") as f:
            f.write("")


@requires(InitialSetup)
class CreateFullSlc(luigi.Task):
    """
    Runs the create full slc tasks
    """

    proc_file = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_createfullslc_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("create full slc task")

        slc_dir = Path(self.outdir).joinpath(__SLC__)
        os.makedirs(slc_dir, exist_ok=True)

        slc_frames = get_scenes(self.burst_data_csv)

        # first create slc for one complete frame which will be a reference frame
        # to resize the incomplete frames.
        resize_master_tab = None
        resize_master_scene = None
        resize_master_pol = None
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(__DATE_FMT__)
            for _pol in _pols:
                if status_frame:
                    resize_task = ProcessSlc(
                        scene_date=slc_scene,
                        raw_path=Path(self.outdir).joinpath(__RAW__),
                        polarization=_pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                    )
                    yield resize_task
                    resize_master_tab = Path(slc_dir).joinpath(
                        slc_scene, f"{slc_scene}_{_pol.upper()}_tab"
                    )
                    break
            if resize_master_tab is not None:
                if resize_master_tab.exists():
                    resize_master_scene = slc_scene
                    resize_master_pol = _pol
                    break

        # need at least one complete frame to enable further processing of the stacks
        # The frame definition were generated using all sentinel-1 acquisition dataset, thus
        # only processing a temporal subset might encounter stacks with all scene's frame
        # not forming a complete master frame.
        # TODO implement a method to resize a stacks to new frames definition
        # TODO Generate a new reference frame using scene that has least number of missing burst
        if resize_master_tab is None:
            raise ValueError(
                f"Not a  single complete frames were available {self.track}_{self.frame}"
            )

        slc_tasks = []
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(__DATE_FMT__)
            for _pol in _pols:
                if _pol not in self.polarization:
                    continue
                if slc_scene == resize_master_scene and _pol == resize_master_pol:
                    continue
                slc_tasks.append(
                    ProcessSlc(
                        scene_date=slc_scene,
                        raw_path=Path(self.outdir).joinpath(__RAW__),
                        polarization=_pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                        ref_master_tab=resize_master_tab,
                    )
                )
        yield slc_tasks
        # TODO decide if we terminate if scenes in a stack fails to process slc
        # TODO or continue to processing after removing failed scenes
        # currently processing removing failed scenes
        slc_inputs_df = pd.read_csv(self.burst_data_csv)
        rewrite = False
        for _slc_task in slc_tasks:
            print("THIS IS slc task")
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
        # clean up raw data directory
        if self.cleanup:
            clean_rawdatadir(Path(self.outdir).joinpath(__RAW__))

        with self.output().open("w") as out_fid:
            out_fid.write("")



class ProcessSlcSubset(luigi.Task):
    """
    Runs single slc processing task
    """

    scene_date = luigi.Parameter()
    raw_path = luigi.Parameter()
    polarization = luigi.Parameter()
    burst_data = luigi.Parameter()
    slc_dir = luigi.Parameter()
    workdir = luigi.Parameter()
    ref_master_tab = luigi.Parameter(default=None)
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.workdir)).joinpath(
                f"{self.scene_date}_{self.polarization}_slc_subset_logs.out"
            )
        )

    def run(self):
        slc_job = SlcProcess(
            str(self.raw_path),
            str(self.slc_dir),
            str(self.polarization),
            str(self.scene_date),
            str(self.burst_data),
            self.ref_master_tab,
        )

        slc_job.main_subset(int(self.rlks), int(self.alks))

        with self.output().open("w") as f:
            f.write("")


@requires(CreateFullSlc)
class CreateSlcSubset(luigi.Task):
    """
    Runs the slc subsetting tasks
    """

    proc_file = luigi.Parameter()
    multi_look = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_createslcsubset_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("subset slc task")

        slc_dir = Path(self.outdir).joinpath(__SLC__)
        slc_frames = get_scenes(self.burst_data_csv)

        # Get all VV par files and compute range and azimuth looks
        slc_par_files = []
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(__DATE_FMT__)
            for _pol in _pols:
                if _pol not in self.polarization or _pol.upper() != "VV":
                    continue
                slc_par = pjoin(
                    self.outdir,
                    __SLC__,
                    slc_scene,
                    f"{slc_scene}_{_pol.upper()}.slc.par",
                )
                if not exists(slc_par):
                    raise FileNotFoundError(f"missing {slc_par} file")
                slc_par_files.append(Path(slc_par))

        # range and azimuth looks are only computed from VV polarization
        rlks, alks, *_ = calculate_mean_look_values(
            slc_par_files,
            int(str(self.multi_look)),
        )

        # first create slc for one complete frame which will be a reference frame
        # to resize the incomplete frames.
        resize_master_tab = None
        resize_master_scene = None
        resize_master_pol = None
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(__DATE_FMT__)
            for _pol in _pols:
                if status_frame:
                    resize_task = ProcessSlcSubset(
                        scene_date=slc_scene,
                        raw_path=Path(self.outdir).joinpath(__RAW__),
                        polarization=_pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                        rlks=rlks,
                        alks=alks
                    )
                    yield resize_task
                    resize_master_tab = Path(slc_dir).joinpath(
                        slc_scene, f"{slc_scene}_{_pol.upper()}_tab"
                    )
                    break
            if resize_master_tab is not None:
                if resize_master_tab.exists():
                    resize_master_scene = slc_scene
                    resize_master_pol = _pol
                    break

        # need at least one complete frame to enable further processing of the stacks
        # The frame definition were generated using all sentinel-1 acquisition dataset, thus
        # only processing a temporal subset might encounter stacks with all scene's frame
        # not forming a complete master frame.
        # TODO implement a method to resize a stacks to new frames definition
        # TODO Generate a new reference frame using scene that has least number of missing burst
        if resize_master_tab is None:
            raise ValueError(
                f"Not a  single complete frames were available {self.track}_{self.frame}"
            )

        slc_tasks = []
        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(__DATE_FMT__)
            for _pol in _pols:
                if _pol not in self.polarization:
                    continue
                if slc_scene == resize_master_scene and _pol == resize_master_pol:
                    continue
                slc_tasks.append(
                    ProcessSlcSubset(
                        scene_date=slc_scene,
                        raw_path=Path(self.outdir).joinpath(__RAW__),
                        polarization=_pol,
                        burst_data=self.burst_data_csv,
                        slc_dir=slc_dir,
                        workdir=self.workdir,
                        ref_master_tab=resize_master_tab,
                        rlks=rlks,
                        alks=alks
                    )
                )
        yield slc_tasks

        # clean up raw data directory
        if self.cleanup:
            clean_rawdatadir(Path(self.outdir).joinpath(__RAW__))

        with self.output().open("w") as out_fid:
            out_fid.write("")


class Multilook(luigi.Task):
    """
    Runs single slc processing task
    """

    slc = luigi.Parameter()
    slc_par = luigi.Parameter()
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.workdir)).joinpath(f"{Path(str(self.slc)).stem}_ml_logs.out")
        )

    def run(self):
        multilook(
            Path(str(self.slc)),
            Path(str(self.slc_par)),
            int(str(self.rlks)),
            int(str(self.alks)),
        )
        with self.output().open("w") as f:
            f.write("")


@requires(CreateSlcSubset)
class CreateMultilook(luigi.Task):
    """
    Runs creation of multi-look image task
    """

    proc_file = luigi.Parameter()
    multi_look = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_createmultilook_status_logs.out"
            )
        )

    def run(self):

        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("create multi-look task")

        # calculate the mean range and azimuth look values
        slc_dir = Path(self.outdir).joinpath(__SLC__)
        slc_frames = get_scenes(self.burst_data_csv)
        slc_par_files = []

        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(__DATE_FMT__)
            for _pol in _pols:
                if _pol not in self.polarization:
                    continue
                slc_par = pjoin(
                    self.outdir,
                    __SLC__,
                    slc_scene,
                    f"{slc_scene}_{_pol.upper()}.slc.par",
                )
                if not exists(slc_par):
                    raise FileNotFoundError(f"missing {slc_par} file")
                slc_par_files.append(Path(slc_par))

        # range and azimuth looks are only computed from VV polarization
        rlks, alks, *_ = calculate_mean_look_values(
            [_par for _par in slc_par_files if "VV" in _par.stem],
            int(str(self.multi_look)),
        )

        # multi-look jobs run
        ml_jobs = []
        for slc_par in slc_par_files:
            slc = slc_par.with_suffix("")
            ml_jobs.append(
                Multilook(
                    slc=slc, slc_par=slc_par, rlks=rlks, alks=alks, workdir=self.workdir
                )
            )

        yield ml_jobs

        with self.output().open("w") as out_fid:
            out_fid.write("rlks:\t {}\n".format(str(rlks)))
            out_fid.write("alks:\t {}".format(str(alks)))


@requires(CreateMultilook)
class CalcInitialBaseline(luigi.Task):
    """
    Runs calculation of initial baseline task
    """

    proc_file = luigi.Parameter()
    master_scene_polarization = luigi.Parameter(default="VV")

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_calcinitialbaseline_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("calculate baseline task")

        # Load the gamma proc config file
        with open(str(self.proc_file), "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        slc_frames = get_scenes(self.burst_data_csv)
        slc_par_files = []
        polarizations = [self.master_scene_polarization]
        for _dt, _, _pols in slc_frames:
            slc_scene = _dt.strftime(__DATE_FMT__)

            if self.master_scene_polarization in _pols:
                slc_par = pjoin(
                    self.outdir,
                    __SLC__,
                    slc_scene,
                    "{}_{}.slc.par".format(slc_scene, self.master_scene_polarization),
                )
            else:
                slc_par = pjoin(
                    self.outdir,
                    __SLC__,
                    slc_scene,
                    "{}_{}.slc.par".format(slc_scene, _pols[0]),
                )
                polarizations.append(_pols[0])

            if not exists(slc_par):
                raise FileNotFoundError(f"missing {slc_par} file")

            slc_par_files.append(Path(slc_par))

        baseline = BaselineProcess(
            slc_par_files,
            list(set(polarizations)),
            master_scene=calculate_master(
                [dt.strftime(__DATE_FMT__) for dt, *_ in slc_frames]
            ),
            outdir=Path(self.outdir),
        )

        # creates a ifg list based on sbas-network
        # TODO confirm with InSAR team if sbas-network is the default ifg list?
        baseline.sbas_list(nmin=int(proc_config.min_connect), nmax=int(proc_config.max_connect))

        with self.output().open("w") as out_fid:
            out_fid.write("")


@requires(CreateGammaDem, CalcInitialBaseline)
class CoregisterDemMaster(luigi.Task):
    """
    Runs co-registration of DEM and master scene
    """

    multi_look = luigi.IntParameter()
    master_scene_polarization = luigi.Parameter(default="VV")
    master_scene = luigi.Parameter(default=None)
    cleanup = luigi.BoolParameter()

    def output(self):

        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_coregisterdemmaster_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("co-register master-dem task")

        # glob a multi-look file and read range and azimuth values computed before
        # TODO need better mechanism to pass parameter between tasks
        ml_file = Path(self.workdir).joinpath(
            f"{self.track}_{self.frame}_createmultilook_status_logs.out"
        )
        with open(ml_file, "r") as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(":")[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(":")[1])

        master_scene = self.master_scene
        if master_scene is None:
            slc_frames = get_scenes(self.burst_data_csv)
            master_scene = calculate_master(
                [dt.strftime(__DATE_FMT__) for dt, *_ in slc_frames]
            )

        master_slc = pjoin(
            Path(self.outdir),
            __SLC__,
            master_scene.strftime(__DATE_FMT__),
            "{}_{}.slc".format(
                master_scene.strftime(__DATE_FMT__), self.master_scene_polarization
            ),
        )

        master_slc_par = Path(master_slc).with_suffix(".slc.par")
        dem = (
            Path(self.outdir)
            .joinpath(__DEM_GAMMA__)
            .joinpath(f"{self.track}_{self.frame}.dem")
        )
        dem_par = dem.with_suffix(dem.suffix + ".par")

        coreg = CoregisterDem(
            rlks=rlks,
            alks=alks,
            shapefile=str(self.vector_file),
            dem=dem,
            slc=Path(master_slc),
            dem_par=dem_par,
            slc_par=master_slc_par,
            dem_outdir=Path(self.outdir).joinpath(__DEM__),
            multi_look=self.multi_look,
        )

        coreg.main()

        with self.output().open("w") as out_fid:
            out_fid.write("")


class CoregisterSlave(luigi.Task):
    """
    Runs the master-slave co-registration task
    """

    proc_file = luigi.Parameter()
    list_idx = luigi.Parameter()
    slc_master = luigi.Parameter()
    slc_slave = luigi.Parameter()
    slave_mli = luigi.Parameter()
    range_looks = luigi.IntParameter()
    azimuth_looks = luigi.IntParameter()
    ellip_pix_sigma0 = luigi.Parameter()
    dem_pix_gamma0 = luigi.Parameter()
    r_dem_master_mli = luigi.Parameter()
    rdc_dem = luigi.Parameter()
    eqa_dem_par = luigi.Parameter()
    dem_lt_fine = luigi.Parameter()
    work_dir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(str(self.work_dir)).joinpath(
                f"{Path(str(self.slc_master)).stem}_{Path(str(self.slc_slave)).stem}_coreg_logs.out"
            )
        )

    def run(self):
        # Load the gamma proc config file
        with open(str(self.proc_file), "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        coreg_slave = CoregisterSlc(
            proc=proc_config,
            list_idx=str(self.list_idx),
            slc_master=Path(str(self.slc_master)),
            slc_slave=Path(str(self.slc_slave)),
            slave_mli=Path(str(self.slave_mli)),
            range_looks=int(str(self.range_looks)),
            azimuth_looks=int(str(self.azimuth_looks)),
            ellip_pix_sigma0=Path(str(self.ellip_pix_sigma0)),
            dem_pix_gamma0=Path(str(self.dem_pix_gamma0)),
            r_dem_master_mli=Path(str(self.r_dem_master_mli)),
            rdc_dem=Path(str(self.rdc_dem)),
            eqa_dem_par=Path(str(self.eqa_dem_par)),
            dem_lt_fine=Path(str(self.dem_lt_fine)),
        )

        coreg_slave.main()

        with self.output().open("w") as f:
            f.write("")


@requires(CoregisterDemMaster)
class CreateCoregisterSlaves(luigi.Task):
    """
    Runs the co-registration tasks.

    The first batch of tasks produced is the master-slave coregistration, followed
    up by each sub-tree of slave-slave coregistrations in the coregistration network.
    """

    proc_file = luigi.Parameter()
    master_scene_polarization = luigi.Parameter(default="VV")
    master_scene = luigi.Parameter(default=None)
    cleanup = luigi.BoolParameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_coregister_slaves_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("co-register master-slaves task")

        # Load the gamma proc config file
        with open(str(self.proc_file), "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        slc_frames = get_scenes(self.burst_data_csv)

        master_scene = self.master_scene
        if master_scene is None:
            master_scene = calculate_master(
                [dt.strftime(__DATE_FMT__) for dt, *_ in slc_frames]
            )

        coreg_tree = create_slave_coreg_tree(
            master_scene, [dt for dt, _, _ in slc_frames]
        )

        master_polarizations = [
            pols for dt, _, pols in slc_frames if dt.date() == master_scene
        ]
        assert len(master_polarizations) == 1

        # TODO if master polarization data does not exist in SLC archive then
        # TODO choose other polarization or raise Error.
        if self.master_scene_polarization not in master_polarizations[0]:
            raise ValueError(
                f"{self.master_scene_polarization}  not available in SLC data for {master_scene}"
            )

        # get range and azimuth looked values
        ml_file = Path(self.workdir).joinpath(
            f"{self.track}_{self.frame}_createmultilook_status_logs.out"
        )
        with open(ml_file, "r") as src:
            for line in src.readlines():
                if line.startswith("rlks"):
                    rlks = int(line.strip().split(":")[1])
                if line.startswith("alks"):
                    alks = int(line.strip().split(":")[1])

        master_scene = master_scene.strftime(__DATE_FMT__)
        master_slc_prefix = (
            f"{master_scene}_{str(self.master_scene_polarization).upper()}"
        )
        master_slc_rlks_prefix = f"{master_slc_prefix}_{rlks}rlks"
        r_dem_master_slc_prefix = f"r{master_slc_prefix}"

        dem_dir = Path(self.outdir).joinpath(__DEM__)
        dem_filenames = CoregisterDem.dem_filenames(
            dem_prefix=master_slc_rlks_prefix, outdir=dem_dir
        )
        slc_master_dir = Path(pjoin(self.outdir, __SLC__, master_scene))
        dem_master_names = CoregisterDem.dem_master_names(
            slc_prefix=master_slc_rlks_prefix,
            r_slc_prefix=r_dem_master_slc_prefix,
            outdir=slc_master_dir,
        )
        kwargs = {
            "proc_file": self.proc_file,
            "list_idx": "-",
            "slc_master": slc_master_dir.joinpath(f"{master_slc_prefix}.slc"),
            "range_looks": rlks,
            "azimuth_looks": alks,
            "ellip_pix_sigma0": dem_filenames["ellip_pix_sigma0"],
            "dem_pix_gamma0": dem_filenames["dem_pix_gam"],
            "r_dem_master_mli": dem_master_names["r_dem_master_mli"],
            "rdc_dem": dem_filenames["rdc_dem"],
            "eqa_dem_par": dem_filenames["eqa_dem_par"],
            "dem_lt_fine": dem_filenames["dem_lt_fine"],
            "work_dir": Path(self.workdir),
        }

        slave_coreg_jobs = []

        # need to account for master scene with polarization different than
        # the one used in coregistration of dem and master scene
        master_pol_coreg = set(list(master_polarizations[0])) - {
            str(self.master_scene_polarization).upper()
        }
        for pol in master_pol_coreg:
            master_slc_prefix = f"{master_scene}_{pol.upper()}"
            kwargs["slc_slave"] = slc_master_dir.joinpath(f"{master_slc_prefix}.slc")
            kwargs["slave_mli"] = slc_master_dir.joinpath(
                f"{master_slc_prefix}_{rlks}rlks.mli"
            )
            slave_coreg_jobs.append(CoregisterSlave(**kwargs))

        for list_index, list_dates in enumerate(coreg_tree):
            list_index += 1  # list index is 1-based
            list_frames = [i for i in slc_frames if i[0].date() in list_dates]

            # Write list file
            list_file_path = Path(proc_config.list_dir) / f"slaves{list_index}.list"
            if not list_file_path.parent.exists():
                list_file_path.parent.mkdir(parents=True)

            with open(list_file_path, "w") as listfile:
                list_date_strings = [
                    dt.strftime(__DATE_FMT__) for dt, _, _ in list_frames
                ]
                listfile.write("\n".join(list_date_strings))

            # Bash passes '-' for slaves1.list, and list_index there after.
            if list_index > 1:
                kwargs["list_idx"] = list_index

            for _dt, _, _pols in list_frames:
                slc_scene = _dt.strftime(__DATE_FMT__)
                if slc_scene == master_scene:
                    continue

                slave_dir = Path(self.outdir).joinpath(__SLC__).joinpath(slc_scene)
                for _pol in _pols:
                    if _pol not in self.polarization:
                        continue

                    slave_slc_prefix = f"{slc_scene}_{_pol.upper()}"
                    kwargs["slc_slave"] = slave_dir.joinpath(f"{slave_slc_prefix}.slc")
                    kwargs["slave_mli"] = slave_dir.joinpath(
                        f"{slave_slc_prefix}_{rlks}rlks.mli"
                    )
                    slave_coreg_jobs.append(CoregisterSlave(**kwargs))

        yield slave_coreg_jobs

        # cleanup slc directory after coreg  and gamma dem dir
        if self.cleanup:
            clean_slcdir(Path(self.outdir).joinpath(__SLC__))
            clean_gammademdir(
                Path(self.outdir).joinpath(__DEM_GAMMA__),
                track_frame=f"{self.track}_{self.frame}",
            )
            # TODO move this clean up methods after interferogram generation task once implemented
            clean_demdir(
                Path(self.outdir).joinpath(__DEM__),
                [
                    "*sigma*",
                    "*.linc",
                    "*.lv_phi",
                    "*.lv_theta",
                    "*.sim",
                    "*dem.tif",
                    "*gamma*",
                    "*.lt",
                    "*.png",
                    "*.lsmap",
                    "_",
                    "*.dem",
                    "*seamask.tif",
                ],
            )
            clean_slcdir(
                Path(self.outdir).joinpath(__SLC__),
                ["*.sigma0", "*.gamma0", "*.png", "*.slc", "*.kml", "*.bmp", "*.mli",],
            )

        with self.output().open("w") as f:
            f.write("")


class ProcessIFG(luigi.Task):
    """
    Runs the interferogram processing tasks.
    """

    proc_file = luigi.Parameter()
    track = luigi.Parameter()
    frame = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()
    cleanup = luigi.BoolParameter()

    master_date = luigi.Parameter()
    slave_date = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_ifg_{self.master_date}-{self.slave_date}_status_logs.out"
            )
        )

    def run(self):
        # Load the gamma proc config file
        with open(str(self.proc_file), 'r') as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        ic = IfgFileNames(proc_config, self.master_date, self.slave_date, self.outdir)
        dc = DEMFileNames(proc_config, self.outdir)
        tc = TempFileConfig(ic)

        # Run interferogram processing workflow w/ ifg width specified in r_master_mli par file
        with open(Path(self.outdir) / ic.r_master_mli_par, 'r') as fileobj:
            ifg_width = get_ifg_width(fileobj)

        run_workflow(
            proc_config,
            ic,
            dc,
            tc,
            ifg_width,
            self.cleanup)

        with self.output().open("w") as f:
            f.write("")

@requires(CreateCoregisterSlaves)
class CreateProcessIFGs(luigi.Task):
    """
    Runs the interferogram processing tasks.
    """

    proc_file = luigi.Parameter()
    track = luigi.Parameter()
    frame = luigi.Parameter()
    outdir = luigi.Parameter()
    workdir = luigi.Parameter()
    cleanup = luigi.BoolParameter()

    def output(self):
        return luigi.LocalTarget(
            Path(self.workdir).joinpath(
                f"{self.track}_{self.frame}_create_ifgs_status_logs.out"
            )
        )

    def run(self):
        log = STATUS_LOGGER.bind(track_frame=f"{self.track}_{self.frame}")
        log.info("Process interferograms task")

        # Load the gamma proc config file
        with open(str(self.proc_file), 'r') as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        # Parse ifg_list to schedule jobs for each interferogram
        with open(Path(self.outdir) / proc_config.list_dir / proc_config.ifg_list) as ifg_list_file:
            ifgs_list = [dates.split(",") for dates in ifg_list_file.read().splitlines()]

        jobs = []
        for master_date, slave_date in ifgs_list:
            jobs.append(
                ProcessIFG(
                    proc_file=self.proc_file,
                    track=self.track,
                    frame=self.frame,
                    outdir=self.outdir,
                    workdir=self.workdir,
                    cleanup=self.cleanup,
                    master_date=master_date,
                    slave_date=slave_date
                )
            )

        yield jobs

        with self.output().open("w") as f:
            f.write("")


class ARD(luigi.WrapperTask):
    """
    Runs the InSAR ARD pipeline using GAMMA software.

    -----------------------------------------------------------------------------
    minimum parameter required to run using default luigi Parameter set in luigi.cfg
    ------------------------------------------------------------------------------
    usage:{
        luigi --module process_gamma ARD
        --proc-file <path to the .proc config file>
        --vector-file <path to a vector file (.shp)>
        --start-date <start date of SLC acquisition>
        --end-date <end date of SLC acquisition>
        --workdir <base working directory where luigi logs will be stored>
        --outdir <output directory where processed data will be stored>
        --local-scheduler (use only local-scheduler)
        --workers <number of workers>
    }
    """

    proc_file = luigi.Parameter()
    vector_file_list = luigi.Parameter(significant=False)
    start_date = luigi.DateParameter(significant=False)
    end_date = luigi.DateParameter(significant=False)
    polarization = luigi.ListParameter(default=["VV", "VH"], significant=False)
    cleanup = luigi.BoolParameter(
        default=False, significant=False, parsing=luigi.BoolParameter.EXPLICIT_PARSING
    )
    outdir = luigi.Parameter(significant=False)
    workdir = luigi.Parameter(significant=False)
    database_name = luigi.Parameter()
    orbit = luigi.Parameter()
    dem_img = luigi.Parameter()
    multi_look = luigi.IntParameter()
    poeorb_path = luigi.Parameter()
    resorb_path = luigi.Parameter()

    def requires(self):
        log = STATUS_LOGGER.bind(vector_file_list=Path(self.vector_file_list).stem)

        # Coregistration processing
        ard_tasks = []

        with open(self.vector_file_list, "r") as fid:
            vector_files = fid.readlines()
            for vector_file in vector_files:
                vector_file = vector_file.rstrip()
                if not re.match(__TRACK_FRAME__, Path(vector_file).stem):
                    log.info(
                        f"{Path(vector_file).stem} should be of {__TRACK_FRAME__} format"
                    )
                    continue

                track, frame, sensor = Path(vector_file).stem.split("_")

                outdir = Path(str(self.outdir)).joinpath(f"{track}_{frame}")
                workdir = Path(str(self.workdir)).joinpath(f"{track}_{frame}")

                os.makedirs(outdir, exist_ok=True)
                os.makedirs(workdir, exist_ok=True)

                kwargs = {
                    "proc_file": self.proc_file,
                    "vector_file": vector_file,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                    "database_name": self.database_name,
                    "polarization": self.polarization,
                    "track": track,
                    "frame": frame,
                    "outdir": outdir,
                    "workdir": workdir,
                    "orbit": self.orbit,
                    "dem_img": self.dem_img,
                    "poeorb_path": self.poeorb_path,
                    "resorb_path": self.resorb_path,
                    "multi_look": self.multi_look,
                    "burst_data_csv": pjoin(outdir, f"{track}_{frame}_burst_data.csv"),
                    "cleanup": self.cleanup,
                }
                ard_tasks.append(CreateCoregisterSlaves(**kwargs))

                # IFG processing
                ard_tasks.append(CreateProcessIFGs(**kwargs))

        yield ard_tasks


def run():
    with open("insar-log.jsonl", "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))
        luigi.run()


if __name__ == "__name__":
    run()
