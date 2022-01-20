import datetime
import itertools
import json
from pathlib import Path
import re
import pandas as pd
import geopandas as gpd

from typing import Optional, List, Tuple, Union

from insar.project import ProcConfig
from insar.constant import SCENE_DATE_FMT
from insar.sensors import identify_data_source, get_data_swath_info
from insar.generate_slc_inputs import query_slc_inputs, slc_inputs
from insar.logs import STATUS_LOGGER

# TODO: We may need to split this up:
# * query utils should be their own file for sure
# * some of these functions would be best built on SlcPaths, but SlcPaths depends on some of these functions...

def load_stack_config(stack_proc_path: Union[str, Path]) -> ProcConfig:
    """
    Loads a stack's .proc config file from a supplied stack path.

    :param stack_proc_path:
        A path either directly to a stack's config.proc file that resides in the stack's
        output directory, or alternatively this may be a path to either the stack's
        output or job directories (which will be used to find the stack's .proc file)
    :returns:
        The stack's loaded ProcConfig
    """

    stack_proc_path = Path(stack_proc_path)

    if not stack_proc_path.exists():
        raise ValueError("Specified path does not exist!")

    if stack_proc_path.is_dir():
        # This is kind of a "hack", but still legitimate & slightly faster...
        # We check for a config.proc straight up in case this is the dir we're looking
        # for - this avoids indirection via the metadata.json, but mostly it's to make
        # our SLC unit testing lives easier (w/o having to setup a stack)
        config = stack_proc_path / "config.proc"
        if config.exists():
            return load_stack_config(config)

        metadata = stack_proc_path / "metadata.json"
        if not metadata.exists():
            raise ValueError("Expected stack dir - metadata.json missing from specified directory!")

        with metadata.open("r") as file:
            metadata = json.load(file)

        og_config = Path(metadata["original_work_dir"]) / "config.proc"

        return load_stack_config(og_config)

    else:
        if stack_proc_path.suffix != ".proc":
            raise ValueError("Expected stack dir or .proc config file!")

        with stack_proc_path.open("r") as proc_file_obj:
            return ProcConfig.from_file(proc_file_obj)


def load_stack_list_file(path: Path) -> List[Union[str, List[str]]]:
    """A simple helper function for loading stack list directory files of all kinds"""

    results = path.read_text().splitlines()

    return [i.split(",") if "," in i else i for i in results]


def find_stack_list_series(base_file: Path):
    """
    This function loads a series of stack list files starting from a provided path
    in that series, returning that plus all subsequent in the series.

    :param base_file:
        The first path in the series of list files to load.
    :return:
        A list of paths for the series that the `base_file` belongs to,
        from the range of `base_file` (inclusive) until the end.
    """
    result = []

    list_dir = base_file.parent
    list_id = base_file.stem.strip("0123456789")
    list_suffix = base_file.suffix
    base_idx = base_file.stem.replace(list_id, "")

    # Un-indexed file doesn't need to exist (mostly for ifgs.list, but we allow it across the board)
    if not base_idx:
        path = list_dir / f"{list_id}{list_suffix}"
        if path.exists():
            result.append(path)

    # Indexed files all have to exist in sequence
    base_idx = int(base_idx or 1)
    path = list_dir / f"{list_id}{base_idx}{list_suffix}"

    while path.exists():
        result.append(path)

        base_idx += 1
        path = list_dir / f"{list_id}{base_idx}{list_suffix}"

    return result


def load_stack_list_series(base_file: Path) -> List[List[Union[str, List[str]]]]:
    paths = find_stack_list_series(base_file)

    return [load_stack_list_file(i) for i in paths]


def load_stack_scene_dates(proc_config: ProcConfig) -> List[List[str]]:
    list_dir = proc_config.output_path / proc_config.list_dir

    return load_stack_list_series(list_dir / "scenes.list")


def load_stack_ifg_pairs(proc_config: ProcConfig) -> List[List[Tuple[str,str]]]:
    list_dir = proc_config.output_path / proc_config.list_dir

    return load_stack_list_series(list_dir / "ifgs.list")


def load_stack_scenes(proc_config: ProcConfig) -> List[Tuple[datetime.date, List[Path]]]:
    scene_dates = load_stack_scene_dates(proc_config)
    slc_dir = Path(proc_config.output_path) / proc_config.slc_dir
    result = []

    for date in itertools.chain(*scene_dates):
        scene_dir = slc_dir / date
        if not scene_dir.exists():
            continue

        date = datetime.datetime.strptime(date, SCENE_DATE_FMT).date()

        metadata_files = list(scene_dir.glob("metadata_*.json"))
        metadata = json.loads(metadata_files[0].read_text())

        source_files_for_date = []

        for values in metadata.values():
            if "src_url" in values:
                source_files_for_date.append(Path(values["src_url"]))

        result.append((date, source_files_for_date))

    return result


