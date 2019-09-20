#!/usr/bin/python3

from os.path import join as pjoin
import tempfile

import shapely
import shapely.wkt
from shapely.ops import cascaded_union
import rasterio
from spatialist import Vector
from subprocess_utils import run_command


def create_gamma_dem(gamma_dem_dir, dem_img, track, frame, shapefile, buffer_width=0.3):
    """
    Automatically creates a DEM and par file for use with GAMMA.
    :param gamma_dem_dir:
        A directory to where gamma dem and par file will be written
    :param dem_img:
        A DEM from where gamma dem will be extracted from
    :param track:
        A track name
    :param frame:
        A frame name
    :param shapefile:
        A 'Path' to a shapefile
    :param buffer:
        Additional buffer to include in a subset of shapefile extent
    """
    vector_object = Vector(shapefile)

    def __get_bounds():
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

        min_lon, min_lat, max_lon, max_lat = __get_bounds()

        # subset dem_img for the area of interest as a geotiff format
        outfile = "{}_{}_temp.tif".format(track, frame)
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
            outfile_new = pjoin(tmpdir, "{}_{}.tif".format(track, frame))
            with rasterio.open(outfile_new, "w", **profile) as dst:
                dst.write(data, 1)

            # dem_import function is a call to GAMMA software which creates a gamma compatible DEM
            command = [
                "dem_import",
                outfile_new,
                "{}_{}.dem".format(track, frame),
                "{}_{}.dem.par".format(track, frame),
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
            dem_png_file = "{}_{}_dem_preview.png".format(track, frame)
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


if __name__ == "__main__":
    kwargs = {
        "gamma_dem_dir": "/g/data/u46/users/pd1813/INSAR/test_insar/",
        "dem_img": "/g/data1/dg9/MASTER_DEM/GAMMA_DEM_SRTM_1as_mosaic.img",
        "track": "T045D",
        "frame": "F20S",
        "shapefile": "/g/data/u46/users/pd1813/INSAR/shape_files/grid_vectors/T045D_F20S.shp",
    }

    create_gamma_dem(**kwargs)
