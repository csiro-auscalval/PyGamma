#!/usr/bin/env python

"""
**************************************************************************************
* create_S1_archive_shapefiles:  Creates a shapefile showing the burst extents and   *
*                                a shapefile of the overall scene extent (merges     *
*                                                                                    *
*            Designed to be executed by 'run_S1_bursts' script only                  *
*                                                                                    *
* author: Sarah Lawrie @ GA       13/03/2019, v1.0                                   *
**************************************************************************************
   Usage: create_S1_archive_shapefiles.py [config_file] [function_file] [orient] [input_archive_list]
"""

## Import required python libraries
import os
import sys
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, Polygon
import fiona
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
shp_dir= var[1]

input_list = '%s/%s_track_data/%s' %(archive_dir,orient,in_list)


def create_shp(in_file, burst_out_shp, scene_out_shp):   

  # load archive burst coordinates into a dataframe
    input_file = in_file.strip()
    df_burst_meta_input = pd.read_csv(input_file, sep=" ")

    ## Convert coordinates into shapely polygons and put into new dataframe
    df_burst_meta = pd.DataFrame([])  # create blank dataframe

    # iterate over coordinates and append to blank dataframe
    for i, row in df_burst_meta_input.iterrows():
        mission = row[0]
        mode = row[1]
        prod_type = row[2]
        date = row[3]
        pass2 = row[4]
        polar = row[5]
        ab_orbit = row[6]
        rel_orbit = row[7]
        swath = row[8]
        burst_num = row[9]
        uniq_prod_id = row[10]
        datatake_id = row[11]
        res_class = row[12]
        proc_level = row[13]
        prod_class = row[14]
        scene_start = row[15]
        scene_stop = row[16]
        ipf_vers = row[17]
        raw_facil = row[18]
        raw_date = row[19]
        raw_time = row[20]
        raw_start = row[21]
        raw_stop = row[22]
        az_time = row[23]
        angle = row[24]
        delta_angle = row[25]
        ul_lon = row[26]
        ul_lat = row[27]
        ur_lon = row[28]
        ur_lat = row[29]
        lr_lon = row[30]
        lr_lat = row[31]
        ll_lon = row[32]
        ll_lat = row[33]
        ul = Point(row[26], row[27])
        ur = Point(row[28], row[29])
        lr = Point(row[30], row[31])
        ll = Point(row[32], row[33])                  
        xml_file = row[34]
        grid_dir = row[35]
        zip_file = row[36]
        pointList = [ul, ur, lr, ll]
        poly = Polygon([[p.x, p.y] for p in pointList]) # creates shapely polygon
        df_temp1 =  gpd.GeoDataFrame([[mission,mode,prod_type,date,pass2,polar,ab_orbit,rel_orbit,swath,
                                       burst_num,uniq_prod_id,datatake_id,res_class,proc_level,prod_class,
                                       scene_start,scene_stop,ipf_vers,raw_facil,raw_date,raw_time,raw_start,
                                       raw_stop,az_time,angle,delta_angle,ul_lon,ul_lat,ur_lon,ur_lat,lr_lon,lr_lat,ll_lon,ll_lat,xml_file,grid_dir,zip_file,poly]],
                          columns = ['Mission','Mode','ProdType','Date','Pass','Polar','AbOrbit','RelOrbit',
                                     'Swath','BurstNum','UniqProdID','DatatakeID','ResClass','ProcLevel',
                                     'ProdClass','SceneStart','SceneStop','IPFVers','RawFacil','RawDate',
                                     'RawTime','RawStart','RawStop','AzTime','Angle','DeltaAngle','UL_Lon',
                                     'UL_Lat','UR_Lon','UR_Lat','LR_Lon','LR_Lat','LL_Lon','LL_Lat','XMLFile',
                                     'GridDir','ZipFile','Extent'],
                          geometry='Extent')
        df_burst_meta = df_burst_meta.append(df_temp1, ignore_index=True)    
    
    ## Consolidate rows (merge dual polarisation details to single entry) and put into new dataframe
    df_burst_final = pd.DataFrame([])  # create blank dataframe

    zips = df_burst_meta.ZipFile.unique()
    zip_list = zips.tolist()
    swaths = df_burst_meta.Swath.unique()
    swath_list = swaths.tolist()
    
    for x in zip_list:
        zip_rows = df_burst_meta.loc[df_burst_meta['ZipFile'] == x]
    
        for y in swath_list:
            swath_rows = zip_rows.loc[zip_rows['Swath'] == y]
            burst_nums = swath_rows.BurstNum.unique()
            burst_list = burst_nums.tolist()
        
            for z in burst_list:
                rows = swath_rows.loc[swath_rows['BurstNum'] == z]

                # if dual polarisation, merge details into single entry
                num_rows = rows.shape[0]
                if num_rows == 2:
                    polar1 = rows.iloc[0]['Polar']
                    polar2 = rows.iloc[1]['Polar']
                    new_polar = "%s,%s" %(polar1,polar2)
                    row = rows.iloc[0].copy()
                    row.loc['Polar'] = new_polar # replace polar value
                    df_burst_final = df_burst_final.append(row)  
                else:
                    df_burst_final = df_burst_final.append(rows)  
                
    # re-order columns to original order                
    df_burst_final = df_burst_final[rows.columns]
    
    # convert to geopandas dataframe
    df_burst_final2 = gpd.GeoDataFrame(df_burst_final, geometry='Extent')
    
    ## Create shapefile of bursts
    df_burst_final2.crs = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
    df_burst_final2.to_file(burst_out_shp, driver='ESRI Shapefile')
    
    ## Create shapefile of scene extent (merge bursts)
    merged = df_burst_final2.drop(columns=['Swath','BurstNum','AzTime','Angle','DeltaAngle','UL_Lon','UL_Lat','UR_Lon','UR_Lat','LR_Lon','LR_Lat','LL_Lon','LL_Lat','XMLFile']) # remove unnecessary columns
    merged = merged.dissolve(by='ZipFile')
    merged.reset_index(level=0, inplace=True) 
    merged.crs = "+proj=longlat +ellps=WGS84 +datum=WGS84 +no_defs"
    merged.to_file(scene_out_shp, driver='ESRI Shapefile')


## Split file names for dataframes
def split_at(s, c, n):
    words = s.split(c)
    return c.join(words[:n]), c.join(words[n:])


name=split_at(in_list,'_',4)[0]
burst_out_shp = '%s/%s_bursts.shp' %(shp_dir,name)
scene_out_shp = '%s/%s_scenes.shp' %(shp_dir,name)

create_shp(input_list, burst_out_shp, scene_out_shp)


# script end
####################
