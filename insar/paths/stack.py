from pathlib import Path
from typing import List, Union, Tuple
import json

from insar.project import ProcConfig

def find_stack_config(stack_proc_path: Union[str, Path]) -> Path:
    """
    Attempt to find a stack's .proc config file from a supplied stack path.

    :param stack_proc_path:
        A path either directly to a stack's config.proc file that resides in the stack's
        output directory, or alternatively this may be a path to either the stack's
        output or job directories (which will be used to find the stack's .proc file)
    :returns:
        The definitive config.proc Path for the provided stack path, or None if the config.proc
        could not be found from the specified .proc path
    """

    stack_proc_path = Path(stack_proc_path)

    if not stack_proc_path.exists():
        return None

    if stack_proc_path.is_dir():
        # This is kind of a "hack", but still legitimate & slightly faster...
        # We check for a config.proc straight up in case this is the dir we're looking
        # for - this avoids indirection via the metadata.json, but mostly it's to make
        # our SLC unit testing lives easier (w/o having to setup a stack)
        config = stack_proc_path / "config.proc"
        if config.exists():
            return find_stack_config(config)

        metadata = stack_proc_path / "metadata.json"
        if not metadata.exists():
            raise ValueError("Expected stack dir - metadata.json missing from specified directory!")

        with metadata.open("r") as file:
            metadata = json.load(file)

        return Path(metadata["original_work_dir"]) / "config.proc"

    else:
        if stack_proc_path.suffix != ".proc":
            raise ValueError("Expected stack dir or .proc config file!")

        with stack_proc_path.open("r") as proc_file_obj:
            stack_config = ProcConfig.from_file(proc_file_obj)

        if not stack_config.output_path:
            return None

        return stack_config.output_path / "config.proc"


