#!/usr/bin/env python

import os
import re
from typing import Optional, List
from collections import namedtuple
import datetime
from pathlib import Path


class ParFileParser:
    def __init__(self, par_file):
        self.par_file = par_file
        self.par_params = None
        with open(self.par_file, "r") as fid:
            tmp_dict = dict()
            lines = fid.readlines()
            for line in lines:
                vals = line.strip().split(":")
                try:
                    tmp_dict[vals[0]] = [v for v in vals[1].split()]
                except IndexError:
                    pass
        self.par_params = tmp_dict

    def all_par_params(self):
        return self.par_params

    def slc_par_params(self):
        par_params = namedtuple(
            "slc_par_params",
            ["tmin", "tmax", "lat", "lon", "r1", "inc", "f", "Br", "Ba"],
        )
        return par_params(
            float(self.par_params["start_time"][0]),
            float(self.par_params["start_time"][0])
            + (float(self.par_params["azimuth_lines"][0]) - 1.0)
            / float(self.par_params["prf"][0]),
            float(self.par_params["center_latitude"][0]),
            float(self.par_params["center_longitude"][0]),
            float(self.par_params["center_range_slc"][0]),
            float(self.par_params["incidence_angle"][0]),
            float(self.par_params["radar_frequency"][0]),
            float(self.par_params["chirp_bandwidth"][0]),
            float(self.par_params["azimuth_proc_bandwidth"][0]),
        )

    def orbit_par_params(self):
        orbit_params = namedtuple("orbit_par_params", ["fDC", "t", "xyz"])
        num_state_vectors = int(self.par_params["number_of_state_vectors"][0])

        xyz = []
        for idx in range(num_state_vectors):
            pos = self.par_params["state_vector_position_{}".format(idx + 1)]
            xyz.append([float(pos[0]), float(pos[1]), float(pos[2])])

        return orbit_params(
            float(self.par_params["doppler_polynomial"][0]),
            [
                float(self.par_params["time_of_first_state_vector"][0])
                + idx * float(self.par_params["state_vector_interval"][0])
                for idx in range(num_state_vectors)
            ],
            xyz
        )


class BaselineProcess:
    def __init__(
            self,
            slc_par_list: List[Path],
            scene_list: Optional[Path] = None,
            master_scene: Optional[str] = None
    ):
        self.slc_par_list = slc_par_list
        self.scenes_list = scene_list
        self.master_scene = master_scene
        self.slc_dates = self.list_slc_dates()

        # select the mater to be center date is None
        if self.master_scene is None:
            self.master_scene = self.slc_dates[int(len(self.slc_dates) / 2)]

    def list_slc_dates(self):
        if self.scenes_list is not None:
            with open(self.scenes_list.as_posix(), "r") as src:
                slc_dates = [datetime.datetime.strptime(scene.strip(), "%Y%m%d").date() for scene in src.readlines()]
                return sorted(slc_dates, reverse=True)

        slc_dates = []
        for par in self.slc_par_list:
            dt_str = re.findall("[0-9]{8}", Path(par).stem)[0]
            slc_dates.append(datetime.datetime.strptime(dt_str, "%Y%m%d").date())
        return sorted(slc_dates, reverse=False)

    def compute_perpendicular_baseline(self):
        for dt in self.slc_dates:
            #TODO need write compute baseline methods

    def main(self):
        print(self.slc_dates)
        pass





if __name__ == "__main__":
    slc_par = ["/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T045D_F20S/SLC/20180108/20180108_VV.slc.par"]
    slc = "/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T045D_F20S/SLC/20180108/20180108_VV.slc"
    scene_list = Path("/g/data/dz56/INSAR_ARD/REPROCESSED/VV/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T45D_F19/lists/scenes.list")
    baseline = BaselineProcess(slc_par)
    baseline.main()
