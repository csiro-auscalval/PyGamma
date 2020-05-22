#!/usr/bin/env python3

from os.path import join as pjoin
from pathlib import Path
from typing import Optional, Union
import tempfile

import shapely
import shapely.wkt
from shapely.ops import cascaded_union
import rasterio
from spatialist import Vector
import structlog

import py_gamma as pg

from insar.subprocess_utils import run_command
from insar.logs import get_wrapped_logger

_LOG = structlog.get_logger("insar")


def create_gamma_dem(
    gamma_dem_dir: Union[Path, str],
    dem_img: Union[Path, str],
    track_frame: str,
    shapefile: Union[Path, str],
    buffer_width: Optional[float] = 0.3,
    create_png: Optional[bool] = False,
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
    :param buffer_wdith:
        Additional buffer to include in a subset of shapefile extent
    :param create_png:
        A flag to create preview of dem
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
            # py_gamma parameters
            cout = []
            cerr = []
            input_dem_pathname = outfile_new
            dem_pathname = str(Path(gamma_dem_dir).joinpath(f"{track_frame}.dem"))
            par_pathname = f"{dem_pathname}.par"
            input_type = 0  # GeoTIFF
            priority = 1  # input DEM parameters have priority
            geoid = "-"  # geoid or constant geoid height value
            geoid_par = "-"  # geoid DEM_par file
            geoid_type = "-"  # global geoid in EQA coordinates
            lat_n_shift = "-"  # latitude or Northing constant shift to apply
            lon_e_shift = "-"  # longitude or Easting constant shift
            zflg = "-"  # no_data values in input file are kept in output file
            no_data = "-"  # value defined in input metadata

            stat = pg.dem_import(
                input_dem_pathname,
                dem_pathname,
                par_pathname,
                input_type,
                priority,
                geoid,
                geoid_par,
                geoid_type,
                lat_n_shift,
                lon_e_shift,
                zflg,
                no_data,
                cout=cout,
                cerr=cerr,
                stdout_flag=False,
                stderr_flag=False,
            )
            if stat != 0:
                msg = "failed to execute pg.dem_import"
                _LOG.error(
                    msg,
                    input_dem_pathname=input_dem_pathname,
                    dem_pathname=dem_pathname,
                    par_pathname=par_pathname,
                    input_type=input_type,
                    priority=priority,
                    geoid=geoid,
                    geoid_par=geoid_par,
                    geoid_type=geoid_type,
                    lat_n_shift=lat_n_shift,
                    lon_e_shift=lon_e_shift,
                    zflg=zflg,
                    no_data=no_data,
                    stat=stat,
                    gamma_stdout=cout,
                    gamma_stderr=cerr,
                )
                raise Exception(msg)

            # create a preview of dem file
            if create_png:
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
