#!/usr/bin/env python
from typing import Optional, Union, Dict, List
import tempfile
from pathlib import Path
import structlog
from PIL import Image
import numpy as np

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.subprocess_utils import working_directory
import insar.constant as const

_LOG = structlog.get_logger("insar")


class SlcBackscatterException(Exception):
    pass


pg = GammaInterface(
    subprocess_func=auto_logging_decorator(
        subprocess_wrapper, SlcBackscatterException, _LOG
    )
)


def generate_normalised_backscatter(
    outdir: Path,
    src_mli: Path,
    ellip_pix_sigma0: Path,
    dem_pix_gamma0: Path,
    dem_lt_fine: Path,
    geo_dem_par: Path,
    dst_stem: Path,
):
    """
    Generate Normalised Radar Backscatter (gamma0) image for secondary scene according to equation in
    Section 10.6 of GAMMA Geocoding and Image Registration Users Guide (p25):

        gamma0 = src_mli * ellip_pix_sigma0 / dem_pix_gamma0

    :param outdir:
        The output directory where all outputs of the processing should go.
    :param src_mli:
        The source scene (typically an mli) to produce backscatter for.
    :param ellip_pix_sigma0:
        A full path to a sigma0 product generated during primary-dem co-registration.
    :param dem_pix_gamma0:
        A full path to a gamma0 product generated during primary-dem co-registration.
    :param dem_lt_fine:
        A full path to a geo_to_rdc look-up table generated during primary-dem co-registration.
    :param geo_dem_par:
        A full path to a geo dem par generated during primary-dem co-registration.
    :param dst_stem:
        The destination path stem, which all outputs will be prefixed with.
    """
    dst_geo_stem = dst_stem.parent / (dst_stem.stem + "_geo" + dst_stem.suffix)
    secondary_gamma0 = outdir / dst_stem.with_suffix(".gamma0")
    secondary_gamma0_geo = outdir / dst_geo_stem.with_suffix(".gamma0")
    secondary_sigma0_geo = secondary_gamma0_geo.with_suffix(".sigma0")

    par_mli = pg.ParFile(str(src_mli.with_suffix(src_mli.suffix + ".par")))
    mli_width = par_mli.get_value("range_samples", dtype=int, index=0)

    geo_dem_par_vals = pg.ParFile(str(geo_dem_par))
    dem_width = geo_dem_par_vals.get_value("width", dtype=int, index=0)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)
        temp_output = temp_dir / "temp_output"

        # temp_output = src_mli * ellip_pix_sigma0
        pg.float_math(
            src_mli,
            ellip_pix_sigma0,
            temp_output,
            mli_width,
            2,  # multiplication
        )

        # secondary_gamma0 = temp_output / dem_pix_gamma0
        pg.float_math(
            temp_output,
            dem_pix_gamma0,
            secondary_gamma0,
            mli_width,
            3,  # division
        )

        # end result: secondary_gamma0 = (src_mli * ellip_pix_sigma0) / dem_pix_gamma0

        # back geocode gamma0 backscatter product to map geometry using B-spline interpolation on sqrt data
        pg.geocode_back(
            secondary_gamma0,
            mli_width,
            dem_lt_fine,
            secondary_gamma0_geo,
            dem_width,
            const.NOT_PROVIDED,  # nlines_out
            5,  # B-spline interpolation
            0,  # float dtype
            const.NOT_PROVIDED,  # lr_in
            const.NOT_PROVIDED,  # lr_out
            5,  # B-spline degree
        )

        # make quick-look png image
        temp_bmp = temp_dir / f"{secondary_gamma0_geo.name}.bmp"
        secondary_png = outdir / temp_bmp.with_suffix(".png").name

        with working_directory(temp_dir):
            pg.raspwr(
                secondary_gamma0_geo,
                dem_width,
                1,  # start
                0,  # nlines
                20,  # pixavr
                20,  # pixavaz
                const.NOT_PROVIDED,  # scale
                const.NOT_PROVIDED,  # exp
                const.NOT_PROVIDED,  # lr
                temp_bmp,
            )

            # Convert the bitmap to a PNG w/ black pixels made transparent
            img = Image.open(temp_bmp.as_posix())
            img = np.array(img.convert("RGBA"))
            img[(img[:, :, :3] == (0, 0, 0)).all(axis=-1)] = (0, 0, 0, 0)
            Image.fromarray(img).save(secondary_png.as_posix())

            # convert gamma0 Gamma file to GeoTIFF
            pg.data2geotiff(
                geo_dem_par,
                secondary_gamma0_geo,
                2,  # float
                secondary_gamma0_geo.with_suffix(".gamma0.tif"),
                0.0,  # no data value
            )

            # create KML map of PNG file
            pg.kml_map(
                secondary_png,
                geo_dem_par,
                secondary_png.with_suffix(".kml"),
            )

            # geocode sigma0 mli
            pg.geocode_back(
                # input
                src_mli,
                mli_width,
                dem_lt_fine,
                # output
                secondary_sigma0_geo,
                dem_width,
                # settings
                const.NOT_PROVIDED,  # nlines_out
                0,  # nearest neighbour interpolation
                0,  # float dtype
                const.NOT_PROVIDED,  # lr_in
                const.NOT_PROVIDED,  # lr_out
            )

            # convert sigma0 Gamma file to GeoTIFF
            pg.data2geotiff(
                geo_dem_par,
                secondary_sigma0_geo,
                2,  # float dtype
                secondary_sigma0_geo.with_suffix(".sigma0.tif"),
                0.0,  # no data value
            )
