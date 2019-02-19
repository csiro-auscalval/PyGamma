#!/usr/bin/python

import os
import shutil
import tempfile
import unittest
from os.path import join as pjoin, abspath, dirname, exists, getmtime
from python_scripts import check_status
from python_scripts.constant import Wildcards, MatchStrings, FolderNames,  ErrorMessages
from data import data as test_data

DATA_DIR = pjoin(dirname(abspath(__file__)), 'data')


class TestCheckStatus(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        if exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @staticmethod
    def write_dummy_file(filename):
        with open(filename, 'w') as fid:
            fid.writelines('This is dummy text')

    @classmethod
    def create_files(cls, scene_dir, files_lists):
        """ creates folders 'scene_dir' and files within the files_list"""
        with open(files_lists, 'r') as src:
            if not exists(scene_dir):
                os.makedirs(scene_dir)
            for item in src.readlines():
                filename = pjoin(scene_dir, item.rstrip())
                cls.write_dummy_file(filename)

    def test_checkrawdata(self):
        """ test to check if raw checkrawdata function's execution is as expected """
        
        #TODO make temporary zipped file with tiff datasets as source s1 data for testing

        kwargs = {'raw_data_path': pjoin(DATA_DIR, 'SLC_DATA_RAW'),
                  's1_dir_path': pjoin(DATA_DIR, 'SLC_DATA_SOURCE'),
                  'download_list_path':  pjoin(DATA_DIR, 's1_des_download_half1.list'),
                  'scenes_list_path': pjoin(DATA_DIR, 'scenes.list')}

        status = check_status.checkrawdata(**kwargs)
        self.assertTrue(status)

        raw_data_dir = pjoin(self.test_dir, test_data.TEST_VARS['tiff_folder'])
        os.makedirs(raw_data_dir)
        self.write_dummy_file(pjoin(raw_data_dir, test_data.TEST_VARS['tiff_file']))

        kwargs['raw_data_path'] = self.test_dir
        status = check_status.checkrawdata(**kwargs)
        self.assertTrue(status)

    def test_checkgammadem(self):
        """ test to check checkgammadem function """

        kwargs = {'track': 'T111A',
                  'gamma_dem_path': self.test_dir}

        gamma_dem_files = [Wildcards.TRACK_DEM_TYPE.value.format(track=kwargs['track']),
                           Wildcards.TRACK_DEM_PAR_TYPE.value.format(track=kwargs['track'])]

        for item in gamma_dem_files:
            filename = pjoin(self.test_dir, item)
            self.write_dummy_file(filename)

        status = check_status.checkgammadem(**kwargs)
        self.assertTrue(status)
        os.remove(pjoin(self.test_dir, gamma_dem_files[0]))
        status = check_status.checkgammadem(**kwargs)
        self.assertFalse(status)

    def test_checkfullslc(self):
        """ test to check checkfullslc function """

        scene_dir = pjoin(self.test_dir, '20170712')
        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['slc_file'])
        self.create_files(scene_dir, files_list)
        status = check_status.checkfullslc(self.test_dir)
        self.assertFalse(status)

        os.remove(pjoin(scene_dir, Wildcards.SLC_ERROR_LOG_TYPE.value))
        error_log = pjoin(pjoin(scene_dir, Wildcards.SLC_ERROR_LOG_TYPE.value))
        with open(error_log, 'w'):
            pass
        status = check_status.checkfullslc(self.test_dir)
        self.assertTrue(status)

    def test_checkmultilook(self):
        """ test to check checkmultilook function """


        pass

    def test_checkbaseline(self):
        pass

    def test_checkdemmaster(self):
        pass

    def test_checkcoregslaves(self):
        pass

    def test_checkifgs(self):
        pass


if __name__ == '__main__':
    unittest.main()
