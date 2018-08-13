#!/usr/bin/env python

"""
*******************************************************************************
* calc_baselines_functions: Functions called by 'calc_baselines.py'.          *
*                                                                             *
*  Baseline functions:                                                        *
*    read_master_info: read info on dataset from master .slc.par file         *
*    read_orbits:      read orbit information from .slc.par file              *
*    llh2xyz:          convert lat, lon, height to xyz coordinates            *
*    normalise:        normalise a data vector to a given interval            *
*    calc_orbit_pos:   calculate satellite orbit position from orbital        *
*                      state vectors                                          *
*                                                                             *
*  SBAS Network functions:                                                    *
*    perps:      list of perependicular baselines w.r.t. master               *
*    dates:      list of acquisitions dates                                   *
*    Bdopp:      list of doppler centroid frequency (fDC) differences         *
*                w.r.t. master                                                *
*    Bperp_max:  maximum Bperp (total decorrelation)                          *
*    Btemp_max:  maximum Btemp (total decorrelation)                          *
*    Ba:         azimuth bandwidth which is the critical fDC value            *
*    coh_thres:  coherence threshold for selection of combinations            *
*    nmin:       minimum number of connections per epoch                      *
*    nmax:       maximum number of connections per epoch                      *
*                                                                             *
*  Plot functions:                                                            *
*    plot_baseline_time_sm:   time vs Bperp w.r.t. a single master            *
*    plot_baseline_time_sbas: time vs Bperp + SBAS connections                *
*                                                                             *
* author: Thomas Fuhrmann @ GA March, 2018 v0.1                               * 
*         Sarah Lawrie @ GA       13/08/2018, v1.0                            *
*             -  Major update to streamline processing:                       *
*                  - use functions for variables and PBS job generation       *
*                  - add option to auto calculate multi-look values and       *
*                      master reference scene                                 *
*                  - add initial and precision baseline calculations          *
*                  - add full Sentinel-1 processing, including resizing and   *
*                     subsetting by bursts                                    *
*                  - remove GA processing option                              *
*******************************************************************************
"""


# import modules
import os
import math
import numpy as np
from datetime import datetime, date, timedelta

# enable other matplotlib libraries to work properly when running from a PBS job
import matplotlib
matplotlib.use('Agg')

from matplotlib import pyplot as plt
from matplotlib import dates as mdates
from mpl_toolkits.axes_grid import make_axes_locatable




# read information from master slc.par file
# INPUT: filename (path and name of slc.par file)
# OUTPUT: start time, end time, centre coordinates
def read_master_info(filename):
    # open file and read relevant lines
    f = open(filename)
    lines = f.readlines()
    # loop through all lines of slc.par file and find relevant records
    for line in lines:
        if "start_time:" in line:
            t_min = float(line[24:36])
        if "azimuth_lines:" in line:
            azlines = float(line[24:36])
        if "center_latitude:" in line:
            lat = float(line[23:36])
        if "center_longitude:" in line:
            lon = float(line[23:36])
        if "prf:" in line:
            prf = float(line[24:37])
        # the following is needed for calculation of critical baselines:
        if "center_range_slc:" in line:
            r1 = float(line[24:37])
        if "incidence_angle:" in line:
            inc = float(line[24:37])
        if "radar_frequency:" in line:
            f = float(line[24:37])
        if "chirp_bandwidth:" in line:
            Br = float(line[24:37])
        if "azimuth_proc_bandwidth:" in line:
            Ba = float(line[24:37])

    t_max = t_min + (azlines-1)/prf;

    # return values
    return t_min, t_max, lat, lon, r1, inc, f, Br, Ba



