#!/usr/bin/python3

from os.path import join as pjoin
from pathlib import Path
from typing import Optional, Union
import tempfile

import shapely
import shapely.wkt
from shapely.ops import cascaded_union
import rasterio
from spatialist import Vector
from python_scripts.subprocess_utils import run_command


def create_gamma_dem(
    gamma_dem_dir: Union[Path, str],
    dem_img: Union[Path, str],
    track_frame: str,
    shapefile: Union[Path, str],
    buffer_width: Optional[float] = 0.3
    ) -> None:
    """
    Automatically creates a DEM and par file for use with GAMMA.
    :param gamma_dem_dir:
        A directory to where gamma dem and par file will be written
    :param dem_img:
        A DEM from where gamma dem will be extracted from
    :param track_frame:
        A track and frame name
    :param shapefile:
        A 'Path' to a shapefile
    :param buffer:
        Additional buffer to include in a subset of shapefile extent
    """
    vector_object = Vector(shapefile)

    def _get_bounds():
        if isinstance(vector_object, Vector):
            return (
                cascaded_union(
                    [
                        shapely.wkt.loads(extent)
                        for extent in vector_object.convert2wkt(set3D=False)
                    ]
                )
                .buffer(buffer_width, cap_style=2, join_style=2)
                .bounds
            )

    with tempfile.TemporaryDirectory() as tmpdir:

        min_lon, min_lat, max_lon, max_lat = _get_bounds()

        # subset dem_img for the area of interest as a geotiff format
        outfile = "{}_temp.tif".format(track_frame)
        command = [
            "gdal_translate",
            "-projwin",
            str(min_lon),
            str(max_lat),
            str(max_lon),
            str(min_lat),
            dem_img,
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
            outfile_new = pjoin(tmpdir, "{}.tif".format(track_frame))
            with rasterio.open(outfile_new, "w", **profile) as dst:
                dst.write(data, 1)

            # dem_import function is a call to GAMMA software which creates a gamma compatible DEM
            command = [
                "dem_import",
                outfile_new,
                "{}.dem".format(track_frame),
                "{}.dem.par".format(track_frame),
                "0",
                "1",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
                "-",
            ]
            run_command(command, gamma_dem_dir)

            # create a preview of dem file
            dem_png_file = "{}_dem_preview.png".format(track_frame)
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

