from pathlib import Path
import luigi
import luigi.configuration
from luigi.util import requires

from pathlib import Path

from insar.make_gamma_dem import create_gamma_dem
from insar.logs import STATUS_LOGGER

from insar.workflow.luigi.utils import tdir, load_settings, mk_clean_dir, PathParameter
from insar.workflow.luigi.stack_setup import InitialSetup

@requires(InitialSetup)
class CreateGammaDem(luigi.Task):
    """
    Runs create gamma dem task
    """

    dem_img = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_creategammadem_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("Beginning gamma DEM creation")

        proc_config, metadata = load_settings(Path(self.proc_file))

        gamma_dem_dir = Path(self.outdir) / proc_config.gamma_dem_dir
        mk_clean_dir(gamma_dem_dir)

        kwargs = {
            "gamma_dem_dir": gamma_dem_dir,
            "dem_img": self.dem_img,
            "stack_id": f"{self.stack_id}",
            "stack_extent": metadata["stack_extent"],
        }

        create_gamma_dem(**kwargs)

        log.info("Gamma DEM creation complete")

        with self.output().open("w") as out_fid:
            out_fid.write("")

