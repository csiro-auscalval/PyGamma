#!/usr/bin/env python
import tempfile
from typing import Optional, Tuple, Union
import shutil
from pathlib import Path
import structlog
from PIL import Image
import numpy as np
from osgeo import gdal

from insar.gamma.proxy import create_gamma_proxy
from insar.subprocess_utils import working_directory
from insar.coreg_utils import latlon_to_px, create_diff_par
from insar import constant as const
from insar.paths.dem import DEMPaths
from insar.paths.coregistration import CoregisteredPrimaryPaths
from insar.paths.backscatter import BackscatterPaths
from insar.paths.slc import SlcPaths
from insar.project import ProcConfig
from insar.process_utils import convert


class CoregisterDemException(Exception):
    pass

pg = create_gamma_proxy(CoregisterDemException)


def append_suffix(path: Path, suffix: str) -> Path:
    """
    A simple filename append function that that only allows for a single '.' extension,
    by keeping any existing extension as a '_' suffix.

    Example: Appending .zip to test.tif, would result in test_tif.zip, instead of test.tif.zip

    >>> append_suffix(Path('/tmp/test.tif'), '.zip').as_posix()
    '/tmp/test_tif.zip'
    """
    return path.parent / (path.name.replace(".", "_") + suffix)


def gen_dem_rdc(
    dem_paths: DEMPaths,
    coreg_paths: CoregisteredPrimaryPaths,
    dem_ovr: int = 1
) -> None:
    """
    Generate DEM coregistered to slc in rdc geometry.

    :param dem_paths:
        The DEM paths we're geocoding to.
    :param coreg_paths:
        The primary reference scene coreg paths being geocoded.
    :param dem_ovr:
        DEM oversampling factor. Default is 1.
    """

    # generate initial geocoding look-up-table and simulated SAR image
    mli_par_pathname = str(coreg_paths.r_dem_primary_mli_par)
    off_par_pathname = const.NOT_PROVIDED
    dem_par_pathname = str(dem_paths.dem_par)
    dem_pathname = str(dem_paths.dem)
    dem_seg_par_pathname = str(dem_paths.geo_dem_par)
    dem_seg_pathname = str(dem_paths.geo_dem)
    lookup_table_pathname = str(dem_paths.dem_lt_rough)
    lat_ovr = dem_ovr
    lon_ovr = dem_ovr
    sim_sar_pathname = str(dem_paths.dem_geo_sim_sar)
    u_zenith_angle = const.NOT_PROVIDED
    v_orientation_angle = const.NOT_PROVIDED
    inc_angle_pathname = str(dem_paths.dem_loc_inc)
    psi_projection_angle = const.NOT_PROVIDED
    pix = const.NOT_PROVIDED  # pixel area normalization factor
    ls_map_pathname = str(dem_paths.dem_lsmap)
    frame = 8
    ls_mode = 2

    # Simple trigger for us to move over to gc_map2 when
    # InSAR team confirm they're ready for the switch.
    use_gc_map2 = False

    if not use_gc_map2:
        pg.gc_map1(
            mli_par_pathname,
            off_par_pathname,
            dem_par_pathname,
            dem_pathname,
            dem_seg_par_pathname,
            dem_seg_pathname,
            lookup_table_pathname,
            lat_ovr,
            lon_ovr,
            sim_sar_pathname,
            u_zenith_angle,
            v_orientation_angle,
            inc_angle_pathname,
            psi_projection_angle,
            pix,
            ls_map_pathname,
            frame,
            ls_mode,
        )
    else:
        # TODO: Consider replacing gc_map1 with gc_map2. The former was deprecated by GAMMA.
        # See https://github.com/GeoscienceAustralia/gamma_insar/issues/232
        pg.gc_map2(
            mli_par_pathname,
            dem_par_pathname,
            dem_pathname,
            dem_seg_par_pathname,
            dem_seg_pathname,
            lookup_table_pathname,
            lat_ovr,
            lon_ovr,
            ls_map_pathname,
            const.NOT_PROVIDED,
            inc_angle_pathname,
            const.NOT_PROVIDED,  # local resolution map
            const.NOT_PROVIDED,  # local offnadir (or look) angle map
            sim_sar_pathname,
            u_zenith_angle,
            v_orientation_angle,
            psi_projection_angle,
            pix,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            frame,
            const.NOT_PROVIDED,
            str(dem_paths.dem_diff),
            const.NOT_PROVIDED  # reference image flag (simulated SAR is the default)
        )

    # generate initial gamma0 pixel normalisation area image in radar geometry
    mli_par_pathname = str(coreg_paths.r_dem_primary_mli_par)
    dem_par_pathname = str(dem_paths.geo_dem_par)
    dem_pathname = str(dem_paths.geo_dem)
    lookup_table_pathname = str(dem_paths.dem_lt_rough)
    ls_map_pathname = str(dem_paths.dem_lsmap)
    inc_map_pathname = str(dem_paths.dem_loc_inc)
    pix_sigma0_pathname = const.NOT_PROVIDED  # no output
    pix_gamma0_pathname = str(dem_paths.dem_pix_gam)

    pg.pixel_area(
        mli_par_pathname,
        dem_par_pathname,
        dem_pathname,
        lookup_table_pathname,
        ls_map_pathname,
        inc_map_pathname,
        pix_sigma0_pathname,
        pix_gamma0_pathname,
    )

