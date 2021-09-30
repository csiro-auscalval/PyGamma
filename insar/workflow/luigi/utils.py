import luigi
import datetime
import json
import shutil
from pathlib import Path
from typing import List, Tuple
import pandas as pd

from insar.project import ProcConfig
from insar.constant import SCENE_DATE_FMT

def read_file_line(filepath, line: int):
    """Reads a specific line from a text file"""
    with Path(filepath).open('r') as file:
        return file.read().splitlines()[line]


def calculate_primary(scenes_list) -> datetime:
    slc_dates = [
        datetime.datetime.strptime(scene.strip(), SCENE_DATE_FMT).date()
        for scene in scenes_list
    ]
    return sorted(slc_dates, reverse=True)[int(len(slc_dates) / 2)]


def read_primary_date(outdir: Path):
    with (outdir / 'lists' / 'primary_ref_scene').open() as f:
        date = f.readline().strip()

    return datetime.datetime.strptime(date, SCENE_DATE_FMT).date()


one_day = datetime.timedelta(days=1)


def merge_overlapping_date_ranges(dates: List[Tuple[datetime.date]]) -> List[Tuple[datetime.date]]:
    if not dates:
        return dates

    dates = sorted(dates, key=lambda x: x[0])
    result = []
    current = dates[0]

    # Range should be (from, to)
    if(current[1] < current[0]):
        raise RuntimeError("Provided date ranges should be (min, max) order")

    for date in dates[1:]:
        lhs, rhs = date

        # Range should be (from, to)
        if(rhs < lhs):
            raise RuntimeError("Provided date ranges should be (min, max) order")

        # Simple 1D line intersection of date ranges
        overlaps = (current[1] + one_day) >= lhs and (rhs + one_day) >= current[0]

        if overlaps:
            current = (min(current[0], lhs), max(current[1], rhs))
        else:
            result.append(current)
            current = date

    result.append(current)
    return result


def simplify_dates(include_dates: List[Tuple[datetime.date]], exclude_dates: List[Tuple[datetime.date]]) -> List[Tuple[datetime.date]]:
    # Merge include dates (eg: if they overlap), this will return a sorted result
    simple_includes = merge_overlapping_date_ranges(include_dates)
    simple_excludes = merge_overlapping_date_ranges(exclude_dates)

    final_include_ranges = []

    # Note: We iterate w/ dynamic index as the list may grow while iterating
    i = 0
    while i < len(simple_includes):
        lhs, rhs = simple_includes[i]

        for exclude_lhs, exclude_rhs in simple_excludes:
            # Remove whole range
            if lhs >= exclude_lhs and rhs <= exclude_rhs:
                lhs, rhs = None, None
            # Split down center
            elif exclude_lhs > lhs and exclude_rhs < rhs:
                simple_includes.append((exclude_rhs + one_day, rhs))
                rhs = exclude_lhs - one_day
            # Chop off the left
            elif lhs >= exclude_lhs and lhs <= exclude_rhs:
                lhs = exclude_rhs + one_day
            # Chop off the right
            elif rhs >= exclude_lhs and rhs <= exclude_rhs:
                rhs = exclude_lhs - one_day

        if lhs is not None and rhs is not None:
            final_include_ranges.append((lhs, rhs))

        i += 1

    return final_include_ranges


class ListParameter(luigi.Parameter):
    """A parameter whose value is in fact a list of comma separated values."""

    def parse(self, arguments):
        return None if arguments is None else arguments.split(",")


class PathParameter(luigi.Parameter):
    """A parameter whose value is a file path."""

    def parse(self, arguments):
        return None if not arguments else Path(arguments)


class DateListParameter(luigi.Parameter):
    """
    A Parameter whose value is a list of :py:class:`~luigi.date_interval.DateInterval`.

    See: https://luigi.readthedocs.io/en/stable/api/luigi.parameter.html#luigi.parameter.DateIntervalParameter
    """
    def parse(self, s):
        if not s:
            return []

        from luigi import date_interval as d

        # Handle tuple and list syntax as well (Luigi often uses tuple, command line supports anything)
        s = s.strip("[](), ")
        if not s:
            return []

        dates = [i.strip() for i in s.split(',')]
        value = []

        for date in dates:
            interval = None

            for cls in [d.Year, d.Month, d.Week, d.Date, d.Custom]:
                interval = cls.parse(date)
                if interval is not None:
                    break

            if interval is None:
                raise ValueError('Invalid date interval - could not be parsed: ' + s + " (type: " + str(type(s)) + ")")

            value.append(interval)

        return value


# TODO: This should take a primary polarisation to filter on
def get_scenes(burst_data_csv):
    df = pd.read_csv(burst_data_csv)
    if len(df) == 0:
        return []

    scene_dates = [_dt for _dt in sorted(df.date.unique())]

    frames_data = []

    for _date in scene_dates:
        df_subset = df[df["date"] == _date]
        if len(df_subset) == 0:
            continue

        polarizations = df_subset.polarization.unique()
        # TODO: This filter should be to primary polarisation
        # (which is not necessarily polarizations[0])
        df_subset_new = df_subset[df_subset["polarization"] == polarizations[0]]
        if len(df_subset_new) == 0:
            continue

        complete_frame = True
        for swath in [1, 2, 3]:
            swath_df = df_subset_new[df_subset_new.swath == "IW{}".format(swath)]
            swath_df = swath_df.sort_values(by="acquisition_datetime", ascending=True)
            for row in swath_df.itertuples():
                missing_bursts = row.missing_primary_bursts.strip("][")
                if missing_bursts:
                    complete_frame = False

        # HACK: Until we implement https://github.com/GeoscienceAustralia/gamma_insar/issues/200
        # - this simply refuses to present any scene with missing bursts to the luigi workflow
        assert(complete_frame)

        dt = datetime.datetime.strptime(_date, "%Y-%m-%d")
        frames_data.append((dt, complete_frame, polarizations))

    return frames_data

def mk_clean_dir(path: Path):
    # Clear directory in case it has incomplete data from an interrupted run we've resumed
    if path.exists():
        shutil.rmtree(path)

    path.mkdir(parents=True, exist_ok=True)

def read_rlks_alks(ml_file: Path):
    with ml_file.open("r") as src:
        for line in src.readlines():
            if line.startswith("rlks"):
                rlks = int(line.strip().split(":")[1])
            if line.startswith("alks"):
                alks = int(line.strip().split(":")[1])

    return rlks, alks

def tdir(workdir):
    return Path(workdir) / 'tasks'

def load_settings(proc_file: Path):
    # Load the gamma proc config file
    with proc_file.open("r") as proc_fileobj:
        proc_config = ProcConfig.from_file(proc_fileobj)

    outdir = Path(proc_config.output_path)

    # Load project metadata
    with (outdir / "metadata.json").open("r") as file:
        metadata = json.load(file)

    return proc_config, metadata