# read orbit information from slc.par file
# INPUT: filename (path and name of slc.par file)
# OUTPUT: time vector, xyz coordinates + first derivative for each time step
def read_orbits(filename):
    # open file and read relevant lines
    f = open(filename)
    lines = f.readlines()
    # counters for state vector position and velocity
    counter = 0
    # loop through all lines of slc.par file and find relevant records
    for line in lines:
        if "doppler_polynomial:" in line:
            temp = line[23:]
            temp1 = temp.split()
            temp2 = temp1[0]
            fDC = float(temp2)
        if "number_of_state_vectors:" in line:
            nsets = int(line[28:45])
            # set up matrix for xyz coordinates (used later)
            xyz = [0] * nsets
            for i in range(nsets):
                xyz[i] = [0] * 3
            # xyz is a matrix of size nsets x 3
        if "time_of_first_state_vector" in line:
            t1 = float(line[28:45])
        if "state_vector_interval" in line:
            interval = float(line[28:45])
        # xyz coordinates
        if "state_vector_position" in line:
            xyz[counter][0] = float(line[25:40])
            xyz[counter][1] = float(line[40:56])
            xyz[counter][2] = float(line[56:72])
            counter = counter + 1

    # set up time vector
    t = [0] * nsets
    t[0] = t1
    i = 1
    for num in range(i, nsets):
        t[i] = t[i-1] + interval
        i = i + 1

    # return values
    return fDC, t, xyz



# Transfrom lat, lon, height to x, y, z
def llh2xyz(lat, lon, h):
    # Constants
    rho = 180/math.pi
    a=6378137
    f=0.0033528107
    c = a/(1-f)
    e2 = 2*f-f**2
    ePrime2 = e2/(1-f)**2
    # calculations
    lat = lat/rho
    lon = lon/rho
    V = math.sqrt(1+ePrime2*(math.cos(lat))**2)
    N = c/V
    M = N/V**2
    p = (N+h)*math.cos(lat)
    x = p*math.cos(lon)
    y = p*math.sin(lon)
    z = ((1-e2)*N+h)*math.sin(lat)
    xyz = np.array((x, y, z))

    # return values as a xyz vector
    return xyz



# Normalises data from a given interval [a;b] to [-2;2]
def normalise(X,a,b):
    # initialise loop (return values will be same length as X)
    i = 0
    Y = X
    # perform normaisation for each value in X
    for x in X:
        Y[i] = (x-a)/(b-a)*4-2
        i = i+1

    # return values
    return Y



# Calculate the in-orbit position for the time of scene centre acquisition
def calc_orbit_pos(t, t_min, t_max, xyz, xyz_centre):
    # normalise time vector to the interval [-2 2]
    n = len(t)
    t = normalise(t, t_min, t_max)
    deg = min(5,n-1)
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
    while abs(dt) > 10**(-10):
        # Position
        xP = poly_x(tm)
        yP = poly_y(tm)
        zP = poly_z(tm)
        # Velocity
        xV = poly_x_der(tm)
        yV = poly_y_der(tm)
        zV = poly_z_der(tm)
        temp1 = (xP-x)*xV + (yP-y)*yV + (zP-z)*zV
        temp2 = xV*xV + yV*yV + zV*zV
        dt = -temp1 / temp2
        tm = tm + dt
    # save position vector as numpy array
    P = np.array((xP, yP, zP))
    return P


# Imported function from Matt Gartwhaite's baseline.py script
def epoch_baselines(epochs, bperp, masidx, slvidx, supermaster):
    '''
    Determine relative perpendicular baselines of epochs from
    interferometric baselines

    INPUT:
    epochs    list of epoch dates
    bperp    list of interferogram absolute perpendicular baselines
    masidx    list of master indices from get_index()
    slvidx    list of slave indices from get_index()
    supermaster    epoch to set relative bperp to zero (integer)

    OUTPUT:
    epochbperp    list of epoch relative perpendicular baselines
    '''

    # Count number of ifgs and epochs
    nifgs = len(bperp)
    nepochs = len(epochs)
    print(nifgs, "interferograms and", nepochs, "epochs in the network.")

    # Initialise design matrix 'A'
    A = np.zeros((nifgs+1,nepochs))

    # assign super-master epoch to constrain relative baselines
    A[0,supermaster] = 1
    b = np.zeros(nifgs+1)
    b[1:nifgs+1] = bperp

    # Construct design matrix
    for i in range(nifgs):
        imas = masidx[i]
        islv = slvidx[i]
        A[i+1,imas] = -1
        A[i+1,islv] = 1

    # Do overdetermined linear inversion x=A\b
    x = np.linalg.lstsq(A,b)
    return x[:][0]



