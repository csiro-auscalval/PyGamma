#!/usr/bin/env python

from typing import Optional, Union, Tuple, List, Dict
from pathlib import Path
import datetime
import shutil
import json
import re
import os

import pandas as pd

from insar.subprocess_utils import working_directory
from insar.parfile import GammaParFile as ParFile
from insar.gamma.proxy import create_gamma_proxy
from insar.logs import STATUS_LOGGER as LOG
from insar.utils import TemporaryDirectory
from insar.constant import SCENE_DATE_FMT
from insar.process_utils import convert
from insar.paths.slc import SlcPaths
from insar import constant as const
import insar.constant as const


class ProcessSlcException(Exception):
    pass


pg = create_gamma_proxy(ProcessSlcException)

# GA's InSAR team found S1 data before Nov 2015 is of poorer quality for SAR interferometry & more
# likely to create interferogram discontinuities. GAMMA's SLC_phase_shift uses March 2015 though.
# The InSAR team has decided not to use interferometric products before this. See:
# https://github.com/GeoscienceAustralia/PyGamma/pull/157

PHASE_SHIFT_DATE = datetime.date(2015, 3, 10)


def get_slc_safe_files(raw_data_dir: Path, scene_date: str) -> List[Path]:
    """Returns list of .SAFE file paths need to form full SLC for a date."""

    return [item for item in (raw_data_dir / scene_date).iterdir() if item.name.endswith(".SAFE")]


def swath_tab_names(paths: SlcPaths, swath: int, pre_fix: Optional[str] = None) -> Tuple[Path, Path, Path]:
    """Formats slc swath tab file names using swath and pre_fix."""

    # Note: swath - 1 is to convert base-1 indices into base 0 for array indexing
    slc = paths.iw_slc[swath - 1]
    slc_par = paths.iw_slc_par[swath - 1]
    slc_tops_par = paths.iw_slc_tops_par[swath - 1]

    if pre_fix:
        slc = slc.parent / f"{pre_fix}_{slc.name}"
        slc_par = slc_par.parent / f"{pre_fix}_{slc_par.name}"
        slc_tops_par = slc_tops_par.parent / f"{pre_fix}_{slc_tops_par.name}"

    return (Path(slc), Path(slc_par), Path(slc_tops_par))


def write_tabs(
    paths: SlcPaths,
    slc_tab_file: Path,
    tab_params: Optional[Dict] = None,
    ident: Optional[str] = None,
    slc_data_dir: Optional[Path] = None,
) -> List[Tuple[Path, Path, Path]]:
    """
    Writes tab (ascii) files needed in process_s1_slc.
    :param paths:
        Slc Paths.
    :param slc_tab_file:
        A full path of an slc tab file.
    :param tab_params:
        An Optional tab params to write SLC tab file content.
    :param ident:
        An Optional parameter to form SLC tab names if tab_params is None.
    :param slc_data_dir:
        An Optional parameter to prepend (slc, par, tops_par) file names to
        form full path.
    """
    files_in_slc_tabs: List[Tuple[Path, Path, Path]] = []

    if slc_tab_file.exists():
        LOG.info(f"SLC tab file {slc_tab_file} exists; skipping writing of parameters")
        return files_in_slc_tabs

    LOG.debug(f"Generating {slc_tab_file}")

    with open(slc_tab_file, "w") as fid:
        for swath in [1, 2, 3]:
            if tab_params is None:
                LOG.debug(f"tab_params=None using swath_tab_names(...) for swath={swath}")
                (slc, par, tops_par) = swath_tab_names(paths, swath, ident)
            else:
                slc = Path(tab_params[swath]["slc"])
                par = Path(tab_params[swath]["par"])
                tops_par = Path(tab_params[swath]["tops_par"])

            if slc_data_dir is not None:
                LOG.debug(f"When writing tab file using slc_data_dir={slc_data_dir} as output path")
                slc = Path(slc_data_dir) / slc.name
                par = Path(slc_data_dir) / par.name
                tops_par = Path(slc_data_dir) / tops_par.name

            LOG.debug(f"tops_par={tops_par} for swath={swath}")

            fid.write(f"{slc} {par} {tops_par}\n")

            files_in_slc_tabs.append((Path(slc), Path(par), Path(tops_par)))

    return files_in_slc_tabs


