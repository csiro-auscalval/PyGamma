#!/usr/bin/env python

"""
Generates a simple summary report on the outputs/progress of a processing job.

Refer to --help for details on parameters/usage and output options.
"""

import datetime
from pathlib import Path
import pandas as pd
import json
import platform
from typing import Optional, Sequence
from datetime import datetime, timedelta
from statistics import mean

# Note: While working with dates, we primarily keep things in the original DT_FMT_SHORT string
# formatting, we only convert to a date if we need to do date/time related ops.
# This just keeps the code simpler (no useless conversions to/from string)
DT_FMT_SHORT = "%Y%m%d"
DT_FMT_LONG = "%Y-%m-%d"
DT_FMT_JSON="%Y-%m-%dT%H:%M:%S.%fZ"
DT_FMT_NO_NS_JSON="%Y-%m-%dT%H:%M:%SZ"

def query_out_dir(dir: Path):
    """
    Scans a gamma insar output directory for information about the job that was processed.
    """

    print("Scanning output directory for information...")
    print("Out dir:", dir)

    # Load top level data
    all_scene_dates = []
    all_ifg_date_pairs = []

    with (dir / "lists" / "scenes.list").open("r") as scenes_file:
        all_scene_dates = [line.strip() for line in scenes_file]

    with (dir / "lists" / "ifgs.list").open("r") as ifgs_file:
        all_ifg_date_pairs = set([line.strip().replace(",", "-") for line in ifgs_file])

    with (dir / "metadata.json").open("r") as metadata_file:
        metadata = json.load(metadata_file)

    pols = metadata["polarisations"]

    # Sanity check
    assert len(all_scene_dates) == int(metadata["num_scene_dates"])

    # Iterate all SLC detect completed products
    all_scenes = set()
    completed_slcs = set()
    completed_coreg_slcs = set()
    completed_backscatter = set()
    coreg_quality_warn = {}

    for date_str in all_scene_dates:
        for pol in pols:
            all_scenes.add(f"{date_str}-{pol}")

        date_dir = dir / "SLC" / date_str
        if not date_dir.exists():
            continue

        # Check to see if data outputs exist
        is_complete = True

        for pol in pols:
            index = f"{date_str}-{pol}"
            is_complete = len(list(date_dir.glob(f"*_{pol}_*gamma0.tif"))) == 1

            if is_complete:
                completed_coreg_slcs.add(index)
                completed_backscatter.add(index)

        # Query ACCURACY_WARNING
        accuracy_warning_path = date_dir / "ACCURACY_WARNING"
        if accuracy_warning_path.exists():
            daz = None
            completed = None
            total = None

            # Note: even if file exists, it may not have had minimisation errors
            # - just warnings about poor burst coreg that didn't impede it's ability to coreg.
            with accuracy_warning_path.open("r") as warning_file:
                for line in warning_file:
                    if "Error on fine coreg" in line:
                        completed, total = line.split(" ")[-1].split("/")
                        completed = int(completed)
                        total = int(total)

                    if "daz: " in line:
                        daz = float(line.split(":")[1].strip().split(" ")[0])

            coreg_quality_warn[date_str] = (completed, total, daz)

    # Iterate all IFGs to detect completed products
    completed_ifgs = set()

    for date_pair in all_ifg_date_pairs:
        date_dir = dir / "INT" / date_pair
        if not date_dir.exists():
            continue

        # Check to see if data outputs exist
        is_complete = len(list(date_dir.glob("*geo_unw.tif"))) == 1

        if is_complete:
            completed_ifgs.add(date_dir.name)

    # Determine missing products
    missing_slc_dates = all_scenes - completed_coreg_slcs
    missing_backscatter_dates = all_scenes - completed_backscatter
    missing_ifgs = all_ifg_date_pairs - completed_ifgs

    return {
        "all_scene_dates": list(all_scene_dates),
        "all_ifg_date_pairs": list(all_ifg_date_pairs),
        "completed_slcs": list(completed_coreg_slcs),
        "missing_slcs": list(missing_slc_dates),
        "completed_coregs": list(completed_coreg_slcs),
        "missing_coregs": list(missing_backscatter_dates),
        "completed_backscatter": list(completed_backscatter),
        "missing_backscatter": list(missing_backscatter_dates),
        "completed_ifgs": list(completed_ifgs),
        "missing_ifgs": list(missing_ifgs),
        "coreg_quality_warn": coreg_quality_warn,
        "metadata": metadata,
    }


