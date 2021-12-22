from typing import Union
from pathlib import Path

from insar.project import ProcConfig
from insar.stack import load_stack_config

from insar.paths.slc import SlcPaths

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

    r_dem_primary_mli: Path

    r_dem_primary_slc_par: Path
    r_dem_primary_mli_par: Path

    r_secondary_slc: Path
    r_secondary_slc_par: Path
    r_secondary_slc_tab: Path
    r_secondary_mli: Path
    r_secondary_mli_par: Path

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
        self.dem_filenames = CoregisterDem.dem_filenames(
            dem_prefix=primary_slc_rlks_prefix,
            outdir=dem_dir
        )

        self.primary_dem = CoregisterDem.dem_primary_names(
            slc_prefix=primary_slc_rlks_prefix,
            r_slc_prefix=f"r{primary_slc_prefix}",
            outdir=self.primary.dir,
        )

        # FIXME: self.primary_dem = CoregisteredDemPaths(...)?
        self.r_dem_primary_mli = self.primary_dem["r_dem_primary_mli"]
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