def read_raw_data(
    paths: SlcPaths, raw_data_dir: Path, polarisation: str
) -> Tuple[
    Dict[str, Dict[str, str]],  # metadata
    Dict[str, Dict[int, Dict[str, Union[datetime.datetime, Path]]]],  # concat_tabs
    Dict[str, Dict[int, int]],  # acquisition_bursts
    List[Path], # temp_slc
]:
    """
    Reads Sentinel-1 SLC data and generate SLC parameter file.
    """

    raw_files_patterns: Dict[str, str] = {
        "data": "*measurement/s1*-iw{swath}-slc-{polarisation}*.tiff",
        "annotation": "*annotation/s1*-iw{swath}-slc-{polarisation}*.xml",
        "calibration": "*annotation/calibration/calibration-s1*-iw{swath}-slc-{polarisation}*.xml",
        "noise": "*annotation/calibration/noise-s1*-iw{swath}-slc-{polarisation}*.xml",
        "orbit_file": "*.EOF",
    }

    acquisition_bursts: Dict[str, Dict[int, int]] = {}
    concat_tabs: Dict[str, Dict[int, Dict[str, Union[datetime.datetime, Path]]]] = {}
    metadata: Dict[str, Dict[str, str]] = {"slc": {}}

    temp_slc: List[Path] = []

    for save_file in get_slc_safe_files(raw_data_dir, paths.date):

        ident = save_file.stem
        concat_tabs[ident] = {}

        # _id = basename of .SAFE folder, e.g.
        # S1A_IW_SLC__1SDV_20180103T191741_20180103T191808_019994_0220EE_1A2D

        # Identify source data URL
        src_url_fn = Path(save_file) / "src_url"

        # - if this is raw_data we've extracted from a source archive, a src_url file will exist
        if src_url_fn.exists():
            src_url = Path(src_url_fn.read_text())

        # - otherwise it's a source data directory that's been provided by the user
        else:
            src_url = Path(save_file).absolute()

        acquisition_bursts[ident] = {}

        metadata[ident] = {"src_url": str(src_url)}

        # add start time to dict
        dt_start = re.findall("[0-9]{8}T[0-9]{6}", ident)[0]
        start_datetime = datetime.datetime.strptime(dt_start, "%Y%m%dT%H%M%S")

        for swath in [1, 2, 3]:

            (tab_slc, tab_par, tab_tops) = swath_tab_names(paths, swath, ident)

            raw_files: List[Optional[Path]] = []

            for key, val in raw_files_patterns.items():
                pattern = val.format(swath=swath, polarisation=polarisation.lower())
                matched_files = list(save_file.glob(pattern))

                if not matched_files:
                    if key == "orbit_file":
                        raw_files.append(None)
                        continue
                    raise FileNotFoundError(f"Failed to find required S1 {key} files")
                elif len(matched_files) != 1:
                    raise ProcessSlcException(
                        f"Invalid ESA SAFE structure, more than one {key} file found for IW{swath}"
                    )

                raw_files.append(Path(matched_files[0]).absolute())

            concat_tabs[ident][swath] = {}
            concat_tabs[ident][swath]["datetime"] = start_datetime
            concat_tabs[ident][swath]["slc"] = tab_slc
            concat_tabs[ident][swath]["par"] = tab_par
            concat_tabs[ident][swath]["tops_par"] = tab_tops

            geotiff_pathname = raw_files[0]
            calibration_xml_pathname = raw_files[2]
            noise_xml_pathname = raw_files[3]

            if raw_files[1] is not None:
                annotation_xml_pathname = raw_files[1]
            else:
                raise FileNotFoundError(f"Failed to find annotation XML file in {save_file}")

            # par_S1_SLC creates the following three output files:
            # 1. tab_par (*.slc.par)
            # 2. slc_pathname (*.slc), and;
            # 3. tops_par_pathname (*slc.TOPS_par).

            LOG.debug(f"Generating {tab_par}, {tab_slc}, and {tab_tops}")

            pg.par_S1_SLC(
                geotiff_pathname,
                annotation_xml_pathname,
                calibration_xml_pathname,
                noise_xml_pathname,
                tab_par,
                tab_slc,
                tab_tops,
                const.SLC_DTYPE_FCOMPLEX,
                const.NOT_PROVIDED,
                const.NOT_PROVIDED,
            )

            # assign orbit file name.  Note: repeating the assignment is harmless
            # (all acquisitions from same date have same orbit file)

            orbit_file = raw_files[4]

            # store the file names of *slc, *.slc.par and
            # *.slc.TOPS_par so that they can to be removed later

            for item in [tab_slc, tab_par, tab_tops]:
                temp_slc.append(item)

            # Use acquisition metadata for this swath to count how many bursts it contains

            num_subswath_burst = 0

            xml_pattern = raw_files_patterns["annotation"]
            xml_pattern = xml_pattern.format(swath=swath, polarisation=polarisation.lower())

            for xml_file in save_file.glob(xml_pattern):
                _, cout, _ = pg.S1_burstloc(xml_file)
                num_bursts = sum([line.startswith("Burst") for line in cout])
                LOG.debug(f"nbursts: {num_bursts} from: {xml_file}")
                num_subswath_burst += num_bursts

            acquisition_bursts[ident][swath] = num_subswath_burst
            metadata[ident][f"IW{swath}_bursts"] = str(num_subswath_burst)

    metadata["slc"]["orbit_url"] = str(orbit_file)

    for k in metadata["slc"].keys():
        v = metadata["slc"][k]
        if isinstance(v, Path):
            metadata["slc"][k] = str(v)

    # Write metadata used to produce this SLC
    metadata_path = paths.dir / f"metadata_{polarisation}.json"
    with metadata_path.open("w") as file:
        json.dump(metadata, file, indent=2)

    return (metadata, concat_tabs, acquisition_bursts, temp_slc)