def query_job_dir(dir: Path):
    """
    Scans a gamma insar job directory for information about the job that was processed.
    """

    print("Scanning job directory for information...")
    print("Job dir:", dir)

    status_log_path = dir / "status-log.jsonl"
    insar_log_path = dir / "insar-log.jsonl"

    # Load metadata
    with (dir / "metadata.json").open("r") as metadata_file:
        metadata = json.load(metadata_file)

    stack_id = metadata["stack_id"]

    # Parse all job stdouts
    job_runs = []

    for stdout_path in dir.glob(f"{stack_id}.o*"):
        with stdout_path.open("r") as stdout_file:
            parsing_enabled = False

            for line in stdout_file:
                # Skip until we hit an NCI resource usage report
                if not parsing_enabled:
                    prefix = "resource usage on "
                    idx = line.lower().find(prefix)
                    if idx > -1:
                        idx += len(prefix)
                        timestamp = datetime.strptime(
                            line[idx:].strip(), "%Y-%m-%d %H:%M:%S:"
                        )
                        parsing_enabled = True
                        parsing_line = 1

                    continue

                # Example:
                #                 Resource Usage on 2021-05-11 13:42:00:
                #   Job Id:             22160355.gadi-pbs
                #   Project:            dg9
                #   Exit Status:        0
                #   Service Units:      77.79
                #   NCPUs Requested:    48                     NCPUs Used: 48
                #                                           CPU Time Used: 12:53:21
                #   Memory Requested:   192.0GB               Memory Used: 131.02GB
                #   Walltime requested: 02:00:00            Walltime Used: 00:48:37
                #   JobFS requested:    400.0GB                JobFS used: 0B
                if parsing_line == 1:
                    prefix, job_id = line.split(":")
                    assert prefix.strip().lower() == "job id"
                elif parsing_line == 2:
                    prefix, compute_project = line.split(":")
                    assert prefix.strip().lower() == "project"
                elif parsing_line == 3:
                    prefix, exit_status = line.split(":")
                    assert prefix.strip().lower() == "exit status"
                elif parsing_line == 4:
                    prefix, service_units = line.split(":")
                    assert prefix.strip().lower() == "service units"
                elif parsing_line == 8:
                    prefix = "walltime used:"
                    idx = line.lower().find(prefix)
                    assert idx > -1
                    idx += len(prefix)
                    h, m, s = [int(i) for i in line[idx:].split(":")]
                    walltime_used = timedelta(hours=h, minutes=m, seconds=s)

                parsing_line += 1

                if parsing_line > 9:
                    parsing_enabled = False

                    job_runs.append(
                        {
                            "timestamp": timestamp,
                            "job_id": job_id.strip(),
                            "compute_project": compute_project.strip(),
                            "exit_status": int(exit_status.strip().split(" ")[0]),
                            "service_units": float(service_units.strip()),
                            "walltime_used": walltime_used,
                        }
                    )

    # Determine total walltime and SU used
    total_walltime = timedelta()
    total_service_units = 0

    for run in job_runs:
        total_walltime += run["walltime_used"]
        total_service_units += run["service_units"]

    # Check Luigi structure to detect completed products
    # FIXME: Currently this script is completely independent of any insar dependencies,
    # but we probably want to use insar.paths to check the ACTUAL data product paths
    # instead of making assumptions about the luigi output files
    num_completed_coreg = len(list((dir / "tasks").glob("*_coreg_logs.out")))
    num_completed_coreg += len(list((dir / "tasks").glob("*coregisterdemprimary*.out")))
    num_completed_backscatter = len(list((dir / "tasks").glob("*nbr_logs.out")))
    num_completed_ifgs = len(list((dir / "tasks").glob("*_ifg_*_status_logs.out")))

    # Parse status.log to detect run/fail/completed products
    started_coreg = {}
    started_backscatter = {}
    started_ifgs = {}
    failed_coreg = {}
    failed_backscatter = {}
    failed_ifgs = {}
    completed_coreg = {}
    completed_backscatter = {}
    completed_ifgs = {}

    walltime_slc = {}
    walltime_coregistration = {}
    walltime_backscatter = {}
    walltime_ifgs = {}

    with (dir / "status-log.jsonl").open("r") as status_file:
        for line in status_file:
            log = json.loads(line[line.index("{") :])
            event = log["event"]

            try:
                timestamp = datetime.strptime(log["timestamp"], DT_FMT_JSON)
            except ValueError:
                timestamp = datetime.strptime(log["timestamp"], DT_FMT_NO_NS_JSON)

            if "DEM primary coregistration" in event:
                if "scene_date" not in log:
                    continue

                index = f"{log['scene_date']}-{log['polarisation']}"
                entry = (
                    timestamp,
                    log["polarisation"],
                    "DEM",
                    log["scene_date"],
                )

                if "Beginning DEM primary coregistration" in event:
                    if index in completed_coreg:
                        del completed_coreg[index]

                    if index in failed_coreg:
                        del failed_coreg[index]

                    started_coreg[index] = entry
                elif "DEM primary coregistration complete" in event:
                    completed_coreg[index] = entry

                    walltime = entry[0] - started_coreg[index][0]
                    walltime_coregistration[index] = walltime
                elif "DEM primary coregistration failed with exception" in event:
                    failed_coreg[index] = (
                        *entry,
                        log["exception"],
                    )

            elif "SLC coregistration" in event:
                # Skip higher level non-processing task logs
                if "secondary_date" not in log:
                    continue

                index = f"{log['secondary_date']}-{log['polarisation']}"
                entry = (
                    timestamp,
                    log["polarisation"],
                    log["primary_date"],
                    log["secondary_date"],
                )

                if "Beginning SLC coregistration" in event:
                    if index in completed_coreg:
                        del completed_coreg[index]

                    if index in failed_coreg:
                        del failed_coreg[index]

                    started_coreg[index] = entry
                elif "SLC coregistration complete" in event:
                    completed_coreg[index] = entry

                    walltime = entry[0] - started_coreg[index][0]
                    walltime_coregistration[index] = walltime
                elif "SLC coregistration failed with exception" in event:
                    failed_coreg[index] = (
                        *entry,
                        log["exception"],
                    )

            elif "normalised radar backscatter" in event.lower():
                # Skip higher level non-processing task logs
                if "scene_date" not in log:
                    continue

                index = f"{log['scene_date']}-{log['polarisation']}"
                entry = (
                    timestamp,
                    log["polarisation"],
                    log["scene_date"]
                )

                if "Beginning" in event:
                    if index in completed_backscatter:
                        del completed_backscatter[index]

                    if index in failed_backscatter:
                        del failed_backscatter[index]

                    started_backscatter[index] = entry
                elif "complete" in event:
                    completed_backscatter[index] = entry

                    walltime = entry[0] - started_backscatter[index][0]
                    walltime_backscatter[index] = walltime
                elif "failed with exception" in event:
                    failed_backscatter[index] = (
                        *entry,
                        log["exception"],
                    )

            elif "interferogram" in event.lower():
                # Skip higher level non-processing task logs
                if "primary_date" not in log:
                    continue

                date_pair = f"{log['primary_date']}-{log['secondary_date']}"
                entry = (timestamp, "VV", log["primary_date"], log["secondary_date"])

                if "Beginning interferogram processing" in event:
                    # Remove failed/completed status if we resumed!
                    if date_pair in completed_ifgs:
                        del completed_ifgs[date_pair]

                    if date_pair in failed_ifgs:
                        del failed_ifgs[date_pair]

                    started_ifgs[date_pair] = entry
                elif "Interferogram complete" in event:
                    completed_ifgs[date_pair] = entry

                    walltime = entry[0] - started_ifgs[date_pair][0]
                    walltime_ifgs[index] = walltime
                elif "Interferogram failed with exception" in event:
                    failed_ifgs[date_pair] = (
                        *entry,
                        log["exception"],
                    )

    assert num_completed_coreg == len(completed_coreg) + len(failed_coreg)
    assert num_completed_backscatter == len(completed_backscatter) + len(
        failed_backscatter
    )
    assert num_completed_ifgs == len(completed_ifgs) + len(failed_ifgs)

    return {
        "job_runs": job_runs,
        "total_walltime": total_walltime,
        "total_service_units": total_service_units,
        "started_backscatter": started_backscatter,
        "started_ifgs": started_ifgs,
        "failed_backscatter": failed_backscatter,
        "failed_ifgs": failed_ifgs,
        "completed_backscatter": completed_backscatter,
        "completed_ifgs": completed_ifgs,
        "walltime_slc": walltime_slc,
        "walltime_coregistration": walltime_coregistration,
        "walltime_backscatter": walltime_backscatter,
        "walltime_ifgs": walltime_ifgs,
    }

