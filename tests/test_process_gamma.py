#!/usr/bin/python

import os
import shutil
import unittest
import luigi
import luigi.execution_summary
import tempfile
from os.path import join as pjoin, exists
from helpers import with_config
from luigi import LocalTarget, configuration
from mock import patch
import process_gamma
import test_check_status as check_status


class TestProcessGamma(unittest.TestCase):
    """
    Test the functions in process_gamma module.
    """

    def setUp(self):
        """
        Creates a temporary directory.
        """
        self.test_dir = tempfile.mkdtemp()
        self.scheduler = luigi.scheduler.Scheduler(prune_on_get_work=False)
        self.worker = luigi.worker.Worker(scheduler=self.scheduler)

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
        Test the ExternalFileChecker class
        """
        e_file = pjoin(self.test_dir, 'testfile.txt')
        target = process_gamma.ExternalFileChecker(e_file)
        luigi.build([target], workers=1, local_scheduler=True)

        self.assertFalse(target.complete())
        self.assertTrue(luigi.worker.worker().retry_external_tasks)

        check_status.TestCheckStatus.write_dummy_file(e_file)

        self.assertTrue(target.complete())


if __name__ == '__main__':
    unittest.main()
