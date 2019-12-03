#!/usr/bin/python3

import os
import signal
import subprocess
import contextlib

import logging

_LOG = logging.getLogger(__name__)

os.environ["CPL_ZIP_ENCODING"] = "UTF-8"

# NOTE
# run_command function is directly copied from https://github.com/OpenDataCubePipelines/eugl/blob/master/eugl/fmask.py


@contextlib.contextmanager
def working_directory(path):
    """
    context manager to change to working directory and back to
    previous directory
    """
    pre_cwd = os.getcwd()
    os.chdir(path)

    try:
        yield
    finally:
        os.chdir(pre_cwd)


class CommandError(RuntimeError):
    """
    Custom class to capture subprocess call errors
    """

    pass


def run_command(command, work_dir, timeout=None, command_name=None):
    """
    A simple utility to execute a subprocess command.
    Raises a CalledProcessError for backwards compatibility
    """
    _proc = subprocess.Popen(
        " ".join(command),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        preexec_fn=os.setsid,
        shell=True,
        cwd=str(work_dir),
    )

    timed_out = False

    try:
        stdout, stderr = _proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # see https://stackoverflow.com/questions/36952245/subprocess-timeout-failure
        os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
        stdout, stderr = _proc.communicate()
        timed_out = True

    if _proc.returncode != 0:
        _LOG.error(stderr.decode("utf-8"))
        _LOG.info(stdout.decode("utf-8"))

        if command_name is None:
            command_name = str(command)

        if timed_out:
            raise CommandError('"%s" timed out' % (command_name))
        else:
            raise CommandError(
                '"%s" failed with return code: %s'
                % (command_name, str(_proc.returncode))
            )
    else:
        _LOG.debug(stdout.decode("utf-8"))