def create_sb_network(dates, Bperps, Bdopp, master_ix, Btemp_max, \
    Bperp_max, Ba, coh_thres, nmin, nmax, outfile1):


    # calculate Bperp differences (bdiff) for all possible IFG combinations
    num_scenes = len(Bperps)
    X, Y = np.meshgrid(np.array(Bperps), np.array(Bperps))
    bdiff_all = X - Y
    bdiff = abs(bdiff_all)
    # calculate Bdopp differences
    X, Y = np.meshgrid(np.array(Bdopp), np.array(Bdopp))
    doppdiff = abs(X-Y)
    # calculate Btemp differences in days (ddiff) for all possible IFG comb.
    dates_diff_days = [0] * num_scenes
    i = 0
    # loop needed to convert date objects to integer dates (eg wrt master)
    for line in dates:
        dates_diff_days[i] = (line - dates[master_ix]).days
        i = i + 1
    X, Y = np.meshgrid(dates_diff_days, dates_diff_days)
    ddiff = abs(X-Y)


    # correlation matrix rho from linear decorrelation model (Kampes 2005)
    rho = (1 - bdiff/Bperp_max) * (1 - ddiff/Btemp_max) * (1 - doppdiff/Ba)
    rho[bdiff > Bperp_max] = 0
    rho[ddiff > Btemp_max] = 0
    rho[doppdiff > Ba] = 0
    rho = rho - np.eye(num_scenes);
    # boolean index of all combinations exceeding coherence threshold
    ix = rho > coh_thres
    # this index will be adapted according to min/max number of IFGs
    ix2 = ix


    # Output numbers on possible connections
    outfile = open(outfile1, "w")
    outfile.write('Theoretical number of possible connections for %s scenes: %d\n' % (num_scenes, num_scenes * (num_scenes - 1) / 2))

    # upper triangle matrix of valid connections
    tri_true = np.logical_not(np.tril(np.ones((num_scenes, num_scenes))))
    outfile.write('Number of connections with predicted coherence greater %3.1f: %d\n' % (coh_thres, np.sum(np.logical_and(ix, tri_true))))
    outfile.write('Mean predicted coherence for these connections: %3.2f\n'% (np.mean(rho[np.logical_and(ix, tri_true)])))


    # keep connections according to nmin even if rho is below threshold
    ntest = 1
    while ntest < nmin+0.5:
        for i in range(0, num_scenes):
            # find scenes with no connections (1st), one connection (2nd), ...
            if np.sum(ix2[i]) < ntest-0.5:
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
                    print("Connection between scene", i, "and scene", j, "\
                    possible (total decorrelation)")
        ntest = ntest + 1


    # delete unwanted connections (greater nmax, low coherence)
    # check if there is any epoch with more than nmax connections
    while any(ix2.sum(axis=0) > nmax + 0.5):
        # loop trough all epochs, only one connection is deleted per epoch
        for i in range(0, num_scenes):
            # find scenes with more than nmax connections
            if np.sum(ix2[i]) > nmax+0.5:
                temp_ix = []
                cand = []
                rho_cand = []
                # get index of all TRUE values in this row of ix2
                temp_ix = np.where(ix2[i])[0]
                num_connect = len(temp_ix)
                for k in range(0, num_connect):
                    # only consider neighbours with more than nmin connect.
                    if np.sum(ix2[temp_ix[k]]) > nmin+0.5:
                        cand.append(temp_ix[k])
                rho_cand = rho[i, cand]
                # get index of scene with minimum correlation
                rho_min_ix = np.argmin(rho_cand)
                # set value in ix2 to False for rho_min_ix
                j = cand[rho_min_ix]
                ix2[i, j] = False
                ix2[j, i] = False


    ix = np.logical_and(ix2, tri_true)
    # final interferogram connections (already sorted ascending for x)
    [epoch1, epoch2] = np.where(ix)
    outfile.write('Number of final SBAS network connections: %d\n' % (len(epoch1)))
    outfile.write('Mean predicted coherence for these connections: %3.2f\n' % (np.mean(rho[ix])))
    outfile.close

    # plot Bperps of final connections
    Bperps_sbas = bdiff_all[ix]

    # return values
    return epoch1, epoch2, Bperps_sbas




