#!/usr/bin/env python

import simplekml
import os
import re
import yaml
import uuid
import shutil
import fnmatch
import tempfile
import datetime
import structlog
import shapely.wkt
import xml.etree.ElementTree as etree
import zipfile as zf
import geopandas as gpd
import pandas as pd
import numpy as np

from io import BytesIO
from os.path import join as pjoin
from pathlib import Path
from typing import Dict, List, Optional, Type, Union
from shapely.ops import cascaded_union  # required for select_bursts_in_vector()
from shapely.geometry import MultiPolygon, Polygon, box
from spatialist import Vector, sqlite3, sqlite_setup

from insar.xml_util import getNamespaces
from insar.gamma.proxy import create_gamma_proxy

_LOG = structlog.get_logger("insar")

class SlcException(Exception):
    pass

pg = create_gamma_proxy(SlcException)


class SlcMetadata:
    """
    Metadata extraction class to scrap slc metadata from a sentinel-1 slc scene.
    """

    def __init__(self, scene: Path,) -> None:
        """
        Extracts metadata from a sentinel-1 SLC.

        SLC metadata are extracted from a `manifest safe' file in SLC safe folder
        and IW SLC burst information are also extracted from annotations/xml files
        using GAMMA SOFTWARE's sentinel-1 debursting program.

        :param scene:
            A full path to a SLC save folder.
        """
        self.scene = os.path.realpath(scene)
        self.pattern = (
            r"^(?P<sensor>S1[AB])_"
            r"(?P<beam>S1|S2|S3|S4|S5|S6|IW|EW|WV|EN|N1|N2|N3|N4|N5|N6|IM)_"
            r"(?P<product>SLC|GRD|OCN)(?P<resolution>F|H|M|_)_"
            r"(?P<product_level>1|2)"
            r"(?P<category>S|A)"
            r"(?P<polarisation>SH|SV|DH|DV|VV|HH|HV|VH)_"
            r"(?P<start_date>[0-9]{8}T[0-9]{6})_"
            r"(?P<stop_date>[0-9]{8}T[0-9]{6})_"
            r"(?P<orbitNumber>[0-9]{6})_"
            r"(?P<dataTakeID>[0-9A-F]{6})_"
            r"(?P<productIdentifier>[0-9A-F]{4})"
            r".zip"
        )

        self.pattern_ds = (
            r"^s1[ab]-"
            r"(?P<swath>s[1-6]|iw[1-3]?|ew[1-5]?|wv[1-2]|n[1-6])-"
            r"(?P<product>slc|grd|ocn)-"
            r"(?P<pol>hh|hv|vv|vh)-"
            r"(?P<start>[0-9]{8}t[0-9]{6})-"
            r"(?P<stop>[0-9]{8}t[0-9]{6})-"
            r"(?:[0-9]{6})-(?:[0-9a-f]{6})-"
            r"(?P<id>[0-9]{3})"
            r"\.xml$"
        )
        self.archive_files = None

        match = re.match(self.pattern, os.path.basename(self.scene))

        if not match:
            _LOG.warning(
                "filename pattern mismatch", pattern=self.pattern, scene=self.scene
            )
        else:
            _LOG.info("filename pattern match", **match.groupdict())

        # taken from /insar/s1_slc_metadata.py, which are used in S1DataDownload
        self.date_fmt = "%Y%m%d"
        self.dt_fmt_1 = "%Y-%m-%d %H:%M:%S.%f"
        self.dt_fmt_2 = "%Y%m%dT%H%M%S"
        self.dt_fmt_3 = "%Y-%m-%dT%H:%M:%S.%f"  # format in the manifest.safe file

        # added self.manifest_file as it is required for S1DataDownload
        self.manifest = "manifest.safe"  # only used for self.manifest_file_list
        manifest_file_list = self.find_archive_files(self.manifest)
        self.manifest_file = manifest_file_list[0]

        # extract metadata that's required for S1DataDownload
        req_metadata_dict = self.get_metadata_essentials(self.manifest_file)

        # add dictionary items and values from req_metadata_dict to self
        # so that they are accessible from S1DataDownload
        for item in req_metadata_dict:
            setattr(self, item, req_metadata_dict[item])

    def get_metadata(self):
        """
        Consolidates metadata of manifest safe file and annotation/swath
        xmls from a slc archive. get_metadata() is used by the function,
        generate_slc_metadata() in /insar/meta_data/s1_gridding_utils.py
        to extract metadata which is either directly archived to a db
        file or dumped into a yaml file.
        """

        metadata = dict()
        try:
            # extract slc acquisition info from manifest.safe file
            metadata["properties"] = self.metadata_manifest_safe(self.manifest_file)
        except ValueError as err:
            raise ValueError(err)

        annotation_xmls = self.find_archive_files(self.pattern_ds)
        assert len(annotation_xmls) > 0

        metadata["measurements"] = dict()
        for xml_file in annotation_xmls:
            xml_pbase = os.path.basename(xml_file)
            # use pygamma to extract burst/swath info from xml:
            metadata["measurements"][xml_pbase] = self.metadata_swath(xml_file)

        metadata["id"] = str(uuid.uuid4())
        metadata["product"] = dict()

        # TODO infer names from metadata after naming convections is discussed
        metadata["product"]["name"] = "ESA_S1_SLC"
        metadata["product"]["url"] = self.scene

        return metadata

    def format_datetime_string(
        self, input_dt: str, in_format: str, out_format: str,
    ) -> str:
        """
        converts a date and time string from an input to an output format

        Parameters
        ----------
        input_dt: str
            date and time string

        in_format: str
            datetime format directive of input_dt, e.g.
            if input_dt = "2018-01-06T19:38:08.036130" then
            in_format = "%Y-%m-%dT%H:%M:%S.%f"

        out_format: str
            datetime format directive of output date & time string
            e.g. out_format = "%Y-%m-%d %H:%M:%S.%f"

        Returns
        -------
            date and time string with a format specified by out_format

        Example
        -------
        out_datetime = format_datetime_string(
            "2018-01-06T19:38:08.036130",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S.%f"
            )

        out_datetime = "2018-01-06 19:38:08.036130"
        """
        return datetime.datetime.strptime(input_dt, in_format).strftime(out_format)

    def get_metadata_essentials(self, manifest_file: Path,) -> Dict:
        """
        Extracts essential metadata required for S1DataDownload from a
        manifest safe file. Without this function, one would need to
        load the entire metadata from metadata_manifest_safe() and then
        keep only keep a few items.

        Parameters
        ----------
        manifest_file: Path
            path to manifest.safe file, e.g.
            S1A_IW_SLC__1SDV_20180106T193808_20180106T193834_020038_02224B_8674.SAFE/manifest.safe

        Return
        ------
            Dictionary containing essential items & values from
            the manifest.safe file
        """
        req_meta = dict()
        manifest_obj = self.extract_archive_BytesIO(target_file=manifest_file)

        # Items "acquisition_start_time", "acquisition_stop_time" &
        # "sensor" are also added to a dict in metadata_manifest_safe.
        # TODO: pursue alternative approaches to simplify this code.
        with manifest_obj as obj:
            manifest = obj.getvalue()
            namespaces = getNamespaces(manifest)
            tree = etree.fromstring(manifest)

            req_meta["sensor"] = (
                tree.find(".//safe:familyName", namespaces).text.replace("ENTINEL-", "")
                + tree.find(".//safe:number", namespaces).text
            )

            req_meta["acquisition_start_time"] = self.format_datetime_string(
                tree.find(".//safe:startTime", namespaces).text,
                self.dt_fmt_3,
                self.dt_fmt_1,
            )

            req_meta["acquisition_stop_time"] = self.format_datetime_string(
                tree.find(".//safe:stopTime", namespaces).text,
                self.dt_fmt_3,
                self.dt_fmt_1,
            )

        return req_meta

    def metadata_manifest_safe(self, manifest_file: Path,) -> Dict:
        """
        Extracts metadata from a manifest safe file.

        Parameters
        ----------
        manifest_file: Path
            A full path to a manifest safe file, e.g.
            S1A_IW_SLC__1SDV_20180106T193808_20180106T193834_020038_02224B_8674.SAFE/manifest.safe

        Return
        ------
            Dictionary containing relevant items & values from
            the manifest.safe file
        """

        manifest_obj = self.extract_archive_BytesIO(target_file=manifest_file)
        meta = dict()
        with manifest_obj as obj:
            manifest = obj.getvalue()
            namespaces = getNamespaces(manifest)
            tree = etree.fromstring(manifest)
            meta["acquisition_mode"] = tree.find(".//s1sarl1:mode", namespaces).text

            meta["acquisition_start_time"] = self.format_datetime_string(
                tree.find(".//safe:startTime", namespaces).text,
                self.dt_fmt_3,
                self.dt_fmt_1,
            )

            meta["acquisition_stop_time"] = self.format_datetime_string(
                tree.find(".//safe:stopTime", namespaces).text,
                self.dt_fmt_3,
                self.dt_fmt_1,
            )

            # "coordinates" contains the lat/lon bounds of the S1
            # acquisition extent. The format is such that:
            # <gml:coordinates>
            #     Lat1,Lon1  Lat2,Lon2 Lat3,Lon3 Lat4,Lon4
            # </gml:coordinates>
            # "coordinates" will eventually be stored in
            # slc_metadata.slc_extent of a db file. To be
            # consistent with burst_metadata.burst_extent
            # which has the following format:
            #     [lon1, lat1], ..., [lonN, latN]
            # we will be switching the lat/lon around
            meta["coordinates"] = [
                list([float(y) for y in x.split(",")[::-1]])
                for x in tree.find(".//gml:coordinates", namespaces).text.split()
            ]

            meta["crs"] = "epsg:{}".format(
                tree.find(".//safe:footPrint", namespaces).attrib["srsName"].split("#")[1]
            )
            meta["orbit"] = tree.find(".//s1:pass", namespaces).text[0]

            meta["orbitNumber_abs"] = int(
                tree.find('.//safe:orbitNumber[@type="start"]', namespaces).text
            )
            meta["orbitNumber_rel"] = int(
                tree.find('.//safe:relativeOrbitNumber[@type="start"]', namespaces).text
            )
            meta["cycleNumber"] = int(tree.find(".//safe:cycleNumber", namespaces).text)
            meta["frameNumber"] = int(
                tree.find(".//s1sarl1:missionDataTakeID", namespaces).text
            )
            meta["orbitNumbers_abs"] = dict(
                [
                    (
                        x,
                        int(
                            tree.find(
                                './/safe:orbitNumber[@type="{0}"]'.format(x), namespaces
                            ).text
                        ),
                    )
                    for x in ["start", "stop"]
                ]
            )
            meta["orbitNumbers_rel"] = dict(
                [
                    (
                        x,
                        int(
                            tree.find(
                                './/safe:relativeOrbitNumber[@type="{0}"]'.format(x),
                                namespaces,
                            ).text
                        ),
                    )
                    for x in ["start", "stop"]
                ]
            )
            meta["polarizations"] = [
                x.text
                for x in tree.findall(
                    ".//s1sarl1:transmitterReceiverPolarisation", namespaces
                )
            ]
            meta["product"] = tree.find(".//s1sarl1:productType", namespaces).text
            meta["category"] = tree.find(".//s1sarl1:productClass", namespaces).text
            meta["sensor"] = (
                tree.find(".//safe:familyName", namespaces).text.replace("ENTINEL-", "")
                + tree.find(".//safe:number", namespaces).text
            )
            meta["IPF_version"] = float(
                tree.find(".//safe:software", namespaces).attrib["version"]
            )
            meta["sliceNumber"] = int(
                tree.find(".//s1sarl1:sliceNumber", namespaces).text
            )
            meta["totalSlices"] = int(
                tree.find(".//s1sarl1:totalSlices", namespaces).text
            )

        return meta

    def metadata_swath(self, xml_file: Path,) -> Dict:
        """
        Extracts swath and bursts information from a xml file.

        Parameters
        ----------
        xml_file: Path
            A full path to xml_file.

        Return
        ------
            Dictionary containing relevant items & values of
            individual bursts extracted from xml files using
            pygamma
        """

        swath_meta = dict()
        swath_obj = self.extract_archive_BytesIO(target_file=xml_file)

        def _metadata_burst(xml_path):
            def _parse_s1_burstloc(gamma_output_list):
                burst_info = dict()
                for line in gamma_output_list:
                    if line.startswith("Burst"):
                        split_line = line.split()
                        temp_dict = dict()
                        temp_dict["burst_num"] = int(split_line[2])
                        temp_dict["rel_orbit"] = int(split_line[3])
                        temp_dict["swath"] = split_line[4]
                        temp_dict["polarization"] = split_line[5]
                        temp_dict["azimuth_time"] = float(split_line[6])
                        temp_dict["angle"] = float(split_line[7])
                        temp_dict["delta_angle"] = float(split_line[8])

                        # "coordinate" is used to generate the column
                        # "burst_extent" for the "bursts_metadata"
                        # table of a db file.
                        temp_dict["coordinate"] = [
                            [float(split_line[14]), float(split_line[13])],
                            [float(split_line[16]), float(split_line[15])],
                            [float(split_line[10]), float(split_line[9])],
                            [float(split_line[12]), float(split_line[11])],
                        ]
                        burst_info["burst {}".format(temp_dict["burst_num"])] = temp_dict
                return burst_info

            with tempfile.TemporaryDirectory() as tmp_dir:
                self.extract_archive_tofile(target_file=xml_path, outdir=tmp_dir, retry=3)

                tmp_path = os.path.join(tmp_dir, os.path.basename(xml_path))
                _, cout, _ = pg.S1_burstloc(tmp_path)
                return _parse_s1_burstloc(cout)

        with swath_obj as obj:
            ann_tree = etree.fromstring(obj.read())
            swath_meta["samples"] = int(
                ann_tree.find(".//imageAnnotation/imageInformation/numberOfSamples").text
            )

            swath_meta["lines"] = int(
                ann_tree.find(".//imageAnnotation/imageInformation/numberOfLines").text
            )

            swath_meta["spacing"] = list(
                [
                    float(ann_tree.find(".//{}PixelSpacing".format(dim)).text)
                    for dim in ["range", "azimuth"]
                ]
            )

            heading = float(ann_tree.find(".//platformHeading").text)
            swath_meta["heading"] = heading if heading > 0 else heading + 360
            swath_meta["incidence"] = float(
                ann_tree.find(".//incidenceAngleMidSwath").text
            )
            swath_meta["image_geometry"] = (
                ann_tree.find(".//projection").text.replace(" ", "_").upper()
            )

        burst_meta = _metadata_burst(xml_file)

        return {**swath_meta, **burst_meta}

    def archive_name_list(self):
        """Sets archive_files with names in a slc zip archive. """

        with zf.ZipFile(self.scene, "r") as archive:
            self.archive_files = archive.namelist()

    def find_archive_files(
        self, pattern: str,
    ):
        """
        Returns a matching name from a archive_file for given pattern
        """

        self.archive_name_list()
        match_names = [
            name
            for name in self.archive_files
            if re.search(pattern, os.path.basename(name))
        ]
        return match_names

    def extract_archive_BytesIO(self, target_file: Path,) -> BytesIO:
        """
        Extracts content from a target file within the slc zip archive
        as a _io.BytesIO object

        Parameters
        ----------
        target_file: Path
            The path of a target file inside the S1 zip archive
            must be supplied (not the full path). Target file
            is usually the:
            (a) manifest.safe file;
            (b) xml file, or;
            (c) tiff file
            e.g.
            S1A_IW_SLC__1SDV_20180106T193808_20180106T193834_020038_02224B_8674.SAFE/manifest.safe

        Returns
        -------
            contents of target file as BytesIO object

        Notes
        -----
            retries are not possible because we can't compare the bytes
            of the target file with that from a BytesIO object,
            BytesIO.__sizeof__() != os.path.getsize(target_file)
        """

        # get archive contents and size from an S1 zip
        # scene = /g/data/{some_path}/S1A_IW_SLC__1SDV_20180106T193808_20180106T193834_020038_02224B_8674.zip
        # target_file = S1A_IW_SLC__1SDV_20180106T193808_{blah}_8674.SAFE/manifest.safe
        # target_file = S1A_IW_SLC__1SDV_20180106T193808_{blah}_8674.SAFE/annotation/s1a-iw1-{blah}-004.xml
        # target_file = S1A_IW_SLC__1SDV_20180106T193808_{blah}_8674.SAFE/measurement/s1a-iw1-{blah}-004.tiff
        with zf.ZipFile(self.scene, "r") as archive:
            file_obj = BytesIO()
            file_obj.write(archive.read(target_file))
            file_obj.seek(0)
            return file_obj

    def extract_archive_tofile(
        self, target_file: Path, outdir: Path, retry: Optional[int] = 0,
    ) -> None:
        """
        Extracts content from a target file within the slc zip archive
        to a file in the user specified outdir. Returns None

        Parameters
        ----------
        target_file: Path
            The path of a target file inside the S1 zip archive
            must be supplied (not the full path). Target file
            is usually the:
            (a) manifest.safe file;
            (b) xml file, or;
            (c) tiff file
            e.g.
            S1A_IW_SLC__1SDV_20180106T193808_20180106T193834_020038_02224B_8674.SAFE/manifest.safe

        outdir: Path
            Output directory to write a copy of the target file.

        retry: int
            The number of retries (must be greater than 0)

        Returns
        -------
            None

        Notes
        -----
            Retries are possible as we can compare the bytes of copied file
            with target file
        """
        # ---------------------------- #
        #          FUNCTIONS           #
        # ---------------------------- #
        def _copy_target_contents(
            o_file, archive_contents,
        ):
            # o_file: str
            # archive_contents: bytes
            with open(o_file, "wb") as out_fid:
                out_fid.write(archive_contents)
            return None

        def _check_byte_size(
            o_file, expected_size,
        ):
            # check the size (in Bytes) of o_file
            # against size of source file
            #
            # o_file: str
            # expected_size: int
            size_ok = False
            if os.path.exists(o_file):
                if os.path.getsize(o_file) == expected_size:
                    size_ok = True
            else:
                _LOG.info("_check_byte_size(): {} does not exist".format(o_file))

            return size_ok

        # ---------------------------- #
        #                              #
        # ---------------------------- #
        # ensure that outdir exists
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        # outfile is effectively a copy of the target file in outdir
        outfile = pjoin(outdir, os.path.basename(target_file))

        # get archive contents and size from an S1 zip
        # scene = /g/data/{some_path}/S1A_IW_SLC__1SDV_20180106T193808_20180106T193834_020038_02224B_8674.zip
        # target_file = S1A_IW_SLC__1SDV_20180106T193808_{blah}_8674.SAFE/manifest.safe
        # target_file = S1A_IW_SLC__1SDV_20180106T193808_{blah}_8674.SAFE/annotation/s1a-iw1-{blah}-004.xml
        # target_file = S1A_IW_SLC__1SDV_20180106T193808_{blah}_8674.SAFE/measurement/s1a-iw1-{blah}-004.tiff
        with zf.ZipFile(self.scene, "r") as zip_archive:
            # open S1 zip and get contents from a target file
            source_size = zip_archive.getinfo(target_file).file_size
            archive_dump = zip_archive.read(target_file)  # <class 'bytes'>

        _copy_target_contents(outfile, archive_dump)

        if retry <= 0:
            _LOG.info("extract_archive_tofile(): no retries specified", retry=retry)
            return None

        else:
            if _check_byte_size(outfile, source_size):
                _LOG.info(
                    "extract_archive_tofile(): _check_byte_size() returned True (no retries performed)"
                )
                return None

            _LOG.info(
                "retrying extraction",
                max_retries=retry,
                target_file=target_file,
                slc_scene=self.scene,
                outfile=outfile,
            )

            retry_count = 0
            while retry_count < retry:

                # retry copying the contents of the archive
                # TODO: can other checks be done to verify the process?
                _copy_target_contents(outfile, archive_dump)
                if _check_byte_size(outfile, source_size) is False:
                    # size of copied archive != original archive
                    retry_count += 1
                else:
                    break

            if retry_count == retry:
                _LOG.error(
                    "failed to extract data",
                    target_file=target_file,
                    slc_scene=self.scene,
                    outfile=outfile,
                )

            return None