def concatenate(paths: SlcPaths, slc_tabs_params) -> None:
    """Concatenate multi-scenes to create new frame."""

    with TemporaryDirectory(delete=const.DISCARD_TEMP_FILES) as tmpdir:
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

        first_tabs, *remaining_tabs = sorted(slc_tabs_params.items(), key=lambda x: x[1][1]["datetime"])
        _, initial_dict = first_tabs
        dt = initial_dict[1]["datetime"]

        if not remaining_tabs:

            # There is only one acquisition for this day, hence
            # remaining_tabs is None, and there is no need to
            # concatenate files using pg.SLC_cat_ScanSAR.
            # Instead, renaming the *.slc, *.slc.par and
            # *.slc.TOPS_par files created from pg.par_S1_SLC.

            LOG.debug(f"Only one acquisition for {dt}, just renaming slc, slc.par, slc.TOPS_par files")

            for swath in [1, 2, 3]:
                (tab_slc, tab_par, tab_tops) = swath_tab_names(paths, swath)

                (initial_dict[swath]["slc"]).rename(tab_slc)
                (initial_dict[swath]["par"]).rename(tab_par)
                (initial_dict[swath]["tops_par"]).rename(tab_tops)

            write_tabs(paths, paths.slc_tab, slc_data_dir=Path(os.getcwd()))

        else:
            # multiple SLC acquisitions for this day. Use
            # pg.SLC_cat_ScanSAR to concatenate these
            # acquisitions into single files

            LOG.debug(f"Multiple acquisitions for {dt}, concatenating into a single file")

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
                    # we don't use a custom prefix / use standard naming
                    tab_slc_prefix = None
                else:
                    # it is crucial that slc_prefix is different
                    # for every iteration, otherwise SLC_cat_ScanSAR
                    # will attempt to overwrite the concatenated
                    # files which cause SLC_cat_ScanSAR to
                    # raise errors and then exit.
                    tab_slc_prefix = "{0:04}{1:02}{2:02}{3:02}{4:02}{5:02}_ix{6}".format(
                        dt.year,
                        dt.month,
                        dt.day,
                        dt.hour,
                        dt.minute,
                        dt.second,
                        idx,
                    )

                # create slc_tab_ifile1 only at the beginning
                if slc_tab_ifile1 is None:
                    slc_tab_ifile1 = tmpdir / f"slc_tab_input1_{idx}.txt"
                    files_in_slc_tab1.append(
                        write_tabs(
                            paths,
                            slc_tab_ifile1,
                            tab_params=initial_dict,
                            slc_data_dir=Path(os.getcwd()),
                        )
                    )

                # create slc_tab_ifile2
                slc_tab_ifile2 = tmpdir.joinpath(f"slc_tab_input2_{idx}.txt")
                files_in_slc_tab2.append(
                    write_tabs(
                        paths,
                        slc_tab_ifile2,
                        tab_params=_remaining_dict_idx,
                        slc_data_dir=Path(os.getcwd()),
                    )
                )

                # create slc_merge_tab_ofile (merge tab)
                slc_merge_tab_ofile = tmpdir / f"slc_merged_tab_{idx}.txt"

                files_in_slc_tab3.append(
                    write_tabs(paths, slc_merge_tab_ofile, ident=tab_slc_prefix, slc_data_dir=Path(os.getcwd()))
                )

                # concat sequential ScanSAR burst SLC images
                tab_input1_path = slc_tab_ifile1
                tab_input2_path = slc_tab_ifile2

                slc_merged_tabs_list.append(slc_merge_tab_ofile)

                # SLC_cat_ScanSAR will perform concatenation. Here,
                # data from slc_tab_ifile2 are appended into
                # slc_tab_ifile1, with the merged output placed
                # into the files specified inside slc_merge_tab_ofile.
                #
                # At the end of the first iteration,
                #   tab_input1_path = tab_output_path

                LOG.debug(f"Concatenating bursts into {slc_merge_tab_ofile}")

                pg.SLC_cat_ScanSAR(
                    tab_input1_path,
                    tab_input2_path,
                    slc_merge_tab_ofile,
                )

                # assign slc_merge_tab_ofile to slc_tab_ifile1
                # to perform series of concatenation

                ## to conserve memory, delete temporary concatenated
                ## files from the previous iteration. This code will
                ## keep concatenated files from the last iteration.
                #if idx > 0:
                #    # get temp. files of previus iterations
                #    for _swath_mfile_list in files_in_slc_tab3[idx - 1]:
                #        for _mfile in _swath_mfile_list:
                #            os.remove(_mfile)

            # set the slc_tab file name
            #shutil.move(slc_merge_tab_ofile, paths.slc_tab)

                LOG.debug(f"Moving {slc_merge_tab_ofile} to {paths.slc_tab}")
                slc_merge_tab_ofile.rename(paths.slc_tab)
        # end-else
    # end-with