def offset_calc(
    log: structlog.BoundLogger,
    dem_paths: DEMPaths,
    coreg_paths: CoregisteredPrimaryPaths,
    land_center: Tuple[int, int],
    dem_width: int,
    r_dem_primary_mli_width: int,
    r_dem_primary_mli_length: int,
    dem_patch_window: int = 1024,
    dem_rpos: Optional[int] = None,
    dem_azpos: Optional[int] = None,
    dem_snr: float = 0.15,
    npoly: int = 1,
    use_external_image: bool = False,
) -> None:
    """Offset computation. (Need more information from InSAR team).
    :param npoly:
        An Optional nth order polynomial term. Otherwise set to default for
        Sentinel-1 acquisitions.
    :param use_external_image:
        An Optional parameter to set use of external image for co-registration.
    """

    nrb_paths = BackscatterPaths(coreg_paths.primary)

    # Get land center from user provided value if possible
    if land_center:
        rpos, azpos = latlon_to_px(pg, coreg_paths.r_dem_primary_mli_par, *land_center)

        log.info(
            "Land center for DEM coregistration",
            mli=coreg_paths.r_dem_primary_mli,
            land_center=land_center,
            land_center_px=(rpos, azpos)
        )

    # Worst case we fall back to center of image (same as GAMMA default)
    else:
        rpos = r_dem_primary_mli_width // 2
        azpos = r_dem_primary_mli_length // 2

    # MCG: Urs Wegmuller recommended using pixel_area_gamma0 rather than
    # simulated SAR image in offset calculation
    mli_1_pathname = str(dem_paths.dem_pix_gam)
    mli_2_pathname = str(coreg_paths.r_dem_primary_mli)
    diff_par_pathname = str(dem_paths.dem_diff)
    rlks = 1
    azlks = 1
    rpos = dem_rpos or rpos
    azpos = dem_azpos or azpos
    offr = const.NOT_PROVIDED
    offaz = const.NOT_PROVIDED
    thres = dem_snr
    patch = dem_patch_window
    cflag = 1  # copy constant range and azimuth offsets

    # Note: these are in no particular order
    grid = np.array([
        # top, right, bottom, left
        [0, patch], [patch, 0], [0, -patch], [-patch, 0],
        # top left, top right, bottom right, bottom left
        [-patch, patch], [patch, patch], [patch, -patch], [-patch, -patch]
    ])

    # Note: These start at land center, and progressively move further out
    grid_attempts = [[0, 0], *(grid * 0.25), *(grid * 0.5), *(grid * 0.75), *grid]

    # Attempt w/ land center pixel, and spiral out if we fail to find a match
    succeeded_land_center = None

    for attempt_offset in grid_attempts:
        # Note: We rely on GAMMA to error-out if these are out-of-bounds
        # - just like it errors out if the center doesn't find a good enough correlation.
        attempt_rpos = int(rpos + attempt_offset[0])
        attempt_azpos = int(azpos + attempt_offset[1])

        try:
            pg.init_offsetm(
                mli_1_pathname,
                mli_2_pathname,
                diff_par_pathname,
                rlks,
                azlks,
                attempt_rpos,
                attempt_azpos,
                offr,
                offaz,
                thres,
                patch,
                cflag,
            )

            mli_1_pathname = str(dem_paths.dem_pix_gam)
            mli_2_pathname = str(coreg_paths.r_dem_primary_mli)
            diff_par_pathname = str(dem_paths.dem_diff)
            offs_pathname = str(dem_paths.dem_offs)
            ccp_pathname = str(dem_paths.dem_ccp)
            rwin = const.NOT_PROVIDED  # range patch size
            azwin = const.NOT_PROVIDED  # azimuth patch size
            offsets_pathname = str(dem_paths.dem_offsets)
            n_ovr = 2
            nr = const.NOT_PROVIDED  # number of offset estimates in range direction
            naz = const.NOT_PROVIDED  # number of offset estimates in azimuth direction
            thres = const.NOT_PROVIDED  # Lanczos interpolator order

            pg.offset_pwrm(
                mli_1_pathname,
                mli_2_pathname,
                diff_par_pathname,
                offs_pathname,
                ccp_pathname,
                rwin,
                azwin,
                offsets_pathname,
                n_ovr,
                nr,
                naz,
                thres,
            )

            offs_pathname = str(dem_paths.dem_offs)
            ccp_pathname = str(dem_paths.dem_ccp)
            diff_par_pathname = str(dem_paths.dem_diff)
            coffs_pathname = str(dem_paths.dem_coffs)
            coffsets_pathname = str(dem_paths.dem_coffsets)
            thres = const.NOT_PROVIDED

            pg.offset_fitm(
                offs_pathname,
                ccp_pathname,
                diff_par_pathname,
                coffs_pathname,
                coffsets_pathname,
                thres,
                npoly,
            )

            succeeded_land_center = (attempt_rpos, attempt_azpos)
            log.info(
                "DEM coregistration succeeded for land center",
                range_px_coord=attempt_rpos,
                azimuth_px_coord=attempt_azpos
            )

            break

        except CoregisterDemException:
            log.info(
                "DEM coregistration failed for land center",
                range_px_coord=attempt_rpos,
                azimuth_px_coord=attempt_azpos
            )

            # Do NOT raise this exception, we loop through attempting other
            # land centers instead (and finally raise our own exception if all fail)
            pass

    # If no land center succeeded, raise an exception for the failure
    if succeeded_land_center is None:
        raise CoregisterDemException("Failed to coregister primary scene to DEM!")

    # refinement of initial geo-coding look-up-table
    ref_flg = 1
    if use_external_image:
        ref_flg = 0

    gc_in_pathname = str(dem_paths.dem_lt_rough)
    width = dem_width
    diff_par_pathname = str(dem_paths.dem_diff)
    gc_out_pathname = str(dem_paths.dem_lt_fine)

    pg.gc_map_fine(
        gc_in_pathname,  # geocoding lookup table
        width,
        diff_par_pathname,
        gc_out_pathname,
        ref_flg,
    )

    # generate refined gamma0 pixel normalization area image in radar geometry
    with tempfile.TemporaryDirectory() as temp_dir:
        pix = Path(temp_dir).joinpath("pix")

        mli_par_pathname = str(coreg_paths.r_dem_primary_mli_par)
        dem_par_pathname = str(dem_paths.geo_dem_par)
        dem_pathname = str(dem_paths.geo_dem)
        lookup_table_pathname = str(dem_paths.dem_lt_fine)
        ls_map_pathname = str(dem_paths.dem_lsmap)
        inc_map_pathname = str(dem_paths.dem_loc_inc)
        pix_sigma0 = const.NOT_PROVIDED
        pix_gamma0 = str(pix)

        pg.pixel_area(
            mli_par_pathname,
            dem_par_pathname,
            dem_pathname,
            lookup_table_pathname,
            ls_map_pathname,
            inc_map_pathname,
            pix_sigma0,
            pix_gamma0,
        )

        # interpolate holes
        data_in_pathname = str(pix)
        data_out_pathname = str(dem_paths.dem_pix_gam)
        width = r_dem_primary_mli_width
        r_max = const.NOT_PROVIDED  # maximum interpolation window radius
        np_min = const.NOT_PROVIDED  # minimum number of points used for the interpolation
        np_max = const.NOT_PROVIDED  # maximum number of points used for the interpolation
        w_mode = 2  # data weighting mode
        dtype = 2  # FLOAT
        cp_data = 1  # copy input data values to output

        pg.interp_ad(
            data_in_pathname,
            data_out_pathname,
            width,
            r_max,
            np_min,
            np_max,
            w_mode,
            dtype,
            cp_data,
        )

        # obtain ellipsoid-based ground range sigma0 pixel reference area
        sigma0 = Path(temp_dir).joinpath("sigma0")

        mli_pathname = str(coreg_paths.r_dem_primary_mli)
        mli_par_pathname = str(coreg_paths.r_dem_primary_mli_par)
        off_par = const.NOT_PROVIDED  # ISP offset/interferogram parameter file
        cmli = str(sigma0)  # radiometrically calibrated output MLI
        antenna = const.NOT_PROVIDED  # 1-way antenna gain pattern file
        rloss_flag = 0  # range spreading loss correction
        ant_flag = 0  # antenna pattern correction
        refarea_flag = 1  # reference pixel area correction
        sc_db = const.NOT_PROVIDED  # scale factor in dB
        k_db = const.NOT_PROVIDED  # calibration factor in dB
        pix_area_pathname = str(dem_paths.ellip_pix_sigma0)

        pg.radcal_MLI(
            mli_pathname,
            mli_par_pathname,
            off_par,
            cmli,
            antenna,
            rloss_flag,
            ant_flag,
            refarea_flag,
            sc_db,
            k_db,
            pix_area_pathname,
        )

        # Generate Gamma0 backscatter image for primary scene according to equation
        # in Section 10.6 of Gamma Geocoding and Image Registration Users Guide
        temp1 = Path(temp_dir).joinpath("temp1")

        d1_pathname = str(coreg_paths.r_dem_primary_mli)
        d2_pathname = str(dem_paths.ellip_pix_sigma0)
        d_out_pathname = str(temp1)
        width = r_dem_primary_mli_width
        mode = 2  # multiplication

        pg.float_math(
            d1_pathname, d2_pathname, d_out_pathname, width, mode,
        )

        d1_pathname = str(temp1)
        d2_pathname = str(dem_paths.dem_pix_gam)
        d_out_pathname = str(nrb_paths.gamma0)
        width = r_dem_primary_mli_width
        mode = 3  # division

        pg.float_math(
            d1_pathname, d2_pathname, d_out_pathname, width, mode,
        )

        # create raster for comparison with primary mli raster
        pwr_pathname = str(nrb_paths.gamma0)
        width = r_dem_primary_mli_width
        start = 1
        nlines = 0  # 0 is to end of file
        pixavr = 20
        pixavaz = 20
        scale = 1.0
        exp = 0.35
        lr = 1  # left/right mirror image flag
        rasf_pathname = str(nrb_paths.gamma0.with_suffix(".bmp"))

        pg.raspwr(
            pwr_pathname,
            width,
            start,
            nlines,
            pixavr,
            pixavaz,
            scale,
            exp,
            lr,
            rasf_pathname,
        )

        # make sea-mask based on DEM zero values
        temp = Path(temp_dir).joinpath("temp")

        f_in_pathname = str(dem_paths.geo_dem)
        value = 0.0001
        new_value = 0
        f_out_pathname = str(temp)
        width = dem_width
        rpl_flg = 0  # replacement option flag; replace all points
        dtype = 2  # FLOAT
        zflg = 1  # zero is a valid data value

        pg.replace_values(
            f_in_pathname,
            value,
            new_value,
            f_out_pathname,
            width,
            rpl_flg,
            dtype,
            zflg,
        )

        hgt_pathname = str(temp)
        pwr_pathname = const.NOT_PROVIDED
        width = dem_width
        start_hgt = 1
        start_pwr = 1
        nlines = 0
        pixavr = 1
        pixavaz = 1
        m_per_cycle = 100.0  # metres per color cycle
        scale = const.NOT_PROVIDED  # display scale factor
        exp = const.NOT_PROVIDED  # display exponent
        lr = const.NOT_PROVIDED  # left/right mirror image flag
        rasf_pathname = str(dem_paths.seamask)

        pg.rashgt(
            hgt_pathname,
            pwr_pathname,
            width,
            start_hgt,
            start_pwr,
            nlines,
            pixavr,
            pixavaz,
            m_per_cycle,
            scale,
            exp,
            lr,
            rasf_pathname,
        )

