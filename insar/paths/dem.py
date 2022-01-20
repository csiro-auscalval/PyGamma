from os import path
from typing import Union
from pathlib import Path

from insar.project import ProcConfig
from insar.stack import load_stack_config

class DEMPaths:
    """
    This class produces pathnames for files relevant to the DEM and it's coregistration
    to the stack's primary/reference scene.

    All code should use this class when referring to pathnames relating to DEM related
    data to avoid duplicating/repeating pathnames to avoid refactoring/renaming
    related errors.
    """

    # Note for PR: Most of these are also intentionally undocumented for now,
    # for reasons similar to the coreg paths - but also:
    #    During a future OOP->functional refactor I'm confident some of these
    #    will turn out to be private/internal paths that don't need to be exposed

    dem: Path
    """
    The path to the extracted region of interest from the master DEM that covers the
    stack extent, converted into GAMMA format for use by the processing workflow.
    """

    dem_par: Path
    """The accompanying GAMMA .par file for `self.dem`"""

    dem_primary_name: Path
    """The common path prefix shared by most DEM pathnames"""

    dem_diff: Path
    """
    The GAMMA .par file for the `DIFF` model.

    In non-GAMMA terms, this holds the offset model used by coregistration.
    """

    rdc_dem: Path
    """The file path for the DEM data in RDC (radar coordinates)."""

    geo_dem: Path
    """The file path for the DEM data in geographic coords."""

    geo_dem_par: Path
    """The accompanying GAMMA .par file for `self.geo_dem`"""

    seamask: Path
    """The path to a GAMMA file that holds the sea mask"""

    dem_lt_rough: Path
    """
    The path to a rough estimate of the geocoding LUT produced midway through the
    coregistration workflow.

    This "is" one crude output of coregistration / can be used to coregister data.
    """

    dem_lt_fine: Path
    """
    The path to the refined geocoding LUT produced at the end of the coregistration
    workflow.

    This is considered the main output of the coregistration, and is used to resample
    all our SLC data with the stack's primary scene / "to coregister the products".
    """

    # Note for future cleanup / next PR: the _sim_sar and _inc files are private / can be dropped
    dem_geo_sim_sar: Path
    dem_rdc_sim_sar: Path
    dem_loc_inc: Path
    dem_rdc_inc: Path

    dem_lsmap: Path
    """
    The layover/shadow mask of the primary scene according to the DEM.

    This is basically a quality mask showing what pixels in the scene are impacted by
    artifacts from that point in the image not being visible for the whole duration of
    the scan (layover and shadowing).
    """

    dem_lsmap_tif: Path
    """The path to the .tif conversion of `self.dem_lsmap`"""

    dem_lsmap_mask_tif: Path
    """
    A CARD4L compliant version of `self.dem_lsmap` in .tif format which can be used as
    a simpler bit mask (0 = bad quality pixels or no data, 1 = good quality data).
    """

    ellip_pix_sigma0: Path
    dem_pix_gam: Path
    dem_pix_gam_bmp: Path
    dem_off: Path
    dem_offs: Path
    dem_ccp: Path
    dem_offsets: Path
    dem_coffs: Path
    dem_coffsets: Path

    # TODO: I'll have to chase up someone in the InSAR team to document these next year
    # - I'm not too familiar w/ what the look vectors are technically...
    #
    # I'm 90% sure they're the vector from surface toward the satellite? but unsure.
    # - and this is probably in spherical coords? so _theta and _phi are those 2 coordinates
    # - that combined produce a vector, likely relative to some common normal vector?
    dem_lv_theta: Path
    dem_lv_phi: Path

    def __init__(self, proc: Union[ProcConfig, Path]):
        """
        Produces all of the DEM and DEM-related (coregistration w/ primary/reference scene)
        product file/directory paths - in the context of a specific stack.

        :param proc:
            The stack's configuration (or locator path), for which paths are to be for.
        """

        if isinstance(proc, Path):
            proc = load_stack_config(proc)

        self.dem = (proc.output_path / proc.gamma_dem_dir / proc.stack_id).with_suffix(".dem")
        self.dem_par = self.dem.with_suffix(".dem.par")
        self.dem_primary_name = "{}_{}_{}rlks".format(
            proc.ref_primary_scene, proc.polarisation, proc.range_looks
        )
        self.dem_primary_name = proc.output_path / proc.dem_dir / self.dem_primary_name
        dmn = self.dem_primary_name

        self.dem_diff = dmn.parent / ("diff_" + dmn.name + ".par")

        self.rdc_dem = dmn.parent / (dmn.name + "_rdc.dem")
        self.geo_dem = dmn.parent / (dmn.name + "_geo.dem")
        self.geo_dem_par = self.geo_dem.with_suffix(".dem.par")
        self.seamask = dmn.parent / (dmn.name + "_geo_seamask.tif")
        self.dem_lt_rough = dmn.parent / (dmn.name + "_rough_geo_to_rdc.lt")
        self.dem_lt_fine = dmn.parent / (dmn.name + "_geo_to_rdc.lt")
        self.dem_geo_sim_sar = dmn.parent / (dmn.name + "_geo.sim")
        self.dem_rdc_sim_sar = dmn.parent / (dmn.name + "_rdc.sim")
        self.dem_loc_inc = dmn.parent / (dmn.name + "_geo.linc")
        self.dem_rdc_inc = dmn.parent / (dmn.name + "_rdc.linc")
        self.dem_lsmap = dmn.parent / (dmn.name + "_geo.lsmap")
        self.dem_lsmap_tif = dmn.parent / (dmn.name + "_geo_lsmap.tif")
        self.dem_lsmap_mask_tif = dmn.parent / (dmn.name + "_geo_lsmap_mask.tif")
        self.ellip_pix_sigma0 = dmn.parent / (dmn.name + "_ellip_pix_sigma0")
        self.dem_pix_gam = dmn.parent / (dmn.name + "_rdc_pix_gamma0")
        self.dem_pix_gam_bmp = self.dem_pix_gam.with_suffix(".bmp")
        self.dem_off = dmn.with_suffix(".off")
        self.dem_offs = dmn.with_suffix(".offs")
        self.dem_ccp = dmn.with_suffix(".ccp")
        self.dem_offsets = dmn.with_suffix(".offsets")
        self.dem_coffs = dmn.with_suffix(".coffs")
        self.dem_coffsets = dmn.with_suffix(".coffsets")
        self.dem_lv_theta = dmn.parent / (dmn.name + "_geo.lv_theta")
        self.dem_lv_phi = dmn.parent / (dmn.name + "_geo.lv_phi")