def resolve_stack_scene_additional_files(
    slc_inputs_df: pd.DataFrame,
    proc_config: ProcConfig,
    polarisations: List[str],
    include_source_files: List[Path],
    shape_file: Optional[Path] = None,
) -> pd.DataFrame:
    """
    This function inserts additional source files into a stack query
    by resolving their dates and determining burst availability before
    finally inserting them into the stack's pandas dataframe.

    In addition to determining burst availability, if a shapefile is provided which
    contains burst information - that burst information is used as a 'reference'
    which is then used to determine 'missing' bursts (eg: what bursts a scene does
    not have, which the shapefile does).  This matches the geospatial DB logic.

    :param slc_inputs_df:
        A pandas dataframe to append resolved scenes into.
    :param proc_config:
        The stack .proc config which contains all the stack's processing information.
    :param polarisations:
        The polarisations of interest to be extracted from source data / acquisitions.
    :param include_source_files:
        A list of source data paths to add into the stack / dataframe.
    :param shape_file:
        If a shapefile is provided AND contains burst information (for S1) it is used
        to filter out unwanted bursts in scenes from processing in the dataframe... as
        well as identify missing bursts that a date doesn't have (but shapefile does).

    :returns:
        A new dataframe which is a copy of the original with the newly resolved / additional
        scenes that were added by this function.
    """
    download_dir = Path(proc_config.output_path) / proc_config.raw_data_dir

    swath_info_by_date = {}

    # Gather swath information for all source files, grouping by date
    for data_path in include_source_files:
        _, _, scene_date = identify_data_source(data_path)

        if scene_date not in swath_info_by_date:
            swath_info_by_date[scene_date] = []

        for swath_data in get_data_swath_info(data_path, download_dir / scene_date):
            if swath_data["polarization"] not in polarisations:
                STATUS_LOGGER.info(
                    "Skipping source data which does not match stack polarisations",
                    source_file=data_path,
                    source_pol=swath_data["polarization"],
                    stack_pols=polarisations
                )
                continue

            swath_info_by_date[scene_date].append(swath_data)

    if shape_file is not None:
        shp_df = gpd.read_file(shape_file)

    # Add each date's swath data info to the stack dataframe
    for date, swath_data_list in swath_info_by_date.items():
        # If we have a shapefile, determine burst availability for each swath
        #
        # Note: all acquisitions swaths share the same burst availability in a date
        # - as it's expected if many acquisitions exist for a single date, they're
        # - concatenated together (as the stack is geometrically larger than a single
        # - satellite acquisition)
        if shape_file is not None:
            # Note: This only applies to S1, and only S1 will have swaths w/ these names
            for swath in ["IW1", "IW2", "IW3"]:
                shp_swath_df = shp_df[shp_df.swath == swath]
                contained_primary_bursts = []

                for swath_data in swath_data_list:
                    if swath_data["swath"] != swath:
                        continue

                    burst_numbers = swath_data["burst_number"]
                    burst_centroids = swath_data["burst_centroid"]
                    if not burst_centroids:
                        continue

                    contained_swath_bursts = []

                    # Remove the centroids from the data object (we don't want them recorded in dataframe)
                    del swath_data["burst_centroid"]

                    for idx, row in shp_swath_df.iterrows():
                        for burst_num, centroid in zip(burst_numbers, burst_centroids):
                            if row.geometry.contains(centroid):
                                contained_primary_bursts.append(row.burst_num)
                                contained_swath_bursts.append(burst_num)

                    # Rewrite "burst_number" to only include those included by the shapefile
                    swath_data["burst_number"] = contained_swath_bursts

                # TODO: de-duplicate shapefile burst availability logic w/ the same code
                # in generate_slc_inputs.py
                missing_bursts = set(shp_swath_df.burst_num.values) - set(contained_primary_bursts)
                missing_bursts = [int(i) for i in missing_bursts]

                for swath_data in swath_data_list:
                    if swath_data["swath"] != swath:
                        continue

                    swath_data["missing_primary_bursts"] = missing_bursts

        slc_inputs_df = slc_inputs_df.append(swath_data_list, ignore_index=True)

    return slc_inputs_df


