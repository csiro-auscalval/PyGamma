#! /usr/bin/env python

import os
import re
from collections import namedtuple
from typing import Optional, Tuple
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
        par_params = namedtuple(
            "slc_par_params",
            ["range_samples", "azimuth_lines"]
        )
        return par_params(
            int(self.par_params["range_samples"][0]),
            int(self.par_params["azimuth_lines"][0])
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
        par_params = namedtuple(
            "dem_par_params",
            ["post_lon"]
        )
        return par_params(
            int(self.par_params["post_lon"][0]),
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

        self.dem_files = self.dem_filenames()
        self.dem_masters = self.dem_master_names()
        for _key, val in {**self.dem_files, **self.dem_masters}.items():
            print(_key, val)
            setattr(self, _key, val)

    def dem_master_names(self):
        attrs = dict()
        attrs['dem_master_dir'] = self.slc.parent

        slc_prefix = f"{self.slc.stem}_{self.rlks}rlks"
        attrs['dem_master_slc'] = self.slc
        attrs['dem_master_slc_par'] = self.slc_par
        attrs['dem_master_mli'] = self.outdir.joinpath(f"{slc_prefix}.mli")
        attrs['dem_master_mli_par'] = attrs['dem_master_mli'].with_suffix(attrs['dem_master_mli'].suffix + ".par")
        attrs['dem_master_sigma0'] = self.outdir.joinpath(f"{slc_prefix}.sigma0")
        attrs['dem_master_sigma0_eqa'] = self.outdir.joinpath(f"{slc_prefix}_eqa.sigma0")
        attrs['dem_master_sigma0_eqa_geo'] = attrs['dem_master_sigma0_eqa'].with_suffix(attrs['dem_master_sigma0_eqa'].suffix + ".tif")
        attrs['dem_master_gamma0'] = self.outdir.joinpath(f"{slc_prefix}.gamma0")
        attrs['dem_master_gamma0_bmp'] = attrs['dem_master_gamma0'].joinpath(".bmp")
        attrs['dem_master_gamma0_eqa'] = self.outdir.joinpath(f"{slc_prefix}_eqa.gamma0")
        attrs['dem_master_gamma0_eqa_bmp'] = attrs['dem_master_gamma0_eqa'].with_suffix(attrs['dem_master_gamma0_eqa'].suffix + ".bmp")
        attrs['dem_master_gamma0_eqa_geo'] = attrs['dem_master_gamma0_eqa'].with_suffix(attrs['dem_master_gamma0_eqa'].suffix + ".tif")
        attrs['r_dem_master_slc'] = self.outdir.joinpath(f"r{self.slc.name}")
        attrs['r_dem_master_slc_par'] = self.outdir.joinpath(f"{self.slc_par.name}")
        attrs['r_dem_master_mli'] = self.outdir.joinpath('r{}_{}rlks.mli'.format(self.slc.stem, str(self.rlks)))
        attrs['r_dem_master_mli_par'] = attrs['r_dem_master_mli'].with_suffix(attrs['r_dem_master_mli'].suffix + ".par")
        attrs['r_dem_master_mli_bmp'] = attrs['r_dem_master_mli'].with_suffix(attrs['r_dem_master_mli'].suffix + ".bmp")
        return attrs

    def dem_filenames(self):
        attrs = dict()
        attrs['dem'] = self.dem
        attrs['dem_par'] = self.dem_par
        dem_prefix = f"{self.slc.stem}_{self.rlks}rlks"
        attrs['dem_diff'] = self.outdir.joinpath(f"diff_{dem_prefix}.par")
        attrs['rdc_dem'] = self.outdir.joinpath(f"{dem_prefix}_rdc.dem")
        attrs['eqa_dem'] = self.outdir.joinpath(f"{dem_prefix}_eqa.dem")
        attrs['eqa_dem_par'] = attrs['eqa_dem'].with_suffix(attrs['eqa_dem'].suffix + ".par")
        attrs['eqa_dem_geo'] = attrs['eqa_dem'].with_suffix(attrs['eqa_dem'].suffix + ".tif")
        attrs['dem_lt_rough'] = self.outdir.joinpath(f"{dem_prefix}_rough_eqa_to_rdc.lt")
        attrs['dem_eqa_sim_sar'] = self.outdir.joinpath(f"{dem_prefix}_eqa.sim")
        attrs['dem_loc_inc'] = self.outdir.joinpath(f"{dem_prefix}_eqa.linc")
        attrs['dem_lsmap'] = self.outdir.joinpath(f"{dem_prefix}_eqa.lsmap")
        attrs['seamask'] = self.outdir.joinpath(f"{dem_prefix}_eqa_seamask.tif")
        attrs['dem_lt_fine'] = self.outdir.joinpath(f"{dem_prefix}_eqa_to_rdc.lt")
        attrs['dem_eqa_sim_sar'] = self.outdir.joinpath(f"{dem_prefix}_eqa.sim")
        attrs['dem_rdc_sim_sar'] = self.outdir.joinpath(f"{dem_prefix}_rdc.sim")
        attrs['dem_rdc_inc'] = self.outdir.joinpath(f"{dem_prefix}_rdc.linc")
        attrs['ellip_pix_sigma0'] = self.outdir.joinpath(f"{dem_prefix}_ellip_pix_sigma0")
        attrs['dem_pix_gam'] = self.outdir.joinpath(f"{dem_prefix}_rdc_pix_gamma0")
        attrs['dem_pix_gam_bmp'] = attrs["dem_pix_gam"].with_suffix(".bmp")
        attrs['dem_off'] = self.outdir.joinpath(f"{dem_prefix}.off")
        attrs['dem_offs'] = self.outdir.joinpath(f"{dem_prefix}.offs")
        attrs['dem_ccp'] = self.outdir.joinpath(f"{dem_prefix}.ccp")
        attrs['dem_offsets'] = self.outdir.joinpath(f"{dem_prefix}.offsets")
        attrs['dem_coffs'] = self.outdir.joinpath(f"{dem_prefix}.coffs")
        attrs['dem_coffsets'] = self.outdir.joinpath(f"{dem_prefix}.coffsets")
        attrs['dem_lv_theta'] = self.outdir.joinpath(f"{dem_prefix}_eqa.lv_theta")
        attrs['dem_lv_phi'] = self.outdir.joinpath(f"{dem_prefix}_eqa.lv_phi")
        attrs['dem_lv_theta_geo'] = attrs['dem_lv_theta'].with_suffix(attrs['dem_lv_theta'].suffix + ".tif")
        attrs['dem_lv_phi_geo'] = attrs['dem_lv_phi'].with_suffix(attrs['dem_lv_phi'].suffix + ".tif")
        attrs['ext_image_flt'] = self.outdir.joinpath(f"{dem_prefix}_ext_img_sar.flt")
        attrs['ext_image_init_sar'] = self.outdir.joinpath(f"{dem_prefix}_ext_img_init.sar")
        attrs['ext_image_sar'] = self.outdir.joinpath(f"{dem_prefix}_ext_img.sar")
        attrs['dem_check_file'] = self.outdir.joinpath(f"{dem_prefix}_DEM_coreg_results")

        return attrs

    def adjust_dem_parameter(self):
        self.dem_window[0] = int(self.dem_window[0] / self.rlks)
        if self.dem_window[0] < 8:
            win1 = round(self.dem_window[0] * self.rlks) * 2
            _LOG.info(f"increasing the dem window1 from {self.dem_window[0]} to {win1}")
            self.dem_window[0] = win1
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

    def copy_slc(
        self,
        raster_out: Optional[bool] = True,
    ) -> None:
        """Copy SLC with options for data format conversion"""
        command = [
            "SLC_copy",
            self.dem_master_slc.as_posix(),
            self.dem_master_slc_par.as_posix(),
            self.r_dem_master_slc.as_posix(),
            self.r_dem_master_slc_par.as_posix(),
            "1",
            "-"
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
            "0"
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
                self.r_dem_master_mli_bmp.as_posix()
            ]
            run_command(command, os.getcwd())

    def over_sample(self):
        """Returns oversampling factor for DEM coregistration"""
        dem_par_params = DemParFileParser(self.dem_par)
        post_lon = dem_par_params.post_lon
        if post_lon <= 0.00011111:
            self.dem_ovr = 1
        elif 0.00011111 < post_lon < 0.0008333:
            self.dem_ovr = 4
        else:
            self.dem_ovr = 8

    def gen_dem_rdc(self):
        """Generate DEM coregistered to slc in rdc geometry"""
        pass

    def main(self):
        self.outdir.mkdir(exist_ok=True)
        with working_directory(self.outdir):
            self.copy_slc()
            self.over_sample()
            exit()
