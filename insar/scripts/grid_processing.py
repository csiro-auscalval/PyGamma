#!/usr/bin/env python

import os
import yaml
import click
import datetime
import structlog
from pathlib import Path
from os.path import exists, join as pjoin

from spatialist.ancillary import finder
from insar.meta_data.s1_gridding_utils import generate_slc_metadata

from insar.meta_data.s1_slc import Archive
from insar.logs import COMMON_PROCESSORS

structlog.configure(processors=COMMON_PROCESSORS)
_LOG = structlog.get_logger("insar")


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
                # In response to issue #84, errors using finder() arise
                # when grid_dir is a file instead of a directory. Check.
                if not os.path.isdir(grid_dir):
                    # this is a file - go to next file
                    continue

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
                                archive.archive_scene(generate_slc_metadata(Path(scene)))
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
    help=("Ingestion of Sentinel-1 slc metadata (yaml format) " "into a SQLite database"),
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
