import pytest
from pathlib import Path
import tempfile
import click
from datetime import datetime, timezone

from tests.fixtures import *
from tests.test_workflow import count_dir_tree

import insar.scripts.insar_pbs
from insar.scripts.insar_pbs import ard_insar

from insar.scripts.process_gamma import run_ard_inline
from insar.project import ARDWorkflow


#
# Note: As these unit tests are all testing user scripts, we test the scripts
# in a similar way to how the user would use the scripts...
#
# Specifically we run the script as similarly to the CLI way as possible w/
# a click.Context, and then check the output logs and files.
#

def test_pbs_job_script(monkeypatch, s1_proc, temp_out_dir):
    """
    This test very simply submits a typical S1 job, checking the script is made
    and qsub is called w/o any errors (but doesn't validate the script in any way)
    """

    subprocmock = mock.NonCallableMock()
    subprocmock.call.side_effect = lambda x: 0
    monkeypatch.setattr(insar.scripts.insar_pbs, 'subprocess', subprocmock)

    # Run the packaging script
    test_shp_path = TEST_DATA_BASE / "T133D_F20S_S1A.shp"

    cli_runner = click.Context(ard_insar)
    cli_runner.invoke(
        ard_insar,
        proc_file=str(s1_proc),
        shape_file=str(test_shp_path),
        date_range=[[datetime(year=2022, month=1, day=1), datetime(year=2022, month=2, day=1)]],
        workdir=str(temp_out_dir),
        outdir=str(temp_out_dir),
        polarization=["VV", "VH"],
        ncpus=48,
        memory=192,
        queue="normal",
        hours=12,
        workers=4,
        email="test@email.net",
        jobfs=400,
        storage="v10 dg9 up71 fj7 dz56 dg9",
        env="ENV_SCRIPT",
        cleanup=False,
        num_threads=14
    )

    # Assert job script was created
    job_script_path = temp_out_dir / "job.bash"
    assert job_script_path.exists()

    # ... and it was qsub'd
    subprocmock.call.assert_called_once()