def phase_shift(paths: SlcPaths, swath: int = 1) -> None:
    """Perform phase shift correction.

    Phase shift-correction is needed for Sentinel-1 IW1 swath data collected
    before 15th March, 2015.

    :param swath:
        Optional swath number to perform phase shift on. Otherwise, IW-1 is
        corrected for the scenes acquired before 15th March, 2015.
    """

    if datetime.datetime.strptime(paths.date, SCENE_DATE_FMT).date() >= PHASE_SHIFT_DATE:
        return

    with TemporaryDirectory(delete=const.DISCARD_TEMP_FILES) as tmpdir:
        tmpdir = Path(tmpdir)
        slc_dir = Path(os.getcwd())
        (tab_slc, tab_par, tab_tops) = swath_tab_names(paths, swath)

        with working_directory(tmpdir):
            slc_1_pathname = Path(slc_dir.joinpath(tab_slc))
            slc_1_par_pathname = Path(slc_dir.joinpath(tab_par))
            slc_2_pathname = tab_slc
            slc_2_par_pathname = tab_par

            pg.SLC_phase_shift(
                slc_1_pathname,
                slc_1_par_pathname,
                slc_2_pathname,
                slc_2_par_pathname,
                -1.25,  # ph_shift: phase shift to add to SLC phase (radians)
            )

            # replace iw1 slc with phase corrected files
            shutil.move(tmpdir.joinpath(tab_slc), slc_dir.joinpath(tab_slc))
            shutil.move(tmpdir.joinpath(tab_par), slc_dir.joinpath(tab_par))


