import luigi
from luigi.util import requires

from insar.constant import SCENE_DATE_FMT
from insar.project import ProcConfig
from insar.calc_baselines_new import BaselineProcess
from insar.logs import STATUS_LOGGER
from insar.paths.stack import StackPaths
from insar.paths.slc import SlcPaths

from insar.workflow.luigi.utils import PathParameter, tdir, get_scenes, read_primary_date
from insar.workflow.luigi.multilook import CreateMultilook


@requires(CreateMultilook)
class CalcInitialBaseline(luigi.Task):
    """
    Runs calculation of initial baseline task
    """

    proc_file = PathParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_calcinitialbaseline_status_logs.out"
        )

    def run(self):
        log = STATUS_LOGGER.bind(stack_id=self.stack_id)
        log.info("Beginning baseline calculation")

        # Load the gamma proc config file
        with open(str(self.proc_file), "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        paths = StackPaths(proc_config)
        slc_frames = get_scenes(paths.acquisition_csv)

        slc_par_files = []
        primary_pol = proc_config.polarisation
        polarizations = [primary_pol]

        # Explicitly NOT supporting cross-polarisation IFGs, for now
        enable_cross_pol_ifgs = False

        for _dt, _, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)

            if primary_pol in _pols:
                slc_paths = SlcPaths(proc_config, slc_scene, primary_pol)
            elif not enable_cross_pol_ifgs:
                continue
            else:
                slc_paths = SlcPaths(proc_config, slc_scene, _pols[0])
                polarizations.append(_pols[0])

            if not slc_paths.slc_par.exists():
                raise FileNotFoundError(f"missing {slc_paths.slc_par} file")

            slc_par_files.append(slc_paths.slc_par)

        baseline = BaselineProcess(
            slc_par_files,
            list(set(polarizations)),
            primary_scene=read_primary_date(paths.output_dir),
            outdir=paths.output_dir,
        )

        # creates a ifg list based on sbas-network
        baseline.sbas_list(nmin=int(proc_config.min_connect), nmax=int(proc_config.max_connect))

        log.info("Baseline calculation complete")

        with self.output().open("w") as out_fid:
            out_fid.write("")

