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
import math
from dataclasses import dataclass

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.subprocess_utils import working_directory
from insar.project import ProcConfig
from insar.coreg_utils import rm_file, grep_stdout
import insar.constant as const

from insar.paths.coregistration import CoregisteredSlcPaths

_LOG = structlog.get_logger("insar")


class CoregisterSlcException(Exception):
    pass


pg = GammaInterface(
    subprocess_func=auto_logging_decorator(
        subprocess_wrapper, CoregisterSlcException, _LOG
    )
)


# FIXME: This could ba generic write_tabs_file that takes a pattern which we write
# per-swath parts into - to be re-used by this + slc + any others
# - when we fix this, move it to use the SlcPaths class.
def write_tabs_file(
    tab_file: Union[Path, str],
    _id: str,
    data_dir: Optional[Path] = None
):
    """Writes a tab file input as required by GAMMA."""
    with open(tab_file, "w") as fid:
        for swath in [1, 2, 3]:
            # FIXME: Path class? (these are probably duplicated elsewhere)
            swath_par = f"{_id}_IW{swath}.slc.par"
            swath_tops_par = f"{_id}_IW{swath}.slc.TOPS_par"
            swath_slc = f"{_id}_IW{swath}.slc"

            if data_dir is not None:
                swath_slc = str(data_dir / swath_slc)
                swath_par = str(data_dir / swath_par)
                swath_tops_par = str(data_dir / swath_tops_par)

            fid.write(swath_slc + " " + swath_par + " " + swath_tops_par + "\n")


def READ_TAB(tab_file: Union[str, Path]):
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


@dataclass
class CoregistrationContext:
    proc: ProcConfig
    paths: CoregisteredSlcPaths
    log: structlog.BoundLogger


