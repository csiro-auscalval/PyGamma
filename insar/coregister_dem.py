#!/usr/bin/env python

import os
import tempfile
from collections import namedtuple
from typing import Optional, Tuple, Union, Dict
import shutil
from pathlib import Path
import structlog

import py_gamma as pg
from insar.subprocess_utils import working_directory, run_command, environ
from insar.logs import COMMON_PROCESSORS

# _LOG = logging.getLogger(__name__)
structlog.configure(processors=COMMON_PROCESSORS)
_LOG = structlog.get_logger()


class SlcParFileParser:
    def __init__(self, par_file: Union[Path, str]) -> None:
        """
        Convenient access fields for SLC image parameter properties.

        :param par_file:
            A full path to a SLC parameter file.
        """
        self.par_file = Path(par_file).as_posix()
        self.par_vals = pg.ParFile(self.par_file)
    
    @property
    def slc_par_params(self):
        """
        Convenient SLC parameter access method needed for SLC-DEM co-registration.
        """
        par_params = namedtuple("slc_par_params", ["range_samples", "azimuth_lines"])
        return par_params(
            self.par_vals.get_value("range_samples", dtype=int, index=0),
            self.par_vals.get_value("azimuth_lines", dtype=int, index=0),
        )


class DemParFileParser:
    def __init__(self, par_file: Union[Path, str]) -> None:
        """
        Convenient access fileds for DEM image parameter properties.

        :param par_file:
            A full path to a DEM parameter file.
        """
        self.par_file = Path(par_file).as_posix()
        self.dem_par_vals = pg.ParFile(self.par_file)
    
    @property
    def dem_par_params(self):
        """
        Convenient DEM parameter access method need for SLC-DEM co-registration.
        """
        par_params = namedtuple("dem_par_params", ["post_lon", "width"])
        return par_params(
            self.dem_par_vals.get_value("post_lon", dtype=float, index=0),
            self.dem_par_vals.get_value("width", dtype=int, index=0),
        )


