#!/usr/bin/python

import os
from os.path import join as pjoin, abspath, dirname, exists, basename
import shutil
import tempfile
import unittest
import fnmatch
import zipfile
import datetime 

import test_check_status as checkstatus

from python_scripts import raw_data_extract
from python_scripts.constant import SAFE_FMT, S1_SOURCE_DIR_FMT, DATE_FMT

DATA_DIR = pjoin(dirname(abspath(__file__)), 'data')


class TestRawDataExtract(unittest.TestCase):

    """
    Test the various functions contained in python_scripts.check_status module.
    """

    def setUp(self):
        """
        Creates a temporary directory.
        """
        self.test_dir = tempfile.mkdtemp()
        self.raw_data = raw_data_extract.S1DataDownload()
        self.test_archive = None
        self.granule = 'S1A_IW_SLC__1SDV_20170712T192147_20170712T192214_017442_01D25D_FB1F'
        self.grid = '25S150E-30S155E'
        self.dt = '20170712'
        self.content = '20170712 25S150E-30S155E {}'.format(self.granule)

        self.files = {self.granule:
                          {'annotation_calibration':
                               ['calibration-s1a-iw1-slc-vh-20170712t192149-20170712t192214-017442-01d25d-001.xml',
                                'calibration-s1a-iw1-slc-vv-20170712t192149-20170712t192214-017442-01d25d-004.xml',
                                'calibration-s1a-iw2-slc-vh-20170712t192147-20170712t192212-017442-01d25d-002.xml',
                                'calibration-s1a-iw2-slc-vv-20170712t192147-20170712t192212-017442-01d25d-005.xml',
                                'calibration-s1a-iw3-slc-vh-20170712t192148-20170712t192213-017442-01d25d-003.xml',
                                'calibration-s1a-iw3-slc-vv-20170712t192148-20170712t192213-017442-01d25d-006.xml',
                                'noise-s1a-iw1-slc-vh-20170712t192149-20170712t192214-017442-01d25d-001.xml',
                                'noise-s1a-iw1-slc-vv-20170712t192149-20170712t192214-017442-01d25d-004.xml',
                                'noise-s1a-iw2-slc-vh-20170712t192147-20170712t192212-017442-01d25d-002.xml',
                                'noise-s1a-iw2-slc-vv-20170712t192147-20170712t192212-017442-01d25d-005.xml',
                                'noise-s1a-iw3-slc-vh-20170712t192148-20170712t192213-017442-01d25d-003.xml',
                                'noise-s1a-iw3-slc-vv-20170712t192148-20170712t192213-017442-01d25d-006.xml'],

                           'annotation': ['s1a-iw1-slc-vh-20170712t192149-20170712t192214-017442-01d25d-001.xml',
                                          's1a-iw1-slc-vv-20170712t192149-20170712t192214-017442-01d25d-004.xml',
                                          's1a-iw2-slc-vh-20170712t192147-20170712t192212-017442-01d25d-002.xml',
                                          's1a-iw2-slc-vv-20170712t192147-20170712t192212-017442-01d25d-005.xml',
                                          's1a-iw3-slc-vh-20170712t192148-20170712t192213-017442-01d25d-003.xml',
                                          's1a-iw3-slc-vv-20170712t192148-20170712t192213-017442-01d25d-006.xml'],
                           'manifest': ['manifest.safe'],
                           'preview': ['map-overlay.kml', 'quick-look.png'],
                           'measurement': ['s1a-iw1-slc-vh-20170712t192149-20170712t192214-017442-01d25d-001.tiff',
                                           's1a-iw1-slc-vv-20170712t192149-20170712t192214-017442-01d25d-004.tiff',
                                           's1a-iw2-slc-vh-20170712t192147-20170712t192212-017442-01d25d-002.tiff',
                                           's1a-iw2-slc-vv-20170712t192147-20170712t192212-017442-01d25d-005.tiff',
                                           's1a-iw3-slc-vh-20170712t192148-20170712t192213-017442-01d25d-003.tiff',
                                           's1a-iw3-slc-vv-20170712t192148-20170712t192213-017442-01d25d-006.tiff']}}

    def tearDown(self):
        """
        Removes the directory after the test.
        """
        if exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def set_directory(self):
        """
        Sets up dummy directories and files in sentinel 1 .SAFE folders
        and zip archive
        """

        safe_folder = pjoin(self.test_dir, '{}.SAFE'.format(self.granule))
        os.makedirs(safe_folder)
        for key in self.files[self.granule]:
            sub_folder = pjoin(self.test_dir, safe_folder, key)
            os.makedirs(sub_folder)
            for item in self.files[self.granule][key]:
                checkstatus.TestCheckStatus.write_dummy_file(pjoin(sub_folder, item))
        self.test_archive = (pjoin(self.test_dir, S1_SOURCE_DIR_FMT.format(y=self.dt[0:4], m=self.dt[4:6],
                                                                           g=self.grid, f=self.granule)))
        shutil.make_archive(self.test_archive, 'zip', safe_folder)
    
    def test_set_download_list(self):
        """
        Test set_download_lists function.
        """
        download_list = pjoin(self.test_dir, 'download_list.txt')
        with open(download_list, 'w') as fid:
            fid.writelines(self.content)

        self.raw_data.download_list_path = download_list
        self.raw_data.set_download_lists()

        self.assertTrue(all(elem in self.raw_data.download_list_files[0] for elem in self.content.split()))

    def test_get_archive(self):
        """
        Test get_archive function.
        """
        self.raw_data.s1_dir_path = self.test_dir
        self.set_directory()
        
        archive_test = zipfile.ZipFile('{}.zip'.format(self.test_archive))
        self.raw_data.s1_dir_path = self.test_dir
        self.raw_data.get_archive(self.grid, self.dt, self.granule)
        self.assertTrue(all(elem in archive_test.namelist() for elem in self.raw_data.archive.namelist()))

        self.raw_data.get_archive(self.grid, self.dt, '{}.dummy'.format(self.granule))
        self.assertFalse(self.raw_data.archive)

    def test_get_acquisition(self): 
        """
        Test get_acquisition function.
        """
        test_dict = {'start_datetime': datetime.datetime(2017, 7, 12, 19, 21, 47, 539885),
                     'stop_datetime': datetime.datetime(2017, 7, 12, 19, 22, 14, 500562), 'sensor': 'S1A'}
        manifest_file = pjoin(DATA_DIR, 'manifest.safe')
        acq_details = self.raw_data.get_acquisition(manifest_file)
        self.assertDictEqual(test_dict, acq_details)

        manifest_file = pjoin(DATA_DIR, 'corrupt_manifest.safe')
        self.assertFalse(self.raw_data.get_acquisition(manifest_file))

    def test_get_poerb_oribit_file(self):
        """
        Test get_poerb_orbit_file function.
        """
        poeorb_files = ['S1A_OPER_AUX_POEORB_OPOD_20170713T121025_V20170712T225942_20170714T005942.EOF',
                        'S1A_OPER_AUX_POEORB_OPOD_20170715T121015_V20170711T225942_20170713T005942.EOF',
                        'S1A_OPER_AUX_POEORB_OPOD_20170715T131022_V20170711T225942_20170713T005942.EOF']

        poeorb_dir = pjoin(self.test_dir, 'POEORB', 'S1A')
        if not exists(poeorb_dir):
            os.makedirs(poeorb_dir)

        for f in poeorb_files:
            checkstatus.TestCheckStatus.write_dummy_file(pjoin(poeorb_dir, f))

        manifest_file = pjoin(DATA_DIR, 'manifest.safe')
        acq = self.raw_data.get_acquisition(manifest_file)

        orb_file = self.raw_data.get_poeorb_orbit_file(self.test_dir, acq)
        self.assertTrue(poeorb_files[2], basename(orb_file))

        acq.pop('start_datetime')
        acq['start_datetime'] = datetime.datetime(2018, 7, 12, 19, 21, 47, 539885)
        self.assertFalse(self.raw_data.get_poeorb_orbit_file(self.test_dir, acq))

    def test_get_resorb_orbit_file(self):
        """
        Test get_resorb_orbit_file function
        """
        resorb_file = ['S1A_OPER_AUX_RESORB_OPOD_20190128T175659_V20190128T123108_20190128T154838.EOF',
                       'S1A_OPER_AUX_RESORB_OPOD_20190128T181941_V20190128T140952_20190128T172722.EOF',
                       'S1A_OPER_AUX_RESORB_OPOD_20190128T183838_V20190128T140952_20190128T172722.EOF']

        resorb_dir = pjoin(self.test_dir, 'RESORB', 'S1A')
        if not exists(resorb_dir):
            os.makedirs(resorb_dir)

        for f in resorb_file:
            checkstatus.TestCheckStatus.write_dummy_file(pjoin(resorb_dir, f))

        manifest_file = pjoin(DATA_DIR, 'manifest.safe')
        acq = self.raw_data.get_acquisition(manifest_file)

        self.assertFalse(self.raw_data.get_resorb_orbit_file(self.test_dir, acq))
        acq.pop('start_datetime')
        acq.pop('stop_datetime')
        acq['start_datetime'] = datetime.datetime(2019, 1, 28, 14, 9, 52)
        acq['stop_datetime'] = datetime.datetime(2019, 1, 28, 14, 9, 52)
        orb_file = self.raw_data.get_resorb_orbit_file(self.test_dir, acq)

        self.assertTrue(resorb_file[2], basename(orb_file))

    def test_archive_download(self):
        """
        Test archive_download function.
        """
        self.raw_data.s1_dir_path = self.test_dir
        self.set_directory()
        self.raw_data.get_archive(self.grid, self.dt, self.granule)

        source_m_paths = fnmatch.filter(self.raw_data.archive.namelist(), '*measurement/*{}*'.format('vv'))
        m_path = pjoin(self.test_dir, '{}.SAFE'.format(self.granule))
        if exists(m_path):
            shutil.rmtree(m_path)
        for m_file in source_m_paths:
            self.raw_data.archive_download(m_file, pjoin(m_path, 'measurement'))

        tiff_extract_files = [f for f in os.listdir(pjoin(m_path, 'measurement'))]
        tiff_source_files = [basename(p) for p in source_m_paths]
        self.assertTrue(all(elem in tiff_source_files for elem in tiff_extract_files))


if __name__ == '__main__':
    unittest.main()