def frame_subset(
    paths: SlcPaths,
    polarisation: str,
    acquisition_bursts,
    burst_data: Path,
    ref_primary_tab: Optional[Path] = None,
) -> None:
    """Subset frames to form full SLC frame of a vector file.

    Full Frame is formed after sub-setting burst data listed in
    the burst_data needed to form a full frame.
    """

    acq_datetime_key = "acquisition_datetime"

    scene_date = datetime.datetime.strptime(paths.date, SCENE_DATE_FMT).date()

    LOG.info(f"Subset frames to form full SLC frame of a vector file for {scene_date}")

    df = pd.read_csv(burst_data, index_col=0)

    df[acq_datetime_key] = pd.to_datetime(df[acq_datetime_key])
    df["date"] = df[acq_datetime_key].apply(lambda x: pd.Timestamp(x).date())
    df_subset = df[(df["date"] == scene_date) & (df["polarization"] == polarisation)]

    tabs_param = dict()
    complete_frame = True

    LOG.debug("Get the burst offset of each acquisition")

    df_subset = df_subset.sort_values(by=acq_datetime_key, ascending=True)
    burst_idx_offs = {}

    # Get acquisition ids (sorted, which due to name patterns sorts by time)
    acquisition_ids = sorted(acquisition_bursts.keys())

    for swath in [1, 2, 3]:
        burst_idx_offs[swath] = {}
        total_bursts = 0

        for acq_id in acquisition_ids:
            acq_bursts = acquisition_bursts[acq_id][swath]

            burst_idx_offs[swath][acq_id] = total_bursts
            total_bursts += acq_bursts

    with TemporaryDirectory(delete=const.DISCARD_TEMP_FILES) as tmpdir:
        tmpdir = Path(tmpdir)
        burst_tab = tmpdir.joinpath("burst_tab")

        LOG.debug(f"Creating burst_tab file {burst_tab}")

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

                    burst_nums = [int(i) for i in row.burst_number.strip("][").split(",")]

                    burst_offs = burst_idx_offs[swath][acq_id]

                    if start_burst is None:
                        start_burst = burst_offs + min(burst_nums)

                    end_burst = burst_offs + max(burst_nums)

                fid.write(str(start_burst) + " " + str(end_burst) + "\n")

                (tab_slc, tab_par, tab_tops) = swath_tab_names(paths, swath)

                tmp_dict["slc"] = tab_slc
                tmp_dict["par"] = tab_par
                tmp_dict["tops_par"] = tab_tops

                tabs_param[swath] = tmp_dict

        # write out slc in and out tab files

        sub_slc_in = tmpdir / "sub_slc_input_tab"
        write_tabs(paths, sub_slc_in, tab_params=tabs_param, slc_data_dir=Path(os.getcwd()))

        sub_slc_out = tmpdir / "sub_slc_output_tab"
        write_tabs(paths, sub_slc_out, slc_data_dir=tmpdir)

        # run the subset
        slc1_tab_pathname = Path(sub_slc_in)
        slc2_tab_pathname = Path(sub_slc_out)
        burst_tab_pathname = Path(burst_tab)

        # BREAKS HERE, out/T45DF39S/SLC/20190208/20190208_VV_IW1.slc.TOPS_par overwritten

        pg.SLC_copy_ScanSAR(
            slc1_tab_pathname,
            slc2_tab_pathname,
            burst_tab_pathname,
            const.SLC_DTYPE_FCOMPLEX,
        )

        for swath in [1, 2, 3]:

            LOG.debug(f"Replacing concatenate slc with burst-subset of concatenated slc for swath={swath}")

            tab_files = swath_tab_names(paths, swath)
            for item in tab_files:
                LOG.debug(f"Moving {tmpdir/item.name} to {item}")
                (tmpdir / item.name).rename(item)

        if not complete_frame:

            LOG.info("Frame incomplete, resizing", slc_tab=paths.slc_tab, ref_primary_tab=ref_primary_tab)

            if ref_primary_tab is None:
                err = (
                    f" ref_primary_tab is None, needs ref_primary_tab "
                    f"to resize incomplete frame for scene {paths.date}"
                )
                raise ValueError(err)

            frame_resize(paths, ref_primary_tab, sub_slc_in)

        else:
            LOG.info("Frame complete, no need to resize", slc_tab=paths.slc_tab)


