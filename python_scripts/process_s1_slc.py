#! /usr/bin/env python

import os
import re
from collections import namedtuple
from typing import Optional
import tempfile
import logging
from pathlib import Path
import shutil
import datetime
import pandas as pd
from python_scripts.subprocess_utils import working_directory, run_command


_LOG = logging.getLogger(__name__)


class SlcProcess:
    def __init__(
        self,
        raw_data_dir: Path,
        slc_output_dir: Path,
        polarization: str,
        scene_date: str,
        burst_data: Path,
        ref_master_tab: Optional[Path] = None,
    ):
        self.raw_data_dir = Path(raw_data_dir)
        self.output_dir = Path(slc_output_dir)
        self.polarization = polarization
        self.scene_date = scene_date
        self.burst_data = burst_data
        self.ref_master_tab = ref_master_tab
        self.raw_files_patterns = {
            "data": "*measurement/s1*-iw{swath}-slc-{polarization}*.tiff",
            "annotation": "*annotation/s1*-iw{swath}-slc-{polarization}*.xml",
            "calibration": "*annotation/calibration/calibration-s1*-iw{swath}-slc-{polarization}*.xml",
            "noise": "*annotation/calibration/noise-s1*-iw{swath}-slc-{polarization}*.xml",
            "orbit_file": "*.EOF",
        }
        self.phase_shift_date = datetime.date(2015, 3, 15)
        self.slc_tabs_params = None
        self.slc_prefix = None
        self.acquisition_date = None
        self.slc_tab = None
        self.orbit_file = None
        self.temp_slc = []

    def swath_tab_names(self, swath, pre_fix):
        swath_par = "{}_{}_iw{}.slc.par"
        swath_tops_par = "{}_{}_iw{}.slc.TOPS_par"
        swath_slc = "{}_{}_iw{}.slc"
        swath_tab = namedtuple('swath_tab', ['slc', 'par', 'tops_par'])
        return swath_tab(swath_slc.format(pre_fix, self.polarization.upper(), swath),
                         swath_par.format(pre_fix, self.polarization.upper(), swath),
                         swath_tops_par.format(pre_fix, self.polarization.upper(), swath))

    def slc_tab_names(self, pre_fix):
        _slc = "{}_{}.slc"
        slc_par = "{}_{}.slc.par"
        slc_tops_par = "{}_{}.slc.TOPS_par"
        slc_tab = namedtuple('slc_tab', ['slc', 'par', 'tops_par'])
        return slc_tab(_slc.format(pre_fix, self.polarization.upper()),
                       slc_par.format(pre_fix, self.polarization.upper()),
                       slc_tops_par.format(pre_fix, self.polarization.upper()))

    def slc_safe_files(self):
        safe_files = [
            item
            for item in self.raw_data_dir.joinpath(self.scene_date).iterdir()
            if item.name.endswith(".SAFE")
        ]
        return safe_files

    def read_raw_data(self):
        _concat_tabs = dict()
        for save_file in self.slc_safe_files():
            _id = save_file.stem
            _concat_tabs[_id] = dict()
            dt_start = re.findall("[0-9]{8}T[0-9]{6}", _id)[0]
            start_datetime = datetime.datetime.strptime(dt_start, "%Y%m%dT%H%M%S")
            self.acquisition_date = start_datetime.date()
            _concat_tabs[_id]["datetime"] = start_datetime

            for swath in [1, 2, 3]:
                _concat_tabs[_id][swath] = dict()
                tab_names = self.swath_tab_names(swath, _id)
                raw_files = [
                    list(
                        save_file.glob(
                            val.format(swath=swath, polarization=self.polarization.lower())
                        )
                    )[0].as_posix()
                    for key, val in self.raw_files_patterns.items()
                ]

                # collect the variables needed to perform slc processing
                _concat_tabs[_id][swath]["slc"] = tab_names.slc
                _concat_tabs[_id][swath]["par"] = tab_names.par
                _concat_tabs[_id][swath]["tops_par"] = tab_names.tops_par

                command = [
                    "par_S1_SLC",
                    raw_files[0],
                    raw_files[1],
                    raw_files[2],
                    raw_files[3],
                    tab_names.par,
                    tab_names.slc,
                    tab_names.tops_par,
                    "0",
                    "-",
                    "-",
                ]
                run_command(command, os.getcwd())

                # assign orbit file name
                self.orbit_file = raw_files[4]

                # store names of flies to be removed later
                for item in [tab_names.slc, tab_names.par, tab_names.tops_par]:
                    self.temp_slc.append(item)
        self.slc_tabs_params = _concat_tabs

    def _write_tabs(self, slc_tab_file, tab_params=None, _id=None, slc_data_dir=None):
        if slc_tab_file.exists():
            _LOG.info(
                f"{slc_tab_file.name} exits, skipping writing of slc tab parameters"
            )
            return

        with open(slc_tab_file, "w") as fid:
            for swath in [1, 2, 3]:
                if tab_params is None:
                    tab_names = self.swath_tab_names(swath, _id)
                    _slc = tab_names.slc
                    _par = tab_names.par
                    _tops_par = tab_names.tops_par
                else:
                    _slc = tab_params[swath]["slc"]
                    _par = tab_params[swath]["par"]
                    _tops_par = tab_params[swath]["tops_par"]

                if slc_data_dir is not None:
                    _slc = slc_data_dir.joinpath(_slc).as_posix()
                    _par = slc_data_dir.joinpath(_par).as_posix()
                    _tops_par = slc_data_dir.joinpath(_tops_par).as_posix()

                fid.write(_slc + " " + _par + " " + _tops_par + "\n")

    def concatenate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            start_tabs, *rest_tabs = sorted(
                self.slc_tabs_params.items(), key=lambda x: x[1]["datetime"]
            )
            slc_tab1 = None
            for idx, item in enumerate(rest_tabs):
                _, _vals_start = start_tabs
                _, _vals_stop = item

                _dt = _vals_start["datetime"]
                if len(rest_tabs) == idx + 1:
                    slc_prefix = "{:04}{:02}{:02}".format(_dt.year, _dt.month, _dt.day)
                else:
                    slc_prefix = "{:04}{:02}{:02}{:02}{:02}{:02}".format(
                        _dt.year, _dt.month, _dt.day, _dt.hour, _dt.minute, _dt.second
                    )

                # create slc_tab1 only at the beginning
                if slc_tab1 is None:
                    slc_tab1 = tmpdir.joinpath(f"slc_tab1_{idx}")
                    self._write_tabs(slc_tab1, tab_params=_vals_start)

                # create slc_tab2
                slc_tab2 = tmpdir.joinpath(f"slc_tab2_{idx}")
                self._write_tabs(slc_tab2, tab_params=_vals_stop)

                # create slc_tab3 (merge tab)
                slc_tab3 = tmpdir.joinpath(f"slc_tab3_{idx}")
                self._write_tabs(slc_tab3, _id=slc_prefix)

                command = [
                    "SLC_cat_ScanSAR",
                    slc_tab1.as_posix(),
                    slc_tab2.as_posix(),
                    slc_tab3.as_posix(),
                ]
                run_command(command, os.getcwd())

                # assign slc_tab3 to slc_tab1 to perform series of concatenation
                slc_tab1 = slc_tab3

            # clean up the temporary slc files after clean up
            for fp in self.temp_slc:
                os.remove(fp)

            # prefix for final slc
            self.slc_prefix = slc_prefix

            # set the slc_tab file name
            self.slc_tab = shutil.move(
                slc_tab3,
                Path(os.getcwd()).joinpath(
                    "{}_{}_tab".format(slc_prefix, self.polarization)
                ),
            )

    def phase_shift(self, swath=1):
        """perform phase shift correction for IW1 scenes acquired before 15th March, 2015"""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            if self.acquisition_date < self.phase_shift_date:
                slc_dir = Path(os.getcwd())
                tab_names = self.swath_tab_names(swath, self.slc_prefix)
                command = [
                    "SLC_phase_shift",
                    slc_dir.joinpath(tab_names.slc).as_posix(),
                    slc_dir.joinpath(tab_names.par).as_posix(),
                    tab_names.slc,
                    tab_names.par,
                    "-1.25",
                ]
                run_command(command, tmpdir.as_posix())

                # replace iw1 slc with phase corrected files
                shutil.move(tmpdir.joinpath(tab_names.slc), slc_dir.joinpath(tab_names.slc))
                shutil.move(tmpdir.joinpath(tab_names.par), slc_dir.joinpath(tab_names.par))

    def mosiac_slc(self, rlks=12, alks=2):
        slc_tab = self.slc_tab_names(self.slc_prefix)
        command = [
            "SLC_mosaic_S1_TOPS",
            self.slc_tab.as_posix(),
            slc_tab.slc,
            slc_tab.par,
            str(rlks),
            str(alks),
        ]
        run_command(command, os.getcwd())

    def orbits(self):
        slc_tab = self.slc_tab_names(self.slc_prefix)
        command = ["S1_OPOD_vec", slc_tab.par, self.orbit_file]
        run_command(command, os.getcwd())

    def frame_subset(self):
        df = pd.read_csv(self.burst_data)
        df["acquistion_datetime"] = pd.to_datetime(df["acquistion_datetime"])
        df["date"] = df["acquistion_datetime"].apply(lambda x: pd.Timestamp(x).date())
        df_subset = df[df["date"] == self.acquisition_date]
        tabs_param = dict()
        complete_frame = True

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            burst_tab = tmpdir.joinpath("burst_tab")
            with open(burst_tab, "w") as fid:
                for swath in [1, 2, 3]:
                    tmp_dict = dict()
                    swath_df = df_subset[df_subset.swath == "IW{}".format(swath)]
                    swath_df = swath_df.sort_values(
                        by="acquistion_datetime", ascending=True
                    )

                    # write the burst numbers to subset from the concatenated swaths
                    start_burst = None
                    end_burst = None
                    total_bursts = 0
                    for row in swath_df.itertuples():
                        missing_bursts = row.missing_master_bursts.strip("][")
                        if missing_bursts:
                            complete_frame = False

                        burst_nums = [
                            int(i) for i in row.burst_number.strip("][").split(",")
                        ]
                        if start_burst is None:
                            start_burst = min(burst_nums)
                        if end_burst is None:
                            end_burst = max(burst_nums)
                        else:
                            end_burst = max(burst_nums) + total_bursts
                        total_bursts += int(row.total_bursts)

                    fid.write(str(start_burst) + " " + str(end_burst) + "\n")
                    tab_names = self.swath_tab_names(swath, self.slc_prefix)
                    tmp_dict["slc"] = tab_names.slc
                    tmp_dict["par"] = tab_names.par
                    tmp_dict["tops_par"] = tab_names.tops_par
                    tabs_param[swath] = tmp_dict

            # write out slc in and out tab files
            sub_slc_in = tmpdir.joinpath("sub_slc_input_tab")
            self._write_tabs(sub_slc_in, tab_params=tabs_param)

            sub_slc_out = tmpdir.joinpath("sub_slc_output_tab")
            self._write_tabs(sub_slc_out, _id=self.slc_prefix, slc_data_dir=tmpdir)

            # run the subset
            command = [
                "SLC_copy_ScanSAR",
                sub_slc_in.as_posix(),
                sub_slc_out.as_posix(),
                burst_tab.as_posix(),
                "0",
            ]
            run_command(command, os.getcwd())

            # replace concatenate slc with burst-subset of concatenated slc
            for swath in [1, 2, 3]:
                tab_names = self.swath_tab_names(swath, self.slc_prefix)
                for item in [tab_names.slc, tab_names.par, tab_names.tops_par]:
                    shutil.move(tmpdir.joinpath(item), item)

            if not complete_frame:
                if self.ref_master_tab is None:
                    err = (
                        f" ref_master_tab is None, needs ref_master_tab "
                        f"to resize incomplete frame for scene {self.scene_date}"
                    )
                    raise ValueError(err)
                self.frame_resize(self.ref_master_tab, sub_slc_in)

    def frame_resize(self, ref_slc_tab: Path, full_slc_tab: Path):
        # determine the resize burst tab
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            burst_tab = tmpdir.joinpath("burst_tab").as_posix()
            command = [
                "S1_BURST_tab",
                ref_slc_tab.as_posix(),
                full_slc_tab.as_posix(),
                burst_tab,
            ]
            run_command(command, os.getcwd())

            # write output in a temp directory
            resize_slc_tab = tmpdir.joinpath("sub_slc_output_tab")
            self._write_tabs(resize_slc_tab, _id=self.slc_prefix, slc_data_dir=tmpdir)

            command = [
                "SLC_copy_ScanSAR",
                full_slc_tab.as_posix(),
                resize_slc_tab.as_posix(),
                burst_tab,
            ]
            run_command(command, os.getcwd())

            # replace full slc with resized slc
            for swath in [1, 2, 3]:
                tab_names = self.swath_tab_names(swath, self.slc_prefix)
                for item in [tab_names.slc, tab_names.par, tab_names.tops_par]:
                    shutil.move(tmpdir.joinpath(item), item)

    def burst_images(self):
        """make a quick look of .png files for each swath and mosiac slc"""
        def _make_png(tab_names):
            range_samples = None
            azimuth_lines = None
            with open(tab_names.par, 'r') as src:
                lines = src.readlines()
                for line in lines:
                    if line.startswith("range_samples:"):
                        range_samples = int(line.split(':')[1].strip())
                    if line.startswith("azimuth_lines:"):
                        azimuth_lines = int(line.split(':')[1].strip())
                    if range_samples is not None and azimuth_lines is not None:
                        break

                with tempfile.TemporaryDirectory() as tmpdir:
                    tmpdir = Path(tmpdir)
                    bmp_file = tmpdir.joinpath("{}".format(tab_names.slc)).with_suffix(".bmp").as_posix()
                    command = [
                        "rasSLC",
                        tab_names.slc,
                        str(range_samples),
                        '1',
                        str(azimuth_lines),
                        "50",
                        "20",
                        "-",
                        "-",
                        "1",
                        "0",
                        "0",
                        bmp_file
                    ]
                    run_command(command, os.getcwd())
                    command = [
                        "convert",
                        bmp_file,
                        Path(tab_names.slc).with_suffix(".png").as_posix()
                    ]
                    run_command(command, os.getcwd())

        tab_names_list = [self.swath_tab_names(swath, self.slc_prefix) for swath in [1, 2, 3]]
        tab_names_list.append(self.slc_tab_names(self.slc_prefix))
        for tab in tab_names_list:
            _make_png(tab)

    def main(self, write_png=True):
        """main method to execute methods need to produce slc"""
        work_dir = self.output_dir.joinpath(self.scene_date)
        work_dir.mkdir(exist_ok=True)
        with working_directory(work_dir):
            self.read_raw_data()
            self.concatenate()
            self.phase_shift()
            self.mosiac_slc()
            self.orbits()
            self.frame_subset()
            self.mosiac_slc()
            if write_png:
                self.burst_images()
