from pathlib import Path
import luigi

import os
import re
import os.path
from pathlib import Path
import luigi
import luigi.configuration
import pandas as pd
import osgeo.gdal
import json
import structlog

import insar
from insar.constant import SCENE_DATE_FMT
from insar.sensors import identify_data_source, get_data_swath_info, acquire_source_data, S1_ID, RSAT2_ID, PALSAR_ID
from insar.sensors.s1 import ANY_S1_SAFE_PATTERN
from insar.project import ProcConfig
from insar.generate_slc_inputs import query_slc_inputs, slc_inputs
from insar.logs import STATUS_LOGGER

from insar.workflow.luigi.utils import DateListParameter, PathParameter, tdir, simplify_dates, calculate_primary

class DataDownload(luigi.Task):
    """
    Downloads/copies the raw source data for a scene, for all requested polarisations.
    """

    data_path = PathParameter()
    poeorb_path = PathParameter()
    resorb_path = PathParameter()
    output_dir = PathParameter()
    polarization = luigi.ListParameter()
    workdir = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{Path(self.data_path).stem}_download.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(data_path=self.data_path)
        failed = False

        try:
            structlog.threadlocal.clear_threadlocal()
            structlog.threadlocal.bind_threadlocal(
                task="Data download",
                data_path=self.data_path,
                polarisation=self.polarization
            )

            log.info("Beginning data download")

            # Setup sensor-specific data acquisition info
            constellation, _, _ = identify_data_source(self.data_path)
            kwargs = {}

            if constellation == S1_ID:
                kwargs["poeorb_path"] = self.poeorb_path
                kwargs["resorb_path"] = self.resorb_path
            elif constellation == RSAT2_ID:
                # RSAT2 has no extra info
                pass
            elif constellation == PALSAR_ID:
                # ALOS PALSAR has no extra info
                pass
            else:
                raise RuntimeError(f"Unsupported constellation: {constellation}")

            outdir = Path(self.output_dir)
            outdir.mkdir(parents=True, exist_ok=True)

            acquire_source_data(
                self.data_path,
                outdir,
                self.polarization,
                **kwargs
            )

            log.info("Data download complete")
        except:
            log.error("Data download failed with exception", exc_info=True)
            failed = True
        finally:
            with self.output().open("w") as f:
                if failed:
                    f.write(str(self.data_path))
                else:
                    f.write("")


