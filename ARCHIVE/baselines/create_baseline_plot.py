"""
Main script
- Asks for master scene (or selects temporal centre as master)
- Calculates perpendicular baselines (Bperp) of all slaves w.r.t. master
- Creates baseline plot, x-axis: Btemp, y-axis: Bperp
- Creates an SBAS network based on coherence and min/max number of connect.
- Saves slave epochs to file slaves.list
- Saves epoch connection to file ifms.list

INPUT:
txtfile: scenes.list located in ../GAMMA/TxxxX/lists/
txtfiles: *.slc.par files located in ../GAMMA/TxxxX/SLC/YYYYMMDD/

OUTPUT:
baseline plot for selected master: ./TxxxX/baseline_plot_masterYYYYMMDD.png
baseline plot with SBAS connections: ./TxxxX/baseline_plot_sbas_network.png
text file with SBAS epochs and Bperps ./TxxxX/baseline_plot_output.txt
master date is written to file TxxxX.proc
List of slaves w.r.t. selected master: ./TxxxX/lists/slaves.list
List of interferograms to be generated: ./TxxxX/lists/ifms.list

@author: Thomas Fuhrmann @ GA March, 2018
based on the STAMPS_BLplot.m Matlab routines developed by
H. Baehr, A. Schenk, T. Fuhrmann @ KIT, Germany, 2010-2017

April, 2018:
 - changed script to allow for median calculation of relative Bperps from
   iteration through all possible masters
 - SLC data is read only once to improve runtime and stored into a list of
   SLC_data objects

usage:
currently this script and the libraries scripts containing subroutines:
 - create_baseline_func_lib
 - create_baseline_plot_lib
 - create_sbas_network
have to be placed and executed in the ../GAMMA/ directory.
Relative paths are used (likely to be changed later).
The scripts shall be added to the gamma_insar repo later.

Load python3 module on NCI: module load python3
Load corresponding matplotlib: module load python3/3.4.3-matplotlib
then execute, e.g.: python3 create_baseline_plot.py T380A
for automated processing use: python3 create_baseline_plot.py TxxxX 1
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
import create_sbas_network as csn


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


# if 1 is given as second argument, automated processing is performed
if len(sys.argv) > 2:
   auto = sys.argv[2]
   auto = int(auto)
   if auto == 1:
       print("Automated processing without user input selected.")
   else:
       print("Set 2nd argument to 1, if automated processing is desired.")
else:
   auto = 0
   print("Processing with user interaction selected.")


# Read scenes.list and convert date strings to datetime objects
trackdir=sys.argv[1]
print("Reading scenes.list file for Track:", trackdir)
filename = "./" + trackdir + "/lists/scenes.list"
if os.path.isfile(filename) and os.access(filename, os.R_OK):
    print("File", filename, "exists and is readable")
    f = open(filename)
    dates = f.readlines()
    dates[:] = [line.rstrip("\n") for line in dates]
    # convert string list to datetime objects
    dates[:] = [datetime.strptime(line, "%Y%m%d") for line in dates]
    num_scenes = len(dates)
else:
    print("ERROR: Can't read file", filename)
    sys.exit()
print()
print("Generating baseline plot for", num_scenes, "scenes:")
print()
# Output epochs and Bperps as a list
print("Epoch   Date [yyyy-mm-dd]")
print("-------------------------")
epoch = 1
for line in dates:
    print("%5d  ---->  %10s" % (epoch, line.strftime("%Y-%m-%d")))
    epoch = epoch + 1
print()


# Get the central point in time (average of first and last date)
date_centre = min(dates) + (max(dates) - min(dates))/2
dates_diff = [0] * (num_scenes)
i = 0
for line in dates:
    temp = dates[i] - date_centre
    dates_diff[i] = abs(temp.days)
    i = i + 1
index_min = np.argmin(dates_diff)


# Initial master selection for plot
master_initial = dates[index_min]
print("Initial master is:", master_initial.strftime("%Y-%m-%d"), \
      "(central location in time)")
if auto == 1:
    master = master_initial
else:
    """
    # old code
    message = "Use initial master (y) or type in your master date \
(e.g.: 20130901): "
    """
    # new code
    message = "Use initial master (y) or type in the epoch number of your \
master choice: "
    while True:
        quest = input(message)
        if quest == "y":
            master = master_initial
            break
        else:
            """
            # old code: use date as input
            if quest.isdigit() and len(quest)==8:
                master = datetime.strptime(quest, "%Y%m%d")
                if master in dates:
                    break
                else:
                    print("Date", master.strftime("%Y%m%d"), \
                    "is not included in the scene list.")
            else:
                print("Not a valid date, please use yyyymmdd format,", \
                "e.g. 20130901")
            """
            # new code: use epoch number
            if quest.isdigit() and int(quest)>0 and int(quest)<=num_scenes:
                master = dates[int(quest)-1]
                break
            else:
                print("Not a valid epoch, please use an integer number", \
                "between 1 and ", num_scenes)
print("Chosen master is:", master.strftime("%Y-%m-%d"))


# read and write to TxxxX.proc file
filename = trackdir + ".proc"
filename_backup = filename + "_backup"
if os.path.isfile(filename) and os.access(filename, os.R_OK):
    cmd_string = "cp " + filename + " " + filename_backup
    os.system(cmd_string)
    f = open(filename,'r')
    filename_temp = filename + "_temp"
    fout = open(filename_temp,'w')
    lines = f.readlines()
    for line in lines:
        if "Master_scene=" in line:
            # change text for selected master
            line = ("Master_scene=" + master.strftime("%Y%m%d") + "\n")
        # write into TxxxX.proc_temp
        fout.write(line)
        # get polarisation, needed for file name of slc.par
        if "Polarisation=" in line:
            # last character in line is \n
            line = line.strip("\n")
            line = line.strip("\t")
            polar = line[-2:]
    f.close
    # overwrite original TxxxX.proc file with new version (_temp)
    cmd_string = "mv -f " + filename_temp + " " + filename
    os.system(cmd_string)
else:
    print("ERROR: Can't read file", filename)
    sys.exit()
print("Master date has been written to " + filename + ".")
print()


# then perform the loop over all scenes
class SLC_data(object):
    # The class "constructor" - It's actually an initializer
    def __init__(self, fDC=0, t_min=0, t_max=0, lat=0, lon=0, r1=0, inc=0, \
                 f=0, Br=0, Ba=0, t=[], xyz=[[],[]]):
        self.fDC = fDC
        self.t_min = t_min
        self.t_max = t_max
        self.lat = lat
        self.lon = lon
        self.r1 = r1
        self.inc = inc
        self.f = f
        self.Br = Br
        self.Ba = Ba
        self.t = t
        self.xyz = xyz # list of variable length

def make_slc_data(fDC, t_min, t_max, lat, lon, r1, inc, f, Br, Ba, t, xyz):
    slc_data = SLC_data(fDC, t_min, t_max, lat, lon, r1, inc, f, Br, Ba, \
                        t, xyz)
    return slc_data


# read all slc.par files and save relevant parameters in the object SLC_data
print("Reading .slc.par files for all scenes...")
scn_idx = 0;
# initialise slc_data object
init = SLC_data()
# list of slc_data objects
slc_dl = [init for i in range(num_scenes)]
for scene in dates:
    filename = "./" + trackdir + "/SLC/" + scene.strftime("%Y%m%d") + \
               "/" + scene.strftime("%Y%m%d") + "_" + polar + ".slc.par"
    if os.path.isfile(filename) and os.access(filename, os.R_OK):
        fDC, t, xyz = cbf.read_orbits(filename)
        t_min, t_max, lat, lon, r1, inc, f, Br, Ba = \
        cbf.read_master_info(filename)
    else:
        print("ERROR: Can't read file", filename)
        sys.exit()
        print()
    slc_dl[scn_idx] = make_slc_data(fDC, t_min, t_max, lat, lon, r1, inc, \
                                    f, Br, Ba, t, xyz)
    scn_idx = scn_idx + 1


# read orbit data an calculate Bperp for all masters
print("Calculating Bperp for all possible master-slave combinations...")
# selected master is saved for later usage
master_sel = master
relBperps = np.zeros((num_scenes, num_scenes-1))
count_mas = 0
# repeat baseline calculation
for master in dates:
    mas_ix = dates.index(master)
    # setup the slaves list
    slaves = list(dates)
    slaves.remove(master)
    # transform scene centre from lat/lon to xyz vector
    P = cbf.llh2xyz(slc_dl[mas_ix].lat, slc_dl[mas_ix].lon, 0)
    # calculate satellite position  for master scene
    t = list(slc_dl[mas_ix].t)
    M = cbf.calc_orbit_pos(t, slc_dl[mas_ix].t_min, slc_dl[mas_ix].t_max, \
                           slc_dl[mas_ix].xyz, P)
    # perpendicular baselines of slaves w.r.t master
    Bperps = [0] * (num_scenes-1)
    # loop through all slaves and calculate Bperp and Bdopp
    counter = 0
    for slave in slaves:
        sla_ix = dates.index(slave)
        # calculate satellite position  for slave scene
        t = list(slc_dl[sla_ix].t)
        S = cbf.calc_orbit_pos(t, slc_dl[mas_ix].t_min, \
                               slc_dl[mas_ix].t_max, slc_dl[sla_ix].xyz, P)
        R1 = M-P
        R2 = S-P
        B = np.linalg.norm(M-S)
        Bpar = np.linalg.norm(R1) - np.linalg.norm(R2)
        Bperp = math.sqrt(B**2 - Bpar**2)
        # sign of Bperp
        temp1 = np.dot(M, R1)
        temp2 = np.linalg.norm(M) * np.linalg.norm(R1)
        theta1 = math.acos(temp1/temp2)
        temp1 = np.dot(M, R2)
        temp2 = np.linalg.norm(M) * np.linalg.norm(R2)
        theta2 = math.acos(temp1/temp2)
        if theta1 < theta2:
            Bperp = -Bperp
        Bperps[counter] = Bperp
        counter = counter+1
    # add master to Bperp list (Bperp=0)
    Bperps.insert(mas_ix, 0.0)
    count_rel = -1
    for Bperp in Bperps:
        if count_rel > -1:
            relBperps[count_mas, count_rel] = Bperp - Bperp_temp
        Bperp_temp = Bperp
        count_rel = count_rel + 1
    count_mas = count_mas + 1


# use median values of relative baselines
relBperps_median = np.median(relBperps, axis=0)
# re-calculate baselines w.r.t. selected master
master = master_sel
master_ix = dates.index(master)
sum_rel = 0
Bperps[master_ix] = 0.0
for i in range(master_ix-1, -1, -1):
    sum_rel = sum_rel - relBperps_median[i]
    Bperps[i] = sum_rel
sum_rel = 0
for i in range(master_ix+1, num_scenes):
    sum_rel = sum_rel + relBperps_median[i-1]
    Bperps[i] = sum_rel
print()


# setup the slaves list and calculate Doppler Centroid differences
slaves = list(dates)
slaves.remove(master)
filename = "./" + trackdir + "/lists/slaves.list"
filename_backup = "./" + trackdir + "/lists/slaves_backup.list"
print("Saving epochs of slaves to file " + filename + "...")
# check if slaves.list file exists and has already be renamed
if os.path.isfile(filename):
    if os.path.isfile(filename_backup):
        print("Backup already exists and will not be overwritten.")
    else:
        # save existing slaves.list to slaves_backup.list
        cmd_string = "cp " + filename + " " + filename_backup
        os.system(cmd_string)
        print("Existing slaves.list saved to slaves_backup.list.")
# save dates of slaves to ./TxxxX/lists/slaves.list
outfile = open(filename, "w")
counter = 0
# doppler centroid frequency (fDC) differences of slaves w.r.t. master
Bdopp = [0] * (num_scenes-1)
for slave in slaves:
    # write slave.list
    outfile.write(slave.strftime("%Y%m%d") + "\n")
    # calc fDC
    slave_ix = dates.index(slave)
    Bdopp[counter] = slc_dl[slave_ix].fDC - slc_dl[master_ix].fDC
    counter = counter+1
Bdopp.insert(master_ix, 0.0)
outfile.close
print(str(num_scenes-1) + " slave epochs written to " + filename + ".")
print()


# plot dates and Bperps for selected master
print("Creating baseline plot for selected master...")
filename = "./" + trackdir + "/baseline_plot_master" + \
master.strftime("%Y%m%d")
cbp.plot_baseline_time_sm(np.array(dates), Bperps, master_ix, filename)
print()


# Output epochs, Bperps and Bdopp as a list
print("Epoch   Date [yyyy-mm-dd]   Bperp [m]   DC diff. [Hz]")
print("-----------------------------------------------------")
epoch = 1
for line, Bperp, dopp in zip(dates, Bperps, Bdopp):
    print("%5d   %16s   %9.1f   %13.1f" % (epoch, \
    line.strftime("%Y-%m-%d"), Bperp, dopp))
    epoch = epoch + 1
print()


# perform SBAS network processing?
if auto != 1:
    message = "Do you wish to continue and generate an SBAS \
network? (y/n): "
    while True:
        quest = input(message)
        if quest == "y":
            break
        elif quest == "n":
            # save dates of SM connections to ./TxxxX/lists/ifms.list
            filename = "./" + trackdir + "/lists/ifms.list"
            filename_backup = "./" + trackdir + "/lists/ifms_backup.list"
            print()
            print("Saving Single-Master epoch connections to file " + \
                  filename + "...")
            # check if slaves.list file exists and has already be renamed
            if os.path.isfile(filename):
                if os.path.isfile(filename_backup):
                    print("Backup already exists and will not be " + \
                          "overwritten.")
                else:
                    # save existing slaves.list to slaves_backup.list
                    cmd_string = "cp " + filename + " " + filename_backup
                    os.system(cmd_string)
                    print("Existing ifms.list saved to ifms_backup.list.")
            outfile = open(filename, "w")
            for slave in slaves:
                outfile.write(master.strftime("%Y%m%d") + "," + \
                              slave.strftime("%Y%m%d") + "\n")
            outfile.close
            print(str(num_scenes-1) + " epoch connections written to " + \
                  filename + ".")
            print()
            print("Program is now closing. Thanks for using!")
            print()
            sys.exit()
        else:
            print("Wrong input, to continue use y, to quit use n")
print("Starting coherence-based SBAS network generation...")
print()


# extract further information from SLC_data object for selected master
Br = slc_dl[master_ix].Br
f = slc_dl[master_ix].f
r1 = slc_dl[master_ix].r1
inc = slc_dl[master_ix].inc
# critical Doppler difference is azimuth bandwidth Ba, see Eq. 4.4.13
# in Hanssen (2001)
Ba = slc_dl[master_ix].Ba


# calculate critical baseline Bperp_max from Eq. 4.4.11 in Hanssen (2001)
print("Critical baseline is calculated from information in slc.par file.")
Bperp_max = Br/f*r1*math.tan(inc/180*math.pi)
# Btemp_max: total temporal decorrelation, use different values for L-band,
# C-band and X-band, therfore get the sensor from current directory
currdir = os.getcwd()
sensor = currdir[:-6].split("/")[-1]
# select sensor-specific default values for temporal decorrelation
# L-band: total decorrelation after 7 years
if sensor == "PALSAR1" or sensor == "PALSAR2":
    Btemp_max = 2556.75
# C-band: total decorrelation after 5 years (see Hooper et al., 2007)
elif sensor == "ASAR" or sensor == "RSAT2" or sensor == "S1":
    Btemp_max = 1826.25
# X-band: total decorrelation after 3 years
elif sensor == "TSX" or sensor == "CSK":
    Btemp_max = 1095.75
else:
    print("Sensor", sensor, "is not added yet. Default C-band parameters \
    are used.")
# linear decorrelation model for Btemp, Bperp, Bdopp is used (Eq. 2.1 & 2.2
# in Kampes (2005) along with a coherence treshold:
coh_thres = 0.5


# Define min/max number of connections to be used
nmin = 4
nmax = 10
print("Parameters for generation of SBAS network:")
print("Minimum number of connections:", nmin)
print("Maximum number of connections:", nmax)
print("Maximum Btemp: %d days (%d years)" % (Btemp_max, Btemp_max/365))
print("Maximum Bperp: %d m" % (Bperp_max))
print("Maximum DC diff.: %d Hz" % (Ba))
print("Coherence Threshold", coh_thres)
# user input for nmin and nmax?
if auto != 1:
    # if automated processing isn't used, nmin and nmax can be changed
    message = "Use this parameters (y), or enter new values for min/max \
number of connections in the form min/max (e.g. 3/9): "
    while True:
        quest = input(message)
        if quest == "y":
            print("Default parameters will be used.")
            print()
            break
        else:
            params = quest.split("/")
            if len(params)==2:
                nmin = int(params[0])
                nmax = int(params[1])
                print()
                break
            else:
                print("Wrong input! For default parameters use y, to",
                "change min/max numbers of connections enter min/max",
                "values, e.g. 3/9.")


# create the SBAS network
epoch1, epoch2, Bperps_sbas = csn.create_sb_network(dates, Bperps, Bdopp, \
                master_ix, Btemp_max, Bperp_max, Ba, coh_thres, nmin, nmax)
# note that epoch1 and epoch2 contain the indices of valid connections


# plot selected connections
print("Creating baseline plot...")
filename = "./" + trackdir + "/baseline_plot_sbas_network"
cbp.plot_baseline_time_sbas(np.array(dates), Bperps, epoch1, epoch2, \
                            filename)
print()


# save dates of connections to ./TxxxX/lists/ifms.list
filename = "./" + trackdir + "/lists/ifms.list"
filename_backup = "./" + trackdir + "/lists/ifms_backup.list"
print("Saving epoch connections to file " + filename + "...")
# check if slaves.list file exists and has already be renamed
if os.path.isfile(filename):
    if os.path.isfile(filename_backup):
        print("Backup already exists and will not be overwritten.")
    else:
        # save existing slaves.list to slaves_backup.list
        cmd_string = "cp " + filename + " " + filename_backup
        os.system(cmd_string)
        print("Existing ifms.list saved to ifms_backup.list.")
outfile = open(filename, "w")
# also check for already existing IFGs in TxxxX/INT directory and create
# the file add_ifms.list
dirname = "./" + trackdir + "/INT"
if os.path.isdir(dirname):
    ifg_exist = os.listdir(dirname)
else:
    ifg_exist = [] # INT directory doesn't exist yet
i_add = 0
add_ifg = [True] * len(epoch1)
exist = [False] * len(ifg_exist)
for epo1, epo2 in zip(epoch1, epoch2):
    outfile.write(dates[epo1].strftime("%Y%m%d") + "," + \
                  dates[epo2].strftime("%Y%m%d") + "\n")
    ifg_dates = dates[epo1].strftime("%Y%m%d") + "-" + \
                dates[epo2].strftime("%Y%m%d")
    i_exist = 0
    for ifg in ifg_exist:
        if ifg == ifg_dates:
            exist[i_exist] = True
            add_ifg[i_add] = False
            break
        i_exist = i_exist + 1
    i_add = i_add + 1
outfile.close
print(str(len(epoch1)) + " epoch connections written to " + filename + ".")
print()


i = 0
del_ifg = []
for ifg in ifg_exist:
    if exist[i] == False:
        print(ifg)
        del_ifg.append(ifg)
    i = i + 1
if len(del_ifg) > 0:
    print("WARNING: The above listed IFG(s) already exist but are not selected.")
    # Delete existing IFGs which are not selected for current SBAS network?
    if auto != 1:
        message = "Delete these interferograms? (y/n): "
        while True:
            quest = input(message)
            if quest == "y":
                for ifg in del_ifg:
                    cmd_string = "rm -rf ./" + trackdir + "/INT/" + ifg
                    os.system(cmd_string)
                break
            elif quest == "n":
                # nothing to do
                break
            else:
                print("Wrong input, to delete listed IFG use y, to keep them",
                      "to keep IFG use n.")
else:
    print("All existing IFGs are selected and will be used.")
print()


if any(add_ifg) == True:
    # save to add_ifms.list
    filename = "./" + trackdir + "/lists/add_ifms.list"
    outfile = open(filename, "w")
    print("IFGs to be added will be written to add_ifms.list, i.e.:")
    i = 0
    for epo1, epo2 in zip(epoch1, epoch2):
        if add_ifg[i] == True:
            print(dates[epo1].strftime("%Y%m%d") + "-" + \
                  dates[epo2].strftime("%Y%m%d"))
            outfile.write(dates[epo1].strftime("%Y%m%d") + "," + \
                          dates[epo2].strftime("%Y%m%d") + "\n")
        i = i + 1
    outfile.close
else:
    print("Stack is already complete. No IFGs to add.")
print()


# save dates and Bperps of connection to ./TxxxX/baseline_plot_output.txt
filename = "./" + trackdir + "/baseline_plot_output.txt"
print("Saving epoch connections and Bperps to file " + filename + "...")
outfile = open(filename, "w")
outfile.write("Date1 [yyyy-mm-dd]   Date2 [yyyy-mm-dd]   Bperp [m]\n")
outfile.write("-----------------------------------------------------\n")
for epochA, epochB, Bperp, in zip(epoch1, epoch2, Bperps_sbas):
    outfile.write("%17s    %17s   %9.1f\n" % (dates[epochA].strftime(\
                  "%Y-%m-%d"), dates[epochB].strftime("%Y-%m-%d"), Bperp))
outfile.close
print(str(len(epoch1)) + " epoch connections written to " + filename + ".")
print()


