#!/usr/bin/env python

import os
import math
import re
from typing import List, Optional, Tuple, Union
from collections import namedtuple
import datetime
from datetime import timedelta
from pathlib import Path
import fnmatch

import structlog
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid import make_axes_locatable
from matplotlib import dates as mdates
import numpy as np


_LOG = structlog.get_logger("insar")


class SlcParFileParser:
    def __init__(self, par_file: Path,) -> None:
        """
        Convenient access fields for SLC image parameter properties.

        :param par_file:
            A full path to a parameter file.
        """

        self.par_file = par_file
        self.par_params = None
        with open(self.par_file.as_posix(), "r") as fid:
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

    @property
    def slc_par_params(self):
        """
        Convenient SLC parameter access method needed for baseline calculation.
        """

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

    @property
    def orbit_par_params(self):
        """
        Covenient orbit parameter access method needed for baseline calculation.
        """

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
            xyz,
        )


class BaselineProcess:
    def __init__(
        self,
        slc_par_list: List[Path],
        polarization: List[str],
        master_scene: datetime.date,
        scene_list: Optional[Path] = None,
        outdir: Optional[Path] = None,
    ) -> None:
        """
        Calculate initial and precision baselines for SLC image stack.

        Provides access to functionality to generate Interferometric-pair List
        using sbas_list, single_master_list and daisy_chain_list methods.

        :param slc_par_list:
            List of Paths of a slc parameter file.
        :param polarization:
            A polarization of slc scenes. SLC parameter list  must be of  same polarization.
        :param master_scene:
            Acquisition date of a master SLC scene.
        :param scene_list:
            Optional scene_list file path containing the slc acquisition dates in 'YYYYMMDD' format.
            Otherwise, slc acquisition dates will be parsed from parameter file in the slc_par_list.
        :param outdir:
            Optional baseline results output path. Otherwise, outdir will be current working directory.
        """

        self.slc_par_list = slc_par_list
        self.scenes_list = scene_list
        self.master_scene = master_scene
        self.polarization = polarization
        self.slc_dates = self.list_slc_dates()
        self.slc_par_list_posix = list(map(lambda x: x.as_posix(), self.slc_par_list))
        # select the mater to be center date is None
        if self.master_scene is None:
            self.master_scene = self.slc_dates[int(len(self.slc_dates) / 2)]
        self.outdir = outdir
        if self.outdir is None:
            self.outdir = os.getcwd()

    def list_slc_dates(self):
        """
        Returns sorted (ascending) dates for a SLC stack.

        Dates are parsed from scenes_list (dates in 'YYYYMMDD' format) if scene list exists.
        Else the dates are parsed from slc_parameter list, first regex pattern "[0-9]{8}
        match is attributed as slc_scene dates.
        """

        if self.scenes_list is not None:
            with open(self.scenes_list.as_posix(), "r") as src:
                slc_dates = [
                    datetime.datetime.strptime(scene.strip(), "%Y%m%d").date()
                    for scene in src.readlines()
                ]
                return sorted(slc_dates, reverse=True)

        slc_dates = []
        for par in self.slc_par_list:
            dt_str = re.findall("[0-9]{8}", Path(par).stem)[0]
            slc_dates.append(datetime.datetime.strptime(dt_str, "%Y%m%d").date())
        return sorted(slc_dates, reverse=False)

    def _match_par(
        self, scene_date: datetime.date,
    ):
        """
        Returns the SLC parameter file for scene_date.
        """

        _date_str = "{:04}{:02}{:02}".format(
            scene_date.year, scene_date.month, scene_date.day
        )

        # slc paramter is matched from slc parameter path lists
        # for any polarizations. Both VV and VH have same params values required
        # to compute baseline
        for pol in self.polarization:
            _par = fnmatch.filter(
                self.slc_par_list_posix,
                "*{}_{}.slc.par".format(scene_date.strftime("%Y%m%d"), pol.upper()),
            )
            if not _par:
                continue
            if Path(_par[0]).exists():
                return Path(_par[0])

        raise FileNotFoundError(f"{scene_date} has no matching slc parameter file")

    def compute_perpendicular_baseline(self):
        """
        Computes baseline calculations for SLC image stack.
        """

        relBperps = np.zeros((len(self.slc_dates), len(self.slc_dates) - 1))

        # compute baseline for treating each slc scene as a master slc
        for m_idx, master_date in enumerate(self.slc_dates):
            m_data = SlcParFileParser(Path(self._match_par(master_date)))
            m_P = self.llh2xyz(m_data.slc_par_params.lat, m_data.slc_par_params.lon, 0.0)
            m_M = self.calc_orbit_pos(
                m_data.orbit_par_params.t,
                m_data.slc_par_params.tmin,
                m_data.slc_par_params.tmax,
                m_data.orbit_par_params.xyz,
                m_P,
            )
            R1 = m_M - m_P
            slaves = self.slc_dates[:]
            slaves.pop(m_idx)
            Bperps = []
            for s_idx, slave_date in enumerate(slaves):
                s_data = SlcParFileParser(Path(self._match_par(slave_date)))
                s_M = self.calc_orbit_pos(
                    s_data.orbit_par_params.t,
                    m_data.slc_par_params.tmin,
                    m_data.slc_par_params.tmax,
                    s_data.orbit_par_params.xyz,
                    m_P,
                )
                R2 = s_M - m_P
                B = np.linalg.norm(m_M - s_M)
                Bpar = np.linalg.norm(R1) - np.linalg.norm(R2)
                Bperp = math.sqrt(B ** 2 - Bpar ** 2)
                temp1 = np.dot(m_M, R1)
                temp2 = np.linalg.norm(m_M) * np.linalg.norm(R1)
                theta1 = math.acos(temp1 / temp2)
                temp1 = np.dot(m_M, R2)
                temp2 = np.linalg.norm(m_M) * np.linalg.norm(R2)
                theta2 = math.acos(temp1 / temp2)
                if theta1 < theta2:
                    Bperp = -Bperp
                Bperps.append(Bperp)
            Bperps.insert(m_idx, 0.0)

            count_rel = -1
            for Bperp in Bperps:
                if count_rel > -1:
                    relBperps[m_idx, count_rel] = Bperp - Bperp_temp

                Bperp_temp = Bperp
                count_rel += 1
        relBperps_median = np.median(relBperps, axis=0)
        m_idx = self.slc_dates.index(self.master_scene)
        sum_rel = 0
        Bperps[m_idx] = 0.0
        for i in range(m_idx - 1, -1, -1):
            sum_rel = sum_rel - relBperps_median[i]
            Bperps[i] = sum_rel
        sum_rel = 0
        for i in range(m_idx + 1, len(self.slc_dates)):
            sum_rel += relBperps_median[i - 1]
            Bperps[i] = sum_rel

        slaves = self.slc_dates[:]
        slaves.pop(m_idx)

        Bdopp = []
        m_data = SlcParFileParser(Path(self._match_par(self.master_scene)))
        for idx, slave in enumerate(slaves):
            s_data = SlcParFileParser(Path(self._match_par(slave)))
            Bdopp.append(s_data.orbit_par_params.fDC - m_data.orbit_par_params.fDC)
        Bdopp.insert(m_idx, 0.0)

        return Bperps, Bdopp

    def sbas_list(
        self,
        btemp_max: Optional[float] = 1826.25,
        coreg_threshold: Optional[float] = 0.5,
        nmin: Optional[int] = 4,
        nmax: Optional[int] = 7,
        outfile: Optional[Path] = None,
    ):
        """
        Coherence-based SBAS Network calculation and Integerogram List.
        """

        bperps, bdopp = self.compute_perpendicular_baseline()
        m_idx = self.slc_dates.index(self.master_scene)
        m_data = SlcParFileParser(Path(self._match_par(self.master_scene)))

        bperp_max = (
            (m_data.slc_par_params.Br / m_data.slc_par_params.f)
            * m_data.slc_par_params.r1
            * math.tan(m_data.slc_par_params.inc / 180.0 * math.pi)
        )

        epoch1, epoch2, bperps_sbas = self.create_sb_network(
            self.slc_dates,
            bperps,
            bdopp,
            m_idx,
            btemp_max,
            bperp_max,
            m_data.slc_par_params.Ba,
            coreg_threshold,
            nmin,
            nmax,
            Path(self.outdir).joinpath("sbas_connection.txt"),
        )

        if outfile is None:
            outfile = Path(self.outdir) / "lists" / "ifgs.list"

            if not outfile.parent.exists():
                outfile.parent.mkdir(parents=True)

        with open(outfile.as_posix(), "w") as fid:
            for ep1, ep2 in zip(epoch1, epoch2):
                fid.write(
                    self.slc_dates[ep1].strftime("%Y%m%d")
                    + ","
                    + self.slc_dates[ep2].strftime("%Y%m%d")
                    + "\n"
                )

    @staticmethod
    def single_master_list(
        master: datetime.date, slaves: List[datetime.date], outfile: Path,
    ) -> None:
        """
        Create single Master Interferogram List.

        :param master:
            Acquisition date for slc master scene.
        :param slaves:
            List of acquisition date for slaves slc scenes.
        :param outfile:
            A full path of an outfile to write interferometric-pair list
        """

        with open(outfile.as_posix(), "w") as fid:
            for slave in slaves:
                fid.write(
                    master.strftime("%Y%m%d") + "," + slave.strftime("%Y%m%d") + "\n"
                )

    @staticmethod
    def daisy_chain_list(scenes: List[datetime.date], outfile: Path,) -> None:
        """
        Create Daisy-chained Interferogram List.

        :param scenes:
            List of acquisition dates for slc scenes.
        :param outfile:
            A full path of an outfile to write inteferometric-par list
        """

        nums = range(0, len(scenes))
        _scenes = [sc.strftime("%Y%m%d") for sc in scenes]
        merged = [(nums[idx], scene) for idx, scene in enumerate(_scenes)]
        with open(outfile.as_posix(), "w") as fid:
            for num, scene in merged:
                num1 = num + 1
                if num1 < len(_scenes):
                    fid.write(scene + "," + _scenes[num1] + "\n")

    @staticmethod
    def llh2xyz(latitude: float, longitude: float, height: float,) -> np.ndarray:
        """
        Transform latitude, longitude, height to state vector position x, y, z.

        :param latitude:
            A latitude geographical coordinate (in decimal degrees).
        :param longitude:
            A longitude geographical coordinate (in decimal degrees).
        :param height:
            Heigh in units (m)

        :returns:
            transformed coordinate in x, y, z units.
        """
        _a = 6378137
        _f = 0.0033528107
        _c = _a / (1 - _f)
        e2 = 2 * _f - _f ** 2
        e2_prime = e2 / (1 - _f) ** 2

        lat = np.deg2rad(latitude)
        lon = np.deg2rad(longitude)

        _n = _c / math.sqrt(1 + e2_prime * (math.cos(lat)) ** 2)
        p = (_n + height) * math.cos(lat)
        x = p * math.cos(lon)
        y = p * math.sin(lon)
        z = ((1 - e2) * _n + height) * math.sin(lat)

        return np.array((x, y, z))

    @staticmethod
    def calc_orbit_pos(
        t: List[float],
        t_min: float,
        t_max: float,
        xyz: List[List[float]],
        xyz_centre: np.ndarray,
    ):
        """
        Calculate the in-orbit position for the time of scene centre acquisition.

        :param t:
            List of time of state vectors.
        :param t_min:
            start time in slc parameter file.
        :param t_max:
            start time + (azimuth_lines - 1.) / slc_parameter['prf']
        :param xyz:
            List of state vector position from slc parameter file.
        :param xyz_centre:
            Centre geographical coordinate (latitude, longitude) and height transformed
            in state vector position.

        :returns:
            Oribit position (x, y, z)
        """

        # normalise time vector to the interval [-2 2]
        n = len(t)

        def norm(xs, a, b):
            """Normalises data from a given interval [a;b] to [-2;2]"""
            # initialise loop (return values will be same length as X)
            i = 0
            ys = xs
            # perform normalization for each value in X
            for x in xs:
                ys[i] = (x - a) / (b - a) * 4 - 2
                i = i + 1
            return ys

        t = norm(t, t_min, t_max)
        deg = min(5, n - 1)
        # split xyz orbit vector as poly1d works with 1d polynomials only
        x = [row[0] for row in xyz]
        y = [row[1] for row in xyz]
        z = [row[2] for row in xyz]
        # estimate polynomial coefficients for orbital state vectors
        poly_x = np.poly1d(np.polyfit(t, x, deg))
        poly_y = np.poly1d(np.polyfit(t, y, deg))
        poly_z = np.poly1d(np.polyfit(t, z, deg))
        # first derivative of polynomials
        poly_x_der = poly_x.deriv()
        poly_y_der = poly_y.deriv()
        poly_z_der = poly_z.deriv()
        # find point from where scene centre is acquired on master orbit
        tm = 0
        dt = 1
        x = xyz_centre[0]
        y = xyz_centre[1]
        z = xyz_centre[2]
        while abs(dt) > 10 ** (-10):
            # Position
            xP = poly_x(tm)
            yP = poly_y(tm)
            zP = poly_z(tm)
            # Velocity
            xV = poly_x_der(tm)
            yV = poly_y_der(tm)
            zV = poly_z_der(tm)
            temp1 = (xP - x) * xV + (yP - y) * yV + (zP - z) * zV
            temp2 = xV * xV + yV * yV + zV * zV
            dt = -temp1 / temp2
            tm = tm + dt
        return np.array((xP, yP, zP))

    @staticmethod
    def epoch_baselines(
        epochs, bperp, masidx, slvidx, supermaster,
    ):
        """Determine relative perpendicular baselines of epochs from interferometric baselines.

        :param epochs:
            List of epoch dates.
        :param bperp:
            List of interferogram absolute perpendicular baselines.
        :param masidx:
            List of master indices from get_index.
        :param slvidx:
            List of slave indices from get_index.
        :param supermaster:
            Epoch to set relative bperp to zero (integer).

        returns:
            epochbperp: List of epoch relative perpendicular baselines.
        """

        # Count number of ifgs and epochs
        nifgs = len(bperp)
        nepochs = len(epochs)

        _LOG.info(
            "number of interferograms and epochs in the network",
            interferograms=nifgs,
            epochs=nepochs,
        )
        # Initialise design matrix 'A'
        A = np.zeros((nifgs + 1, nepochs))

        # assign super-master epoch to constrain relative baselines
        A[0, supermaster] = 1
        b = np.zeros(nifgs + 1)
        b[1 : nifgs + 1] = bperp

        # Construct design matrix
        for i in range(nifgs):
            imas = masidx[i]
            islv = slvidx[i]
            A[i + 1, imas] = -1
            A[i + 1, islv] = 1

        # Do overdetermined linear inversion x=A\b
        x = np.linalg.lstsq(A, b)
        return x[:][0]

    @staticmethod
    def create_sb_network(
        dates: List[datetime.date],
        Bperps: List[float],
        Bdopp: List[float],
        master_ix: int,
        Btemp_max: float,
        Bperp_max: float,
        Ba: float,
        coh_thres: float,
        nmin: int,
        nmax: int,
        outfile1: Union[Path, str],
    ) -> Tuple:
        """
        Creates SBAS network for slc scenes.

        :param dates:
            List of slc acquisition dates sorted (ascending).
        :param Bperps:
            List of perpendicular baselines w.r.t master slc..
        :param Bdopp:
            List of doppler centroid frequency (fDC) difference w.r.t to master slc.
        :param master_idx:
            index of master scene in the list of slc dates.
        :param Btemp_max:
            Maximum Btemp(total decorrelation).
        :param Bperp_max:
            Maximum Bperp(total decorrelation).
        :param coh_thres:
            Coherence threshold for selection of combinations.
        :param nmin:
            Minimum number of connection per epoch.
        :param nmax:
            Maximum number of connection per epoch.

        :returns: (epoch1, epoch2, Bperbs_sbas)
            Lists of epoch1 and epoch2 to form interferometric-pair in sbas list.
            Bperps_sbas: perpendicular baselines of sbas-interferogram list.
        """

        # calculate Bperp differences (bdiff) for all possible IFG combinations
        num_scenes = len(Bperps)
        X, Y = np.meshgrid(np.array(Bperps), np.array(Bperps))
        bdiff_all = X - Y
        bdiff = abs(bdiff_all)
        # calculate Bdopp differences
        X, Y = np.meshgrid(np.array(Bdopp), np.array(Bdopp))
        doppdiff = abs(X - Y)
        # calculate Btemp differences in days (ddiff) for all possible IFG comb.
        dates_diff_days = [0] * num_scenes
        i = 0
        # loop needed to convert date objects to integer dates (eg wrt master)
        for line in dates:
            dates_diff_days[i] = (line - dates[master_ix]).days
            i = i + 1
        X, Y = np.meshgrid(dates_diff_days, dates_diff_days)
        ddiff = abs(X - Y)

        # correlation matrix rho from linear decorrelation model (Kampes 2005)
        rho = (1 - bdiff / Bperp_max) * (1 - ddiff / Btemp_max) * (1 - doppdiff / Ba)
        rho[bdiff > Bperp_max] = 0
        rho[ddiff > Btemp_max] = 0
        rho[doppdiff > Ba] = 0
        rho = rho - np.eye(num_scenes)
        # boolean index of all combinations exceeding coherence threshold
        ix = rho > coh_thres
        # this index will be adapted according to min/max number of IFGs
        ix2 = ix

        # Output numbers on possible connections
        with open(outfile1, "w") as outfile:
            outfile.write(
                "Theoretical number of possible connections for %s scenes: %d\n"
                % (num_scenes, num_scenes * (num_scenes - 1) / 2)
            )

            # upper triangle matrix of valid connections
            tri_true = np.logical_not(np.tril(np.ones((num_scenes, num_scenes))))
            outfile.write(
                "Number of connections with predicted coherence greater %3.1f: %d\n"
                % (coh_thres, np.sum(np.logical_and(ix, tri_true)))
            )
            outfile.write(
                "Mean predicted coherence for these connections: %3.2f\n"
                % (np.mean(rho[np.logical_and(ix, tri_true)]))
            )

            # keep connections according to nmin even if rho is below threshold
            ntest = 1

            if num_scenes < nmin:
                nmin = num_scenes - 1

            while ntest < nmin + 0.5:

                for i in range(0, num_scenes):
                    # find scenes with no connections (1st), one connection (2nd), ...
                    if np.sum(ix2[i]) < ntest - 0.5:
                        # get index of all TRUE values in this row of ix2
                        temp_ix = np.where(np.logical_not(ix2[i]))[0]
                        # get index of scene with maximum correlation
                        rho_max_ix = np.argmax(rho[i, temp_ix])
                        # check if value is not subject to total decorrelation
                        j = temp_ix[rho_max_ix]
                        if rho[i, rho_max_ix] > 0:
                            # set value in ix2 to True for this scene
                            ix2[i, j] = True
                            ix2[j, i] = True
                        else:
                            _LOG.info(
                                "connection between scenes not possible (total decorrelation)",
                                scene_i=i,
                                scene_j=j,
                            )
                ntest = ntest + 1

            # delete unwanted connections (greater nmax, low coherence)
            # check if there is any epoch with more than nmax connections
            while any(ix2.sum(axis=0) > nmax + 0.5):
                # loop trough all epochs, only one connection is deleted per epoch
                for i in range(0, num_scenes):
                    # find scenes with more than nmax connections
                    if np.sum(ix2[i]) > nmax + 0.5:
                        cand = []
                        # get index of all TRUE values in this row of ix2
                        temp_ix = np.where(ix2[i])[0]
                        num_connect = len(temp_ix)
                        for k in range(0, num_connect):
                            # only consider neighbours with more than nmin connect.
                            if np.sum(ix2[temp_ix[k]]) > nmin + 0.5:
                                cand.append(temp_ix[k])
                        rho_cand = rho[i, cand]
                        # get index of scene with minimum correlation
                        rho_min_ix = np.argmin(rho_cand)
                        # set value in ix2 to False for rho_min_ix
                        j = cand[rho_min_ix]
                        ix2[i, j] = False
                        ix2[j, i] = False

            # matrix of connections (true: use this connection, false: don't use
            ix = np.logical_and(ix2, tri_true)

            # add back all daisy-chain interferograms (if not selected already)
            for i in range(0, num_scenes - 1):
                ix[i, i + 1] = True

            # final interferogram connections (already sorted ascending for x)
            [epoch1, epoch2] = np.where(ix)
            outfile.write(
                "Number of final SBAS network connections: %d\n" % (len(epoch1))
            )
            outfile.write(
                "Mean predicted coherence for these connections: %3.2f\n"
                % (np.mean(rho[ix]))
            )
            outfile.close

            # plot Bperps of final connections
            Bperps_sbas = bdiff_all[ix]

            # return values
        return epoch1, epoch2, Bperps_sbas

    @staticmethod
    def plot_baseline_time_sm(
        epochs, Bperps, master_ix, filename,
    ):
        """
        Make a baseline time plot and save to disk
        """

        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        divider = make_axes_locatable(ax1)

        # plot epochs as filled circles
        ax1.plot_date(
            epochs,
            Bperps,
            xdate=True,
            ydate=False,
            marker="o",
            markersize=14,
            markerfacecolor="black",
            linestyle="None",
        )
        # use a red circle for master date
        ax1.plot_date(
            epochs[master_ix],
            Bperps[master_ix],
            xdate=True,
            ydate=False,
            marker="o",
            markersize=14,
            markerfacecolor="darkred",
            linestyle="None",
        )

        # plot epoch numbers as symbols
        labels = [i + 1 for i in range(len(Bperps))]
        for a, b, c in zip(epochs, Bperps, labels):
            ax1.text(
                a, b, c, color="white", ha="center", va="center", size=9, weight="bold"
            )

        # format the time axis ticks
        years = mdates.YearLocator()  # every year
        months = mdates.MonthLocator()  # every month
        yearsFmt = mdates.DateFormatter("%Y-%m-%d")
        ax1.xaxis.set_major_locator(years)
        ax1.xaxis.set_major_formatter(yearsFmt)
        ax1.xaxis.set_minor_locator(months)

        # set the time axis range
        date_min = epochs.min()
        date_max = epochs.max()
        date_range = date_max - date_min
        date_add = date_range.days / 15
        ax1.set_xlim(
            date_min - timedelta(days=date_add), date_max + timedelta(days=date_add),
        )

        # set the Bperp axis range
        Bperp_min = min(Bperps)
        Bperp_max = max(Bperps)
        Bperp_range = Bperp_max - Bperp_min
        ax1.set_ylim(Bperp_min - Bperp_range / 15, Bperp_max + Bperp_range / 15)

        # set axis titles
        ax1.set_xlabel("Date (YYYY-MM-DD)")
        ax1.set_ylabel("Perpendicular Baseline (m)")
        ax1.grid(True)

        # rotates and right aligns the date labels
        fig.autofmt_xdate()

        # Save plot to PNG file
        savepath = filename + ".png"
        plt.savefig(
            savepath,
            orientation="landscape",
            transparent=False,
            format="png",
            papertype="a4",
        )
        return

    @staticmethod
    def plot_baseline_time_sbas(
        epochs, Bperps, epoch1, epoch2, filename,
    ):
        """
        Make a baseline time plot including IFG connections and save to disk
        """

        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        divider = make_axes_locatable(ax1)

        # plot interferograms as lines
        for n, m in zip(epoch1, epoch2):
            # print n, m
            x = [epochs[n], epochs[m]]
            y = [Bperps[n], Bperps[m]]
            #  baselines[x]
            ax1.plot_date(
                x, y, xdate=True, ydate=False, linestyle="-", color="r", linewidth=1.0
            )

        # plot epochs as filled circles
        ax1.plot_date(
            epochs,
            Bperps,
            xdate=True,
            ydate=False,
            marker="o",
            markersize=14,
            markerfacecolor="black",
            linestyle="None",
        )

        # plot epoch numbers as symbols
        labels = [i + 1 for i in range(len(Bperps))]
        for a, b, c in zip(epochs, Bperps, labels):
            ax1.text(
                a, b, c, color="white", ha="center", va="center", size=9, weight="bold"
            )

        # format the time axis ticks
        years = mdates.YearLocator()  # every year
        months = mdates.MonthLocator()  # every month
        yearsFmt = mdates.DateFormatter("%Y-%m-%d")
        ax1.xaxis.set_major_locator(years)
        ax1.xaxis.set_major_formatter(yearsFmt)
        ax1.xaxis.set_minor_locator(months)

        # set the time axis range
        date_min = epochs.min()
        date_max = epochs.max()
        date_range = date_max - date_min
        date_add = date_range.days / 15
        ax1.set_xlim(
            date_min - timedelta(days=date_add), date_max + timedelta(days=date_add),
        )

        # set the Bperp axis range
        Bperp_min = min(Bperps)
        Bperp_max = max(Bperps)
        Bperp_range = Bperp_max - Bperp_min
        ax1.set_ylim(Bperp_min - Bperp_range / 15, Bperp_max + Bperp_range / 15)

        # set axis titles
        ax1.set_xlabel("Date (YYYY-MM-DD)")
        ax1.set_ylabel("Perpendicular Baseline (m)")
        ax1.grid(True)

        # rotates and right aligns the date labels
        fig.autofmt_xdate()

        # Save plot to PNG file
        savepath = filename + ".png"
        plt.savefig(
            savepath,
            orientation="landscape",
            transparent=False,
            format="png",
            papertype="a4",
        )
        return
