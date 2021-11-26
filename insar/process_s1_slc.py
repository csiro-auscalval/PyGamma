#!/usr/bin/env python

import os
import re
from collections import namedtuple
from typing import Optional, Union, Dict, List
import tempfile
from pathlib import Path
import shutil
import datetime
import pandas as pd
import structlog
import json

from insar import constant as const
from insar.constant import SlcFilenames
from insar.subprocess_utils import working_directory
from insar.process_utils import convert
from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper

_LOG = structlog.get_logger("insar")


class ProcessSlcException(Exception):
    pass


# Customise Gamma shim to automatically handle basic error checking and logging
pg = GammaInterface(
    subprocess_func=auto_logging_decorator(subprocess_wrapper, ProcessSlcException, _LOG)
)


class SlcProcess:
    def __init__(
        self,
        raw_data_dir: Union[Path, str],
        slc_output_dir: Union[Path, str],
        polarization: str,
        scene_date: str,
        burst_data: Union[Path, str],
        ref_primary_tab: Optional[Union[Path, str]] = None,
    ) -> None:
        """
        A full SLC creation for Sentinel-1 IW swath data.

        A full SLC image is created using Interferometric-Wide (IW)
        swath data as an input. The three sub-swaths (IW1, IW2, IW3)
        are mosiacked into a single SLC and subsets SLC by bursts
        after full SLC creation.

        :param raw_data_dir:
            A full path to a raw data_dir that contains SLC SAFE files.
        :param slc_output_dir:
            A full path to a output directory to store full SLC files.
        :param polarization:
            A polarization of an SLC file to be used [choice: 'VV' or 'VH']
        :param scene_date:
            A date ('YYYYMMDD') formatted string of SLC acquisition date.
        :param burst_data:
            A full path to a csv file containing burst information needed
            to subset to form full SLC.
        param ref_primary_tab:
            An Optional full path to a reference primary slc tab file.
        """

        self.raw_data_dir = Path(raw_data_dir)
        # FIXME: when we come back to clean this up, output_dir should be the 'actual' output dir,
        # not the top level SLC dir - we don't care about the SLC dir, we always append self.scene_date to it...
        # because that's where we "actually" output data ...
        self.output_dir = Path(slc_output_dir)
        self.polarization = polarization
        self.scene_date = scene_date
        self.burst_data = burst_data

        if ref_primary_tab is not None:
            self.ref_primary_tab = Path(ref_primary_tab)

        self.raw_files_patterns = {
            "data": "*measurement/s1*-iw{swath}-slc-{polarization}*.tiff",
            "annotation": "*annotation/s1*-iw{swath}-slc-{polarization}*.xml",
            "calibration": "*annotation/calibration/calibration-s1*-iw{swath}-slc-{polarization}*.xml",
            "noise": "*annotation/calibration/noise-s1*-iw{swath}-slc-{polarization}*.xml",
            "orbit_file": "*.EOF",
        }

        # GA's InSAR team found S1 data before Nov 2015 is of poorer quality for SAR interferometry & more
        # likely to create interferogram discontinuities. GAMMA's SLC_phase_shift uses March 2015 though.
        # The InSAR team has decided not to use interferometric products before this. See:
        # https://github.com/GeoscienceAustralia/gamma_insar/pull/157
        self.phase_shift_date = datetime.date(2015, 3, 10)

        # slc_tabs_params will be a dict, created in read_raw_data() and used in concatenate()
        self.slc_tabs_params = None  # dict
        self.slc_prefix = None  # str
        self.acquisition_date = None
        self.slc_tab = None
        self.orbit_file = None
        self.temp_slc = []

        self.log = _LOG.bind(task="S1 SLC processing", scene_date=scene_date, ref_primary_tab=ref_primary_tab)

    def swath_tab_names(self, swath: int, pre_fix: str,) -> namedtuple:
        """Formats slc swath tab file names using swath and pre_fix."""

        swath_tab = namedtuple("swath_tab", ["slc", "par", "tops_par"])
        return swath_tab(
            SlcFilenames.SLC_IW_FILENAME.value.format(
                pre_fix, self.polarization.upper(), swath
            ),
            SlcFilenames.SLC_IW_PAR_FILENAME.value.format(
                pre_fix, self.polarization.upper(), swath
            ),
            SlcFilenames.SLC_IW_TOPS_PAR_FILENAME.value.format(
                pre_fix, self.polarization.upper(), swath
            ),
        )

    def slc_tab_names(self, pre_fix: str,) -> namedtuple:
        """Formats slc tab file names using prefix."""

        slc_tab = namedtuple("slc_tab", ["slc", "par", "tops_par"])
        return slc_tab(
            SlcFilenames.SLC_FILENAME.value.format(pre_fix, self.polarization.upper()),
            SlcFilenames.SLC_PAR_FILENAME.value.format(
                pre_fix, self.polarization.upper()
            ),
            SlcFilenames.SLC_TOPS_PAR_FILENAME.value.format(
                pre_fix, self.polarization.upper()
            ),
        )

    def slc_safe_files(self) -> List[Path]:
        """Returns list of .SAFE file paths need to form full SLC for a date."""

        safe_files = [
            item
            for item in self.raw_data_dir.joinpath(self.scene_date).iterdir()
            if item.name.endswith(".SAFE")
        ]
        return safe_files

    def read_scene_date(self):
        """Reads Sentinel-1 SLC data to determine the acquisition date of the scene"""

        _dt = None

        # Read raw data, and take the earliest start date
        for save_file in self.slc_safe_files():
            _id = save_file.stem
            # _id = basename of .SAFE folder, e.g.
            # S1A_IW_SLC__1SDV_20180103T191741_20180103T191808_019994_0220EE_1A2D

            # add start time to dict
            dt_start = re.findall("[0-9]{8}T[0-9]{6}", _id)[0]
            start_datetime = datetime.datetime.strptime(dt_start, "%Y%m%dT%H%M%S")

            # Note: Repeating this assignment here as the second pass doesn't read_raw_data, it uses this function.
            self.acquisition_date = start_datetime.date()

            if _dt is None or start_datetime < _dt:
                _dt = start_datetime

        return _dt

    def read_raw_data(self):
        """Reads Sentinel-1 SLC data and generate SLC parameter file."""

        self.acquisition_bursts = {}
        self.metadata = {
            "slc": {}
        }

        _concat_tabs = dict()
        for save_file in self.slc_safe_files():
            _id = save_file.stem
            _concat_tabs[_id] = dict()
            # _id = basename of .SAFE folder, e.g.
            # S1A_IW_SLC__1SDV_20180103T191741_20180103T191808_019994_0220EE_1A2D

            # Identify source data URL
            src_url = save_file / "src_url"
            # - if this is raw_data we've extracted from a source archive, a src_url file will exist
            if src_url.exists():
                src_url = src_url.read_text()
            # - otherwise it's a source data directory that's been provided by the user
            else:
                src_url = save_file.as_posix()

            self.acquisition_bursts[_id] = {}
            self.metadata[_id] = {
                "src_url": src_url
            }

            # add start time to dict
            dt_start = re.findall("[0-9]{8}T[0-9]{6}", _id)[0]
            start_datetime = datetime.datetime.strptime(dt_start, "%Y%m%dT%H%M%S")
            self.acquisition_date = start_datetime.date()
            _concat_tabs[_id]["datetime"] = start_datetime

            for swath in [1, 2, 3]:
                _concat_tabs[_id][swath] = dict()
                tab_names = self.swath_tab_names(swath, _id)
                raw_files = []

                # Find this swath's raw data files
                for key, val in self.raw_files_patterns.items():
                    pattern = val.format(swath=swath, polarization=self.polarization.lower())
                    matched_files = list(save_file.glob(pattern))

                    # Sanity check SAFE file structure
                    if not matched_files:
                        # We allow orbit files to be missing (also they're not part of SAFE file contents)
                        if key == "orbit_file":
                            raw_files.append(None)
                            continue
                        else:
                            raise FileNotFoundError(f"Failed to find required S1 {key} files")

                    elif len(matched_files) != 1:
                        raise ProcessSlcException(f"Invalid ESA SAFE structure, more than one {key} file found for IW{swath}")

                    raw_files.append(matched_files[0].as_posix())

                # collect the variables needed to perform slc processing
                _concat_tabs[_id][swath]["slc"] = tab_names.slc
                _concat_tabs[_id][swath]["par"] = tab_names.par
                _concat_tabs[_id][swath]["tops_par"] = tab_names.tops_par

                geotiff_pathname = raw_files[0]
                annotation_xml_pathname = raw_files[1]
                calibration_xml_pathname = raw_files[2]
                noise_xml_pathname = raw_files[3]
                slc_par_pathname = tab_names.par
                slc_pathname = tab_names.slc
                tops_par_pathname = tab_names.tops_par

                # par_S1_SLC creates the following three output files:
                # 1. slc_par_pathname (*.slc.par)
                # 2. slc_pathname (*.slc), and;
                # 3. tops_par_pathname (*slc.TOPS_par).
                pg.par_S1_SLC(
                    geotiff_pathname,
                    annotation_xml_pathname,
                    calibration_xml_pathname,
                    noise_xml_pathname,
                    slc_par_pathname,
                    slc_pathname,
                    tops_par_pathname,
                    const.SLC_DTYPE_FCOMPLEX,
                    const.NOT_PROVIDED,  # sc_db, scale factor for FCOMPLEX -> SCOMPLEX
                    const.NOT_PROVIDED,  # noise_pwr, noise intensity for each SLC sample in slant range
                )

                # assign orbit file name
                self.orbit_file = raw_files[4]

                # store the file names of *slc, *.slc.par and
                # *.slc.TOPS_par so that they can to be removed later
                for item in [tab_names.slc, tab_names.par, tab_names.tops_par]:
                    self.temp_slc.append(item)

                # Use acquisition metadata for this swath to count how many bursts it contains
                num_subswath_burst = 0

                xml_pattern = self.raw_files_patterns["annotation"]
                xml_pattern = xml_pattern.format(swath=swath, polarization=self.polarization.lower())
                for xml_file in save_file.glob(xml_pattern):
                    _, cout, _ = pg.S1_burstloc(xml_file)
                    num_bursts = sum([line.startswith("Burst") for line in cout])
                    num_subswath_burst += num_bursts

                self.acquisition_bursts[_id][swath] = num_subswath_burst
                self.metadata[_id][f"IW{swath}_bursts"] = num_subswath_burst

        self.slc_tabs_params = _concat_tabs
        self.metadata["slc"]["orbit_url"] = self.orbit_file

        # Write metadata used to produce this SLC
        metadata_path = self.output_dir / self.scene_date / f"metadata_{self.polarization}.json"
        with metadata_path.open("w") as file:
            json.dump(self.metadata, file, indent=2)

    def _write_tabs(
        self,
        slc_tab_file: Union[Path, str],
        tab_params: Optional[Dict] = None,
        _id: Optional[str] = None,
        slc_data_dir: Optional[Union[Path, str]] = None,
    ) -> None:
        """
        Writes tab (ascii) files needed in SlcProcess.

        :param slc_tab_file:
            A full path of an slc tab file.
        :param tab_params:
            An Optional tab params to write SLC tab file content.
        :param _id:
            An Optional parameter to form SLC tab names if tab_params is None.
        :param slc_data_dir:
            An Optional parameter to prepend (slc, par, tops_par) file names to
            form full path.
        """
        if slc_tab_file.exists():
            self.log.info(
                "SLC tab file exists; skipping writing of SLC tab parameters",
                pathname=slc_tab_file,
            )
            return

        files_in_slc_tabs = []

        with open(slc_tab_file, "w") as fid:
            for swath in [1, 2, 3]:
                if tab_params is None:
                    # using swath_tab_names, create file names for:
                    # *_iw{swath}.slc
                    # *_iw{swath}.slc.par
                    # *_iw{swath}.slc.TOPS_par
                    #
                    # using _id. self.swath_tab_names should create
                    # {_id}_{polarisation}_iw{swath}.slc
                    # {_id}_{polarisation}_iw{swath}.slc.par
                    # {_id}_{polarisation}_iw{swath}.slc.TOPS_par
                    tab_names = self.swath_tab_names(swath, _id)

                    _slc = tab_names.slc
                    _par = tab_names.par
                    _tops_par = tab_names.tops_par
                else:
                    _slc = tab_params[swath]["slc"]
                    _par = tab_params[swath]["par"]
                    _tops_par = tab_params[swath]["tops_par"]

                if slc_data_dir is not None:
                    _slc = Path(slc_data_dir).joinpath(_slc).as_posix()
                    _par = Path(slc_data_dir).joinpath(_par).as_posix()
                    _tops_par = Path(slc_data_dir).joinpath(_tops_par).as_posix()

                files_in_slc_tabs.append([_slc, _par, _tops_par])
                fid.write(_slc + " " + _par + " " + _tops_par + "\n")

        # useful to have easy access to the file names
        # that are listed in these slc_tabs.
        return files_in_slc_tabs

    def concatenate(self) -> None:
        """Concatenate multi-scenes to create new frame."""

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # slc_tabs_params is a multi-layered dict()
            # slc_tabs_params[SAFE_basename][dt]
            # slc_tabs_params[SAFE_basename][swath1][slc]
            # slc_tabs_params[SAFE_basename][swath1][par]
            # slc_tabs_params[SAFE_basename][swath1][tops_par]

            # Order slc_tabs_params based ascending date & time. The
            # first slc_tabs_params[SAFE_basename] will be assigned
            # as first_tabs, the remaining dicts will be stored in
            # remaining_tabs. Note that first_tabs is a tuple,
            # while remaining_tabs is a list of dictionaries
            first_tabs, *remaining_tabs = sorted(
                self.slc_tabs_params.items(), key=lambda x: x[1]["datetime"]
            )
            _, _initial_dict = first_tabs
            _dt = _initial_dict["datetime"]

            if not remaining_tabs:
                # There is only one acquisition for this day, hence
                # remaining_tabs is None, and there is no need to
                # concatenate files using pg.SLC_cat_ScanSAR.
                # Instead, renaming the *.slc, *.slc.par and
                # *.slc.TOPS_par files created from pg.par_S1_SLC.
                self.slc_prefix = "{:04}{:02}{:02}".format(_dt.year, _dt.month, _dt.day)
                self.slc_tab = Path(os.getcwd()).joinpath(
                    "{}_{}_tab".format(self.slc_prefix, self.polarization)
                )
                for swath in [1, 2, 3]:
                    _tab_names = self.swath_tab_names(swath, self.slc_prefix)
                    os.rename(_initial_dict[swath]["slc"], _tab_names.slc)
                    os.rename(_initial_dict[swath]["par"], _tab_names.par)
                    os.rename(_initial_dict[swath]["tops_par"], _tab_names.tops_par)

                files_in_slc_tab = self._write_tabs(
                    self.slc_tab, _id=self.slc_prefix, slc_data_dir=os.getcwd()
                )

            else:
                # multiple SLC acquisitions for this day. Use
                # pg.SLC_cat_ScanSAR to concatenate these
                # acquisitions into single files

                slc_tab_ifile1 = None
                slc_merged_tabs_list = []
                files_in_slc_tab1 = []
                files_in_slc_tab2 = []
                files_in_slc_tab3 = []

                for idx, safe_tuple in enumerate(remaining_tabs):
                    # safe_tuple = (
                    #     safe_basename,
                    #     multi-layered dict
                    # )
                    safe_basename, _remaining_dict_idx = safe_tuple

                    # _remaining_dict_idx = {
                    #     'datetime': datetime object
                    #     1: {
                    #         'slc': *_iw1.slc filename
                    #         'par': *_iw1.slc.par filename
                    #         'tops_par': *_iw1.slc.TOPS_par filename
                    #        }
                    #     2: {
                    #          'slc': *_iw2.slc filename
                    #          'par': *_iw2.slc.par filename
                    #          'tops_par': *_iw2.slc.TOPS_par filename
                    #        }
                    #     3: {
                    #          'slc': *_iw3.slc filename
                    #          'par': *_iw3.slc.par filename
                    #          'tops_par': *_iw3.slc.TOPS_par filename
                    #        }
                    # }

                    # specify slc_prefix
                    if idx == len(remaining_tabs) - 1:
                        # for the last iteration set slc_prefix
                        # as year and date of acquisition. This
                        # will be used in the merging table
                        slc_prefix = "{0:04}{1:02}{2:02}".format(
                            _dt.year, _dt.month, _dt.day
                        )
                    else:
                        # it is crucial that slc_prefix is different
                        # for every iteration, otherwise SLC_cat_ScanSAR
                        # will attempt to overwrite the concatenated
                        # files which cause SLC_cat_ScanSAR to
                        # raise errors and then exit.
                        slc_prefix = "{0:04}{1:02}{2:02}{3:02}{4:02}{5:02}_ix{6}".format(
                            _dt.year,
                            _dt.month,
                            _dt.day,
                            _dt.hour,
                            _dt.minute,
                            _dt.second,
                            idx,
                        )

                    # create slc_tab_ifile1 only at the beginning
                    if slc_tab_ifile1 is None:
                        slc_tab_ifile1 = tmpdir.joinpath(f"slc_tab_input1_{idx}.txt")
                        files_in_slc_tab1.append(
                            self._write_tabs(
                                slc_tab_ifile1,
                                tab_params=_initial_dict,
                                slc_data_dir=os.getcwd(),
                            )
                        )

                    # create slc_tab_ifile2
                    slc_tab_ifile2 = tmpdir.joinpath(f"slc_tab_input2_{idx}.txt")
                    files_in_slc_tab2.append(
                        self._write_tabs(
                            slc_tab_ifile2,
                            tab_params=_remaining_dict_idx,
                            slc_data_dir=os.getcwd(),
                        )
                    )

                    # create slc_merge_tab_ofile (merge tab)
                    slc_merge_tab_ofile = tmpdir.joinpath(f"slc_merged_tab_{idx}.txt")
                    files_in_slc_tab3.append(
                        self._write_tabs(
                            slc_merge_tab_ofile, _id=slc_prefix, slc_data_dir=os.getcwd()
                        )
                    )

                    # concat sequential ScanSAR burst SLC images
                    tab_input1_path = str(slc_tab_ifile1)
                    tab_input2_path = str(slc_tab_ifile2)
                    tab_output_path = str(slc_merge_tab_ofile)
                    slc_merged_tabs_list.append(tab_output_path)

                    # SLC_cat_ScanSAR will perform concatenation. Here,
                    # data from slc_tab_ifile2 are appended into
                    # slc_tab_ifile1, with the merged output placed
                    # into the files specified inside slc_merge_tab_ofile.
                    #
                    # At the end of the first iteration,
                    #   tab_input1_path = tab_output_path
                    pg.SLC_cat_ScanSAR(
                        tab_input1_path, tab_input2_path, tab_output_path,
                    )

                    # assign slc_merge_tab_ofile to slc_tab_ifile1
                    # to perform series of concatenation
                    slc_tab_ifile1 = slc_merge_tab_ofile

                    # to conserve memory, delete temporary concatenated
                    # files from the previous iteration. This code will
                    # keep concatenated files from the last iteration.
                    if idx > 0:
                        # get temp. files of previus iterations
                        for _swath_mfile_list in files_in_slc_tab3[idx - 1]:
                            for _mfile in _swath_mfile_list:
                                os.remove(_mfile)

                # clean up the temporary slc files after clean up
                for fp in self.temp_slc:
                    os.remove(fp)

                # prefix for final slc
                self.slc_prefix = slc_prefix

                # set the slc_tab file name
                self.slc_tab = shutil.move(
                    slc_merge_tab_ofile,
                    Path(os.getcwd()).joinpath(
                        "{}_{}_tab".format(slc_prefix, self.polarization)
                    ),
                )
            # end-else
        # end-with

    def phase_shift(self, swath: Optional[int] = 1,) -> None:
        """Perform phase shift correction.

        Phase shift-correction is needed for Sentinel-1 IW1 swath data collected
        before 15th March, 2015.

        :param swath:
            Optional swath number to perform phase shift on. Otherwise, IW-1 is
            corrected for the scenes acquired before 15th March, 2015.
        """

        if self.acquisition_date >= self.phase_shift_date:
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            slc_dir = Path(os.getcwd())
            tab_names = self.swath_tab_names(swath, self.slc_prefix)

            with working_directory(tmpdir):
                slc_1_pathname = str(slc_dir.joinpath(tab_names.slc))
                slc_1_par_pathname = str(slc_dir.joinpath(tab_names.par))
                slc_2_pathname = tab_names.slc
                slc_2_par_pathname = tab_names.par

                pg.SLC_phase_shift(
                    slc_1_pathname,
                    slc_1_par_pathname,
                    slc_2_pathname,
                    slc_2_par_pathname,
                    -1.25,  # ph_shift: phase shift to add to SLC phase (radians)
                )

                # replace iw1 slc with phase corrected files
                shutil.move(
                    tmpdir.joinpath(tab_names.slc), slc_dir.joinpath(tab_names.slc)
                )
                shutil.move(
                    tmpdir.joinpath(tab_names.par), slc_dir.joinpath(tab_names.par)
                )

    def mosaic_slc(
        self, range_looks: Optional[int] = 12, azimuth_looks: Optional[int] = 2,
    ) -> None:
        """
        Calculate SLC mosaic of Sentinel-1 TOPS burst SLC data.

        :param range_looks:
            An Optional range look value. Otherwise default rlks is used.
        :param azimuth_looks:
            An Optional azimuth look value. Otherwise default alks is used.
        """

        slc_tab = self.slc_tab_names(self.slc_prefix)

        slc_tab_pathname = str(self.slc_tab)
        slc_pathname = slc_tab.slc
        slc_par_pathname = slc_tab.par

        pg.SLC_mosaic_S1_TOPS(
            slc_tab_pathname, slc_pathname, slc_par_pathname, range_looks, azimuth_looks,
        )

    def orbits(self):
        """Extract Sentinel-1 OPOD state vectors and copy into the ISP image parameter file"""

        if not self.orbit_file:
            self.log.warning("No orbit file for this scene exists")
            return

        slc_tab = self.slc_tab_names(self.slc_prefix)

        slc_par_pathname = slc_tab.par
        opod_pathname = self.orbit_file

        pg.S1_OPOD_vec(
            slc_par_pathname, opod_pathname,
        )

    # TODO; check keys for spelling
    # TODO: add to constants
    def frame_subset(self):
        """Subset frames to form full SLC frame of a vector file.

        Full Frame is formed after sub-setting burst data listed in
        the self.burst_data needed to form a full frame.
        """

        acq_datetime_key = "acquisition_datetime"

        df = pd.read_csv(self.burst_data, index_col=0)
        df[acq_datetime_key] = pd.to_datetime(df[acq_datetime_key])
        df["date"] = df[acq_datetime_key].apply(lambda x: pd.Timestamp(x).date())
        df_subset = df[
            (df["date"] == self.acquisition_date)
            & (df["polarization"] == self.polarization)
        ]
        tabs_param = dict()
        complete_frame = True

        # Get the burst offset of each acquisition
        df_subset = df_subset.sort_values(by=acq_datetime_key, ascending=True)
        burst_idx_offs = {}

        # Get acquisition ids (sorted, which due to name patterns sorts by time)
        acquisition_ids = sorted(self.acquisition_bursts.keys())

        for swath in [1, 2, 3]:
            burst_idx_offs[swath] = {}
            total_bursts = 0

            for acq_id in acquisition_ids:
                acq_bursts = self.acquisition_bursts[acq_id][swath]

                burst_idx_offs[swath][acq_id] = total_bursts
                total_bursts += acq_bursts

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            burst_tab = tmpdir.joinpath("burst_tab")

            with open(burst_tab, "w") as fid:
                for swath in [1, 2, 3]:
                    tmp_dict = dict()
                    swath_df = df_subset[df_subset.swath == "IW{}".format(swath)]
                    swath_df = swath_df.sort_values(by=acq_datetime_key, ascending=True)

                    # write the burst numbers to subset from the concatenated swaths
                    start_burst = None
                    end_burst = None

                    for row in swath_df.itertuples():
                        acq_id = Path(row.url).stem

                        missing_bursts = row.missing_primary_bursts.strip("][")
                        if missing_bursts:
                            complete_frame = False

                        burst_nums = [
                            int(i) for i in row.burst_number.strip("][").split(",")
                        ]

                        burst_offs = burst_idx_offs[swath][acq_id]

                        if start_burst is None:
                            start_burst = burst_offs + min(burst_nums)

                        end_burst = burst_offs + max(burst_nums)

                    fid.write(str(start_burst) + " " + str(end_burst) + "\n")
                    tab_names = self.swath_tab_names(swath, self.slc_prefix)
                    tmp_dict["slc"] = tab_names.slc
                    tmp_dict["par"] = tab_names.par
                    tmp_dict["tops_par"] = tab_names.tops_par
                    tabs_param[swath] = tmp_dict

            # write out slc in and out tab files
            sub_slc_in = tmpdir.joinpath("sub_slc_input_tab")
            files_in_slc_in = self._write_tabs(
                sub_slc_in, tab_params=tabs_param, slc_data_dir=os.getcwd()
            )

            sub_slc_out = tmpdir.joinpath("sub_slc_output_tab")
            files_in_slc_out = self._write_tabs(
                sub_slc_out, _id=self.slc_prefix, slc_data_dir=tmpdir
            )

            # run the subset
            slc1_tab_pathname = str(sub_slc_in)
            slc2_tab_pathname = str(sub_slc_out)
            burst_tab_pathname = str(burst_tab)

            pg.SLC_copy_ScanSAR(
                slc1_tab_pathname,
                slc2_tab_pathname,
                burst_tab_pathname,
                const.SLC_DTYPE_FCOMPLEX,
            )

            # replace concatenate slc with burst-subset of concatenated slc
            for swath in [1, 2, 3]:
                tab_names = self.swath_tab_names(swath, self.slc_prefix)
                for item in [tab_names.slc, tab_names.par, tab_names.tops_par]:
                    shutil.move(tmpdir.joinpath(item), item)

            if not complete_frame:
                self.log.info("Frame incomplete, resizing", slc_tab=self.slc_tab, ref_primary_tab=self.ref_primary_tab)

                if self.ref_primary_tab is None:
                    err = (
                        f" ref_primary_tab is None, needs ref_primary_tab "
                        f"to resize incomplete frame for scene {self.scene_date}"
                    )
                    raise ValueError(err)

                self.frame_resize(self.ref_primary_tab, sub_slc_in)

            else:
                self.log.info("Frame complete, no need to resize", slc_tab=self.slc_tab)

    def frame_resize(self, ref_slc_tab: Path, full_slc_tab: Path,) -> None:
        """
        Resizes the full slc to the reference slc.

        :param ref_slc_tab:
            A full path to a reference slc tab file.
        :param full_slc_tab:
            A full path to a slc_tab file to be resized.
        """
        full_slc_tab = Path(full_slc_tab)
        ref_slc_tab = Path(ref_slc_tab)

        # determine the resize burst tab
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            burst_tab = tmpdir.joinpath("burst_tab").as_posix()

            slc1_tab_pathname = str(ref_slc_tab)
            slc2_tab_pathname = str(full_slc_tab)
            burst_tab_pathname = burst_tab

            pg.S1_BURST_tab(
                slc1_tab_pathname, slc2_tab_pathname, burst_tab_pathname,
            )

            # write output in a temp directory
            resize_slc_tab = tmpdir.joinpath("sub_slc_output_tab")
            files_in_resize_tab = self._write_tabs(
                resize_slc_tab, _id=self.slc_prefix, slc_data_dir=tmpdir
            )

            slc1_tab_pathname = str(full_slc_tab)
            slc2_tab_pathname = str(resize_slc_tab)
            burst_tab_pathname = str(burst_tab_pathname)

            pg.SLC_copy_ScanSAR(
                slc1_tab_pathname,
                slc2_tab_pathname,
                burst_tab_pathname,
                const.NOT_PROVIDED,  # output data type; default (same as input)
            )

            # replace full slc with re-sized slc
            for swath in [1, 2, 3]:
                tab_names = self.swath_tab_names(swath, self.slc_prefix)
                for item in [tab_names.slc, tab_names.par, tab_names.tops_par]:
                    shutil.move(tmpdir.joinpath(item), item)

    def burst_images(self):
        """Make a quick look of .png files for each swath and mosiac slc."""

        def _make_png(tab_names):
            _par_vals = pg.ParFile(tab_names.par)
            range_samples = _par_vals.get_value("range_samples", dtype=int, index=0)
            azimuth_lines = _par_vals.get_value("azimuth_lines", dtype=int, index=0)

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir = Path(temp_dir)
                bmp_file = (
                    temp_dir.joinpath("{}".format(tab_names.slc))
                    .with_suffix(".bmp")
                    .as_posix()
                )

                slc_pathname = tab_names.slc
                rasf_pathname = bmp_file

                pg.rasSLC(
                    slc_pathname,
                    range_samples,  # width
                    const.DEFAULT_STARTING_LINE,
                    azimuth_lines,  # nlines
                    50,  # pixavr
                    const.RAS_PIXEL_AVERAGE_AZIMUTH,
                    const.NOT_PROVIDED,  # scale
                    const.NOT_PROVIDED,  # exp
                    const.LEFT_RIGHT_FLIPPING_NORMAL,
                    const.SLC_DTYPE_FCOMPLEX,  # dtype
                    0,  # hdrsz/line header size in bytes, 0 = default
                    rasf_pathname,
                )

                # convert bmp file to png quick look image file
                convert(bmp_file, Path(tab_names.slc).with_suffix(".png"))

        tab_names_list = [
            self.swath_tab_names(swath, self.slc_prefix) for swath in [1, 2, 3]
        ]
        tab_names_list.append(self.slc_tab_names(self.slc_prefix))
        for tab in tab_names_list:
            _make_png(tab)

    def main(
        self,
        write_png: bool = True,
    ):
        """Main method to execute SLC processing sequence need to produce SLC."""
        work_dir = self.output_dir.joinpath(self.scene_date)
        work_dir.mkdir(exist_ok=True)
        with working_directory(work_dir):
            self.read_raw_data()
            self.concatenate()
            self.phase_shift()
            # Note: This is hard-coded to 8, 2 now to match Bash until a final solution
            # is devised...
            self.mosaic_slc(8, 2)
            self.orbits()
            self.frame_subset()

    def main_mosaic(
        self,
        rlks: int,
        alks: int,
        write_png: bool = True,
    ):
        """Main method to execute SLC processing sequence needed to produce SLC mosaic w/ the final rlks/alks."""
        work_dir = self.output_dir.joinpath(self.scene_date)
        work_dir.mkdir(exist_ok=True)

        with working_directory(work_dir):
            # Get slc_prefix/tab based on acquisition date
            _dt = self.read_scene_date()
            self.slc_prefix = "{0:04}{1:02}{2:02}".format(_dt.year, _dt.month, _dt.day)
            self.slc_tab = work_dir / "{}_{}_tab".format(self.slc_prefix, self.polarization)

            # Run the final S1 SLC mosaic (second mosaic on subsetted data w/ final resolution parameters)
            self.mosaic_slc(rlks, alks)

            if write_png:
                self.burst_images()