def generate_summary(job_dir: Optional[Path], out_dir: Optional[Path]):
    assert(job_dir or out_dir)

    # Load metadata (should exist in both work and job dir)
    with ((job_dir or out_dir) / "metadata.json").open("r") as metadata_file:
        metadata = json.load(metadata_file)

    pols = metadata["polarisations"]

    summary = {
        "timestamp": datetime.now(),
        "node": platform.node(),
        "metadata": metadata,
    }

    # Try and fill any gaps if the original dirs are still valid
    if not job_dir and Path(metadata["original_job_dir"]).exists():
        job_dir = Path(metadata["original_job_dir"])

    if not out_dir and Path(metadata["original_work_dir"]).exists():
        out_dir = Path(metadata["original_work_dir"])

    # Query data from job/output directories
    job_query = query_job_dir(job_dir) if job_dir else None
    out_query = query_out_dir(out_dir) if out_dir else None

    summary["job_dir"] = job_dir
    summary["job_query"] = job_query
    summary["out_dir"] = out_dir
    summary["out_query"] = out_query

    # Sanity check job dir <-> work dir correlation and use both to get complete reporting coverage
    if job_query and out_query:
        # Remove failed from missing...
        for key in job_query["failed_backscatter"].keys():
            if key in out_query["missing_backscatter"]:
                out_query["missing_backscatter"].remove(key)

        for key in job_query["failed_ifgs"].keys():
            if key in out_query["missing_ifgs"]:
                out_query["missing_ifgs"].remove(key)

        # Get totals
        num_total_slc_scenes = len(out_query["all_scene_dates"])
        num_total_ifg_scenes = len(out_query["all_ifg_date_pairs"])

        num_completed_backscatter = len(job_query["completed_backscatter"])
        num_completed_ifgs = len(job_query["completed_ifgs"])
        num_completed_backscatter_outdir = len(out_query["completed_backscatter"])
        num_completed_ifgs_outdir = len(out_query["completed_ifgs"])
        # FIXME: primary reference date issues?
        #assert num_completed_backscatter == num_completed_backscatter_outdir
        assert num_completed_ifgs == num_completed_ifgs_outdir

        num_failed_backscatter = len(job_query["failed_backscatter"])
        num_failed_ifgs = len(job_query["failed_ifgs"])

        num_missing_backscatter = len(out_query["missing_backscatter"])
        num_missing_ifgs = len(out_query["missing_ifgs"])

        assert (
            num_completed_backscatter + num_failed_backscatter + num_missing_backscatter
            == num_total_slc_scenes * len(pols)
        )

        assert (
            num_completed_ifgs + num_failed_ifgs + num_missing_ifgs
            == num_total_ifg_scenes
        )

    # If we only have a job dir & data doesn't exist, we can't get an accurate list of expected outputs from
    # the files that alredy exist (Note: we 'could' run the DB query again...)
    elif job_query:
        # Crude estimate if we don't have an out dir to read scene lists from...
        num_total_slc_scenes = len(job_query["started_backscatter"]) // len(pols)
        num_total_ifg_scenes = len(job_query["started_ifgs"])

        num_completed_backscatter = len(job_query["completed_backscatter"])
        num_completed_ifgs = len(job_query["completed_ifgs"])

        num_failed_backscatter = len(job_query["failed_backscatter"])
        num_failed_ifgs = len(job_query["failed_ifgs"])

        num_missing_backscatter = "?"
        num_missing_ifgs = "?"

    # If we only have a data dir, we don't have any failure info (as all that is logged in the job dir)
    else:
        num_total_slc_scenes = len(out_query["all_scene_dates"])
        num_total_ifg_scenes = len(out_query["all_ifg_date_pairs"])

        num_completed_backscatter = len(out_query["completed_backscatter"])
        num_completed_ifgs = len(out_query["completed_ifgs"])

        num_failed_backscatter = "?"
        num_failed_ifgs = "?"

        num_missing_backscatter = len(out_query["missing_backscatter"])
        num_missing_ifgs = len(out_query["missing_ifgs"])

    summary["num_total_slc_scenes"] = num_total_slc_scenes
    summary["num_total_ifg_scenes"] = num_total_ifg_scenes
    summary["num_completed_backscatter"] = num_completed_backscatter
    summary["num_completed_ifgs"] = num_completed_ifgs
    summary["num_failed_backscatter"] = num_failed_backscatter
    summary["num_failed_ifgs"] = num_failed_ifgs
    summary["num_missing_backscatter"] = num_missing_backscatter
    summary["num_missing_ifgs"] = num_missing_ifgs

    # For each failed scene, report errors
    product_errors = {}

    if job_query and (num_failed_backscatter > 0 or num_failed_ifgs > 0):
        # Index jsonl file
        jsonl_path = job_dir / "insar-log.jsonl"
        print(f"Indexing {jsonl_path}...", end="")

        jsonl_index = []
        with jsonl_path.open("r") as log_file:
            while True:
                offset = log_file.tell()
                line = log_file.readline()

                # Break on EOF
                if not line:
                    break

                entry = json.loads(line.strip())
                jsonl_index.append((offset, entry["timestamp"], entry["event"]))

        print(" complete!")

        def read_log_entry(line):
            offset, timestamp, event = jsonl_index[line]

            with (job_dir / "insar-log.jsonl").open("r") as log_file:
                log_file.seek(offset)
                return json.loads(log_file.readline())

        failed_products = {
            "backscatter": job_query["failed_backscatter"],
            "IFG": job_query["failed_ifgs"]
        }

        product_tasks = {
            "backscatter": "SLC backscatter",
            "IFG": "IFG processing"
        }

        for product, failed in failed_products.items():
            failures = []
            task_id = product_tasks[product]

            for index, entry in failed.items():
                timestamp = entry[0]

                # Find matching log entries within 5min of failure
                errors = []
                time_threshold = timedelta(minutes=5)

                for line_no, (line_offset, line_timestamp, line_event) in enumerate(jsonl_index):
                    # Ignore non-failure entries
                    if "Failed to execute" not in line_event:
                        continue

                    line_timestamp = datetime.strptime(line_timestamp, DT_FMT_JSON)

                    # Ignore entries that are too distant from failure
                    dt_timestamp = timestamp - line_timestamp
                    if abs(dt_timestamp) > time_threshold:
                        continue

                    # Ignore entries that aren't SLC backscatter!
                    log_entry = read_log_entry(line_no)
                    if "task" not in log_entry or log_entry["task"] != task_id:
                        continue

                    errors.append(log_entry)

                failures.append((index, errors))

            product_errors[product] = failures

    summary["product_errors"] = product_errors

    # Generate compute remaining estimates
    num_incomplete_slcs = 0  # TODO
    num_incomplete_coregs = 0  # TODO

    if num_missing_backscatter == "?":
        num_incomplete_backscatter = num_failed_backscatter
    elif num_failed_backscatter == "?":
        num_incomplete_backscatter = num_missing_backscatter
    else:
        num_incomplete_backscatter = num_missing_backscatter + num_failed_backscatter

    if num_missing_ifgs == "?":
        num_incomplete_ifgs = num_failed_ifgs
    elif num_failed_ifgs == "?":
        num_incomplete_ifgs = num_missing_ifgs
    else:
        num_incomplete_ifgs = num_missing_ifgs + num_failed_ifgs

    if job_query and (num_incomplete_slcs or num_incomplete_coregs or num_incomplete_backscatter or num_incomplete_ifgs):
        walltime_slc = job_query["walltime_slc"]
        walltime_coregistration = job_query["walltime_coregistration"]
        walltime_backscatter = job_query["walltime_backscatter"]
        walltime_ifgs = job_query["walltime_ifgs"]

        if walltime_slc:
            mean_walltime_slc = mean([wt.total_seconds() for wt in walltime_slc.values()])
            slc_eta_secs = mean_walltime_slc * num_incomplete_slcs
        else:
            slc_eta_secs = (10 * 60) * num_incomplete_slcs  # Assume 10min if we don't know any better

        if walltime_coregistration:
            mean_walltime_coregistration = mean([wt.total_seconds() for wt in walltime_coregistration.values()])
            coreg_eta_secs = mean_walltime_coregistration * num_incomplete_coregs
        else:
            coreg_eta_secs = (20 * 60) * num_incomplete_coregs  # Assume 20min if we don't know any better

        if walltime_backscatter:
            mean_walltime_backscatter = mean([wt.total_seconds() for wt in walltime_backscatter.values()])
            backscatter_eta_secs = mean_walltime_backscatter * num_incomplete_backscatter
        else:
            backscatter_eta_secs = (20 * 60) * num_incomplete_backscatter  # Assume 20min if we don't know any better

        if walltime_ifgs:
            mean_walltime_ifgs = mean([wt.total_seconds() for wt in walltime_ifgs.values()])
            ifg_eta_secs = mean_walltime_ifgs * num_incomplete_ifgs
        else:
            ifg_eta_secs = (15 * 60) * num_incomplete_ifgs  # Assume 15min if we don't know any better

        # General divide by 4, as we run 4 jobs concurrently w/ our standard workflow
        # TODO: This could be confirmed/parsed out of the job script / should probably be in metadata or .proc file
        eta_seconds = (slc_eta_secs + coreg_eta_secs + backscatter_eta_secs + ifg_eta_secs) // 4
        eta = timedelta(seconds=eta_seconds)

        summary["eta_breakdown"] = {
            "slc_eta_secs": slc_eta_secs,
            "coreg_eta_secs": coreg_eta_secs,
            "backscatter_eta_secs": backscatter_eta_secs,
            "ifg_eta_secs": ifg_eta_secs,
            "eta_weight": 0.25
        }

        summary["eta"] = eta

    return summary

