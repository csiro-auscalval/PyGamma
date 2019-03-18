#!/usr/bin/python

import os
import shutil
import tempfile
import unittest
import fnmatch
from os.path import join as pjoin, abspath, dirname, exists, getmtime
from python_scripts import check_status
from python_scripts.constant import Wildcards, MatchStrings, FolderNames,  ErrorMessages
from data import data as test_data

DATA_DIR = pjoin(dirname(abspath(__file__)), 'data')


class TestCheckStatus(unittest.TestCase):

    """
    Test the various functions contained in python_scripts.check_status module.
    """

    def setUp(self):
        """
        Creates a temporary directory.
        """
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """
        Removes the directory after the test.
        """
        if exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @staticmethod
    def write_dummy_file(filename):
        if not exists(dirname(filename)):
            os.makedirs(dirname(filename))
        with open(filename, 'w') as fid:
            fid.writelines('This is dummy fill texts')
    
    @staticmethod
    def write_empty_file(filename): 
        with open(filename, 'w') as fid: 
            pass

    @classmethod
    def create_files(cls, scene_dir, files_lists):
        """
        Creates directory (scene_dir) and populates with dummy
        text files from a files_list.
        """
        with open(files_lists, 'r') as src:
            if not exists(scene_dir):
                os.makedirs(scene_dir)
            for item in src.readlines():
                filename = pjoin(scene_dir, item.rstrip())
                cls.write_dummy_file(filename)

    def test_checkgammadem(self):
        """
        Test the checkgammadem function.
         """
        kwargs = {'track_frame': 'T111A_F20',
                  'gamma_dem_path': self.test_dir}

        gamma_dem_files = [Wildcards.TRACK_DEM_TYPE.value.format(track_frame=kwargs['track_frame']),
                           Wildcards.TRACK_DEM_PAR_TYPE.value.format(track_frame=kwargs['track_frame'])]

        for item in gamma_dem_files:
            filename = pjoin(self.test_dir, item)
            self.write_dummy_file(filename)

        self.assertTrue(check_status.checkgammadem(**kwargs))

        os.remove(pjoin(self.test_dir, gamma_dem_files[0]))
        self.assertFalse(check_status.checkgammadem(**kwargs))

    def test_checkfullslc(self):
        """
        Test the checkfullslc function.
        """
        scene_dir = pjoin(self.test_dir, '20170712')
        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['slc_file'])

        self.create_files(scene_dir, files_list)
        self.assertFalse(check_status.checkfullslc(self.test_dir))

        os.remove(pjoin(scene_dir, Wildcards.SLC_ERROR_LOG_TYPE.value))
        error_log = pjoin(pjoin(scene_dir, Wildcards.SLC_ERROR_LOG_TYPE.value))
        self.write_empty_file(error_log)
        self.assertTrue(check_status.checkfullslc(self.test_dir))

    def test_checkmultilook(self):
        """
        Test the checkmultilook function.
        """
        scene_dir = pjoin(self.test_dir, '20170712')
        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['slc_file'])

        self.create_files(scene_dir, files_list)
        self.assertTrue(check_status.checkmultilook(self.test_dir))

        slc_files = [f for f in os.listdir(scene_dir)]
        mli_file = fnmatch.filter(slc_files, Wildcards.MLI_TYPE.value)[0]
        os.remove(pjoin(scene_dir, mli_file))
        self.write_empty_file(pjoin(scene_dir, mli_file))
        self.assertFalse(check_status.checkmultilook(self.test_dir))

    def test_checkbaseline(self):
        """
        Test the checkbaseline function.
        """
        filename = pjoin(self.test_dir, 'ifg_list.list')

        self.write_dummy_file(filename)
        self.assertTrue(check_status.checkbaseline(filename))
        
        os.remove(filename)
        self.write_empty_file(filename)
        self.assertFalse(check_status.checkbaseline(filename))

    def test_checkdemmaster(self):
        """
        Test the checkdemmaster function.
        """
        kwargs = {'slc_path': pjoin(self.test_dir, 'SLC'),
                  'dem_path': pjoin(self.test_dir, 'DEM'),
                  'master_scene': '20170712'}

        master_scene_path = pjoin(kwargs['slc_path'], kwargs['master_scene'])

        self.create_files(master_scene_path, pjoin(DATA_DIR, test_data.TEST_VARS['slc_file']))
        self.create_files(kwargs['dem_path'], pjoin(DATA_DIR, test_data.TEST_VARS['dem_file']))
        self.assertFalse(check_status.checkdemmaster(**kwargs))
        
        slc_files = [f for f in os.listdir(master_scene_path)]
        dem_files = [f for f in os.listdir(kwargs['dem_path'])]
        
        dem_error_log = pjoin(kwargs['dem_path'], fnmatch.filter(dem_files, Wildcards.DEM_ERROR_LOG_TYPE.value)[0])
        slc_error_log = pjoin(master_scene_path, fnmatch.filter(slc_files, Wildcards.SLC_ERROR_LOG_TYPE.value)[0])
        
        r_mli_file = pjoin(master_scene_path, fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_TYPE.value)[0])
        r_mli_par_file = pjoin(master_scene_path, fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_PAR_TYPE.value)[0])
        rdc_sim_file = pjoin(kwargs['dem_path'], fnmatch.filter(dem_files, Wildcards.RDC_SIM_TYPE.value)[0])

        os.remove(slc_error_log)
        os.remove(dem_error_log)
        self.write_empty_file(slc_error_log)
        with open(dem_error_log, 'w') as fid: 
            fid.writelines(MatchStrings.DEM_USAGE_NOTE.value)
            fid.writelines(MatchStrings.DEM_SCENE_TITLE.value)
            fid.writelines(MatchStrings.DEM_WARNING.value * 55)
            fid.writelines(MatchStrings.DEM_ISP.value)
        self.assertFalse(check_status.checkdemmaster(**kwargs))
        
        os.remove(rdc_sim_file)
        self.write_empty_file(rdc_sim_file)
        self.assertFalse(check_status.checkdemmaster(**kwargs))
        
        os.remove(rdc_sim_file)
        self.write_dummy_file(rdc_sim_file)
        os.remove(r_mli_file)
        self.write_empty_file(r_mli_file)
        self.assertFalse(check_status.checkdemmaster(**kwargs))

        os.remove(r_mli_file)
        os.remove(r_mli_par_file)
        self.write_dummy_file(r_mli_file)
        with open(r_mli_par_file, 'w') as fid:
            fid.writelines('{}:2\n'.format(MatchStrings.SLC_RANGE_SAMPLES.value))
            fid.writelines('{}:3'.format(MatchStrings.SLC_AZIMUTH_LINES.value))
        self.assertTrue(check_status.checkdemmaster(**kwargs))

    def test_checkcoregslaves(self):
        """
        Test the checkcoregslaves function.
        """
        kwargs = {'slc_path': pjoin(self.test_dir, 'SLC'),
                  'master_scene': '20170712'}

        scene_dir = pjoin(kwargs['slc_path'], '20170727')

        self.create_files(scene_dir, pjoin(DATA_DIR, test_data.TEST_VARS['slc_file']))
        slc_files = [f for f in os.listdir(scene_dir)]
        slc_error_log = pjoin(scene_dir, fnmatch.filter(slc_files, Wildcards.SLC_ERROR_LOG_TYPE.value)[0])
        r_mli_file = pjoin(scene_dir, fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_TYPE.value)[0])
        r_mli_par_file = pjoin(scene_dir, fnmatch.filter(slc_files, Wildcards.RADAR_CODED_MLI_PAR_TYPE.value)[0])

        self.assertFalse(check_status.checkcoregslaves(**kwargs))
        
        os.remove(slc_error_log)
        self.write_empty_file(slc_error_log)
        os.remove(r_mli_file)
        self.write_empty_file(r_mli_file)
        self.assertFalse(check_status.checkcoregslaves(**kwargs))
        
        os.remove(r_mli_file)
        os.remove(r_mli_par_file)
        self.write_dummy_file(r_mli_file)
        with open(r_mli_par_file, 'w') as fid: 
            fid.writelines('{}:2\n'.format(MatchStrings.SLC_RANGE_SAMPLES.value))
            fid.writelines('{}:3'.format(MatchStrings.SLC_AZIMUTH_LINES.value))
        self.assertTrue(check_status.checkcoregslaves(**kwargs))

    def test_checkifgs(self):
        """
        Test the checkifg function.
        """
        scene_dir = pjoin(self.test_dir, '20170727')
        self.create_files(scene_dir, pjoin(DATA_DIR, test_data.TEST_VARS['ifg_file']))
        ifg_files = [f for f in os.listdir(scene_dir)]

        ifg_error_log = pjoin(scene_dir, fnmatch.filter(ifg_files, Wildcards.SLC_ERROR_LOG_TYPE.value)[0])
        flat_file = pjoin(scene_dir, fnmatch.filter(ifg_files, Wildcards.INT_FLAT_TYPE.value)[0])
        eqa_unw_file = pjoin(scene_dir, fnmatch.filter(ifg_files, Wildcards.EQA_UNW_TYPE.value)[0])

        self.assertFalse(check_status.checkifgs(self.test_dir))

        os.remove(ifg_error_log)
        self.write_empty_file(ifg_error_log)
        self.assertTrue(check_status.checkifgs(self.test_dir))

        os.remove(flat_file)
        self.write_empty_file(flat_file)
        self.assertFalse(check_status.checkifgs(self.test_dir))

        os.remove(flat_file)
        os.remove(eqa_unw_file)
        self.write_empty_file(eqa_unw_file)
        self.write_dummy_file(flat_file)
        self.assertFalse(check_status.checkifgs(self.test_dir))


if __name__ == '__main__':
    unittest.main()




































