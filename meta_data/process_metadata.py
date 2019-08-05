#!/usr/bin/python3

import os
from io import BytesIO
import logging
from datetime import datetime
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import uuid
import geopandas as gpd
import shapely.wkt
from shapely.geometry import Polygon
from multiprocessing import Pool as ProcessPool
import zipfile as zf
import yaml
import pandas as pd

from xml_util import getNamespaces
from spatialist.ancillary import finder
from spatialist import sqlite_setup, crsConvert, sqlite3, ogr2ogr, Vector, bbox

logging.basicConfig(filename='error.log', level=logging.INFO)

S1_BURSTLOC = "/g/data1/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-20181130/ISP/bin/S1_burstloc"


class S1SLC:

    def __init__(self, scene):
        self.scene = os.path.realpath(scene)
        self.manifest = 'manifest.safe'
        self.pattern = r'^(?P<sensor>S1[AB])_' \
                       r'(?P<beam>S1|S2|S3|S4|S5|S6|IW|EW|WV|EN|N1|N2|N3|N4|N5|N6|IM)_' \
                       r'(?P<product>SLC|GRD|OCN)(?:F|H|M|_)_' \
                       r'(?:1|2)' \
                       r'(?P<category>S|A)' \
                       r'(?P<pols>SH|SV|DH|DV|VV|HH|HV|VH)_' \
                       r'(?P<start>[0-9]{8}T[0-9]{6})_' \
                       r'(?P<stop>[0-9]{8}T[0-9]{6})_' \
                       r'(?P<orbitNumber>[0-9]{6})_' \
                       r'(?P<dataTakeID>[0-9A-F]{6})_' \
                       r'(?P<productIdentifier>[0-9A-F]{4})' \
                       r'\.SAFE$'

        self.pattern_ds = r'^s1[ab]-' \
                          r'(?P<swath>s[1-6]|iw[1-3]?|ew[1-5]?|wv[1-2]|n[1-6])-' \
                          r'(?P<product>slc|grd|ocn)-' \
                          r'(?P<pol>hh|hv|vv|vh)-' \
                          r'(?P<start>[0-9]{8}t[0-9]{6})-' \
                          r'(?P<stop>[0-9]{8}t[0-9]{6})-' \
                          r'(?:[0-9]{6})-(?:[0-9a-f]{6})-' \
                          r'(?P<id>[0-9]{3})' \
                          r'\.xml$'
        self.archive_files = None

    def get_metadata(self):
        metadata = dict()
        manifest_file = self.find_archive_files(self.manifest)
        assert len(manifest_file) == 1

        metadata['properties'] = self.metadata_manifest_safe(manifest_file[0])

        annotation_xmls = self.find_archive_files(self.pattern_ds)
        assert len(annotation_xmls) > 0

        metadata['measurements'] = dict()
        for xml_file in annotation_xmls:
            metadata['measurements'][os.path.basename(xml_file)] = self.metadata_swath(xml_file)

        return metadata

    def metadata_manifest_safe(self, manifest_file):
        def __parse_datetime(dt):
            return datetime.strptime(dt, '%Y-%m-%dT%H:%M:%S.%f').strftime('%Y-%m-%d %H:%M:%S.%f')

        manifest_obj = self.extract_archive_member(manifest_file, obj=True)
        meta = dict()
        with manifest_obj as obj:
            manifest = obj.getvalue()
            namespaces = getNamespaces(manifest)
            tree = ET.fromstring(manifest)
            meta['acquisition_mode'] = tree.find('.//s1sarl1:mode', namespaces).text
            meta['acquisition_start_time'] = __parse_datetime(tree.find('.//safe:startTime', namespaces).text)
            meta['acquisition_stop_time'] = __parse_datetime(tree.find('.//safe:stopTime', namespaces).text)
            meta['coordinates'] = [list([float(y) for y in x.split(',')]) for x in
                                   tree.find('.//gml:coordinates', namespaces).text.split()]
            meta['crs'] = 'epsg:{}'.format(tree.find('.//safe:footPrint', namespaces).attrib['srsName'].split('#')[1])
            meta['orbit'] = tree.find('.//s1:pass', namespaces).text[0]

            meta['orbitNumber_abs'] = int(tree.find('.//safe:orbitNumber[@type="start"]', namespaces).text)
            meta['orbitNumber_rel'] = int(tree.find('.//safe:relativeOrbitNumber[@type="start"]', namespaces).text)
            meta['cycleNumber'] = int(tree.find('.//safe:cycleNumber', namespaces).text)
            meta['frameNumber'] = int(tree.find('.//s1sarl1:missionDataTakeID', namespaces).text)
            meta['orbitNumbers_abs'] = dict(
                [(x, int(tree.find('.//safe:orbitNumber[@type="{0}"]'.format(x), namespaces).text)) for x in
                 ['start', 'stop']])
            meta['orbitNumbers_rel'] = dict(
                [(x, int(tree.find('.//safe:relativeOrbitNumber[@type="{0}"]'.format(x), namespaces).text)) for x in
                 ['start', 'stop']])
            meta['polarizations'] = [x.text for x in
                                     tree.findall('.//s1sarl1:transmitterReceiverPolarisation', namespaces)]
            meta['product'] = tree.find('.//s1sarl1:productType', namespaces).text
            meta['category'] = tree.find('.//s1sarl1:productClass', namespaces).text
            meta['sensor'] = tree.find('.//safe:familyName', namespaces).text.replace('ENTINEL-', '') + tree.find(
                './/safe:number', namespaces).text
            meta['IPF_version'] = float(tree.find('.//safe:software', namespaces).attrib['version'])
            meta['sliceNumber'] = int(tree.find('.//s1sarl1:sliceNumber', namespaces).text)
            meta['totalSlices'] = int(tree.find('.//s1sarl1:totalSlices', namespaces).text)

        return meta

    def metadata_swath(self, xml_file):
        swath_meta = dict()
        swath_obj = self.extract_archive_member(xml_file, obj=True)

        def __metadata_burst(xml_path):
            def __parse_s1_burstloc(in_str):
                burst_info = dict()
                lines = in_str.split('\n')
                for line in lines:
                    if line.startswith('Burst'):
                        split_line = line.split()
                        temp_dict = dict()
                        temp_dict['burst_num'] = int(split_line[2])
                        temp_dict['rel_orbit'] = int(split_line[3])
                        temp_dict['swath'] = split_line[4]
                        temp_dict['polarization'] = split_line[5]
                        temp_dict['azimuth_time'] = float(split_line[6])
                        temp_dict['angle'] = float(split_line[7])
                        temp_dict['delta_angle'] = float(split_line[8])
                        temp_dict['coordinate'] = [[float(split_line[14]), float(split_line[13])],
                                                   [float(split_line[16]), float(split_line[15])],
                                                   [float(split_line[10]), float(split_line[9])],
                                                   [float(split_line[12]), float(split_line[11])]]
                        burst_info['burst {}'.format(temp_dict['burst_num'])] = temp_dict
                return burst_info

            with tempfile.TemporaryDirectory() as tmp_dir:
                self.extract_archive_member(xml_file, outdir=tmp_dir)
                cmd = [S1_BURSTLOC, os.path.join(tmp_dir, os.path.basename(xml_path))]
                out_str = subprocess.check_output(cmd).decode()
                return __parse_s1_burstloc(out_str)

        with swath_obj as obj:
            ann_tree = ET.fromstring(obj.read())
            swath_meta['samples'] = int(ann_tree.find('.//imageAnnotation/imageInformation/numberOfSamples').text)
            swath_meta['lines'] = int(ann_tree.find('.//imageAnnotation/imageInformation/numberOfLines').text)
            swath_meta['spacing'] = list([float(ann_tree.find('.//{}PixelSpacing'.format(dim)).text)
                                          for dim in ['range', 'azimuth']])
            heading = float(ann_tree.find('.//platformHeading').text)
            swath_meta['heading'] = heading if heading > 0 else heading + 360
            swath_meta['incidence'] = float(ann_tree.find('.//incidenceAngleMidSwath').text)
            swath_meta['image_geometry'] = ann_tree.find('.//projection').text.replace(' ', '_').upper()

        burst_meta = __metadata_burst(xml_file)

        return {**swath_meta, **burst_meta}

    def archive_name_list(self):
        with zf.ZipFile(self.scene, 'r') as archive:
            self.archive_files = archive.namelist()

    def find_archive_files(self, pattern):
        self.archive_name_list()
        match_names = [name for name in self.archive_files if re.search(pattern, os.path.basename(name))]
        return match_names

    def extract_archive_member(self, target_file, outdir=None, obj=False):
        with zf.ZipFile(self.scene, 'r') as archive:
            if obj:
                file_obj = BytesIO()
                file_obj.write(archive.read(target_file))
                file_obj.seek(0)
                return file_obj
            if outdir:
                outfile = os.path.join(outdir, os.path.basename(target_file))
            with open(outfile, 'wb') as out_fid:
                out_fid.write(archive.read(target_file))
            return None


