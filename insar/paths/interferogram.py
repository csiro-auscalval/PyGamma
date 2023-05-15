from pathlib import Path

from insar.project import ProcConfig


class InterferogramPaths:
    """
    This class produces pathnames for files relevant to interferogram products.

    All code referring to interferogram related paths should directly use this class
    to avoid issues from repeated/duplicate definitions.
    """

    ifg_dir: Path = Path()
    primary_dir: Path = Path()
    secondary_dir: Path = Path()
    r_primary_slc_name: Path = Path()
    r_primary_slc: Path = Path()
    r_primary_slc_par: Path = Path()
    r_primary_mli_name: Path = Path()
    r_primary_mli: Path = Path()
    r_primary_mli_par: Path = Path()
    r_secondary_slc_name: Path = Path()
    r_secondary_slc: Path = Path()
    r_secondary_slc_par: Path = Path()
    r_secondary_mli_name: Path = Path()
    r_secondary_mli: Path = Path()
    r_secondary_mli_par: Path = Path()
    primary_secondary_name: Path = Path()
    ifg_base: Path = Path()
    ifg_base_init: Path = Path()
    ifg_base_res: Path = Path()
    ifg_base_temp: Path = Path()
    ifg_bperp: Path = Path()
    ifg_ccp: Path = Path()
    ifg_coffs: Path = Path()
    ifg_coffsets: Path = Path()
    ifg_diff_par: Path = Path()
    ifg_filt: Path = Path()
    ifg_filt_float: Path = Path()
    ifg_filt_geocode_bmp: Path = Path()
    ifg_filt_geocode_out: Path = Path()
    ifg_filt_geocode_png: Path = Path()
    ifg_filt_mask: Path = Path()
    ifg_filt_coh: Path = Path()
    ifg_filt_coh_geocode_bmp: Path = Path()
    ifg_filt_coh_geocode_out: Path = Path()
    ifg_filt_coh_geocode_png: Path = Path()
    ifg_flat: Path = Path()
    ifg_flat_float: Path = Path()
    ifg_flat_geocode_bmp: Path = Path()
    ifg_flat_geocode_out: Path = Path()
    ifg_flat_geocode_png: Path = Path()
    ifg_flat_temp: Path = Path()
    ifg_flat0: Path = Path()
    ifg_flat1: Path = Path()
    ifg_flat10: Path = Path()
    ifg_flat_coh: Path = Path()
    ifg_flat_coh_geocode_bmp: Path = Path()
    ifg_flat_coh_geocode_out: Path = Path()
    ifg_flat_coh_geocode_png: Path = Path()
    ifg_flat_coh0: Path = Path()
    ifg_flat_coh0_mask: Path = Path()
    ifg_flat_coh10: Path = Path()
    ifg_flat_coh10_mask: Path = Path()
    ifg_gcp: Path = Path()
    ifg_gcp_ph: Path = Path()
    ifg_mask: Path = Path()
    ifg_mask_thin: Path = Path()
    ifg_off: Path = Path()
    ifg_off10: Path = Path()
    ifg_offs: Path = Path()
    ifg_sim_diff: Path = Path()
    ifg_sim_unw: Path = Path()
    ifg_sim_unw0: Path = Path()
    ifg_sim_unw1: Path = Path()
    ifg_sim_unw_ph: Path = Path()
    ifg_unw: Path = Path()
    ifg_unw_geocode_2pi_bmp: Path = Path()
    ifg_unw_geocode_6pi_bmp: Path = Path()
    ifg_unw_geocode_out: Path = Path()
    ifg_unw_geocode_2pi_png: Path = Path()
    ifg_unw_geocode_6pi_png: Path = Path()
    ifg_unw_mask: Path = Path()
    ifg_unw_model: Path = Path()
    ifg_unw_thin: Path = Path()
    ifg_unw_geocode_out_tiff: Path = Path()
    ifg_flat_geocode_out_tiff: Path = Path()
    ifg_filt_geocode_out_tiff: Path = Path()
    ifg_flat_coh_geocode_out_tiff: Path = Path()
    ifg_filt_coh_geocode_out_tiff: Path = Path()

    def __init__(self, proc: ProcConfig, primary: Path, secondary: Path):
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

        self.ifg_dir = (out_dir / proc.int_dir) / "{}-{}".format(primary, secondary)
        self.primary_dir = (out_dir / proc.slc_dir) / primary
        self.secondary_dir = (out_dir / proc.slc_dir) / secondary

        self.r_primary_slc_name = self.primary_dir / "r{}_{}".format(primary, proc.polarisation)

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
        _primary_secondary_name = "{}-{}_{}_{}rlks".format(primary, secondary, proc.polarisation, proc.range_looks)
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
        self.ifg_filt_coh_geocode_bmp = Path(_primary_secondary_name + "_filt_geo_coh.bmp")
        self.ifg_filt_coh_geocode_out = Path(_primary_secondary_name + "_filt_geo_coh")
        self.ifg_filt_coh_geocode_png = Path(_primary_secondary_name + "_filt_geo_coh.png")

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
        self.ifg_flat_coh_geocode_bmp = Path(_primary_secondary_name + "_flat_geo_coh.bmp")
        self.ifg_flat_coh_geocode_out = Path(_primary_secondary_name + "_flat_geo_coh")
        self.ifg_flat_coh_geocode_png = Path(_primary_secondary_name + "_flat_geo_coh.png")
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
        self.ifg_flat_geocode_out_tiff = Path(_primary_secondary_name + "_flat_geo_int.tif")
        self.ifg_filt_geocode_out_tiff = Path(_primary_secondary_name + "_filt_geo_int.tif")
        self.ifg_flat_coh_geocode_out_tiff = Path(_primary_secondary_name + "_flat_geo_coh.tif")
        self.ifg_filt_coh_geocode_out_tiff = Path(_primary_secondary_name + "_filt_geo_coh.tif")
