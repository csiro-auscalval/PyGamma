import os
import signal
import subprocess
import contextlib

import structlog


_LOG = structlog.get_logger("insar")

os.environ["CPL_ZIP_ENCODING"] = "UTF-8"


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


# NOTE: run_command function is directly copied from:
# https://github.com/OpenDataCubePipelines/eugl/blob/master/eugl/fmask.py

def run_command(
    command, work_dir, timeout=None, command_name=None, return_stdout=False,
):
    """
    A simple utility to execute a subprocess command.
    Raises a CalledProcessError for backwards compatibility
    """
    _proc = subprocess.Popen(
        " ".join([str(i) for i in command]),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        preexec_fn=os.setsid,
        shell=True,
        cwd=str(work_dir),
    )

    timed_out = False

    try:
        _stdout, _stderr = _proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # see https://stackoverflow.com/questions/36952245/subprocess-timeout-failure
        os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
        _stdout, _stderr = _proc.communicate()
        timed_out = True

    stdout_decode = _stdout.decode("utf-8")
    stderr_decode = _stderr.decode("utf-8")
    cmd = str(command)
    if _proc.returncode != 0:
        _LOG.error(
            "command result", command=cmd, std_err=stderr_decode,
        )
        _LOG.info(
            "command result", command=cmd, std_out=stdout_decode,
        )

        if command_name is None:
            command_name = str(command)

        if timed_out:
            _LOG.error(
                "command timed out", command=cmd,
            )
            raise CommandError('"%s" timed out' % command_name)
        else:
            _LOG.error(
                "command failed", command=cmd, return_code=_proc.returncode,
            )
            raise CommandError(
                '"%s" failed with return code: %s' % (command_name, str(_proc.returncode))
            )
    else:
        _LOG.info(
            "command result", command=cmd, std_out=stdout_decode,
        )
        if return_stdout:
            return stdout_decode
