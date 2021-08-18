import luigi
from luigi.util import requires

from pathlib import Path

from insar.calc_multilook_values import multilook, calculate_mean_look_values
from insar.project import ProcConfig
from insar.constant import SCENE_DATE_FMT

from insar.workflow.luigi.utils import tdir, get_scenes
from insar.workflow.luigi.mosaic import CreateSlcMosaic


class Multilook(luigi.Task):
    """
    Produces multilooked SLC given a specified rlks/alks for multilooking
    """

    slc = luigi.Parameter()
    slc_par = luigi.Parameter()
    rlks = luigi.IntParameter()
    alks = luigi.IntParameter()
    workdir = luigi.Parameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{Path(str(self.slc)).stem}_ml_logs.out"
        )

    def run(self):
        multilook(
            Path(str(self.slc)),
            Path(str(self.slc_par)),
            int(str(self.rlks)),
            int(str(self.alks)),
        )

        with self.output().open("w") as f:
            f.write("")

# FIXME: CreateSlcMosaic should NOT be a requirement (this is S1 specific...)
@requires(CreateSlcMosaic)
class CreateMultilook(luigi.Task):
    """
    Runs creation of multi-look image task for all scenes, for all polariastions.
    """

    proc_file = luigi.Parameter()
    multi_look = luigi.IntParameter()

    def output(self):
        return luigi.LocalTarget(
            tdir(self.workdir) / f"{self.stack_id}_createmultilook_status_logs.out"
        )

    def run(self):
        outdir = Path(self.outdir)

        with open(self.proc_file, "r") as proc_fileobj:
            proc = ProcConfig.from_file(proc_fileobj)

        # calculate the mean range and azimuth look values
        slc_dir = outdir / proc.slc_dir
        slc_frames = get_scenes(self.burst_data_csv)
        slc_par_files = []

        for _dt, status_frame, _pols in slc_frames:
            slc_scene = _dt.strftime(SCENE_DATE_FMT)
            for _pol in _pols:
                if _pol not in self.polarization:
                    continue

                slc_par = f"{slc_scene}_{_pol.upper()}.slc.par"
                slc_par = outdir / proc.slc_dir / slc_scene / slc_par
                if not slc_par.exists():
                    raise FileNotFoundError(f"missing {slc_par} file")

                slc_par_files.append(Path(slc_par))

        # range and azimuth looks are only computed from VV polarization
        rlks, alks, *_ = calculate_mean_look_values(
            [_par for _par in slc_par_files if "VV" in _par.stem],
            int(str(self.multi_look)),
        )

        # multi-look jobs run
        ml_jobs = []
        for slc_par in slc_par_files:
            slc = slc_par.with_suffix("")
            ml_jobs.append(
                Multilook(
                    slc=slc, slc_par=slc_par, rlks=rlks, alks=alks, workdir=self.workdir
                )
            )

        yield ml_jobs

        with self.output().open("w") as out_fid:
            out_fid.write("rlks:\t {}\n".format(str(rlks)))
            out_fid.write("alks:\t {}".format(str(alks)))

