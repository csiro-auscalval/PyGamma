#!/usr/bin/python3

import os
import sys
from os.path import join as pjoin, basename, getsize, splitext, exists, dirname
import fnmatch
import zipfile
import shutil
import datetime
import logging

from structlog import wrap_logger
from structlog.processors import JSONRenderer
from mpi4py import MPI

import xml.etree.ElementTree as ET

from .initialize_proc_file import get_path
from .constant import SAFE_FMT, S1_SOURCE_DIR_FMT, DATE_FMT
from .constant import Wildcards, MatchStrings, FolderNames, ErrorMessages

STATUS_LOGGER = wrap_logger(
    logging.getLogger("status"), processors=[JSONRenderer(indent=1, sort_keys=True)]
)
ERROR_LOGGER = wrap_logger(
    logging.getLogger("errors"), processors=[JSONRenderer(indent=1, sort_keys=True)]
)


class S1DataDownload:
    def __init__(
        self,
        raw_data_path=None,
        s1_dir_path=None,
        download_list_path=None,
        polarization=None,
        s1_orbits_path=None,
        raw_data_error=None,
    ):

        self.raw_data_path = raw_data_path
        self.s1_dir_path = s1_dir_path
        self.download_list_path = download_list_path
        self.polarization = polarization
        self.s1_orbits_path = s1_orbits_path
        self.download_list_files = None
        self.raw_data_error = raw_data_error
        self.archive = None

    def set_download_lists(self):
        with open(self.download_list_path, "r") as src:
            self.download_list_files = [
                splitext(fname.strip())[0].split() for fname in src.readlines()
            ]

    def get_archive(self, grid, dt, granule):
        self.archive = None
        source_file = pjoin(
            self.s1_dir_path,
            S1_SOURCE_DIR_FMT.format(
                y=dt[0:4], m=dt[4:6], g=grid, f="{}.zip".format(granule)
            ),
        )
        if not exists(source_file):
            return
        self.archive = zipfile.ZipFile(source_file)

    @staticmethod
    def get_acquisition(manifest_file):

        acquisition_details = {}
        tree = ET.parse(manifest_file)
        root = tree.getroot()

        start_dt = [
            item.text
            for item in root.iter(tag="{http://www.esa.int/safe/sentinel-1.0}startTime")
        ]
        end_dt = [
            item.text
            for item in root.iter(tag="{http://www.esa.int/safe/sentinel-1.0}stopTime")
        ]
        sensor = [
            item.text
            for item in root.iter(tag="{http://www.esa.int/safe/sentinel-1.0}number")
        ]

        if len(start_dt) != 1:
            return
        if len(end_dt) != 1:
            return
        if len(sensor) != 1:
            return

        start_acq_datetime = datetime.datetime.strptime(
            start_dt[0], "%Y-%m-%dT%H:%M:%S.%f"
        )
        end_acq_datetime = datetime.datetime.strptime(end_dt[0], "%Y-%m-%dT%H:%M:%S.%f")
        acquisition_details["start_datetime"] = start_acq_datetime
        acquisition_details["stop_datetime"] = end_acq_datetime
        acquisition_details["sensor"] = "S1{}".format(sensor[0])

        return acquisition_details

    @staticmethod
    def get_poeorb_orbit_file(orbit_file_path, acquisition):

        poeorb_path = pjoin(orbit_file_path, "POEORB", acquisition["sensor"])
        orbit_files = [f for f in os.listdir(poeorb_path)]
        start_date = (
            acquisition["start_datetime"] - datetime.timedelta(days=1)
        ).strftime("%Y%m%d")
        end_date = (
            acquisition["start_datetime"] + datetime.timedelta(days=1)
        ).strftime("%Y%m%d")

        acq_orbit_file = fnmatch.filter(
            orbit_files, "*V{}*_{}*.EOF".format(start_date, end_date)
        )

        if not acq_orbit_file:
            return
        if len(acq_orbit_file) > 1:
            acq_orbit_file = sorted(
                acq_orbit_file,
                key=lambda x: datetime.datetime.strptime(
                    x.split("_")[5], "%Y%m%dT%H%M%S"
                ),
            )
        return pjoin(poeorb_path, acq_orbit_file[-1])

    @staticmethod
    def get_resorb_orbit_file(orbit_file_path, acquisition):
        def __start_strptime(dt):
            return datetime.datetime.strptime(dt, "V%Y%m%dT%H%M%S")

        def __stop_strptime(dt):
            return datetime.datetime.strptime(dt, "%Y%m%dT%H%M%S.EOF")

        resorb_path = pjoin(orbit_file_path, "RESORB", acquisition["sensor"])
        orbit_files = [f for f in os.listdir(resorb_path)]
        acq_date = acquisition["start_datetime"].strftime("%Y%m%d")
        start_time = acquisition["start_datetime"]
        end_time = acquisition["stop_datetime"]

        acq_orbit_file = fnmatch.filter(
            orbit_files, "*V{d}*_{d}*.EOF".format(d=acq_date)
        )
        acq_orbit_file = [
            f
            for f in acq_orbit_file
            if start_time >= __start_strptime(f.split("_")[6])
            and end_time <= __stop_strptime(f.split("_")[7])
        ]

        if not acq_orbit_file:
            return
        if len(acq_orbit_file) > 1:
            acq_orbit_file = sorted(
                acq_orbit_file,
                key=lambda x: datetime.datetime.strptime(
                    x.split("_")[5], "%Y%m%dT%H%M%S"
                ),
            )

        return pjoin(resorb_path, acq_orbit_file[-1])

    def archive_download(self, source_file, target_path):

        if not exists(target_path):
            os.makedirs(target_path)

        target_file = pjoin(target_path, basename(source_file))
        source_size = self.archive.getinfo(source_file).file_size
        if exists(target_file):
            if getsize(target_file) == source_size:
                return

        retry_cnt = 0
        while retry_cnt < 3:
            if retry_cnt > 0:
                STATUS_LOGGER.info(
                    "retry download number {}/3: {}".format(
                        retry_cnt, basename(target_file)
                    )
                )
            data = self.archive.open(source_file)
            with open(target_file, "wb") as f:
                shutil.copyfileobj(data, f)
            target_size = getsize(target_file)
            if target_size != source_size:
                retry_cnt += 1
            else:
                break
        if retry_cnt == 3:
            error = ErrorMessages.RAW_FILE_SIZE_ERROR_MSGS.value.format(
                s=source_size, d=target_size, f=basename(target_file)
            )
            ERROR_LOGGER.error(error)

    def get_scene_files(self, safe_dir, grid, dt, granule):

        self.get_archive(grid, dt, granule)
        if not self.archive:
            return

        pol = self.polarization.lower()

        source_m_paths = fnmatch.filter(
            self.archive.namelist(), "*measurement/*{}*".format(pol)
        )
        source_a_paths = fnmatch.filter(
            self.archive.namelist(), "*annotation/*{}*".format(pol)
        )
        source_c_paths = fnmatch.filter(
            self.archive.namelist(), "*/calibration/*{}*".format(pol)
        )

        manifest_path = fnmatch.filter(self.archive.namelist(), "*.safe")[0]
        quick_look_path = fnmatch.filter(
            self.archive.namelist(), "*/preview/quick-look.png"
        )[0]
        map_overlay_path = fnmatch.filter(
            self.archive.namelist(), "*/preview/map-overlay.kml"
        )[0]

        m_path = pjoin(safe_dir, FolderNames.MEASUREMENT.value)
        a_path = pjoin(safe_dir, FolderNames.ANNOTATION.value)
        c_path = pjoin(
            safe_dir, FolderNames.ANNOTATION.value, FolderNames.CALIBRATION.value
        )
        p_path = pjoin(safe_dir, FolderNames.PREVIEW.value)

        # download s1 files from the source
        self.archive_download(manifest_path, safe_dir)
        self.archive_download(quick_look_path, p_path)
        self.archive_download(map_overlay_path, p_path)

        for m_file in source_m_paths:
            self.archive_download(m_file, m_path)
        for a_file in source_a_paths:
            self.archive_download(a_file, a_path)
        for c_file in source_c_paths:
            self.archive_download(c_file, c_path)

        # download precise orbit files
        manifest_file = pjoin(safe_dir, "manifest.safe")
        acquisition = self.get_acquisition(manifest_file)

        # get precise orbit file from poeorb
        poeorb_file = self.get_poeorb_orbit_file(self.s1_orbits_path, acquisition)

        if poeorb_file:
            orbit_file = pjoin(dirname(safe_dir), basename(poeorb_file))
            if not exists(orbit_file):
                shutil.copyfile(poeorb_file, orbit_file)
        else:
            resorb_file = self.get_resorb_orbit_file(self.s1_orbits_path, acquisition)
            if not resorb_file:
                return
            orbit_file = pjoin(dirname(safe_dir), basename(resorb_file))
            if not exists(orbit_file):
                shutil.copyfile(resorb_file, orbit_file)
            STATUS_LOGGER.info(
                "POEORB file missing: using RESORB file: {}".format(
                    basename(orbit_file)
                )
            )

        return True

    def parallelise(self):
        def enum(*sequential, **named):
            """Handy way to fake an enumerated type in Python
            http://stackoverflow.com/questions/36932/how-can-i-represent-an-enum-in-python
            """
            enums = dict(zip(sequential, range(len(sequential))), **named)
            return type("Enum", (), enums)

        def job(specs):
            dt1, grid1, granule1 = specs[0], specs[1], specs[2]
            safe_dir1 = pjoin(self.raw_data_path, dt1, "{}.SAFE".format(granule1))
            flag = self.get_scene_files(safe_dir1, grid1, dt1, granule1)

            return flag

        def get_jobs():
            self.set_download_lists()
            job_list = []
            for item in self.download_list_files:
                job_list.append(item)
            return job_list

        # Define MPI message tags
        tags = enum("READY", "DONE", "EXIT", "START")

        # Initializations and preliminaries
        comm = MPI.COMM_WORLD  # get MPI communicator object
        size = comm.size  # total number of processes
        rank = comm.rank  # rank of this process
        status = MPI.Status()  # get MPI status object
        flags = []
        if rank == 0:
            # Master process executes code below
            tasks = get_jobs()  # get the tasks to be performed
            task_index = 0
            num_workers = size - 1
            closed_workers = 0
            while closed_workers < num_workers:
                data = comm.recv(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status)
                source = status.Get_source()
                tag = status.Get_tag()
                if tag == tags.READY:
                    if task_index < len(tasks):
                        comm.send(tasks[task_index], dest=source, tag=tags.START)
                        task_index += 1
                    else:
                        comm.send(None, dest=source, tag=tags.EXIT)

                elif tag == tags.DONE:
                    flags.append(data)
                elif tag == tags.EXIT:
                    closed_workers += 1
        else:
            while True:
                comm.send(None, dest=0, tag=tags.READY)
                task = comm.recv(source=0, tag=MPI.ANY_TAG, status=status)
                tag = status.Get_tag()
                if tag == tags.START:
                    # Do the work here
                    # change job method names here
                    result = job(task)
                    comm.send(result, dest=0, tag=tags.DONE)

                elif tag == tags.EXIT:
                    break

            comm.send(None, dest=0, tag=tags.EXIT)
        return flags

    def main(self):
        status = self.parallelise()
        with open(self.raw_data_error, "w") as fid:
            if all(status):
                fid.write("success")
            else:
                fid.write("failure")


if __name__ == "__main__":
    proc_file_path = sys.argv[1]
    path_name = get_path(proc_file_path)
    kwargs = {
        "raw_data_path": path_name["raw_data_dir"],
        "s1_dir_path": path_name["s1_dir"],
        "download_list_path": path_name["download_list"],
        "polarization": path_name["polarization"],
        "s1_orbits_path": path_name["s1_orbits"],
        "raw_data_error": path_name["extract_raw_errors"],
    }

    s1_download_data = S1DataDownload(**kwargs)
    s1_download_data.main()
