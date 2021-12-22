"""
Logging configuration for InSAR logs

Defines structured logging for:
    * Task messages     -- qualname task
    * Status messages   -- qualname status
    * Luigi interface   -- qualname luigi-interface
"""

import logging
import contextlib
from pathlib import Path
from typing import Union
import pkg_resources

import structlog
from structlog.processors import JSONRenderer

from insar.subprocess_utils import working_directory


COMMON_PROCESSORS = [
    structlog.threadlocal.merge_threadlocal,
    structlog.stdlib.add_log_level,
    structlog.processors.TimeStamper(fmt="ISO"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    JSONRenderer(sort_keys=True),
]


def get_wrapped_logger(
    logger_name: str = "root", **kwargs,
):
    """ Returns a struct log equivalent for the named logger """
    logger = structlog.wrap_logger(
        logging.getLogger(logger_name), COMMON_PROCESSORS, **kwargs
    )
    return logger


class FormatJSONL(logging.Formatter):
    """ Prevents printing of the stack trace to enable JSON lines output """

    def formatException(self, ei):
        """ Disables printing separate stack traces """
        return


TASK_LOGGER = get_wrapped_logger("task", stack_info=True)
STATUS_LOGGER = get_wrapped_logger("status")

INTERFACE_LOGGER = logging.getLogger("luigi-interface")


@contextlib.contextmanager
def logging_directory(path: Union[str, Path]):
    """
    A context manager that redirects the insar log into the specified directory for the
    lifetime of the manager.

    Once the manager loses context, the log files are closed leaving the logs in an
    unusable state the user will need to reinitalise if they plan to continue using them.
    """

    if not isinstance(path, Path):
        path = Path(path)

    # Configure logging into the specified path
    with working_directory(path):
        # Configure logging from built-in script logging config file
        logging_conf = pkg_resources.resource_filename("insar", "logging.cfg")
        logging.config.fileConfig(logging_conf)

        with (path / "insar-log.jsonl").open("a") as fobj:
            structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj), processors=COMMON_PROCESSORS)

            yield
