#!/usr/bin/python

import os
import shutil
import tempfile
import unittest
import mock
import time
import json
from os.path import join as pjoin, abspath, dirname, exists, getmtime
from python_scripts import check_status
from data import data as test_data

from python_scripts.proc_template import PROC_FILE_TEMPLATE
from python_scripts.initialize_proc_file import get_path

DATA_DIR = pjoin(dirname(abspath(__file__)), 'data')

TEST_VARS = {'safe_folder': 'S1A_IW_SLC__1SDV_20170712T192147_20170712T192214_017442_01D25D_FB1F.SAFE',
             'tiff_file': 's1a-iw1-slc-vv-20170712t192149-20170712t192214-017442-01d25d-004.tiff'}


class TestCheckStatus(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        if exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_checkrawdata(self):
        """ test to check if raw checkrawdata function's execution is as expected"""

        kwargs = {'raw_data_path': pjoin(DATA_DIR, 'SLC_DATA_RAW'),
                  's1_dir_path': pjoin(DATA_DIR, 'SLC_DATA_SOURCE'),
                  'download_list_path':  pjoin(DATA_DIR, 's1_des_download_half1.list'),
                  'scenes_list_path': pjoin(DATA_DIR, 'scenes.list')}

        status = check_status.checkrawdata(**kwargs)
        self.assertTrue(status)
        raw_data_dir = pjoin(self.test_dir, '20170712', TEST_VARS['safe_folder'], 'measurement')

        os.makedirs(raw_data_dir)
        with open(pjoin(raw_data_dir, TEST_VARS['tiff_file']), 'w') as fid:
            fid.writelines('This is dummy text')

        kwargs['raw_data_path'] = self.test_dir
        status = check_status.checkrawdata(**kwargs)
        self.assertTrue(status)

    def test_checkgammadem(self):
        pass

    def test_checkfullslc(self):
        pass

    def test_checkmultilook(self):
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
