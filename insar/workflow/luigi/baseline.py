import luigi
from luigi.util import requires
from pathlib import Path

from insar.constant import SCENE_DATE_FMT
from insar.project import ProcConfig
from insar.calc_baselines_new import BaselineProcess
from insar.logs import TASK_LOGGER, STATUS_LOGGER, COMMON_PROCESSORS

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

        outdir = Path(self.outdir)

        # Load the gamma proc config file
        with open(str(self.proc_file), "r") as proc_fileobj:
            proc_config = ProcConfig.from_file(proc_fileobj)

        slc_frames = get_scenes(self.burst_data_csv)
        slc_par_files = []
        primary_pol = proc_config.polarisation
        polarizations = [primary_pol]

        # Explicitly NOT supporting cross-polarisation IFGs, for now
        enable_cross_pol_ifgs = False

        for _dt, _, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)
            scene_dir = outdir / proc_config.slc_dir / slc_scene

            if primary_pol in _pols:
                slc_par = f"{slc_scene}_{primary_pol}.slc.par"
            elif not enable_cross_pol_ifgs:
                continue
            else:
                slc_par = f"{slc_scene}_{_pols[0]}.slc.par"
                polarizations.append(_pols[0])

            slc_par = scene_dir / slc_par
            if not slc_par.exists():
                raise FileNotFoundError(f"missing {slc_par} file")

            slc_par_files.append(Path(slc_par))

        baseline = BaselineProcess(
            slc_par_files,
            list(set(polarizations)),
            primary_scene=read_primary_date(outdir),
            outdir=outdir,
        )

        # creates a ifg list based on sbas-network
        baseline.sbas_list(nmin=int(proc_config.min_connect), nmax=int(proc_config.max_connect))

        log.info("Baseline calculation complete")

        with self.output().open("w") as out_fid:
            out_fid.write("")