class S1DataDownload(SlcMetadata):
    """
    A class to download an slc data from a sentinel-1 archive.
    """

    def __init__(
        self,
        slc_scene: Path,
        polarization: List[str],
        s1_orbits_poeorb_path: Path,
        s1_orbits_resorb_path: Path,
    ) -> None:
        """a default class constructor."""
        self.raw_data_path = slc_scene
        self.polarization = polarization
        self.s1_orbits_poeorb_path = s1_orbits_poeorb_path
        self.s1_orbits_resorb_path = s1_orbits_resorb_path

        super(S1DataDownload, self).__init__(self.raw_data_path)
        self.archive_name_list()

    def get_poeorb_orbit_file(self):
        """A method to download precise orbit file for a slc scene."""

        _poeorb_path = pjoin(self.s1_orbits_poeorb_path, self.sensor)
        orbit_files = [p_file for p_file in os.listdir(_poeorb_path)]
        start_datetime = datetime.datetime.strptime(
            self.acquisition_start_time, self.dt_fmt_1
        )
        start_date = (start_datetime - datetime.timedelta(days=1)).strftime(self.date_fmt)
        end_date = (start_datetime + datetime.timedelta(days=1)).strftime(self.date_fmt)

        acq_orbit_file = fnmatch.filter(
            orbit_files, "*V{}*_{}*.EOF".format(start_date, end_date)
        )

        if not acq_orbit_file:
            return

        if len(acq_orbit_file) > 1:
            acq_orbit_file = sorted(
                acq_orbit_file,
                key=lambda x: datetime.datetime.strptime(x.split("_")[5], self.dt_fmt_2),
            )
        return pjoin(_poeorb_path, acq_orbit_file[-1])

    def get_resorb_orbit_file(self):
        """A method to download restitution orbit file for a slc scene."""

        def __start_strptime(dt):
            return datetime.datetime.strptime(dt, "V{}".format(self.dt_fmt_2))

        def __stop_strptime(dt):
            return datetime.datetime.strptime(dt, "{}.EOF".format(self.dt_fmt_2))

        _resorb_path = pjoin(self.s1_orbits_resorb_path, self.sensor)
        orbit_files = [orbit_file for orbit_file in os.listdir(_resorb_path)]
        start_datetime = datetime.datetime.strptime(
            self.acquisition_start_time, self.dt_fmt_1
        )
        end_datetime = datetime.datetime.strptime(
            self.acquisition_stop_time, self.dt_fmt_1
        )
        acq_date = start_datetime.strftime(self.date_fmt)

        acq_orbit_file = fnmatch.filter(orbit_files, "*V{d}*_{d}*.EOF".format(d=acq_date))

        acq_orbit_file = [
            orbit_file
            for orbit_file in acq_orbit_file
            if start_datetime >= __start_strptime(orbit_file.split("_")[6])
            and end_datetime <= __stop_strptime(orbit_file.split("_")[7])
        ]

        if not acq_orbit_file:
            return
        if len(acq_orbit_file) > 1:
            acq_orbit_file = sorted(
                acq_orbit_file,
                key=lambda x: datetime.datetime.strptime(x.split("_")[5], self.dt_fmt_2),
            )

        return pjoin(_resorb_path, acq_orbit_file[-1])

    def slc_download(
        self,
        output_dir: Path,
        retry: Optional[int] = 3,
        polarizations: Optional[List[str]] = None,
    ):
        """A method to download slc raw data."""

        if polarizations is None:
            polarizations = self.polarization

        download_files_patterns = sum(
            [
                [
                    f"*measurement/*{pol.lower()}*",
                    f"*annotation/*{pol.lower()}*",
                    f"*/calibration/*{pol.lower()}*",
                ]
                for pol in polarizations
            ],
            [],
        )

        # extract files from slc archive (zip) file
        files_download = sum(
            [
                fnmatch.filter(self.archive_files, pattern)
                for pattern in download_files_patterns
            ],
            [],
        )

        # If there are no matching polarisations, exit early
        if not files_download:
            return None

        files_download.append(self.manifest_file)

        # get a base slc directory where files will be downloaded
        base_dir = pjoin(output_dir, os.path.commonprefix(files_download))

        try:
            for target_file in files_download:
                path_inzip = os.path.dirname(target_file)
                path_copy_target = pjoin(output_dir, path_inzip)
                # Note:
                #  path_inzip = S1A_IW_SLC__1SDV_20180106T193808_{blah}_8674.SAFE/measurement
                #  path_copy_target = directory where the target files (tiff) are copied to.
                self.extract_archive_tofile(
                    target_file=target_file, outdir=path_copy_target, retry=retry
                )

        # In case of an error during extraction (eg: corrupt zip files), log the failure
        # and clean up the base directory so there's no partial/incomplete raw data for
        # the S1 SLC processing to misinterpret.
        except Exception as e:
            _LOG.error(
                "SLC download failed extraction due to exception, cleaning up...",
                exc_info=True,
                base_dir=base_dir)

            shutil.rmtree(base_dir)
            raise e

        # download orbit files with precise orbit as first choice
        orbit_source_file = self.get_poeorb_orbit_file()

        start_datetime = datetime.datetime.strptime(self.acquisition_start_time, self.dt_fmt_1)

        if orbit_source_file is not None:
            orbit_destination_file = pjoin(base_dir, os.path.basename(orbit_source_file))

        else:
            start_date = (start_datetime - datetime.timedelta(days=1)).strftime(self.date_fmt)
            end_date = (start_datetime + datetime.timedelta(days=1)).strftime(self.date_fmt)

            msg = f"Missing precise orbit file for {self.raw_data_path}\n"
            msg += f"Searched directory: {self.s1_orbits_poeorb_path}/{self.sensor}\n"
            msg += f"with pattern: *V{start_date}*_{end_date}*.EOF"
            _LOG.warning(msg)

            orbit_source_file = self.get_resorb_orbit_file()

            if not orbit_source_file:
                msg = f"No orbit files found for {start_datetime}"
                _LOG.warning(msg, slc_scene=self.scene)
                return base_dir

            orbit_destination_file = pjoin(base_dir, os.path.basename(orbit_source_file))

        _LOG.info(
            "Downloading orbit file",
            scene=self.raw_data_path,
            src_file=orbit_source_file,
            dst_file=orbit_destination_file,
        )

        if not os.path.exists(orbit_destination_file):
            shutil.copyfile(orbit_source_file, orbit_destination_file)

        return base_dir


