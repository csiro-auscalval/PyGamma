"""
Main script
- Reads precision baselines from all GAMMA-generated IFGs
- Calculates perpendicular baselines (Bperp) from TCN info
- Compares precision baselines to initial baselines calculated from
  orbital state vectors in python script create_baseline_plot.py
- Creates baseline plot, x-axis: Btemp, y-axis: Bperp

INPUT:
txtfile: TxxxX.proc (read master date)
txtfile: r*.mli.par for master date (calculate look angle for scene centre)
txtfiles: *base.par files located in ../GAMMA/TxxxX/INT/YYYYMMDD-YYYYMMD/

OUTPUT:
text file comparing initial/final Bperps ./TxxxX/baseline_comp_output.txt
precision baseline plot with valid SBAS connections:
 ./TxxxX/prec_baseline_plot_sbas_network.png

@author: Thomas Fuhrmann @ GA April, 2018

usage:
currently this script and the libraries scritps containing subroutines:
 - create_baseline_func_lib
 - create_baseline_plot_lib
have to be placed and executed in the ../GAMMA/ directory.
Relative paths are used (likely to be changed later).
The scripts shall be added to the gamma_insar repo later.

Load python3 module on NCI: module load python3
Load corresponding matplotlib: module load python3/3.4.3-matplotlib
then execute, e.g.: python3 create_baseline_plot.py T380A
for automated processing use: python3 create_prec_baseline_plot.py TxxxX
"""


# import modules
import sys
import os
import os.path
import math
from datetime import datetime, date
import numpy as np
import operator
import create_baseline_func_lib as cbf
import create_baseline_plot_lib as cbp



# Welome
print()
print("########################")
print("# Create baseline plot #")
print("########################")
print()

# check number of arguments (at least track number has to be given)
if len(sys.argv) < 2:
    print("Please set Track name as argument, e.g. T380A!")
    sys.exit()


# Read master date from TxxxX.proc file
trackdir=sys.argv[1]
filename = trackdir + ".proc"
if os.path.isfile(filename) and os.access(filename, os.R_OK):
    f = open(filename,'r')
    lines = f.readlines()
    for line in lines:
        if "Master_scene=" in line:
            # last character in line is \n
            line = line.strip("\n")
            line = line.strip("\t")
            master = line[-8:]
        if "Polarisation=" in line:
            # last character in line is \n
            line = line.strip("\n")
            line = line.strip("\t")
            polar = line[-2:]
        if "ifm_multi_look=" in line:
            # last character in line is \n
            line = line.strip("\n")
            line = line.strip("\t")
            ifm_ml = line.split("=",1)[1]
else:
    print("ERROR: Can't read file", filename)
    sys.exit()


# Read master r*mli.par file and calculate look angle for centre pixel
print("Reading Master mli.par file for Track:", trackdir)
filename = "./" + trackdir + "/SLC/" + master + "/r" + master + "_" + \
           polar + "_" + ifm_ml + "rlks.mli.par"
# open file and read relevant lines
f = open(filename)
lines = f.readlines()
# loop through all lines of slc.par file and find relevant records
for line in lines:
    if "center_range_slc:" in line:
        crg = float(line[24:37])
    if "sar_to_earth_center:" in line:
        se = float(line[31:45])
    if "earth_radius_below_sensor:" in line:
        re = float(line[31:45])
# look angle resulting from law cosines for general triangles
la = math.acos((se**2 + crg**2 - re**2)/(2 * se * crg))


print("Reading ifms.list file for Track:", trackdir)
filename = "./" + trackdir + "/lists/ifms.list"
if os.path.isfile(filename) and os.access(filename, os.R_OK):
    print("File", filename, "exists and is readable")
    f = open(filename)
    dates = f.readlines()
    dates[:] = [line.rstrip("\n") for line in dates]
    epoch1 = list(dates)
    epoch1[:] = [line.split(",",1)[0] for line in epoch1]
    epoch2 = list(dates)
    epoch2[:] = [line.split(",",1)[1] for line in epoch2]
    num_ifgs = len(dates)
else:
    print("ERROR: Can't read file", filename)
    sys.exit()
print()


# Read all base.par files and calculate Bperp from TCN baselines
print("Calculating Bperp from precision baseline (TCN) in *.base.par")
i = 0
Bperp_prec = [0] * num_ifgs
# loop through all IFGs
for epochA, epochB in zip(epoch1, epoch2):
    filename = "./" + trackdir + "/INT/" + epochA + "-" + epochB + "/" + \
               epochA + "-" + epochB + "_" + polar + "_" + ifm_ml + \
               "rlks_base.par"
    if os.path.isfile(filename) and os.access(filename, os.R_OK):
        f = open(filename)
        lines = f.readlines()
        # loop through all lines of slc.par file and find relevant records
        for line in lines:
            if "precision_baseline(TCN):" in line:
                baseC = float(line[43:58])
                baseN = float(line[60:75])
                Bperp_prec[i] = baseC * math.cos(la) - baseN * math.sin(la)
        # counter for Bperp
    else:
        print("ERROR: Can't read file " + filename + \
              ". IFG does not exist or is corrupt.")
        Bperp_prec[i] = "nan"
    i = i + 1
