#! /usr/bin/env python

import os
import re
import tempfile
import logging
from pathlib import Path
import shutil
import datetime
import pandas as pd
from subprocess_utils import working_directory, run_command


_LOG = logging.getLogger(__name__)


class SlcProcess:
    def __init__(
        self,
        raw_data_dir: Path,
        slc_output_dir: Path,
        polarization: str,
        scene_date: str,
        burst_data: Path
    ):
        self.raw_data_dir = raw_data_dir
        self.output_dir = slc_output_dir
        self.polarization = polarization
        self.scene_date = scene_date
        self.burst_data = burst_data
        self.raw_files_patterns = {
            "data": "*measurement/s1*-iw{swath}-slc-{polarization}*.tiff",
            "annotation": "*annotation/s1*-iw{swath}-slc-{polarization}*.xml",
            "calibration": "*annotation/calibration/calibration-s1*-iw{swath}-slc-{polarization}*.xml",
            "noise": "*annotation/calibration/noise-s1*-iw{swath}-slc-{polarization}*.xml",
            "orbit_file": "*.EOF"
        }
        self.phase_shift_date = datetime.date(2015, 3, 15)
        self.swath_slc_par = "{}_{}_iw{}.slc.par"
        self.swath_slc_tops_par = "{}_{}_iw{}.slc.TOPS_par"
        self.swath_slc = "{}_{}_iw{}.slc"
        self.slc_tabs_params = None
        self.slc_prefix = None
        self.acquisition_date = None
        self.slc_tab = None
        self.slc = None
        self.slc_par = None
        self.orbit_file = None

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
                raw_files = [
                    list(
                        save_file.glob(
                            val.format(swath=swath, polarization=self.polarization)
                        )
                    )[0].as_posix()
                    for key, val in self.raw_files_patterns.items()
                ]
                _slc = self.swath_slc.format(_id, self.polarization.upper(), swath)
                _par = self.swath_slc_par.format(_id, self.polarization.upper(), swath)
                _tops_par = self.swath_slc_tops_par.format(
                    _id, self.polarization.upper(), swath
                )

                # collect the variables needed to perform slc processing
                _concat_tabs[_id][swath]["slc"] = _slc
                _concat_tabs[_id][swath]["par"] = _par
                _concat_tabs[_id][swath]["tops_par"] = _tops_par

                command = [
                    "par_S1_SLC",
                    raw_files[0],
                    raw_files[1],
                    raw_files[2],
                    raw_files[3],
                    _par,
                    _slc,
                    _tops_par,
                    "0",
                    "-",
                    "-",
                ]
                run_command(command, os.getcwd())

                # assign orbit file name
                self.orbit_file = raw_files[4]
        self.slc_tabs_params = _concat_tabs

    def _write_tabs(self, slc_tab_file, tab_params=None, _id=None):
        if slc_tab_file.exists():
            _LOG.info(
                f"{slc_tab_file.name} exits, skipping writing of slc tab parameters"
            )
            return

        with open(slc_tab_file, "w") as fid:
            for swath in [1, 2, 3]:
                if tab_params is None:
                    _slc = self.swath_slc.format(_id, self.polarization.upper(), swath)
                    _par = self.swath_slc_par.format(
                        _id, self.polarization.upper(), swath
                    )
                    _tops_par = self.swath_slc_tops_par.format(
                        _id, self.polarization.upper(), swath
                    )
                else:
                    _slc = tab_params[swath]["slc"]
                    _par = tab_params[swath]["par"]
                    _tops_par = tab_params[swath]["tops_par"]
                fid.write(_slc + " " + _par + " " + _tops_par + "\n")


    def concatenate(self):

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(
                "/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/temp_dir"
            )
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

            # prefix for final slc
            self.slc_prefix = slc_prefix

            # set the slc_tab file name
            self.slc_tab = shutil.move(
                slc_tab3,
                Path(os.getcwd()).joinpath(
                    "{}_{}_tab".format(slc_prefix, self.polarization)
                ),
            )

    def phase_shift(self):
        # perform phase shift correction for IW1 scene is acquired before 15th March, 2015
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            if self.acquisition_date < self.phase_shift_date:
                slc_dir = Path(os.getcwd())
                iw1_slc = self.swath_slc.format(self.slc_prefix, self.polarization.upper(), 1)
                iw1_slc_par = self.swath_slc_par.format(
                    self.slc_prefix, self.polarization.upper(), 1
                )
                command = [
                    "SLC_phase_shift",
                    slc_dir.joinpath(iw1_slc).as_posix(),
                    slc_dir.joinpath(iw1_slc_par).as_posix(),
                    iw1_slc,
                    iw1_slc_par,
                    "-1.25",
                ]
                run_command(command, tmpdir.as_posix())

                # replace iw1 slc with phase corrected files
                shutil.move(tmpdir.joinpath(iw1_slc), slc_dir.joinpath(iw1_slc))
                shutil.move(tmpdir.joinpath(iw1_slc_par), slc_dir.joinpath(iw1_slc_par))

    def mosiac_slc(self, rlks=12, alks=2):
        self.slc = "{}_{}.slc".format(self.slc_prefix, self.polarization.upper())
        self.slc_par = "{}_{}.slc.par".format(self.slc_prefix, self.polarization.upper())
        command = [
            "SLC_mosaic_S1_TOPS",
            self.slc_tab.as_posix(),
            self.slc,
            self.slc_par,
            str(rlks),
            str(alks)
        ]
        run_command(command, os.getcwd())

    def orbits(self):
        command = [
            "S1_OPOD_vec",
            self.slc_par,
            self.orbit_file
        ]
        run_command(command, os.getcwd())

    def frame_subset(self):
        self.acquisition_date = datetime.date(2018, 1, 20)
        df = pd.read_csv(self.burst_data)

        df['acquistion_datetime'] = pd.to_datetime(df['acquistion_datetime'])
        df['date'] = df['acquistion_datetime'].apply(lambda x: pd.Timestamp(x).date())
        df_subset = df[df['date'] == self.acquisition_date]

        tabs_param = dict()
        for swath in [1, 2, 3]:
            swath_df = df_subset[df_subset.swath == 'IW{}'.format(swath)]
            swath_df.sort_values(by='acquistion_datetime', inplace=True, ascending=True)
            tabs_param[swath]['slc'] = self.swath_slc.format(self.slc_prefix, self.polarization.upper(), swath)
            tabs_param[swath]['par'] = self.swath_slc_par.format(
                self.slc_prefix, self.polarization.upper(), swath
            )
            tabs_param[swath]['tops_par'] = self.swath_slc_tops_par.format(
                self.slc_prefix, self.polarization.upper(), swath
            )

        print(tabs_param)

if __name__ == "__main__":
    raw_path = Path(
        "/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/raw_data/T045D/F20S"
    )
    scene_date = "20180108"
    burst_data = "/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T045D_F20S/lists/slc_input.csv"
    polarization = "vv"
    outdir = Path(
        "/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T045D_F20S/SLC"
    )
    work_dir = outdir.joinpath(scene_date)
    work_dir.mkdir(exist_ok=True)
    with working_directory(work_dir):
        slc = SlcProcess(raw_path, outdir, polarization, scene_date, burst_data)
        # slc.read_raw_data()
        # slc.concatenate()
        # slc.phase_shift()
        # slc.mosiac_slc()
        # slc.orbits()
        slc.frame_subset()
