#!/usr/bin/env python

"""
For all py_gamma calls, attempts have been made to best match the Gamma
parameter names and the variable names defined in this module.
"""

import os
from typing import Optional, Union, Dict, List
import tempfile
from collections import namedtuple
from pathlib import Path
import re
import shutil
import structlog

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.subprocess_utils import working_directory, run_command

_LOG = structlog.get_logger("insar")


class CoregisterSlcException(Exception):
    pass


pg = GammaInterface(
    subprocess_func=auto_logging_decorator(
        subprocess_wrapper, CoregisterSlcException, _LOG
    )
)


class SlcParFileParser:
    def __init__(self, par_file: Union[Path, str],) -> None:
        """
        Convenient access fields for SLC image parameter properties

        :param par_file:
            A full path to a SLC image parameter file
        """
        self.par_file = Path(par_file).as_posix()
        self.par_vals = pg.ParFile(self.par_file)

    @property
    def slc_par_params(self):
        """
        Convenient SLC parameter access method needed for SLC-SLC co-registration.
        """
        par_params = namedtuple("slc_par_params", ["range_samples", "azimuth_lines"])
        return par_params(
            self.par_vals.get_value("range_samples", dtype=int, index=0),
            self.par_vals.get_value("azimuth_lines", dtype=int, index=0),
        )


