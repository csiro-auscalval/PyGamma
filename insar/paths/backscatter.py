from pathlib import Path
from insar.path_util import append_suffix

from .slc import SlcPaths

class BackscatterPaths:
    sigma0: Path
    sigma0_geo: Path
    sigma0_geo_tif: Path

    gamma0: Path
    gamma0_geo: Path
    gamma0_geo_tif: Path

    def __init__(self, slc_paths: SlcPaths):
        slc_outdir = slc_paths.dir
        slc_prefix = slc_paths.mli.stem

        self.sigma0 = slc_outdir / f"{slc_prefix}_sigma0"
        self.sigma0_geo = slc_outdir / f"{slc_prefix}_geo_sigma0"
        self.sigma0_geo_tif = append_suffix(self.sigma0_geo, ".tif")

        self.gamma0 = slc_outdir / f"{slc_prefix}_gamma0"
        self.gamma0_geo = slc_outdir / f"{slc_prefix}_geo_gamma0"
        self.gamma0_geo_tif = append_suffix(self.gamma0_geo, ".tif")