def frame_resize(
    paths: SlcPaths,
    ref_slc_tab: Path,
    full_slc_tab: Path,
) -> None:
    """
    Resizes the full slc to the reference slc.

    :param ref_slc_tab:
        A full path to a reference slc tab file.
    :param full_slc_tab:
        A full path to a slc_tab file to be resized.
    """
    LOG.info("Resizing the full SLC to the reference SLC")

    # determine the resize burst tab

    with TemporaryDirectory(delete=const.DISCARD_TEMP_FILES) as tmpdir:
        tmpdir = Path(tmpdir)

        slc1_tab_pathname = Path(ref_slc_tab)
        slc2_tab_pathname = Path(full_slc_tab)
        burst_tab_pathname = (tmpdir / "burst_tab").absolute()

        pg.S1_BURST_tab(
            slc1_tab_pathname,
            slc2_tab_pathname,
            burst_tab_pathname,
        )

        # write output in a temp directory

        resize_slc_tab = tmpdir / "sub_slc_output_tab"
        write_tabs(paths, resize_slc_tab, slc_data_dir=tmpdir)

        slc1_tab_pathname = Path(full_slc_tab)
        slc2_tab_pathname = Path(resize_slc_tab)
        burst_tab_pathname = Path(burst_tab_pathname)

        pg.SLC_copy_ScanSAR(
            slc1_tab_pathname,
            slc2_tab_pathname,
            burst_tab_pathname,
            const.NOT_PROVIDED,
        )

        # replace full slc with re-sized slc

        for swath in [1, 2, 3]:
            tab_files = swath_tab_names(paths, swath)
            for item in tab_files:
                LOG.debug(f"Replacing full SLC with re-sized SLC: {item}")
                shutil.move(tmpdir.joinpath(item), item)


def burst_images(paths: SlcPaths):
    """Make a quick look of .png files for each swath and mosaic slc."""

    def _make_png(tab_slc, tab_par, tab_tops):
        _par_vals = ParFile(tab_par)
        range_samples = _par_vals.get_value("range_samples", dtype=int, index=0)
        azimuth_lines = _par_vals.get_value("azimuth_lines", dtype=int, index=0)

        with TemporaryDirectory(delete=const.DISCARD_TEMP_FILES) as temp_dir:
            temp_dir = Path(temp_dir)
            bmp_file = temp_dir / tab_slc.with_suffix(".bmp")

            slc_pathname = tab_slc

            LOG.debug(f"Making a BMP file of {slc_pathname} as {bmp_file}")

            pg.rasSLC(
                slc_pathname,
                range_samples,
                const.DEFAULT_STARTING_LINE,
                azimuth_lines,
                const.RAS_PIXEL_AVERAGE_RANGE,
                const.RAS_PIXEL_AVERAGE_AZIMUTH,
                const.RAS_PH_SCALE,
                const.RAS_EXP,
                bmp_file,
                const.SLC_DTYPE_FCOMPLEX,
            )

            LOG.debug(f"Converting BMP file {bmp_file} to PNG ")
            convert(bmp_file, bmp_file.with_suffix(".png"))

    tab_names_list = [swath_tab_names(paths, swath) for swath in [1, 2, 3]]
    tab_names_list.append((Path(paths.slc), Path(paths.slc_par), Path(paths.slc_tops_par)))

    for tab in tab_names_list:
        _make_png(*tab)