class Archive:
    """
    A class to create a light-weight sqlite database to archive slc metadata
    and facilitate an automated query into a database.
    """

    def __init__(self, dbfile: Path,) -> None:
        """
        Injest Sentinel-1 SLC metadata into a sqlite database.

        SLC metadata extracted from a manifest safe file and annotation/xmls
        are injested into a sqlite database. Also, querries can be carried
        out into the database to generate SLC informations contained in the
        database.

        Parameters
        ----------
        dbfile: Path
            full path to a database file.
        """

        def _create_table_command(
            db_table_name, db_column_dict,
        ):
            """
            Return the sqlite command (type <string>) that when
            executed, will create a table with the column names
            """
            return """CREATE TABLE if not exists {} ({})""".format(
                db_table_name, ", ".join([" ".join(x) for x in db_column_dict.items()]),
            )

        def _add_geom_column_command(
            db_table_name, db_geom_col_name,
        ):
            """
            Return the sqlite command (type <string>) that when executed,
            will create a geometry (polygon) column to a specified table
            """
            return """SELECT AddGeometryColumn("{}", "{}", 4326, "POLYGON", "XY", 0)""".format(
                db_table_name, db_geom_col_name,
            )

        self.dbfile = Path(dbfile).as_posix()
        self.conn = sqlite_setup(self.dbfile, ["spatialite"])
        self.metadata = dict()
        self.slc_table_name = "slc_metadata"
        self.swath_table_name = "swath_metadata"
        self.bursts_table_name = "bursts_metadata"
        self.duplicate_table_name = "slc_duplicates"
        self.slc_rows_table_name = "slc_rows_metadata"  # new table

        # column names in "slc_metadata" table,
        # "slc_extent" column added below
        self.slc_fields_dict = {
            "id": "TEXT PRIMARY KEY",
            "url": "TEXT",
            "IPF_version": "TEXT",
            "acquisition_mode": "TEXT",
            "acquisition_start_time": "TEXT",
            "acquisition_stop_time": "TEXT",
            "category": "TEXT",
            "crs": "TEXT",
            "cycleNumber": "INTEGER",
            "frameNumber": "INTEGER",
            "orbit": "TEXT",
            "orbitNumber_abs": "INTEGER",
            "orbitNumber_rel": "INTEGER",
            "orbitNumbers_abs_start": "INTEGER",
            "orbitNumbers_abs_stop": "INTEGER",
            "hh": "INTEGER",
            "vv": "INTEGER",
            "hv": "INTEGER",
            "vh": "INTEGER",
            "product": "TEXT",
            "sensor": "TEXT",
            "sliceNumber": "INTEGER",
            "totalSlices": "INTEGER",
        }

        # column names in "swath_metadata" table
        self.swath_fields_dict = {
            "swath_name": "TEXT PRIMARY KEY",
            "id": "TEXT NOT NULL",
            "heading": "REAL",
            "incidence": "REAL",
            "lines": "INTEGER",
            "samples": "INTEGER",
            "range_spacing": "REAL",
            "azimuth_spacing": "REAL",
            "total_bursts": "INTEGER",
        }

        # column names in "bursts_metadata" table,
        # "burst_extent" column added below
        self.burst_fields_dict = {
            "row_id": "TEXT NOT NULL",
            "swath_name": "TEXT NOT NULL",
            "swath": "TEXT",
            "azimuth_time": "REAL",
            "delta_angle": "REAL",
            "burst_number": "INTEGER",
            "polarization": "TEXT",
            "relative_orbit": "INTEGER",
            "angle": "REAL",
        }

        # column names in "slc_duplicates" table
        self.duplicate_fields_dict = {
            "id": "TEXT PRIMARY KEY",
            "url": "TEXT",
        }

        # column names in "slc_rows_metadata" table,
        # "row_extent" column added below
        self.rows_fields_dict = {
            "row_id": "TEXT NOT NULL",
            "iw_list": "TEXT",
            "burst_number": "INTEGER",
            "polarization": "TEXT",
        }

        cursor = self.conn.cursor()

        # ------------------------------- #
        # - create "slc_metadata" table - #
        cursor.execute(_create_table_command(self.slc_table_name, self.slc_fields_dict),)

        # add "slc_extent" column, which will contain
        # polygons of each slc acquisition footprint
        if "slc_extent" not in self.get_colnames(self.slc_table_name):
            cursor.execute(_add_geom_column_command(self.slc_table_name, "slc_extent"),)

        # --------------------------------- #
        # - create "swath_metadata" table - #
        cursor.execute(
            _create_table_command(self.swath_table_name, self.swath_fields_dict,),
        )

        # ---------------------------------- #
        # - create "bursts_metadata" table - #
        cursor.execute(
            _create_table_command(self.bursts_table_name, self.burst_fields_dict,),
        )

        # add "bursts_extent" column, which will contain
        # polygons for all bursts in a given slc acquisition
        if "burst_extent" not in self.get_colnames(self.bursts_table_name):
            cursor.execute(
                _add_geom_column_command(self.bursts_table_name, "burst_extent",),
            )

        # ------------------------------------ #
        # - create "slc_rows_metadata" table - #
        cursor.execute(
            _create_table_command(self.slc_rows_table_name, self.rows_fields_dict,),
        )

        # add "row_extent" column, which will contain
        # polygons for all rows in a given slc acquisition
        if "row_extent" not in self.get_colnames(self.slc_rows_table_name):
            cursor.execute(
                _add_geom_column_command(self.slc_rows_table_name, "row_extent",),
            )

        # --------------------------------- #
        # - create "slc_duplicates" table - #
        cursor.execute(
            _create_table_command(self.duplicate_table_name, self.duplicate_fields_dict,),
        )

        self.conn.commit()

    @property
    def primary_fieldnames(self):
        """Sets primary fieldnames if slc metadata exists."""
        if self.metadata:
            return {
                **{"id": "id"},
                **{
                    pk: [k for k, v in self.metadata[pk].items()]
                    for pk in ["product", "measurements", "properties"]
                },
            }

    @property
    def properties_fieldnames(self):
        """Sets properties fieldnames if slc metadata exists."""
        if self.primary_fieldnames:
            return self.primary_fieldnames["properties"]

    @property
    def measurements(self):
        """ sets measurement fieldnames if slc metadata exists. """
        if self.primary_fieldnames:
            return self.primary_fieldnames["measurements"]

    @property
    def burst_fieldnames(self):
        """Sets burst fieldnames if slc metadata exists."""
        if self.measurements:
            return {
                k
                for k, v in self.metadata["measurements"][self.measurements[0]][
                    "burst 1"
                ].items()
            }

    @property
    def product_id(self):
        """Sets slc product id if slc metadata exists."""
        if self.metadata:
            return self.metadata["id"]

    @property
    def file_location(self):
        """Sets slc file locations if slc metadata exists."""
        if self.metadata:
            return self.metadata["product"]["url"]

    @staticmethod
    def get_corners(
        lats: List[float], lons: List[float],
    ):
        """Returns corner from given latitudes and longitudes."""

        return {
            "xmin": min(lons),
            "xmax": max(lons),
            "ymin": min(lats),
            "ymax": max(lats),
        }

    def get_measurement_fieldnames(
        self, measurement_key: str,
    ):
        """Returns all the measurement fieldnames for a slc scene."""

        return {k for k in self.metadata["measurements"][measurement_key].keys()}

    def get_measurement_metadata(
        self, measurement_key: str,
    ):
        """
        Returns a copy of the metadata associated with all slc
        measurement field names. Note, certain keys/items in
        this dictionary are deleted in get_swath_bursts_metadata(),
        hence why a copy is returned.
        """

        return {k: v for k, v in self.metadata["measurements"][measurement_key].items()}

    def get_slc_metadata(self):
        """
        Returns data from the "properties" key contained in slc metadata.
        """
        slc_metadata = {
            key: self.metadata["properties"][key] for key in self.properties_fieldnames
        }

        # slc_extent has Polygons with format of
        # [lat1 lon1, ..., latN lonN, lat1 lon1]
        # we need the lat/lons to be switched
        # such that:
        # [lon1 lat1, ..., lonN latN, lon1 lat1]
        slc_metadata["slc_extent"] = Polygon(
            [coord for coord in slc_metadata["coordinates"]]
        ).wkt
        return slc_metadata

    def get_burst_names(
        self, measurement_key: str,
    ):
        """
        Returns all the bursts contained
        within a given swath measurement
        """

        return [
            burst
            for burst in self.get_measurement_fieldnames(measurement_key)
            if re.match(r"burst [0-9]", burst)
        ]

    @staticmethod
    def encode_string(
        string: str, encoding: Optional[str] = "utf-8",
    ):
        """Encodes binary values into a string."""
        if not isinstance(string, str):
            return string.encode(encoding)
        return string

    def get_swath_bursts_metadata(
        self, measurement_key, burst_key=None,
    ):
        """Returns measurement or burst metadata."""
        measurement_metadata = self.get_measurement_metadata(measurement_key)
        burst_names = self.get_burst_names(measurement_key)

        burst_metadata = dict()
        for m_field in self.get_measurement_fieldnames(measurement_key):
            m_metadata = measurement_metadata[m_field]
            if m_field in burst_names:
                burst_temp = dict()
                for name in self.burst_fieldnames:
                    burst_temp[name] = m_metadata[name]
                burst_temp["burst_extent"] = [coord for coord in burst_temp["coordinate"]]
                burst_metadata[m_field] = burst_temp
                del measurement_metadata[m_field]

        measurement_metadata["num_bursts"] = len(burst_names)

        if burst_key:
            return burst_metadata[burst_key]

        return measurement_metadata

    def get_slc_row_extent(
        self, subswaths_dict,
    ):
        """

        Parameters
        ----------
        subswaths_dict: dict()
            a dictionary containing xml basenames and burst information
            for all three sub-swaths in a given SLC acquisition.

        Returns
        -------
        row_extent_dict: dict()
            Dictionary containing the row extent (convex hull polygon)
            for a given burst across IW1, IW2 and IW3.
        """
        slc_row_dict = dict()
        for _pol in subswaths_dict:
            # Before we iterate over the burst_keys. We need to check
            # which sub-swath has the max. bursts, given that:
            #
            # IW1 = ["burst 1", ..., "burst 8"]
            # IW2 = ["burst 1", ..., "burst 8", "burst 9"]
            # IW3 = ["burst 1", ..., "burst 8", "burst 9"]
            #  Here, there are 8+(2/3) rows, where row 9 is incomplete
            #
            #  OR
            # IW1 = ["burst 1", ..., "burst 9", "burst 10"]
            # IW2 = ["burst 1", ..., "burst 9"]
            # IW3 = ["burst 1", ..., "burst 9"]
            #  Here, there are 9+(1/3) rows, where row 10 is incomplete
            #
            #  OR subswaths can have equal number of bursts
            # IW1 = ["burst 1", ..., "burst N"]
            # IW2 = ["burst 1", ..., "burst N"]
            # IW3 = ["burst 1", ..., "burst N"]
            #
            # Key assumptions here is that burst i from IW1, IW2, IW3
            # form a single row i. This is isn't always true, however
            # this sorting by rows is a simple intermediate step in
            # creating grids/frames and doesn't need to be perfect.

            # iterate through subswaths and get "total_bursts"
            max_burst_tot = 0  # max. number of rows possible
            min_burst_tot = 1e4  # max. number of complete rows
            max_burst_keys = list()
            max_burst_nums = list()
            for _iw in subswaths_dict[_pol]:
                total_bursts = subswaths_dict[_pol][_iw]["total_bursts"]
                if total_bursts > max_burst_tot:
                    max_burst_tot = total_bursts
                    max_burst_keys = subswaths_dict[_pol][_iw]["burst_key"]
                    max_burst_nums = subswaths_dict[_pol][_iw]["burst_numbers"]

                if total_bursts < min_burst_tot:
                    min_burst_tot = total_bursts

            iw_append_key = []  # sub-swaths with incomplete rows
            for _iw in subswaths_dict[_pol]:
                if subswaths_dict[_pol][_iw]["total_bursts"] == max_burst_tot:
                    iw_append_key.append(_iw)

            # e.g. iw_append_key = ["IW1"] or ["IW2", "IW3"]. As a
            # quick & easy patch, bursts from incomplete rows will be
            # appended to the last complete row, given by min_burst_tot

            slc_row_dict[_pol] = dict()

            for _i, mb_key in enumerate(max_burst_keys):
                poly_wkt_list = []
                xml_list = []
                iw_str = ""
                # Iterate over all iw-xml files for this polarisation.
                if _i <= min_burst_tot - 1:
                    # this is a complete row
                    row_id = "{0}-{1}-row{2:02}".format(
                        self.product_id, _pol, max_burst_nums[_i],
                    )

                    for _iw in subswaths_dict[_pol]:
                        m_xml = subswaths_dict[_pol][_iw]["xml"]
                        iw_str += "{0}.{1}-".format(_iw, max_burst_nums[_i])
                        xml_list.append(m_xml)
                        poly_wkt_list.append(
                            Polygon(
                                self.metadata["measurements"][m_xml][mb_key]["coordinate"]
                            ),
                        )
                    slc_row_dict[_pol][mb_key] = {
                        "convex_hull": MultiPolygon(poly_wkt_list).convex_hull.wkt,
                        "burst_num": max_burst_nums[_i],
                        "iw_list": iw_str[:-1],
                        "xml_list": xml_list,
                        "row_id": row_id,
                        "appended_bursts": [],
                    }
                    # iw_str will provide information as to which
                    # sub-swath(s) the convex hull was applied over.

                if _i > min_burst_tot - 1:
                    # Incomplete row. Append to previous complete row.
                    mb_key_pre = max_burst_keys[min_burst_tot - 1]
                    # mb_key_pre = burst key of previous complete row

                    row_id = slc_row_dict[_pol][mb_key_pre]["row_id"]

                    iw_str = "({})+(".format(
                        slc_row_dict[_pol][mb_key_pre]["iw_list"]
                    )  # = ("IW1.?-IW2.?-IW3.?)+("

                    xml_list = slc_row_dict[_pol][mb_key_pre]["xml_list"]

                    poly_wkt_list.append(
                        shapely.wkt.loads(slc_row_dict[_pol][mb_key_pre]["convex_hull"],),
                    )  # convex hull of previous complete row

                    append_info = []
                    # list that contains [xml, burst_key] of incomplete
                    # rows that are appended to previous row

                    for _iw in iw_append_key:
                        m_xml = subswaths_dict[_pol][_iw]["xml"]
                        iw_str += "{0}.{1}-".format(_iw, max_burst_nums[_i],)
                        poly_wkt_list.append(
                            Polygon(
                                self.metadata["measurements"][m_xml][mb_key]["coordinate"]
                            ),
                        )
                        append_info.append([m_xml, max_burst_keys[_i]])

                    iw_str = iw_str[:-1] + ")"
                    # e.g. iw_str = (IW1.9-IW2.9-IW3.9)+(IW1.10) which
                    # means that burst 10 from IW1 was appended to row
                    # 9. Overwrite the necessary dict values.
                    slc_row_dict[_pol][mb_key_pre] = {
                        "convex_hull": MultiPolygon(poly_wkt_list).convex_hull.wkt,
                        "burst_num": max_burst_nums[min_burst_tot - 1],
                        "iw_list": iw_str,
                        "xml_list": xml_list,
                        "row_id": row_id,
                        "appended_bursts": append_info,
                    }
            # endfor _i
        # endfor _pol
        return slc_row_dict

    def get_tablenames(self):
        """ returns all tables names from sqlite_master schema. """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM sqlite_master WHERE type="table"')
        return sorted([self.encode_string(x[1]) for x in cursor.fetchall()])

    def get_colnames(
        self, table_name: str,
    ):
        """
        Extracts the column names for a specified table name

        Parameters
        ----------

        table_name: str
            the table name in the database

        Return
           a list of the column names in the table
        """
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info({})".format(table_name))
        return sorted([self.encode_string(x[1]) for x in cursor.fetchall()])

    def get_rel_orbit_nums(
        self, orbit_node=None, sensor_type=None, rel_orb_num=None,
    ):
        """
        Get the unique listings of the relative orbit numbers. A
        useful function when prior knowledge of which relative
        orbit numbers does not exist for a given orbit node & sensor

        Parameters
        ----------

        orbit_node : str or None
            The orbit node ("A", "D") for ascending & descending nodes
            respectively. If None then "A" and "D" are included in the
            search.

        sensor_type : str or None
            The sensor ("S1A", "S2A") for S1A and S1B respectively
            If None then "S1A" and "S1B" are included in the search.

        rel_orb_num : int or None
            The relative orbit number. If specified, then this function
            checks if it exists.

        Returns
        -------
        list or None
            Unique listing of the relative orbit numbers
            None if error occured

        Author, Date
        ------------
            Rodrigo Garcia, 2nd April 2020
        """

        table_list = self.get_tablenames()

        # check that there are tables in the db
        if not table_list:
            _LOG.error(
                "Database does not contain any tables", database=self.dbfile,
            )
            return None  # return None for error checks

        # ensure the "slc_metadata" table exists
        if not "slc_metadata" in table_list:
            _LOG.error(
                "Database does not contain the slc_metadata table",
                database=self.dbfile,
                table_list=table_list,
            )
            return None  # return None for error checks

        cursor = self.conn.cursor()

        try:
            table_columns = cursor.execute(
                "SELECT url, orbit, sensor, orbitnumber_rel FROM slc_metadata"
            ).fetchall()

        except sqlite3.OperationalError as err:
            if str(err).lower().find("no such column") != -1:
                _LOG.error(
                    "Database query of slc_metadata table failed",
                    pathname=self.dbfile,
                    error_message=err,
                )
            else:
                raise err

            return None  # return None for error checks

        # ---------------------------------------- #
        #  Get all relative orbit numbers base on  #
        #  the user inputs of sensor type,  orbit  #
        #  node and relative orbit number          #
        # ---------------------------------------- #

        # create a user input set so we can find
        # the union with the table columns
        user_set = []
        if orbit_node:
            user_set.append(orbit_node.upper())
        if sensor_type:
            user_set.append(sensor_type.upper())
        if rel_orb_num:
            user_set.append(rel_orb_num)
        user_set = set(user_set)

        # creating a set to directly obtain unique
        # values without an a posteriori np.unique
        ron_meets_criteria = set()
        for row in table_columns:
            # check if user_set is a subset of row
            if user_set.issubset(set(row[1:])):
                ron_meets_criteria.add(row[3])

        # sort set() in ascending order and return as list
        return sorted(ron_meets_criteria)

    def prepare_slc_metadata_insertion(self):
        """
        prepares to insert slc metadata into a database
        """
        slc_metadata = self.get_slc_metadata()
        polarizations = [pol.lower() for pol in slc_metadata["polarizations"]]
        col_names = self.get_colnames(self.slc_table_name)
        insertion_values = []
        for col in col_names:
            if col in ["hh", "hv", "vv", "vh"]:
                if col in polarizations:
                    insertion_values.append(1)
                else:
                    insertion_values.append(0)
            elif col == "id":
                insertion_values.append(self.product_id)
            elif col == "orbitNumbers_abs_start":
                insertion_values.append(slc_metadata["orbitNumbers_abs"]["start"])
            elif col == "orbitNumbers_abs_stop":
                insertion_values.append(slc_metadata["orbitNumbers_abs"]["stop"])
            elif col == "url":
                insertion_values.append(self.file_location)
            else:
                insertion_values.append(slc_metadata[col])

        insert_cmd = """INSERT INTO {0}({1}) VALUES({2})""".format(
            self.slc_table_name,
            ", ".join(col_names),
            ", ".join(
                ["GeomFromText(?, 4326)" if x == "slc_extent" else "?" for x in col_names]
            ),
        )

        return insert_cmd, tuple(insertion_values)

    def prepare_swath_metadata_insertion(self, measurement_key: str):
        """ prepares swath metadata to be inserted into a database. """
        measurement_metadata = self.get_swath_bursts_metadata(measurement_key)
        col_names = self.get_colnames(self.swath_table_name)
        insertion_values = []
        for col in col_names:
            if col == "id":
                insertion_values.append(self.product_id)
            elif col == "swath_name":
                insertion_values.append(measurement_key)
            elif col == "range_spacing":
                insertion_values.append(measurement_metadata["spacing"][0])
            elif col == "azimuth_spacing":
                insertion_values.append(measurement_metadata["spacing"][1])
            elif col == "total_bursts":
                insertion_values.append(measurement_metadata["num_bursts"])
            else:
                insertion_values.append(measurement_metadata[col])

        insert_cmd = """INSERT INTO {0}({1}) VALUES({2})""".format(
            self.swath_table_name,
            ", ".join(col_names),
            ", ".join(["?" for _ in col_names]),
        )

        return insert_cmd, tuple(insertion_values)

    def prepare_burst_metadata_insertion(
        self, measurement_key: str, burst_key: str, row_id: str,
    ):
        """
        Prepares metadata from a single burst to be inserted into a database.

        Parameters
        ----------
        measurement_key: str
            basename of an xml file, inside a S1 zip, e.g.
            s1b-iw1-slc-hh-20180204t004338-20180204t004406-009466-011062-001.xml

        burst_key: str
           e.g. burst_key = 'burst 1'
                burst_key = 'burst 2' etc.

        row_id: str
            The unique id for a given row, polarisation and slc acquisition.
            e.g. 6eebff47-be4d-4ec2-b148-db32f7e0e293-HH-row01
                 6eebff47-be4d-4ec2-b148-db32f7e0e293-HH-row02
                                   .....
                 6eebff47-be4d-4ec2-b148-db32f7e0e293-HH-row10

        Returns
        -------
        insert_cmd: str
            sqlite insert command

        insertion_values: tuple
            values used in the insert command
        """
        burst_metadata = self.get_swath_bursts_metadata(measurement_key, burst_key,)
        # burst_metadata -> dict with the following items:
        # azimuth_time, angle, delta_angle, coordinate, burst_num
        # rel_orbit, swath, polarization, burst_extent
        # where,
        # burst_extent = coordinate
        col_names = self.get_colnames(self.bursts_table_name)

        insertion_values = []
        for col in col_names:
            if col == "row_id":
                insertion_values.append(row_id)
            elif col == "swath_name":
                insertion_values.append(measurement_key)
            elif col == "burst_number":
                insertion_values.append(burst_metadata["burst_num"])
            elif col == "relative_orbit":
                insertion_values.append(burst_metadata["rel_orbit"])
            elif col == "burst_extent":
                coords = [
                    "{:.6f} {:.6f}".format(item[0], item[1])
                    for item in burst_metadata[col] + [burst_metadata[col][0]]
                ]
                poly_str = "POLYGON (({}))".format(", ".join(coords))
                insertion_values.append(poly_str)
            else:
                insertion_values.append(burst_metadata[col])

        insert_cmd = """INSERT INTO {0}({1}) VALUES({2})""".format(
            self.bursts_table_name,
            ", ".join(col_names),
            ", ".join(
                [
                    "GeomFromText(?, 4326)" if x == "burst_extent" else "?"
                    for x in col_names
                ]
            ),
        )

        return insert_cmd, tuple(insertion_values)

    def prepare_slc_row_insertion(
        self, polarization, burst_key, row_extent_dict,
    ):
        """
        Prepares metadata from a single burst to be inserted into a database.

        Parameters
        ----------
        polarization: str
            polarization mode = "HH", "HV", "VH" or "VV"

        burst_key: str
            burst_key = "burst 1", "burst 2", etc.

        row_extent_dict: dict
            dictionary containing the across track
            convex hull for the burst key

        Returns
        -------
        insert_cmd: str
            sqlite insert command

        insertion_values: tuple
            values used in the insert command
        """
        col_names = self.get_colnames(self.slc_rows_table_name)

        insertion_values = []
        for col in col_names:
            if col == "row_id":
                insertion_values.append(row_extent_dict["row_id"])
            elif col == "polarization":
                insertion_values.append(polarization)
            elif col == "burst_number":
                insertion_values.append(row_extent_dict["burst_num"])
            elif col == "iw_list":
                insertion_values.append(row_extent_dict["iw_list"])
            elif col == "row_extent":
                insertion_values.append(row_extent_dict["convex_hull"])

        insert_cmd = """INSERT INTO {0}({1}) VALUES({2})""".format(
            self.slc_rows_table_name,
            ", ".join(col_names),
            ", ".join(
                ["GeomFromText(?, 4326)" if x == "row_extent" else "?" for x in col_names]
            ),
        )

        return insert_cmd, tuple(insertion_values)

    def archive_scene(
        self, metadata: Union[dict, str],
    ):
        """
        archives a slc scene and its associated metadata
        (dict or a yaml file) into a sqlite database
        """

        if type(metadata) == dict:
            self.metadata = metadata
        else:
            with open(metadata, "r") as src:
                self.metadata = yaml.safe_load(src)
            raise TypeError("metadata should of of type dict or a yaml file")

        cursor = self.conn.cursor()
        slc_str, slc_values = self.prepare_slc_metadata_insertion()

        try:
            cursor.execute(slc_str, slc_values)
        except sqlite3.IntegrityError as err:
            if str(err) == "UNIQUE constraint failed: {}.id".format(self.slc_table_name):
                _LOG.info(
                    "record already exists in slc_duplicate table",
                    pathname=self.file_location,
                    slc_id=self.metadata["id"],
                    table_name=self.slc_table_name,
                )
            else:
                raise err

        # iw_dict is used to generate the slc_rows_metadata table
        iw_dict = dict()
        for _pol in ["HH", "HV", "VH", "VV"]:
            iw_dict[_pol] = dict()

        for m_xml in self.measurements:
            # Here, self.measurements are actually basenames of xml
            # files inside a S1 zip. Recall that there is a single
            # xml file for each sub-swath at a given polarisation.
            swath_cmd, swath_vals = self.prepare_swath_metadata_insertion(m_xml,)

            try:
                cursor.execute(swath_cmd, swath_vals)
            except sqlite3.IntegrityError as err:
                if str(err) == "UNIQUE constraint failed: {}.swath_name".format(
                    self.swath_table_name,
                ):
                    _LOG.info(
                        "duplicate detected",
                        pathname=self.file_location,
                        slc_id=self.product_id,
                        table_name=self.swath_table_name,
                    )
                    self.archive_duplicate()
                    return
                else:
                    raise err

            # NOTE: the number of bursts between subswaths for a given
            # polarization in a given SLC acquisition may not be equal.
            # e.g,
            # IW1 for VH = ['burst 1', ..., 'burst 8']
            # IW2 for VH = ['burst 1', ..., 'burst 8', 'burst 9']
            # IW3 for VH = ['burst 1', ..., 'burst 8', 'burst 9']
            burst_nums = sorted(
                [int(x.strip().split()[-1]) for x in self.get_burst_names(m_xml)]
            )
            # burst_keys = ['burst 1',  ..., 'burst N'] (sorted)
            burst_keys = ["burst {}".format(x) for x in burst_nums]

            _pol = self.metadata["measurements"][m_xml][burst_keys[0]]["polarization"]
            _iw = self.metadata["measurements"][m_xml][burst_keys[0]]["swath"]
            iw_dict[_pol][_iw] = {
                "xml": m_xml,
                "total_bursts": len(burst_keys),
                "burst_key": burst_keys,
                "burst_numbers": burst_nums,
            }

        # ------------------------------------ #
        #  insert data to "slc_rows_metadata"  #
        slc_row_dict = self.get_slc_row_extent(iw_dict)
        for _pol in slc_row_dict:
            for burst_key in slc_row_dict[_pol]:

                # row_id in bursts_metadata and slc_row_metadata
                # must be identical!
                row_id = slc_row_dict[_pol][burst_key]["row_id"]

                # add data to slc_row_metadata table
                slc_row_str, slc_row_values = self.prepare_slc_row_insertion(
                    _pol, burst_key, slc_row_dict[_pol][burst_key],
                )
                cursor.execute(slc_row_str, slc_row_values)

                # iterate through xmls & add to bursts_metadata table
                for m_xml in slc_row_dict[_pol][burst_key]["xml_list"]:
                    burst_str, burst_values = self.prepare_burst_metadata_insertion(
                        m_xml, burst_key, row_id,
                    )
                    cursor.execute(burst_str, burst_values)

                # Adding bursts from incomplete rows to bursts_metadata
                # By separating them apart we can now keep row_id
                # consistent with slc_row_metadata.
                for append_info in slc_row_dict[_pol][burst_key]["appended_bursts"]:
                    # xml, burst_key = append_info[0], append_info[1]
                    burst_str, burst_values = self.prepare_burst_metadata_insertion(
                        append_info[0], append_info[1], row_id,
                    )
                    cursor.execute(burst_str, burst_values)

        self.conn.commit()

    def archive_duplicate(self):
        """ archive duplicate slc scenes. """
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO slc_duplicates(id, url) VALUES(?, ?)",
                (os.path.basename(self.file_location), self.file_location),
            )
        except sqlite3.IntegrityError as err:
            if str(err) == "UNIQUE constraint failed: {}.id".format(
                self.duplicate_table_name
            ):
                _LOG.info(
                    "record already detected in slc_duplicate table",
                    pathname=self.file_location,
                    slc_id=self.metadata["id"],
                    table_name=self.duplicate_table_name,
                )
            else:
                raise err

        self.conn.commit()

    def __enter__(self):
        return self

    def close(self):
        self.conn.close()

    def __exit__(
        self, exc_type, exc_val, exc_tb,
    ):
        self.close()

    def select_bursts_in_vector(
        self,
        tables_join_string: str,
        orbit: Optional[str] = None,
        track: Optional[str] = None,
        spatial_subset: Optional[Vector] = None,
        args: Optional[str] = None,
        min_date_arg: Optional[str] = None,
        max_date_arg: Optional[str] = None,
        columns: Optional[List[str]] = None,
    ):
        """
        Returns pandas dataframe of SLC bursts that are contained within
        an area defined by a shape file. Here, this area is given as a
        spatialist Vector object.

        This function, originally called select() in /insar/s1_slc_metadata.py,
        will be become redundant in future commits, and is only included here
        as a temporary fix to generate data.
        """

        if not columns:
            columns = ["slc_metadata.slc_extent", "bursts_metadata.burst_extent"]
            for key in self.slc_fields_dict.keys():
                columns.append("{}.{}".format(self.slc_table_name, key))
            for key in self.swath_fields_dict.keys():
                columns.append("{}.{}".format(self.swath_table_name, key))
            for key in self.burst_fields_dict.keys():
                columns.append("{}.{}".format(self.bursts_table_name, key))

        if args:
            arg_format = ["{0}='{1}'".format(key, args[key]) for key in args.keys()]
        else:
            arg_format = []

        if orbit:
            arg_format.append("{}.orbit='{}'".format(self.slc_table_name, orbit))

        if track:
            arg_format.append("{}.orbitNumber_rel= {}".format(self.slc_table_name, track))

        if min_date_arg:
            arg_format.append(min_date_arg)
        if max_date_arg:
            arg_format.append(max_date_arg)

        if spatial_subset:
            # Spatial query check. Select data only if burst extent centroid is
            # inside the extent defined by the spatial vector. Note that spatial
            # subset must be an instance of a spatialist Vector
            if isinstance(spatial_subset, Vector):
                wkt_string = cascaded_union(
                    [
                        shapely.wkt.loads(extent)
                        for extent in spatial_subset.convert2wkt(set3D=False)
                    ]
                )
                arg_format.append(
                    "st_within(Centroid(bursts_metadata.burst_extent), GeomFromText('{}', 4326)) = 1".format(
                        wkt_string
                    )
                )

        query = """SELECT {0} from {1} WHERE {2}""".format(
            ", ".join(
                ["AsText({})".format(col) if "extent" in col else col for col in columns]
            ),
            tables_join_string,
            " AND ".join(arg_format),
        )
        cursor = self.conn.cursor()
        cursor.execute(query)

        initial_query_list = cursor.fetchall()
        if not initial_query_list:
            # query failed and returned nothing
            return None

        slc_df = pd.DataFrame(
            [[item for item in row] for row in initial_query_list],
            columns=[col[0] for col in cursor.description],
        )
        if slc_df.empty:
            return None

        return slc_df

    def select(
        self,
        tables_join_string: str,
        orbit: Optional[str] = None,
        args: Optional[str] = None,
        min_date_arg: Optional[str] = None,
        max_date_arg: Optional[str] = None,
        columns: Optional[List[str]] = None,
        frame_num: Optional[int] = None,
        frame_obj: Optional[Type["SlcFrame"]] = None,
        shapefile_name: Optional[Path] = None,
    ):
        """
        Parameters
        ----------

        tables_join_string: str
            string that selects the tables in the sqlite database to query

        orbit: str or None
            ?? unknown ??

        args: dict, str or None
            contains the SLC and burst metadata for the database query

        min_date_arg: datetime, str or None
            start datetime for the query

        max_date_arg: datetime, str or None
            end datetime for the query

        columns: list or None
            a list of the column names from which data will be extracted

        frame_num: int or None
            Frame number associated with a track_frame of spatial query.

        frame_obj: SlcFrame object or None
            Frame definition object from SlcFrame.

        shapefile_name: Path of None
           filename of a shape file

        Returns
        -------
           None or geo-pandas dataframe from the database
        """

        if not columns:
            columns = ["slc_metadata.slc_extent", "bursts_metadata.burst_extent"]
            for key in self.slc_fields_dict.keys():
                columns.append("{}.{}".format(self.slc_table_name, key))
            for key in self.swath_fields_dict.keys():
                columns.append("{}.{}".format(self.swath_table_name, key))
            for key in self.burst_fields_dict.keys():
                columns.append("{}.{}".format(self.bursts_table_name, key))
        if args:
            arg_format = ["{0}='{1}'".format(key, args[key]) for key in args.keys()]
        else:
            arg_format = []

        if orbit:
            arg_format.append("{}.orbit='{}'".format(self.slc_table_name, orbit))

        if min_date_arg:
            arg_format.append(min_date_arg)
        if max_date_arg:
            arg_format.append(max_date_arg)

        frame_intersect_query = ""
        if frame_num:
            if frame_obj is None:
                frame = SlcFrame()
            else:
                frame = frame_obj

            # frame.get_frame_extent(frame_num) calls SlcFrame.generate_frame_polygon()
            gpd_frame = frame.get_frame_extent(frame_num)
            if gpd_frame.empty:
                _LOG.warning(
                    "get frame extent warning, empty geo-pandas data frame",
                    frame_num=frame_num,
                    slc_metadata=args,
                )
                return

            track_frame_extent = gpd_frame["extent"].values[0]  # str
            frame_intersect_query = (
                " AND st_intersects(GeomFromText("
                + "'{}', 4326)".format(track_frame_extent)
                + ", slc_rows_metadata.row_extent) = 1"
            )

        table_select = ", ".join(
            ["AsText({})".format(col) if "extent" in col else col for col in columns]
        )

        base_query = """SELECT {0} FROM {1} WHERE {2}""".format(
            table_select, tables_join_string, " AND ".join(arg_format),
        )
        # base_query is reused in the refinement stage below
        burst_query = base_query + frame_intersect_query
        # during grid-definition burst_query:
        # SELECT
        #        bursts_metadata.burst_number,
        #        slc_metadata.sensor,
        #        AsText(bursts_metadata.burst_extent)
        #        swath_metadata.swath_name,
        #        bursts_metadata.swath,
        #        slc_metadata.orbit,
        #        bursts_metadata.polarization,
        #        slc_metadata.acquisition_start_time,
        #        slc_metadata.url,
        #        AsText(slc_metadata.slc_extent),
        #        AsText(slc_rows_metadata.row_extent)
        #        slc_rows_metadata.row_id
        # FROM
        #        bursts_metadata
        # INNER JOIN swath_metadata ON bursts_metadata.swath_name = swath_metadata.swath_name
        # INNER JOIN slc_metadata ON slc_metadata.id = swath_metadata.id
        # INNER JOIN slc_rows_metadata ON slc_rows_metadata.row_id = bursts_metadata.row_id
        # WHERE
        #        bursts_metadata.relative_orbit={rel_orbit_num} AND
        #        slc_metadata.orbit={A or D} AND
        #        slc_metadata.acquisition_start_time>=Datetime({start_time}) AND
        #        slc_metadata.acquisition_start_time<=Datetime({end_time}) AND
        #        st_intersects(
        #            GeomFromText('POLYGON(({frame_polygon}))', 4326),
        #            slc_rows_metadata.row_extent,
        #        ) = 1
        # See http://www.gaia-gis.it/gaia-sins/spatialite-sql-4.2.0.html
        # and use the Spatialite GUI to experiment with querying the db

        cursor = self.conn.cursor()
        cursor.execute(burst_query)

        initial_query_list = cursor.fetchall()  # initial query
        if not initial_query_list:
            _LOG.error(
                "Database query failed, no SLC bursts in this track intersect with frame",
                frame_num=frame_num,
                slc_metadata=args,
                burst_query=burst_query,
            )
            return

        # check if this track and frame has
        # data from all the three-subswaths
        subswath_set = set()
        poly_wkt_list = []
        for row_ in initial_query_list:
            poly_wkt_list.append(shapely.wkt.loads(row_[2]))
            subswath_set.add(row_[4])
        # Note:
        # subswath_set = {'IW1'}, {'IW2'}, {'IW3'},
        #                {'IW1','IW2'}, {'IW1','IW3'}, {'IW2','IW3'} or
        #                {'IW1','IW2','IW3'}
        #
        # --------------------------------- #
        #   Refining query to include all   #
        #   sub-swaths in a S1 aquisition   #
        # --------------------------------- #
        if len(subswath_set) != 3:
            # A constant issue faced with  bursts that intersect a
            # given frame is that sometimes only 1 or 2 sub-swaths
            # are  selected. These tracks are  then excluded later
            # in  the  workflow.  Given that  the query  logic has
            # changed  to selecting  all bursts from  those tracks
            # that intersect the frame, this check is likely to be
            # redundant. However, it will be kept just in case.
            #
            # Here, an additional query is performed to select
            # bursts from adjacent sub-swaths so that all sub-
            # swaths in the S1 acquisition are utilised.
            #
            # convert list of Polygons to Multipolygon and get the
            # convex_hull  coordinates. This is  a simple approach
            # at obtaining the boundary  of the bursts selected by
            # the initial query
            _LOG.info(
                "< 3 subswaths intersect frame, refining the database query",
                IW_set=subswath_set,
                frame_num=frame_num,
                slc_metdata=args,
            )

            bursts_chull = MultiPolygon(poly_wkt_list).convex_hull.wkt
            refined_intersect_query = (
                " AND st_intersects"
                + "(GeomFromText('{}', 4326)".format(bursts_chull)
                + ", bursts_metadata.burst_extent) = 1"
            )

            cursor2 = self.conn.cursor()
            cursor2.execute(base_query + refined_intersect_query)

            refined_query_list = cursor2.fetchall()
            if len(refined_query_list) > len(initial_query_list):
                # overwrite  extracted data from  the initial query
                # if the refined query  has more data. The  refined
                # query was coded such that it will include all the
                # bursts contained from the initial query plus any
                # additional overlapping bursts. The refined query
                # will replace/overwrite initial query as this is
                # easier than finding then appending these new
                # overlapping bursts.
                #
                # Note refined query doesn't always find additional
                # overlapping bursts
                initial_query_list = refined_query_list
            else:
                _LOG.info(
                    "refined query did not find additional overlapping bursts",
                    frame_num=frame_num,
                    slc_metdata=args,
                    refined_query=refined_intersect_query,
                )

        slc_df = pd.DataFrame(
            [[item for item in row] for row in initial_query_list],
            columns=[col[0] for col in cursor.description],
        )

        if slc_df.empty:
            _LOG.error(
                "geopandas data frame (slc_df) fail from db query",
                frame_num=frame_num,
                slc_metdata=args,
            )
            return

        geopandas_df = gpd.GeoDataFrame(
            slc_df,
            crs={"init": "epsg:4326"},
            geometry=slc_df["AsText(bursts_metadata.burst_extent)"].map(
                shapely.wkt.loads
            ),
        )
        if shapefile_name:
            geopandas_df.to_file(shapefile_name, driver="ESRI Shapefile")

        return geopandas_df

    def select_duplicates(self):
        """ returns pandas data frame of duplicate SLC in archive"""
        cursor = self.conn.cursor()
        cursor.execute("""SELECT * from slc_duplicates""")
        duplicates_df = pd.DataFrame(
            [[item for item in row] for row in cursor.fetchall()],
            columns=[col[0] for col in cursor.description],
        )
        return duplicates_df


