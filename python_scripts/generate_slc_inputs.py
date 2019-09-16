#!/usr/bin/python3
import os
from pathlib import Path
from datetime import datetime

import shapely.wkt
import geopandas as gpd
import pandas as pd
from spatialist import Vector
from python_scripts.s1_slc_metadata import Archive


def __slc_df_dict_format(df, master_grid_df):
    """A helper function for munging a pandas data to form slc input dict.

    :param df: A pandas data frame

    :return:
    A dict: A sample dict
    {   "VH": {
            "IW1": {
                "48b33e9e-b4cf-4443-8e99-8239ba6bbda6": {
                    "burst_nums": [1],
                    "acquisition_datetime": numpy.datetime("2019-01-06T20:34:32.136277000"),
                    "url": "< path to slc zip file>"
                },
                "fc5493c9-7665-49aa-a879-d09bfed0dcba": {
                    "burst_nums": [3, 6, 8, 10, 5, 2, 9, 7, 4],
                    "acquisition_datetime": numpy.datetime("2019-01-06T20:34:04.554823000"),
                    "url": "< path to slc zip file>"
            },
            "IW2": {
                "48b33e9e-b4cf-4443-8e99-8239ba6bbda6": {
                    "burst_nums": [1],
                    "acquisition_datetime": numpy.datetime("2019-01-06T20:34:32.136277000"),
                    "url": "< path to slc zip file>"
                },
                "fc5493c9-7665-49aa-a879-d09bfed0dcba": {
                    "burst_nums": [3, 6, 8, 10, 5, 2, 9, 7, 4],
                    "acquisition_datetime": numpy.datetime("2019-01-06T20:34:04.554823000"),
                    "url": "< path to slc zip file>"
                }
            },
            "IW3": {
                "48b33e9e-b4cf-4443-8e99-8239ba6bbda6": {
                    "burst_nums": [2, 1],
                    "acquisition_datetime": numpy.datetime("2019-01-06T20:34:32.136277000"),
                    "url": "< path to slc zip file>"
                },
                "fc5493c9-7665-49aa-a879-d09bfed0dcba": {
                    "burst_nums": [3, 6, 8, 10, 5, 9, 7, 4],
                    "acquisition_datetime": numpy.datetime("2019-01-06T20:34:04.554823000"),
                    "url": "< path to slc zip file>"
                }
            }
        },
        "VV": {
                ...
              }
    }

    """

    def __get_burst_overlap(slc_df, swath_name):
        """a helper method to check if bursts overlaps within the buffered master burst."""
        master_swath_df = master_grid_df[master_grid_df.swath == swath_name]
        burst_overlaps = []
        gpd_slc = gpd.GeoDataFrame(
            slc_df, crs={"init": "epsg:4326"},
            geometry=slc_df["AsText(bursts_metadata.burst_extent)"].map(shapely.wkt.loads)
        )

        for burst_num in master_swath_df.burst_num:

            burst_geom = master_swath_df[master_swath_df.burst_num == burst_num]["geometry"].values[0]
            burst_geom = burst_geom.buffer(+0.02, cap_style=2, join_style=2)
            for idx, row in gpd_slc.iterrows():
                if burst_geom.contains(row['geometry']):
                    burst_overlaps.append(row['burst_number'])
        return burst_overlaps

    polarizations = df.polarization.unique()
    swaths = df.swath.unique()
    pol_dict = dict()
    for pol in polarizations:
        swath_dict = dict()
        for swath in swaths:
            swath_subset = df[(df.swath == swath) & (df.polarization == pol)].copy()
            slc_ids = swath_subset.id.unique()
            slc_dict = dict()
            for slc_id in slc_ids:
                slc_subset = swath_subset[swath_subset.id == slc_id]
                slc_dict[slc_id] = {
                    "burst_nums": list(slc_subset.burst_number.values),
                    "acquisition_datetime": slc_subset.acquisition_start_time.unique()[
                        0
                    ],
                    "url": slc_subset.url.unique()[0],
                }
            swath_dict[swath] = slc_dict
        pol_dict[pol] = swath_dict
    return pol_dict


def query_slc_inputs(
    dbfile: Path,
    spatial_subset: Path,
    start_date: datetime,
    end_date: datetime,
    orbit: str,
    track: int,
    return_dataframe: bool = True
):
    """A method to query sqlite database and generate slc input dict.

    :param dbfile: A path to sqlite database
    :param spatial_subset: A path to a vector shape file
    :param start_date: A datetime object
    :param end_date: A datetime object
    :param orbit: A 'str' type, sentinel-1 acquisition orbit type
    :param track: A 'int' type, sentinel-1 relative orbit number (track)

    :return:
        Returns a dict type of slc input field values for all unique date queried
        from a dbfile between start_date and end_date (inclusive of the end dates)
        for area within a spatial_subset if data is in the database. Else returns
        None.

    """
    with Archive(dbfile) as archive:
        tables_join_string = (
            "{0} INNER JOIN {1} on {0}.swath_name = {1}.swath_name INNER JOIN {2} "
            "on {2}.id = {1}.id".format(
                archive.bursts_table_name,
                archive.swath_table_name,
                archive.slc_table_name,
            )
        )
        min_date_arg = '{}.acquisition_start_time>=Datetime("{}")'.format(
            archive.slc_table_name, start_date
        )
        max_date_arg = '{}.acquisition_start_time<=Datetime("{}")'.format(
            archive.slc_table_name, end_date
        )

        columns = [
            "{}.burst_number".format(archive.bursts_table_name),
            "{}.total_bursts".format(archive.swath_table_name),
            "{}.burst_extent".format(archive.bursts_table_name),
            "{}.swath_name".format(archive.swath_table_name),
            "{}.id".format(archive.swath_table_name),
            "{}.swath".format(archive.bursts_table_name),
            "{}.orbit".format(archive.slc_table_name),
            "{}.orbitNumber_rel".format(archive.slc_table_name),
            "{}.sensor".format(archive.slc_table_name),
            "{}.polarization".format(archive.bursts_table_name),
            "{}.acquisition_start_time".format(archive.slc_table_name),
            "{}.url".format(archive.slc_table_name),
        ]

        slc_df = archive.select(
            tables_join_string=tables_join_string,
            orbit=orbit,
            track=track,
            spatial_subset=Vector(spatial_subset),
            columns=columns,
            min_date_arg=min_date_arg,
            max_date_arg=max_date_arg,
        )
        slc_df.to_csv('{}.csv'.format(os.path.basename(spatial_subset)[:-4]))
        slc_df["acquisition_start_time"] = pd.to_datetime(
            slc_df["acquisition_start_time"]
        )

        if return_dataframe:
            return slc_df

        unique_dates = [
            dt for dt in slc_df.acquisition_start_time.map(pd.Timestamp.date).unique()
        ]

        if unique_dates:
            return {
                dt.strftime("%Y-%m-%d"): __slc_df_dict_format(
                    slc_df[slc_df.acquisition_start_time.map(pd.Timestamp.date) == dt],
                    gpd.read_file(spatial_subset)
                )
                for dt in unique_dates
            }
        return None


if __name__ == "__main__":
    database_name = "/g/data/u46/users/pd1813/INSAR/s1_slc_database.db"
    shapefile = "/g/data/u46/users/pd1813/INSAR/shape_files/grid_vectors/T045D_F28S.shp"
    start_date = datetime(2015, 3, 1)
    end_date = datetime(2015, 3, 2)
    inputs = query_slc_inputs(
        database_name, shapefile, start_date, end_date, 'D', 45
    )
    print(inputs)