def process_s1_slc(
    paths: SlcPaths, polarisation: str, raw_data_dir: Path, burst_data: Path, ref_primary_tab: Optional[Path] = None
) -> None:
    """
    Process raw S1 .SAFE IW swath data to produce a singular mosaiced SLC for a scene date.

    A full SLC image is created using Interferometric-Wide (IW) swath data as an input.
    The three sub-swaths (IW1, IW2, IW3) are mosaiced into a single SLC and subsets SLC
    by bursts after full SLC creation to only include bursts relevant to our stack extent.

    :param paths:
        The SlcPaths that we want to process / produce.
    :param raw_data_dir:
        A full path to a raw data_dir that contains SLC SAFE files.
    :param polarisation:
        A polarisation of an SLC file to be used [eg: 'VV', 'VH', 'HH', or 'HV]
    :param burst_data:
        A full path to a csv file containing burst information needed
        to subset to form full SLC.
    param ref_primary_tab:
        An Optional full path to a reference primary slc tab file.
    """

    LOG.debug(f"Running process_s1_slc(...)")

    paths.dir.mkdir(parents=True, exist_ok=True)

    with working_directory(paths.dir):
        LOG.debug(f"Read the raw .SAFE data for each acquisition")

        slc_tab_params: Dict[str, Dict[int, Dict[str, Union[datetime.datetime, Path]]]]

        metadata, slc_tabs_params, acquisition_bursts, temps = read_raw_data(paths, raw_data_dir, polarisation)

        LOG.debug(f"Concatenate bursts into one whole-of-date SLC for each subswath")

        concatenate(paths, slc_tabs_params)

        LOG.debug(f"Phase shift correction for earlier datasets")

        phase_shift(paths)

        LOG.debug(f"Mosaic the subswaths into a single SLC for the whole date {paths.slc_par}")

        pg.SLC_mosaic_ScanSAR(
            paths.slc_tab,
            paths.slc,
            paths.slc_par,
            const.SLC_MOSAIC_RANGE_LOOKS,
            const.SLC_MOSAIC_AZIMUTH_LOOKS,
            None,
            None,
        )

        # If an orbit file exists, extract orbital state vectors into the
        # date's SLC .par (overriding embedded orbital state vectors)

        orbit_file = Path(metadata["slc"]["orbit_url"])

        if not orbit_file:
            LOG.warning("No orbit file for this scene exists")
        else:
            pg.S1_OPOD_vec(
                paths.slc_par,
                orbit_file,
            )

        LOG.debug(
            f"Subset the bursts in the final SLC to only include acquisition bursts "
            f"which intersect our scene (throwing away those that fall outside"
        )

        frame_subset(paths, polarisation, acquisition_bursts, burst_data, ref_primary_tab)

        # clean up the temporary slc files after clean up
        # for fp in temps:
        #    LOG.debug(f"Removing temporary file: {fp}")
        #    os.remove(fp)


def process_s1_slc_mosaic(
    paths: SlcPaths,
    range_looks: int = 12,
    azimuth_looks: int = 2,
    write_png: bool = True,
) -> None:
    """
    Produces the mosaic of Sentinel-1 TOPS burst SLC data for a specified scene date.

    :param range_looks:
        An Optional range look value. Otherwise default rlks is used.
    :param azimuth_looks:
        An Optional azimuth look value. Otherwise default alks is used.
    """

    with working_directory(paths.dir):

        LOG.debug(
            f"SLC mosaicing using rlks={range_looks} and "
            f"alks={azimuth_looks} and paths: {paths.slc_tab} "
            f"{paths.slc} {paths.slc_par}"
        )

        # These files already exist, removing before overwritting them

        paths.slc.unlink()
        paths.slc_par.unlink()

        pg.SLC_mosaic_ScanSAR(paths.slc_tab, paths.slc, paths.slc_par, range_looks, azimuth_looks)

        if write_png:
            LOG.debug("Writing burst images to PNG")
            burst_images(paths)
