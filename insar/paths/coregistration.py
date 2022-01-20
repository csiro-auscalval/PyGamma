from typing import Union
from pathlib import Path

from insar.project import ProcConfig
from insar.stack import load_stack_config

from insar.paths.slc import SlcPaths

class CoregisteredPrimaryPaths:
    """
    This class produces pathnames for files relevant to the coregistration of the
    primary stack scene to the stack's DEM.

    This is similar yet distinct from `CoregisteredSlcPaths` as the primary scene has
    no other scene SLC it can coregister to (hence it's considered the primary or
    "reference" scene that secondary scenes coregister to) - instead the primary scene
    is coregistered to the DEM instead.

    All code should use this class when referring to pathnames relating to coregistered
    SLC data relating to the primary scene  to avoid duplicating/repeating pathnames to
    avoid refactoring/renaming related errors.
    """

    dem_primary_slc_name: Path
    """A common path prefix shared by most path names in this class"""

    dem_primary_slc: Path
    """The primary scene's SLC data file path before coregistration"""

    dem_primary_slc_par: Path
    """The accompanying GAMMA .par file for `self.dem_primary_slc`"""

    dem_primary_mli: Path
    """The primary scene's multi-looked SLC data file path before coregistration."""

    dem_primary_mli_par: Path
    """The accompanying GAMMA .par file for `self.dem_primary_mli`"""

    r_dem_primary_slc: Path
    """The primary scene's coregistered SLC data file path."""

    r_dem_primary_slc_par: Path
    """The accompanying GAMMA .par file for `self.r_dem_primary_slc`"""

    r_dem_primary_mli: Path
    """The primary scene's multi-looked coregistered SLC data file path."""

    r_dem_primary_mli_par: Path
    """The accompanying GAMMA .par file for `self.r_dem_primary_mli`"""

    def __init__(self, proc: ProcConfig):
        out_dir = proc.output_path

        dem_primary_dir = out_dir / proc.slc_dir / proc.ref_primary_scene

        suffix = proc.ref_primary_scene + "_" + proc.polarisation
        self.dem_primary_slc_name = dem_primary_dir / suffix

        self.dem_primary_slc = dem_primary_dir / (suffix + ".slc")
        self.dem_primary_slc_par = dem_primary_dir / (suffix + ".slc.par")

        suffix_lks = f"{proc.ref_primary_scene}_{proc.polarisation}_{proc.range_looks}rlks"
        dem_primary_mli_name = dem_primary_dir / suffix_lks
        self.dem_primary_mli = dem_primary_mli_name.with_suffix(".mli")
        self.dem_primary_mli_par = dem_primary_mli_name.with_suffix(".mli.par")

        suffix_slc = f"r{proc.ref_primary_scene}_{proc.polarisation}"
        r_dem_primary_slc_name = dem_primary_dir / suffix_slc
        self.r_dem_primary_slc = r_dem_primary_slc_name.with_suffix(".slc")
        self.r_dem_primary_slc_par = r_dem_primary_slc_name.with_suffix(".slc.par")

        suffix_mli = "r{}_{}_{}rlks".format(
            proc.ref_primary_scene, proc.polarisation, proc.range_looks
        )
        r_dem_primary_mli_name = dem_primary_dir / suffix_mli
        self.r_dem_primary_mli = r_dem_primary_mli_name.with_suffix(".mli")
        self.r_dem_primary_mli_par = r_dem_primary_mli_name.with_suffix(".mli.par")


