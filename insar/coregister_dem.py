#!/usr/bin/env python

import os
import tempfile
from collections import namedtuple
from typing import Optional, Tuple, Union, Dict
import shutil
from pathlib import Path
import structlog
from PIL import Image
import numpy as np
from osgeo import gdal

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.subprocess_utils import working_directory, run_command
from insar.coreg_utils import read_land_center_coords
from insar import constant as const

_LOG = structlog.get_logger("insar")


class CoregisterDemException(Exception):
    pass


pg = GammaInterface(
    subprocess_func=auto_logging_decorator(
        subprocess_wrapper, CoregisterDemException, _LOG
    )
)


def append_suffix(path: Path, suffix: str) -> Path:
    """
    A simple filename append function that that only allows for a single '.' extension,
    by keeping any existing extension as a '_' suffix.

    Example: Appending .zip to test.tif, would result in test_tif.zip, instead of test.tif.zip

    >>> append_suffix(Path('/tmp/test.tif'), '.zip').as_posix()
    '/tmp/test_tif.zip'
    """
    return path.parent / (path.name.replace(".", "_") + suffix)


class CoregisterDem:
    """TODO: DEM Coregistration docs"""

    def __init__(
        self,
        rlks: int,
        alks: int,
        shapefile: Union[Path, str],
        dem: Union[Path, str],
        slc: Union[Path, str],
        dem_par: Union[Path, str],
        slc_par: Union[Path, str],
        dem_patch_window: Optional[int] = 1024,
        dem_rpos: Optional[int] = None,
        dem_azpos: Optional[int] = None,
        dem_offset: Optional[Tuple[int, int]] = (0, 0),
        dem_offset_measure: Optional[Tuple[int, int]] = (32, 32),
        dem_window: Optional[Tuple[int, int]] = (256, 256),
        dem_snr: Optional[float] = 0.15,
        dem_rad_max: Optional[int] = 4,
        dem_ovr: int = 1,
        multi_look: int = None,
        dem_outdir: Optional[Union[Path, str]] = None,
        slc_outdir: Optional[Union[Path, str]] = None,
        ext_image_flt: Optional[Union[Path, str]] = None,
    ) -> None:
        """
        Generates DEM coregistered to SLC image in radar geometry.
        :param rlks:
            A range look value.
        :param alks:
            An azimuth look value.
        :param shapefile:
            A full path to the shape file that includes the DEM being processed.
            This file is used for determining the scene center for initial offset.
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
        :param multi_look:
            TODO: docs
        :param dem_outdir:
            An Optional full path to store dem files.
        :param slc_outdir:
            An Optional full path to store SLC files.
        :param ext_image_flt:
            An Optional full path to an external image filter to be used in co-registration.
        """
        # TODO: refactor all the paths/use ProcConfig, DemConfig ??
        self.alks = alks
        self.rlks = rlks
        self.shapefile = shapefile
        self.dem = dem
        self.slc = slc
        self.dem_par = Path(dem_par)
        self.slc_par = Path(slc_par)
        self.dem_outdir = dem_outdir
        self.slc_outdir = slc_outdir

        if self.dem_outdir is None:
            self.dem_outdir = Path(os.getcwd())
        if self.slc_outdir is None:
            self.slc_outdir = Path(self.slc).parent

        self.dem_patch_window = dem_patch_window
        self.dem_rpos = dem_rpos
        self.dem_azpos = dem_azpos
        self.dem_offset = list(dem_offset)
        self.dem_offset_measure = list(dem_offset_measure)
        self.dem_window = list(dem_window)
        self.dem_snr = dem_snr
        self.dem_rad_max = dem_rad_max
        self.dem_ovr = dem_ovr

        if multi_look is None:
            msg = "multi_look parameter needs to be >= 1"
            _LOG.error(msg)
            raise ValueError(msg)

        self.multi_look = multi_look
        self.adjust_dem_parameters()

        self.dem_master_slc = self.slc
        self.dem_master_slc_par = self.slc_par

        self.dem_width = None
        self.dem_height = None
        self.r_dem_master_mli_width = None
        self.r_dem_master_mli_length = None
        self.dem_files = self.dem_filenames(
            dem_prefix=f"{self.slc.stem}_{self.rlks}rlks", outdir=self.dem_outdir
        )
        self.dem_masters = self.dem_master_names(
            slc_prefix=f"{self.slc.stem}_{self.rlks}rlks",
            r_slc_prefix=f"r{self.slc.stem}",
            outdir=self.slc_outdir,
        )

        # set more class attributes needed for DEM-SLC co-registration
        for _key, val in {**self.dem_files, **self.dem_masters}.items():
            setattr(self, _key, val)

        if ext_image_flt is not None:
            self.ext_image_flt.symlink_to(ext_image_flt)

    @staticmethod
    def dem_master_names(
        slc_prefix: str, r_slc_prefix: str, outdir: Union[Path, str],
    ) -> Dict:
        """
        Collate DEM master file names used need in CoregisterDem class.
        :param slc_prefix:
            A pre_fix of SLC image file.
        :param r_slc_prefix:
            A prefix of radar coded SLC image file.
        :param outdir:
            A full path to store DEM co-registered SLC files.
        :returns:
            Dict with SLC file names and paths needed in CoregisterDem class.
        """

        attrs = dict()
        attrs["dem_master_mli"] = outdir.joinpath(f"{slc_prefix}.mli")
        attrs["dem_master_mli_par"] = attrs["dem_master_mli"].with_suffix(
            attrs["dem_master_mli"].suffix + ".par"
        )
        attrs["dem_master_sigma0"] = outdir.joinpath(f"{slc_prefix}.sigma0")
        attrs["dem_master_sigma0_geo"] = outdir.joinpath(f"{slc_prefix}_geo.sigma0")
        attrs["dem_master_sigma0_geo_tif"] = append_suffix(attrs["dem_master_sigma0_geo"], ".tif")
        attrs["dem_master_gamma0"] = outdir.joinpath(f"{slc_prefix}.gamma0")
        attrs["dem_master_gamma0_bmp"] = append_suffix(attrs["dem_master_gamma0"], ".bmp")
        attrs["dem_master_gamma0_geo"] = outdir.joinpath(f"{slc_prefix}_geo.gamma0")
        attrs["dem_master_gamma0_geo_bmp"] = append_suffix(attrs["dem_master_gamma0_geo"], ".bmp")
        attrs["dem_master_gamma0_geo_tif"] = append_suffix(attrs["dem_master_gamma0_geo_bmp"], ".tif")

        attrs["r_dem_master_slc"] = outdir.joinpath(f"{r_slc_prefix}.slc")
        attrs["r_dem_master_slc_par"] = outdir.joinpath(f"{r_slc_prefix}.slc.par")
        attrs["r_dem_master_mli"] = outdir.joinpath("r{}.mli".format(slc_prefix))
        attrs["r_dem_master_mli_par"] = attrs["r_dem_master_mli"].with_suffix(
            attrs["r_dem_master_mli"].suffix + ".par"
        )
        attrs["r_dem_master_mli_bmp"] = append_suffix(attrs["r_dem_master_mli"], ".bmp")
        return attrs

    @staticmethod
    def dem_filenames(dem_prefix: str, outdir: Path,) -> Dict:
        """
        Collate DEM file names used need in CoregisterDem class.
        :param dem_prefix:
            A pre_fix of dem file name.
        :param outdir:
            A full path to store DEM files generated during dem coregistration.
        :returns:
            Dict with DEM file names and paths needed in CoregisterDem class.
        """

        attrs = dict()
        attrs["dem_diff"] = outdir.joinpath(f"diff_{dem_prefix}.par")
        attrs["rdc_dem"] = outdir.joinpath(f"{dem_prefix}_rdc.dem")
        attrs["geo_dem"] = outdir.joinpath(f"{dem_prefix}_geo.dem")
        attrs["geo_dem_par"] = attrs["geo_dem"].with_suffix(
            attrs["geo_dem"].suffix + ".par"
        )
        attrs["geo_dem_geo"] = append_suffix(attrs["geo_dem"], ".tif")
        attrs["dem_lt_rough"] = outdir.joinpath(f"{dem_prefix}_rough_geo_to_rdc.lt")
        attrs["dem_geo_sim_sar"] = outdir.joinpath(f"{dem_prefix}_geo.sim")
        attrs["dem_loc_inc"] = outdir.joinpath(f"{dem_prefix}_geo.linc")
        attrs["dem_lsmap"] = outdir.joinpath(f"{dem_prefix}_geo.lsmap")
        attrs["seamask"] = outdir.joinpath(f"{dem_prefix}_geo_seamask.tif")
        attrs["dem_lt_fine"] = outdir.joinpath(f"{dem_prefix}_geo_to_rdc.lt")
        attrs["dem_geo_sim_sar"] = outdir.joinpath(f"{dem_prefix}_geo.sim")
        attrs["dem_rdc_sim_sar"] = outdir.joinpath(f"{dem_prefix}_rdc.sim")
        attrs["dem_rdc_inc"] = outdir.joinpath(f"{dem_prefix}_rdc.linc")
        attrs["ellip_pix_sigma0"] = outdir.joinpath(f"{dem_prefix}_ellip_pix_sigma0")
        attrs["dem_pix_gam"] = outdir.joinpath(f"{dem_prefix}_rdc_pix_gamma0")
        attrs["dem_pix_gam_bmp"] = attrs["dem_pix_gam"].with_suffix(".bmp")
        attrs["dem_off"] = outdir.joinpath(f"{dem_prefix}.off")
        attrs["dem_offs"] = outdir.joinpath(f"{dem_prefix}.offs")
        attrs["dem_ccp"] = outdir.joinpath(f"{dem_prefix}.ccp")
        attrs["dem_offsets"] = outdir.joinpath(f"{dem_prefix}.offsets")
        attrs["dem_coffs"] = outdir.joinpath(f"{dem_prefix}.coffs")
        attrs["dem_coffsets"] = outdir.joinpath(f"{dem_prefix}.coffsets")
        attrs["dem_lv_theta"] = outdir.joinpath(f"{dem_prefix}_geo.lv_theta")
        attrs["dem_lv_phi"] = outdir.joinpath(f"{dem_prefix}_geo.lv_phi")
        attrs["dem_lv_theta_geo"] = append_suffix(attrs["dem_lv_theta"], ".tif")
        attrs["dem_lv_phi_geo"] = append_suffix(attrs["dem_lv_phi"],".tif")

        # external image parameters to be used in co-registration
        attrs["ext_image_flt"] = outdir.joinpath(f"{dem_prefix}_ext_img_sar.flt")
        attrs["ext_image_init_sar"] = outdir.joinpath(f"{dem_prefix}_ext_img_init.sar")
        attrs["ext_image_sar"] = outdir.joinpath(f"{dem_prefix}_ext_img.sar")
        attrs["dem_check_file"] = outdir.joinpath(f"{dem_prefix}_DEM_coreg_results")

        return attrs

    def _set_attrs(self) -> None:
        """
        Internal class dem master attributes setter.
        """

        if self.r_dem_master_mli_width is None:
            mli_par = pg.ParFile(str(self.r_dem_master_mli_par))
            self.r_dem_master_mli_width = mli_par.get_value("range_samples", dtype=int, index=0)
            self.r_dem_master_mli_length = mli_par.get_value("azimuth_lines", dtype=int, index=0)

        if self.dem_width is None:
            geo_dem_par = pg.ParFile(str(self.geo_dem_par))
            self.dem_width = geo_dem_par.get_value("width", dtype=int, index=0)
            self.dem_height = geo_dem_par.get_value("nlines", dtype=int, index=0)

    def adjust_dem_parameters(self) -> None:
        """
        Adjusts DEM parameters to valid, usable values.

        Ensures DEM window meets minimum size limits. Updates patch size for DEM co-registration to
        handle resolution changes based on multi-look values, and to confirm valid patch window size
        for offset estimation.
        """
        self.dem_window[0] = int(self.dem_window[0] / self.multi_look)

        msg = "increase DEM_WIN to fix window size (needs to be DEM_WIN/multi_look >=8)"
        if self.dem_window[0] < const.MIN_DEM_WIN_AXIS:
            _LOG.info(msg, old_dem_window0=self.dem_window[0])
            raise ValueError(msg)  # fail fast to force bad settings to be fixed

        if self.dem_window[0] % 2:
            # must be an even number for Gamma's 'offset_pwrm' to work
            self.dem_window[0] += 1

        self.dem_window[1] = int(self.dem_window[1] / self.multi_look)

        if self.dem_window[1] < const.MIN_DEM_WIN_AXIS:
            _LOG.info(msg, old_dem_window1=self.dem_window[1])
            raise ValueError(msg)  # fail fast to force bad settings to be fixed

        if self.dem_window[1] % 2:
            # must be an even number for Gamma's 'offset_pwrm' to work
            self.dem_window[1] += 1

        # adjust patch size
        self.dem_patch_window = int(self.dem_patch_window / self.multi_look)
        min_patch_size = min(const.INIT_OFFSETM_CORRELATION_PATCH_SIZES)

        if self.dem_patch_window < min_patch_size:
            self.dem_patch_window = min_patch_size

            _LOG.info(
                "increasing DEM patch window",
                old_patch_window=self.dem_patch_window,
                new_patch_window=min_patch_size,
            )

        # adjust offsets
        self.dem_offset[0] = int(self.dem_offset[0] / self.multi_look)
        self.dem_offset[1] = int(self.dem_offset[1] / self.multi_look)

        if self.dem_rpos is not None:
            self.dem_rpos = int(self.dem_rpos / self.multi_look)

        if self.dem_azpos is not None:
            self.dem_azpos = int(self.dem_azpos / self.multi_look)

    def copy_slc(self, raster_out: Optional[bool] = True,) -> None:
        """
        Copy SLC with options for data format conversion.
        :param raster_out:
            An Optional flag to output raster files.
        """

        # copy SLC image file to new file r_dem_master_slc.
        # TODO this step seems redundant if we can directly use SLC image file to
        # multi-look. (Confirm with InSAR geodesy Team)

        slc_in_pathname = str(self.dem_master_slc)
        slc_par_in_pathname = str(self.dem_master_slc_par)
        slc_out_pathname = str(self.r_dem_master_slc)
        slc_par_out_pathname = str(self.r_dem_master_slc_par)
        fcase = 1  # FCOMPLEX
        sc = "-"  # scale factor

        pg.SLC_copy(
            slc_in_pathname,
            slc_par_in_pathname,
            slc_out_pathname,
            slc_par_out_pathname,
            fcase,
            sc,
        )

        # multi-look SLC image file
        slc_pathname = str(self.r_dem_master_slc)
        slc_par_pathname = str(self.r_dem_master_slc_par)
        mli_pathname = str(self.r_dem_master_mli)
        mli_par_pathname = str(self.r_dem_master_mli_par)
        rlks = self.rlks
        azlks = self.alks
        loff = 0  # offset to starting line

        pg.multi_look(
            slc_pathname,
            slc_par_pathname,
            mli_pathname,
            mli_par_pathname,
            rlks,
            azlks,
            loff,
        )

        # output raster image of multi-looked SLC image file if needed
        # TODO only useful for visual debugging phase.
        # This is redundant in production phase (Consult InSAR team and remove)
        if raster_out:
            pwr_pathname = str(self.r_dem_master_mli)
            mli_par = pg.ParFile(str(self.r_dem_master_mli_par))
            width = mli_par.get_value("range_samples", dtype=int, index=0)
            start = 1
            nlines = 0  # default (to end of file)
            pixavr = 20
            pixavaz = 20
            scale = 1.0
            exp = 0.35
            lr = 1  # left/right mirror image flag
            rasf_pathname = str(self.r_dem_master_mli_bmp)

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

    def gen_dem_rdc(self, use_external_image: Optional[bool] = False,) -> None:
        """
        Generate DEM coregistered to slc in rdc geometry.
        :param use_external_image:
            An Optional parameter to set use of external image for co-registration.
        """

        # generate initial geocoding look-up-table and simulated SAR image

        mli_par_pathname = str(self.r_dem_master_mli_par)
        off_par_pathname = "-"
        dem_par_pathname = str(self.dem_par)
        dem_pathname = str(self.dem)
        dem_seg_par_pathname = str(self.geo_dem_par)
        dem_seg_pathname = str(self.geo_dem)
        lookup_table_pathname = str(self.dem_lt_rough)
        lat_ovr = self.dem_ovr
        lon_ovr = self.dem_ovr
        sim_sar_pathname = str(self.dem_geo_sim_sar)
        u_zenith_angle = "-"
        v_orientation_angle = "-"
        inc_angle_pathname = str(self.dem_loc_inc)
        psi_projection_angle = "-"
        pix = "-"  # pixel area normalization factor
        ls_map_pathname = str(self.dem_lsmap)
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
                str(self.dem_diff),
                const.NOT_PROVIDED  # reference image flag (simulated SAR is the default)
            )

        # generate initial gamma0 pixel normalisation area image in radar geometry
        mli_par_pathname = str(self.r_dem_master_mli_par)
        dem_par_pathname = str(self.geo_dem_par)
        dem_pathname = str(self.geo_dem)
        lookup_table_pathname = str(self.dem_lt_rough)
        ls_map_pathname = str(self.dem_lsmap)
        inc_map_pathname = str(self.dem_loc_inc)
        pix_sigma0_pathname = "-"  # no output
        pix_gamma0_pathname = str(self.dem_pix_gam)

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

        # any of the dem master mli size is not set. Set the dem size attributes.
        if any(
            item is None
            for item in [
                self.r_dem_master_mli_width,
                self.r_dem_master_mli_length,
                self.dem_width,
            ]
        ):
            self._set_attrs()

        if use_external_image:
            # transform simulated SAR intensity image to radar geometry
            dem1_par_pathname = str(self.dem_par)
            data1_pathname = str(self.ext_image)
            dem2_par_pathname = str(self.geo_dem_par)
            data2_pathname = str(self.ext_image_flt)
            lat_ovr = 1
            lon_ovr = 1
            interp_mode = 1  # bicubic spline
            dtype = 0  # FLOAT
            bflg = "-"  # use DEM bounds specified by dem2_par_pathname

            pg.map_trans(
                dem1_par_pathname,
                data1_pathname,
                dem2_par_pathname,
                data2_pathname,
                lat_ovr,
                lon_ovr,
                interp_mode,
                dtype,
                bflg,
            )

            # transform external image to radar geometry
            lookup_table_pathname = str(self.dem_lt_rought)
            data_in_pathname = str(self.ext_image_flt)
            width_in = self.dem_width
            data_out_pathname = str(self.ext_image_init_sar)
            width_out = self.r_dem_master_mli_width
            nlines_out = self.r_dem_master_mli_length
            interp_mode = 1  # nearest neighbor
            dtype = 0  # FLOAT
            lr_in = "-"
            lr_out = "-"
            n_ovr = 2
            rad_max = 4
            nintr = "-"  # n points for interpolation when not nearest neighbor

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

    def create_diff_par(self) -> None:
        """Fine coregistration of master MLI and simulated SAR image."""
        with tempfile.TemporaryDirectory() as temp_dir:
            return_file = Path(temp_dir).joinpath("returns")
            with open(return_file, "w") as fid:
                fid.write("" + "\n")
                fid.write("{} {}\n".format(*self.dem_offset))
                fid.write("{} {}\n".format(*self.dem_offset_measure))
                fid.write("{} {}\n".format(*self.dem_window))
                fid.write("{}".format(self.dem_snr))

            # FIXME: non-interactive would be better...
            command = [
                "create_diff_par",
                self.r_dem_master_mli_par.as_posix(),
                "-",
                self.dem_diff.as_posix(),
                "1",
                "<",
                return_file.as_posix(),
            ]
            run_command(command, os.getcwd())

    def offset_calc(
        self, npoly: Optional[int] = 1, use_external_image: Optional[bool] = False,
    ) -> None:
        """Offset computation. (Need more information from InSAR team).
        :param npoly:
            An Optional nth order polynomial term. Otherwise set to default for
            Sentinel-1 acquisitions.
        :param use_external_image:
            An Optional parameter to set use of external image for co-registration.
        """
        # set parameters
        if any(
            item is None
            for item in [
                self.r_dem_master_mli_width,
                self.r_dem_master_mli_length,
                self.dem_width,
            ]
        ):
            self._set_attrs()

        # Read land center coordinates from shape file
        land_center = read_land_center_coords(pg, self.r_dem_master_mli_par, Path(self.shapefile))

        if land_center is not None:
            _LOG.info(
                "Land center for DEM coregistration determined from shape file",
                mli=self.r_dem_master_mli,
                shapefile=self.shapefile,
                land_center=land_center
            )

            rpos, azpos = land_center

        else:
            rpos, azpos = None, None

        # MCG: Urs Wegmuller recommended using pixel_area_gamma0 rather than simulated SAR image in offset calculation
        mli_1_pathname = str(self.dem_pix_gam)
        mli_2_pathname = str(self.r_dem_master_mli)
        diff_par_pathname = str(self.dem_diff)
        rlks = 1
        azlks = 1
        rpos = self.dem_rpos or rpos
        azpos = self.dem_azpos or azpos
        offr = const.NOT_PROVIDED
        offaz = const.NOT_PROVIDED
        thres = self.dem_snr
        patch = self.dem_patch_window
        cflag = 1  # copy constant range and azimuth offsets

        pg.init_offsetm(
            mli_1_pathname,
            mli_2_pathname,
            diff_par_pathname,
            rlks,
            azlks,
            rpos,
            azpos,
            offr,
            offaz,
            thres,
            patch,
            cflag,
        )

        mli_1_pathname = str(self.dem_pix_gam)
        mli_2_pathname = str(self.r_dem_master_mli)
        diff_par_pathname = str(self.dem_diff)
        offs_pathname = str(self.dem_offs)
        ccp_pathname = str(self.dem_ccp)
        rwin = "-"  # range patch size
        azwin = "-"  # azimuth patch size
        offsets_pathname = str(self.dem_offsets)
        n_ovr = 2
        nr = "-"  # number of offset estimates in range direction
        naz = "-"  # number of offset estimates in azimuth direction
        thres = "-"  # Lanczos interpolator order

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

        offs_pathname = str(self.dem_offs)
        ccp_pathname = str(self.dem_ccp)
        diff_par_pathname = str(self.dem_diff)
        coffs_pathname = str(self.dem_coffs)
        coffsets_pathname = str(self.dem_coffsets)
        thres = "-"

        pg.offset_fitm(
            offs_pathname,
            ccp_pathname,
            diff_par_pathname,
            coffs_pathname,
            coffsets_pathname,
            thres,
            npoly,
        )

        # refinement of initial geo-coding look-up-table
        ref_flg = 1
        if use_external_image:
            ref_flg = 0

        gc_in_pathname = str(self.dem_lt_rough)
        width = self.dem_width
        diff_par_pathname = str(self.dem_diff)
        gc_out_pathname = str(self.dem_lt_fine)

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

            mli_par_pathname = str(self.r_dem_master_mli_par)
            dem_par_pathname = str(self.geo_dem_par)
            dem_pathname = str(self.geo_dem)
            lookup_table_pathname = str(self.dem_lt_fine)
            ls_map_pathname = str(self.dem_lsmap)
            inc_map_pathname = str(self.dem_loc_inc)
            pix_sigma0 = "-"
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
            data_out_pathname = str(self.dem_pix_gam)
            width = self.r_dem_master_mli_width
            r_max = "-"  # maximum interpolation window radius
            np_min = "-"  # minimum number of points used for the interpolation
            np_max = "-"  # maximum number of points used for the interpolation
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

            mli_pathname = str(self.r_dem_master_mli)
            mli_par_pathname = str(self.r_dem_master_mli_par)
            off_par = "-"  # ISP offset/interferogram parameter file
            cmli = str(sigma0)  # radiometrically calibrated output MLI
            antenna = "-"  # 1-way antenna gain pattern file
            rloss_flag = 0  # range spreading loss correction
            ant_flag = 0  # antenna pattern correction
            refarea_flag = 1  # reference pixel area correction
            sc_db = "-"  # scale factor in dB
            k_db = "-"  # calibration factor in dB
            pix_area_pathname = str(self.ellip_pix_sigma0)

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

            # Generate Gamma0 backscatter image for master scene according to equation
            # in Section 10.6 of Gamma Geocoding and Image Registration Users Guide
            temp1 = Path(temp_dir).joinpath("temp1")

            d1_pathname = str(self.r_dem_master_mli)
            d2_pathname = str(self.ellip_pix_sigma0)
            d_out_pathname = str(temp1)
            width = self.r_dem_master_mli_width
            mode = 2  # multiplication

            pg.float_math(
                d1_pathname, d2_pathname, d_out_pathname, width, mode,
            )

            d1_pathname = str(temp1)
            d2_pathname = str(self.dem_pix_gam)
            d_out_pathname = str(self.dem_master_gamma0)
            width = self.r_dem_master_mli_width
            mode = 3  # division

            pg.float_math(
                d1_pathname, d2_pathname, d_out_pathname, width, mode,
            )

            # create raster for comparison with master mli raster
            pwr_pathname = str(self.dem_master_gamma0)
            width = self.r_dem_master_mli_width
            start = 1
            nlines = 0  # 0 is to end of file
            pixavr = 20
            pixavaz = 20
            scale = 1.0
            exp = 0.35
            lr = 1  # left/right mirror image flag
            rasf_pathname = str(self.dem_master_gamma0_bmp)

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

            f_in_pathname = str(self.geo_dem)
            value = 0.0001
            new_value = 0
            f_out_pathname = str(temp)
            width = self.dem_width
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
            pwr_pathname = "-"
            width = self.dem_width
            start_hgt = 1
            start_pwr = 1
            nlines = 0
            pixavr = 1
            pixavaz = 1
            m_per_cycle = 100.0  # metres per color cycle
            scale = "-"  # display scale factor
            exp = "-"  # display exponent
            lr = "-"  # left/right mirror image flag
            rasf_pathname = str(self.seamask)

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
        self, use_external_image: Optional[bool] = False,
    ):
        """
        Method to geocode image files to radar geometry.
        :param use_external_image:
            An Optional external image is to be used for co-registration.
        """

        # set parameters
        if any(
            item is None
            for item in [
                self.r_dem_master_mli_width,
                self.r_dem_master_mli_length,
                self.dem_width,
            ]
        ):
            self._set_attrs()

        # geocode map geometry DEM to radar geometry
        lookup_table_pathname = str(self.dem_lt_fine)
        data_in_pathname = str(self.geo_dem)
        width_in = self.dem_width
        data_out_pathname = str(self.rdc_dem)
        width_out = self.r_dem_master_mli_width
        nlines_out = self.r_dem_master_mli_length
        interp_mode = 1
        dtype = 0  # FLOAT
        lr_in = "-"
        lr_out = "-"
        n_ovr = 2
        rad_max = self.dem_rad_max
        nintr = "-"  # number of points required for interpolation

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

            hgt_pathname = str(self.rdc_dem)
            pwr_pathname = str(self.r_dem_master_mli)
            width = self.r_dem_master_mli_width
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
                self.dem_outdir.joinpath(self.rdc_dem.stem).with_suffix(".png")
            )

        # Geocode simulated SAR intensity image to radar geometry
        lookup_table_pathname = str(self.dem_lt_fine)
        data_in_pathname = str(self.dem_geo_sim_sar)
        width_in = self.dem_width
        data_out_pathname = str(self.dem_rdc_sim_sar)
        width_out = self.r_dem_master_mli_width
        nlines_out = self.r_dem_master_mli_length
        interp_mode = 0  # resampling interpolation; 1/dist
        dtype = 0  # FLOAT
        lr_in = "-"
        lr_out = "-"
        n_ovr = 2
        rad_max = self.dem_rad_max  # maximum interpolation search radius
        nintr = "-"  # number of points required for interpolation

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
        lookup_table_pathname = str(self.dem_lt_fine)
        data_in_pathname = str(self.dem_loc_inc)
        width_in = self.dem_width
        data_out_pathname = str(self.dem_rdc_inc)
        width_out = self.r_dem_master_mli_width
        nlines_out = self.r_dem_master_mli_length
        interp_mode = 0  # resampling interpolation; 1/dist
        dtype = 0  # FLOAT
        lr_in = "-"
        lr_out = "-"
        n_ovr = 2
        rad_max = self.dem_rad_max  # maximum interpolation search radius
        nintr = "-"  # number of points required for interpolation

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
            lookup_table_pathname = str(self.dem_lt_fine)
            data_in_pathname = str(self.ext_image_flt)
            width_in = self.dem_width
            data_out_pathname = str(self.ext_image_sar)
            width_out = self.r_dem_master_mli_width
            nlines_out = self.r_dem_master_mli_length
            interp_mode = 0  # resampling interpolation; 1/dist
            dtype = 0  # FLOAT
            lr_in = "-"
            lr_out = "-"
            n_ovr = 2
            rad_max = self.dem_rad_max  # maximum interpolation search radius
            nintr = "-"  # number of points required for interpolation

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

        # Convert lsmap to geotiff
        ls_map_tif = str(append_suffix(self.dem_lsmap, ".tif"))
        pg.data2geotiff(
            str(self.geo_dem_par),
            str(self.dem_lsmap),
            5,  # data type (BYTE)
            ls_map_tif,  # output oath
            0.0,  # No data
        )

        # Create CARD4L mask (1 = good pixel, 0 = bad)
        ls_map_file = gdal.Open(ls_map_tif)
        ls_map_img = ls_map_file.ReadAsArray()

        # Sanity check
        assert(ls_map_img.shape[0] == self.dem_height)
        assert(ls_map_img.shape[1] == self.dem_width)

        # Simply turn non-good pixels to 0 (all that remains then is the good pixels which are already 1)
        ls_map_img[ls_map_img != 1] = 0

        # Save this back out as a geotiff w/ identical projection as the lsmap
        ls_map_mask_tif = append_suffix(self.dem_lsmap, "_mask.tif")
        ls_mask_file = gdal.GetDriverByName("GTiff").Create(
            ls_map_mask_tif.as_posix(),
            ls_map_img.shape[1], ls_map_img.shape[0], 1,
            gdal.GDT_Byte,
            options = ["COMPRESS=PACKBITS"]
        )

        ls_mask_file.SetGeoTransform(ls_map_file.GetGeoTransform())
        ls_mask_file.SetProjection(ls_map_file.GetProjection())
        ls_mask_file.GetRasterBand(1).WriteArray(ls_map_img)
        ls_mask_file.GetRasterBand(1).SetNoDataValue(0)
        ls_mask_file.FlushCache()
        ls_mask_file = None

        # Back-geocode Gamma0 backscatter product to map geometry using B-spline interpolation on sqrt of data
        data_in_pathname = str(self.dem_master_gamma0)
        width_in = self.r_dem_master_mli_width
        lookup_table_pathname = str(self.dem_lt_fine)
        data_out_pathname = str(self.dem_master_gamma0_geo)
        width_out = self.dem_width
        nlines_out = "-"
        interp_mode = 5  # B-spline interpolation sqrt(x)
        dtype = 0  # FLOAT
        lr_in = "-"
        lr_out = "-"
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
        pwr_pathname = str(self.dem_master_gamma0_geo)
        width = self.dem_width
        start = 1
        nlines = 0  # to end of file
        pixavr = 20
        pixavaz = 20
        scale = "-"
        exp = "-"
        lr = "-"
        rasf_pathname = str(self.dem_master_gamma0_geo_bmp)

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
        img = Image.open(self.dem_master_gamma0_geo_bmp.as_posix())
        img = np.array(img.convert("RGBA"))
        img[(img[:, :, :3] == (0, 0, 0)).all(axis=-1)] = (0, 0, 0, 0)
        Image.fromarray(img).save(
            self.dem_master_gamma0_geo_bmp.with_suffix(".png").as_posix()
        )

        # geotiff gamma0 file
        dem_par_pathname = str(self.geo_dem_par)
        data_pathname = str(self.dem_master_gamma0_geo)
        dtype = 2  # FLOAT
        geotiff_pathname = self.dem_master_gamma0_geo_tif
        nodata = 0.0

        pg.data2geotiff(
            dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
        )

        # geocode sigma0 mli
        shutil.copyfile(self.r_dem_master_mli, self.dem_master_sigma0)

        data_in_pathname = str(self.dem_master_sigma0)
        width_in = self.r_dem_master_mli_width
        lookup_table_pathname = str(self.dem_lt_fine)
        data_out_pathname = str(self.dem_master_sigma0_geo)
        width_out = self.dem_width
        nlines_out = "-"
        interp_mode = 0
        dtype = 0  # FLOAT
        lr_in = "-"
        lr_out = "-"

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
        dem_par_pathname = str(self.geo_dem_par)
        data_pathname = str(self.dem_master_sigma0_geo)
        dtype = 2  # FLOAT
        geotiff_pathname = str(self.dem_master_sigma0_geo_tif)
        nodata = 0.0

        pg.data2geotiff(
            dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
        )

        # geotiff DEM
        dem_par_pathname = str(self.geo_dem_par)
        data_pathname = str(self.geo_dem)
        dtype = 2  # FLOAT
        geotiff_pathname = str(self.geo_dem_geo)
        nodata = 0.0

        pg.data2geotiff(
            dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
        )

        # create kml
        image_pathname = str(self.dem_master_gamma0_geo_bmp.with_suffix(".png"))
        dem_par_pathname = str(self.geo_dem_par)
        kml_pathname = str(self.dem_master_gamma0_geo_bmp.with_suffix(".kml"))

        pg.kml_map(
            image_pathname, dem_par_pathname, kml_pathname,
        )

        # clean up now intermittent redundant files.
        for item in [
            self.dem_offs,
            self.dem_offsets,
            self.dem_coffs,
            self.dem_coffsets,
            self.dem_lt_rough,
            self.dem_master_gamma0_geo_bmp,
        ]:
            # TODO uncomment remove comment in production phase.
            if item.exists():
                # os.remove(item)
                pass

    def look_vector(self):
        """Create look vector files."""

        # create angles look vector image
        slc_par_pathname = str(self.r_dem_master_slc_par)
        off_par_pathname = "-"
        dem_par_pathname = str(self.geo_dem_par)
        dem_pathname = str(self.geo_dem)
        lv_theta_pathname = str(self.dem_lv_theta)
        lv_phi_pathname = str(self.dem_lv_phi)

        pg.look_vector(
            slc_par_pathname,
            off_par_pathname,
            dem_par_pathname,
            dem_pathname,
            lv_theta_pathname,
            lv_phi_pathname,
        )

        # convert look vector files to geotiff file
        dem_par_pathname = str(self.geo_dem_par)
        data_pathname = str(self.dem_lv_theta)
        dtype = 2  # FLOAT
        geotiff_pathname = str(self.dem_lv_theta_geo)
        nodata = 0.0

        pg.data2geotiff(
            dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
        )

        dem_par_pathname = str(self.geo_dem_par)
        data_pathname = str(self.dem_lv_phi)
        dtype = 2  # FLOAT
        geotiff_pathname = str(self.dem_lv_phi_geo)
        nodata = 0.0

        pg.data2geotiff(
            dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
        )

    def main(self):
        """Main method to execute SLC-DEM coregistration task in sequence."""

        self.dem_outdir.mkdir(exist_ok=True)
        with working_directory(self.dem_outdir):
            self.copy_slc()
            self.create_diff_par()
            self.gen_dem_rdc()
            self.offset_calc()
            self.geocode()
            self.look_vector()
