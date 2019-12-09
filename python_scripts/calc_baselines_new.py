#!/usr/bin/env python

import math
import re
import logging
from typing import List, Optional
from collections import namedtuple
import datetime
from datetime import timedelta
from pathlib import Path
import fnmatch

import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid import make_axes_locatable
from matplotlib import dates as mdates
import numpy as np

_LOG = logging.getLogger(__name__)


class ParFileParser:
    def __init__(self, par_file: Path):
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
            polarization: str,
            scene_list: Optional[Path] = None,
            master_scene: Optional[str] = None
    ):
        self.slc_par_list = slc_par_list
        self.scenes_list = scene_list
        self.master_scene = master_scene
        self.polarization = polarization
        self.slc_dates = self.list_slc_dates()
        print(self.slc_dates)
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
        slc_par_list = [item.as_posix() for item in self.slc_par_list]
        def _match_par(scene_date: datetime.date):
            _date_str = "{:04}{:02}{:02}".format(scene_date.year, scene_date.month, scene_date.day)
            _par = fnmatch.filter(
                slc_par_list, "*{}_{}.slc.par".format(scene_date.strftime("%Y%m%d"), self.polarization.upper())
            )

            if len(_par) != 1:
                raise IndexError(f"{scene_date} has {len(_par)} match. match must be only 1 file")
            return Path(_par[0])

        relBperps = np.zeros((len(self.slc_dates), len(self.slc_dates) - 1))

        for m_idx, master_date in enumerate(self.slc_dates):
            m_data = ParFileParser(Path(_match_par(master_date)))
            m_P = self.llh2xyz(m_data.slc_par_params.lat, m_data.slc_par_params.lon, 0.0)
            m_M = self.calc_orbit_pos(
                m_data.orbit_par_params.t,
                m_data.slc_par_params.tmin,
                m_data.slc_par_params.tmax,
                m_data.orbit_par_params.xyz,
                m_P
            )
            R1 = m_M - m_P
            slaves = self.slc_dates[:]
            slaves.pop(m_idx)
            Bperps = []
            for s_idx, slave_date in enumerate(slaves):
                s_data = ParFileParser(Path(_match_par(slave_date)))
                s_M = self.calc_orbit_pos(
                    s_data.orbit_par_params.t,
                    m_data.slc_par_params.tmin,
                    m_data.slc_par_params.tmax,
                    s_data.orbit_par_params.xyz,
                    m_P
                )
                R2 = s_M - m_P
                B = np.linalg.norm(m_M - s_M)
                Bpar = np.linalg.norm(R1) - np.linalg.norm(R2)
                Bperp = math.sqrt(B**2 - Bpar**2)
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
        print(self.slc_dates)
        m_idx = self.slc_dates.index(self.master_scene)
        sum_rel = 0
        Bperps[m_idx] = 0.0
        for i in range(m_idx - 1, -1, -1):
            sum_rel = sum_rel - relBperps_median[i]
            Bperps[i] = sum_rel
        sum_rel = 0
        for i in range(m_idx + 1, len(self.slc_dates)):
            sum_rel += relBperps_median[i-1]
            Bperps[i] = sum_rel

        slaves = self.slc_dates[:]
        slaves.pop(m_idx)

        Bdopp = []
        m_data = ParFileParser(Path(_match_par(self.master_scene)))
        for idx, slave in enumerate(slaves):
            s_data = ParFileParser(Path(_match_par(slave)))
            Bdopp.append(s_data.orbit_par_params.fDC - m_data.orbit_par_params.fDC)
        Bdopp.insert(m_idx, 0.0)

        return {dt: (Bperps[idx], Bdopp[idx]) for idx, dt in enumerate(self.slc_dates)}


    @staticmethod
    def llh2xyz(latitude: float, longitude: float, height: float):
        """Transform lat, lon, height to x, y, z"""
        _a = 6378137
        _f = 0.0033528107
        _c = _a / (1 - _f)
        e2 = 2 * _f - _f**2
        e2_prime= e2 / (1 - _f)**2

        lat = np.deg2rad(latitude)
        lon = np.deg2rad(longitude)

        _n = _c / math.sqrt(1 + e2_prime * (math.cos(lat))**2)
        p = (_n + height) * math.cos(lat)
        x = p * math.cos(lon)
        y = p * math.sin(lon)
        z = ((1 - e2) * _n + height) * math.sin(lat)

        return np.array((x, y, z))


    @staticmethod
    def calc_orbit_pos(t, t_min, t_max, xyz, xyz_centre):
        """Calculate the in-orbit position for the time of scene centre acquisition"""
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
    def epoch_baselines(epochs, bperp, masidx, slvidx, supermaster):
        """
        Determine relative perpendicular baselines of epochs from
        interferometric baselines
        epochs: List of epoch dates
        bperp: List of interferogram absolute perpendicular baselines
        masidx: List of master indices from get_index()
        slvidx: List of slave indices from get_index()
        supermaster: epoch to set relative bperp to zero (integer)

        returns:
        epochbperp: List of epoch relative perpendicular baselines
        """

        # Count number of ifgs and epochs
        nifgs = len(bperp)
        nepochs = len(epochs)

        _LOG.info(nifgs, "interferograms and", nepochs, "epochs in the network.")
        # Initialise design matrix 'A'
        A = np.zeros((nifgs + 1, nepochs))

        # assign super-master epoch to constrain relative baselines
        A[0, supermaster] = 1
        b = np.zeros(nifgs + 1)
        b[1:nifgs + 1] = bperp

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
    def create_sb_network(dates, Bperps, Bdopp, master_ix, Btemp_max, Bperp_max, Ba, coh_thres, nmin, nmax, outfile1):

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
        rho = rho - np.eye(num_scenes);
        # boolean index of all combinations exceeding coherence threshold
        ix = rho > coh_thres
        # this index will be adapted according to min/max number of IFGs
        ix2 = ix

        # Output numbers on possible connections
        with open(outfile1, "w") as outfile:
            outfile.write('Theoretical number of possible connections for %s scenes: %d\n' % (
            num_scenes, num_scenes * (num_scenes - 1) / 2))

            # upper triangle matrix of valid connections
            tri_true = np.logical_not(np.tril(np.ones((num_scenes, num_scenes))))
            outfile.write('Number of connections with predicted coherence greater %3.1f: %d\n' % (
            coh_thres, np.sum(np.logical_and(ix, tri_true))))
            outfile.write(
                'Mean predicted coherence for these connections: %3.2f\n' % (np.mean(rho[np.logical_and(ix, tri_true)])))

            # keep connections according to nmin even if rho is below threshold
            ntest = 1
            while ntest < nmin + 0.5:
                for i in range(0, num_scenes):
                    # find scenes with no connections (1st), one connection (2nd), ...
                    if np.sum(ix2[i]) < ntest - 0.5:
                        # get index of all TRUE values in this row of ix2
                        temp_ix = np.where(np.logical_not(ix2[i]))[0]
                        # get index of scene with maximum correlation
                        rho_max_ix = np.argmax(rho[i, temp_ix])
                        # check if value is not subject to total decorrelation
                        if rho[i, rho_max_ix] > 0:
                            j = temp_ix[rho_max_ix]
                            # set value in ix2 to True for this scene
                            ix2[i, j] = True
                            ix2[j, i] = True
                        else:
                            _LOG.info("Connection between scene", i, "and scene", j, "\
                            possible (total decorrelation)")
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
            outfile.write('Number of final SBAS network connections: %d\n' % (len(epoch1)))
            outfile.write('Mean predicted coherence for these connections: %3.2f\n' % (np.mean(rho[ix])))
            outfile.close

            # plot Bperps of final connections
            Bperps_sbas = bdiff_all[ix]

            # return values
        return epoch1, epoch2, Bperps_sbas

    @staticmethod
    def plot_baseline_time_sm(epochs, Bperps, master_ix, filename):
        """
        Make a baseline time plot and save to disk
        """

        fig = plt.figure()
        ax1 = fig.add_subplot(111)
        divider = make_axes_locatable(ax1)

        # plot epochs as filled circles
        ax1.plot_date(epochs, Bperps, xdate=True, ydate=False, marker="o",
                      markersize=14, markerfacecolor="black", linestyle="None")
        # use a red circle for master date
        ax1.plot_date(epochs[master_ix], Bperps[master_ix], xdate=True,
                      ydate=False, marker="o", markersize=14,
                      markerfacecolor="darkred", linestyle="None")

        # plot epoch numbers as symbols
        labels = [i + 1 for i in range(len(Bperps))]
        for a, b, c in zip(epochs, Bperps, labels):
            ax1.text(a, b, c, color="white", ha="center", va="center", size=9,
                     weight="bold")

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
        ax1.set_xlim(date_min - timedelta(days=date_add), date_max + \
                     timedelta(days=date_add))

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
        plt.savefig(savepath, orientation="landscape", transparent=False,
                    format="png", papertype="a4")
        return

    @staticmethod
    def plot_baseline_time_sbas(epochs, Bperps, epoch1, epoch2, filename):
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
            ax1.plot_date(x, y, xdate=True, ydate=False, linestyle='-', \
                          color='r', linewidth=1.0)

        # plot epochs as filled circles
        ax1.plot_date(epochs, Bperps, xdate=True, ydate=False, marker="o",
                      markersize=14, markerfacecolor="black", linestyle="None")

        # plot epoch numbers as symbols
        labels = [i + 1 for i in range(len(Bperps))]
        for a, b, c in zip(epochs, Bperps, labels):
            ax1.text(a, b, c, color="white", ha="center", va="center", size=9,
                     weight="bold")

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
        ax1.set_xlim(date_min - timedelta(days=date_add), date_max + \
                     timedelta(days=date_add))

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
        plt.savefig(savepath, orientation="landscape", transparent=False,
                    format="png", papertype="a4")
        return

    def main(self):
        baseline_data = self.compute_perpendicular_baseline()
        for key, val in baseline_data.items():
            print(key, val)





if __name__ == "__main__":
    slc_par = ["/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T045D_F20S/SLC/20180108/20180108_VV.slc.par"]
    slc = "/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T045D_F20S/SLC/20180108/20180108_VV.slc"
    scene_list = Path("/g/data/dz56/INSAR_ARD/REPROCESSED/VV/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T45D_F19/lists/scenes.list")
    slc_par = []
    with open("/g/data/u46/users/pd1813/INSAR/INSAR_BACKSCATTER/test_backscatter_workflow/par_files.txt", "r") as fid:
        lines = fid.readlines()
        for line in lines:
            fp = Path("/g/data/dz56/INSAR_ARD/REPROCESSED/VV/INSAR_ANALYSIS/VICTORIA/S1/GAMMA/T45D_F19/SLC").joinpath(line.rstrip())
            if fp.stem.startswith("r"):
                continue
            slc_par.append(fp)

    pol = "VV"
    baseline = BaselineProcess(slc_par, pol, master_scene="20170101)
    baseline.main()
