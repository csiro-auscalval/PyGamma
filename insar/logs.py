"""
Logging configuration for InSAR logs

Defines structured logging for:
    * Task messages     -- qualname task
    * Status messages   -- qualname status
    * Luigi interface   -- qualname luigi-interface
"""

import pkg_resources
import contextlib
import structlog
import logging
import luigi
import sys
import os

from pathlib import Path
from typing import Union
from osgeo import gdal

print("Starting logging")

class FormatJSONL(logging.Formatter):
    """ Prevents printing of the stack trace to enable JSON lines output """

    def formatException(self, ei):
        """ Disables printing separate stack traces """
        return


class ValueRenderer:

    def __init__(self, keys=['event']):
        self.keys = keys

    def __call__(self, logger, method_name, log) -> str:
        return f"{log['event']}    [{log['filename']}:{log['lineno']}]"


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


@contextlib.contextmanager
def logging_directory(path: Union[str, Path]):
    """
    A context manager that redirects the gamma log into the specified directory for the
    lifetime of the manager.

    Once the manager loses context, the log files are closed leaving the logs in an
    unusable state the user will need to reinitalise if they plan to continue using them.
    """
    yield

    if not isinstance(path, Path):
        path = Path(path)

    # Configure logging into the specified path
    with working_directory(path):
        # Configure logging from built-in script logging config file
        with (path / "insar-log.jsonl").open("a") as fobj:
            structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj),
                                processors=COMMON_PROCESSORS)

            yield



COMMON_PROCESSORS = [
    structlog.threadlocal.merge_threadlocal,
    #structlog.stdlib.add_log_level,
    #structlog.processors.TimeStamper(fmt="ISO"),
    #structlog.processors.StackInfoRenderer(),
    #structlog.processors.format_exc_info,
    structlog.processors.CallsiteParameterAdder(
        [structlog.processors.CallsiteParameter.FILENAME,
         structlog.processors.CallsiteParameter.FUNC_NAME,
         structlog.processors.CallsiteParameter.LINENO],
    ),
    #structlog.dev.ConsoleRenderer()
    #structlog.processors.JSONRenderer(sort_keys=True),
    #structlog.processors.KeyValueRenderer(key_order=["event"]),
    ValueRenderer(['event', 'filename', 'lineno'])
]

def getLogger(logger_name: str = "root", **kwargs):
    if logger_name in ["status", "task"]:
        logger = structlog.wrap_logger(logging.getLogger(logger_name), COMMON_PROCESSORS, **kwargs)
    else:
        logger = logging.getLogger(logger_name)
    return logger


luigi.interface.InterfaceLogging.setup(luigi.interface.core())

gdal.SetConfigOption("CPL_DEBUG", "ON")
gdal.ConfigurePythonLogging(logger_name="gdal", enable_debug=True)

try:
    logging_conf = pkg_resources.resource_filename("insar", "logging.cfg")
    logging.config.fileConfig(logging_conf)
    print(f"Logging configuration loaded from {logging_conf}")
except KeyError:
    print(f"Error loading logging configuration from {logging_conf}")
    pass

ROOT_LOGGER = getLogger()
GDAL_LOGGER = getLogger("gdal")
LUIGI_LOGGER = getLogger("luigi-interface")

TASK_LOGGER = getLogger("task", stack_info=True)
STATUS_LOGGER = getLogger("status")
GAMMA_LOGGER = getLogger("gamma")

GAMMA_LOGGER.info("Starting GAMMA logger")

#@luigi.Task.event_handler(luigi.Event.FAILURE)
#def on_failure(task, exception):
#    """Capture any Task Failure here."""
#    TASK_LOGGER.exception(
#        "Task failed",
#        task=task.get_task_family(),
#        params=task.to_str_params(),
#        stack_id=getattr(task, "stack_id", ""),
#        stack_info=True,
#        status="failure",
#        exception=exception.__str__(),
#        traceback=traceback.format_exc().splitlines(),
#    )
#
#
#@luigi.Task.event_handler(luigi.Event.SUCCESS)
#def on_success(task):
#    """Capture any Task Success here."""
#    TASK_LOGGER.info(
#        "Task succeeded",
#        task=task.get_task_family(),
#        params=task.to_str_params(),
#        stack_id=getattr(task, "stack_id", ""),
#        status="success",
#    )

print("Logging setup complete")