class DemParFileParser:
    def __init__(self, par_file: Union[Path, str],) -> None:
        """
        Convenient access fields for DEM image parameter properties.

        :param par_file:
            A full path to a DEM parameter file.
        """
        self.par_file = Path(par_file).as_posix()
        self.dem_par_vals = pg.ParFile(self.par_file)

    @property
    def dem_par_params(self):
        """
        Convenient DEM parameter access method needed for SLC-SLC co-registration.
        """
        par_params = namedtuple("dem_par_params", ["post_lon", "width"])
        return par_params(
            self.dem_par_vals.get_value("post_lon", dtype=float, index=0),
            self.dem_par_vals.get_value("width", dtype=int, index=0),
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
        Co-registers Sentinel-1 IW SLC to a chosen master SLC geometry.

        :param slc_master:
            A full path to a master (reference) SLC image file.
        :param slc_slave:
            A full Path to a slave SLC image file.
        :param slave_mli:
            A full path to a slave image multi-looked image file.
        :param range_looks:
            A range look value.
        :param azimuth_looks:
            An azimuth look value.
        :param ellip_pix_sigma0:
            A full path to a sigma0 product generated during master-dem co-registration.
        :param dem_pix_gamma0:
            A full path to a gamma0 product generated during master-dem co-registration.
        :param r_dem_master_mli:
            A full path to a reference multi-looked image parameter file.
        :param rdc_dem:
            A full path to a dem (height map) in RDC of master SLC.
        :param eqa_dem_par:
            A full path to a eqa dem par generated during master-dem co-registration.
        :param dem_lt_fine:
            A full path to a eqa_to_rdc look-up table generated during master-dem co-registration.
        :param outdir:
            A full path to a output directory.
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
                "DEM Master MLI par file not found",
                pathname=str(self.r_dem_master_mli_par),
            )

        self.r_dem_master_slc_par = self.slc_master.with_suffix(".slc.par")
        if not self.r_dem_master_slc_par.exists():
            _LOG.error(
                "DEM Master SLC par file not found",
                pathname=str(self.r_dem_master_slc_par),
            )

        self.slc_slave_par = self.slc_slave.with_suffix(".slc.par")
        if not self.slc_slave_par.exists():
            _LOG.error("SLC Slave par file not found", pathname=str(self.slc_slave_par))

        self.slave_mli_par = self.slave_mli.with_suffix(".mli.par")
        if not self.slave_mli_par.exists():
            _LOG.error("Slave MLI par file not found", pathname=str(self.slave_mli_par))

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
    def swath_tab_names(swath: int, prefix: str,) -> namedtuple:
        """
        Returns namedtuple swath-slc names.

        :param swath:
            An IW swath number.
        :param prefix:
            A prefix of full SLC name.

        :returns:
            A namedtuple containing the names of slc, par and tops_par.
        """

        swath_par = f"{prefix}_iw{swath}.slc.par"
        swath_tops_par = f"{prefix}_iw{swath}.slc.TOPS_par"
        swath_slc = f"{prefix}_iw{swath}.slc"

        # TODO: refactor to define in module scope
        swath_tab = namedtuple("swath_tab", ["slc", "par", "tops_par"])
        return swath_tab(swath_slc, swath_par, swath_tops_par)

    def set_tab_files(
        self, out_dir: Optional[Union[Path, str]] = None,
    ):
        """Writes tab files used in slave co-registration."""

        if out_dir is None:
            out_dir = self.out_dir

        # write a slave slc tab file
        self.slave_slc_tab = out_dir.joinpath(f"{self.slc_slave.stem}_tab")
        self._write_tabs(self.slave_slc_tab, self.slc_slave.stem, self.slc_slave.parent)

        # write a re-sampled slave slc tab file
        self.r_slave_slc_tab = out_dir.joinpath(f"r_{self.slc_slave.stem}_tab")
        self._write_tabs(
            self.r_slave_slc_tab, f"r{self.slc_slave.stem}", self.slc_slave.parent
        )

        # write master slc tab file
        self.master_slc_tab = out_dir.joinpath(f"{self.slc_master.stem}_tab")
        self._write_tabs(
            self.master_slc_tab, self.slc_master.stem, self.slc_master.parent
        )

        self.r_slave_slc = out_dir.joinpath(f"r{self.slc_slave.name}")
        self.r_slave_slc_par = out_dir.joinpath(f"r{self.slc_slave.name}.par")

    def get_lookup(self, outfile: Optional[Path] = None,) -> None:
        """Determine lookup table based on orbit data and DEM."""

        self.slave_lt = outfile
        if outfile is None:
            self.slave_lt = self.out_dir.joinpath(f"{self.master_slave_prefix}.lt")

        mli1_par_pathname = str(self.r_dem_master_mli_par)
        dem_rdc_pathname = str(self.rdc_dem)
        mli2_par_pathname = str(self.slave_mli_par)
        lookup_table_pathname = str(self.slave_lt)

        pg.rdc_trans(
            mli1_par_pathname, dem_rdc_pathname, mli2_par_pathname, lookup_table_pathname,
        )

    def master_sample_size(self):
        """Returns the start and end rows and cols."""
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
        """Reduce offset estimation to max offset values."""
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
        """Writes a tab file input as required by GAMMA."""
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
    def _grep_stdout(std_output: list, match_start_string: str,) -> str:
        """
        A helper method to return matched string from std_out.

        :param std_output:
            A list containing the std output collected by py_gamma.
        :param match_start_string:
            A case sensitive string to be scanned in stdout.

        :returns:
            A full string line of the matched string.
        """
        for line in std_output:
            print(line)
            if line.startswith(match_start_string):
                return line

    @staticmethod
    def _grep_offset_parameter(
        offset_file: Union[Path, str], match_start_string: Optional[str] = None,
    ) -> Union[Dict, List]:
        """
        Method to read an offset parameter file.

        :param offset_file:
            A full path to a offset parameter file.
        :param match_start_string:
            An Optional case sensitive string to be search in a dictionary keys.

        :returns:
            A full key, values generated from the offset files or a  value
            that matched the Optional match_start_string key.
        """
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
        Performs a coarse co-registration.

        Iterative improvement of refinement offsets between master SLC and resampled slave RSLC
        using intensity matching (offset_pwr_tracking).
        """

        _LOG.info("Iterative improvement of refinement offset using matching")
        # create slave offset
        if self.slave_off is None:
            self.slave_off = self.out_dir.joinpath(f"{self.master_slave_prefix}.off")

        slc1_par_pathname = str(self.r_dem_master_slc_par)
        slc2_par_pathname = str(self.slc_slave_par)
        off_par_pathname = str(self.slave_off)
        algorithm = 1  # intensity cross-correlation
        rlks = self.rlks
        azlks = self.alks
        iflg = 0  # non-interactive mode

        pg.create_offset(
            slc1_par_pathname,
            slc2_par_pathname,
            off_par_pathname,
            algorithm,
            rlks,
            azlks,
            iflg,
        )

        # TODO: cleanup to constants.py?
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
                    slc2_tab_pathname = str(self.slave_slc_tab)
                    slc2_par_pathname = str(self.slc_slave_par)
                    slc1_tab_pathname = str(self.master_slc_tab)
                    slc1_par_pathname = str(self.r_dem_master_slc_par)
                    lookup_table_pathname = str(self.slave_lt)
                    mli1_par_pathname = str(self.r_dem_master_mli_par)
                    mli2_par_pathname = str(self.slave_mli_par)
                    off_par_pathname = str(slave_off_start)
                    slc2r_tab_pathname = str(self.r_slave_slc_tab)
                    slc_2r_pathname = str(self.r_slave_slc)
                    slc2r_par_pathname = str(self.r_slave_slc_par)

                    pg.SLC_interp_lt_ScanSAR(
                        slc2_tab_pathname,
                        slc2_par_pathname,
                        slc1_tab_pathname,
                        slc1_par_pathname,
                        lookup_table_pathname,
                        mli1_par_pathname,
                        mli2_par_pathname,
                        off_par_pathname,
                        slc2r_tab_pathname,
                        slc_2r_pathname,
                        slc2r_par_pathname,
                    )

                    if slave_doff.exists():
                        os.remove(slave_doff)

                    # create and update ISP offset parameter file
                    slc1_par_pathname = str(self.r_dem_master_slc_par)
                    slc2_par_pathname = str(self.slc_slave_par)
                    off_par_pathname = str(slave_doff)
                    algorithm = 1  # intensity cross-correlation
                    rlks = self.rlks
                    azlks = self.alks
                    iflg = 0  # non-interactive mode

                    pg.create_offset(
                        slc1_par_pathname,
                        slc2_par_pathname,
                        off_par_pathname,
                        algorithm,
                        rlks,
                        azlks,
                        iflg,
                    )

                    # offset tracking between SLC images using intensity cross-correlation
                    slc1_pathname = str(self.slc_master)
                    slc2_pathname = str(self.r_slave_slc)
                    slc1_par_pathname = str(self.r_dem_master_slc_par)
                    slc2_par_pathname = str(self.r_slave_slc_par)
                    off_par_pathname = str(slave_doff)
                    offs_pathname = str(slave_offs)
                    ccp_pathname = str(slave_snr)
                    rwin = 128
                    azwin = 64
                    offsets = "-"
                    n_ovr = 1
                    thres = 0.2
                    rstep = self.range_step
                    azstep = self.azimuth_step
                    rstart = self.master_sample.slc_width_start
                    rstop = self.master_sample.slc_width_end
                    azstart = self.master_sample.slc_lines_start
                    azstop = self.master_sample.slc_lines_end

                    pg.offset_pwr_tracking(
                        slc1_pathname,
                        slc2_pathname,
                        slc1_par_pathname,
                        slc2_par_pathname,
                        off_par_pathname,
                        offs_pathname,
                        ccp_pathname,
                        rwin,
                        azwin,
                        offsets,
                        n_ovr,
                        thres,
                        rstep,
                        azstep,
                        rstart,
                        rstop,
                        azstart,
                        azstop,
                    )

                    # range and azimuth offset polynomial estimation
                    offs_pathname = str(slave_offs)
                    ccp_pathname = str(slave_snr)
                    off_par = str(slave_doff)
                    coffs = "-"
                    coffsets = "-"
                    thres = 0.2
                    npoly = 1
                    interact_mode = 0  # off

                    _, cout, _ = pg.offset_fit(
                        offs_pathname,
                        ccp_pathname,
                        off_par,
                        coffs,
                        coffsets,
                        thres,
                        npoly,
                        interact_mode,
                    )

                    range_stdev, azimuth_stdev = re.findall(
                        "[-+]?[0-9]*\.?[0-9]+",
                        self._grep_stdout(
                            cout, "final model fit std. dev. (samples) range:"
                        ),
                    )

                    # look-up table refinement
                    # determine range and azimuth corrections for look-up table (in mli pixels)
                    doff_vals = pg.ParFile(slave_doff.as_posix())
                    d_azimuth = doff_vals.get_value(
                        "azimuth_offset_polynomial", dtype=float, index=0
                    )
                    d_range = doff_vals.get_value(
                        "range_offset_polynomial", dtype=float, index=0
                    )
                    d_azimuth_mli = d_azimuth / self.alks
                    d_range_mli = d_range / self.rlks

                    _LOG.info(
                        "matching iteration",
                        iteration=iteration + 1,
                        daz=d_azimuth,
                        dr=d_range,
                        daz_mli=d_azimuth_mli,
                        dr_mli=d_range_mli,
                        max_azimuth_threshold=max_azimuth_threshold,
                        max_iterations=max_iteration,
                    )
                    _LOG.info(
                        "matching iteration and standard deviation",
                        iteration=iteration + 1,
                        azimuth_stdev=azimuth_stdev,
                        range_stdev=range_stdev,
                        max_azimuth_threshold=max_azimuth_threshold,
                        max_iterations=max_iteration,
                    )

                    if slave_diff_par.exists():
                        os.remove(slave_diff_par)

                    # create template diff parameter file for geocoding
                    par1_pathname = str(self.r_dem_master_mli_par)
                    par2_pathname = str(self.r_dem_master_mli_par)
                    diff_par_pathname = str(slave_diff_par)
                    par_type = 1  # SLC/MLI_par ISP SLC/MLI parameters
                    iflg = 0  # non-interactive mode

                    pg.create_diff_par(
                        par1_pathname, par2_pathname, diff_par_pathname, par_type, iflg,
                    )

                    # update range_offset_polynomial in diff param file
                    par_in_pathname = str(slave_diff_par)
                    par_out_pathname = str(slave_diff_par)
                    search_keyword = "range_offset_polynomial"
                    new_value = f"{d_range_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"

                    pg.set_value(
                        par_in_pathname, par_out_pathname, search_keyword, new_value,
                    )

                    # update azimuth_offset_polynomial in diff param file
                    par_in_pathname = str(slave_diff_par)
                    par_out_pathname = str(slave_diff_par)
                    search_keyword = "azimuth_offset_polynomial"
                    new_value = f"{d_azimuth_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"

                    pg.set_value(
                        par_in_pathname, par_out_pathname, search_keyword, new_value,
                    )

                    # update look-up table
                    _slave_lt = temp_dir.joinpath(f"{self.slave_lt.name}.{iteration}")
                    shutil.copy(self.slave_lt, _slave_lt)

                    # geocoding look-up table refinement using diff par offset polynomial
                    gc_in = str(_slave_lt)
                    width = self.master_sample.mli_width_end
                    diff_par = str(slave_diff_par)
                    gc_out = str(self.slave_lt)
                    ref_flg = 1

                    pg.gc_map_fine(
                        gc_in, width, diff_par, gc_out, ref_flg,
                    )
                    # TODO: do we raise and kill the program or iterate here on exception?

                    iteration += 1

            # TODO this needs to be removed once fine co-registration step is implemented
            shutil.copy(slave_doff, self.slave_off)

    def resample_full(self):
        """Resample full data set"""

        # re-sample ScanSAR burst mode SLC using a look-up-table and SLC offset polynomials
        slc2_tab = str(self.slave_slc_tab)
        slc2_par = str(self.slc_slave_par)
        slc1_tab = str(self.master_slc_tab)
        slc1_par = str(self.r_dem_master_slc_par)
        lookup_table_pathname = str(self.slave_lt)
        mli1_par = str(self.r_dem_master_mli_par)
        mli2_par = str(self.slave_mli_par)
        off_par = str(self.slave_off)
        slc2r_tab = str(self.r_slave_slc_tab)
        slc_2r = str(self.r_slave_slc)
        slc2r_par = str(self.r_slave_slc_par)

        pg.SLC_interp_lt_ScanSAR(
            slc2_tab,
            slc2_par,
            slc1_tab,
            slc1_par,
            lookup_table_pathname,
            mli1_par,
            mli2_par,
            off_par,
            slc2r_tab,
            slc_2r,
            slc2r_par,
        )

    def multi_look(self):
        """Multi-look co-registered slaves."""
        self.r_slave_mli = self.out_dir.joinpath(f"r{self.slave_mli.name}")
        self.r_slave_mli_par = self.r_slave_mli.with_suffix(".mli.par")

        slc_pathname = str(self.r_slave_slc)
        slc_par_pathname = str(self.r_slave_slc_par)
        mli_pathname = str(self.r_slave_mli)
        mli_par_pathname = str(self.r_slave_mli_par)
        rlks = self.rlks
        alks = self.alks

        pg.multi_look(
            slc_pathname, slc_par_pathname, mli_pathname, mli_par_pathname, rlks, alks,
        )

    def generate_normalised_backscatter(self):
        """
        Normalised radar backscatter.

        Generate Gamma0 backscatter image for slave scene according to equation in
        Section 10.6 of Gamma Geocoding and Image Registration Users Guide.
        """
        slave_gamma0 = self.out_dir.joinpath(f"{self.slave_mli.stem}.gamma0")
        slave_gamma0_eqa = self.out_dir.joinpath(f"{self.slave_mli.stem}_eqa.gamma0")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)
            temp_output = temp_dir.joinpath("temp_output")
            with working_directory(temp_dir):
                d1_pathname = str(self.r_slave_mli)
                d2_pathname = str(self.ellip_pix_sigma0)
                d_out_pathname = str(temp_output)
                width = self.master_sample.mli_width_end
                mode = 2  # multiplication

                pg.float_math(
                    d1_pathname, d2_pathname, d_out_pathname, width, mode,
                )

            d1_pathname = str(temp_output)
            d2_pathname = str(self.dem_pix_gamma0)
            d_out_pathname = str(slave_gamma0)
            width = self.master_sample.mli_width_end
            mode = 3  # division

            pg.float_math(
                d1_pathname, d2_pathname, d_out_pathname, width, mode,
            )

            # back geocode gamma0 backscatter product to map geometry using B-spline interpolation on sqrt data
            eqa_dem_par_vals = DemParFileParser(self.eqa_dem_par)
            dem_width = eqa_dem_par_vals.dem_par_params.width

            data_in_pathname = str(slave_gamma0)
            width_in = self.master_sample.mli_width_end
            lookup_table_pathname = str(self.dem_lt_fine)
            data_out_pathname = str(slave_gamma0_eqa)
            width_out = dem_width
            nlines_out = "-"
            interp_mode = 5  # B-spline interpolation
            dtype = 0  # float
            lr_in = "-"
            lr_out = "-"
            order = 5  # B-spline degree

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
            temp_bmp = temp_dir.joinpath(f"{slave_gamma0_eqa.name}.bmp")
            slave_png = self.out_dir.joinpath(temp_bmp.with_suffix(".png").name)

            with working_directory(temp_dir):
                pwr_pathname = str(slave_gamma0_eqa)
                width = dem_width
                start = 1
                nlines = 0
                pixavr = 20
                pixavaz = 20
                scale = "-"
                exp = "-"
                lr = "-"
                rasf_pathname = str(temp_bmp)

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

                # image magick conversion routine
                command = [
                    "convert",
                    temp_bmp.as_posix(),
                    "-transparent",
                    "black",
                    slave_png.as_posix(),
                ]
                run_command(command, os.getcwd())

                # convert gamma0 Gamma file to GeoTIFF
                dem_par_pathname = str(self.eqa_dem_par)
                data_pathname = str(slave_gamma0_eqa)
                dtype = 2  # float
                geotiff_pathname = str(slave_gamma0_eqa.with_suffix(".gamma0.tif"))
                nodata = 0.0

                pg.data2geotiff(
                    dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
                )

                # create KML map of PNG file
                image_pathname = str(slave_png)
                dem_par_pathname = str(self.eqa_dem_par)
                kml_pathname = str(slave_png.with_suffix(".kml"))

                pg.kml_map(
                    image_pathname, dem_par_pathname, kml_pathname,
                )

                # geocode sigma0 mli
                slave_sigma0_eqa = slave_gamma0_eqa.with_suffix(".sigma0")

                data_in_pathname = str(self.r_slave_mli)
                width_in = self.master_sample.mli_width_end
                lookup_table_pathname = str(self.dem_lt_fine)
                data_out_pathname = str(slave_sigma0_eqa)
                width_out = dem_width
                nlines_out = "-"
                interp_mode = 0  # nearest-neighbor
                dtype = 0  # float
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

                # convert sigma0 Gamma file to GeoTIFF
                dem_par_pathname = str(self.eqa_dem_par)
                data_pathname = str(slave_sigma0_eqa)
                dtype = 2  # float
                geotiff_pathname = str(slave_sigma0_eqa.with_suffix(".sigma0.tif"))
                nodata = 0.0

                pg.data2geotiff(
                    dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
                )

    def main(self):
        """Main method to execute methods sequence of methods need for master-slave coregistration."""
        with working_directory(self.out_dir):
            self.set_tab_files()
            self.get_lookup()
            self.reduce_offset()
            self.coarse_registration()
            self.resample_full()
            self.multi_look()
            self.generate_normalised_backscatter()
