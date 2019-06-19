#!/usr/bin/env python

"""
**************************************************************************************
* create_S1_archive_dataframe:  Creates a geopandas dataframe with shapely polygons  *
*                               of archive burst coordinates for a S1 track.         *
*                                                                                    *
*                               To save future processing time, the dataframe is     *
*                               saved for use when creating 'frame' scene stacks.    *
*                                                                                    *
*            Designed to be executed by 'run_S1_bursts' script only                  *
*                                                                                    *
* author: Sarah Lawrie @ GA       13/03/2019, v1.0                                   *
**************************************************************************************
   Usage: create_S1_archive_dataframe.py [config_file] [function_file] [orient] [input_archive_list]
"""

## Import required python libraries
import os
import sys
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import cv2
import subprocess

config_file = sys.argv[1]
function_file = sys.argv[2]
orient = sys.argv[3]
in_list = sys.argv[4]

# Extract variables from config file 
def call_func(funcname):
    CMD = 'echo $(source %s %s; echo $(%s))' %(function_file,config_file,funcname)
    p = subprocess.Popen(CMD, stdout=subprocess.PIPE, shell=True, executable='/bin/bash')
    return p.stdout.readlines()[0].strip()

var = call_func('python_variables').strip().decode('ascii').split()
archive_dir = var[0]

input_list = '%s/%s_track_data/%s' %(archive_dir,orient,in_list)


def archive_coords(in_file, out_file):
    
    # load archive burst coordinates into a dataframe
    input_file = in_file.strip()
    df_archive_input = pd.read_csv(input_file, sep=" ")

    # determine each swath's maximum number bursts for each zip file (used for GAMMA input)
    df_zip = pd.DataFrame([])    
    swaths = df_archive_input.Swath.unique()
    swath_list = swaths.tolist()

    for x in swath_list:
        swath = df_archive_input.loc[df_archive_input['Swath'] == x]
        zip_files = swath.ZipFile.unique()
        zip_list = zip_files.tolist()
    
        for y in zip_list:
            files = swath[swath.ZipFile == y]
            max_burst = files['BurstNum'].max()
            df1 = pd.DataFrame([[x, y, max_burst]],columns = ['Swath','ZipFile','MaxBurst'])
            df_zip = df_zip.append(df1, ignore_index=True)      
        
        ## Convert archive burst coordinates into shapely polygons and put into new dataframe
        df_archive = pd.DataFrame([]) # create blank dataframe
    
        # iterate over coordinates and append to blank dataframe    
        for i, row in df_archive_input.iterrows():
            mission = row[0]
            type1 = row[2]
            date = row[3]
            pass1 = row[4]
            polar = row[5]
            rel_orbit = row[7]
            swath = row[8]
            burst_num = row[9]             
            ipf = row[17]
            raw_date = row[19]    
            ul = Point(row[26], row[27])
            ur = Point(row[28], row[29])
            lr = Point(row[30], row[31]) 
            ll = Point(row[32], row[33])
            grid = row[35]
            zip_file = row[36]
            pointList = [ul, ur, lr, ll]
            poly = Polygon([[p.x, p.y] for p in pointList]) # creates shapely polygon
            df_temp2 =  gpd.GeoDataFrame([[mission,type1,date,pass1,polar,rel_orbit,ipf,raw_date,burst_num,swath,poly,grid,zip_file]],
                                         columns = ['Mission','Type','Date','Pass','Polar','RelOrbit','IPFVer','RawDate','BurstNum',
                                                    'Swath','Extent','GridDir','ZipFile'],
                                         geometry='Extent')
            df_archive = df_archive.append(df_temp2, ignore_index=True)
    
    # add max burst value to dataframe
    df_archive2 = pd.merge(df_archive, df_zip, on=['Swath','ZipFile'])
    
    # save updated archive burst coordinates dataframe for future use
    output_file = out_file.strip()
    df = df_archive2.to_pickle(output_file)


## Split file names for dataframes
def split_at(s, c, n):
    words = s.split(c)
    return c.join(words[:n]), c.join(words[n:])


name=split_at(in_list,'_',4)[0]
out_file='%s/%s_track_data/%s_Dataframe' %(archive_dir,orient,name)

archive_coords(input_list, out_file)
        

# script end
####################
