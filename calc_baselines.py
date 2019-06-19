#!/usr/bin/env python

"""
*******************************************************************************
* calc_baselines:  Calculates the initial and precision baselines, creates    *
*                  slaves.list and ifgs.list, and plots the baseline results. *
*                                                                             *
*                  Script calls functions in 'calc_baseline_functions.py'     *
*                                                                             *
*                  When creating the initial baselines, the reference         *
*                  master, slaves list and interferogram lists are also       *
*                  generated.                                                 *
*                                                                             *
*     Script based on the STAMPS_BLplot.m Matlab routines developed by        *
*     H. Baehr, A. Schenk, T. Fuhrmann @ KIT, Germany, 2010-2017              *
*                                                                             *
* input:  [proc_file]   name of GAMMA proc file (eg. gamma.proc)              *
*         [type]        type of baseline to calculate (initial or precision)  *
*                                                                             *
* author: Thomas Fuhrmann @ GA    March, 2018 v0.1                            *
*         Sarah Lawrie @ GA       13/08/2018, v1.0                            *
*             -  Major update to streamline processing:                       *
*                  - use functions for variables and PBS job generation       *
*                  - add option to auto calculate multi-look values and       *
*                      master reference scene                                 *
*                  - add initial and precision baseline calculations          *
*                  - add full Sentinel-1 processing, including resizing and   *
*                     subsetting by bursts                                    *
*                  - remove GA processing option                              *
*         Sarah Lawrie @ GA       26/03/2019, v1.1                            *
*             -  Add 'add scenes' functionality to workflow                   *
*******************************************************************************
   Usage: calc_baselines.py [proc_file] [type]
"""


import os
import sys
import math
from datetime import datetime, date
import numpy as np
import operator
from shutil import copyfile, rmtree, move
import fileinput


import calc_baselines_functions as cbf


# Input parameters
proc_file = sys.argv[1]
type = sys.argv[2]


# Extract variables from proc file (not using ConfigParser, as config file not in right format)
for line in open(proc_file):
    if line.startswith('NCI_PATH='):
        nci_path = line.split('=')[1].strip()
    if line.startswith('PROJECT='):
        project = line.split('=')[1].strip()
    if line.startswith('SENSOR='):
        sensor = line.split('=')[1].strip()
    if line.startswith('TRACK='):
        track = line.split('=')[1].strip()
    if line.startswith('FRAME='):
        frame = line.split('=')[1].strip()
    if line.startswith('SLC_DIR='):
        slc_dir1 = line.split('=')[1].strip()
    if line.startswith('INT_DIR='):
        int_dir1 = line.split('=')[1].strip()
    if line.startswith('BASE_DIR='):
        base_dir1 = line.split('=')[1].strip()
    if line.startswith('LIST_DIR='):
        list_dir1 = line.split('=')[1].strip()
    if line.startswith('PRE_PROC_DIR='):
        pre_proc_dir1 = line.split('=')[1].strip()
    if line.startswith('SCENE_LIST='):
        scene_list = line.split('=')[1].strip()
    if line.startswith('SLAVE_LIST='):
        slave_list = line.split('=')[1].strip()
    if line.startswith('IFG_LIST='):
        ifg_list = line.split('=')[1].strip()
    if line.startswith('REMOVE_IFG_LIST='):
        remove_ifg_list = line.split('=')[1].strip()
    if line.startswith('ADD_DO_SLC='):
        add_scenes = line.split('=')[1].strip()
    if line.startswith('ADD_SCENE_LIST='):
        add_scene_list = line.split('=')[1].strip()
    if line.startswith('ADD_SLAVE_LIST='):
        add_slave_list = line.split('=')[1].strip()
    if line.startswith('ADD_IFG_LIST='):
        add_ifg_list = line.split('=')[1].strip()
    if line.startswith('POLARISATION='):
        polar = line.split('=')[1].strip()
    if line.startswith('PROCESS_METHOD='):
        method = line.split('=')[1].strip()
    if line.startswith('REF_MASTER_SCENE='):
        master1 = line.split('=')[1].strip()
    if line.startswith('RANGE_LOOKS='):
        rlks = line.split('=')[1].strip()
    if line.startswith('MIN_CONNECT='):
        nmin = int(line.split('=')[1].strip())
    if line.startswith('MAX_CONNECT='):
        nmax = int(line.split('=')[1].strip())

