from pathlib import Path

from insar.project import ProcConfig

class InterferogramPaths:
    """
    This class produces pathnames for files relevant to interferogram products.

    All code referring to interferogram related paths should directly use this class
    to avoid issues from repeated/duplicate definitions.
    """

    # These aren't even typed yet... this was too big a change for this PR
    # - for now, this class remains practically unchanged from it's existence
    # in project.py.
    #
    # I'll hack to tackle all of these when I wrap up all the documentation work.
    __slots__ = [
        "ifg_dir",
        "primary_dir",
        "secondary_dir",
        "r_primary_slc_name",
        "r_primary_slc",
        "r_primary_slc_par",
        "r_primary_mli_name",
        "r_primary_mli",
        "r_primary_mli_par",
        "r_secondary_slc_name",
        "r_secondary_slc",
        "r_secondary_slc_par",
        "r_secondary_mli_name",
        "r_secondary_mli",
        "r_secondary_mli_par",
        "primary_secondary_name",
        "ifg_base",
        "ifg_base_init",
        "ifg_base_res",
        "ifg_base_temp",
        "ifg_bperp",
        "ifg_ccp",
        "ifg_coffs",
        "ifg_coffsets",
        "ifg_diff_par",
        "ifg_filt",
        "ifg_filt_float",
        "ifg_filt_geocode_bmp",
        "ifg_filt_geocode_out",
        "ifg_filt_geocode_png",
        "ifg_filt_mask",
        "ifg_filt_coh",
        "ifg_filt_coh_geocode_bmp",
        "ifg_filt_coh_geocode_out",
        "ifg_filt_coh_geocode_png",
        "ifg_flat",
        "ifg_flat_float",
        "ifg_flat_geocode_bmp",
        "ifg_flat_geocode_out",
        "ifg_flat_geocode_png",
        "ifg_flat_temp",
        "ifg_flat0",
        "ifg_flat1",
        "ifg_flat10",
        "ifg_flat_coh",
        "ifg_flat_coh_geocode_bmp",
        "ifg_flat_coh_geocode_out",
        "ifg_flat_coh_geocode_png",
        "ifg_flat_coh0",
        "ifg_flat_coh0_mask",
        "ifg_flat_coh10",
        "ifg_flat_coh10_mask",
        "ifg_gcp",
        "ifg_gcp_ph",
        "ifg_mask",
        "ifg_mask_thin",
        "ifg_off",
        "ifg_off10",
        "ifg_offs",
        "ifg_sim_diff",
        "ifg_sim_unw",
        "ifg_sim_unw0",
        "ifg_sim_unw1",
        "ifg_sim_unw_ph",
        "ifg_unw",
        "ifg_unw_geocode_2pi_bmp",
        "ifg_unw_geocode_6pi_bmp",
        "ifg_unw_geocode_out",
        "ifg_unw_geocode_2pi_png",
        "ifg_unw_geocode_6pi_png",
        "ifg_unw_mask",
        "ifg_unw_model",
        "ifg_unw_thin",
        # vars for GeoTIFF outputs
        "ifg_unw_geocode_out_tiff",
        "ifg_flat_geocode_out_tiff",
        "ifg_filt_geocode_out_tiff",
        "ifg_flat_coh_geocode_out_tiff",
        "ifg_filt_coh_geocode_out_tiff",
    ]

    def __init__(
        self,
        proc: ProcConfig,
        primary: str,
        secondary: str
    ):
        """
        Produces interferogram paths for a specified date pair in the context of a
        specific stack.

        :param proc:
            The stack's configuration (or locator path), for which paths are to be for.
        :param primary:
            The primary date of the interferogram.
        :param secondary:
            The secondary date of the interferogram.
        """

        out_dir = proc.output_path

        self.ifg_dir = out_dir / proc.int_dir / "{}-{}".format(primary, secondary)
        self.primary_dir = out_dir / proc.slc_dir / primary
        self.secondary_dir = out_dir / proc.slc_dir / secondary

        self.r_primary_slc_name = self.primary_dir / "r{}_{}".format(
            primary, proc.polarisation
        )

        self.r_primary_slc = self.r_primary_slc_name.with_suffix(".slc")
        self.r_primary_slc_par = self.r_primary_slc_name.with_suffix(".slc.par")

        self.r_primary_mli_name = self.primary_dir / "r{}_{}_{}rlks".format(
            primary, proc.polarisation, proc.range_looks
        )
        self.r_primary_mli = self.r_primary_mli_name.with_suffix(".mli")
        self.r_primary_mli_par = self.r_primary_mli.with_suffix(".mli.par")

        self.r_secondary_slc_name = self.secondary_dir / "r{}_{}".format(secondary, proc.polarisation)

        self.r_secondary_slc = self.r_secondary_slc_name.with_suffix(".slc")
        self.r_secondary_slc_par = self.r_secondary_slc.with_suffix(".slc.par")
        self.r_secondary_mli_name = self.secondary_dir / "r{}_{}_{}rlks".format(
            secondary, proc.polarisation, proc.range_looks
        )
        self.r_secondary_mli = self.r_secondary_mli_name.with_suffix(".mli")
        self.r_secondary_mli_par = self.r_secondary_mli.with_suffix(".mli.par")

        # use intermed str as Path doesn't handle filename concatenation
        _primary_secondary_name = "{}-{}_{}_{}rlks".format(
            primary, secondary, proc.polarisation, proc.range_looks
        )
        self.primary_secondary_name = self.ifg_dir / _primary_secondary_name

        self.ifg_base = self.ifg_dir / (_primary_secondary_name + "_base.par")
        self.ifg_base_init = Path(_primary_secondary_name + "_base_init.par")
        self.ifg_base_res = Path(_primary_secondary_name + "_base_res.par")
        self.ifg_base_temp = Path(_primary_secondary_name + "_base_temp.par")
        self.ifg_bperp = Path(_primary_secondary_name + "_bperp.par")

        self.ifg_ccp = Path(_primary_secondary_name + ".ccp")
        self.ifg_coffs = Path(_primary_secondary_name + ".coffs")
        self.ifg_coffsets = Path(_primary_secondary_name + ".coffsets")
        self.ifg_diff_par = Path(_primary_secondary_name + "_diff.par")

        self.ifg_filt = Path(_primary_secondary_name + "_filt_int")
        self.ifg_filt_float = Path(_primary_secondary_name + "_filt_int_flt")
        self.ifg_filt_geocode_bmp = Path(_primary_secondary_name + "_filt_geo_int.bmp")
        self.ifg_filt_geocode_out = Path(_primary_secondary_name + "_filt_geo_int")
        self.ifg_filt_geocode_png = Path(_primary_secondary_name + "_filt_geo_int.png")
        self.ifg_filt_mask = Path(_primary_secondary_name + "_filt_mask_int")
        self.ifg_filt_coh = Path(_primary_secondary_name + "_filt_coh")
        self.ifg_filt_coh_geocode_bmp = Path(
            _primary_secondary_name + "_filt_geo_coh.bmp"
        )
        self.ifg_filt_coh_geocode_out = Path(_primary_secondary_name + "_filt_geo_coh")
        self.ifg_filt_coh_geocode_png = Path(
            _primary_secondary_name + "_filt_geo_coh.png"
        )

        self.ifg_flat = Path(_primary_secondary_name + "_flat_int")
        self.ifg_flat_float = Path(_primary_secondary_name + "_flat_int_flt")
        self.ifg_flat_geocode_bmp = Path(_primary_secondary_name + "_flat_geo_int.bmp")
        self.ifg_flat_geocode_out = Path(_primary_secondary_name + "_flat_geo_int")
        self.ifg_flat_geocode_png = Path(_primary_secondary_name + "_flat_geo_int.png")
        self.ifg_flat_temp = Path(_primary_secondary_name + "_flat_temp_int")
        self.ifg_flat0 = Path(_primary_secondary_name + "_flat0_int")
        self.ifg_flat1 = Path(_primary_secondary_name + "_flat1_int")
        self.ifg_flat10 = Path(_primary_secondary_name + "_flat10_int")
        self.ifg_flat_coh = Path(_primary_secondary_name + "_flat_coh")
        self.ifg_flat_coh_geocode_bmp = Path(
            _primary_secondary_name + "_flat_geo_coh.bmp"
        )
        self.ifg_flat_coh_geocode_out = Path(_primary_secondary_name + "_flat_geo_coh")
        self.ifg_flat_coh_geocode_png = Path(
            _primary_secondary_name + "_flat_geo_coh.png"
        )
        self.ifg_flat_coh0 = Path(_primary_secondary_name + "_flat0_coh")
        self.ifg_flat_coh0_mask = Path(_primary_secondary_name + "_flat0_coh_mask.ras")
        self.ifg_flat_coh10 = Path(_primary_secondary_name + "_flat10_coh")
        self.ifg_flat_coh10_mask = Path(_primary_secondary_name + "_flat10_coh_mask.ras")

        self.ifg_gcp = Path(_primary_secondary_name + ".gcp")
        self.ifg_gcp_ph = Path(_primary_secondary_name + ".gcp_ph")
        self.ifg_mask = Path(_primary_secondary_name + "_mask.ras")
        self.ifg_mask_thin = Path(_primary_secondary_name + "_mask_thin.ras")
        self.ifg_off = Path(_primary_secondary_name + "_off.par")
        self.ifg_off10 = Path(_primary_secondary_name + "_off10.par")
        self.ifg_offs = Path(_primary_secondary_name + ".offs")

        self.ifg_sim_diff = Path(_primary_secondary_name + "_sim_diff_unw")
        self.ifg_sim_unw = Path(_primary_secondary_name + "_sim_unw")
        self.ifg_sim_unw0 = Path(_primary_secondary_name + "_sim0_unw")
        self.ifg_sim_unw1 = Path(_primary_secondary_name + "_sim1_unw")
        self.ifg_sim_unw_ph = Path(_primary_secondary_name + "_sim_ph_unw")
        self.ifg_unw = Path(_primary_secondary_name + "_unw")
        self.ifg_unw_geocode_2pi_bmp = Path(_primary_secondary_name + "_geo_unw_2pi.bmp")
        self.ifg_unw_geocode_6pi_bmp = Path(_primary_secondary_name + "_geo_unw_6pi.bmp")
        self.ifg_unw_geocode_out = Path(_primary_secondary_name + "_geo_unw")
        self.ifg_unw_geocode_2pi_png = Path(_primary_secondary_name + "_geo_unw_2pi.png")
        self.ifg_unw_geocode_6pi_png = Path(_primary_secondary_name + "_geo_unw_6pi.png")
        self.ifg_unw_mask = Path(_primary_secondary_name + "_mask_unw")
        self.ifg_unw_model = Path(_primary_secondary_name + "_model_unw")
        self.ifg_unw_thin = Path(_primary_secondary_name + "_thin_unw")

        self.ifg_unw_geocode_out_tiff = Path(_primary_secondary_name + "_geo_unw.tif")
        self.ifg_flat_geocode_out_tiff = Path(
            _primary_secondary_name + "_flat_geo_int.tif"
        )
        self.ifg_filt_geocode_out_tiff = Path(
            _primary_secondary_name + "_filt_geo_int.tif"
        )
        self.ifg_flat_coh_geocode_out_tiff = Path(
            _primary_secondary_name + "_flat_geo_coh.tif"
        )
        self.ifg_filt_coh_geocode_out_tiff = Path(
            _primary_secondary_name + "_filt_geo_coh.tif"
        )