class StackPaths:
    """
    This class produces the path names relevant for a stack.

    This class should correlate to the documentation (`docs/Stack.md`) of what a stack
    is, and it's file structure as specified by the document.

    All code referring to interferogram related paths should directly use this class
    to avoid issues from repeated/duplicate definitions & to ensure they obey the
    specifications that this class is written to conform to.
    """

    output_dir: Path
    """The path to the stack data output directory where all the products live."""

    job_dir: Path
    """The path to the stack job directory where all the logs and workflow files live."""

    proc_config: Path
    """The path to the .proc config file used for producing the stack's products."""

    metadata: Path
    """
    The path to the JSON metadata file that contains high-level information about the
    stack's properties, and high level properties of it's processed products.
    """

    # Stack directories
    acquisition_dir: Path
    """The path to the stack directory which contains the source data acquisition files."""

    list_dir: Path
    """The path to the stack directory which contains the structural list files."""

    slc_dir: Path
    """The path to the stack directory which is the parent of all SLC scenes."""

    int_dir: Path
    """The path to the stack directory which is the parent of all interferograms."""

    dem_dir: Path
    """
    The path to the stack directory which houses the DEM <-> primary scene offset
    models which ultimately coregister the stack to the DEM.
    """

    gamma_dem_dir: Path
    """
    The path to the stack directory which houses the DEM data itself, extracted from
    a master DEM, for just the region of the stack's geospatial extents.
    """

    # Stack structural lists paths

    num_appends: int
    """
    The number of times dates have been added to the stack.

    This includes the very first stack processing, so a new stack starts at `1`.
    """

    scenes_lists: List[Path]
    """
    A list of files with line-separated YYYYMMDD dates for all scenes added to the stack
    at each append.

    The first entry will be the original stack scenes, each subsequent entry correlates
    to each append into the stack.
    """

    coreg_tree_levels: List[Path]
    """
    A list of files with line-separated YYYYMMDD dates for each level of the coregistration
    "tree". Indices to the list correlate to the same tree level, where level 0 is the root.
    """

    append_manifests: List[Path]
    """
    A list of append manifest files for each manifest that has occured.
    """

    ifg_pair_lists: List[Path]
    """
    A list of files with line-separated YYYMMMDD,YYYYMMDD date pairs that
    interferograms are produced for.

    The first entry will be the original stack ifg pairs, each subsequent entry correlates
    to each append into the stack.  Note: it's possible the original stack processing has
    no ifg pairs at all (eg: the original stack only had a single scene), so the length of
    this list wil ltypically be 1+`num_appends` or `num_appends` in the corner case.
    """

    acquisition_csv: Path
    """
    The path to a CSV file with entries for every data acquisition used in the stack's
    scene products and relevant geospatial metadata.
    """

    # Stack log paths

    insar_log: Path
    """A path to the JSONL log used for maintaining a manifest of all GAMMA and related steps that were taken to produce products."""

    status_log: Path
    """A path to the JSONL log used to summarise the status of stack processing down to a per-product level."""

    task_log: Path
    """A path to the JSONL log used for maintaining a manifest of all workflow tasks scheduled and their success/failure."""

    luigi_log: Path
    """A path to the text log used by Luigi to provide status updates on it's scheduling and task status."""

    def __init__(
        self,
        stack_config: ProcConfig
    ):
        """
        Produce the stack paths given a .proc config for a stack.

        This takes a `ProcConfig` as this is always the first step in every part of
        the gamma_insar code, even before a stack exists we need/make a .config file.

        :param stack_config:
            The stack's configuration (or locator path), for which paths are to be for.
        """

        # Sanity check stack config for key variables, sometimes these could be blank
        # in a "template" .config file where users rely on CLI overrides to autofill.
        if not stack_config.stack_id:
            raise ValueError("Provided stack config is incomplete, missing STACK_ID")

        if not stack_config.output_path:
            raise ValueError("Provided stack config is incomplete, missing OUTPUT_PATH")

        if not stack_config.job_path:
            raise ValueError("Provided stack config is incomplete, missing JOB_PATH")

        out_dir = stack_config.output_path

        self.output_dir = out_dir
        self.job_dir = stack_config.job_path

        # Stack dirs are all defined by the stack config
        self.acquisition_dir = out_dir / stack_config.raw_data_dir
        self.list_dir = out_dir / stack_config.list_dir
        self.slc_dir = out_dir / stack_config.slc_dir
        self.int_dir = out_dir / stack_config.int_dir
        self.dem_dir = out_dir / stack_config.dem_dir
        self.gamma_dem_dir = out_dir / stack_config.gamma_dem_dir

        # config and metadata are specified a fixed filenames in docs/Stack.md
        self.proc_config = self.output_dir / "config.proc"
        self.metadata = self.output_dir / "metadata.json"
        self.acquisition_csv = self.output_dir / f"{stack_config.stack_id}_burst_data.csv"

        # log files are specified as fixed filenames in docs/Stack.md
        self.insar_log = self.job_dir / "insar-log.jsonl"
        self.status_log = self.job_dir / "status-log.jsonl"
        self.task_log = self.job_dir / "task-log.jsonl"
        self.luigi_log = self.job_dir / "luigi-interface.log"

        # Non-existant stack starts as a negative append index, so pre-append workflow can
        # also simply .append() paths
        self.num_appends = -1
        self.scenes_lists = []
        self.coreg_tree_levels = []
        self.append_manifests = []
        self.ifg_pair_lists = []

        # Attempt to load existing stack
        if self.list_dir.exists():
            self.append_manifests = sorted(self.list_dir.glob("append*.manifest"))
            self.coreg_tree_levels = sorted(self.list_dir.glob("secondaries*.list"))

            first_scenes_list = self.list_dir / "scenes.list"
            if not first_scenes_list.exists():
                return

            self.scenes_lists = [first_scenes_list]

            first_ifgs_list = self.list_dir / "ifgs.list"
            if first_ifgs_list.exists():
                self.ifg_pair_lists = [first_ifgs_list]

            # Note: sorting f"blah{N}" strings doesn't sort numerically which we need
            # so we ignore the glob, and generate our own numerical list (easiest approach)
            self.num_appends = len(self.append_manifests)
            self.scenes_lists += [self.list_dir / f"scenes{i}.list" for i in range(1, self.num_appends+1)]
            self.ifg_pair_lists += [self.list_dir / f"ifgs{i}.list" for i in range(1, self.num_appends+1)]

            coreg_tree_depth = len(self.coreg_tree_levels)
            self.coreg_tree_levels = [self.list_dir / f"secondaries{i}.list" for i in range(1, coreg_tree_depth+1)]

            # Sanity check...
            if any(not p.exists() for p in self.scenes_lists):
                raise RuntimeError("Unexpected error loading stack, missing one or more scenes .list files")

            if any(not p.exists() for p in self.ifg_pair_lists):
                raise RuntimeError("Unexpected error loading stack, missing one or more ifgs .list files")

            if any(not p.exists() for p in self.coreg_tree_levels):
                raise RuntimeError("Unexpected error loading stack, missing one or more secondaries .list files")


    # TODO: This isn't finished / used yet... but kept in PR and added as a TODO so I don't forget
    # - mostly for stack_setup.py / resume.py / append.py workflow modules which modify these
    #
    # - this will likely need splitting into two (one for append levels, one for adding tree levels)
    def append(self, index: int, tree_levels: Tuple[int, int]):
        """
        Appends a new paths that represent a new stack append index and coregistration tree levels.

        :param index:
            The data append index (0 for the first data in a new stack).
        :param tree_levels:
            The (first level, last level) tuple that describes the coregistration tree levels
            that were added as part of this append.

            Levels are inclusive, and start from 1 for the root of the tree (not 0).
        """

        self.num_appends += 1

        # Sanity check...
        if len(self.scenes_lists) != self.num_appends:
            raise RuntimeError("Provided append index does not match the next stack append index!")

        if min(tree_levels) < len(self.coreg_tree_levels):
            raise RuntimeError("Provided tree levels already exist in the stack!")

        # If this is the first data added to the stack, we have different filenames
        if self.num_appends == 0:
            # As per docks/Stack.md - the first scenes list has no index, it's just `scenes.list`
            self.scenes_lists = [self.list_dir / "scenes.list"]
            self.ifg_pair_lists = [self.list_dir / "ifgs.list"]

        # Otherwise 1 based indices for all appends.
        else:
            self.scenes_lists.append(self.list_dir / f"scenes{self.num_appends}.list")
            self.ifg_pair_lists.append(self.list_dir / f"ifgs{self.num_appends}.list")

        new_levels = range(tree_levels[0], tree_levels[1]+1)
        self.coreg_tree_levels += [self.list_dir / f"secondaries{i}" for i in new_levels]