# Project directories
proj_dir = os.path.join(nci_path, "INSAR_ANALYSIS", project, sensor, "GAMMA")
if sensor == "S1":
    track_name = "%s_%s"%(track,frame)
    track_dir =  os.path.join(proj_dir, track_name)
else:
    track_name = track
    track_dir = os.path.join(proj_dir, track)

slc_dir = os.path.join(proj_dir, track_dir, slc_dir1)
int_dir = os.path.join(proj_dir, track_dir, int_dir1)

base_dir = os.path.join(proj_dir, track_dir, base_dir1)
list_dir = os.path.join(proj_dir, track_dir, list_dir1)
pre_proc_dir = os.path.join(proj_dir, pre_proc_dir1)
results_dir = os.path.join(proj_dir, track_dir, "results")


# Create baselines directory
if not os.path.exists(base_dir):
    os.makedirs(base_dir)

# Lists
scenes_list = os.path.join(list_dir, scene_list)
slaves_list = os.path.join(list_dir, slave_list)
ifgs_list = os.path.join(list_dir, ifg_list)
remove_ifgs_list = os.path.join(list_dir, remove_ifg_list)
add_scenes_list = os.path.join(list_dir, add_scene_list)
add_slaves_list = os.path.join(list_dir, add_slave_list)
add_ifgs_list = os.path.join(list_dir, add_ifg_list)
slaves_list_org=os.path.join(list_dir,"slaves.list_org")
ifgs_list_org=os.path.join(list_dir,"ifgs.list_org")
ifgs_list_post_remove=os.path.join(list_dir,"ifgs.list_post_remove_ifgs")



################ INITIAL BASELINE CALCULATION ####################

