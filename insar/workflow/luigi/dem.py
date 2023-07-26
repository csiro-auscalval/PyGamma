import luigi
import luigi.configuration

import insar.constant as const

from luigi.util import requires
from pathlib import Path
from pathlib import Path

from insar.make_gamma_dem import create_gamma_dem
from insar.logs import STATUS_LOGGER as LOG

from insar.workflow.luigi.utils import tdir, load_settings,  PathParameter
from insar.workflow.luigi.stack_setup import InitialSetup

@requires(InitialSetup)
class CreateGammaDem(luigi.Task):
    """
    Subset the DEM based on stack extent and convert to GAMMA format.
    """

    dem_img = PathParameter()

    def output(self) -> luigi.LocalTarget:
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_creategammadem_status_logs.out"
        )

    def run(self) -> None:
        LOG.info("Beginning DEM creation")

        proc_config, metadata = load_settings(Path(self.proc_file))

        gamma_dem_dir = Path(self.outdir) / proc_config.dem_dir
        gamma_dem_dir.mkdir(parents=True, exist_ok=True)

        create_gamma_dem(gamma_dem_dir,
                         self.dem_img,
                         str(self.stack_id),
                         metadata["stack_extent"])

        LOG.info("DEM creation complete")

        with self.output().open("w") as out_fid:
            out_fid.write("")