# adapated from baseline.py (@author Matt Garthwaite, 31/03/2016)
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
    labels = [i+1 for i in range(len(Bperps))]
    for a, b, c in zip(epochs, Bperps, labels):
        ax1.text(a, b, c, color="white", ha="center", va="center", size=9,
                 weight="bold")


    #format the time axis ticks
    years    = mdates.YearLocator()   # every year
    months   = mdates.MonthLocator()  # every month
    yearsFmt = mdates.DateFormatter("%Y-%m-%d")
    ax1.xaxis.set_major_locator(years)
    ax1.xaxis.set_major_formatter(yearsFmt)
    ax1.xaxis.set_minor_locator(months)

    #set the time axis range
    date_min = epochs.min()
    date_max = epochs.max()
    date_range = date_max - date_min
    date_add = date_range.days/15
    ax1.set_xlim(date_min - timedelta(days=date_add), date_max + \
                 timedelta(days=date_add))

    # set the Bperp axis range
    Bperp_min = min(Bperps)
    Bperp_max = max(Bperps)
    Bperp_range = Bperp_max - Bperp_min
    ax1.set_ylim(Bperp_min - Bperp_range/15, Bperp_max + Bperp_range/15)

    #set axis titles
    ax1.set_xlabel("Date (YYYY-MM-DD)")
    ax1.set_ylabel("Perpendicular Baseline (m)")
    ax1.grid(True)

    #rotates and right aligns the date labels
    fig.autofmt_xdate()

    # Save plot to PNG file
    savepath = filename+".png"
    plt.savefig(savepath, orientation="landscape", transparent=False,
                format="png", papertype="a4")
    return



# adapated from baseline.py (@author Matt Garthwaite, 31/03/2016)
def plot_baseline_time_sbas(epochs, Bperps, epoch1, epoch2, filename):
    """
    Make a baseline time plot including IFG connections and save to disk
    """

    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    divider = make_axes_locatable(ax1)

    # plot interferograms as lines
    for n, m in zip(epoch1, epoch2):
        #print n, m
        x = [epochs[n], epochs[m]]
        y = [Bperps[n], Bperps[m]]
        #  baselines[x]
        ax1.plot_date(x, y, xdate=True, ydate=False, linestyle='-', \
        color = 'r', linewidth=1.0)

    # plot epochs as filled circles
    ax1.plot_date(epochs, Bperps, xdate=True, ydate=False, marker="o",
                  markersize=14, markerfacecolor="black", linestyle="None")

    # plot epoch numbers as symbols
    labels = [i+1 for i in range(len(Bperps))]
    for a, b, c in zip(epochs, Bperps, labels):
        ax1.text(a, b, c, color="white", ha="center", va="center", size=9,
                 weight="bold")

    #format the time axis ticks
    years    = mdates.YearLocator()   # every year
    months   = mdates.MonthLocator()  # every month
    yearsFmt = mdates.DateFormatter("%Y-%m-%d")
    ax1.xaxis.set_major_locator(years)
    ax1.xaxis.set_major_formatter(yearsFmt)
    ax1.xaxis.set_minor_locator(months)

    #set the time axis range
    date_min = epochs.min()
    date_max = epochs.max()
    date_range = date_max - date_min
    date_add = date_range.days/15
    ax1.set_xlim(date_min - timedelta(days=date_add), date_max + \
                 timedelta(days=date_add))

    # set the Bperp axis range
    Bperp_min = min(Bperps)
    Bperp_max = max(Bperps)
    Bperp_range = Bperp_max - Bperp_min
    ax1.set_ylim(Bperp_min - Bperp_range/15, Bperp_max + Bperp_range/15)

    #set axis titles
    ax1.set_xlabel("Date (YYYY-MM-DD)")
    ax1.set_ylabel("Perpendicular Baseline (m)")
    ax1.grid(True)

    #rotates and right aligns the date labels
    fig.autofmt_xdate()

    # Save plot to PNG file
    savepath = filename+".png"
    plt.savefig(savepath, orientation="landscape", transparent=False,
                format="png", papertype="a4")
    return

