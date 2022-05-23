#!/usr/bin/env python3

from os.path import join as pjoin
from pathlib import Path
from typing import Union, Tuple
import tempfile

import rasterio

from insar import constant as const
from insar.subprocess_utils import run_command
from insar.gamma.proxy import create_gamma_proxy

class GammaDemException(Exception):
    pass


pg = create_gamma_proxy(GammaDemException)

def create_gamma_dem(
    gamma_dem_dir: Union[Path, str],
    dem_img: Union[Path, str],
    stack_id: str,
    stack_extent: Tuple[float],
    buffer_width: float = 0.3,
    create_png: bool = False,
) -> None:
    """
    Automatically creates a DEM and par file for use with GAMMA.
    :param gamma_dem_dir:
        A directory to where gamma dem and par file will be written
    :param dem_img:
        A DEM from where gamma dem will be extracted from
    :param stack_id:
        An identifying name for the stack, which is used to name other filenames.
    :param stack_extent:
        A tuple of ((minx, miny), (maxx, maxy)) representing the lon/lat boundary extent of the stack being processed.
    :param buffer_width:
        Additional buffer (in degrees) to include around the stack extent
    :param create_png:
        A flag to create preview of dem
    """

    with tempfile.TemporaryDirectory() as tmpdir:
        (min_lon, min_lat), (max_lon, max_lat) = stack_extent
        min_lon -= buffer_width
        min_lat -= buffer_width
        max_lon += buffer_width
        max_lat += buffer_width

        # subset dem_img for the area of interest as a geotiff format
        outfile = "{}_temp.tif".format(stack_id)
        command = [
            "gdal_translate",
            "-projwin",
            str(min_lon),
            str(max_lat),
            str(max_lon),
            str(min_lat),
            str(dem_img),
            outfile,
        ]
        run_command(command, tmpdir)

        # get nodata value from geotiff file to make into gamma compatible format
        # sets the nodata pixels to 0.0001 and update nodata value to None
        with rasterio.open(pjoin(tmpdir, outfile), "r") as src:
            data = src.read(1)
            mask = data == src.nodata
            data[mask] = 0.0001
            profile = src.profile
            profile.update(nodata=None)
            outfile_new = pjoin(tmpdir, "{}.tif".format(stack_id))

            with rasterio.open(outfile_new, "w", **profile) as dst:
                dst.write(data, 1)

            # dem_import function is a call to GAMMA software which creates a gamma compatible DEM
            input_dem_pathname = outfile_new
            dem_pathname = str(Path(gamma_dem_dir).joinpath(f"{stack_id}.dem"))
            par_pathname = f"{dem_pathname}.par"
            input_type = 0  # GeoTIFF
            priority = 1  # input DEM parameters have priority

            pg.dem_import(
                input_dem_pathname,
                dem_pathname,
                par_pathname,
                input_type,
                priority,
                const.NOT_PROVIDED,  # geoid or constant geoid height value
                const.NOT_PROVIDED,  # geoid_par, geoid DEM_par file
                const.NOT_PROVIDED,  # geoid_type, global geoid in EQA coordinates
                const.NOT_PROVIDED,  # lat_n_shift, latitude or Northing constant shift to apply
                const.NOT_PROVIDED,  # lon_e_shift, longitude or Easting constant shift
                const.NOT_PROVIDED,  # zflg, no_data values in input file are kept in output file
                const.NOT_PROVIDED,  # no_data, value defined in input metadata
            )

            # TODO: replace/add PIL option?
            # create a preview of dem file
            if create_png:
                dem_png_file = "{}_dem_preview.png".format(stack_id)
                command = [
                    "gdal_translate",
                    "-of",
                    "PNG",
                    "-outsize",
                    "10%",
                    "10%",
                    outfile_new,
                    dem_png_file,
                ]
                run_command(command, gamma_dem_dir)
