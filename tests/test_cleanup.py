#!/usr/bin/python

import shutil
import tempfile
import unittest
import os
from os.path import join as pjoin, abspath, dirname, exists
from python_scripts import clean_up
from data import data as test_data
import time
import test_check_status as checkstatus

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
            checkstatus.TestCheckStatus.write_dummy_file(pjoin(self.test_dir, f))
        clean_up.clean_rawdatadir(raw_data_path=self.test_dir)
        self.assertFalse(os._exists(self.test_dir))

    def test_clean_scldir(self):
        """ test case to check if SLC directory is cleaned as expected"""

        scene_dir = pjoin(self.test_dir, '20161122')
        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['slc_file'])
        checkstatus.TestCheckStatus.create_files(scene_dir, files_list)

        clean_up.clean_slcdir(slc_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(scene_dir)]
        files_test = test_data.SLC_FILES
        self.assertTrue(all(elem in files_cleanup for elem in files_test))

    def test_clean_ifgdir(self):
        """ test case to check if IFG directory is cleaned as expected"""

        scene_dir = pjoin(self.test_dir, '20161005-20161017')
        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['ifg_file'])
        checkstatus.TestCheckStatus.create_files(scene_dir, files_list)

        clean_up.clean_ifgdir(ifg_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(scene_dir)]
        files_test = test_data.IFG_FILES
        self.assertTrue(all(elem in files_cleanup for elem in files_test))

    def test_clean_demdir(self):
        """ test case to check if DEM directory is cleaned as expected"""

        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['dem_file'])
        checkstatus.TestCheckStatus.create_files(self.test_dir, files_list)

        clean_up.clean_demdir(dem_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(self.test_dir)]
        files_test = test_data.DEM_FILES
        self.assertTrue(all(elem in files_cleanup for elem in files_test))

    def test_clean_checkpoints(self):
        """ test case to check if check point file are cleaned as expected"""

        with open(pjoin(DATA_DIR, test_data.TEST_VARS['check_file']), 'r') as src:
            for item in src.readlines():
                checkstatus.TestCheckStatus.write_dummy_file(pjoin(self.test_dir, item.rstrip()))
                time.sleep(.001)

        clean_up.clean_checkpoints(checkpoint_path=self.test_dir)
        files_cleanup = [item for item in os.listdir(self.test_dir)]
        files_test = test_data.CHECKPOINT_FILES[-1]
        self.assertTrue(files_test not in files_cleanup)


if __name__ == '__main__':
    unittest.main()
