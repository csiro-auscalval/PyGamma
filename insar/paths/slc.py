from typing import Optional, List, Union
from pathlib import Path
import datetime

from insar.constant import SCENE_DATE_FMT
from insar.project import ProcConfig
from insar.stack import load_stack_config

class SlcPaths:
    """
    Contains the path names of key SLC data and related files.

    All code should use this class when referring to pathnames relating to SLC data to
    avoid duplicating/repeating pathnames to avoid refactoring/renaming related errors.
    """

    dir: Path
    """The directory which contains all of the SLC products provided by this class or otherwise"""

    slc: Path
    """
    The path to the scene's SLC product itself, which is basically the mosaic of
    all the subswath SLCs (`iw_slc`) combined."""

    slc_par: Path
    """The GAMMA par file for the scene's mosaiced SLC product."""

    slc_tops_par: Path
    """The GAMMA TOPS_par file for the scene's mosaiced SLC product."""

    slc_tab: Path
    """
    A GAMMA TAB file that represents this `SlcPaths` structure, essentially referring to
    `{self.slc} {self.slc_par} {self.slc_tops_par}`.
    """

    iw_slc: List[Path]
    """A list of paths for the scene's SLC products for each subswath."""

    iw_slc_par: List[Path]
    """A list of GAMMA par files for each `self.iw_slc`."""

    iw_slc_tops_par: List[Path]
    """A list of GAMMA TOPS_par files for each `self.iw_slc`."""

    mli: Optional[Path]
    """
    The path to the scene's multi-looked SLC product.

    This is the key output of the SLC processing workflow step.

    Note: This may be None if no range looks had been provided to the constructor.
    """

    mli_par: Optional[Path]
    """
    The path to the GAMMA par file for `self.mli`.

    Note: This may be None if no range looks had been provided to the constructor.
    """

    def __init__(
        self,
        stack_config: Union[ProcConfig, Path],
        date: Union[str, datetime.datetime, datetime.date],
        pol: str,
        rlks: Optional[int] = None
    ):
        """
        Produces the SLC paths for a specified scene within a specified stack.

        :param stack_config:
            The stack's configuration (or locator path), for which paths are to be for.
        :param date:
            The date being specified for the scene to produce paths for.
        :param pol:
            The polarisation being specified for the scene to produce paths for.
        :param rlks:
            The range looks computed for this stack, if it has been computed yet.

            If this is not provided / has not been computed, the `mli` and `mli_par`
            fields simply will be set to `None`.
        """

        if not isinstance(stack_config, ProcConfig):
            stack_config = load_stack_config(stack_config)

        if isinstance(date, str):
            # Parse as a date to sanity check
            date = datetime.datetime.strptime(date, SCENE_DATE_FMT)
            # Back to str if it passes...
            date = date.strftime(SCENE_DATE_FMT)
        elif isinstance(date, datetime.datetime):
            date = date.strftime(SCENE_DATE_FMT)
        elif isinstance(date, datetime.date):
            date = date.strftime(SCENE_DATE_FMT)

        # TODO: Should be based on some kind of 'stack' paths?
        slc_dir = Path(stack_config.output_path) / stack_config.slc_dir / date
        self.dir = slc_dir

        self.slc = slc_dir / f"{date}_{pol}.slc"
        self.slc_par = slc_dir / f"{date}_{pol}.slc.par"
        self.slc_tops_par = slc_dir / f"{date}_{pol}.slc.TOPS_par"
        self.slc_tab = slc_dir / f"{date}_{pol}_tab"

        swaths = [1, 2, 3]
        self.iw_slc = [slc_dir / f"{date}_{pol}_IW{i}.slc" for i in swaths]
        self.iw_slc_par = [slc_dir / f"{date}_{pol}_IW{i}.slc.par" for i in swaths]
        self.iw_slc_tops_par = [slc_dir / f"{date}_{pol}_IW{i}.slc.TOPS_par" for i in swaths]

        if rlks is not None:
            self.mli = slc_dir / f"{date}_{pol}_{rlks}rlks.mli"
            self.mli_par = slc_dir / f"{date}_{pol}_{rlks}rlks.mli.par"