class CoregisterSlc:
    def __init__(
        self,
        proc: ProcConfig,
        list_idx: Union[str, int],
        slc_primary: Union[str, Path],
        slc_secondary: Union[str, Path],
        range_looks: int,
        azimuth_looks: int,
        rdc_dem: Union[str, Path],
        outdir: Optional[Union[str, Path]] = None,
    ) -> None:
        """
        Co-registers Sentinel-1 IW SLC to a chosen primary SLC geometry.

        :param proc:
            The gamma proc configuration file for the coregistration processing.
        :param list_idx:
            The list file index the secondary originated from (eg: 1 for secondaries1.list),
            or '-' if not applicable (eg: primary coregistration).
        :param slc_primary:
            A full path to a primary (reference) SLC image file.
        :param slc_secondary:
            A full Path to a secondary SLC image file.
        :param range_looks:
            A range look value.
        :param azimuth_looks:
            An azimuth look value.
        :param rdc_dem:
            A full path to a dem (height map) in RDC of primary SLC.
        :param outdir:
            A full path to a output directory.
        """
        self.proc = proc
        self.list_idx = list_idx
        self.rdc_dem = rdc_dem
        self.alks = azimuth_looks
        self.rlks = range_looks

        self.secondary_date, self.secondary_pol = slc_secondary.stem.split('_')
        self.primary_date, self.primary_pol = slc_primary.stem.split('_')

        self.log = _LOG.bind(
            task="SLC coregistration",
            polarization=self.secondary_pol,
            secondary_date=self.secondary_date,
            slc_secondary=slc_secondary,
            primary_date=self.primary_date,
            slc_primary=slc_primary,
            list_idx=self.list_idx
        )

        self.range_step = None
        self.azimuth_step = None
        self.primary_sample = None

        paths = CoregisteredSlcPaths(
            proc,
            self.primary_date,
            self.secondary_date,
            self.secondary_pol,
            range_looks
        )

        self.out_dir = outdir
        if self.out_dir is None:
            self.out_dir = paths.secondary.dir
        self.accuracy_warning = self.out_dir / "ACCURACY_WARNING"

        self.ctx = CoregistrationContext(proc, paths, self.log)


    def set_tab_files(
        self,
        paths: CoregisteredSlcPaths
    ):
        """Writes tab files used in secondary co-registration."""

        # write a secondary slc tab file
        write_tabs_file(paths.secondary_slc_tab, paths.secondary.slc.stem, paths.secondary.dir)

        # write a re-sampled secondary slc tab file
        write_tabs_file(
            paths.r_secondary_slc_tab, paths.r_secondary_slc.stem, paths.secondary.dir
        )

        # write primary slc tab file
        write_tabs_file(
            paths.primary_slc_tab, paths.primary.slc.stem, paths.primary.dir
        )


    def get_lookup(self, lut_path: Path, rdc_dem: Path) -> None:
        """
        Determine lookup table based on orbit data and DEM.

        :param rdc_dem:
            A full path to a dem (height map) in RDC of primary SLC.
        """

        paths = self.ctx.paths

        pg.rdc_trans(
            paths.r_dem_primary_mli_par,
            rdc_dem,
            paths.secondary.mli_par,
            lut_path,
        )

    def primary_sample_size(self):
        """Returns the start and end rows and cols."""

        paths = self.ctx.paths

        par_slc = pg.ParFile(str(paths.r_dem_primary_slc_par))
        par_mli = pg.ParFile(str(paths.r_dem_primary_mli_par))
        sample_size = namedtuple(
            "primary",
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
            par_slc.get_value("range_samples", dtype=int, index=0),
            0,
            par_slc.get_value("azimuth_lines", dtype=int, index=0),
            0,
            par_mli.get_value("range_samples", dtype=int, index=0),
        )

    def reduce_offset(
        self,
        range_offset_max: Optional[int] = 64,
        azimuth_offset_max: Optional[int] = 32,
    ):
        """Reduce offset estimation to max offset values."""
        self.primary_sample = self.primary_sample_size()

        self.range_step = int(
            (self.primary_sample.slc_width_end - self.primary_sample.slc_width_start) / 64
        )
        if range_offset_max > self.range_step:
            self.range_step = range_offset_max
        self.azimuth_step = int(
            (self.primary_sample.slc_lines_end - self.primary_sample.slc_lines_start) / 64
        )
        if azimuth_offset_max > self.azimuth_step:
            self.azimuth_step = azimuth_offset_max

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

        Iterative improvement of refinement offsets between primary SLC and resampled secondary RSLC
        using intensity matching (offset_pwr_tracking).
        """

        paths = self.ctx.paths

        self.log.info("Beginning coarse coregistration")

        # coreg between differently polarised data makes no sense
        if self.secondary_pol != self.primary_pol:
            raise ValueError("Can not coregister two scenes of different polarisation!")

        # create secondary offset
        pg.create_offset(
            str(paths.r_dem_primary_slc_par),
            str(paths.secondary.slc_par),
            str(paths.secondary_off),
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

            secondary_doff = self.out_dir / f"{paths.r_primary_secondary_name}.doff"
            secondary_offs = temp_dir.joinpath(f"{paths.r_primary_secondary_name}.offs")
            secondary_snr = temp_dir.joinpath(f"{paths.r_primary_secondary_name}.snr")
            secondary_diff_par = temp_dir.joinpath(f"{paths.r_primary_secondary_name}.diff_par")

            while abs(d_azimuth) > max_azimuth_threshold and iteration < max_iteration:
                secondary_off_start = temp_dir.joinpath(f"{paths.secondary_off.name}.start")
                shutil.copy(paths.secondary_off, secondary_off_start)

                # re-sample ScanSAR burst mode SLC using a look-up-table and SLC offset polynomials for refinement
                with working_directory(temp_dir):
                    pg.SLC_interp_lt_ScanSAR(
                        str(paths.secondary_slc_tab),
                        str(paths.secondary.slc_par),
                        str(paths.primary_slc_tab),
                        str(paths.r_dem_primary_slc_par),
                        str(paths.secondary_lt),
                        str(paths.r_dem_primary_mli_par),
                        str(paths.secondary.mli_par),
                        str(secondary_off_start),
                        str(paths.r_secondary_slc_tab),
                        str(paths.r_secondary_slc),
                        str(paths.r_secondary_slc_par),
                    )

                    if secondary_doff.exists():
                        os.remove(secondary_doff)

                    # create and update ISP offset parameter file
                    pg.create_offset(
                        str(paths.r_dem_primary_slc_par),
                        str(paths.secondary.slc_par),
                        str(secondary_doff),
                        1,          # intensity cross-correlation
                        self.rlks,
                        self.alks,
                        0,          # non-interactive mode
                    )

                    # offset tracking between SLC images using intensity cross-correlation
                    pg.offset_pwr_tracking(
                        str(paths.primary.slc),
                        str(paths.r_secondary_slc),
                        str(paths.r_dem_primary_slc_par),
                        str(paths.r_secondary_slc_par),
                        str(secondary_doff),
                        str(secondary_offs),
                        str(secondary_snr),
                        128,                 # rwin
                        64,                  # azwin
                        const.NOT_PROVIDED,  # offsets
                        1,                   # n_ovr
                        0.2,                 # thres
                        self.range_step,
                        self.azimuth_step,
                        self.primary_sample.slc_width_start,
                        self.primary_sample.slc_width_end,
                        self.primary_sample.slc_lines_start,
                        self.primary_sample.slc_lines_end,
                    )

                    # range and azimuth offset polynomial estimation
                    _, cout, _ = pg.offset_fit(
                        str(secondary_offs),
                        str(secondary_snr),
                        str(secondary_doff),
                        const.NOT_PROVIDED,  # coffs
                        const.NOT_PROVIDED,  # coffsets
                        0.2,                 # thresh
                        1,                   # npolynomial
                        0,                   # non-interactive
                    )

                    range_stdev, azimuth_stdev = re.findall(
                        r"[-+]?[0-9]*\.?[0-9]+",
                        grep_stdout(
                            cout, "final model fit std. dev. (samples) range:"
                        ),
                    )

                    # look-up table refinement
                    # determine range and azimuth corrections for look-up table (in mli pixels)
                    doff_vals = pg.ParFile(secondary_doff.as_posix())
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
                        secondary_offs=secondary_offs,
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

                    if secondary_diff_par.exists():
                        os.remove(secondary_diff_par)

                    # create template diff parameter file for geocoding
                    par1_pathname = str(paths.r_dem_primary_mli_par)
                    par2_pathname = str(paths.r_dem_primary_mli_par)
                    diff_par_pathname = str(secondary_diff_par)
                    par_type = 1  # SLC/MLI_par ISP SLC/MLI parameters
                    iflg = 0  # non-interactive mode

                    pg.create_diff_par(
                        par1_pathname, par2_pathname, diff_par_pathname, par_type, iflg,
                    )

                    # update range_offset_polynomial in diff param file
                    par_in_pathname = str(secondary_diff_par)
                    par_out_pathname = str(secondary_diff_par)
                    search_keyword = "range_offset_polynomial"
                    new_value = f"{d_range_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"

                    pg.set_value(
                        par_in_pathname, par_out_pathname, search_keyword, new_value,
                    )

                    # update azimuth_offset_polynomial in diff param file
                    par_in_pathname = str(secondary_diff_par)
                    par_out_pathname = str(secondary_diff_par)
                    search_keyword = "azimuth_offset_polynomial"
                    new_value = f"{d_azimuth_mli}   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00   0.0000e+00"

                    pg.set_value(
                        par_in_pathname, par_out_pathname, search_keyword, new_value,
                    )

                    # update look-up table
                    _secondary_lt = temp_dir.joinpath(f"{paths.secondary_lt.name}.{iteration}")
                    shutil.copy(paths.secondary_lt, _secondary_lt)

                    # geocoding look-up table refinement using diff par offset polynomial
                    pg.gc_map_fine(
                        str(_secondary_lt),
                        self.primary_sample.mli_width_end,
                        str(secondary_diff_par),
                        str(paths.secondary_lt),
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


    def get_tertiary_coreg_scene(
        self,
        secondary = None,
        list_idx = None
    ):
        if secondary is None:
            secondary = self.secondary_date

        if list_idx is None:
            list_idx = self.list_idx

        paths = self.ctx.paths

        # slc_secondary is something like:
        # /g/data/dz56/insar_initial_processing/T147D_F28S_S1A/SLC/20180220/20180220_VV.slc.par
        list_dir = Path(self.proc.output_path) / self.proc.list_dir

        coreg_secondary = None

        # coregister to nearest secondary if list_idx is given
        if list_idx == const.NOT_PROVIDED:  # coregister to primary
            coreg_secondary = None

        elif list_idx == "0":  # coregister to adjacent secondary
            # get secondary position in secondaries.list
            # secondary_pos=`grep -n $secondary $secondary_list | cut -f1 -d:`
            secondary_pos = self._get_matching_lineno(self.proc.secondary_list, secondary)

            if int(secondary) < int(self.proc.ref_primary_scene):
                coreg_pos = secondary_pos + 1

            elif int(secondary) > int(self.proc.ref_primary_scene):
                coreg_pos = secondary_pos - 1

            # coreg_secondary=`head -n $coreg_pos $secondary_list | tail -1`
            coreg_secondary = self._read_line(self.proc.secondary_list, coreg_pos)

        elif int(list_idx) > 20140000:  # coregister to particular secondary
            coreg_secondary = list_idx

        else:  # coregister to secondary image with short temporal baseline
            # take the first/last secondary of the previous list for coregistration
            prev_list_idx = int(list_idx) - 1

            if int(secondary) < int(self.proc.ref_primary_scene):
                # coreg_secondary=`head $list_dir/secondaries$prev_list_idx.list -n1`
                coreg_secondary = self._read_line(list_dir / f'secondaries{prev_list_idx}.list', 0)

            elif int(secondary) > int(self.proc.ref_primary_scene):
                # coreg_secondary=`tail $list_dir/secondaries$prev_list_idx.list -n1`
                coreg_secondary = self._read_line(list_dir / f'secondaries{prev_list_idx}.list', -1)

        return coreg_secondary


    def fine_coregistration(
        self,
        secondary: Union[str, int],
        list_idx: Union[str, int],
        max_iteration: Optional[int] = 5,
        max_azimuth_threshold: Optional[float] = 0.01,
        azimuth_px_offset_target: Optional[float] = 0.0001,
    ):
        """Performs a fine co-registration"""

        self.coarse_registration(max_iteration, max_azimuth_threshold)
        daz = None
        paths = self.ctx.paths

        self.log.info("Beginning fine coregistration")

        # slc_secondary is something like:
        # /g/data/dz56/insar_initial_processing/T147D_F28S_S1A/SLC/20180220/20180220_VV.slc.par
        slc_dir = Path(self.proc.output_path) / self.proc.slc_dir

        with tempfile.TemporaryDirectory() as temp_dir, open(Path(temp_dir) / f"{paths.r_primary_secondary_name}.ovr_results", 'w') as secondary_ovr_res:
            temp_dir = Path(temp_dir)

            # initialize the output text file
            secondary_ovr_res.writelines('\n'.join([
                "    Burst Overlap Results",
                f"        thresholds applied: cc_thresh: {self.proc.coreg_s1_cc_thresh},  ph_fraction_thresh: {self.proc.coreg_s1_frac_thresh}, ph_stdev_thresh (rad): {self.proc.coreg_s1_stdev_thresh}",
                "",
                "        IW  overlap  ph_mean ph_stdev ph_fraction   (cc_mean cc_stdev cc_fraction)    weight",
                "",
            ]))

            for iteration in range(1, max_iteration+1):
                # cp -rf $secondary_off $secondary_off_start
                secondary_off_start = temp_dir.joinpath(f"{paths.secondary_off.name}.start")
                shutil.copy(paths.secondary_off, secondary_off_start)

                # GM SLC_interp_lt_S1_TOPS $secondary_slc_tab $secondary_slc_par $primary_slc_tab $r_dem_primary_slc_par $secondary_lt $r_dem_primary_mli_par $secondary_mli_par $secondary_off_start $r_secondary_slc_tab $r_secondary_slc $r_secondary_slc_par
                pg.SLC_interp_lt_ScanSAR(
                    str(paths.secondary_slc_tab),
                    str(paths.secondary.slc_par),
                    str(paths.primary_slc_tab),
                    str(paths.r_dem_primary_slc_par),
                    str(paths.secondary_lt),
                    str(paths.r_dem_primary_mli_par),
                    str(paths.secondary.mli_par),
                    str(secondary_off_start),
                    str(paths.r_secondary_slc_tab),
                    str(paths.r_secondary_slc),
                    str(paths.r_secondary_slc_par),
                )

                # Query tertiary coreg scene (based on list_idx)
                coreg_secondary = self.get_tertiary_coreg_scene()
                r_coreg_secondary_tab = None

                if coreg_secondary:
                    r_coreg_secondary_tab = f'{slc_dir}/{coreg_secondary}/r{coreg_secondary}_{self.proc.polarisation}_tab'

                iter_log = self.log.bind(
                    iteration=iteration,
                    max_iteration=max_iteration,
                    primary_slc_tab=paths.primary_slc_tab,
                    r_secondary_slc_tab=paths.r_secondary_slc_tab,
                    r_secondary2_slc_tab=r_coreg_secondary_tab
                )

                try:
                    # S1_COREG_OVERLAP $primary_slc_tab $r_secondary_slc_tab $secondary_off_start $secondary_off $self.proc.coreg_s1_cc_thresh $self.proc.coreg_s1_frac_thresh $self.proc.coreg_s1_stdev_thresh $r_coreg_secondary_tab > $secondary_off.az_ovr.$it.out
                    daz, azpol = self.S1_COREG_OVERLAP(
                        iteration,
                        secondary_ovr_res,
                        str(paths.r_primary_secondary_name),
                        str(paths.primary_slc_tab),
                        str(paths.r_secondary_slc_tab),
                        str(secondary_off_start),
                        str(paths.secondary_off),
                        float(self.proc.coreg_s1_cc_thresh),
                        float(self.proc.coreg_s1_frac_thresh),
                        float(self.proc.coreg_s1_stdev_thresh),
                        r_coreg_secondary_tab,
                    )  # TODO: cout -> $secondary_off.az_ovr.$it.out

                    # daz=`awk '$1 == "azimuth_pixel_offset" {print $2}' $secondary_off.az_ovr.$it.out`
                    # ^--> we return this directly from S1_COREG_OVERLAP (no need to keep reading the file over and over like bash does)

                    # cp -rf $secondary_off $secondary_off.az_ovr.$it
                    shutil.copy(paths.secondary_off, f"{paths.secondary_off}.az_ovr.{iteration}")

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
                    # as we update secondary_off on the fly each iteration on success.
                    #
                    # This action is simply to use the coarse .doff as a best estimate.
                    if iteration == 1:
                        iter_log.warning("CAUTION: No fine coregistration iterations succeeded, proceeding with coarse coregistration")
                        secondary_doff = self.out_dir / f"{paths.r_primary_secondary_name}.doff"
                        shutil.copy(secondary_doff, paths.secondary_off)

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
        secondary_ovr_res,
        r_primary_secondary_name,
        primary_slc_tab,
        r_secondary_slc_tab,
        secondary_off_start,
        secondary_off,
        secondary_s1_cct,
        secondary_s1_frac,
        secondary_s1_stdev,
        r_secondary2_slc_tab: Optional[Union[str, Path]]
    ):
        """S1_COREG_OVERLAP"""
        samples_all = 0
        sum_all = 0.0
        sum_weight_all = 0.0

        log = self.log.bind(az_ovr_iter=iteration, primary_slc_tab=primary_slc_tab, r_secondary_slc_tab=r_secondary_slc_tab, r_secondary2_slc_tab=r_secondary2_slc_tab)

        # determine number of rows and columns of tab file and read burst SLC filenames from tab files
        primary_IWs = READ_TAB(primary_slc_tab)
        r_secondary_IWs = READ_TAB(r_secondary_slc_tab)

        # option to coregister to another secondary
        if r_secondary2_slc_tab is not None:
            r_secondary2_IWs = READ_TAB(r_secondary2_slc_tab)

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
        lines_offset_IWi[0] = calc_line_offset(primary_IWs[0])
        log.info(f"lines_offset_IW1: {lines_offset_IWi[0]}")

        if primary_IWs[1] is not None:
            lines_offset_IWi[1] = calc_line_offset(primary_IWs[1])
            log.info(f"lines_offset_IW2: {lines_offset_IWi[1]}")

        if primary_IWs[2] is not None:
            lines_offset_IWi[2] = calc_line_offset(primary_IWs[2])
            log.info(f"lines_offset_IW3: {lines_offset_IWi[2]}")

        # calculate lines_offset for the second scene (for comparsion)
        log.info(f"lines_offset_IW1: {calc_line_offset(r_secondary_IWs[0])}")

        if r_secondary_IWs[1] is not None:
            log.info(f"lines_offset_IW2: {calc_line_offset(r_secondary_IWs[1])}")

        if r_secondary_IWs[2] is not None:
            log.info(f"lines_offset_IW3: {calc_line_offset(r_secondary_IWs[2])}")

        # set some parameters used
        primary_IW1_par = pg.ParFile(primary_IWs[0].par)

        # FIXME: Magic constants...
        round_to_6_digits = True

        # This code path is to match Bash... which seems to round to 6 digits when doing math in awk
        if round_to_6_digits:
            azimuth_line_time = round(primary_IW1_par.get_value("azimuth_line_time", dtype=float, index=0), 6)
            dDC = round(1739.43 * azimuth_line_time * lines_offset_IWi[0], 6)
            dt = round(0.159154 / dDC, 6)
            dpix_factor = round(dt / azimuth_line_time, 6)
        else:
            azimuth_line_time = primary_IW1_par.get_value("azimuth_line_time", dtype=float, index=0)
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

            primary_IWi = primary_IWs[subswath_id-1]
            r_secondary_IWi = r_secondary_IWs[subswath_id-1]
            r_secondary2_IWi = r_secondary2_IWs[subswath_id-1] if r_secondary2_slc_tab is not None else None

            primary_IWi_par = pg.ParFile(primary_IWi.par)
            primary_IWi_TOPS = pg.ParFile(primary_IWi.TOPS_par)

            number_of_bursts_IWi = primary_IWi_TOPS.get_value("number_of_bursts", dtype=int, index=0)
            lines_per_burst = primary_IWi_TOPS.get_value("lines_per_burst", dtype=int, index=0)
            lines_offset = lines_offset_IWi[subswath_id-1]
            lines_overlap = lines_per_burst - lines_offset
            range_samples = primary_IWi_par.get_value("range_samples", dtype=int, index=0)
            samples = 0
            sum = 0.0
            sum_weight = 0.0

            for i in range(1, number_of_bursts_IWi):
                starting_line1 = lines_offset + (i - 1)*lines_per_burst
                starting_line2 = i*lines_per_burst
                log.info(f"{i} {starting_line1} {starting_line2}")

                # custom file names to enable parallel processing of secondary coregistration
                mas_IWi_slc = r_primary_secondary_name + f"_{IWid}_slc"
                mas_IWi_par = r_primary_secondary_name + f"_{IWid}_par"

                # SLC_copy primary_IWi.slc primary_IWi.par mas_IWi_slc.{i}.1 mas_IWi_par.{i}.1 - 1. 0 $range_samples $starting_line1 $lines_overlap
                # w/ option to coregister to another secondary via r_secondary2_slc_tab
                pg.SLC_copy(
                    primary_IWi.slc if r_secondary2_slc_tab is None else r_secondary2_IWi.slc,
                    primary_IWi.par,
                    temp_dir / f"{mas_IWi_slc}.{i}.1",
                    temp_dir / f"{mas_IWi_par}.{i}.1",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line1,
                    lines_overlap
                )

                # SLC_copy primary_IWi.slc primary_IWi.par mas_IWi_slc.{i}.2 mas_IWi_par.{i}.2 - 1. 0 $range_samples $starting_line2 $lines_overlap
                # w/ option to coregister to another secondary via r_secondary2_slc_tab
                pg.SLC_copy(
                    primary_IWi.slc if r_secondary2_slc_tab is None else r_secondary2_IWi.slc,
                    primary_IWi.par,
                    temp_dir / f"{mas_IWi_slc}.{i}.2",
                    temp_dir / f"{mas_IWi_par}.{i}.2",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line2,
                    lines_overlap
                )

                # SLC_copy $r_secondary_IWi.slc $primary_IWi.par $r_secondary_IWi.slc.{i}.1 $r_secondary_IWi.par.{i}.1 - 1. 0 $range_samples $starting_line1 $lines_overlap
                r_secondary_IWi_slc_name = Path(r_secondary_IWi.slc).name
                r_secondary_IWi_par_name = Path(r_secondary_IWi.par).name

                pg.SLC_copy(
                    r_secondary_IWi.slc,
                    primary_IWi.par,
                    temp_dir / f"{r_secondary_IWi_slc_name}.{i}.1",
                    temp_dir / f"{r_secondary_IWi_par_name}.{i}.1",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line1,
                    lines_overlap
                )

                # SLC_copy $r_secondary_IWi.slc $primary_IWi.par $r_secondary_IWi.slc.{i}.2 $r_secondary_IWi.par.{i}.2 - 1. 0 $range_samples $starting_line2 $lines_overlap
                pg.SLC_copy(
                    r_secondary_IWi.slc,
                    primary_IWi.par,
                    temp_dir / f"{r_secondary_IWi_slc_name}.{i}.2",
                    temp_dir / f"{r_secondary_IWi_par_name}.{i}.2",
                    const.NOT_PROVIDED,
                    1.0,
                    0,
                    range_samples,
                    starting_line2,
                    lines_overlap
                )

                # calculate the 2 single look interferograms for the burst overlap region i
                # using the earlier burst --> *.int1, using the later burst --> *.int2
                off1 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.off1")
                int1 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.int1")
                rm_file(off1)
                rm_file(int1)

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

                # SLC_intf $mas_IWi_slc.{i}.1 $r_secondary_IWi.slc.{i}.1 $mas_IWi_par.{i}.1 $mas_IWi_par.{i}.1 $off1 $int1 1 1 0 - 0 0
                pg.SLC_intf(
                    temp_dir / f"{mas_IWi_slc}.{i}.1",
                    temp_dir / f"{r_secondary_IWi_slc_name}.{i}.1",
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

                off2 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.off2")
                int2 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.int2")
                rm_file(off2)
                rm_file(int2)

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

                # SLC_intf $mas_IWi_slc.{i}.2 $r_secondary_IWi_slc.{i}.2 $mas_IWi_par.{i}.2 $mas_IWi_par.{i}.2 $off2 $int2 1 1 0 - 0 0
                pg.SLC_intf(
                    temp_dir / f"{mas_IWi_slc}.{i}.2",
                    temp_dir / f"{r_secondary_IWi_slc_name}.{i}.2",
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
                diff_par1 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff_par")
                diff1 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff")
                rm_file(diff_par1)

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
                diff20 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20")
                off20 = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.off20")

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
                diff20cc = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.coh")
                diff20cc_ras = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.cc.ras")

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

                # rascc_mask $diff20cc - $range_samples20 1 1 0 1 1 $secondary_s1_cct - 0.0 1.0 1. .35 1 $diff20cc_ras
                pg.rascc_mask(
                    str(diff20cc),
                    const.NOT_PROVIDED,
                    range_samples20,
                    1,
                    1,
                    0,
                    1,
                    1,
                    secondary_s1_cct,
                    const.NOT_PROVIDED,
                    0.0,
                    1.0,
                    1.0,
                    0.35,
                    1,
                    diff20cc_ras
                )

                # adf filtering of double differential interferogram
                diff20adf = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.adf")
                diff20adfcc = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.adf.coh")

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

                rm_file(diff20adfcc)

                # unwrapping of filtered phase considering coherence and mask determined from unfiltered double differential interferogram
                diff20cc = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.coh")
                diff20cc_ras = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.cc.ras")
                diff20phase = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.phase")

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
                    secondary_ovr_res.write(f"{IWid} {i} MCF FAILURE\n")
                    continue

                # determine overlap phase average (in radian), standard deviation (in radian), and valid data fraction
                cc_mean = 0
                cc_stdev = 0
                cc_fraction = 0
                mean = 0
                stdev = 0
                fraction = 0

                if diff20cc.exists():
                    diff20ccstat = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.cc.stat")

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
                    diff20phasestat = temp_dir / Path(f"{r_primary_secondary_name}.{IWid}.{i}.diff20.phase.stat")

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

                # only for overlap regions with a significant area with high coherence and phase standard deviation < secondary_s1_stdev
                weight = 0.0

                if fraction > secondary_s1_frac and stdev < secondary_s1_stdev:
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
                        frac_msg = f"fraction ({fraction}) <= secondary_s1_frac ({secondary_s1_frac})"
                        noise_msg = f"stdev ({stdev}) >= secondary_s1_stdev ({secondary_s1_stdev})"

                        if fraction <= secondary_s1_frac:
                            file.writelines(f"{msg_prefix}: {frac_msg}\n")

                        if stdev >= secondary_s1_stdev:
                            file.writelines(f"{msg_prefix}: {noise_msg}\n")

                # calculate average over the sub-swath and print it out to output text file
                if fraction > 0:
                    log.info(f"{IWid} {i} {mean} {stdev} {fraction} ({cc_mean} {cc_stdev} {cc_fraction}) {weight}")
                    secondary_ovr_res.write(f"{IWid} {i} {mean} {stdev} {fraction} ({cc_mean} {cc_stdev} {cc_fraction}) {weight}\n")

                else:
                    log.info(f"{IWid} {i} 0.00000 0.00000 0.00000 ({cc_mean} {cc_stdev} {cc_fraction}) {weight}")
                    secondary_ovr_res.write(f"{IWid} {i} 0.00000 0.00000 0.00000 ({cc_mean} {cc_stdev} {cc_fraction}) {weight}\n")

            # Validate data (log accuracy issues if there were issues processing any bursts)
            expected_samples = number_of_bursts_IWi - 1
            if samples != expected_samples:
                with self.accuracy_warning.open("a") as file:
                    file.writelines(f"Partial data warning on iter {iteration}, subswath {subswath_id}: only {samples}/{expected_samples} bursts processed\n")

            # Compute average
            average = sum / sum_weight if samples > 0 else 0.0
            log.info(f"{IWid} average", average=average)
            secondary_ovr_res.write(f"{IWid} average: {average}\n")

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
        secondary_ovr_res.write(f"scene mean: {average_all}, subswath mean: {subswath_mean}, subswath stddev: {subswath_stddev}\n")

        # conversion of phase offset (in radian) to azimuth offset (in SLC pixel)
        azimuth_pixel_offset = -dpix_factor * average_all
        if round_to_6_digits:
            azimuth_pixel_offset = round(azimuth_pixel_offset, 6)

        log.info(f"azimuth_pixel_offset {azimuth_pixel_offset} [azimuth SLC pixel]")
        secondary_ovr_res.write(f"azimuth_pixel_offset {azimuth_pixel_offset} [azimuth SLC pixel]\n")

        # correct offset file for determined additional azimuth offset
        azpol = self._grep_offset_parameter(secondary_off_start, "azimuth_offset_polynomial")
        azpol = [float(x) for x in azpol]

        azpol[0] = azpol[0] + azimuth_pixel_offset
        log.info(f"azpol_1_out {' '.join([str(i) for i in azpol])}")

        # set_value $secondary_off_start $secondary_off azimuth_offset_polynomial $azpol_1_out $azpol_2 $azpol_3 $azpol_4 $azpol_5 $azpol_6 0
        pg.set_value(
            str(secondary_off_start),
            str(secondary_off),
            "azimuth_offset_polynomial",
            *azpol,
            0
        )

        return azimuth_pixel_offset, azpol

    def resample_full(self, lut_path: Path, offset_path: Path):
        """
        Resample full-resolution SLC image using a look-up table and SLC offset polynomials for refinement
        Uses the GAMMA DIFF/GEO program: SLC_interp_lt_ScanSAR (suitable for Sentinel-1 IW data)
        """

        paths = self.ctx.paths

        slc2_tab = str(paths.secondary_slc_tab)
        slc2_par = str(paths.secondary.slc_par)
        slc1_tab = str(paths.primary_slc_tab)
        slc1_par = str(paths.r_dem_primary_slc_par)
        mli1_par = str(paths.r_dem_primary_mli_par)
        mli2_par = str(paths.secondary.mli_par)
        slc2r_tab = str(paths.r_secondary_slc_tab)
        slc_2r = str(paths.r_secondary_slc)
        slc2r_par = str(paths.r_secondary_slc_par)

        pg.SLC_interp_lt_ScanSAR(
            slc2_tab,
            slc2_par,
            slc1_tab,
            slc1_par,
            lut_path,
            mli1_par,
            mli2_par,
            offset_path,
            slc2r_tab,
            slc_2r,
            slc2r_par,
        )

    def multi_look(self):
        """
        Generates down-sampled multi-look intensity image from a secondary SLC image.
        Uses the GAMMA ISP program: multi_look
        """

        paths = self.ctx.paths

        slc_pathname = str(paths.r_secondary_slc)
        slc_par_pathname = str(paths.r_secondary_slc_par)
        mli_pathname = str(paths.r_secondary_mli)
        mli_par_pathname = str(paths.r_secondary_mli_par)
        rlks = self.rlks
        alks = self.alks

        pg.multi_look(
            slc_pathname, slc_par_pathname, mli_pathname, mli_par_pathname, rlks, alks,
        )


    def main(self):
        """Main method to process coregistered SLC products."""

        # Re-bind thread local context
        try:
            structlog.threadlocal.clear_threadlocal()
            structlog.threadlocal.bind_threadlocal(
                task="SLC coregistration and multi-looking",
                slc_dir=self.out_dir,
                primary_date=self.primary_date,
                secondary_date=self.secondary_date
            )

            # Validate inputs
            paths = self.ctx.paths

            if not paths.r_dem_primary_mli_par.exists():
                self.log.error(
                    "DEM primary MLI par file not found",
                    pathname=paths.r_dem_primary_mli_par,
                )

            if not paths.r_dem_primary_slc_par.exists():
                self.log.error(
                    "DEM primary SLC par file not found",
                    pathname=paths.r_dem_primary_slc_par,
                )

            if not paths.secondary.slc_par.exists():
                self.log.error("SLC secondary par file not found", pathname=paths.secondary.slc_par)

            if not paths.secondary.mli_par.exists():
                self.log.error("Secondary MLI par file not found", pathname=paths.secondary.mli_par)


            with working_directory(self.out_dir):
                self.set_tab_files(paths)
                self.get_lookup(paths.secondary_lt, self.rdc_dem)
                self.reduce_offset()
                self.fine_coregistration(self.secondary_date, self.list_idx)

                # Note: for now, resampling/multilook remains part of "coregistration"
                # - this is technically 1) resampling based on the coregistration and 2) downsampling...
                self.resample_full(paths.secondary_lt, paths.secondary_off)
                self.multi_look()

        finally:
            structlog.threadlocal.clear_threadlocal()


    def apply_coregistration(
        self,
        secondary_off: Optional[Path],
        lookup_table: Optional[Path]
    ):
        """Applies a coregistration LUT and offset refinements to SLC products."""

        paths = self.ctx.paths

        if secondary_off is None:
            secondary_off = paths.secondary_off

        if lookup_table is None:
            lookup_table = paths.secondary_lt

        # Re-bind thread local context
        try:
            structlog.threadlocal.clear_threadlocal()
            structlog.threadlocal.bind_threadlocal(
                task="SLC coregistration and resampling",
                slc_dir=self.out_dir,
                primary_date=self.primary_date,
                secondary_date=self.secondary_date
            )

            with working_directory(self.out_dir):
                self.set_tab_files(self.ctx.paths)

                # Note: for now, resampling/multilook remains part of "coregistration"
                # - this is technically 1) the application of the coregistration and 2) downsampling...
                self.resample_full(lookup_table, secondary_off)
                self.multi_look()

        finally:
            structlog.threadlocal.clear_threadlocal()
