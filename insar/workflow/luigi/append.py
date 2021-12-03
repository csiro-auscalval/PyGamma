import itertools
from pathlib import Path
import pandas as pd
import luigi
import luigi.configuration
import json

from insar.coreg_utils import append_secondary_coreg_tree, load_coreg_tree
from insar.stack import load_stack_config, load_stack_scene_dates
from insar.project import ARDWorkflow
from insar.logs import STATUS_LOGGER
from insar.sensors import identify_data_source
from insar.constant import SCENE_DATE_FMT
from insar.stack import resolve_stack_scene_additional_files

from insar.workflow.luigi.utils import PathParameter, read_primary_date, tdir, get_scenes, read_rlks_alks
from insar.workflow.luigi.baseline import BaselineProcess
from insar.workflow.luigi.coregistration import CoregisterSecondary, get_coreg_kwargs
from insar.workflow.luigi.backscatter import ProcessBackscatter
from insar.workflow.luigi.interferogram import ProcessIFG
from insar.workflow.luigi.resume import ReprocessSingleSLC


class AppendDatesToStack(luigi.Task):
    """
    This task appends new dates to an existing stack, producing
    the additional coregistration & interferogram products for
    the new dates.
    """

    proc_file = PathParameter()
    stack_id = luigi.Parameter()

    append_idx = luigi.IntParameter()
    append_scenes = luigi.ListParameter()

    workflow = luigi.EnumParameter(enum=ARDWorkflow)

    # Orbit filter for S1 geospatial temporal query
    orbit = luigi.OptionalParameter()

    def output_path(self):
        proc_config = load_stack_config(self.proc_file)
        fname = f"{self.stack_id}_append_{self.append_idx}_status.out"
        return tdir(proc_config.job_path) / fname

    def output(self):
        return luigi.LocalTarget(self.output_path())

    def run(self):
        # TODO: This shares a fair bit of duplicate code w/ stack_setup.py as the processes are similar-ish
        # - we need to come back and clean this up / de-duplicate the code (though there's likely a better
        # design where setup and append can probably co-exist in a single task - i did attempt this but
        # wasted too much time / decided to just complicate things more w/ a new task to "get it done" first)

        log = STATUS_LOGGER.bind(stack_id=self.stack_id, append_idx=self.append_idx)
        if not self.append_scenes:
            log.info("No data to append to stack / nothing to process!")
            return

        log.info(
            "Appending dates to stack...",
            append_scenes=self.append_scenes
        )

        # Load stack details
        append_idx = self.append_idx
        proc_config = load_stack_config(self.proc_file)
        outdir = Path(proc_config.output_path)
        workdir = Path(proc_config.job_path)
        list_dir = outdir / proc_config.list_dir
        append_manifest = list_dir / f"append{append_idx}.manifest"
        append_dates_list = list_dir / f"scenes{append_idx}.list"
        metadata = json.loads((outdir / "metadata.json").read_text())
        shape_file = None
        burst_data_csv = metadata["burst_data"]
        pols = metadata["polarizations"]
        append_scenes = self.append_scenes
        primary_scene = read_primary_date(outdir)
        primary_pol = proc_config.polarisation

        if "shape_file" in metadata:
            shape_file = metadata["shape_file"]
            shape_file = Path(shape_file) if shape_file else None

        # Load the stack's existing scene data
        slc_inputs_df = pd.read_csv(burst_data_csv, index_col=0)

        # If the new scenes haven't had SLC generated yet, do so...
        # - this gate exists as Luigi w/ runtime dependencies will call run()
        # - once for each yield... thus we don't want to keep querying/appending/validating
        #
        # TODO: Longer term when we clean this up, this indicates we should split this into
        # distinct tasks w/ clear dependencies between each step in the process to avoid this
        # - as per the TODO above, this comes back to stack_setup shared logic, this subset of
        # - the task is a kind of 'append setup' + SLC generation combined
        append_dates = []

        if not append_dates_list.exists():
            # immediately make a deep copy of it, for validation later on
            original_slc_inputs_df = slc_inputs_df.copy(deep=True)

            # Add any explicit source data files into the "inputs" data frame
            slc_inputs_df = resolve_stack_scene_additional_files(
                slc_inputs_df,
                proc_config,
                pols,
                append_scenes,
                shape_file
            )

            append_dates = set(slc_inputs_df["date"].unique()) - set(original_slc_inputs_df["date"].unique())
            append_dates = [i.strftime(SCENE_DATE_FMT) for i in append_dates]

            # Drop duplicates (this is because of how Luigi works, run() is called multiple times w/ dynamic deps being yielded)
            # pandas can't handle lists? slc_inputs_df = slc_inputs_df.drop_duplicates()
            slc_inputs_df = slc_inputs_df.loc[slc_inputs_df.astype(str).drop_duplicates().index]

            # Sanity check that we've only added data / not removed or modified anything - data loss / corruption is unacceptable!
            # this includes dataframe indices (should be unchanged / append only).  This shouldn't be possible, as we only
            # append code now (previously code did merge dataframes) - but still better to be safe than sorry for future changes.
            for index, row in original_slc_inputs_df.iterrows():
                if not slc_inputs_df.loc[index].equals(row):
                    raise RuntimeError("Data corruption prevented, an existing stack scene entry does not match appended results")

            # Finally, if everything seems above board - save the new SLC inputs
            slc_inputs_df.to_csv(burst_data_csv)

            # Process the SLC of the new scenes
            append_scene_tasks = []

            for scene in append_dates:
                for pol in pols:
                    task = ReprocessSingleSLC(
                        proc_file = self.proc_file,
                        stack_id = self.stack_id,
                        polarization = pol,
                        burst_data_csv = burst_data_csv,
                        poeorb_path = proc_config.poeorb_path,
                        resorb_path = proc_config.resorb_path,
                        scene_date = scene,
                        ref_primary_tab = None,  # FIXME: GH issue #200
                        outdir = outdir,
                        workdir = workdir,
                        resume_token = "append"
                    )

                    append_scene_tasks.append(task)

            yield append_scene_tasks

            # Remove corrupt scenes, if any exist...
            corrupt_indices = []

            for task in append_scene_tasks:
                failed_file = Path(task.output().path).read_text().strip()
                if not failed_file:
                    continue

                _, _, scene_date = identify_data_source(failed_file)

                log.info(
                    f"corrupted zip file detected, removed whole date from processing",
                    failed_file=failed_file,
                    scene_date=scene_date
                )

                scene_date_dashed = f"{scene_date[0:4]}-{scene_date[4:6]}-{scene_date[6:8]}"
                bad_idx = slc_inputs_df[slc_inputs_df["date"].astype(str) == scene_date_dashed].index

                corrupt_indices.append(bad_idx)
                append_dates.remove(scene_date)
                append_scenes.remove(failed_file)

            if corrupt_indices:
                slc_inputs_df.drop(corrupt_indices, inplace=True)
                slc_inputs_df.to_csv(burst_data_csv)

            # Write newly appended scenes .list file
            append_dates_list.write_text("\n".join(append_dates))

        else:
            append_dates = append_dates_list.read_text().splitlines()

        # Load the appended scenes
        slc_frames = get_scenes(burst_data_csv)
        stack_dates = load_stack_scene_dates(proc_config)[:self.append_idx]

        #
        # Produce new coreg tree additions
        #

        if not append_manifest.exists():
            # Load the stack's current coreg tree
            old_coreg_tree = load_coreg_tree(proc_config)

            # Append then new scenes to the stack
            new_coreg_tree = append_secondary_coreg_tree(primary_scene, stack_dates, append_dates)

            # Sanity check (because I'm paranoid we could invalidate existing data)
            # - that the existing part of the tree remains unchanged, and all new
            # - dates are added into lower levels of the tree.
            for i, old_tree_level in enumerate(old_coreg_tree):
                if old_tree_level != new_coreg_tree[i]:
                    raise RuntimeError("Validation failure while appending new scenes to coregistration tree")

            # Save the new tree levels
            first_new_coreg_level = len(old_coreg_tree)
            second_new_coreg_level = len(new_coreg_tree)

            for i in range(first_new_coreg_level, second_new_coreg_level):
                new_tree_level = new_coreg_tree[i]

                scene_file = Path(list_dir / f"secondaries{i+1}.list")
                scene_file.write_text("\n".join([i.strftime(SCENE_DATE_FMT) for i in new_tree_level]))

            # Write a simple description of 'what' the append added to the stack (eg: what is new to the append)
            # - this is succinctly what levels of the coreg tree were appended (this implies what dates are new as well)
            append_manifest.write_text(f"Coregistration tree levels {first_new_coreg_level} to {second_new_coreg_level}")

        else:
            new_coreg_tree = load_coreg_tree(proc_config)

            manifest_text = append_manifest.read_text().split()

            first_new_coreg_level = int(manifest_text[-3])
            second_new_coreg_level = int(manifest_text[-1])

        #
        # Create new SBAS network
        #

        prior_dates = sorted(itertools.chain(*stack_dates))

        # Produce a subset of scenes that includes ALL of the new dates and some
        # of the already-processed dates to produce connections with...
        num_connections = min(len(prior_dates), int(proc_config.num_linked_append_dates))
        network_scenes = prior_dates[-num_connections:] + list(append_dates)

        # Create SBAS network from the scene subset & write to ifg date-pair list
        ifgs_outfile = list_dir / f"ifgs{append_idx}.list"
        slc_par_files = []

        for slc_scene in network_scenes:
            scene_dir = outdir / proc_config.slc_dir / slc_scene

            slc_par = scene_dir / f"{slc_scene}_{primary_pol}.slc.par"
            if not slc_par.exists():
                raise FileNotFoundError(f"missing {slc_par} file")

            slc_par_files.append(slc_par)

        baseline = BaselineProcess(
            slc_par_files,
            [primary_pol],
            primary_scene=primary_scene,
            outdir=outdir,
        )

        # creates a ifg list based on sbas-network
        baseline.sbas_list(
            nmin=int(proc_config.min_connect),
            nmax=int(proc_config.max_connect),
            outfile=ifgs_outfile
        )

        # get range and azimuth looked values
        ml_file = tdir(workdir) / f"{self.stack_id}_createmultilook_status_logs.out"
        rlks, alks = read_rlks_alks(ml_file)

        # Schedule the new scenes for coregistration
        coreg_kwargs = get_coreg_kwargs(self.proc_file)

        # FIXME: de-duplicate w/ coregistration.py
        coreg_tasks = []

        for list_index in range(first_new_coreg_level, second_new_coreg_level):
            list_dates = new_coreg_tree[list_index]
            list_index += 1  # list index is 1-based
            list_frames = [i for i in slc_frames if i[0].date() in list_dates]

            coreg_kwargs["list_idx"] = list_index

            for _dt, _, _pols in list_frames:
                slc_scene = _dt.strftime(SCENE_DATE_FMT)
                if slc_scene == primary_scene:
                    continue

                if primary_pol not in _pols:
                    log.warning(
                        f"Skipping SLC coregistration due to missing primary polarisation data for that date",
                        primary_pol=primary_pol,
                        pols=_pols,
                        slc_scene=slc_scene
                    )
                    continue

                secondary_dir = outdir / proc_config.slc_dir / slc_scene

                # Process coreg for all polarisations, the secondary polarisations will
                # simply apply primary LUTs to secondary products.
                for pol in _pols:
                    secondary_slc_prefix = f"{slc_scene}_{pol}"
                    coreg_kwargs["slc_secondary"] = secondary_dir / f"{secondary_slc_prefix}.slc"
                    coreg_kwargs["secondary_mli"] = secondary_dir / f"{secondary_slc_prefix}_{rlks}rlks.mli"
                    coreg_tasks.append(CoregisterSecondary(**coreg_kwargs))

        yield coreg_tasks

        # Schedule scene backscatter
        # FIXME: de-duplicate w/ backscatter.py
        if self.workflow.value[0] >= ARDWorkflow.Backscatter.value[0]:
            backscatter_tasks = []

            nrb_kwargs = {
                "proc_file": self.proc_file,
                "outdir": outdir,
                "workdir": workdir,

                "ellip_pix_sigma0": coreg_kwargs["ellip_pix_sigma0"],
                "dem_pix_gamma0": coreg_kwargs["dem_pix_gamma0"],
                "dem_lt_fine": coreg_kwargs["dem_lt_fine"],
                "geo_dem_par": coreg_kwargs["geo_dem_par"],
            }

            for secondary_date in append_dates:
                secondary_dir = outdir / proc_config.slc_dir / secondary_date

                for pol in pols:
                    prefix = f"{secondary_date}_{pol.upper()}_{rlks}rlks"

                    nrb_kwargs["outdir"] = secondary_dir
                    nrb_kwargs["src_mli"] = secondary_dir / f"r{prefix}.mli"
                    # TBD: We have always written the backscatter w/ the same
                    # pattern, but going forward we might want coregistered
                    # backscatter to also have the 'r' prefix?  as some
                    # backscatters in the future will 'not' be coregistered...
                    nrb_kwargs["dst_stem"] = secondary_dir / f"{prefix}"

                    task = ProcessBackscatter(**nrb_kwargs)
                    backscatter_tasks.append(task)

            yield backscatter_tasks

        # Schedule scene interferograms
        if self.workflow == ARDWorkflow.Interferogram:
            ifg_tasks = []

            ifgs_list = [i.split(",") for i in ifgs_outfile.read_text().splitlines()]

            for primary_date, secondary_date in ifgs_list:
                ifg_tasks.append(
                    ProcessIFG(
                        proc_file=self.proc_file,
                        shape_file=shape_file,
                        stack_id=self.stack_id,
                        outdir=outdir,
                        workdir=workdir,
                        primary_date=primary_date,
                        secondary_date=secondary_date
                    )
                )

            yield ifg_tasks

        # Mark task as complete
        Path(self.output().path).write_text("")
