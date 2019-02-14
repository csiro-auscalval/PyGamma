#!/usr/bin/python

import shutil

import tempfile
import unittest
import os
from os.path import join as pjoin, abspath, dirname
from python_scripts import clean_up


DATA_DIR = pjoin(dirname(abspath(__file__)), 'data')


class TestCleanUp(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        # Remove the directory after the test
        pass

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
        files_test = ['r20161122_VV_tab', 'r20161122_VV.slc.par', 'r20161122_VV_8rlks.mli',
                      '20161122_HH_8rlks.gamma0', 'r20161122_VV_8rlks.mli.par',
                      '20161122_HH_8rlks_eqa.gamma0.kml', '20161122_HH_8rlks_eqa.gamma0',
                      '20161122_HH_8rlks_eqa.gamma0.png', 'r20161122_VV.slc']

        self.assertListEqual(files_cleanup, files_test)

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
        files_test = ['20161005-20161017_VV_8rlks_eqa_unw.kml', '20161005-20161017_VV_8rlks_off.par',
                      '20161005-20161017_VV_8rlks_diff.par', '20161005-20161017_VV_8rlks_eqa.unw.tif',
                      '20161005-20161017_VV_8rlks_flat_eqa.int.tif', '20161005-20161017_VV_8rlks_flat_eqa.int',
                      '20161005-20161017_VV_8rlks_filt_eqa.int.tif', '20161005-20161017_VV_8rlks_eqa_unw.png',
                      '20161005-20161017_VV_8rlks_mask.ras', '20161005-20161017_VV_8rlks_flat.cc', 'command.log',
                      '20161005-20161017_VV_8rlks_filt_eqa.int', 'ifg.rsc',
                      '20161005-20161017_VV_8rlks_flat_eqa.cc', '20161005-20161017_VV_8rlks_filt_eqa_int.kml',
                      '20161005-20161017_VV_8rlks_flat_eqa.cc.tif', '20161005-20161017_VV_8rlks_filt.int',
                      '20161005-20161017_VV_8rlks_flat_eqa_cc.kml', 'temp_log',
                      '20161005-20161017_VV_8rlks_mask_thin.ras', '20161005-20161017_VV_8rlks_flat.int',
                      '20161005-20161017_VV_8rlks_filt_eqa_int.png', '20161005-20161017_VV_8rlks_flat_eqa_int.kml',
                      '20161005-20161017_VV_8rlks_bperp.par', 'error.log',
                      '20161005-20161017_VV_8rlks_flat_eqa_int.png', '20161005-20161017_VV_8rlks_filt_eqa_cc.png',
                      '20161005-20161017_VV_8rlks_base.par', '20161005-20161017_VV_8rlks_filt_eqa_cc.kml',
                      '20161005-20161017_VV_8rlks_flat_eqa_cc.png', 'output.log', '20161005-20161017_VV_8rlks.unw',
                      '20161005-20161017_VV_8rlks_filt.cc', '20161005-20161017_VV_8rlks_eqa.unw',
                      '20161005-20161017_VV_8rlks_filt_eqa.cc.tif', '20161005-20161017_VV_8rlks_filt_eqa.cc']

        self.assertListEqual(files_cleanup, files_test)


if __name__ == '__main__':
    unittest.main()