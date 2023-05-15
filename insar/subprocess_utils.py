import os
import signal
import subprocess
import contextlib

from insar.logs import STATUS_LOGGER as STATUS_LOG, GAMMA_LOGGER as GAMMA_LOG

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


def run_command(command, work_dir, timeout=None, command_name=None, return_stdout=False):
    """
    A simple utility to execute a subprocess command.
    Raises a CalledProcessError for backwards compatibility
    """

    proc = subprocess.Popen(
        " ".join([str(i) for i in command]),
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE,
        preexec_fn=os.setsid,
        shell=True,
        cwd=str(work_dir),
    )

    timed_out = False

    try:
        stdout, stderr = proc.communicate(timeout=timeout)

    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        stdout, stderr = proc.communicate()
        timed_out = True

    cmd = str(command)

    stdout_decode = stdout.decode("utf-8")
    stderr_decode = stderr.decode("utf-8")

    if proc.returncode != 0:
        STATUS_LOG.error(
            f"GAMMA command {cmd} has non-zero return code {proc.returncode}",
            command=cmd,
            std_err=stderr_decode,
        )

        if command_name is None:
            command_name = cmd

        if timed_out:
            raise CommandError(f'GAMMA command `{command_name}` timed out')
        else:
            raise CommandError(f'GAMMA command `{command_name}` has return code: {proc.returncode}')

    return stdout_decode
