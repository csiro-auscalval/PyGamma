#! /usr/bin/env python

import os
import tempfile
from collections import namedtuple
from typing import Optional, Tuple
import shutil
import logging
from pathlib import Path
from python_scripts.subprocess_utils import working_directory, run_command

_LOG = logging.getLogger(__name__)


class SlcParFileParser:
    def __init__(self, par_file: Path):
        self.par_file = par_file
        self.par_params = None
        with open(self.par_file.as_posix(), "r") as fid:
            tmp_dict = dict()
            lines = fid.readlines()
            for line in lines:
                vals = line.strip().split(":")
                try:
                    tmp_dict[vals[0]] = [v for v in vals[1].split()]
                except IndexError:
                    pass
        self.par_params = tmp_dict

    @property
    def slc_par_params(self):
        par_params = namedtuple("slc_par_params", ["range_samples", "azimuth_lines"])
        return par_params(
            int(self.par_params["range_samples"][0]),
            int(self.par_params["azimuth_lines"][0]),
        )


class DemParFileParser:
    def __init__(self, par_file: Path):
        self.par_file = par_file
        self.par_params = None
        with open(self.par_file.as_posix(), "r") as fid:
            tmp_dict = dict()
            lines = fid.readlines()
            for line in lines:
                vals = line.strip().split(":")
                try:
                    tmp_dict[vals[0]] = [v for v in vals[1].split()]
                except IndexError:
                    pass
        self.par_params = tmp_dict

    @property
    def dem_par_params(self):
        par_params = namedtuple("dem_par_params", ["post_lon", "width"])
        return par_params(
            float(self.par_params["post_lon"][0]), int(self.par_params["width"][0])
        )


