#!/usr/bin/env python3

import rasterio
import insar.constant as const

from osgeo import gdal
from os.path import join as pjoin
from pathlib import Path
from typing import Union, Tuple, Type
from insar.subprocess_utils import run_command
from insar.gamma.proxy import create_gamma_proxy
from insar.utils import TemporaryDirectory
from insar.logs import STATUS_LOGGER as LOG
from collections import namedtuple

PixelSize = namedtuple('PixelSize', 'x y')

class GammaDemException(Exception):
    pass


pg = create_gamma_proxy(GammaDemException)

def get_pixel_size(fn: Path) -> PixelSize:
    fd = gdal.Open(str(fn))
    geo = fd.GetGeoTransform()
    return PixelSize(geo[1], -geo[5])

def create_gamma_dem(
    output_path: Path,
    dem_img: Path,
    stack_id: str,
    stack_extent: Tuple[Tuple[float, float], Tuple[float, float]],
    buffer_width: float = 0.3,
) -> None:

    with TemporaryDirectory(delete=const.DISCARD_TEMP_FILES) as tmpdir:
        (min_lon, min_lat), (max_lon, max_lat) = stack_extent
        min_lon -= buffer_width
        min_lat -= buffer_width
        max_lon += buffer_width
        max_lat += buffer_width

        tmpfn = Path(tmpdir) / f"{stack_id}_before_nodata_fix.tif"
        outfn = output_path / f"{stack_id}.tif"

        pixel_size = get_pixel_size(dem_img)

        LOG.debug(f"DEM file {dem_img} has pixel_size.x = {pixel_size.x} pixel_size.y = {pixel_size.y}")

        if const.DEM_GEOTIFF_OVERSAMPLE_RATE > 1:
            new_pixel_size_x = pixel_size.x / const.DEM_GEOTIFF_OVERSAMPLE_RATE
            new_pixel_size_y = pixel_size.y / const.DEM_GEOTIFF_OVERSAMPLE_RATE
            command = [
                "gdal_translate",
                "-tr",
                new_pixel_size_x,
                new_pixel_size_y,
                "-projwin",
                str(min_lon),
                str(max_lat),
                str(max_lon),
                str(min_lat),
                str(dem_img),
                str(tmpfn),
            ]
            run_command(command, tmpdir)
        else:
            command = [
                "gdal_translate",
                "-projwin",
                str(min_lon),
                str(max_lat),
                str(max_lon),
                str(min_lat),
                str(dem_img),
                str(tmpfn),
            ]
            run_command(command, tmpdir)

        # get nodata value from geotiff file to make into gamma compatible format
        # sets the nodata pixels to 0.0001 and update nodata value to None
        with rasterio.open(tmpfn, "r") as src:
            data = src.read(1)
            mask = data == src.nodata
            data[mask] = 0.0001
            profile = src.profile
            profile.update(nodata=None)

            with rasterio.open(outfn, "w", **profile) as dst:
                dst.write(data, 1)

        pixel_size = get_pixel_size(outfn)
        LOG.debug(f"DEM file {outfn} has pixel_size.x = {pixel_size.x} pixel_size.y = {pixel_size.y}")

        # dem_import function is a call to GAMMA software which creates a gamma compatible DEM
        dem_pathname = output_path / f"{stack_id}.dem"
        par_pathname = f"{dem_pathname}.par"
        input_type = 0  # GeoTIFF
        priority = 1  # input DEM parameters have priority

        pg.dem_import(
            outfn,
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