def geocode(
    dem_paths: DEMPaths,
    coreg_paths: CoregisteredPrimaryPaths,
    dem_width: int,
    dem_height: int,
    r_dem_primary_mli_width: int,
    r_dem_primary_mli_length: int,
    dem_rad_max: int = 4,
    use_external_image: bool = False,
):
    """
    Method to geocode image files to radar geometry.
    :param use_external_image:
        An Optional external image is to be used for co-registration.
    """

    nrb_paths = BackscatterPaths(coreg_paths.primary)

    # geocode map geometry DEM to radar geometry
    lookup_table_pathname = str(dem_paths.dem_lt_fine)
    data_in_pathname = str(dem_paths.geo_dem)
    width_in = dem_width
    data_out_pathname = str(dem_paths.rdc_dem)
    width_out = r_dem_primary_mli_width
    nlines_out = r_dem_primary_mli_length
    interp_mode = 1
    dtype = const.DTYPE_FLOAT
    lr_in = const.NOT_PROVIDED
    lr_out = const.NOT_PROVIDED
    n_ovr = 2
    rad_max = dem_rad_max
    nintr = const.NOT_PROVIDED  # number of points required for interpolation

    pg.geocode(
        lookup_table_pathname,
        data_in_pathname,
        width_in,
        data_out_pathname,
        width_out,
        nlines_out,
        interp_mode,
        dtype,
        lr_in,
        lr_out,
        n_ovr,
        rad_max,
        nintr,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        rdc_dem_bmp = Path(temp_dir).joinpath("rdc_dem.bmp")

        hgt_pathname = str(dem_paths.rdc_dem)
        pwr_pathname = str(coreg_paths.r_dem_primary_mli)
        width = r_dem_primary_mli_width
        start_hgt = 1
        start_pwr = 1
        nlines = 0
        pixavr = 20
        pixavaz = 20
        m_per_cycle = 500.0  # metres per color cycle
        scale = 1.0  # display scale factor
        exp = 0.35  # display exponent
        lr = 1  # left/right mirror image flag
        rasf_pathname = str(rdc_dem_bmp)

        pg.rashgt(
            hgt_pathname,
            pwr_pathname,
            width,
            start_hgt,
            start_pwr,
            nlines,
            pixavr,
            pixavaz,
            m_per_cycle,
            scale,
            exp,
            lr,
            rasf_pathname,
        )

        Image.open(rdc_dem_bmp).save(
            dem_paths.rdc_dem.with_suffix(".png")
        )

    # Geocode simulated SAR intensity image to radar geometry
    lookup_table_pathname = str(dem_paths.dem_lt_fine)
    data_in_pathname = str(dem_paths.dem_geo_sim_sar)
    width_in = dem_width
    data_out_pathname = str(dem_paths.dem_rdc_sim_sar)
    width_out = r_dem_primary_mli_width
    nlines_out = r_dem_primary_mli_length
    interp_mode = 0  # resampling interpolation; 1/dist
    dtype = const.DTYPE_FLOAT
    lr_in = const.NOT_PROVIDED
    lr_out = const.NOT_PROVIDED
    n_ovr = 2
    rad_max = dem_rad_max  # maximum interpolation search radius
    nintr = const.NOT_PROVIDED  # number of points required for interpolation

    pg.geocode(
        lookup_table_pathname,
        data_in_pathname,
        width_in,
        data_out_pathname,
        width_out,
        nlines_out,
        interp_mode,
        dtype,
        lr_in,
        lr_out,
        n_ovr,
        rad_max,
        nintr,
    )

    # Geocode local incidence angle image to radar geometry
    lookup_table_pathname = str(dem_paths.dem_lt_fine)
    data_in_pathname = str(dem_paths.dem_loc_inc)
    width_in = dem_width
    data_out_pathname = str(dem_paths.dem_rdc_inc)
    width_out = r_dem_primary_mli_width
    nlines_out = r_dem_primary_mli_length
    interp_mode = 0  # resampling interpolation; 1/dist
    dtype = const.DTYPE_FLOAT
    lr_in = const.NOT_PROVIDED
    lr_out = const.NOT_PROVIDED
    n_ovr = 2
    rad_max = dem_rad_max  # maximum interpolation search radius
    nintr = const.NOT_PROVIDED  # number of points required for interpolation

    pg.geocode(
        lookup_table_pathname,
        data_in_pathname,
        width_in,
        data_out_pathname,
        width_out,
        nlines_out,
        interp_mode,
        dtype,
        lr_in,
        lr_out,
        n_ovr,
        rad_max,
        nintr,
    )

    # Geocode external image to radar geometry
    if use_external_image:
        msg = "Feature is rarely used & disabled until required"
        raise NotImplementedError(msg)

    # Convert lsmap to geotiff
    pg.data2geotiff(
        dem_paths.geo_dem_par,
        dem_paths.dem_lsmap,
        5,  # data type (BYTE)
        dem_paths.dem_lsmap_tif,  # output path
        0.0,  # No data
    )

    # Create CARD4L mask (1 = good pixel, 0 = bad)
    ls_map_file = gdal.Open(str(dem_paths.dem_lsmap_tif))
    ls_map_img = ls_map_file.ReadAsArray()

    # Sanity check
    assert(ls_map_img.shape[0] == dem_height)
    assert(ls_map_img.shape[1] == dem_width)

    # Simply turn non-good pixels to 0 (all that remains then is the good pixels which are already 1)
    ls_map_img[ls_map_img != 1] = 0

    # Save this back out as a geotiff w/ identical projection as the lsmap
    ls_mask_file = gdal.GetDriverByName("GTiff").Create(
        dem_paths.dem_lsmap_mask_tif.as_posix(),
        ls_map_img.shape[1], ls_map_img.shape[0], 1,
        gdal.GDT_Byte,
        options=["COMPRESS=PACKBITS"]
    )

    ls_mask_file.SetGeoTransform(ls_map_file.GetGeoTransform())
    ls_mask_file.SetProjection(ls_map_file.GetProjection())
    ls_mask_file.GetRasterBand(1).WriteArray(ls_map_img)
    ls_mask_file.GetRasterBand(1).SetNoDataValue(0)
    ls_mask_file.FlushCache()
    ls_mask_file = None  # noqa

    # Back-geocode Gamma0 backscatter product to map geometry using B-spline interpolation on sqrt of data
    data_in_pathname = str(nrb_paths.gamma0)
    width_in = r_dem_primary_mli_width
    lookup_table_pathname = str(dem_paths.dem_lt_fine)
    data_out_pathname = str(nrb_paths.gamma0_geo)
    width_out = dem_width
    nlines_out = const.NOT_PROVIDED
    interp_mode = 5  # B-spline interpolation sqrt(x)
    dtype = const.DTYPE_FLOAT
    lr_in = const.NOT_PROVIDED
    lr_out = const.NOT_PROVIDED
    order = 5  # Lanczos function order or B-spline degree

    pg.geocode_back(
        data_in_pathname,
        width_in,
        lookup_table_pathname,
        data_out_pathname,
        width_out,
        nlines_out,
        interp_mode,
        dtype,
        lr_in,
        lr_out,
        order,
    )

    # make quick-look png image
    pwr_pathname = str(nrb_paths.gamma0_geo)
    width = dem_width
    start = 1
    nlines = 0  # to end of file
    pixavr = 20
    pixavaz = 20
    scale = const.NOT_PROVIDED
    exp = const.NOT_PROVIDED
    lr = const.NOT_PROVIDED
    rasf_pathname = nrb_paths.gamma0_geo_tif.with_suffix(".bmp").as_posix()

    pg.raspwr(
        pwr_pathname,
        width,
        start,
        nlines,
        pixavr,
        pixavaz,
        scale,
        exp,
        lr,
        rasf_pathname,
    )

    # Convert the bitmap to a PNG w/ black pixels made transparent
    convert(
        rasf_pathname,
        nrb_paths.gamma0_geo_tif.with_suffix(".png")
    )

    # geotiff gamma0 file
    dem_par_pathname = str(dem_paths.geo_dem_par)
    data_pathname = str(nrb_paths.gamma0_geo)
    dtype = const.DTYPE_GEOTIFF_FLOAT
    geotiff_pathname = nrb_paths.gamma0_geo_tif
    nodata = 0.0

    pg.data2geotiff(
        dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
    )

    # geocode sigma0 mli
    shutil.copyfile(coreg_paths.r_dem_primary_mli, nrb_paths.sigma0)

    data_in_pathname = str(nrb_paths.sigma0)
    width_in = r_dem_primary_mli_width
    lookup_table_pathname = str(dem_paths.dem_lt_fine)
    data_out_pathname = str(nrb_paths.sigma0_geo)
    width_out = dem_width
    nlines_out = const.NOT_PROVIDED
    interp_mode = 0
    dtype = const.DTYPE_FLOAT
    lr_in = const.NOT_PROVIDED
    lr_out = const.NOT_PROVIDED

    pg.geocode_back(
        data_in_pathname,
        width_in,
        lookup_table_pathname,
        data_out_pathname,
        width_out,
        nlines_out,
        interp_mode,
        dtype,
        lr_in,
        lr_out,
    )

    # geotiff sigma0 file
    dem_par_pathname = str(dem_paths.geo_dem_par)
    data_pathname = str(nrb_paths.sigma0_geo)
    dtype = const.DTYPE_GEOTIFF_FLOAT
    geotiff_pathname = str(nrb_paths.sigma0_geo_tif)
    nodata = 0.0

    pg.data2geotiff(
        dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
    )

    # geotiff DEM
    dem_par_pathname = str(dem_paths.geo_dem_par)
    data_pathname = str(dem_paths.geo_dem)
    dtype = const.DTYPE_GEOTIFF_FLOAT
    geotiff_pathname = append_suffix(dem_paths.geo_dem, ".tif")
    nodata = 0.0

    pg.data2geotiff(
        dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
    )

    # create kml
    image_pathname = str(nrb_paths.gamma0_geo_tif.with_suffix(".png"))
    dem_par_pathname = str(dem_paths.geo_dem_par)
    kml_pathname = str(nrb_paths.gamma0_geo_tif.with_suffix(".kml"))

    pg.kml_map(
        image_pathname, dem_par_pathname, kml_pathname,
    )

    # clean up now intermittent redundant files.
    for item in [
        dem_paths.dem_offs,
        dem_paths.dem_offsets,
        dem_paths.dem_coffs,
        dem_paths.dem_coffsets,
        dem_paths.dem_lt_rough,
        nrb_paths.gamma0_geo_tif.with_suffix(".bmp"),
    ]:
        # TODO uncomment remove comment in production phase.
        if item.exists():
            # os.remove(item)
            pass

def look_vector(dem_paths: DEMPaths, coreg_paths: CoregisteredPrimaryPaths):
    """Create look vector files."""

    # create angles look vector image
    slc_par_pathname = str(coreg_paths.r_dem_primary_slc_par)
    off_par_pathname = const.NOT_PROVIDED
    dem_par_pathname = str(dem_paths.geo_dem_par)
    dem_pathname = str(dem_paths.geo_dem)
    lv_theta_pathname = str(dem_paths.dem_lv_theta)
    lv_phi_pathname = str(dem_paths.dem_lv_phi)

    pg.look_vector(
        slc_par_pathname,
        off_par_pathname,
        dem_par_pathname,
        dem_pathname,
        lv_theta_pathname,
        lv_phi_pathname,
    )

    # convert look vector files to geotiff file
    dem_par_pathname = str(dem_paths.geo_dem_par)
    data_pathname = str(dem_paths.dem_lv_theta)
    dtype = const.DTYPE_GEOTIFF_FLOAT
    geotiff_pathname = append_suffix(dem_paths.dem_lv_theta, ".tif")
    nodata = 0.0

    pg.data2geotiff(
        dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
    )

    dem_par_pathname = str(dem_paths.geo_dem_par)
    data_pathname = str(dem_paths.dem_lv_phi)
    dtype = const.DTYPE_GEOTIFF_FLOAT
    geotiff_pathname = append_suffix(dem_paths.dem_lv_phi, ".tif")
    nodata = 0.0

    pg.data2geotiff(
        dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
    )


def coregister_primary(
    log: structlog.BoundLogger,
    proc_config: ProcConfig,
    rlks: int,
    alks: int,
    multi_look: int,
    dem_patch_window: int = 1024,
    dem_rpos: Optional[int] = None,
    dem_azpos: Optional[int] = None,
    dem_offset: Tuple[int, int] = (0, 0),
    dem_offset_measure: Tuple[int, int] = (32, 32),
    dem_window: Tuple[int, int] = (256, 256),
    dem_snr: Optional[float] = None,
    dem_rad_max: int = 4,
    dem_ovr: int = 1,
    land_center: Optional[Tuple[float, float]] = None,
    ext_image_flt: Optional[Union[Path, str]] = None,
):
    """
    Generates SLC coregistered to DEM image in radar geometry.

    :param rlks:
        A range look value used on SLCs
    :param alks:
        An azimuth look value used on SLCs
    :param multi_look:
        The multi-look value (for both width and height) to use on the DEM.
    :param dem:
        A full path to a DEM image file.
    :param slc:
        A full path to a SLC image file.
    :param dem_par:
        A full path to a DEM parameter file.
    :param slc_par:
        A full path to a SLC parameter file.
    :param dem_patch_window:
        An Optional DEM patch window size.
    :param dem_rpos:
        An Optional range 'rpos' value.
    :param dem_azpos:
        An Optional azimuth 'azpos' value.
    :param dem_offset:
        An Optional dem offset value.
    :param dem_offset_measure:
        An Optional dem offset measure value.
    :param dem_window:
        An Optional dem window value.
    :param dem_snr:
        An Optional dem signal-to-noise ratio value.
    :param dem_rad_max:
        An Optional dem rad max value.
    :param dem_ovr:
        DEM oversampling factor. Default is 1.
    :param ext_image_flt:
        DISABLED: Optional full path to an external image filter to use for
        co-registration in very flat scenes with no features (rarely used).
    :param land_center:
        A user defined scene center of (latitude, longitude) to use for initial offset.
    """

    if not dem_snr:
        dem_snr = float(proc_config.dem_snr)

    dem_paths = DEMPaths(proc_config)
    primary_slc_paths = SlcPaths(
        proc_config,
        proc_config.ref_primary_scene,
        proc_config.polarisation,
        rlks
    )
    coreg_paths = CoregisteredPrimaryPaths(primary_slc_paths)

    if not coreg_paths.dem_primary_slc.exists():
        raise CoregisterDemException("Primary scene SLC is missing")

    if not coreg_paths.dem_primary_slc_par.exists():
        raise CoregisterDemException("Primary scene SLC .par is missing")

    if multi_look < 1:
        msg = "multi_look parameter needs to be >= 1"
        log.error(msg)
        raise ValueError(msg)

    """
    Adjusts DEM parameters to valid, usable values.

    Ensures DEM window meets minimum size limits. Updates patch size for DEM co-registration to
    handle resolution changes based on multi-look values, and to confirm valid patch window size
    for offset estimation.
    """
    dem_window = list(dem_window)
    dem_offset = list(dem_offset)

    dem_window[0] = dem_window[0] // multi_look

    msg = "increase DEM_WIN to fix window size (needs to be DEM_WIN/multi_look >=8)"
    if dem_window[0] < const.MIN_DEM_WIN_AXIS:
        log.info(msg, old_dem_window0=dem_window[0])
        raise ValueError(msg)  # fail fast to force bad settings to be fixed

    if dem_window[0] % 2:
        # must be an even number for Gamma's 'offset_pwrm' to work
        dem_window[0] += 1

    dem_window[1] = dem_window[1] // multi_look

    if dem_window[1] < const.MIN_DEM_WIN_AXIS:
        log.info(msg, old_dem_window1=dem_window[1])
        raise ValueError(msg)  # fail fast to force bad settings to be fixed

    if dem_window[1] % 2:
        # must be an even number for Gamma's 'offset_pwrm' to work
        dem_window[1] += 1

    # adjust patch size
    dem_patch_window = dem_patch_window // multi_look
    min_patch_size = min(const.INIT_OFFSETM_CORRELATION_PATCH_SIZES)

    if dem_patch_window < min_patch_size:
        log.info(
            "increasing DEM patch window",
            old_patch_window=dem_patch_window,
            new_patch_window=min_patch_size,
        )

        dem_patch_window = min_patch_size

    # adjust offsets
    dem_offset[0] = dem_offset[0] // multi_look
    dem_offset[1] = dem_offset[1] // multi_look

    if dem_rpos is not None:
        dem_rpos = dem_rpos // multi_look

    if dem_azpos is not None:
        dem_azpos = dem_azpos // multi_look

    if ext_image_flt is not None:
        # From Matt Garth in MS Teams on 17/8/2021: This feature was
        # developed when we had the case of processing a scene of very flat
        # terrain. In that case, the synthetic amplitude image has no
        # variation and therefore there is no features to use to align the
        # image during co-registration. I am happy for it to be left out of
        # pygamma. We haven't used the feature for many years. If we need it
        # later we can implement it at that time.

        msg = "Feature is rarely used & disabled until required"
        raise NotImplementedError(msg)

    with working_directory(dem_paths.dem_primary_name.parent):
        # copy SLC image file to new file r_dem_primary_slc.
        #
        # Note: This may seem redundant but all future processing modules expect
        # there to be "resampled" SLC/MLI data, despite the primary reference
        # scene never getting "resampled" (because it is the source of coregistration
        # other scenes are resampling TO!).
        #
        # Thus we just copy our data to these paths, to avoid the alternative: a
        # code path in every single future processing module that would use the raw
        # data for primary reference scene, and resampled for all others.
        pg.SLC_copy(
            coreg_paths.dem_primary_slc,
            coreg_paths.dem_primary_slc_par,
            coreg_paths.r_dem_primary_slc,
            coreg_paths.r_dem_primary_slc_par,
            1,  # SLC is FCOMPLEX
            const.NOT_PROVIDED,  # We aren't scaling, just a plain copy
        )

        # multi-look SLC image file
        pg.multi_look(
            coreg_paths.r_dem_primary_slc,
            coreg_paths.r_dem_primary_slc_par,
            coreg_paths.r_dem_primary_mli,
            coreg_paths.r_dem_primary_mli_par,
            rlks,
            alks,
            0  # No line offset
        )

        # Create initial .par for geocoding
        create_diff_par(
            coreg_paths.r_dem_primary_mli_par,
            None,
            dem_paths.dem_diff,
            dem_offset,
            dem_offset_measure,
            dem_window,
            dem_snr
        )

        # Produce initial DEM<->RDC geocoding LUT (and various DEM measurements in RDC)
        gen_dem_rdc(dem_paths, coreg_paths, dem_ovr=dem_ovr)

        # Read image sizes
        mli_par = pg.ParFile(str(coreg_paths.r_dem_primary_mli_par))
        r_dem_primary_mli_width = mli_par.get_value("range_samples", dtype=int, index=0)
        r_dem_primary_mli_length = mli_par.get_value("azimuth_lines", dtype=int, index=0)

        geo_dem_par = pg.ParFile(str(dem_paths.geo_dem_par))
        dem_width = geo_dem_par.get_value("width", dtype=int, index=0)
        dem_height = geo_dem_par.get_value("nlines", dtype=int, index=0)

        # Refine offset model for coregistration
        offset_calc(
            log,
            dem_paths,
            coreg_paths,
            land_center,
            dem_width,
            r_dem_primary_mli_width,
            r_dem_primary_mli_length,
            dem_patch_window,
            dem_rpos,
            dem_azpos,
            dem_snr
        )

        # Geocode products w/ coregistration LUT
        geocode(
            dem_paths,
            coreg_paths,
            dem_width,
            dem_height,
            r_dem_primary_mli_width,
            r_dem_primary_mli_length,
            dem_rad_max
        )

        # Create "look" vectors for the coregistered GEO products
        # for use by other processing modules.
        look_vector(dem_paths, coreg_paths)
