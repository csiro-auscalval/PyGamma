#!/usr/bin/python

import os
import shutil
import unittest
import luigi
import luigi.execution_summary
import tempfile
from os.path import join as pjoin, abspath, dirname, exists, basename
from helpers import with_config
from luigi import LocalTarget, configuration
from mock import patch
import process_gamma
import test_check_status as check_status
from python_scripts.proc_template import PROC_FILE_TEMPLATE
from python_scripts.initialize_proc_file import get_path

DATA_DIR = pjoin(dirname(abspath(__file__)), 'data')


class TestProcessGamma(unittest.TestCase):
    """
    Test the functions in process_gamma module.
    """

    def setUp(self):
        """
        Creates a temporary directory.
        """
        self.test_dir = tempfile.mkdtemp()
        self.proc_file = pjoin(self.test_dir, 'test.proc')
        self.s1_download_file = pjoin(DATA_DIR, 's1_des_download.list')
        self.scheduler = luigi.scheduler.Scheduler(prune_on_get_work=False)
        self.worker = luigi.worker.Worker(scheduler=self.scheduler)
       
        kwargs = {'download_list': basename(self.s1_download_file),
                  'outdir': self.test_dir,
                  'project': 'dg9',
                  'track': 'TESTA', 
                  'polarization' : 'VV',
                  'multilook': 2, 
                  'extract_raw_data': 'yes',
                  'do_slc': 'yes',
                  'do_s1_resize': 'yes',
                  'coregister_dem': 'yes',
                  'coregister_slaves': 'yes',
                  'process_ifgs': 'yes',
                  'process_geotiff': 'yes',
                  'clean_up': 'yes'}
        proc_data = PROC_FILE_TEMPLATE.format(**kwargs)
        with open(self.proc_file, 'w') as fid:
            fid.writelines(proc_data)

    def run_task(self, task):
        self.worker.add(task)
        self.worker.run()

    def summary_dict(self):
        return luigi.execution_summary._summary_dict(self.worker)

    def summary(self):
        return luigi.execution_summary.summary(self.worker)

    def tearDown(self):
        """
        Removes the directory after the test.
        """
        if exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @with_config({'scheduler': {'retry_count': '2', 'retry_delay': '0.0'}, 'worker': {'wait_interval': '0.01'}})
    def test_externalfilechecker(self):
        """
        Test the ExternalFileChecker function.
        """
        e_file = pjoin(self.test_dir, 'testfile.txt')
        target = process_gamma.ExternalFileChecker(e_file)
        luigi.build([target], workers=1, local_scheduler=True)

        self.assertFalse(target.complete())
        self.assertTrue(luigi.worker.worker().retry_external_tasks)

        check_status.TestCheckStatus.write_dummy_file(e_file)
        self.assertTrue(target.complete())
    
    def test_initial_setup(self): 
        """
        Test the InitialSetup function.
        """
        target = process_gamma.InitialSetup(proc_file_path=self.proc_file, s1_download_list=self.s1_download_file)
        # luigi.build([target], workers=1, local_scheduler=True)
        self.run_task(target)   
        path_name = get_path(self.proc_file)
        self.assertTrue(exists(path_name['scenes_list']))
        self.assertTrue(target.complete())
        d = self.summary_dict()
        self.assertTrue({target}, (d['completed']))
        
        summary = self.summary()
        result = summary.split('\n')
        print(result)
        expected = ['', 
                    '===== Luigi Execution Summary =====', 
                    '', 
                    'Scheduled 1 tasks of which:', 
                    '* 1 ran successfully:', 
                    '    - 1 InitialSetup(proc_file_path={}, s1_download_list={})'.format(self.proc_file, self.s1_download_file), 
                    '', 
                    'This progress looks :) because there were no failed tasks or missing dependencies', 
                    '', 
                    '===== Luigi Execution Summary =====', 
                    '']
        self.assertEqual(len(result), len(expected))
        for i, line in enumerate(result): 
            self.assertEqual(line, expected[i])
   










if __name__ == '__main__':
    unittest.main()
