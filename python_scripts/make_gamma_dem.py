#!/usr/bin/python3

from os.path import join as pjoin, abspath, basename, dirname, exists
import rasterio
import tempfile

from python_scripts.subprocess_utils import run_command


def create_gamma_dem(gamma_dem_dir, dem_img, track, frame, min_lat, max_lat, min_lon, max_lon):
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
    :param min_lat:
        A minimum latitude extent to form Area of Interest for GAMMA dem
    :param max_lat:
        A maximum latitude extent to form Area of Interest for GAMMA dem
    :param min_lon:
        A minimum longitude extent to form Area of Interest for GAMMA dem
    :param max_lon:
        A maximum longitude extent to form Area of Interest for GAMMA dem
    """
    with tempfile.TemporaryDirectory() as tmpdir:

        # subset dem_img for the area of interest as a geotiff format
        outfile = '{}_{}_temp.tif'.format(track, frame)
        command = ['gdal_translate', '-projwin', str(min_lon),
                   str(max_lat), str(max_lon), str(min_lat), dem_img, outfile]
        run_command(command, tmpdir)

        # get nodata value from geotiff file to make into gamma compatible format
        # sets the nodata pixels to 0.0001 and update nodata value to None
        with rasterio.open(pjoin(tmpdir, outfile), 'r') as src:
            data = src.read(1)
            mask = (data == src.nodata)
            data[mask] = 0.0001
            profile = src.profile
            profile.update(nodata=None)
            outfile_new = pjoin(tmpdir, '{}_{}.tif'.format(track, frame))
            with rasterio.open(outfile_new, 'w', **profile) as dst:
                dst.write(data, 1)

            # dem_import function is a call to GAMMA software which creates a gamma compatible DEM
            command = ['dem_import', outfile_new, '{}_{}.dem'.format(track, frame),
                       '{}_{}.dem.par'.format(track, frame), '0', '1', '-', '-', '-', '-', '-', '-', '-']
            run_command(command, gamma_dem_dir)

            # create a preview of dem file
            dem_png_file = '{}_{}_dem_preview.png'.format(track, frame)
            command = ['gdal_translate', '-of', 'PNG', '-outsize', '10%', '10%', outfile_new, dem_png_file]
            run_command(command, gamma_dem_dir)
            

if __name__ == '__main__':
    kwargs = {'gamma_dem_dir': '/g/data/u46/users/pd1813/INSAR/test_a/',
              'dem_img': '/g/data1/dg9/MASTER_DEM/GAMMA_DEM_SRTM_1as_mosaic.img',
              'track': 'T118D',
              'frame': 'F19',
              'min_lat': -36.40105916524334,
              'max_lat': -33.85754636915053,
              'min_lon': 144.10384743508246,
              'max_lon': 147.5394048023552}

    create_gamma_dem(**kwargs)
