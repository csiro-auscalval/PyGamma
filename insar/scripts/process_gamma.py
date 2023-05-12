#!/usr/bin/env python3

import warnings
import luigi
import os

from insar.logs import STATUS_LOGGER as LOG, logging_directory
from insar.workflow.luigi.ard import ARD
from typing import Dict, Any
from pathlib import Path

warnings.simplefilter(action='error', category=UserWarning)

def run() -> None:
    print("PyGamma")
    luigi.run()
    print("Finished.")


def run_ard_inline(args: Dict[str, Any]) -> None:
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

    # Run Luigi from the working directory
    work_dir = Path(args["workdir"])
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(work_dir)

    # And have logs also written to the working directory
    with logging_directory(work_dir):
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

if __name__ == "__main__":
    run()
