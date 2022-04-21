#!/usr/bin/env python

import os
import uuid
import structlog
from typing import Optional, Union, Dict
from pathlib import Path

from shapely.ops import cascaded_union
import yaml
from insar.meta_data.s1_slc import SlcMetadata
from insar.meta_data.metadata_diagnosis import diagnose

_LOG = structlog.get_logger("insar")


def generate_slc_metadata(
    slc_scene: Path,
    outdir: Optional[Path] = None,
    yaml_file: Optional[bool] = False,
    max_retries: Optional[int] = 30,
) -> Union[Dict, None]:
    """
    generate_slc_metadata extracts slc metadata from a S1 zip file
    denoted as slc_scene. This function is used in the
    slc-ingestion and ard_insar commands.

    Intermittent issues with extracting burst metadata from xml files
    using pygamma has necessitated the creation of a slc metadata
    diagnosis tool. This tool has been successful at identifying
    slc metadata that does not have essential information. In the
    workflow, the generate_slc_metadata() function in
    insar.meta_data.s1_gridding_utils is used to insert slc metadata
    into either a yaml or directly into a sqlite database. As such,
    this is a potential place to include the diagnosis tool and
    retries.

    Parameters
    ----------

    slc_scene: Path
        Full path to a S1 zip file

    outdir: Path or None
        An output directory to store yaml_file

    yaml_file: {True | False} or None
        A bool flag to write a yaml file containing slc metadata

    max_retries: int
        The number of slc metadata extraction retries

    Returns
    -------
        if yaml_file is False then a  "dict"  containing slc
        metadata is returned, else the "dict" is dumped into
        a yaml file and None is returned.
    """
    # Do not exit the while loop until the slc-metadata has
    # all the necessary information or max_retries is reached
    retry_cnt = 0
    while retry_cnt < max_retries:
        _LOG.info(
            "creating slc-metadata", S1_scene=slc_scene, retry=retry_cnt,
        )

        # ----- get slc_metadata ----- #
        scene_obj = SlcMetadata(slc_scene)
        try:
            slc_metadata = scene_obj.get_metadata()
        except ValueError as err:
            raise ValueError(err)
        except AssertionError as err:
            raise AssertionError(err)

        keys = slc_metadata.keys()

        if "id" not in keys:
            slc_metadata["id"] = str(uuid.uuid4())
        if "product" not in keys:
            slc_metadata["product"] = {
                "name": "ESA_S1_{}".format(slc_metadata["properties"]["product"]),
                "url": scene_obj.scene,
            }

        # diagnose slc_metadata dict to ensure that it has required metadata.
        if diagnose(slc_metadata, slc_scene):
            # returns True for pass, or False for fail
            # exit while look if slc_metadata has passed
            break

        retry_cnt += 1

    if retry_cnt >= max_retries:
        _LOG.error(
            "error: max. retries hit for slc-metadata creation",
            S1_scene=slc_scene,
            num_retries=retry_cnt,
        )
    else:
        _LOG.info(
            "slc-metadata created and passed checks",
            S1_scene=slc_scene,
            num_retries=retry_cnt,
        )

    # What should occur if max retries is reached? should
    # the slc-metadata be saved??

    # --------------------------- #
    #  Save slc-metadata as yaml  #
    #    or store in sqlite db    #
    # --------------------------- #
    if not yaml_file:
        return slc_metadata

    if outdir is None:
        outdir = os.getcwd()
    else:
        if not os.path.exists(outdir.as_posix()):
            os.makedirs(outdir.as_posix())
    with open(
        os.path.join(
            outdir, "{}.yaml".format(os.path.basename(slc_scene.as_posix())[:-4]),
        ),
        "w",
    ) as out_fid:
        yaml.dump(slc_metadata, out_fid)
