#!/usr/bin/env python

"""
   *** This is a legacy file that should not be used ***
   instead use the command line:
   create-task-files insar-files --input-path {/path/to/shps/} --out-dir {/path/to/output}

   Description
   A utility to generate task files that are inputs to pbs
   batch processing. Each task file contains all the shape
   files for a given track, e.g.

   input_list_T002D.txt :
   /path/to/shp/T002D_F09.shp
   /path/to/shp/T002D_F10.shp
   ....
   ....
   /path/to/shp/T002D_F27.shp

"""

# get a unique listing of the different tracks 
# for each unique track find the frames.
import os
import sys
import click
import numpy as np
from pathlib import Path
from os.path import join as pjoin

@click.group()
@click.version_option()
def cli():
    """
    Command line interface parent group
    """
@cli.command(
    name="create-task-files",
    help="creates task files that are used in pbs batch processing"
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
def generate_task_files(
    input_path: click.Path,
    out_dir: click.Path,
    ):
    """

    Parameters
    ----------
    input_path: Path
        Path to the parent directory containing the grid-definition/adjustment
        shape files

    out_dir: Path
        Path to a directory to store adjusted grid definition files.

    """

    # find the unique tracks
    all_tracks = []
    shape_files = []
    for f in  os.listdir(input_path):
        full_f = pjoin(input_path, f)
        if os.path.isfile(full_f) and f.lower().endswith(".shp"):
            shape_files.append(full_f)
            all_tracks.append(f.split("_")[0])

    all_tracks = np.array(all_tracks, order='C')
    shape_files= np.array(shape_files, order='C')

    # iterate through the unique tracks and obtain all frames
    for track in np.unique(all_tracks):
        shp_for_track = shape_files[all_tracks == track]

        out_filename = pjoin(out_dir, "input_list_{}.txt".format(track))

        with open(out_filename, "w") as fid:
            fid.write("\n".join(shp_for_track))

if __name__ == "__main__":
    cli()