class InitialSetup(luigi.Task):
    """
    Runs the initial setup of insar processing workflow by
    creating required directories and file lists
    """

    stack_id = luigi.Parameter()
    proc_file = PathParameter()
    include_dates = DateListParameter()
    exclude_dates = DateListParameter()
    shape_file = PathParameter()
    source_data = luigi.ListParameter()
    orbit = luigi.Parameter()
    sensor = luigi.OptionalParameter()
    polarization = luigi.ListParameter()
    outdir = PathParameter()
    workdir = PathParameter()
    burst_data_csv = PathParameter()
    poeorb_path = PathParameter()
    resorb_path = PathParameter()
    cleanup = luigi.BoolParameter()
    dem_img = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_initialsetup_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("initial setup task", sensor=self.sensor)

        with open(self.proc_file, "r") as proc_file_obj:
            proc_config = ProcConfig.from_file(proc_file_obj)

        outdir = Path(proc_config.output_path)
        pols = list(self.polarization)

        # If we have a shape file, query the DB for scenes in that extent
        # TBD: The database geospatial/temporal query is currently Sentinel-1 only
        # GH issue: https://github.com/GeoscienceAustralia/gamma_insar/issues/261
        if self.shape_file and proc_config.sensor == "S1":
            # get the relative orbit number, which is int value of the numeric part of the track name
            # Note: This is S1 specific...
            rel_orbit = int(re.findall(r"\d+", str(proc_config.track))[0])

            # Convert luigi half-open DateInterval into the inclusive tuple ranges we use
            init_include_dates = [(d.date_a, d.date_b) for d in self.include_dates or []]
            init_exclude_dates = [(d.date_a, d.date_b) for d in self.exclude_dates or []]

            # Find the maximum extent of the queried dates
            include_dates = sorted(simplify_dates(init_include_dates, init_exclude_dates))
            min_date = include_dates[0][0]
            max_date = max([d[1] for d in include_dates])

            log.info(
                "Simplified final include dates",
                final_dates=include_dates,
                initial_includes=init_include_dates,
                initial_excludes=init_exclude_dates
            )

            # Query SLCs that match our search criteria for the maximum span
            # of dates that covers all of our include dates.
            slc_query_results = query_slc_inputs(
                str(proc_config.database_path),
                str(self.shape_file),
                min_date,
                max_date,
                str(self.orbit),
                rel_orbit,
                pols,
                self.sensor
            )

            if slc_query_results is None:
                raise ValueError(
                    f"No {pols} data was returned for {str(self.shape_file)} "
                    f"from date: {min_date} "
                    f"to date: {max_date} "
                    f"orbit: {self.orbit} "
                    f"sensor: {self.sensor} "
                    f"in DB: {str(proc_config.database_path)}"
                )

            slc_inputs_df = pd.concat(
                [slc_inputs(slc_query_results[pol]) for pol in pols],
                ignore_index=True
            )

            # Filter out dates we don't care about - as our search query is for
            # a single giant span of dates, but our include dates may be more fine
            # grained than the query supports.
            exclude_indices = []

            for index, row in slc_inputs_df.iterrows():
                date = row["date"]

                keep = any(date >= lhs or date <= rhs for lhs,rhs in include_dates)
                if not keep:
                    exclude_indices.append(index)

            slc_inputs_df.drop(exclude_indices, inplace=True)

        # Otherwise, create an empty dataframe
        else:
            slc_inputs_df = pd.DataFrame()
            init_include_dates = []
            init_exclude_dates = []

        # Determine the selected sensor(s) from the query, for directory naming
        additional_scenes = list(self.source_data or [])
        selected_sensors = "NONE"
        num_input_scenes = len(slc_inputs_df) + len(additional_scenes)

        if num_input_scenes > 0:
            # Compile list of source data to acquire / 'download'
            download_list = additional_scenes

            if len(slc_inputs_df) > 0:
                selected_sensors = slc_inputs_df.sensor.unique()
                selected_sensors = "_".join(sorted(selected_sensors))

                download_list = download_list + list(slc_inputs_df.url.unique())

            # download slc data
            download_dir = outdir / proc_config.raw_data_dir

            os.makedirs(download_dir, exist_ok=True)

            download_tasks = []
            for slc_url in download_list:
                _, _, scene_date = identify_data_source(slc_url)

                download_tasks.append(
                    DataDownload(
                        data_path=slc_url.rstrip(),
                        polarization=self.polarization,
                        poeorb_path=self.poeorb_path,
                        resorb_path=self.resorb_path,
                        workdir=self.workdir,
                        output_dir=download_dir / scene_date,
                    )
                )
            yield download_tasks

            # Detect scenes w/ incomplete/bad raw data, and remove those scenes from
            # processing while logging the situation for post-processing analysis.
            for _task in download_tasks:
                with open(_task.output().path) as fid:
                    failed_file = fid.readline().strip()
                    if not failed_file:
                        continue

                    _, _, scene_date = identify_data_source(failed_file)

                    log.info(
                        f"corrupted zip file detected, removed whole date from processing",
                        failed_file=failed_file,
                        scene_date=scene_date
                    )

                    if failed_file in additional_scenes:
                        additional_scenes.remove(failed_file)
                    else:
                        scene_date = f"{scene_date[0:4]}-{scene_date[4:6]}-{scene_date[6:8]}"
                        indexes = slc_inputs_df[slc_inputs_df["date"].astype(str) == scene_date].index
                        slc_inputs_df.drop(indexes, inplace=True)

        # Add any explicit source data files into the "inputs" data frame
        for data_path in additional_scenes:
            _, _, scene_date = identify_data_source(data_path)

            for swath_data in get_data_swath_info(data_path, download_dir / scene_date):
                if swath_data["polarization"] not in pols:
                    log.info(
                        "Skipping source data which does not match stack polarisations",
                        source_file=data_path,
                        source_pol=swath_data["polarization"],
                        stack_pols=pols
                    )
                    continue

                slc_inputs_df = slc_inputs_df.append(swath_data, ignore_index=True)

        # save slc burst data details which is used by different tasks
        slc_inputs_df.to_csv(self.burst_data_csv)
        num_scenes = len(slc_inputs_df)

        if num_scenes == 0:
            log.info("Stack setup failed - no valid scenes specified!")

            # Touch an empty scenes.list just to make it clear there are
            # simply no scenes in this stack...
            (outdir / proc_config.list_dir / 'scenes.list').touch()

            with self.output().open("w") as out_fid:
                out_fid.write("")

            return

        # Determine stack extents
        stack_extent = None

        for swath_extent in slc_inputs_df["swath_extent"]:
            if not stack_extent:
                stack_extent = swath_extent
            else:
                scene_min, scene_max = stack_extent
                swath_min, swath_max = swath_extent

                scene_min = (min(scene_min[0], swath_min[0]), min(scene_min[1], swath_min[1]))
                scene_max = (max(scene_max[0], swath_max[0]), max(scene_max[1], swath_max[1]))

                stack_extent = (scene_min, scene_max)

        # Write reference scene before we start processing
        formatted_scene_dates = set([str(dt).replace("-", "") for dt in slc_inputs_df["date"]])
        ref_scene_date = calculate_primary(formatted_scene_dates)
        log.info("Automatically computed primary reference scene date", ref_scene_date=ref_scene_date)

        with open(outdir / proc_config.list_dir / 'primary_ref_scene', 'w') as ref_scene_file:
            ref_scene_file.write(ref_scene_date.strftime(SCENE_DATE_FMT))

        # Write scenes list
        with open(outdir / proc_config.list_dir / 'scenes.list', 'w') as scenes_list_file:
            scenes_list_file.write('\n'.join(sorted(formatted_scene_dates)))

        with self.output().open("w") as out_fid:
            out_fid.write("")

        # Update .proc file "auto" reference scene
        if proc_config.ref_primary_scene.lower() == "auto":
            proc_config.ref_primary_scene = ref_scene_date.strftime(SCENE_DATE_FMT)

            with open(self.proc_file, "w") as proc_file_obj:
                proc_config.save(proc_file_obj)

        # Write high level workflow metadata
        _, gamma_version = os.path.split(os.environ["GAMMA_INSTALL_DIR"])[-1].split("-")
        workdir = Path(self.workdir)

        metadata = {
            # General workflow parameters
            #
            # Note: This is also accessible indirectly in the log files, and
            # potentially in other plain text files - but repeated here
            # for easy access for external software so it doesn't need to
            # know the nity gritty of all our auxilliary files or logs.
            "stack_id": str(self.stack_id),
            # TODO: We may want to have framing definition specific metadata
            # - this implies we need a concept of framing definitions (for which GA's S1 definition would be one of them)
            #"track_frame_sensor": f"{self.track}_{self.frame}_{selected_sensors}",
            "original_work_dir": Path(self.outdir).as_posix(),
            "original_job_dir": workdir.as_posix(),
            "shape_file": str(self.shape_file),
            "database": str(proc_config.database_path),
            "source_data": self.source_data,
            "stack_extent": stack_extent,
            "poeorb_path": str(self.poeorb_path),
            "resorb_path": str(self.resorb_path),
            "source_data_path": str(os.path.commonpath(list(download_list))),
            "dem_path": str(self.dem_img),
            "primary_ref_scene": ref_scene_date.strftime(SCENE_DATE_FMT),
            "include_dates": [(d1.strftime(SCENE_DATE_FMT), d2.strftime(SCENE_DATE_FMT)) for d1,d2 in init_include_dates],
            "exclude_dates": [(d1.strftime(SCENE_DATE_FMT), d2.strftime(SCENE_DATE_FMT)) for d1,d2 in init_exclude_dates],
            "burst_data": str(self.burst_data_csv),
            "num_scene_dates": len(formatted_scene_dates),
            "polarizations": pols,

            # Software versions used for processing
            "gamma_version": gamma_version,
            "gamma_insar_version": insar.__version__,
            "gdal_version": str(osgeo.gdal.VersionInfo()),
        }

        # We write metadata to BOTH work and out dirs
        with (outdir / "metadata.json").open("w") as file:
            json.dump(metadata, file, indent=2)

        with (workdir / "metadata.json").open("w") as file:
            json.dump(metadata, file, indent=2)