def export_report_json(summary: dict, out_json_path: Path):
    with out_json_path.open("w") as file:
        json.dump(summary, file, indent=2, default=str)

def print_header_line(msg=None, width=80, filler='='):
    line = filler * (width // len(filler))

    if not msg:
        print(line)
        return

    msg_len = len(msg)
    buffer_width = width - msg_len

    line = line[:(buffer_width-1) // 2] + " " + msg + " " + line[-(buffer_width-2)//2:]

    print(line)

def print_report(summary: dict):
    metadata = summary["metadata"]
    stack_id = metadata["stack_id"]
    job_query = summary["job_query"]
    out_query = summary["out_query"]
    pols = metadata["polarisations"]

    print_header_line()
    print_header_line("gamma_insar processing summary report")
    print_header_line(f"generated at {summary['timestamp']} on {summary['node']}")
    print_header_line()
    print("Stack ID:",stack_id)
    # FIXME: This doesn't always exist anymore (could be no-DB alos/rs2, or even no-DB S1 w/ source_data provided directly)
    #print("Temporal range:", min(metadata["include_dates"]), "-", max(metadata["include_dates"]))
    print("Shape file:", metadata["shape_file"])
    print("Database:", metadata["database"])
    # TBD: most coding standards enforce american spelling, but I figured for our printed outputs we want AU?
    print("Polarisations:", metadata["polarisations"])
    print("Total scenes:", metadata["num_scene_dates"])

    num_total_slc_scenes = summary["num_total_slc_scenes"]
    num_total_ifg_scenes = summary["num_total_ifg_scenes"]
    num_completed_backscatter = summary["num_completed_backscatter"]
    num_completed_ifgs = summary["num_completed_ifgs"]
    num_failed_backscatter = summary["num_failed_backscatter"]
    num_failed_ifgs = summary["num_failed_ifgs"]
    num_missing_backscatter = summary["num_missing_backscatter"]
    num_missing_ifgs = summary["num_missing_ifgs"]

    if job_query:
        # Report NCI processing details (resource usage / node info / total job success or fail / etc)
        print("")
        print_header_line("Run Summary")

        for run in job_query["job_runs"]:
            started = run["timestamp"]
            walltime = run["walltime_used"]
            su_used = run["service_units"]
            proj = run["compute_project"]
            print(f"[{started}] Job ran for {walltime} using {su_used} SU from {proj}")

        print("\nTotal walltime:", job_query["total_walltime"])
        print("Total SU used:", job_query["total_service_units"], "\n")

    # Report coregistration quality warnings
    if out_query and out_query["coreg_quality_warn"]:
        print("")
        print_header_line("SLC coregistration warnings")
        minor_warnings = 0

        for date, (completed, total, daz) in out_query["coreg_quality_warn"].items():
            if completed is not None:
                if daz is None:
                    print(f"[{date}] completely failed fine coreg!")
                else:
                    print(f"[{date}] failed on iter {completed}/{total}, achieved daz: {daz}")
            else:
                if daz is None:
                    # Not even worth mentioning in the human print out... too much noise for something
                    # so common and relatively insignificant
                    #print(f"[{date}] burst quality issues, minimisation still succeeded.")
                    minor_warnings += 1
                else:
                    print(f"[{date}] burst quality issues, only achieved daz: {daz}")

        print(f"{minor_warnings} SLC coregs had minor burst quality issues, but still achieved target daz.")

    # Report processing error messages
    for product, failures in summary["product_errors"].items():
        if not failures:
            continue

        print("")
        print_header_line(f"{product.capitalize()} failures")
        for index, errors in failures:
            if not errors:
                print(f"!! FAILED TO EXTRACT DETAILS FOR {index} {product} !!")

            for log_entry in errors:
                entry_desc = ""

                for idx_id in ["primary_date", "secondary_date", "scene_date"]:
                    if idx_id in log_entry:
                        entry_desc += f" | {idx_id}: {log_entry[idx_id]}"

                print(f"[{log_entry['timestamp']} | {log_entry['task']}{entry_desc}] {log_entry['event']}")
                print("\n".join(log_entry["cerr"]))

    # Report completion metrics (including estimated walltime/KSU to complete)
    print("")
    print_header_line("Product Summary")
    if num_total_slc_scenes and not isinstance(num_total_slc_scenes, str):
        completed_backscatter_pct = (num_completed_backscatter // (num_total_slc_scenes * len(pols))) * 100.0
    else:
        completed_backscatter_pct = num_total_slc_scenes  # copy the str value

    if num_total_ifg_scenes and not isinstance(num_total_ifg_scenes, str):
        completed_ifg_pct = (num_completed_ifgs / num_total_ifg_scenes) * 100.0
    else:
        completed_ifg_pct = num_total_ifg_scenes  # copy the str value

    print(
        f"Completed {num_completed_backscatter}/{num_total_slc_scenes * len(pols)} ({completed_backscatter_pct:.3f}%) backscatter products!"
    )
    print(
        f"Completed {num_completed_ifgs}/{num_total_ifg_scenes} ({completed_ifg_pct:.3f}%) IFG products!"
    )
    print(f"Missing {num_missing_backscatter} backscatter products!")
    print(f"Missing {num_missing_ifgs} IFG products!")
    print(f"Failed {num_failed_backscatter} backscatter products!")
    print(f"Failed {num_failed_ifgs} IFG products!")
    print()

    # Report time to complete based on estimated walltime
    if "eta" in summary:
        eta = summary["eta"]

        print("Estimated walltime to complete:", eta)

        # Report KSU to complete based on estimated walltime
        eta_hours = eta.total_seconds() / 3600
        # Assumes 48 cores, on normal queue (2.0 SU multiplier)
        print(f"Estimated SU to complete: {eta_hours * 48 * 2:.3f}")


def main(args: Optional[Sequence[str]] = None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a simple summary report on the outputs/progress of a processing job."
    )

    parser.add_argument(
        "path",
        type=str, nargs='+',
        help="The path of the job to report on (or a base dir from which --job-id queries from)",
    )

    parser.add_argument(
        "--job-id",
        type=str,
        help="The name of the processing job to look for, relative to the path (if path is a base path)",
    )

    parser.add_argument(
        "--print",
        action='store_true',
        help="Prints the summary report data to the terminal output",
    )

    parser.add_argument(
        "--json",
        help="Saves the summary report data as JSON into the specified file path",
    )

    parser.add_argument(
        "--csv",
        help="Creates a very brief summary spreadsheet in csv format.",
    )

    args = parser.parse_args(args)

    # Validate inputs
    if args.json:
        json_path = Path(args.json)
        if not json_path.parent.exists():
            print("Directory for JSON file does not exist!")
            exit(1)

        if json_path.is_dir():
            print("Target JSON path is a directory, expected a file!")
            exit(1)

    if args.csv:
        csv_path = Path(args.csv)
        if not csv_path.parent.exists():
            print("Directory for CSV file does not exist!")
            exit(1)

        if csv_path.is_dir():
            print("Target CSV path is a directory, expected a file!")
            exit(1)

    summaries = {}

    # Find/query directories
    for path in args.path:
        target_dir = Path(path)
        if not target_dir.exists():
            print("Provided path does not exist:", target_dir)
            exit(1)

        metadata_path = target_dir / "metadata.json"
        if not metadata_path.exists():
            print("Provided path does not look like a stack path, missing metadata.json")
            exit(1)

        job_dir = None
        out_dir = None

        if args.job_id:
            job_dirs = list(target_dir.glob(f"job*{args.job_id}"))
            assert len(job_dirs) == 0 or len(job_dirs) == 1

            if job_dirs:
                job_dir = job_dirs[0]

            if (target_dir / args.job_id).exists():
                out_dir = target_dir / args.job_id

        else:
            is_job_dir = (target_dir / "insar-log.jsonl").exists()
            if is_job_dir:
                job_dir = target_dir
            else:
                out_dir = target_dir

        if not job_dir and not out_dir:
            print("Failed to find any job logs or data in target directory")
            exit(1)

        print("Job dir:", job_dir)
        print("Out dir:", out_dir)
        summary = generate_summary(job_dir, out_dir)
        stack_id = summary["metadata"]["stack_id"]

        if stack_id in summaries:
            # Check dirs
            dirs_match = summaries[stack_id]["job_dir"] == job_dir or summaries[stack_id]["out_dir"] == out_dir

            if dirs_match:
                print(f"Warning: Skipping duplicate summary for {stack_id}...")
            else:
                print(f"Error: Multiple jobs found for {stack_id}, thus script can only handle 1 occurrence of each frame.")
                exit(1)

        summaries[stack_id] = summary

    # Finally, generate report...
    if args.print:
        for stack_id, summary in summaries.items():
            print_report(summary)

    if args.json:
        export_report_json(summaries, json_path)

    if args.csv:
        with csv_path.open("w") as csv_file:
            csv_file.write("Frame,Completed IFGs,Total expected IFGs,Errors,Remaining,rough ETA (hours),comments,\n")

            for stack_id, summary in summaries.items():
                num_total = summary["num_total_ifg_scenes"]
                num_completed = summary["num_completed_ifgs"]
                num_failed = summary["num_failed_ifgs"]
                num_missing = summary["num_missing_ifgs"]

                if "eta" in summary:
                    eta = summary["eta"].total_seconds() // 3600
                else:
                    eta = 0

                csv_file.write(f"{stack_id},{num_completed},{num_total},{num_failed},{num_missing},{eta},\n")


if __name__ == "__main__":
    main()