def resolve_stack_scene_query(
    proc_config: ProcConfig,
    include_queries: List[Union[Path, datetime.date, Tuple[datetime.date, datetime.date], str]],
    sensors: List[str],
    orbit: str,
    polarisations: List[str],
    sensor_filters: List[Optional[str]],
    shape_file: Optional[Path] = None,
) -> Tuple[List[Tuple[datetime.date, List[Path]]], pd.DataFrame]:
    """
    Resolve a scene query (a set of dates, date ranges, or source data files) to a set
    of source data paths through a geospatial-temporal query from the scene DB using
    the provided shape-file (if none provided it's just a temporal query) that match
    the specified parameters (sensor/orbit/polarisation).

    :param proc_config:
        The stack .proc config which contains all the stack's processing information.
    :param include_queries:
        A list of either source data path's to use directly, or dates and date ranges to
        query the DB with for source data.
    :param sensors:
        A list of sensors to query scenes for.
    :param orbit:
        The orbit type to query scenes for ("A" for ascending, "D" for descending)
    :param polarisations:
        The polarisations scenes produced from the query must contain to be processed.
    :param sensor_filters:
        A list (one per `sensor` entry) of filters to apply to each sensor, varies by
        satellite constellation - to further refine what scenes from the query to
        accept into the stack.

        For `"S1"` satellites, allowed filters are: `["S1A", "S1B"]`
    :param shape_file:
        An optional shapefile to use which constrains the DB query w/ a geospatial extent
        in which to find scenes (if not provided, no geospatial constraint is applied).

        Additionally, if the shapefile contains burst information (for S1) it is also
        used to filter out unwanted bursts in scenes from processing - this is useful
        as not all S1 acquisitions are consistent (bursts in acquisitions vary over time).
        As well as identify what bursts from the shapefile are missing for each date (if any).

    :returns:
        Returns two values (scene_list, scene_dataframe).

        A list for every date in which at least one valid scene was identified, of elements
        that are tuples containing the date and a list of source data paths to acquisitions
        that matched the include query and passed all the specified filters.

        A dataframe which contains the satellite acquisition details for all identified scenes.
    """

    include_dates = []
    include_source_files = []

    for query in include_queries:
        # Strings may be a YYYYMMDD date, or a file path
        if isinstance(query, str):
            if re.match("\d{8}", query):
                query = datetime.datetime.strptime(query, SCENE_DATE_FMT).date()
                include_dates.append((query,query))

            else:
                include_source_files.append(Path(query))

        elif isinstance(query, tuple):
            assert(len(query) == 2)
            assert(all(isinstance(i, datetime.date) for i in query))

            include_dates.append(query)

        elif isinstance(query, datetime.date):
            include_dates.append((query,query))

        elif isinstance(query, Path):
            include_source_files.append(query)

    resolved_source_files = []
    slc_inputs_df = pd.DataFrame()

    if shape_file:
        for sensor, sensor_filter in zip(sensors, sensor_filters):
            # If we have a shape file, query the DB for scenes in that extent
            # TBD: The database geospatial/temporal query is currently Sentinel-1 only
            # GH issue: https://github.com/GeoscienceAustralia/gamma_insar/issues/261
            if sensor == "S1":
                # get the relative orbit number, which is int value of the numeric part of the track name
                # Note: This is S1 specific...
                rel_orbit = int(re.findall(r"\d+", str(proc_config.track))[0])

                # Find the maximum extent of the queried dates
                min_date = include_dates[0][0]
                max_date = max([d[1] for d in include_dates])

                # Query SLCs that match our search criteria for the maximum span
                # of dates that covers all of our include dates.
                slc_query_results = query_slc_inputs(
                    str(proc_config.database_path),
                    str(shape_file),
                    min_date,
                    max_date,
                    orbit,
                    rel_orbit,
                    polarisations,
                    sensor_filter
                )

                if slc_query_results is None:
                    continue

                slc_inputs_df = slc_inputs_df.append(
                    [slc_inputs(slc_query_results[pol]) for pol in polarisations],
                    ignore_index=True
                )

                # Filter out dates we don't care about - as our search query is for
                # a single giant span of dates, but our include dates may be more fine
                # grained than the query supports.
                exclude_indices = []

                for index, row in slc_inputs_df.iterrows():
                    date = row["date"]

                    keep = any(date >= lhs or date <= rhs for lhs,rhs in include_dates)
                    if not keep:
                        exclude_indices.append(index)

                slc_inputs_df.drop(exclude_indices, inplace=True)

            else:
                raise NotImplementedError(f"{sensor} does not support geospatial queries")

    # Add any explicit source data files into the "inputs" data frame
    slc_inputs_df = resolve_stack_scene_additional_files(
        slc_inputs_df,
        proc_config,
        polarisations,
        include_source_files,
        shape_file
    )

    # Convert to simpler date -> [source paths]
    if not slc_inputs_df.empty:
        for date in slc_inputs_df["date"].unique():
            urls = slc_inputs_df[slc_inputs_df["date"] == date].url.unique()
            urls = [Path(i) for i in urls.astype(str)]

            resolved_source_files.append((date, urls))

    # Note: returning both simplified and pandas data, both are useful in
    # different contexts / not sure it justifies two functions though
    return resolved_source_files, slc_inputs_df
