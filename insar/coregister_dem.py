#!/usr/bin/env python

import os
import tempfile
from collections import namedtuple
from typing import Optional, Tuple, Union, Dict
import shutil
import logging
from pathlib import Path

import py_gamma as gamma_program
from .subprocess_utils import working_directory, run_command

_LOG = logging.getLogger(__name__)


class SlcParFileParser:
    def __init__(self, par_file: Union[Path, str]) -> None:
        """
        Convenient access fields for SLC image parameter properties.

        :param par_file: 
            A full path to a SLC parameter file.
        """
        self.par_file = Path(par_file).as_posix()
        self.par_vals = gamma_program.ParFile(self.par_file)

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
        self.dem_par_params = gamma_program.ParFile(self.par_file)

    @property
    def dem_par_params(self):
        """
        Convenient DEM parameter access method need for SLC-DEM co-registration.
        """
        par_params = namedtuple("dem_par_params", ["post_lon", "width"])
        return par_params(
            self.dem_par_params.get_value("post_lon", dtype=float, index=0),
            self.dem_par_params.get_value("width", dtype=int, index=0),
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
        self.ext_image_flt = Path(ext_image_flt)
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
        if self.ext_image_flt is not None:
            os.symlink(self.ext_image_flt, attrs["ext_image_flt"])

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
            _LOG.info(f"increasing the dem window1 from {self.dem_window[0]} to {win1}")
            self.dem_window[0] = win1

        self.dem_window[1] = int(self.dem_window[1] / self.rlks)
        if self.dem_window[1] < 8:
            win2 = round(self.dem_window[1] * self.rlks) * 2
            _LOG.info(f"increasing the dem window2 from {self.dem_window[1]} to {win2}")
            self.dem_window[1] = win2

        if self.dem_patch_window / self.rlks < 128.0:
            _LOG.info(f"adjusting dem patch window from {self.dem_patch_window} to 128")
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
        gamma_program.SLC_copy(
            self.dem_master_slc.as_posix(),
            self.dem_master_slc_par.as_posix(),
            self.r_dem_master_slc.as_posix(),
            self.r_dem_master_slc_par.as_posix(),
            1,
            "-",
        )
        
        # multi-look SLC image file
        gamma_program.multi_look(
            self.r_dem_master_slc.as_posix(),
            self.r_dem_master_slc_par.as_posix(),
            self.r_dem_master_mli.as_posix(),
            self.r_dem_master_mli_par.as_posix(),
            self.rlks,
            self.alks,
            0,
        )
        
        # output raster image of multi-looked SLC image file if needed
        # TODO only useful for visual debugging phase. 
        # This is redundant in production phase (Consult InSAR team and remove)
        if raster_out:
            params = SlcParFileParser(self.r_dem_master_mli_par)
            gamma_program.raspwr(
                self.r_dem_master_mli.as_posix(),
                params.slc_par_params.range_samples,
                1,
                0,
                20,
                20,
                1.0,
                0.35,
                1,
                self.r_dem_master_mli_bmp.as_posix(),
            )

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
        gamma_program.gc_map1(
            self.r_dem_master_mli_par.as_posix(),
            "-",
            self.dem_par.as_posix(),
            self.dem.as_posix(),
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_lt_rough.as_posix(),
            self.dem_ovr,
            self.dem_ovr,
            self.dem_eqa_sim_sar.as_posix(),
            "-",
            "-",
            self.dem_loc_inc.as_posix(),
            "-",
            "-",
            self.dem_lsmap.as_posix(),
            8,
            2,
        )

        # generate initial gamma0 pixel normalisation area image in radar geometry
        gamma_program.pixel_area(
            self.r_dem_master_mli_par.as_posix(),
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_lt_rough.as_posix(),
            self.dem_lsmap.as_posix(),
            self.dem_loc_inc.as_posix(),
            "_",
            self.dem_pix_gam.as_posix(),
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
            gamma_program.map_trans(
                self.dem_par.as_posix(),
                self.ext_image.as_posix(),
                self.eqa_dem_par.as_posix(),
                self.ext_image_flt.as_posix(),
                1,
                1,
                1,
                0,
                "-",
            )

            # transform external image to radar geometry
            gamma_program.geocode(
                self.dem_lt_rought.as_posix(),
                self.ext_image_flt.as_posix(),
                self.dem_width,
                self.ext_image_init_sar.as_posix(),
                self.r_dem_master_mli_width,
                self.r_dem_master_mli_length,
                1,
                0,
                "-",
                "-",
                2,
                4,
                "-",
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

            gamma_program.create_diff_par(
                self.r_dem_master_mli_par.as_posix(),
                "-",
                self.dem_diff.as_posix(),
                1,
                cin=return_file.as_posix(),
            )

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
        gamma_program.init_offsetm(
            self.dem_pix_gam.as_posix(),
            self.r_dem_master_mli.as_posix(),
            self.dem_diff.as_posix(),
            1,
            1,
            self.dem_rpos,
            self.dem_azpos,
            "-",
            "-",
            self.dem_snr,
            self.dem_patch_window,
            1,
        )

        gamma_program.offset_pwrm(
            self.dem_pix_gam.as_posix(),
            self.r_dem_master_mli.as_posix(),
            self.dem_diff.as_posix(),
            self.dem_offs.as_posix(),
            self.dem_ccp.as_posix(),
            "-",
            "-",
            self.dem_offsets.as_posix(),
            2,
            "-",
            "-",
            "-",
        )

        gamma_program.offset_fitm(
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

        gamma_program.gc_map_fine(
            self.dem_lt_rough.as_posix(),
            self.dem_width,
            self.dem_diff.as_posix(),
            self.dem_lt_fine.as_posix(),
            ref_flg,
        )

        # generate refined gamma0 pixel normalization area image in radar geometry
        with tempfile.TemporaryDirectory() as temp_dir:
            pix = Path(temp_dir).joinpath("pix")
            gamma_program.pixel_area(
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
            gamma_program.interp_ad(
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
            gamma_program.radcal_MLI(
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
            gamma_program.float_math(
                self.r_dem_master_mli.as_posix(),
                self.ellip_pix_sigma0.as_posix(),
                temp1.as_posix(),
                self.r_dem_master_mli_width,
                2,
            )
            gamma_program.float_math(
                temp1.as_posix(),
                self.dem_pix_gam.as_posix(),
                self.dem_master_gamma0.as_posix(),
                self.r_dem_master_mli_width,
                3,
            )

            # create raster for comparison with master mli raster
            gamma_program.raspwr(
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
            gamma_program.replace_values(
                self.eqa_dem.as_posix(),
                0.0001,
                0,
                temp.as_posix(),
                self.dem_width,
                0,
                2,
                1,
            )

            gamma_program.rashgt(
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
        gamma_program.geocode(
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
            gamma_program.rashgt(
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
        gamma_program.geocode(
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
        gamma_program.geocode(
            "geocode",
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
            gamma_program.geocode(
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
        gamma_program.geocode_back(
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
        gamma_program.raspwr(
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
        gamma_program.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.dem_master_gamma0_eqa.as_posix(),
            2,
            self.dem_master_gamma0_eqa_geo.as_posix(),
            0.0,
        )

        # geocode and geotif sigma0 mli
        shutil.copyfile(self.r_dem_master_mli, self.dem_master_sigma0)

        gamma_program.geocode_back(
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

        gamma_program.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.dem_master_sigma0_eqa.as_posix(),
            2,
            self.dem_master_sigma0_eqa_geo.as_posix(),
            0.0,
        )

        # geotiff DEM
        gamma_program.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            2,
            self.eqa_dem_geo.as_posix(),
            0.0,
        )
        # create kml
        gamma_program.kml_map(
            self.dem_master_gamma0_eqa_bmp.with_suffix(".png").as_posix(),
            self.eqa_dem_par.as_posix(),
            self.dem_master_gamma0_eqa_bmp.with_suffix(".kml").as_posix(),
        )

        # clean up now redundant files
        for item in [
            self.dem_offs,
            self.dem_offsets,
            self.dem_coffs,
            self.dem_coffsets,
            self.dem_lt_rough,
            self.dem_master_gamma0_eqa_bmp,
        ]:
            if item.exists():
                # os.remove(item)
                pass

    def look_vector(self):
        """Create look vector files."""

        # create angles look vector image
        gamma_program.look_vector(
            self.r_dem_master_slc_par.as_posix(),
            "-",
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_lv_theta.as_posix(),
            self.dem_lv_phi.as_posix(),
        )

        # convert look vector files to geotiff file
        gamma_program.data2geotiff(
            self.eqa_dem_par.as_posix(),
            self.dem_lv_theta.as_posix(),
            2,
            self.dem_lv_theta_geo.as_posix(),
            0.0,
        )
        
        gamma_program.data2geotiff(
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