class CoregisterDem:
    def __init__(
        self,
        rlks: int,
        alks: int,
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
        :param r_pos:
            An Optional range 'rpos' value.
        :param azpos:
            An Optional azimuth 'azpos' value.
        :param dem_offset:
            An Optional dem offset value.
        :param dem offset measure:
            An Optional dem offset measure value.
        :param dem_window:
            An Optional dem window value.
        :param dem_snr:
            An Optional dem signal-to-noise ratio value.
        :param dem_rad_max:
            An Optional dem rad max value.
        :param dem_outdir:
            An Optional full path to store dem files.
        :param slc_outdir:
            An Optional full path to store SLC files.
        :param ext_image_flt:
            An Optional full path to an external image filter to be used in co-registration.
        """

        self.alks = alks
        self.rlks = rlks
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

        # adjust dem parameters for range looks greater than 1
        if self.rlks > 1:
            self.adjust_dem_parameter()

        self.dem_master_slc = self.slc
        self.dem_master_slc_par = self.slc_par

        self.dem_ovr = None
        self.dem_width = None
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
    def dem_master_names(slc_prefix: str, r_slc_prefix: str, outdir: Union[Path, str]) -> Dict:
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
        attrs["dem_master_sigma0_eqa"] = outdir.joinpath(f"{slc_prefix}_eqa.sigma0")
        attrs["dem_master_sigma0_eqa_geo"] = attrs["dem_master_sigma0_eqa"].with_suffix(
            attrs["dem_master_sigma0_eqa"].suffix + ".tif"
        )
        attrs["dem_master_gamma0"] = outdir.joinpath(f"{slc_prefix}.gamma0")
        attrs["dem_master_gamma0_bmp"] = attrs["dem_master_gamma0"].with_suffix(
            attrs["dem_master_gamma0"].suffix + ".bmp"
        )
        attrs["dem_master_gamma0_eqa"] = outdir.joinpath(f"{slc_prefix}_eqa.gamma0")
        attrs["dem_master_gamma0_eqa_bmp"] = attrs["dem_master_gamma0_eqa"].with_suffix(
            attrs["dem_master_gamma0_eqa"].suffix + ".bmp"
        )
        attrs["dem_master_gamma0_eqa_geo"] = attrs["dem_master_gamma0_eqa"].with_suffix(
            attrs["dem_master_gamma0_eqa"].suffix + ".tif"
        )

        attrs["r_dem_master_slc"] = outdir.joinpath(f"{r_slc_prefix}.slc")
        attrs["r_dem_master_slc_par"] = outdir.joinpath(f"{r_slc_prefix}.slc.par")
        attrs["r_dem_master_mli"] = outdir.joinpath("r{}.mli".format(slc_prefix))
        attrs["r_dem_master_mli_par"] = attrs["r_dem_master_mli"].with_suffix(
            attrs["r_dem_master_mli"].suffix + ".par"
        )
        attrs["r_dem_master_mli_bmp"] = attrs["r_dem_master_mli"].with_suffix(
            attrs["r_dem_master_mli"].suffix + ".bmp"
        )
        return attrs

    @staticmethod
    def dem_filenames(dem_prefix: str, outdir: Path) -> Dict:
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
        attrs["eqa_dem"] = outdir.joinpath(f"{dem_prefix}_eqa.dem")
        attrs["eqa_dem_par"] = attrs["eqa_dem"].with_suffix(
            attrs["eqa_dem"].suffix + ".par"
        )
        attrs["eqa_dem_geo"] = attrs["eqa_dem"].with_suffix(
            attrs["eqa_dem"].suffix + ".tif"
        )
        attrs["dem_lt_rough"] = outdir.joinpath(f"{dem_prefix}_rough_eqa_to_rdc.lt")
        attrs["dem_eqa_sim_sar"] = outdir.joinpath(f"{dem_prefix}_eqa.sim")
        attrs["dem_loc_inc"] = outdir.joinpath(f"{dem_prefix}_eqa.linc")
        attrs["dem_lsmap"] = outdir.joinpath(f"{dem_prefix}_eqa.lsmap")
        attrs["seamask"] = outdir.joinpath(f"{dem_prefix}_eqa_seamask.tif")
        attrs["dem_lt_fine"] = outdir.joinpath(f"{dem_prefix}_eqa_to_rdc.lt")
        attrs["dem_eqa_sim_sar"] = outdir.joinpath(f"{dem_prefix}_eqa.sim")
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
        attrs["dem_lv_theta"] = outdir.joinpath(f"{dem_prefix}_eqa.lv_theta")
        attrs["dem_lv_phi"] = outdir.joinpath(f"{dem_prefix}_eqa.lv_phi")
        attrs["dem_lv_theta_geo"] = attrs["dem_lv_theta"].with_suffix(
            attrs["dem_lv_theta"].suffix + ".tif"
        )
        attrs["dem_lv_phi_geo"] = attrs["dem_lv_phi"].with_suffix(
            attrs["dem_lv_phi"].suffix + ".tif"
        )

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
            mli_par = SlcParFileParser(self.r_dem_master_mli_par)
            self.r_dem_master_mli_width = mli_par.slc_par_params.range_samples
            self.r_dem_master_mli_length = mli_par.slc_par_params.azimuth_lines

        if self.dem_width is None:
            eqa_dem_params = DemParFileParser(self.eqa_dem_par)
            self.dem_width = eqa_dem_params.dem_par_params.width

    def adjust_dem_parameter(self) -> None:
        """
        Function to adjust the DEM parameters.
        """

        self.dem_window[0] = int(self.dem_window[0] / self.rlks)
        if self.dem_window[0] < 8:
            win1 = round(self.dem_window[0] * self.rlks) * 2
            _LOG.info(
                "increasing DEM window1 size",
                old_window=self.dem_window[0],
                new_window=win1
            )
            self.dem_window[0] = win1

        self.dem_window[1] = int(self.dem_window[1] / self.rlks)
        if self.dem_window[1] < 8:
            win2 = round(self.dem_window[1] * self.rlks) * 2
            _LOG.info(
                "increasing DEM window2 size",
                old_window=self.dem_window[2],
                new_window=win2
            )
            self.dem_window[1] = win2

        if self.dem_patch_window / self.rlks < 128.0:
            _LOG.info(
                "increasing DEM patch window",
                old_patch_window=self.dem_patch_window,
                new_patch_window=128
            )
            self.dem_patch_window = 128

        self.dem_offset[0] = int(self.dem_offset[0] / self.rlks)
        self.dem_offset[1] = int(self.dem_offset[1] / self.rlks)

        if self.dem_rpos is not None:
            self.dem_rpos = int(self.dem_rpos / self.rlks)
        if self.dem_azpos is not None:
            self.dem_azpos = int(self.dem_azpos / self.rlks)

    def copy_slc(self, raster_out: Optional[bool] = True) -> None:
        """
        Copy SLC with options for data format conversion.

        :param raster_out:
            An Optional flag to output raster files.
        """

        # copy SLC image file to new file r_dem_master_slc.
        # TODO this step seems redundant if we can directly use SLC image file to
        # multi-look. (Confirm with InSAR geodesy Team)
        cout = []
        cerr = []
        slc_in_pathname = str(self.dem_master_slc)
        slc_par_in_pathname = str(self.dem_master_slc_par)
        slc_out_pathname = str(self.r_dem_master_slc)
        slc_par_out_pathname = str(self.r_dem_master_slc_par)
        fcase = 1  # FCOMPLEX
        sc = "-"  # scale factor
        stat = pg.SLC_copy(
            slc_in_pathname,
            slc_par_in_pathname,
            slc_out_pathname,
            slc_par_out_pathname,
            fcase,
            sc,
            cout=cout,
            cerr=cerr,
            stdout_flag=False,
            stderr_flag=False
        )

        if stat != 0:
            msg = "failed to execute pg.SLC_copy"
            _LOG.error(
                msg,
                slc_in_pathname=slc_in_pathname,
                slc_par_in_pathname=slc_par_in_pathname,
                slc_out_pathname=slc_out_pathname,
                slc_par_out_pathname=slc_par_out_pathname,
                fcase=fcase,
                sc=sc,
                stat=stat,
                gamma_error=cerr
            )
            raise Exception(msg)

        # multi-look SLC image file
        cout = []
        cerr = []
        slc_pathname = str(self.r_dem_master_slc)
        slc_par_pathname = str(self.r_dem_master_slc_par)
        mli_pathname = str(self.r_dem_master_mli)
        mli_par_pathname = str(self.r_dem_master_mli_par)
        rlks = self.rlks
        azlks = self.alks
        loff = 0  # offset to starting line
        stat = pg.multi_look(
            slc_pathname,
            slc_par_pathname,
            mli_pathname,
            mli_par_pathname,
            rlks,
            azlks,
            loff,
            cout=cout,
            cerr=cerr,
            stdout_flag=False,
            stderr_flag=False
        )

        if stat != 0:
            msg = "failed to execute pg.multi_look"
            _LOG.error(
                msg,
                slc_pathname=slc_pathname,
                slc_par_pathname=slc_par_pathname,
                mli_pathname=mli_pathname,
                mli_par_pathname=mli_par_pathname,
                rlks=rlks,
                azlks=azlks,
                loff=loff,
                stat=stat,
                gamma_error=cerr
            )
            raise Exception(msg)

        # output raster image of multi-looked SLC image file if needed
        # TODO only useful for visual debugging phase.
        # This is redundant in production phase (Consult InSAR team and remove)
        if raster_out:
            params = SlcParFileParser(self.r_dem_master_mli_par)
            cout = []
            cerr = []
            pwr_pathname = str(self.r_dem_master_mli)
            width = params.slc_par_params.range_samples
            start = 1
            nlines = 0  # default (to end of file)
            pixavr = 20
            pixavaz = 20
            scale = 1.0
            exp = 0.35
            lr = 1  # left/right mirror image flag
            rasf_pathname = str(self.r_dem_master_mli_bmp)
            stat = pg.raspwr(
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
                cout=cout,
                cerr=cerr,
                stdout_flag=False,
                stderr_flag=False
            )

            if stat != 0:
                msg = "failed to execute pg.raspwr"
                _LOG.error(
                    msg,
                    pwr_pathname=pwr_pathname,
                    width=width,
                    start=start,
                    nlines=nlines,
                    pixavr=pixavr,
                    pixavaz=pixavaz,
                    scale=scale,
                    exp=exp,
                    lr=lr,
                    rasf_pathname=rasf_pathname,
                    stat=stat,
                    gamma_error=cerr
                )
                raise Exception(msg)

    def over_sample(self) -> None:
        """Returns oversampling factor for DEM coregistration."""

        params = DemParFileParser(self.dem_par)
        post_lon = params.dem_par_params.post_lon

        # 0.4 arc second or smaller DEMs resolution
        if post_lon <= 0.00011111:
            self.dem_ovr = 1
        # greater than 0.4 or less then 3 arc seconds DEMs resolution
        elif 0.00011111 < post_lon < 0.0008333:
            self.dem_ovr = 4
        # other DEMs resolution
        else:
            self.dem_ovr = 8

    def gen_dem_rdc(self, use_external_image: Optional[bool] = False) -> None:
        """
        Generate DEM coregistered to slc in rdc geometry.

        :param use_external_image:
            An Optional parameter to set use of external image for co-registration.
        """

        # generate initial geocoding look-up-table and simulated SAR image
        cout = []
        cerr = []
        mli_par_pathname = str(self.r_dem_master_mli_par)
        off_par_pathname = "-"
        dem_par_pathname = str(self.dem_par)
        dem_pathname = str(self.dem)
        dem_seg_par_pathname = str(self.eqa_dem_par)
        dem_seg_pathname = str(self.eqa_dem)
        lookup_table_pathname = str(self.dem_lt_rough)
        lat_ovr = self.dem_ovr
        lon_ovr = self.dem_ovr
        sim_sar_pathname = str(self.dem_eqa_sim_sar)
        u_zenith_angle = "-"
        v_orientation_angle = "-"
        inc_angle_pathname = str(self.dem_loc_inc)
        psi_projection_angle = "-"
        pix = "-"  # pixel area normalization factor
        ls_map_pathname = str(self.dem_lsmap)
        frame = 8
        ls_mode = 2
        stat = pg.gc_map1(
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
            cout=cout,
            cerr=cerr,
            stdout_flag=False,
            stderr_flag=False
        )

        if stat != 0:
            msg = "failed to execute pg.gc_map1"
            _LOG.error(
                msg,
                mli_par_pathname=mli_par_pathname,
                off_par_pathname=off_par_pathname,
                dem_par_pathname=dem_par_pathname,
                dem_pathname=dem_pathname,
                dem_seg_par_pathname=dem_seg_par_pathname,
                dem_seg_pathname=dem_seg_pathname,
                lookup_table_pathname=lookup_table_pathname,
                lat_ovr=lat_ovr,
                lon_ovr=lon_ovr,
                sim_sar_pathname=sim_sar_pathname,
                u_zenith_angle=u_zenith_angle,
                v_orientation_angle=v_orientation_angle,
                inc_angle_pathname=inc_angle_pathname,
                psi_projection_angle=psi_projection_angle,
                pix=pix,
                ls_map_pathname=ls_map_pathname,
                frame=frame,
                ls_mode=ls_mode,
                stat=stat,
                gamma_error=cerr
            )
            raise Exception(msg)

        # generate initial gamma0 pixel normalisation area image in radar geometry
        cout = []
        cerr = []
        mli_par_pathname = str(self.r_dem_master_mli_par)
        dem_par_pathname = str(self.eqa_dem_par)
        dem_pathname = str(self.eqa_dem)
        lookup_table_pathname = str(self.dem_lt_rough)
        ls_map_pathname = str(self.dem_lsmap)
        inc_map_pathname = str(self.dem_loc_inc)
        pix_sigma0_pathname = "-"  # no output
        pix_gamma0_pathname = str(self.dem_pix_gam)
        stat = pg.pixel_area(
            mli_par_pathname,
            dem_par_pathname,
            dem_pathname,
            lookup_table_pathname,
            ls_map_pathname,
            inc_map_pathname,
            pix_sigma0_pathname,
            pix_gamma0_pathname,
            cout=cout,
            cerr=cerr,
            stdout_flag=False,
            stderr_flag=False
        )

        if stat != 0:
            msg = "failed to execute pg.pixel_area"
            _LOG.error(
                msg,
                mli_par_pathname=mli_par_pathname,
                dem_par_pathname=dem_par_pathname,
                dem_pathname=dem_pathname,
                lookup_table_pathname=lookup_table_pathname,
                ls_map_pathname=ls_map_pathname,
                inc_map_pathname=inc_map_pathname,
                pix_sigma0_pathname=pix_sigma0_pathname,
                pix_gamma0_pathname=pix_gamma0_pathname,
                stat=stat,
                gamma_error=cerr
            )
            raise Exception(msg)

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
            cout = []
            cerr = []
            dem1_par_pathname = str(self.dem_par)
            data1_pathname = str(self.ext_image)
            dem2_par_pathname = str(self.eqa_dem_par)
            data2_pathname = str(self.ext_image_flt)
            lat_ovr = 1
            lon_ovr = 1
            interp_mode = 1  # bicubic spline
            dtype = 0  # FLOAT
            bflg = "-"  # use DEM bounds specified by dem2_par_pathname
            stat = pg.map_trans(
                dem1_par_pathname,
                data1_pathname,
                dem2_par_pathname,
                data2_pathname,
                lat_ovr,
                lon_ovr,
                interp_mode,
                dtype,
                bflg,
                cout=cout,
                cerr=cerr,
                stdout_flag=False,
                stderr_flag=False
            )

            if stat != 0:
                msg = "failed to execute pg.map_trans"
                _LOG.error(
                    msg,
                    dem1_par_pathname=dem1_par_pathname,
                    data1_pathname=data1_pathname,
                    dem2_par_pathname=dem2_par_pathname,
                    data2_pathname=data2_pathname,
                    lat_ovr=lat_ovr,
                    lon_ovr=lon_ovr,
                    interp_mode=interp_mode,
                    dtype=dtype,
                    bflg=bflg,
                    stat=stat,
                    gamma_error=cerr
                )
                raise Exception(msg)

            # transform external image to radar geometry
            cout = []
            cerr = []
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
                cout=cout,
                cerr=cerr,
                stdout_flag=False,
                stderr_flag=False
            )

            if stat != 0:
                msg = "failed to execute pg.geocode"
                _LOG.error(
                    msg,
                    lookup_table_pathname=lookup_table_pathname,
                    data_in_pathname=data_in_pathname,
                    width_in=width_in,
                    data_out_pathname=data_out_pathname,
                    width_out=width_out,
                    nlines_out=nlines_out,
                    interp_mode=interp_mode,
                    dtype=dtype,
                    lr_in=lr_in,
                    lr_out=lr_out,
                    n_ovr=n_ovr,
                    rad_max=rad_max,
                    nintr=nintr,
                    stat=stat,
                    gamma_error=cerr
                )
                raise Exception(msg)

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

            command = [
                "create_diff_par",
                self.r_dem_master_mli_par.as_posix(),
                "-",
                self.dem_diff.as_posix(),
                "1",
                "<",
                return_file.as_posix()
            ]
            run_command(command, os.getcwd())

    def offset_calc(
        self, npoly: Optional[int] = 1, use_external_image: Optional[bool] = False
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

        # MCG: Urs Wegmuller recommended using pixel_area_gamma0 rather than simulated SAR image in offset calculation
        cout = []
        cerr = []
        mli_1_pathname = str(self.dem_pix_gam)
        mli_2_pathname = str(self.r_dem_master_mli)
        diff_par_pathname = str(self.dem_diff)
        rlks = 1
        azlks = 1
        rpos = self.dem_rpos
        azpos = self.dem_azpos
        offr = "-"  # initial range offset
        offaz = "-"  # initial azimuth offset
        thres = self.dem_snr
        patch = self.dem_patch_window
        cflag = 1  # copy constant range and azimuth offsets
        stat = pg.init_offsetm(
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
            cout=cout,
            cerr=cerr,
            stdout_flag=False,
            stderr_flag=False
        )

        if stat != 0:
            msg = "failed to execute pg.init_offsetm"
            _LOG.error(
                msg,
                mli_1_pathname=mli_1_pathname,
                mli_2_pathname=mli_2_pathname,
                diff_par_pathname=diff_par_pathname,
                rlks=rlks,
                azlks=azlks,
                rpos=rpos,
                offr=offr,
                offaz=offaz,
                thres=thres,
                patch=patch,
                cflag=cflag,
                stat=stat,
                gamma_error=cerr
            )
            raise Exception(msg)

        cout = []
        cerr = []
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
        stat = pg.offset_pwrm(
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
            cout=cout,
            cerr=cerr,
            stdout_flag=False,
            stderr_flag=False
        )

        if stat != 0:
            msg = "failed to execute pg.offset_pwrm"
            _LOG.error(
                msg,
                mli_1_pathname=mli_1_pathname,
                mli_2_pathname=mli_2_pathname,
                diff_par_pathname=diff_par_pathname,
                offs_pathname=offs_pathname,
                ccp_pathname=ccp_pathname,
                rwin=rwin,
                azwin=azwin,
                offsets_pathname=offsets_pathname,
                n_ovr=n_ovr,
                nr=nr,
                naz=naz,
                thres=thres,
                stat=stat,
                gamma_error=cerr
            )
            raise Exception(msg)

        pg.offset_fitm(
            self.dem_offs.as_posix(),
            self.dem_ccp.as_posix(),
            self.dem_diff.as_posix(),
            self.dem_coffs.as_posix(),
            self.dem_coffsets.as_posix(),
            "-",
            npoly,
        )

        # refinement of initial geo-coding look-up-table
        ref_flg = 1
        if use_external_image:
            ref_flg = 0

        pg.gc_map_fine(
            self.dem_lt_rough.as_posix(),
            self.dem_width,
            self.dem_diff.as_posix(),
            self.dem_lt_fine.as_posix(),
            ref_flg,
        )

        # generate refined gamma0 pixel normalization area image in radar geometry
        with tempfile.TemporaryDirectory() as temp_dir:
            pix = Path(temp_dir).joinpath("pix")
            pg.pixel_area(
                self.r_dem_master_mli_par.as_posix(),
                self.eqa_dem_par.as_posix(),
                self.eqa_dem.as_posix(),
                self.dem_lt_fine.as_posix(),
                self.dem_lsmap.as_posix(),
                self.dem_loc_inc.as_posix(),
                "-",
                pix.as_posix(),
            )

            # interpolate holes
            pg.interp_ad(
                pix.as_posix(),
                self.dem_pix_gam.as_posix(),
                self.r_dem_master_mli_width,
                "-",
                "-",
                "-",
                2,
                2,
                1,
            )

            # obtain ellipsoid-based ground range sigma0 pixel reference area
            sigma0 = Path(temp_dir).joinpath("sigma0")
            pg.radcal_MLI(
                self.r_dem_master_mli.as_posix(),
                self.r_dem_master_mli_par.as_posix(),
                "-",
                sigma0.as_posix(),
                "-",
                0,
                0,
                1,
                "-",
                "-",
                self.ellip_pix_sigma0.as_posix(),
            )

            # Generate Gamma0 backscatter image for master scene according to equation
            # in Section 10.6 of Gamma Geocoding and Image Registration Users Guide
            temp1 = Path(temp_dir).joinpath("temp1")
            pg.float_math(
                self.r_dem_master_mli.as_posix(),
                self.ellip_pix_sigma0.as_posix(),
                temp1.as_posix(),
                self.r_dem_master_mli_width,
                2,
            )
            pg.float_math(
                temp1.as_posix(),
                self.dem_pix_gam.as_posix(),
                self.dem_master_gamma0.as_posix(),
                self.r_dem_master_mli_width,
                3,
            )

            # create raster for comparison with master mli raster
            pg.raspwr(
                self.dem_master_gamma0.as_posix(),
                self.r_dem_master_mli_width,
                1,
                0,
                20,
                20,
                1.0,
                0.35,
                1,
                self.dem_master_gamma0_bmp.as_posix(),
            )

            # make sea-mask based on DEM zero values
            temp = Path(temp_dir).joinpath("temp")
            pg.replace_values(
                self.eqa_dem.as_posix(),
                0.0001,
                0,
                temp.as_posix(),
                self.dem_width,
                0,
                2,
                1,
            )

            pg.rashgt(
                temp.as_posix(),
                "-",
                self.dem_width,
                1,
                1,
                0,
                1,
                1,
                100.0,
                "-",
                "-",
                "-",
                self.seamask.as_posix(),
            )

    def geocode(self, use_external_image: Optional[bool] = False):
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
        pg.geocode(
            self.dem_lt_fine.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_width,
            self.rdc_dem.as_posix(),
            self.r_dem_master_mli_width,
            self.r_dem_master_mli_length,
            1,
            0,
            "-",
            "-",
            2,
            self.dem_rad_max,
            "-",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            rdc_dem_bmp = Path(temp_dir).joinpath("rdc_dem.bmp")
            pg.rashgt(
                self.rdc_dem.as_posix(),
                self.r_dem_master_mli.as_posix(),
                self.r_dem_master_mli_width,
                1,
                1,
                0,
                20,
                20,
                500.0,
                1.0,
                0.35,
                1,
                rdc_dem_bmp.as_posix(),
            )

            command = [
                "convert",
                rdc_dem_bmp.as_posix(),
                self.dem_outdir.joinpath(self.rdc_dem.stem)
                .with_suffix(".png")
                .as_posix(),
            ]
            run_command(command, os.getcwd())

        # Geocode simulated SAR intensity image to radar geometry
        pg.geocode(
            self.dem_lt_fine.as_posix(),
            self.dem_eqa_sim_sar.as_posix(),
            self.dem_width,
            self.dem_rdc_sim_sar.as_posix(),
            self.r_dem_master_mli_width,
            self.r_dem_master_mli_length,
            0,
            0,
            "-",
            "-",
            2,
            self.dem_rad_max,
            "-",
        )

        # Geocode local incidence angle image to radar geometry
        pg.geocode(
            self.dem_lt_fine.as_posix(),
            self.dem_loc_inc.as_posix(),
            self.dem_width,
            self.dem_rdc_inc.as_posix(),
            self.r_dem_master_mli_width,
            self.r_dem_master_mli_length,
            0,
            0,
            "-",
            "-",
            2,
            self.dem_rad_max,
            "-",
        )

        # Geocode external image to radar geometry
        if use_external_image:
            pg.geocode(
                self.dem_lt_fine.as_posix(),
                self.ext_image_flt.as_posix(),
                self.dem_width,
                self.ext_image_sar.as_posix(),
                self.r_dem_master_mli_width,
                self.r_dem_master_mli_length,
                0,
                0,
                "-",
                "-",
                2,
                self.dem_rad_max,
                "-",
            )

        # Back-geocode Gamma0 backscatter product to map geometry using B-spline interpolation on sqrt of data
        pg.geocode_back(
            self.dem_master_gamma0.as_posix(),
            self.r_dem_master_mli_width,
            self.dem_lt_fine.as_posix(),
            self.dem_master_gamma0_eqa.as_posix(),
            self.dem_width,
            "-",
            5,
            0,
            "-",
            "-",
            5,
        )

        # make quick-look png image
        pg.raspwr(
            self.dem_master_gamma0_eqa.as_posix(),
            self.dem_width,
            1,
            0,
            20,
            20,
            "-",
            "-",
            "-",
            self.dem_master_gamma0_eqa_bmp.as_posix(),
        )

        command = [
            "convert",
            self.dem_master_gamma0_eqa_bmp.as_posix(),
            "-transparent",
            "black",
            self.dem_master_gamma0_eqa_bmp.with_suffix(".png").as_posix(),
        ]
        run_command(command, os.getcwd())

        # geotiff gamma0 file
        pg.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.dem_master_gamma0_eqa.as_posix(),
            2,
            self.dem_master_gamma0_eqa_geo.as_posix(),
            0.0,
        )

        # geocode and geotif sigma0 mli
        shutil.copyfile(self.r_dem_master_mli, self.dem_master_sigma0)

        pg.geocode_back(
            self.dem_master_sigma0.as_posix(),
            self.r_dem_master_mli_width,
            self.dem_lt_fine.as_posix(),
            self.dem_master_sigma0_eqa.as_posix(),
            self.dem_width,
            "-",
            0,
            0,
            "-",
            "-",
        )

        pg.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.dem_master_sigma0_eqa.as_posix(),
            2,
            self.dem_master_sigma0_eqa_geo.as_posix(),
            0.0,
        )

        # geotiff DEM
        pg.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            2,
            self.eqa_dem_geo.as_posix(),
            0.0,
        )
        # create kml
        pg.kml_map(
            self.dem_master_gamma0_eqa_bmp.with_suffix(".png").as_posix(),
            self.eqa_dem_par.as_posix(),
            self.dem_master_gamma0_eqa_bmp.with_suffix(".kml").as_posix(),
        )

        # clean up now intermittent redundant files.
        for item in [
            self.dem_offs,
            self.dem_offsets,
            self.dem_coffs,
            self.dem_coffsets,
            self.dem_lt_rough,
            self.dem_master_gamma0_eqa_bmp,
        ]:
            # TODO uncomment remove comment in production phase.
            if item.exists():
                # os.remove(item)
                pass

    def look_vector(self):
        """Create look vector files."""

        # create angles look vector image
        pg.look_vector(
            self.r_dem_master_slc_par.as_posix(),
            "-",
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_lv_theta.as_posix(),
            self.dem_lv_phi.as_posix(),
        )

        # convert look vector files to geotiff file
        pg.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.dem_lv_theta.as_posix(),
            2,
            self.dem_lv_theta_geo.as_posix(),
            0.0,
        )

        pg.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.dem_lv_phi.as_posix(),
            2,
            self.dem_lv_phi_geo.as_posix(),
            0.0,
        )

    def main(self):
        """Main method to execute SLC-DEM coregistration task in sequence."""
        
        self.dem_outdir.mkdir(exist_ok=True)
        with working_directory(self.dem_outdir):
            self.copy_slc()
            self.over_sample()
            self.gen_dem_rdc()
            self.create_diff_par()
            self.offset_calc()
            self.geocode()
            self.look_vector()
