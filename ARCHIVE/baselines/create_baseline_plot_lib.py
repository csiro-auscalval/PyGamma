"""
Library of plotting tools for creating time x Bperp plots
- plot_baseline_time_sm: time vs Bperp w.r.t. a single master
- plot_baseline_time_sbas: time vs Bperp + SBAS connections

@author Thomas Fuhrmann @ GA March, 2018
"""


# import modules
from datetime import datetime, date, timedelta
from matplotlib import pyplot as plt
from matplotlib import dates as mdates
from mpl_toolkits.axes_grid import make_axes_locatable


#############
# Functions #
#############


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
    print("Writing plot to", savepath)
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
    print("Writing plot to", savepath)
    plt.savefig(savepath, orientation="landscape", transparent=False,
                format="png", papertype="a4")
    return
