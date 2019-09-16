#!/usr/bin/python3

import logging
import os
from os.path import join as pjoin
import re
import subprocess
import tempfile
import xml.etree.ElementTree as etree
import zipfile as zf
import datetime
from io import BytesIO
import fnmatch
import shutil

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely.wkt
import yaml
from shapely.geometry import Polygon, box
from shapely.ops import cascaded_union
from spatialist import Vector, sqlite3, sqlite_setup
from python_scripts.xml_util import getNamespaces

_LOG = logging.getLogger(__name__)

S1_BURSTLOC = (
    "/g/data1/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-20181130/ISP/bin/S1_burstloc"
)


class SlcMetadata:
    """
    Metadata extraction class to scrap slc metadata from a sentinel-1 slc scene.
    """

    def __init__(self, scene):
        """ a default class constructor """

        self.scene = os.path.realpath(scene)
        self.pattern = (
            r"^(?P<sensor>S1[AB])_"
            r"(?P<beam>S1|S2|S3|S4|S5|S6|IW|EW|WV|EN|N1|N2|N3|N4|N5|N6|IM)_"
            r"(?P<product>SLC|GRD|OCN)(?:F|H|M|_)_"
            r"(?:1|2)"
            r"(?P<category>S|A)"
            r"(?P<pols>SH|SV|DH|DV|VV|HH|HV|VH)_"
            r"(?P<start>[0-9]{8}T[0-9]{6})_"
            r"(?P<stop>[0-9]{8}T[0-9]{6})_"
            r"(?P<orbitNumber>[0-9]{6})_"
            r"(?P<dataTakeID>[0-9A-F]{6})_"
            r"(?P<productIdentifier>[0-9A-F]{4})"
            r"\.SAFE$"
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
        if not re.match(self.pattern, os.path.basename(self.scene)):
            _LOG.info(
                "{} does not match s1 filename pattern".format(
                    os.path.basename(self.scene)
                )
            )

        self.date_fmt = "%Y%m%d"
        self.dt_fmt_1 = "%Y-%m-%d %H:%M:%S.%f"
        self.dt_fmt_2 = "%Y%m%dT%H%M%S"
        self.dt_fmt_3 = "%Y-%m-%dT%H:%M:%S.%f"

        manifest_file_list = self.find_archive_files("manifest.safe")
        assert len(manifest_file_list) == 1
        self.manifest_file = manifest_file_list[0]

        self.archive_files = None

        self.slc_metadata = self.metadata_manifest_safe()

        for item in self.slc_metadata:
            setattr(self, item, self.slc_metadata[item])

    def get_metadata(self):
        """ Consolidates meta data manifest safe file and annotation/swath xmls from a slc archive. """

        metadata = dict()

        metadata["properties"] = self.slc_metadata

        annotation_xmls = self.find_archive_files(self.pattern_ds)
        assert len(annotation_xmls) > 0

        metadata["measurements"] = dict()
        for xml_file in annotation_xmls:
            metadata["measurements"][os.path.basename(xml_file)] = self.metadata_swath(
                xml_file
            )

        return metadata

    def metadata_manifest_safe(self):
        """ Extracts metadata from a manifest safe file for a slc. """

        def __parse_datetime(dt):
            return datetime.datetime.strptime(dt, self.dt_fmt_3).strftime(self.dt_fmt_1)

        manifest_obj = self.extract_archive_member(self.manifest_file, obj=True)
        meta = dict()
        with manifest_obj as obj:
            manifest = obj.getvalue()
            namespaces = getNamespaces(manifest)
            tree = etree.fromstring(manifest)
            meta["acquisition_mode"] = tree.find(".//s1sarl1:mode", namespaces).text
            meta["acquisition_start_time"] = __parse_datetime(
                tree.find(".//safe:startTime", namespaces).text
            )
            meta["acquisition_stop_time"] = __parse_datetime(
                tree.find(".//safe:stopTime", namespaces).text
            )
            meta["coordinates"] = [
                list([float(y) for y in x.split(",")])
                for x in tree.find(".//gml:coordinates", namespaces).text.split()
            ]
            meta["crs"] = "epsg:{}".format(
                tree.find(".//safe:footPrint", namespaces)
                .attrib["srsName"]
                .split("#")[1]
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

    def metadata_swath(self, xml_file):
        """ Extracts swath and bursts metadata from a xml file for a swath in slc scene. """

        swath_meta = dict()
        swath_obj = self.extract_archive_member(xml_file, obj=True)

        def __metadata_burst(xml_path):
            def __parse_s1_burstloc(in_str):
                burst_info = dict()
                lines = in_str.split("\n")
                for line in lines:
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
                        temp_dict["coordinate"] = [
                            [float(split_line[14]), float(split_line[13])],
                            [float(split_line[16]), float(split_line[15])],
                            [float(split_line[10]), float(split_line[9])],
                            [float(split_line[12]), float(split_line[11])],
                        ]
                        burst_info[
                            "burst {}".format(temp_dict["burst_num"])
                        ] = temp_dict
                return burst_info

            with tempfile.TemporaryDirectory() as tmp_dir:
                self.extract_archive_member(xml_file, outdir=tmp_dir)
                cmd = [S1_BURSTLOC, os.path.join(tmp_dir, os.path.basename(xml_path))]
                out_str = subprocess.check_output(cmd).decode()
                return __parse_s1_burstloc(out_str)

        with swath_obj as obj:
            ann_tree = etree.fromstring(obj.read())
            swath_meta["samples"] = int(
                ann_tree.find(
                    ".//imageAnnotation/imageInformation/numberOfSamples"
                ).text
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

        burst_meta = __metadata_burst(xml_file)

        return {**swath_meta, **burst_meta}

    def archive_name_list(self):
        """ Sets archive_files with names in a slc zip archive. """

        with zf.ZipFile(self.scene, "r") as archive:
            self.archive_files = archive.namelist()

    def find_archive_files(self, pattern):
        """ Returns a matching name from a archive_file for given pattern. """

        self.archive_name_list()
        match_names = [
            name
            for name in self.archive_files
            if re.search(pattern, os.path.basename(name))
        ]
        return match_names

    def extract_archive_member(self, target_file, outdir=None, obj=False, retry=None):
        """Extracts a content of a target file from a slc zip archive as an object or a file.

        :param target_file: A 'Path' to file in a slc zip archive
        :param outdir: A 'Path' to directory where extracted file will be saved
        :param obj: A 'bol' parameter to indicate to return either object (True) or write to a file (False)
        :param retry: A 'bol' parameter to indicate if downloads need to be retried
        :return: A file object or None
        """
        archive = zf.ZipFile(self.scene, "r")

        def __archive_download(name_outfile):
            if obj:
                file_obj = BytesIO()
                file_obj.write(archive.read(target_file))
                file_obj.seek(0)
                return file_obj

            with open(name_outfile, "wb") as out_fid:
                out_fid.write(archive.read(target_file))
            return outfile

        outfile = os.path.basename(target_file)
        if outdir:
            if not os.path.exists(outdir):
                os.makedirs(outdir)

            outfile = os.path.join(outdir, os.path.basename(target_file))

        if retry is None:
            return __archive_download(outfile)

        source_size = archive.getinfo(target_file).file_size
        if os.path.exists(outfile):
            if os.path.getsize(outfile) == source_size:
                return

        retry_count = 0
        while retry_count < retry:
            if retry_count > 0:
                _LOG.info(
                    "retry download number {}/{}: {}".format(
                        retry_count, os.path.basename(target_file, str(retry))
                    )
                )

            if os.path.getsize(__archive_download(outfile)) != source_size:
                retry_count += 1
            else:
                break
            if retry_count == retry:
                _LOG.error(
                    "download failed for {}".format(os.path.basename(target_file))
                )


class S1DataDownload(SlcMetadata):
    """
    A class to download an slc data from a sentinel-1 archive.
    """

    def __init__(
        self, slc_scene, polarization, s1_orbits_poeorb_path, s1_orbits_resorb_path
    ):
        """a default class constructor."""
        self.raw_data_path = slc_scene
        self.polarization = polarization
        self.s1_orbits_poeorb_path = s1_orbits_poeorb_path
        self.s1_orbits_resorb_path = s1_orbits_resorb_path

        super(S1DataDownload, self).__init__(self.raw_data_path)
        self.archive_name_list()

    def get_poeorb_orbit_file(self):
        """A method to download precise orbit file for a slc scene."""

        _poeorb_path = os.path.join(self.s1_orbits_poeorb_path, self.sensor)
        orbit_files = [p_file for p_file in os.listdir(_poeorb_path)]
        start_datetime = datetime.datetime.strptime(
            self.acquisition_start_time, self.dt_fmt_1
        )
        start_date = (start_datetime - datetime.timedelta(days=1)).strftime(
            self.date_fmt
        )
        end_date = (start_datetime + datetime.timedelta(days=1)).strftime(self.date_fmt)

        acq_orbit_file = fnmatch.filter(
            orbit_files, "*V{}*_{}*.EOF".format(start_date, end_date)
        )

        if not acq_orbit_file:
            return
        if len(acq_orbit_file) > 1:
            acq_orbit_file = sorted(
                acq_orbit_file,
                key=lambda x: datetime.datetime.strptime(
                    x.split("_")[5], self.dt_fmt_2
                ),
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

        acq_orbit_file = fnmatch.filter(
            orbit_files, "*V{d}*_{d}*.EOF".format(d=acq_date)
        )

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
                key=lambda x: datetime.datetime.strptime(
                    x.split("_")[5], self.dt_fmt_2
                ),
            )

        return pjoin(_resorb_path, acq_orbit_file[-1])

    def slc_download(self, output_dir=None, retry=3):
        """A method to download slc raw data."""

        download_files_patterns = [
            "*measurement/*{}*".format(self.polarization.lower()),
            "*annotation/*{}*".format(self.polarization.lower()),
            "*/calibration/*{}*".format(self.polarization.lower()),
            "*/preview/quick-look.png",
            "*/preview/map-overlay.kml",
        ]

        def __archive_download(target_file):
            """ A helper method to download target file from archive"""
            out_dir = os.path.dirname(target_file)
            if output_dir:
                out_dir = os.path.join(output_dir, out_dir)
            self.extract_archive_member(target_file, outdir=out_dir, retry=retry)

        # download files from slc archive (zip) file
        files_download = sum(
            [
                fnmatch.filter(self.archive_files, pattern)
                for pattern in download_files_patterns
            ],
            [],
        )
        files_download.append(self.manifest_file)
        for fp in files_download:
            __archive_download(fp)

        # get a base slc directory where files will be downloaded
        base_dir = os.path.commonprefix(files_download)
        if output_dir:
            base_dir = os.path.join(output_dir, base_dir)

        # download orbit files with precise orbit as first choice
        orbit_source_file = self.get_poeorb_orbit_file()
        orbit_destination_file = os.path.join(
            base_dir, os.path.basename(orbit_source_file)
        )

        if not orbit_source_file:
            orbit_source_file = self.get_resorb_orbit_file()
            if not orbit_source_file:
                _LOG.error(
                    "no orbit files found for {}".format(os.path.basename(self.scene))
                )
            orbit_destination_file = os.path.join(
                base_dir, os.path.basename(orbit_source_file)
            )

        if not os.path.exists(orbit_destination_file):
            shutil.copyfile(orbit_source_file, orbit_destination_file)


class Archive:
    """
    A class to create a light-weight sqlite database to archive slc metadata and
    facilitate an automated query into a database.
    """

    def __init__(self, dbfile):
        """ A default class constructor"""

        self.dbfile = dbfile
        self.conn = sqlite_setup(self.dbfile, ["spatialite"])
        self.metadata = dict()
        self.slc_table_name = "slc_metadata"
        self.swath_table_name = "swath_metadata"
        self.bursts_table_name = "bursts_metadata"
        self.duplicate_table_name = "slc_duplicates"

        self.slc_fields_lookup = {
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

        self.swath_fields_lookup = {
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

        self.burst_fields_lookup = {
            "swath_name": "TEXT NOT NULL",
            "swath": "TEXT",
            "azimuth_time": "REAL",
            "delta_angle": "REAL",
            "burst_number": "INTEGER",
            "polarization": "TEXT",
            "relative_orbit": "INTEGER",
            "angle": "REAL",
        }

        cursor = self.conn.cursor()

        create_slc_table_string = """CREATE TABLE if not exists {} ({})""".format(
            self.slc_table_name,
            ", ".join([" ".join(x) for x in self.slc_fields_lookup.items()]),
        )
        cursor.execute(create_slc_table_string)
        if "slc_extent" not in self.get_colnames(self.slc_table_name):
            cursor.execute(
                'SELECT AddGeometryColumn("{}", "slc_extent", 4326, "POLYGON", "XY", 0)'.format(
                    self.slc_table_name
                )
            )

        create_swath_table_string = """CREATE TABLE if not exists {} ({})""".format(
            self.swath_table_name,
            ", ".join([" ".join(x) for x in self.swath_fields_lookup.items()]),
        )
        cursor.execute(create_swath_table_string)

        create_burst_table_string = """CREATE TABLE if not exists {} ({})""".format(
            self.bursts_table_name,
            ", ".join([" ".join(x) for x in self.burst_fields_lookup.items()]),
        )
        cursor.execute(create_burst_table_string)

        if "burst_extent" not in self.get_colnames(self.bursts_table_name):
            cursor.execute(
                'SELECT AddGeometryColumn("{}", "burst_extent", 4326, "POLYGON", "XY", 0)'.format(
                    self.bursts_table_name
                )
            )

        cursor.execute(
            "CREATE TABLE if not exists {} (id TEXT, url TEXT)".format(
                self.duplicate_table_name
            )
        )
        self.conn.commit()

    @property
    def primary_fieldnames(self):
        """ Sets primary fieldnames if slc metadata exists. """
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
        """ Sets properties fieldnames if slc metadata exists. """
        if self.primary_fieldnames:
            return self.primary_fieldnames["properties"]

    @property
    def measurements(self):
        """ Sets measurement fieldnames if slc metadata exists. """
        if self.primary_fieldnames:
            return self.primary_fieldnames["measurements"]

    @property
    def burst_fieldnames(self):
        """ Sets burst fieldnames if slc metadata exists. """
        if self.measurements:
            return {
                k
                for k, v in self.metadata["measurements"][self.measurements[0]][
                    "burst 1"
                ].items()
            }

    @property
    def product_id(self):
        """ Sets slc product id if slc metadata exists. """
        if self.metadata:
            return self.metadata["id"]

    @property
    def file_location(self):
        """ Sets slc file locations if slc metadata exists. """
        if self.metadata:
            return self.metadata["product"]["url"]

    def load_metadata(self, yaml_file):
        """ Loads the contents of metadata from slc yaml file"""
        with open(yaml_file, "r") as out_fid:
            self.metadata = yaml.load(out_fid)

    @staticmethod
    def get_corners(lats, lons):
        """ Returns coorner from given latitudes and longitudes. """
        return {
            "xmin": min(lons),
            "xmax": max(lons),
            "ymin": min(lats),
            "ymax": max(lats),
        }

    def get_measurement_fieldnames(self, measurement_key):
        """ Returns all the measurement fieldnames for a slc scene. """
        return {k for k, v in self.metadata["measurements"][measurement_key].items()}

    def get_measurement_metadata(self, measurement_key):
        """ Returns metadata associated with all slc measurement field names. """
        return {
            mk: mv for mk, mv in self.metadata["measurements"][measurement_key].items()
        }

    def get_slc_metadata(self):
        """ Returns a slc metadata. """
        slc_metadata = {
            key: self.metadata["properties"][key] for key in self.properties_fieldnames
        }
        slc_metadata["slc_extent"] = Polygon(
            [coord for coord in slc_metadata["coordinates"]]
        ).wkt
        return slc_metadata

    def get_burst_names(self, measurement_key):
        """ Returns all the bursts contained within a given swath measurement. """
        return [
            burst
            for burst in self.get_measurement_fieldnames(measurement_key)
            if re.match(r"burst [0-9]", burst)
        ]

    @staticmethod
    def encode_string(string, encoding="utf-8"):
        """ Encodes binary values into a string. """
        if not isinstance(string, str):
            return string.encode(encoding)
        return string

    def get_swath_bursts_metadata(self, measurement_key, burst_key=None):
        """ Returns measurement or burst metadata. """
        measurement_metadata = self.get_measurement_metadata(measurement_key)
        burst_names = self.get_burst_names(measurement_key)

        burst_metadata = dict()
        for m_field in self.get_measurement_fieldnames(measurement_key):
            m_metadata = measurement_metadata[m_field]
            if m_field in burst_names:
                burst_temp = dict()
                for name in self.burst_fieldnames:
                    burst_temp[name] = m_metadata[name]
                burst_temp["burst_extent"] = [
                    coord for coord in burst_temp["coordinate"]
                ]
                burst_metadata[m_field] = burst_temp
                del measurement_metadata[m_field]

        measurement_metadata["num_bursts"] = len(burst_names)

        if burst_key:
            return burst_metadata[burst_key]

        return measurement_metadata

    def get_tablenames(self):
        """ Returns all tables names from sqlite_master schema. """
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM sqlite_master WHERE type="table"')
        return sorted([self.encode_string(x[1]) for x in cursor.fetchall()])

    def get_colnames(self, table_name):
        """ Returns column names for a given table name. """
        cursor = self.conn.cursor()
        cursor.execute("PRAGMA table_info({})".format(table_name))
        return sorted([self.encode_string(x[1]) for x in cursor.fetchall()])

    def prepare_slc_metadata_insertion(self):
        """ Prepares to insert slc metadata into a database. """
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

        insert_string = """INSERT INTO {0}({1}) VALUES({2})""".format(
            self.slc_table_name,
            ", ".join(col_names),
            ", ".join(
                [
                    "GeomFromText(?, 4326)" if x == "slc_extent" else "?"
                    for x in col_names
                ]
            ),
        )

        return insert_string, tuple(insertion_values)

    def prepare_swath_metadata_insertion(self, measurement_key):
        """ Prepares swath metadata to be inserted into a database. """
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

        insert_string = """INSERT INTO {0}({1}) VALUES({2})""".format(
            self.swath_table_name,
            ", ".join(col_names),
            ", ".join(["?" for _ in col_names]),
        )

        return insert_string, tuple(insertion_values)

    def prepare_burst_metadata_insertion(self, measurement_key, burst_key):
        """ Prepares a burst metadata to be inserted into a database. """
        burst_metadata = self.get_swath_bursts_metadata(measurement_key, burst_key)
        col_names = self.get_colnames(self.bursts_table_name)

        insertion_values = []
        for col in col_names:
            if col == "swath_name":
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

        insert_string = """INSERT INTO {0}({1}) VALUES({2})""".format(
            self.bursts_table_name,
            ", ".join(col_names),
            ", ".join(
                [
                    "GeomFromText(?, 4326)" if x == "burst_extent" else "?"
                    for x in col_names
                ]
            ),
        )

        return insert_string, tuple(insertion_values)

    def archive_scene(self, yaml_file):
        """ Archives a slc scene and its associated metadata from a yaml file into a database"""

        self.load_metadata(yaml_file)
        cursor = self.conn.cursor()
        slc_str, slc_vals = self.prepare_slc_metadata_insertion()

        try:
            cursor.execute(slc_str, slc_vals)
        except sqlite3.IntegrityError as err:
            if str(err) == "UNIQUE constraint failed: {}.id".format(
                self.slc_table_name
            ):
                _LOG.info(
                    "{} already ingested into the database".format(
                        os.path.basename(yaml_file)
                    )
                )
                return
            else:
                raise err

        for measurement in self.measurements:
            swath_str, swath_vals = self.prepare_swath_metadata_insertion(measurement)
            try:
                cursor.execute(swath_str, swath_vals)
            except sqlite3.IntegrityError as err:
                if str(err) == "UNIQUE constraint failed: {}.swath_name".format(
                    self.swath_table_name
                ):
                    _LOG.info(
                        "{} duplicates is detected".format(os.path.basename(yaml_file))
                    )
                    self.archive_duplicate(yaml_file)
                    return
                else:
                    raise err

            burst_keys = self.get_burst_names(measurement)
            for burst_key in burst_keys:
                burst_str, burst_vals = self.prepare_burst_metadata_insertion(
                    measurement, burst_key
                )
                cursor.execute(burst_str, burst_vals)
        self.conn.commit()

    def archive_duplicate(self, yaml_file):
        """ Archive duplicate slc scenes. """
        self.load_metadata(yaml_file)
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO slc_duplicates(id, url) VALUES(?, ?)",
            (self.product_id, self.file_location),
        )
        self.conn.commit()

    def __enter__(self):
        """ Returns Archive class object. """
        return self

    def close(self):
        """ Ensures db connection is closed. """
        self.conn.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """ Closes a Archive class. """
        self.close()

    def select(
        self,
        tables_join_string,
        orbit,
        track,
        spatial_subset=None,
        args=None,
        min_date_arg=None,
        max_date_arg=None,
        columns=None,
    ):
        """ Returns geo-pandas data frame of from the database of selected SLC. """

        if not columns:
            columns = ["slc_metadata.slc_extent", "bursts_metadata.burst_extent"]
            for key in self.slc_fields_lookup.keys():
                columns.append("{}.{}".format(self.slc_table_name, key))
            for key in self.swath_fields_lookup.keys():
                columns.append("{}.{}".format(self.swath_table_name, key))
            for key in self.burst_fields_lookup.keys():
                columns.append("{}.{}".format(self.bursts_table_name, key))
        if args:
            arg_format = ["{0}='{1}'".format(key, args[key]) for key in args.keys()]
        else:
            arg_format = []

        arg_format.append("{}.orbit='{}'".format(self.slc_table_name, orbit))
        arg_format.append("{}.orbitNumber_rel= {}".format(self.slc_table_name, track))

        if spatial_subset:
            # spatial query checks selects data only if centroid of burst extent is
            # inside a spatial vector. Spatial subset should be a instance of a Vector
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

        if min_date_arg:
            arg_format.append(min_date_arg)
        if max_date_arg:
            arg_format.append(max_date_arg)

        query = """SELECT {0} from {1} WHERE {2}""".format(
            ", ".join(
                [
                    "AsText({})".format(col) if "extent" in col else col
                    for col in columns
                ]
            ),
            tables_join_string,
            " AND ".join(arg_format),
        )
        cursor = self.conn.cursor()
        cursor.execute(query)

        slc_df = pd.DataFrame(
            [[item for item in row] for row in cursor.fetchall()],
            columns=[col[0] for col in cursor.description],
        )
        if slc_df.empty:
            return
        return slc_df

    def select_duplicates(self):
        """ Returns pandas data frame of duplicate SLC in archive"""
        cursor = self.conn.cursor()
        cursor.execute("""SELECT * from slc_duplicates""")
        duplicates_df = pd.DataFrame(
            [[item for item in row] for row in cursor.fetchall()],
            columns=[col[0] for col in cursor.description],
        )
        return duplicates_df


class SlcFrame:
    """
    A class to create a Frame definition based on latitude width and
    the buffer size. It is hard corded to start from latitude
    of 0.0 to 50 in the southern hemisphere and longitude 100 to 179.0.
    """

    def __init__(self, width_lat=None, buffer_lat=None):
        """ A default class constructor. """
        self.southern_hemisphere = True
        self.start_lat = 0.0
        self.end_lat = 50.0
        self.start_lon = 100.0
        self.end_lon = 179.0
        if width_lat is None:
            self.width_lat = 1.1
        else:
            self.width_lat = width_lat
        if buffer_lat is None:
            self.buffer_lat = 0.01
        else:
            self.buffer_lat = buffer_lat

    def generate_frame_polygon(self, shapefile_name=None):
        """ Generates a frame with associated extent for the frame definition defined in class constructor. """
        latitudes = [
            i
            for i in np.arange(
                self.start_lat, self.end_lat + self.width_lat, self.width_lat
            )
        ]
        start_lats = [lat - self.buffer_lat for lat in latitudes]
        end_lats = [lat + self.buffer_lat for _, lat in enumerate(latitudes[1:])]

        if self.southern_hemisphere:
            start_lats = np.array(start_lats) * -1.0
            end_lats = np.array(end_lats) * -1.0

        df = pd.DataFrame()
        df["frame"] = ["Frame_{:02}".format(i + 1) for i in range(len(start_lats) - 1)]
        df["extent"] = [
            box(self.start_lon, start_lat, self.end_lon, end_lats[idx]).wkt
            for idx, start_lat in enumerate(start_lats[:-1])
        ]
        geopandas_df = gpd.GeoDataFrame(
            df, crs={"init": "epsg:4326"}, geometry=df["extent"].map(shapely.wkt.loads)
        )

        if shapefile_name:
            geopandas_df.to_file(shapefile_name, driver="ESRI Shapefile")
        return geopandas_df

    def get_frame_extent(self, frame_name):
        """ Returns a geo-pandas data frame for a frame_name."""
        gpd_df = self.generate_frame_polygon()
        return gpd_df.loc[gpd_df["frame"] == frame_name]


if __name__ == "__main__":
    slc = "/g/data/fj7/Copernicus/Sentinel-1/C-SAR/SLC/2019/2019-06/30S145E-35S150E//S1A_IW_SLC__1SDV_20190630T193933_20190630T194000_027913_0326C8_0037.zip"
    poeorb_path = "/g/data/fj7/Copernicus/Sentinel-1/POEORB"
    resorb_path = "/g/data/fj7/Copernicus/Sentinel-1/RESORB"
    s1_obj = S1DataDownload(slc, "VV", poeorb_path, resorb_path)
    s1_obj.slc_download(output_dir="/g/data/u46/users/pd1813/INSAR/temp_raw_data")
    # f = s1_obj.get_resorb_orbit_file()
    # print(f)
