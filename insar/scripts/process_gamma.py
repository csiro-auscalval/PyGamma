#!/usr/bin/env python
import os
import traceback
from pathlib import Path
from typing import Dict, Any

import luigi
import luigi.configuration
import logging
import logging.config
import structlog
import pkg_resources

from insar.logs import TASK_LOGGER, STATUS_LOGGER, COMMON_PROCESSORS
from insar.workflow.luigi.ard import ARD

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


def run_ard_inline(args: Dict[str, Any]):
    """
    This function simply runs the ARD workflow directly in the same thread of the caller.

    This is opposed to `luigi.run` and `luigi.build` DAG execution which runs the tasks
    in one (or more) separate processes (assuming local scheduler).

    Ignoring differences in scheduling of tasks to processes/threads, logically this
    function should execute the same tasks with the exact same arguments (in dependency
    order), and thus should produce identical outcomes to `luigi.run` / `luigi.build`.

    The reason we have this function is primarily for unit testing - where we want to be
    able to have assertions and exceptions raised up the stack into pytest, which does
    not happen while using `luigi.run` or `luigi.build` as tasks run in other processes
    and exceptions get eaten by Luigi's own exception handling/logging code.

    :param args:
        The dictionary of parameters to be passed into the top-level ARD task.
    """

    from luigi.task import flatten

    # Configure logging into the job dir
    job_dir = Path(args["workdir"])
    os.chdir(job_dir)

    # Configure logging from built-in script logging config file
    logging_conf = pkg_resources.resource_filename("insar", "logging.cfg")
    logging.config.fileConfig(logging_conf)

    with (job_dir / "insar-log.jsonl").open("a") as fobj:
        structlog.configure(logger_factory=structlog.PrintLoggerFactory(fobj), processors=COMMON_PROCESSORS)

        # Create top level ARD task
        ard = ARD(**args)
        tasks = [ard]

        # Process workflow DAG
        while tasks:
            current = tasks[-1]
            if current.complete():
                tasks.pop()
                continue

            # Check and run direct depedencies
            pending_deps = [dep for dep in current.deps() if not dep.complete()]
            if pending_deps:
                tasks += pending_deps
                continue

            # Run task...
            task_gen = current.run()
            while task_gen:
                try:
                    requires = next(task_gen)
                except StopIteration:
                    break

                new_req = flatten(requires)
                pending_deps = [dep for dep in new_req if not dep.complete()]
                if pending_deps:
                    break

            # Run any dynamic dependencies
            if pending_deps:
                tasks += pending_deps
                continue

            # Otherwise run is complete, no more dependencies, we're done!
            tasks.pop()


if __name__ == "__name__":
    run()
