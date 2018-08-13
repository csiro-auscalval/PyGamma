"""
Function to create an SBAS network
INPUT:
- Bperps: list of perependicular baselines w.r.t. master
- dates: list of acquisitions dates
- Bdopp: list of doppler centroid frequency (fDC) differences w.r.t. master
- Bperp_max: maximum Bperp (total decorrelation)
- Btemp_max: maximum Btemp (total decorrelation)
- Ba: azimuth bandwidth which is the critical fDC value
- coh_thres: coherence threshold for selection of combinations
- nmin: minimum number of connections per epoch
- nmax: maximum number of connections per epoch

@author Thomas Fuhrmann @ GA March, 2018
"""


import numpy as np


#############
# Functions #
#############


def create_sb_network(dates, Bperps, Bdopp, master_ix, Btemp_max, \
    Bperp_max, Ba, coh_thres, nmin, nmax):


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
    print("Theoretical number of possible connections for", num_scenes, \
          "scenes: %d" % (num_scenes * (num_scenes - 1) / 2))
    # upper triangle matrix of valid connections
    tri_true = np.logical_not(np.tril(np.ones((num_scenes, num_scenes))))
    print("Number of connections with predicted coherence greater", \
          "%3.1f: %d" % (coh_thres, np.sum(np.logical_and(ix, tri_true))))
    print("Mean predicted coherence for these connections: %3.2f"
          % (np.mean(rho[np.logical_and(ix, tri_true)])))


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
    print("Number of final SBAS network connections: %d" % (len(epoch1)))
    print("Mean predicted coherence for these connections: %3.2f"
          % (np.mean(rho[ix])))
    print()
    # plot Bperps of final connections
    Bperps_sbas = bdiff_all[ix]


    # return values
    return epoch1, epoch2, Bperps_sbas
