#!/usr/bin/env python

import os
import re
import sys
import math
import yaml
import click
import datetime
import structlog
import numpy as np
from pathlib import Path
from typing import Optional
from os.path import exists, isdir, join as pjoin, split, splitext

from spatialist.ancillary import finder
from insar.meta_data.s1_gridding_utils import (
    generate_slc_metadata,
    grid_adjustment,
    grid_definition,
)
from insar.meta_data.s1_slc import Archive
from insar.logs import COMMON_PROCESSORS, STATUS_LOGGER

structlog.configure(processors=COMMON_PROCESSORS)
_LOG = structlog.get_logger("insar")
GRID_NAME_FMT = "{track}_{frame}{ext}"


# ----------------------------------------- #
#                                           #
#   Defining the click groups:              #
#       - slc-archive                       #
#       - grid-definition                   #
#       - create-task-files                 #
#                                           #
#   New groups also need to be added to     #
#   the entry_points in setup.py            #
#                                           #
# ----------------------------------------- #
@click.group()
@click.version_option()
def cli():
    """
    Command line interface parent group
    """


# add slc-archive group to cli()
@cli.group(
    name="slc-archive",
    help="handles ingestion of slc acquisition details into sqlite databases",
)
def slc_archive_cli():
    """
    Sentinel-1 slc ingestion command group
    """


# add grid-definition group to cli()
@cli.group(
    name="grid-definition", help="Create and adjust Sentinel-1 track and frames",
)
def grid_definition_cli():
    """
    Sentinel-1 track and frame creation and adjustment command group
    """


# add pbs-task-file-creation to cli()
@cli.group(
    name="create-task-files",
    help="creates task files that are used in pbs batch processing",
)
def create_task_files_cli():
    """
    creation of task .txt files that are used in pbs batch processing
    """


# -------------------------------------------- #
# -------------------------------------------- #
#                                              #
#    task-files group                          #
#                                              #
# -------------------------------------------- #
# -------------------------------------------- #
@create_task_files_cli.command(
    "insar-files", help="Generate input files for inSAR pbs jobs",
)
@click.option(
    "--input-path",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    help="Path to grid definition/adjusted shape files",
    required=True,
)
@click.option(
    "--out-dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, writable=True),
    help="output directory where task files are created",
    default=Path(os.getcwd()),
)
def insar_task_files(
    input_path: click.Path, out_dir: click.Path,
):
    """

    Parameters
    ----------
    input_path: Path
        Path to the parent directory containing the
        grid-definition/adjustment shape files

    out_dir: Path
        Path to a directory to store adjusted grid definition files.

    """

    # iterate through shp files in input_path
    # and extract the unique listings of the
    # track names.
    all_tracks = []
    shape_files = []
    for f in os.listdir(input_path):
        full_f = pjoin(input_path, f)
        if os.path.isfile(full_f) and f.lower().endswith(".shp"):
            shape_files.append(full_f)
            all_tracks.append(f.split("_")[0])

    all_tracks = np.array(all_tracks, order="C")
    shape_files = np.array(shape_files, order="C")

    # iterate through the unique tracks and obtain all frames
    for track in np.unique(all_tracks):
        shp_for_track = shape_files[all_tracks == track]

        out_filename = pjoin(out_dir, "input_list_{}.txt".format(track))

        with open(out_filename, "w") as fid:
            fid.write("\n".join(shp_for_track))


