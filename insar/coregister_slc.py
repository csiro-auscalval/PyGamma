#! /usr/bin/env python

import os
from typing import Optional, Union
import tempfile
from collections import namedtuple
from pathlib import Path
import re
import logging
import shutil

import py_gamma as gamma_program

from .subprocess_utils import working_directory, run_command

_LOG = logging.getLogger(__name__)


class SlcParFileParser:
    def __init__(self, par_file: Path):
        self.par_file = par_file
        self.par_vals = gamma_program.ParFile(self.par_file)

    @property
    def slc_par_params(self):
        par_params = namedtuple("slc_par_params", ["range_samples", "azimuth_lines"])
        return par_params(
            self.par_vals.get_value("range_samples", dtype=int, index=0),
            self.par_vals.get_value("azimuth_lines", dtype=int, index=0),
        )


class DemParFileParser:
    def __init__(self, par_file: Path):
        self.par_file = par_file
        self.dem_par_params = gamma_program.ParFile(self.par_file)

    @property
    def dem_par_params(self):
        par_params = namedtuple("dem_par_params", ["post_lon", "width"])
        return par_params(
            self.dem_par_params.get_value("post_lon", dtype=float, index=0),
            self.dem_par_params.get_value("width", dtype=int, index=0),
        )


class CoregisterSlc:
    def __init__(
        self,
        slc_master: Union[str, Path],
        slc_slave: Union[str, Path],
        slave_mli: Union[str, Path],
        range_looks: int,
        azimuth_looks: int,
        ellip_pix_sigma0: Union[str, Path],
        dem_pix_gamma0: Union[str, Path],
        r_dem_master_mli: Union[str, Path],
        rdc_dem: Union[str, Path],
        eqa_dem_par: Union[str, Path],
        dem_lt_fine: Union[str, Path],
        outdir: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Co-registers Sentinel-1 IWS SLC to chosen master SLC geometry.

        :param slc_master: Full path to a master (reference) SLC
        :param slc_slave: Full Path to a slave SLC
        :param slave_mli: Full path to a slave image multi-looked file
        :param range_looks: range look value
        :param azimuth_looks: azimuth look value
        :param ellip_pix_sigma0: sigma0 product generated during master-dem co-registration
        :param dem_pix_gamma0: gamma0 product generated during master-dem co-registration
        :param r_dem_master_mli: Full path to a reference multi-looked parameter file
        :param rdc_dem: Full path to a dem (height map) in RDC of master SLC
        :param eqa_dem_par: Full path to a eqa dem par generated during master-dem co-registration
        :param dem_lt_fine: Full path to a eqa_to_rdc look-up table generated during master-dem co-registration
        :param outdir: Full path to a output directory
        """
        self.slc_master = slc_master
        self.slc_slave = slc_slave
        self.rdc_dem = rdc_dem
        self.slave_mli = slave_mli
        self.alks = azimuth_looks
        self.rlks = range_looks
        self.r_dem_master_mli = r_dem_master_mli
        self.ellip_pix_sigma0 = ellip_pix_sigma0
        self.dem_pix_gamma0 = dem_pix_gamma0
        self.eqa_dem_par = eqa_dem_par
        self.dem_lt_fine = dem_lt_fine
        self.out_dir = outdir
        if self.out_dir is None:
            self.out_dir = Path(self.slc_slave).parent
        self.slave_lt = None

        self.r_dem_master_mli_par = self.r_dem_master_mli.with_suffix(".mli.par")
        if not self.r_dem_master_mli_par.exists():
            _LOG.error(
                FileNotFoundError(
                    f"{self.r_dem_master_mli_par.as_posix()} does not exists"
                )
            )

        self.r_dem_master_slc_par = self.slc_master.with_suffix(".slc.par")
        if not self.r_dem_master_slc_par.exists():
            _LOG.error(
                FileNotFoundError(
                    f"{self.r_dem_master_slc_par.as_posix()} does not exists"
                )
            )

        self.slc_slave_par = self.slc_slave.with_suffix(".slc.par")
        if not self.slc_slave_par.exists():
            _LOG.error(
                FileNotFoundError(f"{self.slc_slave_par.as_posix()} does not exists")
            )

        self.slave_mli_par = self.slave_mli.with_suffix(".mli.par")
        if not self.slave_mli_par.exists():
            _LOG.error(
                FileNotFoundError(f"{self.slave_mli_par.as_posix()} does not exist")
            )

        self.master_sample = self.master_sample_size()

        self.range_step = None
        self.azimuth_step = None
        self.slave_off = None
        self.r_slave_slc = None
        self.r_slave_slc_par = None
        self.r_slave_slc_tab = None
        self.master_slc_tab = None
        self.slave_slc_tab = None
        self.r_slave_slc = None
        self.r_slave_slc_par = None
        self.r_slave_mli = None
        self.r_slave_mli_par = None
        self.master_slave_prefix = f"{self.slc_master.stem}-{self.slc_slave.stem}"

    @staticmethod
    def swath_tab_names(swath: int, prefix: str) -> namedtuple:
        """Returns namedtuple swath-slc names"""
        swath_par = f"{prefix}_iw{swath}.slc.par"
        swath_tops_par = f"{prefix}_iw{swath}.slc.TOPS_par"
        swath_slc = f"{prefix}_iw{swath}.slc"
        swath_tab = namedtuple("swath_tab", ["slc", "par", "tops_par"])
        return swath_tab(swath_slc, swath_par, swath_tops_par)

    def set_tab_files(self, out_dir: Optional[Union[Path, str]] = None):
        """Writes tab files used in slave co-registration"""
        if out_dir is None:
            out_dir = self.out_dir

        # write a slave slc tab file
        self.slave_slc_tab = out_dir.joinpath("slave_slc_tab")
        self._write_tabs(self.slave_slc_tab, self.slc_slave.stem, self.slc_slave.parent)

        # write a re-sampled slave slc tab file
        self.r_slave_slc_tab = out_dir.joinpath("r_slave_slc_tab")
        self._write_tabs(
            self.r_slave_slc_tab, f"r{self.slc_slave.stem}", self.slc_slave.parent
        )

        # write master slc tab file
        self.master_slc_tab = out_dir.joinpath("master_slc_tab")
        self._write_tabs(
            self.master_slc_tab, self.slc_master.stem, self.slc_master.parent
        )

        self.r_slave_slc = out_dir.joinpath(f"r{self.slc_slave.name}")
        self.r_slave_slc_par = out_dir.joinpath(f"{self.slc_slave.name}.par")

    def get_lookup(self, outfile: Optional[Path] = None) -> None:
        """Determine lookup table based on orbit data and DEM"""
        self.slave_lt = outfile
        if outfile is None:
            self.slave_lt = self.out_dir.joinpath(f"{self.master_slave_prefix}.lt")

        gamma_program.rdc_trans(
            self.r_dem_master_mli_par.as_posix(),
            self.rdc_dem.as_posix(),
            self.slave_mli_par.as_posix(),
            self.slave_lt.as_posix(),
        )

    def master_sample_size(self):
        """Returns the start and end rows and cols"""
        _par_slc = SlcParFileParser(self.r_dem_master_slc_par)
        _par_mli = SlcParFileParser(self.r_dem_master_mli_par)
        sample_size = namedtuple(
            "master",
            [
                "slc_width_start",
                "slc_width_end",
                "slc_lines_start",
                "slc_lines_end",
                "mli_width_start",
                "mli_width_end",
            ],
        )
        return sample_size(
            0,
            _par_slc.slc_par_params.range_samples,
            0,
            _par_slc.slc_par_params.azimuth_lines,
            0,
            _par_mli.slc_par_params.range_samples,
        )

    def reduce_offset(
        self,
        range_offset_max: Optional[int] = 64,
        azimuth_offset_max: Optional[int] = 32,
    ):
        """Reduce offset estimation to max offset values"""
        self.range_step = int(
            (self.master_sample.slc_width_end - self.master_sample.slc_width_start) / 64
        )
        if range_offset_max > self.range_step:
            self.range_step = range_offset_max
        self.azimuth_step = int(
            (self.master_sample.slc_lines_end - self.master_sample.slc_lines_start) / 64
        )
        if azimuth_offset_max > self.azimuth_step:
            self.azimuth_step = azimuth_offset_max

    def _write_tabs(
        self,
        tab_file: Union[Path, str],
        _id: str,
        data_dir: Optional[Union[Path, str]] = None,
    ):
        """writes a tab file input as required by GAMMA."""
        with open(tab_file, "w") as fid:
            for swath in [1, 2, 3]:
                tab_names = self.swath_tab_names(swath, _id)
                _slc = tab_names.slc
                _par = tab_names.par
                _tops_par = tab_names.tops_par

                if data_dir is not None:
                    _slc = data_dir.joinpath(_slc).as_posix()
                    _par = data_dir.joinpath(_par).as_posix()
                    _tops_par = data_dir.joinpath(_tops_par).as_posix()
                fid.write(_slc + " " + _par + " " + _tops_par + "\n")

    @staticmethod
    def _grep_stdout(std_output: str, match_start_string: str):
        lines = std_output.split("\n")
        for line in lines:
            if line.startswith(match_start_string):
                return line

    @staticmethod
    def _grep_offset_parameter(
        offset_file: Union[Path, str], match_start_string: Optional[str] = None
    ):
        with open(offset_file, "r") as fid:
            tmp_dict = dict()
            lines = fid.readlines()
            for line in lines:
                vals = line.strip().split(":")
                try:
                    tmp_dict[vals[0]] = [v for v in vals[1].split()]
                except IndexError:
                    pass
            if match_start_string is not None:
                return tmp_dict[match_start_string]
            return tmp_dict

    def coarse_registration(
        self,
        max_iteration: Optional[int] = 5,
        max_azimuth_threshold: Optional[float] = 0.01,
    ):
        """
        Performs a coarse co-registration

        Iterative improvement of refinement offsets between master SLC and resampled slave RSLC
        using intensity matching (offset_pwr_tracking).
        """

        _LOG.info("Iterative improvement of refinement offset using matching")
        # create slave offset
        if self.slave_off is None:
            self.slave_off = self.out_dir.joinpath(f"{self.master_slave_prefix}.off")
        gamma_program.create_offset(
            self.r_dem_master_slc_par.as_posix(),
            self.slc_slave_par.as_posix(),
            self.slave_off.as_posix(),
            1,
            self.rlks,
            self.alks,
            0,
        )

        d_azimuth = 1.0
        iteration = 0
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            slave_doff = temp_dir.joinpath(f"{self.master_slave_prefix}.doff")
            slave_offs = temp_dir.joinpath(f"{self.master_slave_prefix}.offs")
            slave_snr = temp_dir.joinpath(f"{self.master_slave_prefix}.snr")
            slave_diff_par = temp_dir.joinpath(f"{self.master_slave_prefix}.diff_par")

            while abs(d_azimuth) > max_azimuth_threshold and iteration < max_iteration:
                slave_off_start = temp_dir.joinpath(f"{self.slave_off.name}.start")
                shutil.copy(self.slave_off, slave_off_start)

                # re-sample ScanSAR burst mode SLC using a look-up-table and SLC offset polynomials for refinement
                with working_directory(temp_dir):
                    gamma_program.SLC_interp_lt_ScanSAR(
                        self.slave_slc_tab.as_posix(),
                        self.slc_slave_par.as_posix(),
                        self.master_slc_tab.as_posix(),
                        self.r_dem_master_slc_par.as_posix(),
                        self.slave_lt.as_posix(),
                        self.r_dem_master_mli_par.as_posix(),
                        self.slave_mli_par.as_posix(),
                        slave_off_start.as_posix(),
                        self.r_slave_slc_tab.as_posix(),
                        self.r_slave_slc.as_posix(),
                        self.r_slave_slc_par.as_posix(),
                    )

                    if slave_doff.exists():
                        os.remove(slave_doff)

                    # create and update ISP offset parameter file
                    gamma_program.create_offset(
                        self.r_dem_master_slc_par.as_posix(),
                        self.slc_slave_par.as_posix(),
                        slave_doff.as_posix(),
                        1,
                        self.rlks,
                        self.alks,
                        0,
                    )

                    # offset tracking between SLC images using intensity cross-correlation
                    gamma_program.offset_pwr_tracking(
                        self.slc_master.as_posix(),
                        self.r_slave_slc.as_posix(),
                        self.r_dem_master_slc_par.as_posix(),
                        self.r_slave_slc_par.as_posix(),
                        slave_doff.as_posix(),
                        slave_offs.as_posix(),
                        slave_snr.as_posix(),
                        128,
                        64,
                        "-",
                        1,
                        0.2,
                        self.range_step,
                        self.azimuth_step,
                        self.master_sample.slc_width_start,
                        self.master_sample.slc_width_end,
                        self.master_sample.slc_lines_start,
                        self.master_sample.slc_lines_end,
                    )

                    # range and azimuth offset polynomial estimation
                    _std_output = temp_dir.joinpath("offset_fit.log")
                    gamma_program.offset_fit(
                        slave_offs.as_posix(),
                        slave_snr.as_posix(),
                        slave_doff.as_posix(),
                        "-",
                        "-",
                        0.2,
                        1,
                        0,
                        logf=_std_output.as_posix(),
                    )

                    range_stdev, azimuth_stdev = re.findall(
                        "[-+]?[0-9]*\.?[0-9]+",
                        self._grep_stdout(
                            _std_output, "final model fit std. dev. (samples) range:"
                        ),
                    )

                    # look-up table refinement
                    # determine range and azimuth corrections for look-up table (in mli pixels)
                    doff_vals = gamma_program.ParFile(slave_doff.as_posix())
                    d_azimuth = doff_vals.get_value(
                        "azimuth_offset_polynomial", dtype=float, index=0
                    )
                    d_range = doff_vals.get_value(
                        "range_offset_polynomial", dtype=float, index=0
                    )
                    d_azimuth_mli = d_azimuth / self.alks
                    d_range_mli = d_range / self.rlks

                    _LOG.info(
                        f"matching iteration {iteration + 1}\n"
                        f"daz:\t{d_azimuth:0.6f}\n "
                        f"dr:\t{d_range:0.6f}\n "
                        f"daz_mli:\t{d_azimuth_mli:0.6f}\n "
                        f"dr_mli:\t{d_range_mli:0.6f}"
                    )
                    _LOG.info(
                        f"matching iteration {iteration + 1} standard deviation\n"
                        f"azimuth stdev:\t {float(azimuth_stdev):0.6f}\n"
                        f"range stdev:\t {float(range_stdev):0.6f}"
                    )

                    if slave_diff_par.exists():
                        os.remove(slave_diff_par)

                    # create diff parameter file for geocoding
                    gamma_program.create_diff_par(
                        self.r_dem_master_mli_par.as_posix(),
                        self.r_dem_master_mli_par.as_posix(),
                        slave_diff_par.as_posix(),
                        1,
                        0,
                    )

                    # update range_offset_polynomial in diff param file
                    gamma_program.set_value(
                        slave_diff_par.as_posix(),
                        slave_diff_par.as_posix(),
                        "range_offset_polynomial",
                        f"{d_range_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00",
                    )

                    # update azimuth_offset_polynomial in diff param file
                    gamma_program.set_value(
                        slave_diff_par.as_posix(),
                        slave_diff_par.as_posix(),
                        "azimuth_offset_polynomial",
                        f"{d_azimuth_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00",
                    )

                    # update look-up table
                    _slave_lt = temp_dir.joinpath(f"{self.slave_lt.name}.{iteration}")
                    shutil.copy(self.slave_lt, _slave_lt)

                    # geocoding look-up table refinement using diff par offset polynomial
                    gamma_program.gc_map_fine(
                        _slave_lt.as_posix(),
                        self.master_sample.mli_width_end,
                        slave_diff_par.as_posix(),
                        self.slave_lt.as_posix(),
                        1,
                    )
                    iteration += 1

            # TODO this needs to be removed once fine co-registration step is implemented
            shutil.copy(slave_doff, self.slave_off)

    def resample_full(self):
        """Resample full data set"""

        # re-sample ScanSAR burst mode SLC using a look-up-table and SLC offset polynomials
        gamma_program.SLC_interp_lt_ScanSAR(
            self.slave_slc_tab.as_posix(),
            self.slc_slave_par.as_posix(),
            self.master_slc_tab.as_posix(),
            self.r_dem_master_slc_par.as_posix(),
            self.slave_lt.as_posix(),
            self.r_dem_master_mli_par.as_posix(),
            self.slave_mli_par.as_posix(),
            self.slave_off.as_posix(),
            self.r_slave_slc_tab.as_posix(),
            self.r_slave_slc.as_posix(),
            self.r_slave_slc_par.as_posix(),
        )

    def multi_look(self):
        """Multi-look co-registered slaves"""
        self.r_slave_mli = self.out_dir.joinpath(f"r{self.slave_mli.name}")
        self.r_slave_mli_par = self.r_slave_mli.with_suffix(".mli.par")
        gamma_program.multi_look(
            self.r_slave_slc.as_posix(),
            self.r_slave_slc_par.as_posix(),
            self.r_slave_mli.as_posix(),
            self.r_slave_mli_par.as_posix(),
            self.rlks,
            self.alks,
        )

    def generate_normalised_backscatter(self):
        """
        Generate Gamma0 backscatter image for slave scene according to equation in
        Section 10.6 of Gamma Geocoding and Image Registration Users Guide
        """
        slave_gamma0 = self.out_dir.joinpath(f"{self.slave_mli.stem}.gamma0")
        slave_gamma0_eqa = self.out_dir.joinpath(f"{self.slave_mli.stem}_eqa.gamma0")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            temp_output = temp_dir.joinpath("temp_output")
            with working_directory(temp_dir):
                gamma_program.float_math(
                    self.r_slave_mli.as_posix(),
                    self.ellip_pix_sigma0.as_posix(),
                    temp_output.as_posix(),
                    self.master_sample.mli_width_end,
                    2,
                )

            gamma_program.float_math(
                temp_output.as_posix(),
                self.dem_pix_gamma0.as_posix(),
                slave_gamma0.as_posix(),
                self.master_sample.mli_width_end,
                3,
            )

            # back geocode gamma0 backscatter product to map geometry using B-spline interpolation on sqrt data
            eqa_dem_par_vals = DemParFileParser(self.eqa_dem_par)
            dem_width = eqa_dem_par_vals.dem_par_params.width
            gamma_program.geocode_back(
                slave_gamma0.as_posix(),
                self.master_sample.mli_width_end,
                self.dem_lt_fine.as_posix(),
                slave_gamma0_eqa.as_posix(),
                dem_width,
                "-",
                5,
                0,
                "-",
                "-",
                5,
            )

            # make quick-look png image
            temp_bmp = temp_dir.joinpath(f"{slave_gamma0_eqa.name}.bmp")
            slave_png = self.out_dir.joinpath(temp_bmp.with_suffix(".png").name)

            with working_directory(temp_dir):
                gamma_program.raspwr(
                    slave_gamma0_eqa.as_posix(),
                    dem_width,
                    1,
                    0,
                    20,
                    20,
                    "-",
                    "-",
                    "-",
                    temp_bmp.as_posix(),
                )

                command = [
                    "convert",
                    temp_bmp.as_posix(),
                    "-transparent",
                    "black",
                    slave_png.as_posix(),
                ]
                run_command(command, os.getcwd())

                gamma_program.data2geotiff(
                    self.eqa_dem_par.as_posix(),
                    slave_gamma0_eqa.as_posix(),
                    2,
                    slave_gamma0_eqa.with_suffix(".gamma0.tif").as_posix(),
                    0.0,
                )

                gamma_program.kml_map(
                    slave_png.as_posix(),
                    self.eqa_dem_par.as_posix(),
                    slave_png.with_suffix(".kml").as_posix(),
                )

                # geocode sigma0 mli
                slave_sigma0_eqa = slave_gamma0_eqa.with_suffix(".sigma0")
                gamma_program.geocode_back(
                    self.r_slave_mli.as_posix(),
                    self.master_sample.mli_width_end,
                    self.dem_lt_fine.as_posix(),
                    slave_sigma0_eqa.as_posix(),
                    dem_width,
                    "-",
                    0,
                    0,
                    "-",
                    "-",
                )
                gamma_program.data2geotiff(
                    self.eqa_dem_par.as_posix(),
                    slave_gamma0_eqa.as_posix(),
                    2,
                    slave_sigma0_eqa.with_suffix(".sigma0.tif").as_posix(),
                    0.0,
                )

    def main(self):
        """main method to execute methods needed to product master-slave coregistration"""
        with working_directory(self.out_dir):
            self.set_tab_files()
            self.get_lookup()
            self.reduce_offset()
            self.coarse_registration()
            self.resample_full()
            self.multi_look()
            self.generate_normalised_backscatter()