print()


# read initial baseline estimates (based on orbits only) and compare
filename = "./" + trackdir + "/baseline_plot_output.txt"
if os.path.isfile(filename) and os.access(filename, os.R_OK):
    f = open(filename)
    # file has two headerlines
    lines = f.readlines()[2:]
    lines[:] = [line.rstrip("\n") for line in lines]
    epoch1_init = list(lines)
    epoch1_init[:] = [line.split()[0] for line in lines]
    epoch2_init = list(lines)
    epoch2_init[:] = [line.split()[1] for line in lines]
    Bperp_init = list(lines)
    Bperp_init[:] = [float(line.split()[2]) for line in lines]
    num_ifgs_init = len(lines)
    epoch1_init[:] = [datetime.strptime(line, "%Y-%m-%d") for line in \
                      epoch1_init]
    epoch2_init[:] = [datetime.strptime(line, "%Y-%m-%d") for line in \
                      epoch2_init]
    # combined date string of epoch1 and epoch2
    epoch12_init = [" "] * num_ifgs_init
    i = 0
    for line in epoch12_init:
        epoch12_init[i] = datetime.strftime(epoch1_init[i], "%Y%m%d") + \
                    "," + datetime.strftime(epoch2_init[i], "%Y%m%d")
        i = i + 1


    # compare epoch connections to find identical epochs and
    # save dates and Bperps of connection to ./TxxxX/baseline_comparison.txt
    filename = "./" + trackdir + "/baseline_comparison.txt"
    print("Comparing Bperps and saving result to file " + filename + "...")
    outfile = open(filename, "w")
    outfile.write("Date1 [yyyy-mm-dd]   Date2 [yyyy-mm-dd]   init. Bperp \
[m]   final Bperp [m]   Difference [m]\n")
    outfile.write("--------------------------------------------------------\
------------------------------------\n")
    counter = 0
    diff_sum_abs = 0
    diff_min = 0
    diff_max = 0
    # loop through both lists with inital and final epoch connections
    for i in range(num_ifgs_init):
        for j in range(num_ifgs):
            if epoch12_init[i] == dates[j] and not(Bperp_prec[j] == "nan"):
                diff = Bperp_init[i] - Bperp_prec[j]
                # calculate some statistics on Bperp differences
                diff_sum_abs = diff_sum_abs + abs(diff)
                if diff < diff_min:
                    diff_min = diff
                if diff > diff_max:
                    diff_max = diff
                # write Bperps to file
                outfile.write("%17s    %17s         %9.1f         %9.1f    \
    %9.1f\n" % (epoch1_init[i].strftime("%Y-%m-%d"), \
epoch2_init[i].strftime("%Y-%m-%d"), Bperp_init[i], Bperp_prec[j], diff))
                counter = counter + 1
    outfile.close
    print(str(counter) + " identical epoch connections written to " + \
    filename + ".")
    print()
    print("Mean absolute difference: %9.1f" % (diff_sum_abs/counter))
    print("Minimum difference: %9.1f" % diff_min)
    print("Maximum difference: %9.1f" % diff_max)
else:
    print("Cannot compare precise Bperps to initial Bperps. File", \
    filename, "does not exist.")



# retrieve epoch inidices
# list of all epochs
epochs = list(set(epoch1 + epoch2))
epochs.sort()
# get indices of epoch connections
epo1 = np.array(epoch1)
epo2 = np.array(epoch2)
epo1_ix = epo1
epo2_ix = epo2
counter = 0
for epo in epochs:
    temp = np.where(epo1 == epo)[0]
    epo1_ix[temp] = counter
    temp = np.where(epo2 == epo)[0]
    epo2_ix[temp] = counter
    counter = counter + 1
# convert numpy array to list of integer indices
epoch1_ix = [ int(epo) for epo in epo1_ix ]
epoch2_ix = [ int(epo) for epo in epo2_ix ]


# delete connections which don't exist (Bperp_prec is set to "nan")
del_idx = np.where(np.array(Bperp_prec) == "nan")[0]
Bperp_prec = [e for i, e in enumerate(Bperp_prec) if i not in del_idx]
epoch1_ix = [e for i, e in enumerate(epoch1_ix) if i not in del_idx]
epoch2_ix = [e for i, e in enumerate(epoch2_ix) if i not in del_idx]
# get the master index to be used as the zero baseline level
master_ix = epochs.index(master)
# convert to datetime object (needed for epoch_baselines and for plotting)
epochs[:] = [datetime.strptime(epo, "%Y%m%d") for epo in epochs]
# re-calculate Bprep_prec w.r.t. SM constellation
epochbperp = cbf.epoch_baselines(epochs,Bperp_prec,epoch1_ix,epoch2_ix, \
                                 master_ix)


# plot scene connections using precision baselines
print("Creating baseline plot...")
filename = "./" + trackdir + "/baseline_plot_sbas_network_final"
cbp.plot_baseline_time_sbas(np.array(epochs), epochbperp, epoch1_ix, \
                            epoch2_ix, filename)
print()