class CoregisterDem:
    def __init__(
        self,
        rlks: int,
        alks: int,
        dem: Path,
        slc: Path,
        dem_par: Path,
        slc_par: Path,
        dem_patch_window: Optional[int] = 1024,
        dem_rpos: Optional[int] = None,
        dem_azpos: Optional[int] = None,
        dem_offset: Optional[Tuple[int, int]] = (0, 0),
        dem_offset_measure: Optional[Tuple[int, int]] = (32, 32),
        dem_window: Optional[Tuple[int, int]] = (256, 256),
        dem_snr: Optional[float] = 0.15,
        dem_rad_max: Optional[int] = 4,
        outdir: Optional[Path] = None,
    ) -> None:
        self.alks = alks
        self.rlks = rlks
        self.dem = dem
        self.slc = slc
        self.dem_par = dem_par
        self.slc_par = slc_par
        self.outdir = outdir
        if self.outdir is None:
            self.outdir = Path(os.getcwd())

        self.dem_patch_window = dem_patch_window
        self.dem_rpos = dem_rpos
        self.dem_azpos = dem_azpos
        self.dem_offset = list(dem_offset)
        self.dem_offset_measure = list(dem_offset_measure)
        self.dem_window = list(dem_window)
        self.dem_snr = dem_snr
        self.dem_rad_max = dem_rad_max

        if self.rlks > 1:
            self.adjust_dem_parameter()

        self.dem_ovr = None
        self.dem_width = None
        self.r_dem_master_mli_width = None
        self.r_dem_master_mli_length = None
        self.dem_files = self.dem_filenames()
        self.dem_masters = self.dem_master_names()
        for _key, val in {**self.dem_files, **self.dem_masters}.items():
            print(_key, val)
            setattr(self, _key, val)

    def dem_master_names(self):
        attrs = dict()
        attrs["dem_master_dir"] = self.slc.parent

        slc_prefix = f"{self.slc.stem}_{self.rlks}rlks"
        attrs["dem_master_slc"] = self.slc
        attrs["dem_master_slc_par"] = self.slc_par
        attrs["dem_master_mli"] = self.outdir.joinpath(f"{slc_prefix}.mli")
        attrs["dem_master_mli_par"] = attrs["dem_master_mli"].with_suffix(
            attrs["dem_master_mli"].suffix + ".par"
        )
        attrs["dem_master_sigma0"] = self.outdir.joinpath(f"{slc_prefix}.sigma0")
        attrs["dem_master_sigma0_eqa"] = self.outdir.joinpath(
            f"{slc_prefix}_eqa.sigma0"
        )
        attrs["dem_master_sigma0_eqa_geo"] = attrs["dem_master_sigma0_eqa"].with_suffix(
            attrs["dem_master_sigma0_eqa"].suffix + ".tif"
        )
        attrs["dem_master_gamma0"] = self.outdir.joinpath(f"{slc_prefix}.gamma0")
        attrs["dem_master_gamma0_bmp"] = attrs["dem_master_gamma0"].with_suffix(
            attrs["dem_master_gamma0"].suffix + ".bmp"
        )
        attrs["dem_master_gamma0_eqa"] = self.outdir.joinpath(
            f"{slc_prefix}_eqa.gamma0"
        )
        attrs["dem_master_gamma0_eqa_bmp"] = attrs["dem_master_gamma0_eqa"].with_suffix(
            attrs["dem_master_gamma0_eqa"].suffix + ".bmp"
        )
        attrs["dem_master_gamma0_eqa_geo"] = attrs["dem_master_gamma0_eqa"].with_suffix(
            attrs["dem_master_gamma0_eqa"].suffix + ".tif"
        )
        attrs["r_dem_master_slc"] = self.outdir.joinpath(f"r{self.slc.name}")
        attrs["r_dem_master_slc_par"] = self.outdir.joinpath(f"r{self.slc_par.name}")
        attrs["r_dem_master_mli"] = self.outdir.joinpath(
            "r{}_{}rlks.mli".format(self.slc.stem, str(self.rlks))
        )
        attrs["r_dem_master_mli_par"] = attrs["r_dem_master_mli"].with_suffix(
            attrs["r_dem_master_mli"].suffix + ".par"
        )
        attrs["r_dem_master_mli_bmp"] = attrs["r_dem_master_mli"].with_suffix(
            attrs["r_dem_master_mli"].suffix + ".bmp"
        )
        return attrs

    def dem_filenames(self):
        attrs = dict()
        attrs["dem"] = self.dem
        attrs["dem_par"] = self.dem_par
        dem_prefix = f"{self.slc.stem}_{self.rlks}rlks"
        attrs["dem_diff"] = self.outdir.joinpath(f"diff_{dem_prefix}.par")
        attrs["rdc_dem"] = self.outdir.joinpath(f"{dem_prefix}_rdc.dem")
        attrs["eqa_dem"] = self.outdir.joinpath(f"{dem_prefix}_eqa.dem")
        attrs["eqa_dem_par"] = attrs["eqa_dem"].with_suffix(
            attrs["eqa_dem"].suffix + ".par"
        )
        attrs["eqa_dem_geo"] = attrs["eqa_dem"].with_suffix(
            attrs["eqa_dem"].suffix + ".tif"
        )
        attrs["dem_lt_rough"] = self.outdir.joinpath(
            f"{dem_prefix}_rough_eqa_to_rdc.lt"
        )
        attrs["dem_eqa_sim_sar"] = self.outdir.joinpath(f"{dem_prefix}_eqa.sim")
        attrs["dem_loc_inc"] = self.outdir.joinpath(f"{dem_prefix}_eqa.linc")
        attrs["dem_lsmap"] = self.outdir.joinpath(f"{dem_prefix}_eqa.lsmap")
        attrs["seamask"] = self.outdir.joinpath(f"{dem_prefix}_eqa_seamask.tif")
        attrs["dem_lt_fine"] = self.outdir.joinpath(f"{dem_prefix}_eqa_to_rdc.lt")
        attrs["dem_eqa_sim_sar"] = self.outdir.joinpath(f"{dem_prefix}_eqa.sim")
        attrs["dem_rdc_sim_sar"] = self.outdir.joinpath(f"{dem_prefix}_rdc.sim")
        attrs["dem_rdc_inc"] = self.outdir.joinpath(f"{dem_prefix}_rdc.linc")
        attrs["ellip_pix_sigma0"] = self.outdir.joinpath(
            f"{dem_prefix}_ellip_pix_sigma0"
        )
        attrs["dem_pix_gam"] = self.outdir.joinpath(f"{dem_prefix}_rdc_pix_gamma0")
        attrs["dem_pix_gam_bmp"] = attrs["dem_pix_gam"].with_suffix(".bmp")
        attrs["dem_off"] = self.outdir.joinpath(f"{dem_prefix}.off")
        attrs["dem_offs"] = self.outdir.joinpath(f"{dem_prefix}.offs")
        attrs["dem_ccp"] = self.outdir.joinpath(f"{dem_prefix}.ccp")
        attrs["dem_offsets"] = self.outdir.joinpath(f"{dem_prefix}.offsets")
        attrs["dem_coffs"] = self.outdir.joinpath(f"{dem_prefix}.coffs")
        attrs["dem_coffsets"] = self.outdir.joinpath(f"{dem_prefix}.coffsets")
        attrs["dem_lv_theta"] = self.outdir.joinpath(f"{dem_prefix}_eqa.lv_theta")
        attrs["dem_lv_phi"] = self.outdir.joinpath(f"{dem_prefix}_eqa.lv_phi")
        attrs["dem_lv_theta_geo"] = attrs["dem_lv_theta"].with_suffix(
            attrs["dem_lv_theta"].suffix + ".tif"
        )
        attrs["dem_lv_phi_geo"] = attrs["dem_lv_phi"].with_suffix(
            attrs["dem_lv_phi"].suffix + ".tif"
        )
        attrs["ext_image_flt"] = self.outdir.joinpath(f"{dem_prefix}_ext_img_sar.flt")
        attrs["ext_image_init_sar"] = self.outdir.joinpath(
            f"{dem_prefix}_ext_img_init.sar"
        )
        attrs["ext_image_sar"] = self.outdir.joinpath(f"{dem_prefix}_ext_img.sar")
        attrs["dem_check_file"] = self.outdir.joinpath(
            f"{dem_prefix}_DEM_coreg_results"
        )

        return attrs

    def _set_attrs(self):
        if self.r_dem_master_mli_width is None:
            mli_par = SlcParFileParser(self.r_dem_master_mli_par)
            self.r_dem_master_mli_width = mli_par.slc_par_params.range_samples
            self.r_dem_master_mli_length = mli_par.slc_par_params.azimuth_lines

        if self.dem_width is None:
            eqa_dem_params = DemParFileParser(self.eqa_dem_par)
            self.dem_width = eqa_dem_params.dem_par_params.width

    def adjust_dem_parameter(self):
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
        """Copy SLC with options for data format conversion"""
        command = [
            "SLC_copy",
            self.dem_master_slc.as_posix(),
            self.dem_master_slc_par.as_posix(),
            self.r_dem_master_slc.as_posix(),
            self.r_dem_master_slc_par.as_posix(),
            "1",
            "-",
        ]
        run_command(command, os.getcwd())

        command = [
            "multi_look",
            self.r_dem_master_slc.as_posix(),
            self.r_dem_master_slc_par.as_posix(),
            self.r_dem_master_mli.as_posix(),
            self.r_dem_master_mli_par.as_posix(),
            str(self.rlks),
            str(self.alks),
            "0",
        ]
        run_command(command, os.getcwd())

        if raster_out:
            params = SlcParFileParser(self.r_dem_master_mli_par)
            command = [
                "raspwr",
                self.r_dem_master_mli.as_posix(),
                str(params.slc_par_params.range_samples),
                "1",
                "0",
                "20",
                "20",
                "1.0",
                "0.35",
                "1",
                self.r_dem_master_mli_bmp.as_posix(),
            ]
            run_command(command, os.getcwd())

    def over_sample(self):
        """Returns oversampling factor for DEM coregistration"""
        params = DemParFileParser(self.dem_par)
        post_lon = params.dem_par_params.post_lon
        if post_lon <= 0.00011111:
            self.dem_ovr = 1
        elif 0.00011111 < post_lon < 0.0008333:
            self.dem_ovr = 4
        else:
            self.dem_ovr = 8

    def gen_dem_rdc(self, use_external_image: Optional[bool] = False):
        """Generate DEM coregistered to slc in rdc geometry"""

        # generate initial geocoding look-up-table and simulated SAR image
        command = [
            "gc_map",
            self.r_dem_master_mli_par.as_posix(),
            "-",
            self.dem_par.as_posix(),
            self.dem.as_posix(),
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_lt_rough.as_posix(),
            str(self.dem_ovr),
            str(self.dem_ovr),
            self.dem_eqa_sim_sar.as_posix(),
            "-",
            "-",
            self.dem_loc_inc.as_posix(),
            "-",
            "-",
            self.dem_lsmap.as_posix(),
            "8",
            "2",
        ]
        run_command(command, os.getcwd())

        # generate initial gamma0 pixel normalisation area image in radar geometry
        command = [
            "pixel_area",
            self.r_dem_master_mli_par.as_posix(),
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_lt_rough.as_posix(),
            self.dem_lsmap.as_posix(),
            self.dem_loc_inc.as_posix(),
            "_",
            self.dem_pix_gam.as_posix(),
        ]
        run_command(command, os.getcwd())

        if any(item is None for item in [self.r_dem_master_mli_width,
                                         self.r_dem_master_mli_length,
                                         self.dem_width
                                         ]
               ):
            self._set_attrs()

        if use_external_image:
            # transform simulated SAR intensity image to radar geometry
            command = [
                "map_trans",
                self.dem_par.as_posix(),
                self.ext_image.as_posix(),
                self.eqa_dem_par.as_posix(),
                self.ext_image_flt.as_posix(),
                "1",
                "1",
                "1",
                "0",
                "-",
            ]
            run_command(command, os.getcwd())

            # transform external image to radar geometry
            command = [
                "geocode",
                self.dem_lt_rought.as_posix(),
                self.ext_image_flt.as_posix(),
                str(self.dem_width),
                self.ext_image_init_sar.as_posix(),
                str(self.r_dem_master_mli_width),
                str(self.r_dem_master_mli_length),
                "1",
                "0",
                "-",
                "-",
                "2",
                "4",
                "-",
            ]
            run_command(command, os.getcwd())

    def create_diff_par(self):
        """Fine coregistration of master MLI and simulated SAR image"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = "/g/data1a/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/"
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
                str(return_file),
            ]
            run_command(command, os.getcwd())

    def offset_calc(
        self, npoly: Optional[int] = 1, use_external_image: Optional[bool] = False
    ):
        """offset computation"""
        # set parameters
        if any(item is None for item in [self.r_dem_master_mli_width,
                                         self.r_dem_master_mli_length,
                                         self.dem_width
                                         ]
               ):
            self._set_attrs()

        # MCG: Urs Wegmuller recommended using pixel_area_gamma0 rather than simulated SAR image in offset calculation
        command = [
            "init_offsetm",
            self.dem_pix_gam.as_posix(),
            self.r_dem_master_mli.as_posix(),
            self.dem_diff.as_posix(),
            "1",
            "1",
            str(self.dem_rpos),
            str(self.dem_azpos),
            "-",
            "-",
            str(self.dem_snr),
            str(self.dem_patch_window),
            "1",
        ]
        run_command(command, os.getcwd())

        command = [
            "offset_pwrm",
            self.dem_pix_gam.as_posix(),
            self.r_dem_master_mli.as_posix(),
            self.dem_diff.as_posix(),
            self.dem_offs.as_posix(),
            self.dem_ccp.as_posix(),
            "-",
            "-",
            self.dem_offsets.as_posix(),
            "2",
            "-",
            "-",
            "-",
        ]
        run_command(command, os.getcwd())

        command = [
            "offset_fitm",
            self.dem_offs.as_posix(),
            self.dem_ccp.as_posix(),
            self.dem_diff.as_posix(),
            self.dem_coffs.as_posix(),
            self.dem_coffsets.as_posix(),
            "-",
            str(npoly),
        ]
        run_command(command, os.getcwd())

        # refinement of initial geocoding look-up-table
        ref_flg = 1
        if use_external_image:
            ref_flg = 0

        command = [
            "gc_map_fine",
            self.dem_lt_rough.as_posix(),
            str(self.dem_width),
            self.dem_diff.as_posix(),
            self.dem_lt_fine.as_posix(),
            str(ref_flg),
        ]
        run_command(command, os.getcwd())

        # generate refined gamma0 pixel normalization area image in radar geometry
        with tempfile.TemporaryDirectory() as temp_dir:
            pix = Path(temp_dir).joinpath("pix")
            command = [
                "pixel_area",
                self.r_dem_master_mli_par.as_posix(),
                self.eqa_dem_par.as_posix(),
                self.eqa_dem.as_posix(),
                self.dem_lt_fine.as_posix(),
                self.dem_lsmap.as_posix(),
                self.dem_loc_inc.as_posix(),
                "-",
                pix.as_posix(),
            ]
            run_command(command, os.getcwd())

            # interpolate holes
            command = [
                "interp_ad",
                pix.as_posix(),
                self.dem_pix_gam.as_posix(),
                str(self.r_dem_master_mli_width),
                "-",
                "-",
                "-",
                "2",
                "2",
                "1",
            ]
            run_command(command, os.getcwd())

            # obtain ellipsoid-based ground range sigma0 pixel reference area
            sigma0 = Path(temp_dir).joinpath("sigma0")
            command = [
                "radcal_MLI",
                self.r_dem_master_mli.as_posix(),
                self.r_dem_master_mli_par.as_posix(),
                "-",
                sigma0.as_posix(),
                "-",
                "0",
                "0",
                "1",
                "-",
                "-",
                self.ellip_pix_sigma0.as_posix(),
            ]
            run_command(command, os.getcwd())

            # Generate Gamma0 backscatter image for master scene according to equation
            # in Section 10.6 of Gamma Geocoding and Image Registration Users Guide
            temp1 = Path(temp_dir).joinpath("temp1")
            command = [
                "float_math",
                self.r_dem_master_mli.as_posix(),
                self.ellip_pix_sigma0.as_posix(),
                temp1.as_posix(),
                str(self.r_dem_master_mli_width),
                "2",
            ]
            run_command(command, os.getcwd())
            command = [
                "float_math",
                temp1.as_posix(),
                self.dem_pix_gam.as_posix(),
                self.dem_master_gamma0.as_posix(),
                str(self.r_dem_master_mli_width),
                "3",
            ]
            run_command(command, os.getcwd())

            # create raster for comparison with master mli raster
            command = [
                "raspwr",
                self.dem_master_gamma0.as_posix(),
                str(self.r_dem_master_mli_width),
                "1",
                "0",
                "20",
                "20",
                "1.",
                ".35",
                "1",
                self.dem_master_gamma0_bmp.as_posix(),
            ]
            run_command(command, os.getcwd())

            # make sea-mask based on DEM zero values
            temp = Path(temp_dir).joinpath("temp")
            command = [
                "replace_values",
                self.eqa_dem.as_posix(),
                "0.0001",
                "0",
                temp.as_posix(),
                str(self.dem_width),
                "0",
                "2",
                "1",
            ]
            run_command(command, os.getcwd())
            command = [
                "rashgt",
                temp.as_posix(),
                "-",
                str(self.dem_width),
                "1",
                "1",
                "0",
                "1",
                "1",
                "100.",
                "-",
                "-",
                "-",
                self.seamask.as_posix(),
            ]
            run_command(command, os.getcwd())

    def geocode(self, use_external_image: Optional[bool] = False):
        """geocode tasks"""

        # set parameters
        if any(item is None for item in [self.r_dem_master_mli_width,
                                         self.r_dem_master_mli_length,
                                         self.dem_width
                                         ]
               ):
            self._set_attrs()

        # geocode map geometry DEM to radar geometry
        command = [
            "geocode",
            self.dem_lt_fine.as_posix(),
            self.eqa_dem.as_posix(),
            str(self.dem_width),
            self.rdc_dem.as_posix(),
            str(self.r_dem_master_mli_width),
            str(self.r_dem_master_mli_length),
            "1",
            "0",
            "-",
            "-",
            "2",
            str(self.dem_rad_max),
            "-",
        ]
        run_command(command, os.getcwd())
        with tempfile.TemporaryDirectory() as temp_dir:
            rdc_dem_bmp = Path(temp_dir).joinpath("rdc_dem.bmp")
            command = [
                "rashgt",
                self.rdc_dem.as_posix(),
                self.r_dem_master_mli.as_posix(),
                str(self.r_dem_master_mli_width),
                "1",
                "1",
                "0",
                "20",
                "20",
                "500.",
                "1.",
                ".35",
                "1",
                rdc_dem_bmp.as_posix(),
            ]
            run_command(command, os.getcwd())
            command = [
                "convert",
                rdc_dem_bmp.as_posix(),
                self.outdir.joinpath(self.rdc_dem.stem).with_suffix(".png").as_posix(),
            ]
            run_command(command, os.getcwd())

        # Geocode simulated SAR intensity image to radar geometry
        command = [
            "geocode",
            self.dem_lt_fine.as_posix(),
            self.dem_eqa_sim_sar.as_posix(),
            str(self.dem_width),
            self.dem_rdc_sim_sar.as_posix(),
            str(self.r_dem_master_mli_width),
            str(self.r_dem_master_mli_length),
            "0",
            "0",
            "-",
            "-",
            "2",
            str(self.dem_rad_max),
            "-",
        ]
        run_command(command, os.getcwd())

        # Geocode local incidence angle image to radar geometry
        command = [
            "geocode",
            self.dem_lt_fine.as_posix(),
            self.dem_loc_inc.as_posix(),
            str(self.dem_width),
            self.dem_rdc_inc.as_posix(),
            str(self.r_dem_master_mli_width),
            str(self.r_dem_master_mli_length),
            "0",
            "0",
            "-",
            "-",
            "2",
            str(self.dem_rad_max),
            "-",
        ]
        run_command(command, os.getcwd())

        # Geocode external image to radar geometry
        if use_external_image:
            command = [
                "geocode",
                self.dem_lt_fine.as_posix(),
                self.ext_image_flt.as_posix(),
                str(self.dem_width),
                self.ext_image_sar.as_posix(),
                str(self.r_dem_master_mli_width),
                str(self.r_dem_master_mli_length),
                "0",
                "0",
                "-",
                "-",
                "2",
                str(self.dem_rad_max),
                "-",
            ]
            run_command(command, os.getcwd())

        # Back-geocode Gamma0 backscatter product to map geometry using B-spline interpolation on sqrt of data
        command = [
            "geocode_back",
            self.dem_master_gamma0.as_posix(),
            str(self.r_dem_master_mli_width),
            self.dem_lt_fine.as_posix(),
            self.dem_master_gamma0_eqa.as_posix(),
            str(self.dem_width),
            "-",
            "5",
            "0",
            "-",
            "-",
            "5",
        ]
        run_command(command, os.getcwd())

        # make quick-look png image
        command = [
            "raspwr",
            self.dem_master_gamma0_eqa.as_posix(),
            str(self.dem_width),
            "1",
            "0",
            "20",
            "20",
            "-",
            "-",
            "-",
            self.dem_master_gamma0_eqa_bmp.as_posix()
        ]
        run_command(command, os.getcwd())

        command = [
            "convert",
            self.dem_master_gamma0_eqa_bmp.as_posix(),
            "-transparent",
            "black",
            self.dem_master_gamma0_eqa_bmp.with_suffix(".png").as_posix()
        ]
        run_command(command, os.getcwd())

        # geotiff gamma0 file
        command = [
            "data2geotiff",
            self.eqa_dem_par.as_posix(),
            self.dem_master_gamma0_eqa.as_posix(),
            "2",
            self.dem_master_gamma0_eqa_geo.as_posix(),
            "0.0"
        ]
        run_command(command, os.getcwd())

        # geocode and geotif sigma0 mli
        shutil.copyfile(self.r_dem_master_mli, self.dem_master_sigma0)

        command = [
            "geocode_back",
            self.dem_master_sigma0.as_posix(),
            str(self.r_dem_master_mli_width),
            self.dem_lt_fine.as_posix(),
            self.dem_master_sigma0_eqa.as_posix(),
            str(self.dem_width),
            "-",
            "0",
            "0",
            "-",
            "-"
        ]
        run_command(command, os.getcwd())

        command = [
            "data2geotiff",
            self.eqa_dem_par.as_posix(),
            self.dem_master_sigma0_eqa.as_posix(),
            "2",
            self.dem_master_sigma0_eqa_geo.as_posix(),
            "0.0"
        ]
        run_command(command, os.getcwd())

        # geotiff DEM
        command = [
            "data2geotiff",
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            "2",
            self.eqa_dem_geo.as_posix(),
            "0.0"
        ]
        run_command(command, os.getcwd())

        # create kml
        command = [
            "kml_map",
            self.dem_master_gamma0_eqa_bmp.with_suffix(".png").as_posix(),
            self.eqa_dem_par.as_posix(),
            self.dem_master_gamma0_eqa_bmp.with_suffix(".kml").as_posix()
        ]
        run_command(command, os.getcwd())

        # clean up now redundant files
        for item in [
            self.dem_offs,
            self.dem_offsets,
            self.dem_coffs,
            self.dem_coffsets,
            self.dem_lt_rough,
            self.dem_master_gamma0_eqa_bmp
        ]:
            if item.exists():
                # os.remove(item)
                pass

    def look_vector(self):
        """create look vector files"""
        command = [
            "look_vector",
            self.r_dem_master_slc_par.as_posix(),
            "-",
            self.eqa_dem_par.as_posix(),
            self.eqa_dem.as_posix(),
            self.dem_lv_theta.as_posix(),
            self.dem_lv_phi.as_posix()
        ]
        run_command(command, os.getcwd())

        # geocode look vectors
        command = [
            "data2geotiff",
            self.eqa_dem_par.as_posix(),
            self.dem_lv_theta.as_posix(),
            "2",
            self.dem_lv_theta_geo.as_posix(),
            "0.0"
        ]
        run_command(command, os.getcwd())

        command = [
            "data2geotiff",
            self.eqa_dem_par.as_posix(),
            self.dem_lv_phi.as_posix(),
            "2",
            self.dem_lv_phi_geo.as_posix(),
            "0.0"
        ]
        run_command(command, os.getcwd())

    def main(self):
        self.outdir.mkdir(exist_ok=True)
        with working_directory(self.outdir):
            self.copy_slc()
            self.over_sample()
            self.gen_dem_rdc()
            self.create_diff_par()
            self.offset_calc()
            self.geocode()
            self.look_vector()
