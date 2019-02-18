#!/usr/bin/python

import shutil
import tempfile
import unittest
import os
from os.path import join as pjoin, abspath, dirname, exists, getmtime
from python_scripts import clean_up
from data import data as test_data
import time

DATA_DIR = pjoin(dirname(abspath(__file__)), 'data')


class TestCleanUp(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        if exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_clean_rawdatadir(self):
        """ test case to check if raw data directory is removed"""
        dummy_file_lists = ['dummy_{i}.txt'.format(i=idx) for idx in range(5)]
        for f in dummy_file_lists:
            with open(pjoin(self.test_dir, f), 'w') as fid:
                fid.writelines('This is dummy text')

        clean_up.clean_rawdatadir(raw_data_path=self.test_dir)
        self.assertFalse(os._exists(self.test_dir))

    def test_clean_scldir(self):
        """ test case to check if SLC directory is cleaned as expected"""
        with open(pjoin(DATA_DIR, 'slc_files.txt'), 'r') as src:
            scene_dir = pjoin(self.test_dir, '20161122')
            os.makedirs(scene_dir)
            for item in src.readlines():
                with open(pjoin(scene_dir, item.rstrip()), 'w') as fid:
                    fid.writelines('This is dummy text')

        clean_up.clean_slcdir(slc_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(scene_dir)]
        files_test = test_data.SLC_FILES
        self.assertTrue(all(elem in files_cleanup for elem in files_test))

    def test_clean_ifgdir(self):
        """ test case to check if IFG directory is cleaned as expected"""
        with open(pjoin(DATA_DIR, 'ifg_files.txt'), 'r') as src:
            scene_dir = pjoin(self.test_dir, '20161005-20161017')
            os.makedirs(scene_dir)
            for item in src.readlines():
                with open(pjoin(scene_dir, item.rstrip()), 'w') as fid:
                    fid.writelines('This is dummy text')

        clean_up.clean_ifgdir(ifg_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(scene_dir)]
        files_test = test_data.IFG_FILES
        self.assertTrue(all(elem in files_cleanup for elem in files_test))

    def test_clean_demdir(self):
        """ test case to check if DEM directory is cleaned as expected"""
        with open(pjoin(DATA_DIR, 'dem_files.txt'), 'r') as src:
            for item in src.readlines():
                with open(pjoin(self.test_dir, item.rstrip()), 'w') as fid:
                    fid.writelines('This is dummy text')

        clean_up.clean_demdir(dem_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(self.test_dir)]
        files_test = test_data.DEM_FILES
        self.assertTrue(all(elem in files_cleanup for elem in files_test))

    def test_clean_checkpoints(self):
        """ test case to check if check point file are cleaned as expected"""
        with open(pjoin(DATA_DIR, 'check_files.txt'), 'r') as src:
            for item in src.readlines():
                with open(pjoin(self.test_dir, item.rstrip()), 'w') as fid:
                    fid.writelines('This is dummy text')
                time.sleep(.001)

        clean_up.clean_checkpoints(checkpoint_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(self.test_dir)]
        files_test = 'Slc_resize_status_logs.out'
        if files_test not in files_cleanup:
            flag = True
        self.assertTrue(flag)


if __name__ == '__main__':
    unittest.main()
