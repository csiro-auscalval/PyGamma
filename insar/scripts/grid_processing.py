#!/usr/bin/env python

import os
from typing import Optional
from os.path import exists, isdir, join as pjoin, split, splitext
from pathlib import Path
import datetime
import re
import math
import logging

import click
from spatialist.ancillary import finder
from insar.meta_data.s1_gridding_utils import generate_slc_metadata, grid_adjustment, grid_definition
from insar.meta_data.s1_slc import Archive

_LOG = logging.getLogger(__name__)
GRID_NAME_FMT = "{track}_{frame}{ext}"


@click.group()
@click.version_option()
def cli():
    """
    Command line interface parent group
    """


@cli.group(
    name="slc-archive",
    help="handles injestion of slc acquistion details into the database",
)
def slc_archive_cli():
    """
    Sentinel-1 slc injestion command group
    """


@cli.group(name="grid-definition", help="process Sentinel-1 grid definition")
def grid_definition_cli():
    """
    Sentinel-1 grid definition command group
    """


@grid_definition_cli.command("grid-adjustment", help="Reconfigure the defined grid")
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
    default=r"^T[0-9]{3}[AD]_F[0-9]{2}[SN]",
)
def process_grid_adjustment(input_path: Path, out_dir: Path, pattern: str):
    """
    A method to process the grid adjustment for InSAR grid auto-generated grid definition
    from grid_definition method.
    """

    def _get_required_grids(vector_file, vector_file_dir):
        if re.match(pattern, vector_file):
            name_pcs = re.split(r"[_](?=[ADF])", vector_file)
            track = name_pcs[0]
            frame, ext = splitext(name_pcs[1])
            frame_num = int(re.findall(r"\d+", frame)[0])
            before_frame = re.sub(r"\d+", "{:02}".format(frame_num - 1), frame)
            after_frame = re.sub(r"\d+", "{:02}".format(frame_num + 1), frame)
            grid_before = pjoin(
                vector_file_dir,
                GRID_NAME_FMT.format(track=track, frame=before_frame, ext=ext),
            )
            grid_after = pjoin(
                vector_file_dir,
                GRID_NAME_FMT.format(track=track, frame=after_frame, ext=ext),
            )
            if not exists(grid_before):
                grid_before = None
            if not exists(grid_after):
                grid_after = None
            return track, frame, grid_before, grid_after

        raise ValueError

    def _process_adjustment(in_path):
        dir_name, file_name = split(in_path)
        try:
            track, frame, grid_before_path, grid_after_path = _get_required_grids(
                file_name, dir_name
            )
        except ValueError as err:
            _LOG.error(
                "vector file {} does match {} pattern".format(file_name, pattern)
            )
            raise err
        try:
            grid_adjustment(
                in_path,
                pjoin(out_dir, file_name),
                track=track,
                frame=frame,
                grid_before_shapefile=grid_before_path,
                grid_after_shapefile=grid_after_path,
            )
        except ValueError:
            _LOG.error("{} does not have data in all three swaths".format(file_name))
        except AttributeError:
            _LOG.error(
                "{} does not have data in a swath after grid adjustment".format(
                    file_name
                )
            )

    if not isdir(input_path):
        if input_path.endswith(".shp"):
            _process_adjustment(input_path)
            return
        _LOG.error("{} is not of type .shp file".format(os.path.basename(input_path)))
        raise TypeError

    for fid in os.listdir(input_path):
        in_file = pjoin(input_path, fid)
        if in_file.endswith(".shp"):
            _process_adjustment(in_file)
        else:
            _LOG.info("{} is not of type .shp file".format(fid))


@grid_definition_cli.command(
    "grid-generation", help="produces a grid definition for Sentinel-1 relative orbit"
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
    "--hemisphere",
    type=str,
    default="S",
    help="define grid in southern[S] or northern[N] hemisphere",
)
@click.option(
    "--sensor",
    type=str,
    default=None,
    help="Sentinel-1A (S1A) or 1B (S1B), default=None selects both S1A and S1B sensors",
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
    default=1.25,
    help="how wide the grid should be in latitude (in decimal degrees)",
)
@click.option(
    "--latitude-buffer",
    type=float,
    default=0.01,
    help="overlap between two grids in latitude (in decimal degrees)",
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
    hemisphere: str,
    relative_orbit_number: int,
    sensor: str,
    orbits: str,
    latitude_width: float,
    latitude_buffer: float,
    start_date: Optional[click.DateTime] = None,
    end_date: Optional[click.DateTime] = None,
):
    """
    A method to process InSAR grid definition for given rel_orbits
    """
    frame_numbers = [i + 1 for i in range(math.ceil(90.0 / latitude_width))]
    grid_definition(
        database_path,
        out_dir,
        relative_orbit_number,
        hemisphere,
        sensor,
        orbits,
        latitude_width,
        latitude_buffer,
        start_date,
        end_date,
        frame_numbers,
    )


@slc_archive_cli.command(
    "slc-injestion", help="slc acquistion details injestion into the database"
)
@click.option(
    "--database-name",
    type=click.Path(dir_okay=False, file_okay=True),
    required=True,
    help="name of database to injest slc acquistion details into",
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
    help="Sentinel-1 acquistion month",
)
@click.option(
    "--slc-dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False),
    required=True,
    help="base directory where slc data are stored",
)
def process_slc_injestion(
    database_name: click.Path, year: int, month: int, slc_dir: click.Path
):
    """
    Method to ingest slc scenes into the database
    """
    month_dir = pjoin(slc_dir, "{:04}".format(year), "{:04}-{:02}".format(year, month))
    try:
        for grid in os.listdir(month_dir):
            grid_dir = pjoin(month_dir, grid)
            scenes_slc = finder(
                str(grid_dir), [r"^S1[AB]_IW_SLC.*\.zip"], regex=True, recursive=True
            )
            for scene in scenes_slc:
                try:
                    with Archive(database_name) as archive:
                        archive.archive_scene(generate_slc_metadata(scene))
                except (AssertionError, ValueError, TypeError) as err:
                    _LOG.error("{}: {}".format(scene, err))
    except IOError as err:
        _LOG.error("{} does not exists".format(month_dir))
        raise IOError(err)


if __name__ == "__main__":
    cli()