class CoregisteredSlcPaths:
    """
    This class produces pathnames for files relevant to coregistering SLC products.

    All code should use this class when referring to pathnames relating to coregistered
    SLC data to avoid duplicating/repeating pathnames to avoid refactoring/renaming
    related errors.
    """

    slc_primary: SlcPaths
    slc_secondary: SlcPaths

    # Note for PR: These fields are intentionally not commented yet...
    # the plan is to: once the code refactoring is complete, finish the file structure
    # documentation for the stack for each product, and then correlate those to fields
    # in this class directly - and simultaniously document these fields correlating
    # them back to the stack definition/documentation as well.
    secondary_mli: Path

    # Also as above, some fields are duplicates / need to be cleaned up as part of
    # another refactor (probably during the upcoming OOP->functional refactor where
    # most of the related code will be getting touched)
    r_dem_primary_mli: Path

    r_dem_primary_slc_par: Path
    r_dem_primary_mli_par: Path

    r_secondary_slc: Path
    """The secondary scene's coregistered SLC data file path"""

    r_secondary_slc_par: Path
    """The accompanying GAMMA .par file for `self.r_secondary_slc`"""

    r_secondary_slc_tab: Path
    """The accompanying GAMMA TAB file for `self.r_secondary_slc`"""

    r_secondary_mli: Path
    """The secondary scene's multi-looked coregistered SLC data file path"""

    r_secondary_mli_par: Path
    """The accompanying GAMMA .par file for `self.r_secondary_mli_par`"""

    primary_slc_tab: Path
    secondary_slc_tab: Path

    def __init__(
        self,
        stack_config: Union[ProcConfig, Path],
        primary_date: str,
        secondary_date: str,
        polarisation: str,
        rlks: int
    ):
        """
        Produces coregistered SLC paths for a specified date pair and polarisation, in the
        context of a specific stack.

        :param stack_config:
            The stack's configuration (or locator path), for which paths are to be for.
        :param primary_date:
            The primary date being coregistered to.
        :param secondary_date:
            The secondary date that most of the paths in this class refer to.
        :param polarisation:
            The polarisation for the path's products.
        :param rlks:
            The range looks computed for this stack.
        """

        if not isinstance(stack_config, ProcConfig):
            stack_config = load_stack_config(stack_config)

        # Copy params
        self.primary_date = primary_date
        self.secondary_date = secondary_date
        self.polarisation = polarisation
        self.rlks = rlks

        # Get primary/secondary scene paths
        #
        # Note: When referring to primary scene in a coreg context, we also always refer
        # to primary polarisation!  This is because coregistration is always done w/
        # primary polarisation data - and secondary polarisations are re-sampled w/ the
        # exact same models.
        self.primary = SlcPaths(stack_config, primary_date, stack_config.polarisation, rlks)
        self.secondary = SlcPaths(stack_config, secondary_date, polarisation, rlks)

        # Also get the DEM coregistered primary scene paths
        # FIXME: Should be part of this file... not a random static function in CoregisterDem?
        from insar.coregister_dem import CoregisterDem
        primary_slc_prefix = f"{primary_date}_{stack_config.polarisation}"
        primary_slc_rlks_prefix = f"{primary_slc_prefix}_{rlks}rlks"

        dem_dir = Path(stack_config.output_path) / stack_config.dem_dir

        self.primary_dem = CoregisteredPrimaryPaths(stack_config)
        #self.primary_dem = CoregisterDem.dem_primary_names(
        #    slc_prefix=primary_slc_rlks_prefix,
        #    r_slc_prefix=f"r{primary_slc_prefix}",
        #    outdir=self.primary.dir,
        #)

        # FIXME: self.primary_dem = CoregisteredDemPaths(...)?
        self.r_dem_primary_mli = self.primary_dem.r_dem_primary_mli
        self.r_dem_primary_mli_par = self.r_dem_primary_mli.with_suffix(".mli.par")
        # FIXME: self.primary_dem.r_dem_slc_par?
        self.r_dem_primary_slc_par = self.primary.slc_par
        self.r_dem_primary_slc_par = self.r_dem_primary_slc_par.parent / ("r" + self.r_dem_primary_slc_par.name)

        # Finally produce our coregistered secondary paths (eg: resampled products & offset models)
        out_dir = self.secondary.dir

        self.r_secondary_mli = out_dir / f"r{self.secondary.mli.name}"
        self.r_secondary_mli_par = self.r_secondary_mli.with_suffix(".mli.par")

        self.r_secondary_slc_tab = out_dir / f"r{self.secondary.slc.stem}_tab"
        self.r_secondary_slc = out_dir / f"r{self.secondary.slc.name}"
        self.r_secondary_slc_par = out_dir / f"r{self.secondary.slc.name}.par"

        primary_secondary_prefix = f"{primary_date}-{secondary_date}"
        self.r_primary_secondary_name = f"{primary_secondary_prefix}_{polarisation}_{rlks}rlks"

        self.secondary_lt = out_dir / f"{self.r_primary_secondary_name}.lt"
        self.secondary_off = out_dir / f"{self.r_primary_secondary_name}.off"

        # TODO: Should these really be first class citizens? they're temporary files more than anything, and more relevant to SlcPaths
        self.primary_slc_tab = out_dir / f"{self.primary.slc.stem}_tab"
        self.secondary_slc_tab = out_dir / f"{self.secondary.slc.stem}_tab"