class Archive:

    def __init__(self, dbfile):
        self.dbfile = dbfile
        self.conn = sqlite_setup(self.dbfile, ['spatialite'])
        self.metadata = dict()
        self.slc_table_name = "slc_metadata"
        self.swath_table_name = "swath_metadata"
        self.bursts_table_name = "bursts_metadata"
        self.duplicate_table_name = "slc_duplicates"

        self.slc_fields_lookup = {'id': 'TEXT PRIMARY KEY',
                                  'url': 'TEXT',
                                  'IPF_version': 'TEXT',
                                  'acquisition_mode': 'TEXT',
                                  'acquisition_start_time': 'TEXT',
                                  'acquisition_stop_time': 'TEXT',
                                  'category': 'TEXT',
                                  'crs': 'TEXT',
                                  'cycleNumber': 'INTEGER',
                                  'frameNumber': 'INTEGER',
                                  'orbit': 'TEXT',
                                  'orbitNumber_abs': 'INTEGER',
                                  'orbitNumber_rel': 'INTEGER',
                                  'orbitNumbers_abs_start': 'INTEGER',
                                  'orbitNumbers_abs_stop': 'INTEGER',
                                  'hh': 'INTEGER',
                                  'vv': 'INTEGER',
                                  'hv': 'INTEGER',
                                  'vh': 'INTEGER',
                                  'product': 'TEXT',
                                  'sensor': 'TEXT',
                                  'sliceNumber': 'INTEGER',
                                  'totalSlices': 'INTEGER'}

        self.swath_fields_lookup = {'swath_name': 'TEXT PRIMARY KEY',
                                    'id': 'TEXT NOT NULL',
                                    'heading': 'REAL',
                                    'incidence': 'REAL',
                                    'lines': 'INTEGER',
                                    'samples': 'INTEGER',
                                    'range_spacing': 'REAL',
                                    'azimuth_spacing': 'REAL',
                                    'total_bursts': 'INTEGER',
                                    }

        self.burst_fields_lookup = {'swath_name': 'TEXT NOT NULL',
                                    'swath': 'TEXT',
                                    'azimuth_time': 'REAL',
                                    'delta_angle': 'REAL',
                                    'burst_number': 'INTEGER',
                                    'polarization': 'TEXT',
                                    'relative_orbit': 'INTEGER',
                                    'angle': 'REAL',
                                    }

        cursor = self.conn.cursor()

        create_slc_table_string = '''CREATE TABLE if not exists {} ({})'''\
            .format(self.slc_table_name, ', '.join([' '.join(x) for x in self.slc_fields_lookup.items()]))
        cursor.execute(create_slc_table_string)
        if 'slc_extent' not in self.get_colnames(self.slc_table_name):
            cursor.execute('SELECT AddGeometryColumn("{}", "slc_extent", 4326, "POLYGON", "XY", 0)'
                           .format(self.slc_table_name))

        create_swath_table_string = '''CREATE TABLE if not exists {} ({})'''\
            .format(self.swath_table_name, ', '.join([' '.join(x) for x in self.swath_fields_lookup.items()]))
        cursor.execute(create_swath_table_string)

        create_burst_table_string = '''CREATE TABLE if not exists {} ({})'''\
            .format(self.bursts_table_name, ', '.join([' '.join(x) for x in self.burst_fields_lookup.items()]))
        cursor.execute(create_burst_table_string)

        if 'burst_extent' not in self.get_colnames(self.bursts_table_name):
            cursor.execute('SELECT AddGeometryColumn("{}", "burst_extent", 4326, "POLYGON", "XY", 0)'
                           .format(self.bursts_table_name))

        cursor.execute('CREATE TABLE if not exists {} (id TEXT, url TEXT)'.format(self.duplicate_table_name))
        self.conn.commit()

    @property
    def primary_fieldnames(self):
        if self.metadata:
            return {**{'id': 'id'}, **{pk: [k for k, v in self.metadata[pk].items()] for
                                       pk in ['product', 'measurements', 'properties']}}

    @property
    def properties_fieldnames(self):
        if self.primary_fieldnames:
            return self.primary_fieldnames['properties']

    @property
    def measurements(self):
        if self.primary_fieldnames:
            return self.primary_fieldnames['measurements']

    @property
    def burst_fieldnames(self):
        if self.measurements:
            return {k for k, v in self.metadata['measurements'][self.measurements[0]]['burst 1'].items()}

    @property
    def product_id(self):
        if self.metadata:
            return self.metadata['id']

    @property
    def file_location(self):
        if self.metadata:
            return self.metadata['product']['url']

    def load_metadata(self, yaml_file):
        with open(yaml_file, 'r') as out_fid:
            self.metadata = yaml.load(out_fid)

    @staticmethod
    def get_corners(lats, lons):
        return {'xmin': min(lons), 'xmax': max(lons), 'ymin': min(lats), 'ymax': max(lats)}

    def get_measurement_fieldnames(self, measurement_key):
        return {k for k, v in self.metadata['measurements'][measurement_key].items()}

    def get_measurement_metadata(self, measurement_key):
        return {mk: mv for mk, mv in self.metadata['measurements'][measurement_key].items()}

    def get_slc_metadata(self):
        slc_metadata = {key: self.metadata['properties'][key] for key in self.properties_fieldnames}
        slc_metadata['slc_extent'] = Polygon([coord for coord in slc_metadata['coordinates']]).wkt
        return slc_metadata

    def get_burst_names(self, measurement_key):
        return [burst for burst in self.get_measurement_fieldnames(measurement_key) if re.match(r'burst [0-9]', burst)]

    @staticmethod
    def encode_string(string, encoding='utf-8'):
        if not isinstance(string, str):
            return string.encode(encoding)
        return string

    def get_swath_bursts_metadata(self, measurement_key, burst_key=None):
        measurement_metadata = self.get_measurement_metadata(measurement_key)
        burst_names = self.get_burst_names(measurement_key)

        burst_metadata = dict()
        for m_field in self.get_measurement_fieldnames(measurement_key):
            m_metadata = measurement_metadata[m_field]
            if m_field in burst_names:
                burst_temp = dict()
                for name in self.burst_fieldnames:
                    burst_temp[name] = m_metadata[name]
                burst_temp['burst_extent'] = Polygon([coord for coord in burst_temp['coordinate']]).wkt
                burst_metadata[m_field] = burst_temp
                del measurement_metadata[m_field]
        measurement_metadata['num_bursts'] = len(burst_names)

        if burst_key:
            return burst_metadata[burst_key]

        return measurement_metadata

    def get_tablenames(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM sqlite_master WHERE type="table"')
        return sorted([self.encode_string(x[1]) for x in cursor.fetchall()])

    def get_colnames(self, table_name):
        cursor = self.conn.cursor()
        cursor.execute('PRAGMA table_info({})'.format(table_name))
        return sorted([self.encode_string(x[1]) for x in cursor.fetchall()])

    def prepare_slc_metadata_insertion(self):
        slc_metadata = self.get_slc_metadata()
        polarizations = [pol.lower() for pol in slc_metadata['polarizations']]
        col_names = self.get_colnames(self.slc_table_name)
        insertion_values = []
        for col in col_names:
            if col in ['hh', 'hv', 'vv', 'vh']:
                if col in polarizations:
                    insertion_values.append(1)
                else:
                    insertion_values.append(0)
            elif col == 'id':
                insertion_values.append(self.product_id)
            elif col == 'orbitNumbers_abs_start':
                insertion_values.append(slc_metadata['orbitNumbers_abs']['start'])
            elif col == 'orbitNumbers_abs_stop':
                insertion_values.append(slc_metadata['orbitNumbers_abs']['stop'])
            elif col == 'url':
                insertion_values.append(self.file_location)
            else:
                insertion_values.append(slc_metadata[col])

        insert_string = '''INSERT INTO {0}({1}) VALUES({2})'''\
            .format(self.slc_table_name, ', '.join(col_names), ', '
                    .join(['GeomFromText(?, 4326)' if x == 'slc_extent' else '?' for x in col_names]))

        return insert_string, tuple(insertion_values)

    def prepare_swath_metadata_insertion(self, measurement_key):
        measurement_metadata = self.get_swath_bursts_metadata(measurement_key)
        col_names = self.get_colnames(self.swath_table_name)
        insertion_values = []
        for col in col_names:
            if col == 'id':
                insertion_values.append(self.product_id)
            elif col == 'swath_name':
                insertion_values.append(measurement_key)
            elif col == 'range_spacing':
                insertion_values.append(measurement_metadata['spacing'][0])
            elif col == 'azimuth_spacing':
                insertion_values.append(measurement_metadata['spacing'][1])
            elif col == 'total_bursts':
                insertion_values.append(measurement_metadata['num_bursts'])
            else:
                insertion_values.append(measurement_metadata[col])

        insert_string = '''INSERT INTO {0}({1}) VALUES({2})'''\
            .format(self.swath_table_name, ', '.join(col_names), ', '.join(['?' for x in col_names]))

        return insert_string, tuple(insertion_values)

    def prepare_burst_metadata_insertion(self, measurement_key, burst_key):

        burst_metadata = self.get_swath_bursts_metadata(measurement_key, burst_key)
        col_names = self.get_colnames(self.bursts_table_name)
        insertion_values = []
        for col in col_names:
            if col == 'swath_name':
                insertion_values.append(measurement_key)
            elif col == 'burst_number':
                insertion_values.append(burst_metadata['burst_num'])
            elif col == 'relative_orbit':
                insertion_values.append(burst_metadata['rel_orbit'])
            else:
                insertion_values.append(burst_metadata[col])

        insert_string = '''INSERT INTO {0}({1}) VALUES({2})'''\
            .format(self.bursts_table_name, ', '.join(col_names), ', '
                    .join(['GeomFromText(?, 4326)' if x == 'burst_extent' else '?' for x in col_names]))

        return insert_string, tuple(insertion_values)

    def archive_scene(self, yaml_file):

        self.load_metadata(yaml_file)
        cursor = self.conn.cursor()
        slc_str, slc_vals = self.prepare_slc_metadata_insertion()

        try:
            cursor.execute(slc_str, slc_vals)
        except sqlite3.IntegrityError as err:
            if str(err) == 'UNIQUE constraint failed: {}.id'.format(self.slc_table_name):
                logging.info('{} already ingested into the database'.format(os.path.basename(yaml_file)))
            else:
                raise err

        for measurement in self.measurements:
            swath_str, swath_vals = self.prepare_swath_metadata_insertion(measurement)
            try:
                cursor.execute(swath_str, swath_vals)
            except sqlite3.IntegrityError as err:
                if str(err) == 'UNIQUE constraint failed: {}.swath_name'.format(self.swath_table_name):
                    logging.info('{} duplicates is detected'.format(os.path.basename(yaml_file)))
                    self.archive_duplicate(yaml_file)
                else:
                    raise err

            burst_keys = self.get_burst_names(measurement)
            for burst_key in burst_keys:
                burst_str, burst_vals = self.prepare_burst_metadata_insertion(measurement, burst_key)
                cursor.execute(burst_str, burst_vals)
        self.conn.commit()

    def archive_duplicate(self, yaml_file):
        self.load_metadata(yaml_file)
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO slc_duplicates(id, url) VALUES(?, ?)', (self.product_id, self.file_location))
        self.conn.commit()

    def __enter__(self):
        return self

    def close(self):
        self.conn.close()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def select(self, args, tables_join_string,
               min_date_arg=None,
               max_date_arg=None,
               columns=None,
               shapefile_name=None):

        if not columns:
            columns = ['slc_metadata.slc_extent', 'bursts_metadata.burst_extent']
            for key in self.slc_fields_lookup.keys():
                columns.append('{}.{}'.format(self.slc_table_name, key))
            for key in self.swath_fields_lookup.keys():
                columns.append('{}.{}'.format(self.swath_table_name, key))
            for key in self.burst_fields_lookup.keys():
                columns.append('{}.{}'.format(self.bursts_table_name, key))

        arg_format = ["{0}='{1}'".format(key, args[key]) for key in args.keys()]

        if min_date_arg:
            arg_format.append(min_date_arg)
        if max_date_arg:
            arg_format.append(max_date_arg)

        query = ('''SELECT {0} from {1} WHERE {2}'''.format(
                 ', '.join(['AsText({})'.format(col) if 'extent' in col else col for col in columns]),
                 tables_join_string, ' AND '.join(arg_format)))
        cursor = self.conn.cursor()
        cursor.execute(query)

        df = pd.DataFrame([[item for item in row] for row in cursor.fetchall()],
                          columns=[col[0] for col in cursor.description])
        print(df.head())
        if shapefile_name:
            crs = {'init': 'epsg:4326'}
            geopandas_df = gpd.GeoDataFrame(df, crs=crs,
                                            geometry=df['AsText(bursts_metadata.burst_extent)'].map(shapely.wkt.loads))
            geopandas_df.to_file(shapefile_name, driver='ESRI Shapefile')
        else:
            return df

    def select_duplicates(self):
        cursor = self.conn.cursor()
        cursor.execute('''SELECT * from slc_duplicates''')
        df = pd.DataFrame([[item for item in row] for row in cursor.fetchall()],
                          columns=[col[0] for col in cursor.description])
        print(df.head())
        return df


class DummyPool:

    def __enter__(self):
        return self

    def starmap(self, func, args):
        return [func(*arg) for arg in args]


def pool(processes):
    if not processes:
        return DummyPool()
    return ProcessPool(processes=processes)


def generate_slc_yaml(year=None, month=None, s1_dir=None, out_dir=None):
    path1 = os.path.join(s1_dir, '{:04}'.format(year), '{:04}-{:02}'.format(year, month))
    if not os.path.exists(path1):
        return

    for grid in os.listdir(path1):
        if not re.match(r'[0-9]', grid):
            continue
        else:
            s1_path = os.path.join(path1, grid)
            scenes_s1 = finder(str(s1_path), [r'^S1[AB]_IW_SLC.*\.zip'], regex=True, recursive=True)
            for scene in scenes_s1:
                scene_obj = S1SLC(scene)
                slc_metadata = scene_obj.get_metadata()
                slc_metadata['id'] = str(uuid.uuid4())
                slc_metadata['product'] = {'name': 'ESA_S1_{}'.format(slc_metadata['properties']['product']),
                                           'url': scene_obj.scene}
                if not os.path.exists(out_dir):
                    os.makedirs(out_dir)
                with open(os.path.join(out_dir, '{}.yaml'.format(os.path.basename(scene)[:-4])), 'w') as out_fid:
                    yaml.dump(slc_metadata, out_fid)


def process_yaml_generation(years=None, nprocs=1, s1_dir=None, out_dir=None):

    if not years:
        return
    with pool(processes=nprocs) as proc:
        proc.starmap(generate_slc_yaml, [(year, mnt, s1_dir, out_dir) for year in years for mnt in range(1, 13)])


def process_query(dbfile):

    with Archive(dbfile) as archive:
        tables_join_string = '{0} INNER JOIN {1} on {0}.swath_name = {1}.swath_name INNER JOIN {2} on {2}.id = {1}.id'\
            .format(archive.bursts_table_name, archive.swath_table_name, archive.slc_table_name)
        bursts_query_args = {'{}.product'.format(archive.slc_table_name): 'SLC'}

        columns = ['{}.burst_number'.format(archive.bursts_table_name),
                   '{}.burst_extent'.format(archive.bursts_table_name),
                   '{}.swath_name'.format(archive.swath_table_name),
                   '{}.orbit'.format(archive.slc_table_name),
                   '{}.acquisition_start_time'.format(archive.slc_table_name),
                   '{}.url'.format(archive.slc_table_name)]

        start_date = '2018-12-12 00:00:00'
        end_date = '2018-12-31 00:00:00'

        min_date_arg = '{}.acquisition_start_time>=Datetime("{}")'.format(archive.slc_table_name, start_date)
        max_date_arg = '{}.acquisition_start_time<=Datetime("{}")'.format(archive.slc_table_name, end_date)

        archive.select(bursts_query_args, tables_join_string, min_date_arg=None, max_date_arg=None, columns=None)

        archive.select_duplicates()


def s1_slc_ingestion(dbfile, yaml_dir):
    for yaml_file in os.listdir(yaml_dir):
        print('inserting {}'.format(yaml_file))
        archive = Archive(dbfile)
        archive.archive_scene(os.path.join(yaml_dir, yaml_file))


if __name__ == '__main__':

    # process_yaml_generation(years=[2014, 2015, 2016, 2017, 2018, 2019],
    #                         nprocs=16,
    #                         out_dir='/g/data/u46/users/pd1813/INSAR/Sentinel1_yamls',
    #                         s1_dir='/g/data1/fj7/Copernicus/Sentinel-1/C-SAR/SLC/')

    yaml_dir = '/g/data/u46/users/pd1813/INSAR/S1_YAML'
    database_name = '/g/data/u46/users/pd1813/INSAR/VICTORIA_S1_SLC_DATABASE_V2.db'
    s1_slc_ingestion(database_name, yaml_dir)
    process_query(database_name)