class SlcFrame:
    """
    A class to create a Frame definition based on
    a latitude/longitude bounding box, the latitude
    width and the buffer size of the frame. The
    default values for the bounding box cover
    continental Australia.

    Parameters
    ----------

    bbox_nlat: float (default = 0.0)
        Northern latitude (decimal degrees) of bounding box

    bbox_wlon: float (default = 100.0)
        Western longitude (decimal degrees) of bounding box

    bbox_slat: float (default = -50.0)
        Southern latitude (decimal degrees) of bounding box

    bbox_elon: float (default = 179.0)
        Eastern longitude (decimal degrees) of bounding box

    width_lat: float (default = -1.25)
        latitude width (decimal degrees) of each frame

    buffer_lat: float (default = 0.01)
        The amount of overlap (decimal degrees) of adjacent frames

    Author
    ------
       Modified by Rodrigo Garcia, 15th April 2020
    """

    def __init__(
        self,
        bbox_nlat: Optional[float] = 0.0,
        bbox_wlon: Optional[float] = 100.0,
        bbox_slat: Optional[float] = -50.0,
        bbox_elon: Optional[float] = 179.0,
        width_lat: Optional[float] = -1.25,
        buffer_lat: Optional[float] = 0.01,
    ) -> None:

        self.north_lat = bbox_nlat
        self.south_lat = bbox_slat
        self.west_lon = bbox_wlon
        self.east_lon = bbox_elon
        self.width_lat = width_lat
        self.buffer_lat = buffer_lat

        # defining private variables that the user cannot see
        self._slat_frame_coords = self.get_slat_frame_coords()
        self._elat_frame_coords = self.get_elat_frame_coords()
        self._frame_numbers = np.arange(1, self._slat_frame_coords.shape[0] + 1, 1)

    @property
    def frame_numbers(self):
        # return self._frame_numbers to the user, who won't be able to modify it
        return self._frame_numbers

    @property
    def slat_frame_coords(self):
        return self._slat_frame_coords

    @property
    def elat_frame_coords(self):
        return self._elat_frame_coords

    def get_slat_frame_coords(self):
        # add self.buffer_lat after np.arange call so that
        # len(get_slat_frame_coords) = len(get_elat_frame_coords)
        return np.arange(self.north_lat, self.south_lat, self.width_lat) + self.buffer_lat

    def get_elat_frame_coords(self):
        # subtract self.buffer_lat after np.arange call so that
        # len(get_slat_frame_coords) = len(get_elat_frame_coords)
        return (
            np.arange(
                self.north_lat + self.width_lat,
                self.south_lat + self.width_lat,
                self.width_lat,
            )
            - self.buffer_lat
        )

    def get_bbox_wkt(self):
        nth_lat_frame = self.slat_frame_coords
        sth_lat_frame = self.elat_frame_coords

        df_bbox = []
        for i in range(nth_lat_frame.shape[0]):
            df_bbox.append(
                box(self.west_lon, nth_lat_frame[i], self.east_lon, sth_lat_frame[i],).wkt
            )

        return df_bbox

    def generate_frame_polygon(
        self, shapefile_name: Optional[Path] = None,
    ):
        """
        generates a frame with associated extent for the
        frame definition defined in class constructor.

        Code modified by R. Garcia to make it more generic
        """

        df = pd.DataFrame()
        df["frame_num"] = list(self.frame_numbers)
        df["extent"] = self.get_bbox_wkt()
        geopandas_df = gpd.GeoDataFrame(
            df, crs={"init": "epsg:4326"}, geometry=df["extent"].map(shapely.wkt.loads),
        )

        if geopandas_df.empty:
            _LOG.error("failed to generate frame polygon as geopandas dataframe")

        if shapefile_name:
            geopandas_df.to_file(shapefile_name, driver="ESRI Shapefile")

        return geopandas_df

    def get_frame_extent(
        self, frame_num: int,
    ):
        """ returns a geo-pandas data frame for a frame_name. """
        gpd_df = self.generate_frame_polygon()
        return gpd_df.loc[gpd_df["frame_num"] == frame_num]

    def get_frame_coords_list(
        self, frame_num: int,
    ):
        """ returns a lon,lat coordinate list for the frame number. """
        poly_shapely = self.get_bbox_wkt()[frame_num - 1]  # frame num ranges from 1 to N
        return list(shapely.wkt.loads(poly_shapely).exterior.coords)