if type == 'initial':

    # Read scenes.list and convert date strings to datetime objects
    if os.path.isfile(scenes_list) and os.access(scenes_list, os.R_OK):
        f = open(scenes_list)
        dates = f.readlines()
        dates[:] = [line.rstrip("\n") for line in dates]
        # convert string list to datetime objects
        dates[:] = [datetime.strptime(line, "%Y%m%d") for line in dates]
        num_scenes = len(dates)
    else:
        print("ERROR: Can't read file", scenes_list)
        sys.exit()

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
    if master1 == 'auto':
        if sensor =='S1':
            pass # reference master updated by process_gamma script
        else:
            master_initial = dates[index_min]
            master = master_initial

            # read and write master to proc file
            proc_file_backup = os.path.join(pre_proc_dir, track_dir + ".proc_pre_init_baseline")
            if os.path.isfile(proc_file) and os.access(proc_file, os.R_OK):
                copyfile(proc_file, proc_file_backup)
                replace = { "REF_MASTER_SCENE=auto" : "REF_MASTER_SCENE="+str(master.strftime("%Y%m%d")) }
                for line in fileinput.input(proc_file, inplace=True):
                    line = line.rstrip('\r\n')
                    print(replace.get(line, line))

                # reference master date to text file
                outfile = open(os.path.join(results_dir, track_dir + "_DEM_ref_master_results"), "w")
                outfile.write('DEM REFERENCE MASTER SCENE' + '\n')
                outfile.write(' ' + '\n')
                outfile.write('%s\n' % (str(master.strftime("%Y%m%d"))))
                outfile.close
            else:
                print("ERROR: Can't read file", proc_file)
                sys.exit()
    else:
        master = datetime.strptime(master1, "%Y%m%d")


    # Perform the loop over all scenes
    class SLC_data(object):
        # The class "constructor" - It's actually an initializer
        def __init__(self, fDC=0, t_min=0, t_max=0, lat=0, lon=0, r1=0, inc=0, f=0, Br=0, Ba=0, t=[], xyz=[[],[]]):
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
        slc_data = SLC_data(fDC, t_min, t_max, lat, lon, r1, inc, f, Br, Ba, t, xyz)
        return slc_data


    # Read all slc.par files and save relevant parameters in the object SLC_data
    scn_idx = 0;
    # initialise slc_data object
    init = SLC_data()
    # list of slc_data objects
    slc_dl = [init for i in range(num_scenes)]
    for scene in dates:
        slc_par = os.path.join(slc_dir, scene.strftime("%Y%m%d"), scene.strftime("%Y%m%d") + "_" + polar + ".slc.par")
        if os.path.isfile(slc_par) and os.access(slc_par, os.R_OK):
            fDC, t, xyz = cbf.read_orbits(slc_par)
            t_min, t_max, lat, lon, r1, inc, f, Br, Ba = cbf.read_master_info(slc_par)
        else:
            print("ERROR: Can't read file", slc_par)
            sys.exit()

        slc_dl[scn_idx] = make_slc_data(fDC, t_min, t_max, lat, lon, r1, inc, f, Br, Ba, t, xyz)
        scn_idx = scn_idx + 1


    # Read orbit data an calculate Bperp for all masters
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
        # calculate satellite position for master scene
        t = list(slc_dl[mas_ix].t)
        M = cbf.calc_orbit_pos(t, slc_dl[mas_ix].t_min, slc_dl[mas_ix].t_max, slc_dl[mas_ix].xyz, P)
        # perpendicular baselines of slaves w.r.t master
        Bperps = [0] * (num_scenes-1)
        # loop through all slaves and calculate Bperp and Bdopp
        counter = 0
        for slave in slaves:
            sla_ix = dates.index(slave)
            # calculate satellite position for slave scene
            t = list(slc_dl[sla_ix].t)
            S = cbf.calc_orbit_pos(t, slc_dl[mas_ix].t_min, slc_dl[mas_ix].t_max, slc_dl[sla_ix].xyz, P)
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


    # Use median values of relative baselines
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


    # Setup the slaves list and calculate Doppler Centroid differences
    slaves = list(dates)
    slaves.remove(master)

    # backup existing slave list if adding scenes to already processed dataset
    if add_scenes == "yes":
        slaves_list_org = os.path.join(list_dir, slave_list + "_org")
        os.rename(slaves_list, slaves_list_org)

    # save dates of slaves to slaves.list
    outfile = open(slaves_list, "w")
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

    # backup baseline files created for already processed dataset
    if add_scenes == "yes":
        initial_plot_file = os.path.join(base_dir, track_name + "_baseline_master_" + master.strftime("%Y%m%d") + "_initial.txt")
        initial_plot_file_new = os.path.join(base_dir, track_name + "_baseline_master_" + master.strftime("%Y%m%d") + "_initial_org.txt")
        initial_plot = os.path.join(base_dir, track_name + "_baseline_master_" + master.strftime("%Y%m%d") + "_initial_plot.png")
        initial_plot_new = os.path.join(base_dir, track_name + "_baseline_master_" + master.strftime("%Y%m%d") + "_initial_plot_org.png")
        move(initial_plot_file, initial_plot_file_new)
        move(initial_plot, initial_plot_new)

        if method == 'sbas':
            sbas_para_file = os.path.join(base_dir, track_name + "_SBAS_parameters.txt")
            sbas_para_file_new = os.path.join(base_dir, track_name + "_SBAS_parameters_org.txt")
            sbas_connt_file = os.path.join(base_dir, track_name + "_SBAS_connections.txt")
            sbas_connt_file_new = os.path.join(base_dir, track_name + "_SBAS_connections_org.txt")
            sbas_net_file = os.path.join(base_dir, track_name + "_baseline_SBAS_network.txt")
            sbas_net_file_new = os.path.join(base_dir, track_name + "_baseline_SBAS_network_org.txt")
            sbas_plot = os.path.join(base_dir, track_name + "_baseline_SBAS_network_plot.png")
            sbas_plot_new = os.path.join(base_dir, track_name + "_baseline_SBAS_network_plot_org.png")
            move(sbas_para_file, sbas_para_file_new)
            move(sbas_connt_file, sbas_connt_file_new)
            move(sbas_net_file, sbas_net_file_new)
            move(sbas_plot, sbas_plot_new)

    # Plot dates and Bperps for selected master
    filename = os.path.join(base_dir, track_name + "_baseline_master_" + master.strftime("%Y%m%d") + "_initial_plot")
    cbf.plot_baseline_time_sm(np.array(dates), Bperps, master_ix, filename)

    # Output epochs, Bperps and Bdopp to text file
    outfile = open(os.path.join(base_dir, track_name + "_baseline_master_" + master.strftime("%Y%m%d") + "_initial.txt"), "w")
    outfile.write('Epoch   Date[yyyy-mm-dd]   Bperp[m]    DCdiff[Hz]' + '\n')
    outfile.write('-------------------------------------------------' + '\n')
    epoch = 1
    for line, Bperp, dopp in zip(dates, Bperps, Bdopp):
        outfile.write('%5d  %16s  %9.1f %13.1f\n' % (epoch, line.strftime("%Y-%m-%d"), Bperp, dopp))
        epoch = epoch + 1
    outfile.close


    # create add slaves list if adding scenes to already processed dataset
    if add_scenes == "yes":
        org_slaves = []
        with open(slaves_list_org) as f:
            org_slaves = f.read().splitlines()

        new_slaves = []
        with open(slaves_list) as f:
            new_slaves = f.read().splitlines()

        add_slaves = list(set(new_slaves) - set(org_slaves))
        outfile = open(add_slaves_list, "w")
        for slave in add_slaves:
            outfile.write(slave + "\n")

        outfile.close
 
    ## Backup existing ifg list if adding scenes to already processed dataset
    if add_scenes == "yes":
        ifgs_list_org = os.path.join(list_dir, ifg_list + "_org")
        os.rename(ifgs_list, ifgs_list_org)


    ##### Create Single Master Interferogram List ##### 

    if method == 'single':
        # write new ifgs.list
        outfile = open(ifgs_list, "w")
        # epoch indices (needed later for add_ifgs functionality)
        epoch1 = []
        epoch2 = []
        for slave in slaves:
            outfile.write(master.strftime("%Y%m%d") + "," + slave.strftime("%Y%m%d") + "\n")
            # epoch1 is mas_ix
            epoch1.append(mas_ix)
            # get the index of slave for epoch2
            epoch2.append(dates.index(slave))
        outfile.close


    ##### Create Daisy-chained Interferogram List #####

    elif method == 'chain':
        # create temporary list for numbering each scene
        nums = range(0, num_scenes)

        # create temporary scene list with dates in yyyymmdd format
        scenes = []
        for scene in dates:
            in_scene = scene.strftime("%Y%m%d")
            scenes.append(in_scene)

        # join lists
        merged = []
        for idx, i  in enumerate(scenes):
            merged.append( (nums[idx], i) )

        # write new ifgs.list
        outfile = open(ifgs_list, "w")
        # epoch indices (needed later for add_ifgs functionality)
        epoch1 = []
        epoch2 = []
        for num, scene in merged:
            num1 = num + 1
            if num1 < len(scenes):
                outfile.write(scene + "," + scenes[num1] + "\n")
                epoch1.append(dates.index(datetime.strptime(scene, "%Y%m%d")))
                epoch2.append(dates.index(datetime.strptime(scenes[num1], "%Y%m%d")))
        outfile.close


    ##### Coherence-based SBAS Network Calculation and Interferogram List #####

    elif method == 'sbas':

        # extract further information from SLC_data object for selected master
        Br = slc_dl[master_ix].Br
        f = slc_dl[master_ix].f
        r1 = slc_dl[master_ix].r1
        inc = slc_dl[master_ix].inc

        # critical Doppler difference is azimuth bandwidth Ba, see Eq. 4.4.13 in Hanssen (2001)
        Ba = slc_dl[master_ix].Ba

        # calculate critical baseline Bperp_max from Eq. 4.4.11 in Hanssen (2001)
        Bperp_max = Br/f*r1*math.tan(inc/180*math.pi)

        # Btemp_max: total temporal decorrelation, use different values for L-band,
        #            C-band and X-band

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
            print("Sensor", sensor, "is not added yet. Default C-band parameters are used.")
            Btemp_max = 1826.25

        # linear decorrelation model for Btemp, Bperp, Bdopp is used (Eq. 2.1 & 2.2 in Kampes (2005) along with a coherence threshold:
        coh_thres = 0.5

        # min/max number of connections to be used are now defined in .proc file
        # default values are: nmin = 4
        #                     nmax = 7 (Sentinel-1)
        #                     nmax = 10 (other sensors)
        # reduced max threshold for Sentinel-1 because of small repeat time

        # Output SBAS network parameters
        outfile = open(os.path.join(base_dir, track_name + "_SBAS_parameters.txt"), "w")
        outfile.write('Parameters for generation of SBAS network' + '\n')
        outfile.write('-----------------------------------------' + '\n')
        outfile.write('Minimum number of connections: ' '%d\n' % (nmin))
        outfile.write('Maximum number of connections: ' '%d\n' % (nmax))
        outfile.write('Maximum Btemp: ' '%d' ' days (' '%d' ' years)\n' % (Btemp_max, Btemp_max/365))
        outfile.write('Maximum Bperp: ' '%d' ' m\n' % (Bperp_max))
        outfile.write('Maximum DC diff.: ' '%d' ' Hz\n' % (Ba))
        outfile.write('Coherence Threshold: ' '%s\n' % (coh_thres))
        outfile.close

        # create the SBAS network
        outfile = os.path.join(base_dir, track_name + "_SBAS_connections.txt")
        epoch1, epoch2, Bperps_sbas, ddiff_sbas, doppdiff_sbas = cbf.create_sb_network(dates, Bperps, Bdopp, master_ix, Btemp_max, Bperp_max, Ba, coh_thres, nmin, nmax, outfile)
        # note that epoch1 and epoch2 contain the indices of valid connections

        # plot selected connections
        filename = os.path.join(base_dir, track_name + "_baseline_SBAS_network_plot")
        cbf.plot_baseline_time_sbas(np.array(dates), Bperps, epoch1, epoch2, filename)

        # save dates of connections to ifgs.list
        # write new ifgs.list
        outfile = open(ifgs_list, "w")
        for epo1, epo2 in zip(epoch1, epoch2):
            outfile.write(dates[epo1].strftime("%Y%m%d") + "," + dates[epo2].strftime("%Y%m%d") + "\n")
        outfile.close

        # save dates and Bperps of connection to ./TxxxX/baseline_plot_output.txt
        outfile = open(os.path.join(base_dir, track_name + "_baseline_SBAS_network.txt"), "w")
        outfile.write("Date1[yyyy-mm-dd]   Date2[yyyy-mm-dd]   DateDiff[d]   Bperp[m]   DCdiff[Hz]\n")
        outfile.write("---------------------------------------------------------------------------\n")
        for epochA, epochB, Bperp, ddiff, doppdiff in zip(epoch1, epoch2, Bperps_sbas, ddiff_sbas, doppdiff_sbas):
            outfile.write("%16s    %16s   %11d  %9.1f    %9.1f\n" % (dates[epochA].strftime("%Y-%m-%d"), dates[epochB].strftime("%Y-%m-%d"), ddiff, Bperp, doppdiff))
        outfile.close

    else:
        pass


    ### Create add ifgs list if adding scenes to already processed dataset
    if add_scenes == "yes":        
        org_ifgs = []
        with open(ifgs_list_org) as f:
            org_ifgs = f.read().splitlines()

        new_ifgs = []
        with open(ifgs_list) as f:
            new_ifgs = f.read().splitlines()
        
        removed_ifgs = []
        with open(remove_ifgs_list) as f:
            removed_ifgs = f.read().splitlines()
    
        # identify new ifgs to process and ifgs no longer required due to new network with additional scenes
        add_ifgs = list(set(new_ifgs) - set(org_ifgs))

        # remove previously removed ifgs from list
        final_ifgs = list(set(add_ifgs) - set(removed_ifgs))
        outfile = open(add_ifgs_list, "w")
        for ifg in final_ifgs:
            outfile.write(ifg + "\n")

        outfile.close



