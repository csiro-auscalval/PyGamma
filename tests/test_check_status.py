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
        with open(filename, 'w') as fid:
            fid.writelines('This is dummy text')
    
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
    '''
    def test_checkrawdata(self):
        """
        Test the checkrawdata function.
        """
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
    '''

    def test_checkgammadem(self):
        """
        Test the checkgammadem function.
         """
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
        """
        Test the checkfullslc function.
        """
        scene_dir = pjoin(self.test_dir, '20170712')
        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['slc_file'])
        self.create_files(scene_dir, files_list)
        status = check_status.checkfullslc(self.test_dir)
        self.assertFalse(status)

        os.remove(pjoin(scene_dir, Wildcards.SLC_ERROR_LOG_TYPE.value))
        error_log = pjoin(pjoin(scene_dir, Wildcards.SLC_ERROR_LOG_TYPE.value))
        
        self.write_empty_file(error_log)
        status = check_status.checkfullslc(self.test_dir)
        self.assertTrue(status)

    def test_checkmultilook(self):
        """
        Test the checkmultilook function.
        """
        scene_dir = pjoin(self.test_dir, '20170712')
        files_list = pjoin(DATA_DIR, test_data.TEST_VARS['slc_file'])
        self.create_files(scene_dir, files_list)
        status = check_status.checkmultilook(self.test_dir)
        
        slc_files = [f for f in os.listdir(scene_dir)]
        mli_file = fnmatch.filter(slc_files, Wildcards.MLI_TYPE.value)[0]
        os.remove(pjoin(scene_dir, mli_file))
        
        self.write_empty_file(pjoin(scene_dir, mli_file))
        status = check_status.checkmultilook(self.test_dir)
        self.assertFalse(status)

    def test_checkbaseline(self):
        """
        Test the checkbaseline function.
        """
        filename = pjoin(self.test_dir, 'ifg_list.list')
        self.write_dummy_file(filename)
        status = check_status.checkbaseline(filename)
        self.assertTrue(status)
        
        os.remove(filename)
        self.write_empty_file(filename)
        status = check_status.checkbaseline(filename)
        self.assertFalse(status)

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
        
        status = check_status.checkdemmaster(**kwargs)
        self.assertFalse(status)
        
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
             fid.writelines([MatchStrings.DEM_WARNING.value for i in range(55)])
             fid.writelines(MatchStrings.DEM_ISP.value)

        status = check_status.checkdemmaster(**kwargs)
        self.assertFalse(status)
        
        os.remove(rdc_sim_file)
        self.write_empty_file(rdc_sim_file)
        status = check_status.checkdemmaster(**kwargs)
        self.assertFalse(status)
        
        os.remove(rdc_sim_file)
        self.write_dummy_file(rdc_sim_file)
        
        os.remove(r_mli_file)
        self.write_empty_file(r_mli_file)
        status = check_status.checkdemmaster(**kwargs)
        self.assertTrue(status)
        
    def test_checkcoregslaves(self):
        pass

    def test_checkifgs(self):
        pass


if __name__ == '__main__':
    unittest.main()







































