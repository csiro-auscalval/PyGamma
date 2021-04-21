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
from PIL import Image
import numpy as np
import math

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.subprocess_utils import working_directory, run_command
from insar.project import ProcConfig
import insar.constant as const

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


# TBD: In the future we might want this to go into some sort of common utils module if we need it elsewhere too
def _unlink(path):
    '''A hacky unlink/delete file function for Python <3.8 which lacks a missing_ok parameter in Path.unlink'''
    path = Path(path)

    if path.exists():
        path.unlink()


class CoregisterSlc:
    def __init__(
        self,
        proc: ProcConfig,
        list_idx: Union[str, int],
        slc_master: Union[str, Path],
        slc_slave: Union[str, Path],
        slave_mli: Union[str, Path],
        range_looks: int,
        azimuth_looks: int,
        ellip_pix_sigma0: Union[str, Path],
        dem_pix_gamma0: Union[str, Path],
        r_dem_master_mli: Union[str, Path],
        rdc_dem: Union[str, Path],
        geo_dem_par: Union[str, Path],
        dem_lt_fine: Union[str, Path],
        outdir: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Co-registers Sentinel-1 IW SLC to a chosen master SLC geometry.

        :param proc:
            The gamma proc configuration file for the coregistration processing.
        :param list_idx:
            The list file index the slave originated from (eg: 1 for slaves1.list),
            or '-' if not applicable (eg: master coregistration).
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
        :param geo_dem_par:
            A full path to a geo dem par generated during master-dem co-registration.
        :param dem_lt_fine:
            A full path to a geo_to_rdc look-up table generated during master-dem co-registration.
        :param outdir:
            A full path to a output directory.
        """
        self.proc = proc
        self.list_idx = list_idx
        self.slc_master = slc_master
        self.slc_slave = slc_slave
        self.rdc_dem = rdc_dem
        self.slave_mli = slave_mli
        self.alks = azimuth_looks
        self.rlks = range_looks
        self.r_dem_master_mli = r_dem_master_mli
        self.ellip_pix_sigma0 = ellip_pix_sigma0
        self.dem_pix_gamma0 = dem_pix_gamma0
        self.geo_dem_par = geo_dem_par
        self.dem_lt_fine = dem_lt_fine
        self.out_dir = outdir
        if self.out_dir is None:
            self.out_dir = Path(self.slc_slave).parent
        self.slave_lt = None
        self.accuracy_warning = self.out_dir / "ACCURACY_WARNING"

        self.slave_date, self.slave_polar = self.slc_slave.stem.split('_')
        self.master_date, self.master_polar = self.slc_master.stem.split('_')

        self.log = _LOG.bind(
            task="SLC coregistration",
            slave_date=self.slave_date,
            slc_slave=self.slc_slave,
            master_date=self.master_date,
            slc_master=self.slc_master,
            list_idx=self.list_idx
        )

        self.r_dem_master_mli_par = self.r_dem_master_mli.with_suffix(".mli.par")
        if not self.r_dem_master_mli_par.exists():
            self.log.error(
                "DEM Master MLI par file not found",
                pathname=str(self.r_dem_master_mli_par),
            )

        # Note: the slc_master dir is the correct directory / this matches the bash
        self.r_dem_master_slc_par = self.slc_master.with_suffix(".slc.par")
        self.r_dem_master_slc_par = self.r_dem_master_slc_par.parent / ("r" + self.r_dem_master_slc_par.name)
        if not self.r_dem_master_slc_par.exists():
            self.log.error(
                "DEM Master SLC par file not found",
                pathname=str(self.r_dem_master_slc_par),
            )

        self.slc_slave_par = self.slc_slave.with_suffix(".slc.par")
        if not self.slc_slave_par.exists():
            self.log.error("SLC Slave par file not found", pathname=str(self.slc_slave_par))

        self.slave_mli_par = self.slave_mli.with_suffix(".mli.par")
        if not self.slave_mli_par.exists():
            self.log.error("Slave MLI par file not found", pathname=str(self.slave_mli_par))

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

        master_slave_prefix = f"{self.master_date}-{self.slave_date}"
        self.r_master_slave_name = f"{master_slave_prefix}_{self.slave_polar}_{self.rlks}rlks"

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

        swath_par = f"{prefix}_IW{swath}.slc.par"
        swath_tops_par = f"{prefix}_IW{swath}.slc.TOPS_par"
        swath_slc = f"{prefix}_IW{swath}.slc"

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
        self.r_slave_slc_tab = out_dir.joinpath(f"r{self.slc_slave.stem}_tab")
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
            self.slave_lt = self.out_dir.joinpath(f"{self.r_master_slave_name}.lt")

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

        self.log.info("Beginning coarse coregistration")

        # create slave offset
        if self.slave_off is None:
            self.slave_off = self.out_dir.joinpath(f"{self.r_master_slave_name}.off")

        pg.create_offset(
            str(self.r_dem_master_slc_par),
            str(self.slc_slave_par),
            str(self.slave_off),
            1,          # intensity cross-correlation
            self.rlks,
            self.alks,
            0,          # non-interactive mode
        )

        # TODO: cleanup to constants.py?
        d_azimuth = 1.0
        iteration = 0
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir = Path(temp_dir)

            slave_doff = self.out_dir / f"{self.r_master_slave_name}.doff"
            slave_offs = temp_dir.joinpath(f"{self.r_master_slave_name}.offs")
            slave_snr = temp_dir.joinpath(f"{self.r_master_slave_name}.snr")
            slave_diff_par = temp_dir.joinpath(f"{self.r_master_slave_name}.diff_par")

            while abs(d_azimuth) > max_azimuth_threshold and iteration < max_iteration:
                slave_off_start = temp_dir.joinpath(f"{self.slave_off.name}.start")
                shutil.copy(self.slave_off, slave_off_start)

                # re-sample ScanSAR burst mode SLC using a look-up-table and SLC offset polynomials for refinement
                with working_directory(temp_dir):
                    pg.SLC_interp_lt_ScanSAR(
                        str(self.slave_slc_tab),
                        str(self.slc_slave_par),
                        str(self.master_slc_tab),
                        str(self.r_dem_master_slc_par),
                        str(self.slave_lt),
                        str(self.r_dem_master_mli_par),
                        str(self.slave_mli_par),
                        str(slave_off_start),
                        str(self.r_slave_slc_tab),
                        str(self.r_slave_slc),
                        str(self.r_slave_slc_par),
                    )

                    if slave_doff.exists():
                        os.remove(slave_doff)

                    # create and update ISP offset parameter file
                    pg.create_offset(
                        str(self.r_dem_master_slc_par),
                        str(self.slc_slave_par),
                        str(slave_doff),
                        1,          # intensity cross-correlation
                        self.rlks,
                        self.alks,
                        0,          # non-interactive mode
                    )

                    # offset tracking between SLC images using intensity cross-correlation
                    pg.offset_pwr_tracking(
                        str(self.slc_master),
                        str(self.r_slave_slc),
                        str(self.r_dem_master_slc_par),
                        str(self.r_slave_slc_par),
                        str(slave_doff),
                        str(slave_offs),
                        str(slave_snr),
                        128,                 # rwin
                        64,                  # azwin
                        const.NOT_PROVIDED,  # offsets
                        1,                   # n_ovr
                        0.2,                 # thres
                        self.range_step,
                        self.azimuth_step,
                        self.master_sample.slc_width_start,
                        self.master_sample.slc_width_end,
                        self.master_sample.slc_lines_start,
                        self.master_sample.slc_lines_end,
                    )

                    # range and azimuth offset polynomial estimation
                    _, cout, _ = pg.offset_fit(
                        str(slave_offs),
                        str(slave_snr),
                        str(slave_doff),
                        const.NOT_PROVIDED,  # coffs
                        const.NOT_PROVIDED,  # coffsets
                        0.2,                 # thresh
                        1,                   # npolynomial
                        0,                   # non-interactive
                    )

                    range_stdev, azimuth_stdev = re.findall(
                        r"[-+]?[0-9]*\.?[0-9]+",
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

                    self.log.info(
                        "matching iteration",
                        slave_offs=slave_offs,
                        iteration=iteration + 1,
                        daz=d_azimuth,
                        dr=d_range,
                        azimuth_stdev=azimuth_stdev,
                        range_stdev=range_stdev,
                        daz_mli=d_azimuth_mli,
                        dr_mli=d_range_mli,
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
                    pg.gc_map_fine(
                        str(_slave_lt),
                        self.master_sample.mli_width_end,
                        str(slave_diff_par),
                        str(self.slave_lt),
                        1,  # ref_flg
                    )

                    iteration += 1

    def _read_line(
        self,
        filepath: Union[str, Path],
        line: int
    ):
        """Reads a specific line from a text file"""
        with open(filepath, 'r') as file:
            return file.read().splitlines()[line]

    def _get_matching_lineno(
        self,
        filepath: Union[str, Path],
        value: str
    ):
        """Get the (first) line number of a matching string in a file"""

        with open(filepath, 'r') as file:
            for lineno, line in enumerate(file.read().splitlines()):
                if line == value:
                    return lineno

        return -1

    def READ_TAB(
        self,
        tab_file: Union[str, Path]
    ):
        """
        Read a tab file, returning the (slc, par, TOPS_par) for each
        available sub-swath in the tab file.
        """

        tab_record = namedtuple("tab_record", ["slc", "par", "TOPS_par"])

        with open(tab_file, 'r') as file:
            lines = file.read().splitlines()

            # Remove empty lines
            lines = [line for line in lines if len(line.strip()) > 0]

            # determine number of rows and columns of tab file
            nrows = len(lines)
            ncols = len(lines[0].split())

            # first line
            IW1_result = tab_record(*lines[0].split())

            # second line
            IW2_result = None
            if nrows > 1:
                IW2_result = tab_record(*lines[1].split())

            # third line
            IW3_result = None
            if nrows > 2:
                IW3_result = tab_record(*lines[2].split())

            return (IW1_result, IW2_result, IW3_result)


    def get_tertiary_coreg_scene(
        self,
        slave = None,
        list_idx = None
    ):
        if slave is None:
            slave = self.slave_date

        if list_idx is None:
            list_idx = self.list_idx

        # slc_slave is something like:
        # /g/data/dz56/insar_initial_processing/T147D_F28S_S1A/SLC/20180220/20180220_VV.slc.par
        list_dir = Path(self.slc_slave).parent.parent.parent / self.proc.list_dir

        coreg_slave = None

        # coregister to nearest slave if list_idx is given
        if list_idx == const.NOT_PROVIDED:  # coregister to master
            coreg_slave = None

        elif list_idx == "0":  # coregister to adjacent slave
            # get slave position in slaves.list
            # slave_pos=`grep -n $slave $slave_list | cut -f1 -d:`
            slave_pos = self._get_matching_lineno(self.proc.slave_list, slave)

            if int(slave) < int(self.proc.ref_master_scene):
                coreg_pos = slave_pos + 1

            elif int(slave) > int(self.proc.ref_master_scene):
                coreg_pos = slave_pos - 1

            # coreg_slave=`head -n $coreg_pos $slave_list | tail -1`
            coreg_slave = self._read_line(self.proc.slave_list, coreg_pos)

        elif int(list_idx) > 20140000:  # coregister to particular slave
            coreg_slave = list_idx

        else:  # coregister to slave image with short temporal baseline
            # take the first/last slave of the previous list for coregistration
            prev_list_idx = int(list_idx) - 1

            if int(slave) < int(self.proc.ref_master_scene):
                # coreg_slave=`head $list_dir/slaves$prev_list_idx.list -n1`
                coreg_slave = self._read_line(list_dir / f'slaves{prev_list_idx}.list', 0)

            elif int(slave) > int(self.proc.ref_master_scene):
                # coreg_slave=`tail $list_dir/slaves$prev_list_idx.list -n1`
                coreg_slave = self._read_line(list_dir / f'slaves{prev_list_idx}.list', -1)

        return coreg_slave


    def fine_coregistration(
        self,
        slave: Union[str, int],
        list_idx: Union[str, int],
        max_iteration: Optional[int] = 5,
        max_azimuth_threshold: Optional[float] = 0.01,
        azimuth_px_offset_target: Optional[float] = 0.0001,
    ):
        """Performs a fine co-registration"""

        self.coarse_registration(max_iteration, max_azimuth_threshold)
        daz = None

        self.log.info("Beginning fine coregistration")

        # slc_slave is something like:
        # /g/data/dz56/insar_initial_processing/T147D_F28S_S1A/SLC/20180220/20180220_VV.slc.par
        slc_dir = Path(self.slc_slave).parent.parent.parent / self.proc.slc_dir

        with tempfile.TemporaryDirectory() as temp_dir, open(Path(temp_dir) / f"{self.r_master_slave_name}.ovr_results", 'w') as slave_ovr_res:
            temp_dir = Path(temp_dir)

            # initialize the output text file
            slave_ovr_res.writelines('\n'.join([
                "    Burst Overlap Results",
                f"        thresholds applied: cc_thresh: {self.proc.coreg_s1_cc_thresh},  ph_fraction_thresh: {self.proc.coreg_s1_frac_thresh}, ph_stdev_thresh (rad): {self.proc.coreg_s1_stdev_thresh}",
                "",
                "        IW  overlap  ph_mean ph_stdev ph_fraction   (cc_mean cc_stdev cc_fraction)    weight",
                "",
            ]))

            for iteration in range(1, max_iteration+1):
                # cp -rf $slave_off $slave_off_start
                slave_off_start = temp_dir.joinpath(f"{self.slave_off.name}.start")
                shutil.copy(self.slave_off, slave_off_start)

                # GM SLC_interp_lt_S1_TOPS $slave_slc_tab $slave_slc_par $master_slc_tab $r_dem_master_slc_par $slave_lt $r_dem_master_mli_par $slave_mli_par $slave_off_start $r_slave_slc_tab $r_slave_slc $r_slave_slc_par
                pg.SLC_interp_lt_ScanSAR(
                    str(self.slave_slc_tab),
                    str(self.slc_slave_par),
                    str(self.master_slc_tab),
                    str(self.r_dem_master_slc_par),
                    str(self.slave_lt),
                    str(self.r_dem_master_mli_par),
                    str(self.slave_mli_par),
                    str(slave_off_start),
                    str(self.r_slave_slc_tab),
                    str(self.r_slave_slc),
                    str(self.r_slave_slc_par),
                )

                # Query tertiary coreg scene (based on list_idx)
                coreg_slave = self.get_tertiary_coreg_scene()
                r_coreg_slave_tab = None

                if coreg_slave:
                    r_coreg_slave_tab = f'{slc_dir}/{coreg_slave}/r{coreg_slave}_{self.proc.polarisation}_tab'

                iter_log = self.log.bind(
                    iteration=iteration,
                    max_iteration=max_iteration,
                    master_slc_tab=self.master_slc_tab,
                    r_slave_slc_tab=self.r_slave_slc_tab,
                    r_slave2_slc_tab=r_coreg_slave_tab
                )

                try:
                    # S1_COREG_OVERLAP $master_slc_tab $r_slave_slc_tab $slave_off_start $slave_off $self.proc.coreg_s1_cc_thresh $self.proc.coreg_s1_frac_thresh $self.proc.coreg_s1_stdev_thresh $r_coreg_slave_tab > $slave_off.az_ovr.$it.out
                    daz, azpol = self.S1_COREG_OVERLAP(
                        iteration,
                        slave_ovr_res,
                        str(self.r_master_slave_name),
                        str(self.master_slc_tab),
                        str(self.r_slave_slc_tab),
                        str(slave_off_start),
                        str(self.slave_off),
                        float(self.proc.coreg_s1_cc_thresh),
                        float(self.proc.coreg_s1_frac_thresh),
                        float(self.proc.coreg_s1_stdev_thresh),
                        r_coreg_slave_tab,
                    )  # TODO: cout -> $slave_off.az_ovr.$it.out

                    # daz=`awk '$1 == "azimuth_pixel_offset" {print $2}' $slave_off.az_ovr.$it.out`
                    # ^--> we return this directly from S1_COREG_OVERLAP (no need to keep reading the file over and over like bash does)

                    # cp -rf $slave_off $slave_off.az_ovr.$it
                    shutil.copy(self.slave_off, f"{self.slave_off}.az_ovr.{iteration}")

                    iter_log.info(f'fine iteration update', daz=daz, azpol=azpol)

                    # Break out of the loop if we reach our target accuracy
                    if abs(daz) <= azimuth_px_offset_target:
                        break

                except CoregisterSlcException as ex:
                    iter_log.warning(
                        "Error while processing SLC fine coregistration, continuing with best estimate!",
                        daz=daz,
                        azimuth_px_offset_target=azimuth_px_offset_target,
                        exc_info=True
                    )

                    # Note: We only need to take action if we don't even complete the first iteration,
                    # as we update slave_off on the fly each iteration on success.
                    #
                    # This action is simply to use the coarse .doff as a best estimate.
                    if iteration == 1:
                        iter_log.warning("CAUTION: No fine coregistration iterations succeeded, proceeding with coarse coregistration")
                        slave_doff = self.out_dir / f"{self.r_master_slave_name}.doff"
                        shutil.copy(slave_doff, self.slave_off)

                    break

        # Mark inaccurate scenes
        if daz is None or abs(daz) > azimuth_px_offset_target:
            with self.accuracy_warning.open("a") as file:
                file.writelines(f"Error on fine coreg iteration {iteration}/{max_iteration}\n")

                if daz is not None:
                    file.writelines(f"daz: {daz} (failed to reach {azimuth_px_offset_target})\n")
                else:
                    file.writelines(f"Completely failed fine coregistration, proceeded with coarse coregistration\n")

    def S1_COREG_OVERLAP(
        self,
        iteration,
        slave_ovr_res,
        r_master_slave_name,
        master_slc_tab,
        r_slave_slc_tab,
        slave_off_start,
        slave_off,
        slave_s1_cct,
        slave_s1_frac,
        slave_s1_stdev,
        r_slave2_slc_tab: Optional[Union[str, Path]]
    ):
        """S1_COREG_OVERLAP"""
        samples_all = 0
        sum_all = 0.0
        sum_weight_all = 0.0

        log = self.log.bind(az_ovr_iter=iteration, master_slc_tab=master_slc_tab, r_slave_slc_tab=r_slave_slc_tab, r_slave2_slc_tab=r_slave2_slc_tab)

        # determine number of rows and columns of tab file and read burst SLC filenames from tab files
        master_IWs = self.READ_TAB(master_slc_tab)
        r_slave_IWs = self.READ_TAB(r_slave_slc_tab)

        # option to coregister to another slave
        if r_slave2_slc_tab is not None:
            r_slave2_IWs = self.READ_TAB(r_slave2_slc_tab)

        def calc_line_offset(IW):
            IW_par = pg.ParFile(IW.par)
            IW_TOPS = pg.ParFile(IW.TOPS_par)
            azimuth_line_time = IW_par.get_value("azimuth_line_time", dtype=float, index=0)
            burst_start_time_1 = IW_TOPS.get_value("burst_start_time_1", dtype=float, index=0)
            burst_start_time_2 = IW_TOPS.get_value("burst_start_time_2", dtype=float, index=0)
            lines_offset_float = (burst_start_time_2 - burst_start_time_1) / azimuth_line_time
            return int(0.5 + lines_offset_float)

        # determine lines offset between start of burst1 and start of burst2
        lines_offset_IWi = [None, None, None]

        # lines offset between start of burst1 and start of burst2
        lines_offset_IWi[0] = calc_line_offset(master_IWs[0])
        log.info(f"lines_offset_IW1: {lines_offset_IWi[0]}")

        if master_IWs[1] is not None:
            lines_offset_IWi[1] = calc_line_offset(master_IWs[1])
            log.info(f"lines_offset_IW2: {lines_offset_IWi[1]}")

        if master_IWs[2] is not None:
            lines_offset_IWi[2] = calc_line_offset(master_IWs[2])
            log.info(f"lines_offset_IW3: {lines_offset_IWi[2]}")

        # calculate lines_offset for the second scene (for comparsion)
        log.info(f"lines_offset_IW1: {calc_line_offset(r_slave_IWs[0])}")

        if r_slave_IWs[1] is not None:
            log.info(f"lines_offset_IW2: {calc_line_offset(r_slave_IWs[1])}")

        if r_slave_IWs[2] is not None:
            log.info(f"lines_offset_IW3: {calc_line_offset(r_slave_IWs[2])}")

        # set some parameters used
        master_IW1_par = pg.ParFile(master_IWs[0].par)

        # FIXME: Magic constants...
        round_to_6_digits = True

        # This code path is to match Bash... which seems to round to 6 digits when doing math in awk
        if round_to_6_digits:
            azimuth_line_time = round(master_IW1_par.get_value("azimuth_line_time", dtype=float, index=0), 6)
            dDC = round(1739.43 * azimuth_line_time * lines_offset_IWi[0], 6)
            dt = round(0.159154 / dDC, 6)
            dpix_factor = round(dt / azimuth_line_time, 6)
        else:
            azimuth_line_time = master_IW1_par.get_value("azimuth_line_time", dtype=float, index=0)
            dDC = 1739.43 * azimuth_line_time * lines_offset_IWi[0]
            dt = 0.159154 / dDC
            dpix_factor = dt / azimuth_line_time

        log.info(f"dDC {dDC} Hz")
        log.info(f"dt {dt} s")
        log.info(f"dpix_factor {dpix_factor} azimuth pixel")
        log.info(f"azimuth pixel offset = {dpix_factor} * average_phase_offset")

        ###################
        # determine phase offsets for sub-swath overlap regions
        def calc_phase_offsets(subswath_id, temp_dir):
            nonlocal sum_all
            nonlocal samples_all
            nonlocal sum_weight_all

            # Get subswath file paths & load par files
            IWid = f"IW{subswath_id}"

            master_IWi = master_IWs[subswath_id-1]
            r_slave_IWi = r_slave_IWs[subswath_id-1]
            r_slave2_IWi = r_slave2_IWs[subswath_id-1] if r_slave2_slc_tab is not None else None

            master_IWi_par = pg.ParFile(master_IWi.par)
            master_IWi_TOPS = pg.ParFile(master_IWi.TOPS_par)

            number_of_bursts_IWi = master_IWi_TOPS.get_value("number_of_bursts", dtype=int, index=0)
            lines_per_burst = master_IWi_TOPS.get_value("lines_per_burst", dtype=int, index=0)
            lines_offset = lines_offset_IWi[subswath_id-1]
            lines_overlap = lines_per_burst - lines_offset
            range_samples = master_IWi_par.get_value("range_samples", dtype=int, index=0)
            samples = 0
            sum = 0.0
            sum_weight = 0.0

            for i in range(1, number_of_bursts_IWi):
                starting_line1 = lines_offset + (i - 1)*lines_per_burst
                starting_line2 = i*lines_per_burst
                log.info(f"{i} {starting_line1} {starting_line2}")

                # custom file names to enable parallel processing of slave coregistration
                mas_IWi_slc = r_master_slave_name + f"_{IWid}_slc"
                mas_IWi_par = r_master_slave_name + f"_{IWid}_par"

                # SLC_copy master_IWi.slc master_IWi.par mas_IWi_slc.{i}.1 mas_IWi_par.{i}.1 - 1. 0 $range_samples $starting_line1 $lines_overlap
                # w/ option to coregister to another slave via r_slave2_slc_tab
                pg.SLC_copy(
                    master_IWi.slc if r_slave2_slc_tab is None else r_slave2_IWi.slc,
                    master_IWi.par,
                    temp_dir / f"{mas_IWi_slc}.{i}.1",
                    temp_dir / f"{mas_IWi_par}.{i}.1",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line1,
                    lines_overlap
                )

                # SLC_copy master_IWi.slc master_IWi.par mas_IWi_slc.{i}.2 mas_IWi_par.{i}.2 - 1. 0 $range_samples $starting_line2 $lines_overlap
                # w/ option to coregister to another slave via r_slave2_slc_tab
                pg.SLC_copy(
                    master_IWi.slc if r_slave2_slc_tab is None else r_slave2_IWi.slc,
                    master_IWi.par,
                    temp_dir / f"{mas_IWi_slc}.{i}.2",
                    temp_dir / f"{mas_IWi_par}.{i}.2",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line2,
                    lines_overlap
                )

                # SLC_copy $r_slave_IWi.slc $master_IWi.par $r_slave_IWi.slc.{i}.1 $r_slave_IWi.par.{i}.1 - 1. 0 $range_samples $starting_line1 $lines_overlap
                pg.SLC_copy(
                    r_slave_IWi.slc,
                    master_IWi.par,
                    temp_dir / f"{r_slave_IWi.slc}.{i}.1",
                    temp_dir / f"{r_slave_IWi.par}.{i}.1",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line1,
                    lines_overlap
                )

                # SLC_copy $r_slave_IWi.slc $master_IWi.par $r_slave_IWi.slc.{i}.2 $r_slave_IWi.par.{i}.2 - 1. 0 $range_samples $starting_line2 $lines_overlap
                pg.SLC_copy(
                    r_slave_IWi.slc,
                    master_IWi.par,
                    temp_dir / f"{r_slave_IWi.slc}.{i}.2",
                    temp_dir / f"{r_slave_IWi.par}.{i}.2",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line2,
                    lines_overlap
                )

                # calculate the 2 single look interferograms for the burst overlap region i
                # using the earlier burst --> *.int1, using the later burst --> *.int2
                off1 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.off1")
                int1 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.int1")
                _unlink(off1)
                _unlink(int1)

                # create_offset $mas_IWi_par.{i}.1 $mas_IWi_par.{i}.1 $off1 1 1 1 0
                pg.create_offset(
                    temp_dir / f"{mas_IWi_par}.{i}.1",
                    temp_dir / f"{mas_IWi_par}.{i}.1",
                    str(off1),
                    1,  # intensity cross-correlation
                    1,
                    1,
                    0,  # non-interactive mode
                )

                # SLC_intf $mas_IWi_slc.{i}.1 $r_slave_IWi.slc.{i}.1 $mas_IWi_par.{i}.1 $mas_IWi_par.{i}.1 $off1 $int1 1 1 0 - 0 0
                pg.SLC_intf(
                    temp_dir / f"{mas_IWi_slc}.{i}.1",
                    temp_dir / f"{r_slave_IWi.slc}.{i}.1",
                    temp_dir / f"{mas_IWi_par}.{i}.1",
                    temp_dir / f"{mas_IWi_par}.{i}.1",
                    str(off1),
                    str(int1),
                    1,
                    1,
                    0,
                    const.NOT_PROVIDED,
                    0,
                    0
                )

                off2 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.off2")
                int2 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.int2")
                _unlink(off2)
                _unlink(int2)

                # create_offset $mas_IWi_par.{i}.2 $mas_IWi_par.{i}.2 $off2 1 1 1 0
                pg.create_offset(
                    temp_dir / f"{mas_IWi_par}.{i}.2",
                    temp_dir / f"{mas_IWi_par}.{i}.2",
                    str(off2),
                    1,  # intensity cross-correlation
                    1,
                    1,
                    0   # non-interactive mode
                )

                # SLC_intf $mas_IWi_slc.{i}.2 $r_slave_IWi_slc.{i}.2 $mas_IWi_par.{i}.2 $mas_IWi_par.{i}.2 $off2 $int2 1 1 0 - 0 0
                pg.SLC_intf(
                    temp_dir / f"{mas_IWi_slc}.{i}.2",
                    temp_dir / f"{r_slave_IWi.slc}.{i}.2",
                    temp_dir / f"{mas_IWi_par}.{i}.2",
                    temp_dir / f"{mas_IWi_par}.{i}.2",
                    str(off2),
                    str(int2),
                    1,
                    1,
                    0,
                    const.NOT_PROVIDED,
                    0,
                    0
                )

                # calculate the single look double difference interferogram for the burst overlap region i
                # insar phase of earlier burst is subtracted from interferogram of later burst
                diff_par1 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff_par")
                diff1 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff")
                _unlink(diff_par1)

                # create_diff_par $off1 $off2 $diff_par1 0 0
                pg.create_diff_par(
                    str(off1),
                    str(off2),
                    str(diff_par1),
                    0,
                    0
                )

                # cpx_to_real $int1 tmp $range_samples 4
                pg.cpx_to_real(
                    str(int1),
                    temp_dir / "tmp",
                    range_samples,
                    4
                )

                # sub_phase $int2 tmp $diff_par1 $diff1 1 0
                pg.sub_phase(
                    str(int2),
                    temp_dir / "tmp",
                    str(diff_par1),
                    str(diff1),
                    1,
                    0
                )

                # multi-look the double difference interferogram (200 range x 4 azimuth looks)
                diff20 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20")
                off20 = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.off20")

                # multi_cpx $diff1 $off1 $diff20 $off20 200 4
                pg.multi_cpx(
                    str(diff1),
                    str(off1),
                    str(diff20),
                    str(off20),
                    200,
                    4
                )

                off20_par = pg.ParFile(off20.as_posix())
                range_samples20 = off20_par.get_value("interferogram_width", dtype=int, index=0)
                azimuth_lines20 = off20_par.get_value("interferogram_azimuth_lines", dtype=int, index=0)

                # TBD: awk does /2, and everything in awk is a float... but was this actually intended? (odd / 2 would result in a fraction)
                range_samples20_half = range_samples20 / 2
                azimuth_lines20_half = azimuth_lines20 / 2
                log.info(f"range_samples20_half: {range_samples20_half}")
                log.info(f"azimuth_lines20_half: {azimuth_lines20_half}")

                # determine coherence and coherence mask based on unfiltered double differential interferogram
                diff20cc = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.coh")
                diff20cc_ras = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.cc.ras")

                # cc_wave $diff20  - - $diff20cc $range_samples20 5 5 0
                pg.cc_wave(
                    str(diff20),
                    const.NOT_PROVIDED,
                    const.NOT_PROVIDED,
                    str(diff20cc),
                    range_samples20,
                    5,
                    5,
                    0
                )

                # rascc_mask $diff20cc - $range_samples20 1 1 0 1 1 $slave_s1_cct - 0.0 1.0 1. .35 1 $diff20cc_ras
                pg.rascc_mask(
                    str(diff20cc),
                    const.NOT_PROVIDED,
                    range_samples20,
                    1,
                    1,
                    0,
                    1,
                    1,
                    slave_s1_cct,
                    const.NOT_PROVIDED,
                    0.0,
                    1.0,
                    1.0,
                    0.35,
                    1,
                    diff20cc_ras
                )

                # adf filtering of double differential interferogram
                diff20adf = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.adf")
                diff20adfcc = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.adf.coh")

                # adf $diff20 $diff20adf $diff20adfcc $range_samples20 0.4 16 7 2
                pg.adf(
                    str(diff20),
                    str(diff20adf),
                    str(diff20adfcc),
                    range_samples20,
                    0.4,
                    16,
                    7,
                    2
                )

                _unlink(diff20adfcc)

                # unwrapping of filtered phase considering coherence and mask determined from unfiltered double differential interferogram
                diff20cc = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.coh")
                diff20cc_ras = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.cc.ras")
                diff20phase = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.phase")

                # mcf $diff20adf $diff20cc $diff20cc_ras $diff20phase $range_samples20 1 0 0 - - 1 1 512 $range_samples20_half $azimuth_lines20_half
                try:
                    pg.mcf(
                        str(diff20adf),
                        str(diff20cc),
                        str(diff20cc_ras),
                        str(diff20phase),
                        range_samples20,
                        1,
                        0,
                        0,
                        const.NOT_PROVIDED,
                        const.NOT_PROVIDED,
                        1,
                        1,
                        512,
                        range_samples20_half,
                        azimuth_lines20_half
                    )

                # Explicitly allow for MCF failures, by ignoring them (which is what bash did)
                # - the side effects of this is we won't use this burst as a sample that's accumulated into sum/average
                # -- worst case if all bursts fail, samples == 0, which is explictly handled as an error blow.
                except CoregisterSlcException as ex:
                    with self.accuracy_warning.open("a") as file:
                        file.writelines(f"MCF failure on iter {iteration}, subswath {subswath_id}, burst {i}\n")

                    log.info(f"{IWid} {i} MCF FAILURE")
                    slave_ovr_res.write(f"{IWid} {i} MCF FAILURE\n")
                    continue

                # determine overlap phase average (in radian), standard deviation (in radian), and valid data fraction
                cc_mean = 0
                cc_stdev = 0
                cc_fraction = 0
                mean = 0
                stdev = 0
                fraction = 0

                if diff20cc.exists():
                    diff20ccstat = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.cc.stat")

                    # image_stat $diff20cc $range_samples20 - - - - $diff20ccstat
                    pg.image_stat(
                        str(diff20cc),
                        range_samples20,
                        const.NOT_PROVIDED,
                        const.NOT_PROVIDED,
                        const.NOT_PROVIDED,
                        const.NOT_PROVIDED,
                        str(diff20ccstat)
                    )

                    diff20ccstat = self._grep_offset_parameter(diff20ccstat)
                    cc_mean = float(diff20ccstat["mean"][0])
                    cc_stdev = float(diff20ccstat["stdev"][0])
                    cc_fraction = float(diff20ccstat["fraction_valid"][0])

                # Check size of diff20phase file if it exists (I assume there's been issues with partial failures in the past?)
                diff20phase_size = diff20phase.stat().st_size if diff20phase.exists() else 0

                if diff20phase_size > 0:
                    diff20phasestat = temp_dir / Path(f"{r_master_slave_name}.{IWid}.{i}.diff20.phase.stat")

                    # image_stat $diff20phase $range_samples20 - - - - $diff20phasestat
                    pg.image_stat(
                        str(diff20phase),
                        range_samples20,
                        const.NOT_PROVIDED,
                        const.NOT_PROVIDED,
                        const.NOT_PROVIDED,
                        const.NOT_PROVIDED,
                        str(diff20phasestat)
                    )

                    diff20phasestat = self._grep_offset_parameter(diff20phasestat)
                    mean = float(diff20phasestat["mean"][0])
                    stdev = float(diff20phasestat["stdev"][0])
                    fraction = float(diff20phasestat["fraction_valid"][0])

                log.info(f"cc_fraction1000: {cc_fraction * 1000.0}")

                # only for overlap regions with a significant area with high coherence and phase standard deviation < slave_s1_stdev
                weight = 0.0

                if fraction > slave_s1_frac and stdev < slave_s1_stdev:
                    weight = fraction / (stdev + 0.1) / (stdev + 0.1)  # +0.1 to limit maximum weights for very low stdev

                    sum += mean * fraction
                    samples += 1
                    sum_weight += fraction

                    sum_all += mean * fraction
                    samples_all += 1
                    sum_weight_all += fraction

                else:
                    with self.accuracy_warning.open("a") as file:
                        msg_prefix = f"Poor data in {iteration}, subswath {subswath_id}, burst {i}"
                        frac_msg = f"fraction ({fraction}) <= slave_s1_frac ({slave_s1_frac})"
                        noise_msg = f"stdev ({stdev}) >= slave_s1_stdev ({slave_s1_stdev})"

                        if fraction <= slave_s1_frac:
                            file.writelines(f"{msg_prefix}: {frac_msg}\n")

                        if stdev >= slave_s1_stdev:
                            file.writelines(f"{msg_prefix}: {noise_msg}\n")

                # calculate average over the sub-swath and print it out to output text file
                if fraction > 0:
                    log.info(f"{IWid} {i} {mean} {stdev} {fraction} ({cc_mean} {cc_stdev} {cc_fraction}) {weight}")
                    slave_ovr_res.write(f"{IWid} {i} {mean} {stdev} {fraction} ({cc_mean} {cc_stdev} {cc_fraction}) {weight}\n")

                else:
                    log.info(f"{IWid} {i} 0.00000 0.00000 0.00000 ({cc_mean} {cc_stdev} {cc_fraction}) {weight}")
                    slave_ovr_res.write(f"{IWid} {i} 0.00000 0.00000 0.00000 ({cc_mean} {cc_stdev} {cc_fraction}) {weight}\n")

            # Validate data (log accuracy issues if there were issues processing any bursts)
            expected_samples = number_of_bursts_IWi - 1
            if samples != expected_samples:
                with self.accuracy_warning.open("a") as file:
                    file.writelines(f"Partial data warning on iter {iteration}, subswath {subswath_id}: only {samples}/{expected_samples} bursts processed\n")

            # Compute average
            average = sum / sum_weight if samples > 0 else 0.0
            log.info(f"{IWid} average", average=average)
            slave_ovr_res.write(f"{IWid} average: {average}\n")

            return average

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            iw1_mean = calc_phase_offsets(1, temp_path)  # IW1
            iw2_mean = calc_phase_offsets(2, temp_path)  # IW2
            iw3_mean = calc_phase_offsets(3, temp_path)  # IW3

        ###################################################################################################################

        # calculate global average
        if samples_all > 0:
            average_all = sum_all / sum_weight_all
        else:
            msg = f"CRITICAL failure on iter {iteration}, no bursts from any subswath processed!"

            with self.accuracy_warning.open("a") as file:
                file.writelines(f"\n{msg}\n\n")

            raise CoregisterSlcException(msg)

        # Calculate subswath stats
        subswath_mean = (iw1_mean + iw2_mean + iw3_mean) / 3
        subswath_stddev = (iw1_mean - subswath_mean)**2 + (iw2_mean - subswath_mean)**2 + (iw3_mean - subswath_mean)**2
        subswath_stddev = math.sqrt(subswath_stddev)

        log.info(f"subswath stats", mean=subswath_mean, stddev=subswath_stddev)
        log.info(f"scene stats", mean=average_all)
        slave_ovr_res.write(f"scene mean: {average_all}, subswath mean: {subswath_mean}, subswath stddev: {subswath_stddev}\n")

        # conversion of phase offset (in radian) to azimuth offset (in SLC pixel)
        azimuth_pixel_offset = -dpix_factor * average_all
        if round_to_6_digits:
            azimuth_pixel_offset = round(azimuth_pixel_offset, 6)

        log.info(f"azimuth_pixel_offset {azimuth_pixel_offset} [azimuth SLC pixel]")
        slave_ovr_res.write(f"azimuth_pixel_offset {azimuth_pixel_offset} [azimuth SLC pixel]\n")

        # correct offset file for determined additional azimuth offset
        azpol = self._grep_offset_parameter(slave_off_start, "azimuth_offset_polynomial")
        azpol = [float(x) for x in azpol]

        azpol[0] = azpol[0] + azimuth_pixel_offset
        log.info(f"azpol_1_out {' '.join([str(i) for i in azpol])}")

        # set_value $slave_off_start $slave_off azimuth_offset_polynomial $azpol_1_out $azpol_2 $azpol_3 $azpol_4 $azpol_5 $azpol_6 0
        pg.set_value(
            str(slave_off_start),
            str(slave_off),
            "azimuth_offset_polynomial",
            *azpol,
            0
        )

        return azimuth_pixel_offset, azpol

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
        slave_gamma0_geo = self.out_dir.joinpath(f"{self.slave_mli.stem}_geo.gamma0")

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
            geo_dem_par_vals = DemParFileParser(self.geo_dem_par)
            dem_width = geo_dem_par_vals.dem_par_params.width

            data_in_pathname = str(slave_gamma0)
            width_in = self.master_sample.mli_width_end
            lookup_table_pathname = str(self.dem_lt_fine)
            data_out_pathname = str(slave_gamma0_geo)
            width_out = dem_width
            nlines_out = const.NOT_PROVIDED
            interp_mode = 5  # B-spline interpolation
            dtype = 0  # float
            lr_in = const.NOT_PROVIDED
            lr_out = const.NOT_PROVIDED
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
            temp_bmp = temp_dir.joinpath(f"{slave_gamma0_geo.name}.bmp")
            slave_png = self.out_dir.joinpath(temp_bmp.with_suffix(".png").name)

            with working_directory(temp_dir):
                pwr_pathname = str(slave_gamma0_geo)
                width = dem_width
                start = 1
                nlines = 0
                pixavr = 20
                pixavaz = 20
                scale = const.NOT_PROVIDED
                exp = const.NOT_PROVIDED
                lr = const.NOT_PROVIDED
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

                # Convert the bitmap to a PNG w/ black pixels made transparent
                img = Image.open(temp_bmp.as_posix())
                img = np.array(img.convert('RGBA'))
                img[(img[:, :, :3] == (0, 0, 0)).all(axis=-1)] = (0, 0, 0, 0)
                Image.fromarray(img).save(slave_png.as_posix())

                # convert gamma0 Gamma file to GeoTIFF
                dem_par_pathname = str(self.geo_dem_par)
                data_pathname = str(slave_gamma0_geo)
                dtype = 2  # float
                geotiff_pathname = str(slave_gamma0_geo.with_suffix(".gamma0.tif"))
                nodata = 0.0

                pg.data2geotiff(
                    dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
                )

                # create KML map of PNG file
                image_pathname = str(slave_png)
                dem_par_pathname = str(self.geo_dem_par)
                kml_pathname = str(slave_png.with_suffix(".kml"))

                pg.kml_map(
                    image_pathname, dem_par_pathname, kml_pathname,
                )

                # geocode sigma0 mli
                slave_sigma0_geo = slave_gamma0_geo.with_suffix(".sigma0")

                data_in_pathname = str(self.r_slave_mli)
                width_in = self.master_sample.mli_width_end
                lookup_table_pathname = str(self.dem_lt_fine)
                data_out_pathname = str(slave_sigma0_geo)
                width_out = dem_width
                nlines_out = const.NOT_PROVIDED
                interp_mode = 0  # nearest-neighbor
                dtype = 0  # float
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

                # convert sigma0 Gamma file to GeoTIFF
                dem_par_pathname = str(self.geo_dem_par)
                data_pathname = str(slave_sigma0_geo)
                dtype = 2  # float
                geotiff_pathname = str(slave_sigma0_geo.with_suffix(".sigma0.tif"))
                nodata = 0.0

                pg.data2geotiff(
                    dem_par_pathname, data_pathname, dtype, geotiff_pathname, nodata,
                )

    def main(self):
        """Main method to execute methods sequence of methods need for master-slave coregistration."""

        # Re-bind thread local context to IFG processing state
        structlog.threadlocal.clear_threadlocal()
        structlog.threadlocal.bind_threadlocal(
            task="SLC coregistration",
            slc_dir=self.out_dir,
            master_date=self.master_date,
            slave_date=self.slave_date
        )

        with working_directory(self.out_dir):
            self.set_tab_files()
            self.get_lookup()
            self.reduce_offset()
            self.fine_coregistration(self.slave_date, self.list_idx)
            self.resample_full()
            self.multi_look()
            self.generate_normalised_backscatter()
