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


def with_suffix(path: Path, suffix: str):
    return path.parent / (path.name + suffix)


def quicklook(src_path: Path, width: int, dst_path: Path):
    pg.raspwr(
        src_path,
        width,
        1,  # start
        0,  # nlines
        20,  # pixavr
        20,  # pixavaz
        const.NOT_PROVIDED,  # scale
        const.NOT_PROVIDED,  # exp
        const.NOT_PROVIDED,  # lr
        "temp.bmp",
    )

    # Convert the bitmap to a PNG w/ black pixels made transparent
    img = Image.open("temp.bmp")
    img = np.array(img.convert("RGBA"))
    img[(img[:, :, :3] == (0, 0, 0)).all(axis=-1)] = (0, 0, 0, 0)
    Image.fromarray(img).save(dst_path.as_posix())

def generate_nrt_backscatter(
    outdir: Path,
    src_path: Path,
    dem_path: Path,
    dst_stem: Path,
    dem_attitude_override: Optional[int] = None
):
    """
    Generates radar backscatter for a scene.

    :param outdir:
        The output directory where all outputs of the processing should go.
    :param src_sigma0:
        The source scene (typically an mli) to produce backscatter for.
    :param dem
    :param dst_stem:
        The destination path stem, which all outputs will be prefixed with.
    """
    dem_par_path = with_suffix(dem_path, ".par")
    dem_par = pg.ParFile(str(dem_par_path))
    dem_width = dem_par.get_value("width", dtype=int, index=0)

    geo_dem_path = with_suffix(dst_stem, "_geo.dem")
    geo_dem_par_path = with_suffix(geo_dem_path, ".par")
    geo_dem_lut_path = with_suffix(dst_stem, "_dem_geo_to_rdc_rough.lt")

    linc_path = with_suffix(dst_stem, "_linc")
    lsmap_path = with_suffix(dst_stem, "_lsmap")

    src_par_path = with_suffix(src_path, ".par")
    src_par = pg.ParFile(str(src_par_path))
    src_width = src_par.get_value("range_samples", dtype=int, index=0)

    dst_sigma0_path = with_suffix(dst_stem, "_sigma0")
    dst_gamma0_path = with_suffix(dst_stem, "_gamma0")

    # This code branch is disabled as there's some gc_map2 related quirks we need to handle
    # - the end goal is to use gc_map2 though...
    # GH issue: https://github.com/GeoscienceAustralia/gamma_insar/issues/232
    if False:
        pg.gc_map2(
            # Inputs
            src_par_path,
            dem_par_path,
            dem_attitude_override or dem_path,
            # Outputs
            geo_dem_par_path,
            geo_dem_path,
            geo_dem_lut_path,
            const.NOT_PROVIDED,  # default oversampling factor
            const.NOT_PROVIDED,  # default oversampling factor
            lsmap_path,
            const.NOT_PROVIDED,
            linc_path,
            const.NOT_PROVIDED,  # local resolution map
            const.NOT_PROVIDED,  # local offnadir (or look) angle map
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            # Settings
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            8,  # frame pixels (padding pixels around the edge)
            const.NOT_PROVIDED,  # no lsmap scaling
            const.NOT_PROVIDED,  # no offset polynomial (we're not coregistered)
            const.NOT_PROVIDED  # reference image flag (simulated SAR is the default)
        )
    else:
        pg.gc_map1(
            # Inputs
            src_par_path,
            const.NOT_PROVIDED,
            dem_par_path,
            dem_attitude_override or dem_path,
            # Outputs
            geo_dem_par_path,
            geo_dem_path,
            geo_dem_lut_path,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            linc_path,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            lsmap_path,
            # Settings
            8,  # frame pixels (padding pixels around the edge)
            const.NOT_PROVIDED,   # no lsmap scaling
        )

    pg.pixel_area(
        src_par_path,
        dem_par_path,
        dem_path,
        geo_dem_lut_path,
        lsmap_path,
        linc_path,
        with_suffix(dst_sigma0_path, "_ufratio"),
        with_suffix(dst_gamma0_path, "_ufratio"),
    )

    # interpolate holes
    pg.interp_ad(
        with_suffix(dst_sigma0_path, "_ufratio"),
        with_suffix(dst_sigma0_path, "_ratio"),
        src_width,
        const.NOT_PROVIDED,  # Interpolation window
        const.NOT_PROVIDED,  # Min points for interpolation
        const.NOT_PROVIDED,  # max points
        const.NOT_PROVIDED,  # Weighting algorithm
        2,  # float
        1,  # copy data
    )

    pg.interp_ad(
        with_suffix(dst_gamma0_path, "_ufratio"),
        with_suffix(dst_gamma0_path, "_ratio"),
        src_width,
        const.NOT_PROVIDED,  # Interpolation window
        const.NOT_PROVIDED,  # Min points for interpolation
        const.NOT_PROVIDED,  # max points
        2,  # Weighting algorithm
        2,  # float
        1,  # copy data
    )

    # obtain ellipsoid-based ground range sigma0 pixel reference area
    # TBD: Is this required?
    dst_sigma0_cal_path = with_suffix(dst_sigma0_path, "_cal")
    dst_sigma0_cal_par_path = with_suffix(dst_sigma0_path, "_cal.par")
    dst_sigma0_cal_area_path = with_suffix(dst_sigma0_path, "_cal_area")

    dst_gamma0_cal_path = with_suffix(dst_gamma0_path, "_cal")
    dst_gamma0_cal_par_path = with_suffix(dst_gamma0_path, "_cal.par")
    dst_gamma0_cal_area_path = with_suffix(dst_gamma0_path, "_cal_area")

    # Apply radiometric calibration
    # In this prototype, this produces 2 things:
    # 1) direct outputs of radiometrically calibrated sigma0 and gamma0 products!
    # 2) scaling factors to apply sigma0/gamma0 terrain correction to manually
    #    produce our own products w/ float_math...
    pg.radcal_MLI(
        src_path,
        src_par_path,
        const.NOT_PROVIDED,
        dst_sigma0_cal_path,
        const.NOT_PROVIDED,  # antenna
        0,  # No range spread correction
        0,  # No antenna correction
        1,  # sigma0
        const.NOT_PROVIDED,  # no db scaling
        const.NOT_PROVIDED,  # no calibration factor
        dst_sigma0_cal_area_path,
    )

    pg.radcal_MLI(
        src_path,
        src_par_path,
        const.NOT_PROVIDED,
        dst_gamma0_cal_path,
        const.NOT_PROVIDED,  # antenna
        0,  # No range spread correction
        0,  # No antenna correction
        2,  # gamma0
        const.NOT_PROVIDED,  # no db scaling
        const.NOT_PROVIDED,  # no calibration factor
        dst_gamma0_cal_area_path,
    )

    # Generate Gamma0 backscatter image for primary scene according to equation
    # in Section 10.6 of Gamma Geocoding and Image Registration Users Guide
    pg.float_math(
        src_path,
        dst_sigma0_cal_area_path,
        "temp",
        src_width,
        2,  # Multiply
    )

    pg.float_math(
        "temp",
        with_suffix(dst_gamma0_path, "_ratio"),
        dst_gamma0_path,
        src_width,
        3,  # Divide
    )

    # Geocode...
    def geocode(src, dst):
        pg.geocode_back(
            src,
            src_width,
            geo_dem_lut_path,
            dst,
            dem_width,
            const.NOT_PROVIDED,
            5,  # B-spline curve interpolation
            0,  # Float type
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            5,  # curve degree
        )

        # Convert to tif
        pg.data2geotiff(
            geo_dem_par_path,
            dst,
            2,  # float
            with_suffix(dst, ".tif"),
            0.0,  # no data value
        )

        quicklook(src, src_width, with_suffix(dst, ".png"))

    # Convert to tif
    pg.data2tiff(
        src_path,
        src_width,
        2,  # float
        with_suffix(src_path, ".tif"),
        0.0,  # no data value
    )

    geocode(src_path, with_suffix(src_path, "_geo"))
    #geocode(dst_sigma0_path, with_suffix(dst_sigma0_path, "_geo"))
    geocode(dst_gamma0_path, with_suffix(dst_gamma0_path, "_geo"))
    geocode(dst_sigma0_cal_path, with_suffix(dst_sigma0_cal_path, "_geo"))
    geocode(dst_gamma0_cal_path, with_suffix(dst_gamma0_cal_path, "_geo"))

