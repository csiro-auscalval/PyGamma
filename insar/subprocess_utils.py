#!/usr/bin/env python

import os
import functools
import itertools
import logging
import signal
import subprocess
import contextlib


from luigi import six

_LOG = logging.getLogger(__name__)

os.environ["CPL_ZIP_ENCODING"] = "UTF-8"


class WithConfig(object):
    """
    Decorator to override config settings for the length of a function.
    Usage:
    """

    def __init__(self, config, replace_sections=False):
        self.config = config
        self.replace_sections = replace_sections

    def _make_dict(self, old_dict):
        if self.replace_sections:
            old_dict.update(self.config)
            return old_dict

        def get_section(sec):
            old_sec = old_dict.get(sec, {})
            new_sec = self.config.get(sec, {})
            old_sec.update(new_sec)
            return old_sec

        all_sections = itertools.chain(old_dict.keys(), self.config.keys())
        return {sec: get_section(sec) for sec in all_sections}

    def __call__(self, fun):
        @functools.wraps(fun)
        def wrapper(*args, **kwargs):
            import luigi.configuration

            orig_conf = luigi.configuration.LuigiConfigParser.instance()
            new_conf = luigi.configuration.LuigiConfigParser()
            luigi.configuration.LuigiConfigParser._instance = new_conf
            orig_dict = {k: dict(orig_conf.items(k)) for k in orig_conf.sections()}
            new_dict = self._make_dict(orig_dict)
            for (section, settings) in six.iteritems(new_dict):
                new_conf.add_section(section)
                for (name, value) in six.iteritems(settings):
                    new_conf.set(section, name, value)
            try:
                return fun(*args, **kwargs)
            finally:
                luigi.configuration.LuigiConfigParser._instance = orig_conf

        return wrapper


@contextlib.contextmanager
def environ(env):
    """Temporarily set environment variables inside the context manager and
    fully restore previous environment afterwards
    """
    original_env = {key: os.getenv(key) for key in env}
    os.environ.update(env)
    try:
        yield
    finally:
        for key, value in original_env.items():
            if value is None:
                del os.environ[key]
            else:
                os.environ[key] = value


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


# NOTE
# run_command function is directly copied from https://github.com/OpenDataCubePipelines/eugl/blob/master/eugl/fmask.py


def run_command(
    command, work_dir, timeout=None, command_name=None, return_stdout=False
):
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
        _stdout, _stderr = _proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # see https://stackoverflow.com/questions/36952245/subprocess-timeout-failure
        os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
        _stdout, _stderr = _proc.communicate()
        timed_out = True

    if _proc.returncode != 0:
        _LOG.error(_stderr.decode("utf-8"))
        _LOG.info(_stdout.decode("utf-8"))

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
        _LOG.debug(_stdout.decode("utf-8"))
        if return_stdout:
            return _stdout.decode("utf-8")