################ PRECISION BASELINE CALCULATION ####################

elif type == 'precision':

    # Read master r*mli.par file and calculate look angle for centre pixel
    # open file and read relevant lines
    f = open(os.path.join(slc_dir, master1, "r" + master1 + "_" + polar + "_" + rlks + "rlks.mli.par"))
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

    if os.path.isfile(ifgs_list) and os.access(ifgs_list, os.R_OK):
        print("File", ifgs_list, "exists and is readable")
        f = open(ifgs_list)
        dates = f.readlines()
        dates[:] = [line.rstrip("\n") for line in dates]
        epoch1 = list(dates)
        epoch1[:] = [line.split(",",1)[0] for line in epoch1]
        epoch2 = list(dates)
        epoch2[:] = [line.split(",",1)[1] for line in epoch2]
        num_ifgs = len(dates)
    else:
        print("ERROR: Can't read file", ifgs_list)
        sys.exit()

    # Read all base.par files and calculate Bperp from TCN baselines
    print("Calculating Bperp from precision baseline (TCN) in *.base.par")
    i = 0
    Bperp_prec = [0] * num_ifgs
    # loop through all IFGs
    for epochA, epochB in zip(epoch1, epoch2):
        filename = os.path.join(int_dir, epochA + "-" + epochB, epochA + "-" + epochB + "_" + polar + "_" + rlks + "rlks_base.par")
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
            print("ERROR: Can't read file " + filename + ". IFG does not exist or is corrupt.")
            Bperp_prec[i] = "nan"
        i = i + 1

    # read initial baseline estimates (based on orbits only) and compare
    filename = os.path.join(base_dir, track_name + "_baseline_plot_output.txt")

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
        epoch1_init[:] = [datetime.strptime(line, "%Y-%m-%d") for line in epoch1_init]
        epoch2_init[:] = [datetime.strptime(line, "%Y-%m-%d") for line in epoch2_init]
        # combined date string of epoch1 and epoch2
        epoch12_init = [" "] * num_ifgs_init
        i = 0
        for line in epoch12_init:
            epoch12_init[i] = datetime.strftime(epoch1_init[i], "%Y%m%d") + "," + datetime.strftime(epoch2_init[i], "%Y%m%d")
            i = i + 1


        # compare epoch connections to find identical epochs and
        # save dates and Bperps of connection to ./TxxxX/baseline_comparison.txt
        outfile = open(os.path.join(base_dir, track_name + "_baseline_comparison.txt"), "w")
        outfile.write("Date1 [yyyy-mm-dd]   Date2 [yyyy-mm-dd]   init. Bperp [m]   final Bperp [m]   Difference [m]\n")
        outfile.write("--------------------------------------------------------------------------------------------\n")
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
                    outfile.write("%17s    %17s         %9.1f         %9.1f    %9.1f\n" % (epoch1_init[i].strftime("%Y-%m-%d"), epoch2_init[i].strftime("%Y-%m-%d"), Bperp_init[i], Bperp_prec[j], diff))
                    counter = counter + 1
        outfile.close
        print(str(counter) + " identical epoch connections written to " + filename + ".")
        print()
        print("Mean absolute difference: %9.1f" % (diff_sum_abs/counter))
        print("Minimum difference: %9.1f" % diff_min)
        print("Maximum difference: %9.1f" % diff_max)
    else:
        print("Cannot compare precise Bperps to initial Bperps. File", filename, "does not exist.")

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
    master_ix = epochs.index(master1)
    # convert to datetime object (needed for epoch_baselines and for plotting)
    epochs[:] = [datetime.strptime(epo, "%Y%m%d") for epo in epochs]
    # re-calculate Bprep_prec w.r.t. SM constellation
    epochbperp = cbf.epoch_baselines(epochs,Bperp_prec,epoch1_ix,epoch2_ix, master_ix)

    # plot scene connections using precision baselines
    filename = os.path.join(base_dir, track_name + "_baseline_SBAS_network_final_plot")
    cbf.plot_baseline_time_sbas(np.array(epochs), epochbperp, epoch1_ix, epoch2_ix, filename)

else:
    pass

