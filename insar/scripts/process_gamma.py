#!/usr/bin/env python

import traceback
from typing import List, Tuple
import luigi
import luigi.configuration
import logging
import logging.config
import structlog
import pkg_resources

from insar.logs import TASK_LOGGER, STATUS_LOGGER, COMMON_PROCESSORS
from insar.workflow.luigi.ard import ARD, ARDWorkflow

@luigi.Task.event_handler(luigi.Event.FAILURE)
def on_failure(task, exception):
    """Capture any Task Failure here."""
    TASK_LOGGER.exception(
        "Task failed",
        task=task.get_task_family(),
        params=task.to_str_params(),
        stack_id=getattr(task, "stack_id", ""),
        stack_info=True,
        status="failure",
        exception=exception.__str__(),
        traceback=traceback.format_exc().splitlines(),
    )


@luigi.Task.event_handler(luigi.Event.SUCCESS)
def on_success(task):
    """Capture any Task Succes here."""
    TASK_LOGGER.info(
        "Task succeeded",
        task=task.get_task_family(),
        params=task.to_str_params(),
        stack_id=getattr(task, "stack_id", ""),
        status="success",
    )


def run():
    # Configure logging from built-in script logging config file
    logging_conf = pkg_resources.resource_filename("insar", "logging.cfg")
    logging.config.fileConfig(logging_conf)

    with open("insar-log.jsonl", "a") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj), processors=COMMON_PROCESSORS)

        try:
            luigi.run()
        except Exception as e:
            # Log all exceptions to the status log
            state = e.state if hasattr(e, "state") else {}
            STATUS_LOGGER.error("Unhandled exception running ARD workflow", exc_info=True, **state)

            # But don't catch them, release them back to Luigi
            raise e


if __name__ == "__name__":
    run()