# -------------------------------------------- #
# -------------------------------------------- #
#                                              #
#   grid definition group:                     #
#       - grid-generation-new (recommended)    #
#       - grid-generation (legacy)             #
#       - grid-adjustment                      #
#                                              #
# -------------------------------------------- #
# -------------------------------------------- #
@grid_definition_cli.command(
    "grid-adjustment", help="Reconfigure the defined grid",
)
@click.option(
    "--input-path",
    type=click.Path(exists=True, dir_okay=True, file_okay=True),
    help="Path to grid definition vector file(s)",
    required=True,
)
@click.option(
    "--out-dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    help="directory to output grid adjustment vector file(s)",
    default=os.getcwd(),
)
@click.option(
    "--pattern",
    type=str,
    help="regex pattern to match the vector filename",
    default=r"^T[0-9]{3}[AD]_F[0-9]{2}",
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to contain the logging events.",
    default="grid-adjustment.jsonl",
)
@click.option(
    "--create-kml",
    default=False,
    is_flag=True,
    help="If specified, saves kml files of the bursts for each frame",
)
def process_grid_adjustment(
    input_path: Path,
    out_dir: Path,
    pattern: str,
    log_pathname: click.Path,
    create_kml: click.BOOL,
):
    """
    A method to process the grid adjustment for InSAR grid auto-
    generated grid definition.

    This grid adjustment is for bulk grid adjustment process. It
    assumes that all the grid definition required to perform
    resides in input_path and naming conventions are as genrated
    by grid_definition process. For more user control on individual
    grid adjustment check metadata.s1_gridding_utils.grid_adjustment.

    Parameters
    ----------
    input_path: Path
        A full path to grid-definition input files parent directory.

    out_dir: Path
        A full path to a directory to store adjusted grid definition
        files.

    pattern: str
        regex pattern search for shp filenames that were created during
        grid-definition

    log_pathname: Path
        Path of log file

    create_kml: bool
        Create kml (True or False). kml files are created in out_dir

    """

    def _get_required_grids(
        vector_file, vector_file_dir,
    ):
        _LOG.info("processing _get_required_grids", pathname=vector_file)

        if re.match(pattern, vector_file):
            name_pcs = re.split(r"[_](?=[ADF])", vector_file)
            track = name_pcs[0]
            frame, ext = splitext(name_pcs[1])
            frame_num = int(re.findall(r"\d+", frame)[0])
            before_frame = re.sub(r"\d+", "{:02}".format(frame_num - 1), frame,)
            after_frame = re.sub(r"\d+", "{:02}".format(frame_num + 1), frame,)
            grid_before = pjoin(
                vector_file_dir,
                GRID_NAME_FMT.format(track=track, frame=before_frame, ext=ext,),
            )
            grid_after = pjoin(
                vector_file_dir,
                GRID_NAME_FMT.format(track=track, frame=after_frame, ext=ext,),
            )
            if not exists(grid_before):
                grid_before = None

            if not exists(grid_after):
                grid_after = None

            return track, frame, grid_before, grid_after

        raise ValueError

    def _process_adjustment(in_path):
        _LOG.info("processing _process_adjustment", pathname=in_path)

        dir_name, file_name = split(in_path)
        try:
            (track, frame, grid_before_path, grid_after_path,) = _get_required_grids(
                file_name, dir_name
            )
        except ValueError as err:
            _LOG.error(
                "vector filename pattern mismatch", pathname=file_name, pattern=pattern,
            )
            raise err

        try:
            grid_adjustment(
                in_grid_shapefile=in_path,
                out_grid_shapefile=pjoin(out_dir, file_name),
                create_kml=create_kml,
                track=track,
                frame=frame,
                grid_before_shapefile=grid_before_path,
                grid_after_shapefile=grid_after_path,
            )
        except ValueError:
            _LOG.error("data is required in all three swaths", pathname=file_name)
        except AttributeError:
            _LOG.error("no data in swath after grid adjustment", pathname=file_name)

    with open(log_pathname, "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))

        if not isdir(input_path):
            if input_path.endswith(".shp"):
                _process_adjustment(input_path)
                return
            _LOG.error("file is not an ESRI Shapefile", pathname=input_path)
            raise TypeError

        for fid in os.listdir(input_path):
            in_file = pjoin(input_path, fid)
            if in_file.endswith(".shp"):
                _process_adjustment(in_file)
            else:
                _LOG.error("file is not an ESRI Shapefile; skipping", pathname=in_file)


@grid_definition_cli.command(
    "grid-generation", help="produces a grid definition for Sentinel-1 relative orbit",
)
@click.option(
    "--database-path",
    type=click.Path(exists=True, dir_okay=False, file_okay=True),
    required=True,
    help="full path to a sqlite database name",
)
@click.option(
    "--out-dir",
    type=click.Path(dir_okay=True, file_okay=False, writable=True),
    default=os.getcwd(),
    help="directory to output grid vector files",
)
@click.option(
    "--relative-orbit-number",
    type=int,
    required=True,
    help="relative orbit number of Sentinel-1",
)
@click.option(
    "--sensor",
    type=str,
    default=None,
    help=(
        "Sentinel-1A (S1A) or 1B (S1B), default=None selects both S1A "
        "and S1B sensors"
    ),
)
@click.option(
    "--orbits",
    type=str,
    default="D",
    help="Sentinel-1 overpass ascending [A] or descending [D]",
)
@click.option(
    "--latitude-width",
    type=float,
    default=-1.25,
    help=(
        "The latitude length of the grid (in decimal degrees, " "and must be negative)"
    ),
)
@click.option(
    "--latitude-buffer",
    type=float,
    default=0.01,
    help=(
        "overlap between two grids in latitude (in decimal "
        "degrees, and must be positive)"
    ),
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to contain the logging events.",
    default="grid-generation.jsonl",
)
@click.option(
    "--start-date",
    type=click.DateTime(),
    default=None,
    help="start date to begin query into database",
)
@click.option(
    "--end-date",
    type=click.DateTime(),
    default=None,
    help="end date to stop query into database",
)
def process_grid_definition(
    database_path: click.Path,
    out_dir: click.Path,
    relative_orbit_number: int,
    sensor: str,
    orbits: str,
    latitude_width: float,
    latitude_buffer: float,
    log_pathname: click.Path,
    start_date: Optional[click.DateTime] = None,
    end_date: Optional[click.DateTime] = None,
):
    """
    A method to process InSAR grid definition for given rel_orbits

    legacy code that should not be used
    """
    with open(log_pathname, "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))
        grid_definition(
            dbfile=database_path,
            out_dir=out_dir,
            rel_orbit=relative_orbit_number,
            sensor=sensor,
            orbits=orbits,
            create_kml=False,
            latitude_width=latitude_width,
            latitude_buffer=latitude_buffer,
            start_date=start_date,
            end_date=end_date,
        )


@grid_definition_cli.command(
    "grid-generation-new",
    help="produces a grid definition for Sentinel-1 (new version)",
)
@click.option(
    "--database-path",
    type=click.Path(exists=True, dir_okay=False, file_okay=True),
    required=True,
    help="full path to a sqlite database name",
)
@click.option(
    "--out-dir",
    type=click.Path(dir_okay=True, file_okay=False, writable=True),
    default=os.getcwd(),
    help="directory to output grid vector files",
)
@click.option(
    "--latitude-width",
    type=float,
    default=-1.25,
    help=(
        "The latitude length of the grid (in decimal degrees, " "and must be negative)"
    ),
)
@click.option(
    "--latitude-buffer",
    type=float,
    default=0.01,
    help=(
        "overlap between two grids in latitude (in decimal degrees, "
        "and must be positive)"
    ),
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to contain the logging events.",
    default="grid-generation.jsonl",
)
@click.option(
    "--create-kml",
    default=False,
    is_flag=True,
    help="If specified, saves kml files of the bursts for each frame",
)
@click.option(
    "--relative-orbit-number",
    type=int,
    default=None,
    help="relative orbit number of Sentinel-1",
)
@click.option(
    "--sensor",
    type=str,
    default=None,
    help=(
        "Sentinel-1A (S1A) or 1B (S1B), default=None selects "
        "both S1A and S1B sensors"
    ),
)
@click.option(
    "--orbits",
    type=str,
    default=None,
    help="Sentinel-1 overpass ascending [A] or descending [D]",
)
@click.option(
    "--start-date",
    type=click.DateTime(),
    default=None,
    help="start date to begin query into database",
)
@click.option(
    "--end-date",
    type=click.DateTime(),
    default=None,
    help="end date to stop query into database",
)
@click.option(
    "--northern-latitude",
    type=float,
    default=0.0,
    help="Northern latitude (decimal degrees North) of the bounding box",
)
@click.option(
    "--western-longitude",
    type=float,
    default=100.0,
    help="Western longitude (decimal degrees East) of the bounding box",
)
@click.option(
    "--southern-latitude",
    type=float,
    default=-50.0,
    help="Southern latitude (decimal degrees North) of the bounding box",
)
@click.option(
    "--eastern-longitude",
    type=float,
    default=179.0,
    help="Eastern longitude (decimal degrees East) of the bounding box",
)
def process_grid_definition_NEW(
    database_path: click.Path,
    out_dir: click.Path,
    latitude_width: float,
    latitude_buffer: float,
    log_pathname: click.Path,
    create_kml: click.BOOL,
    relative_orbit_number: Optional[int] = None,
    sensor: Optional[str] = None,
    orbits: Optional[str] = None,
    start_date: Optional[click.DateTime] = None,
    end_date: Optional[click.DateTime] = None,
    northern_latitude: Optional[float] = 0.0,
    western_longitude: Optional[float] = 100.0,
    southern_latitude: Optional[float] = -50.0,
    eastern_longitude: Optional[float] = 179.0,
):
    """
    Description
    -----------
    A method to define a consistent track and frame for Sentinel-1 over
    a given region-of-interest

    Updated method of inSAR track/frame creation, with the following
    additions:
    (1) relative_orbit_number as an optional input. Here, the senor
        and orbit inputs are used to determine  the unique listings
        of  the relative orbits. This  eliminates  the need for the
        user to specify the relative orbit number, which  typically
        isn't known beforehand.

    (2) optional lat/lon bounding box to generate shp files for a
        user specified region of interest.

    (3) removed hemisphere command as it was redundant

    (4) latitude width made negative to align with definition of the
        origin, being the northern-most latitude of the region-of-
        interest.

    (5) added an option to create kml files that contain the selected
        bursts for each frame in a given relative orbit number

    (6) Set sensor and orbit node to optional that default to None

    Parameters
    ----------
    database_path: Path
        A full path to sqlite database file created from slc-archive

    out_dir: Path
        A full path to a directory to store the shape files

    latitude_width: float
        latitude width of a given frame (decimal degrees, & negative).
        default = -1.25

    latitude_buffer: float
        overlapping buffer between subsequent frames (decimal degrees)
        default = 0.01

    log_pathname: Path
        Path of log file

    create_kml: bool
        Create kml (True or False). kml files are created in out_dir

    relative_orbit_number: int or None
        Relative orbit number of Sentinel-1

    sensor: str or None
        {'S1A' or 'S1B'} for Sentinel-1A and -1B respectively.
        default=None selects both S1A and S1B sensors

    orbits: str, None
        {'A' or 'D'} for Sentinel-1 ascending or descending nodes,
        respectively. default=None selects both A and D nodes

    start_date: DateTime, None
        Sentinel 1 acquisition start date

    end_date: DateTime, None
        Sentinel 1 acquisition end date

    northern_latitude: float, 0.0
        Northern latitude (decimal degrees North) of the bounding box

    western_longitude: float, 100.0
        Western longitude (decimal degrees East) of the bounding box

    southern_latitude: float, -50.0
        Southern latitude (decimal degrees North) of the bounding box

    eastern_longitude: float, 179.0
        Eastern longitude (decimal degrees East) of the bounding box
    """

    with open(log_pathname, "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))

        # ----------------------------------------- #
        #   check that the user bounding box is OK  #
        # ----------------------------------------- #
        if northern_latitude <= southern_latitude:
            err_str = (
                "input bounding box error, northern latitude" " <= southern latitude"
            )
            _LOG.error(
                err_str,
                northern_latitude=northern_latitude,
                southern_latitude=southern_latitude,
            )
            raise Exception(err_str + "\n")

        if eastern_longitude <= western_longitude:
            err_str = (
                "input bounding box error, eastern longitude" " <= western latitude"
            )
            _LOG.error(
                err_str,
                eastern_longitude=eastern_longitude,
                western_longitude=western_longitude,
            )
            raise Exception(err_str + "\n")

        # latitude width must be negative as the origin is the
        # northern latitude of the bounding box
        if latitude_width > 0:
            _LOG.warning(
                (
                    "input latitude width is positive, multiplying by -1"
                    " to convert it to negative"
                ),
                latitude_width=latitude_width,
            )
            latitude_width *= -1.0

        if latitude_width == 0:
            _LOG.error("input latitude width = 0, but expected latitude width < 0",)
            raise Exception("latitude width = 0, but expected latitude width < 0")

        # asserting latitude buffer > 0
        if latitude_buffer < 0:
            _LOG.warning(
                (
                    "input latitude (overlap) buffer is negative, taking "
                    "absolute value to convert it to positive"
                ),
                latitude_buffer=latitude_buffer,
            )
            latitude_buffer = abs(latitude_buffer)

        if latitude_buffer == 0:
            _LOG.error("input latitude buffer = 0, but expected latitude buffer > 0",)
            raise Exception("latitude buffer = 0, but expected latitude buffer > 0")

        # ensuring that orbits is 'A', 'D' or None
        orbit_node_list = None
        if orbits:
            if orbits.lower() == "a":
                orbit_node_list = ["A"]
            elif orbits.lower() == "d":
                orbit_node_list = ["D"]
            else:
                _LOG.error(
                    "expected orbit as 'A' or 'D'", input_orbit=orbits,
                )
                raise Exception("input orbit is neither 'A' nor 'D'")
        else:
            orbit_node_list = ["A", "D"]
        # ------------------------------------------- #
        #  first query the database and get a unique  #
        #    listing of the relative orbit numbers    #
        # ------------------------------------------- #
        with Archive(database_path) as archive:

            # loop through the orbits
            for orbit_node in orbit_node_list:
                uniq_relorb_nums = archive.get_rel_orbit_nums(
                    orbit_node=orbit_node,
                    sensor_type=sensor,
                    rel_orb_num=relative_orbit_number,
                )
                # uniq_relorb_nums can be None, [] or [1,2,3,....,N]

                # do not use "if not uniq_relorb_nums:" as None or
                # empty lists ([]) will be accepted
                if uniq_relorb_nums:
                    # relative orbit numbers were found
                    _LOG.info(
                        "Sucessfully extracted relative orbit numbers",
                        s1_sensor=sensor,
                        orbit_node=orbit_node,
                        extracted_rel_orbs=uniq_relorb_nums,
                        relative_orbit_num=relative_orbit_number,
                    )
                    # iterate through the relative orbit numbers and
                    # create the shapefiles:
                    for rel_orb in uniq_relorb_nums:
                        grid_definition(
                            dbfile=database_path,
                            out_dir=out_dir,
                            rel_orbit=rel_orb,
                            sensor=sensor,
                            create_kml=create_kml,
                            orbits=orbit_node,
                            latitude_width=latitude_width,
                            latitude_buffer=latitude_buffer,
                            start_date=start_date,
                            end_date=end_date,
                            bbox_nlat=northern_latitude,
                            bbox_wlon=western_longitude,
                            bbox_slat=southern_latitude,
                            bbox_elon=eastern_longitude,
                        )

                else:
                    # empty list or errors occured
                    _LOG.info(
                        "No relative orbit numbers were found",
                        s1_sensor=sensor,
                        orbit_node=orbit_node,
                        relative_orbit_num=relative_orbit_number,
                    )


# ----------------------------------------- #
# ----------------------------------------- #
#                                           #
#  SLC archive group:                       #
#        -  slc-ingestion                   #
#        -  slc-ingest-yaml                 #
#                                           #
# ----------------------------------------- #
# ----------------------------------------- #
@slc_archive_cli.command(
    "slc-ingestion", help="slc acquisition details ingestion into the database",
)
@click.option(
    "--database-name",
    type=click.Path(dir_okay=False, file_okay=True),
    required=True,
    help=(
        "name of database to ingest slc acquisition details "
        "(ignored if --save-yaml specified)"
    ),
)
@click.option(
    "--year",
    type=int,
    default=datetime.datetime.now().year,
    help="Sentinel-1 acquisition year",
)
@click.option(
    "--month",
    type=int,
    default=datetime.datetime.now().month,
    help="Sentinel-1 acquisition month",
)
@click.option(
    "--slc-dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    required=True,
    help="base directory where slc data are stored",
)
@click.option(
    "--save-yaml",
    default=False,
    is_flag=True,
    help="If specified, stores SLC metadata as a yaml",
)
@click.option(
    "--yaml-dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, writable=True),
    required=False,
    help="directory where the yaml SLC metadata will be stored",
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to a log file",
    default="slc-ingestion.jsonl",
)
def process_slc_ingestion(
    database_name: click.Path,
    year: int,
    month: int,
    slc_dir: click.Path,
    save_yaml: click.BOOL,
    yaml_dir: click.Path,
    log_pathname: str,
):
    """
    Description
    -----------
    A method to ingest slc metadata from the xml files inside
    Sentinel-1 zip files into:
    (1) a sqlite database, or;
    (2) a series of yaml files.

    Note that in (2), the yaml files stored in yaml-dir have the
    same directory structure as the Sentinel-1 database in
    /g/data/fj7/Copernicus/Sentinel-1/C-SAR/SLC

    Parameters
    ----------
    database_name: Path
        name of sqlite database to ingest slc acquisition details.
        Ignored if --save-yaml specified

    year: int
        the year of the Sentinel-1 acquisition

    month: int
        the month of the Sentinel-1 acquisition
        months represented as integer, for example:
         1 -> January
         2 -> February
         . ->  ...
        12 -> December

    slc_dir: Path
        base directory where slc data (i.e. Sentinel-1 zips) are stored
        /g/data/fj7/Copernicus/Sentinel-1/C-SAR/SLC

    save_yaml: bool
        If specified, stores SLC metadata as a yaml, in which case
        a sqlite database file is not created (i.e. database_name
        is ignored)

    yaml_dir: Path
        directory where the yaml SLC metadata will be stored

    log_pathname: str
        Output pathname to a log file

    """
    with open(log_pathname, "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))

        year_month = "{:04}-{:02}".format(year, month)
        slc_ym_dir = pjoin(slc_dir, str(year), year_month)
        try:
            for grid in os.listdir(slc_ym_dir):
                _LOG.info("processing grid", grid=grid)

                grid_dir = pjoin(slc_ym_dir, grid)
                scenes_slc = finder(
                    target=str(grid_dir),
                    matchlist=[r"^S1[AB]_IW_SLC.*\.zip"],
                    regex=True,
                    recursive=True,
                )

                for scene in scenes_slc:
                    _LOG.info("processing scene", scene=scene)
                    try:
                        # Merging a plethora of SQLite databases is a
                        # cumbersome task, especially for batch
                        # processing across multiple cores. An
                        # alternative solution is to simply save the
                        # SLC metadata as yaml in a user specified
                        # directory (yaml_dir), and then compile all
                        # the yaml files into a single SQLite database.
                        if save_yaml is True:
                            yaml_dir = Path(yaml_dir)
                            outdir = yaml_dir.joinpath(str(year), year_month, grid,)
                            generate_slc_metadata(Path(scene), outdir, True)
                        else:
                            with Archive(database_name) as archive:
                                archive.archive_scene(
                                    generate_slc_metadata(Path(scene))
                                )
                    except (AssertionError, ValueError, TypeError) as err:
                        _LOG.error(
                            "failed to execute generate_slc_metadata",
                            scene=scene,
                            err=err,
                        )

        except IOError as err:
            _LOG.error("directory does not exist", directory=slc_ym_dir)
            raise IOError(err)


# Create a child command of the slc-archive called slc-ingeest-yaml
@slc_archive_cli.command(
    "slc-ingest-yaml",
    help=(
        "Ingestion of Sentinel-1 slc metadata (yaml format) " "into a SQLite database"
    ),
)
@click.option(
    "--database-name",
    type=click.Path(dir_okay=False, file_okay=True),
    required=True,
    help="output SQLite database (.db) containing slc acquisition metadata",
)
@click.option(
    "--yaml-dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, writable=True),
    required=True,
    help="directory containing yaml files that will be ingested",
)
@click.option(
    "--log-pathname",
    type=click.Path(dir_okay=False),
    help="Output pathname to a log file",
    default="yaml-ingestion.jsonl",
)
def ingest_slc_yamls(
    database_name: click.Path, yaml_dir: click.Path, log_pathname: str,
):
    """
    Description
    -----------
    A method to ingest slc metadata from yaml files into a sqlite
    database. This command needs to be run if the --save_yaml
    commandline argument was used in slc-archive slc-ingestion

    Parameters
    ----------
    database_name: Path
        output SQLite database (.db) containing slc acquisition
        metadata

    yaml_dir: Path
        directory containing yaml files that will be ingested

    log_pathname: str
        Output pathname to a log file

    """

    with open(log_pathname, "w") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj))

        ## Get yaml files from input directory (yaml_dir)
        yaml_slc_files = finder(
            yaml_dir, [r"S1[AB]_IW_SLC.*\.yaml"], regex=True, recursive=True
        )
        for yaml_file in yaml_slc_files:
            _LOG.info("processing yaml", pathname=yaml_file)

            if not exists(yaml_file):
                _LOG.warning("file not found; skipping", pathname=yaml_file)
                continue

            ## Load yaml files
            try:
                with open(yaml_file, "r") as in_fid:
                    slc_metadata = yaml.load(in_fid, Loader=yaml.FullLoader)

                ## Generate Archive
                with Archive(database_name) as archive:
                    archive.archive_scene(slc_metadata)

            except (AssertionError, ValueError, TypeError, IOError) as err:
                _LOG.error("failed", pathname=yaml_file, err=err)


if __name__ == "__main__":
    cli()
