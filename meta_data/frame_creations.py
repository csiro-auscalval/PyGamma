import json
import os

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shapely.wkt
from descartes import PolygonPatch
from matplotlib.collections import PatchCollection
from mpl_toolkits.basemap import Basemap
from process_s1_metadata import pool
from scipy import stats
from shapely.geometry import Polygon
from shapely.ops import cascaded_union

csv_dir = "/g/data/u46/users/pd1813/INSAR/dataframe"


def plot_samples(mp):
    fig = plt.figure()
    ax = fig.add_subplot(111)
    m = Basemap(
        projection="merc",
        ellps="WGS84",
        llcrnrlon=100.0,
        llcrnrlat=-50.0,
        urcrnrlon=179.0,
        urcrnrlat=0.0,
        lat_ts=0,
        resolution="l",
    )
    m.drawcoastlines(linewidth=0.3)
    m.drawmapboundary()
    cm = plt.get_cmap("RdBu")
    num_colours = len(mp)
    minx, miny, maxx, maxy = mp.bounds
    w, h = maxx - minx, maxy - miny
    ax.set_xlim(minx - 0.2 * w, maxx + 0.2 * w)
    ax.set_ylim(miny - 0.2 * h, maxy + 0.2 * h)
    ax.set_aspect(1)
    patches = []

    for idx, p in enumerate(mp):
        colour = cm(1.0 * idx / num_colours)
        patches.append(
            PolygonPatch(p, fc=colour, ec="#555555", lw=0.2, alpha=1, zorder=1)
        )

    ax.add_collection(PatchCollection(patches, match_original=True))
    ax.set_xticks([])
    ax.set_yticks([])
    plt.tight_layout()
    plt.show()


def count_bursts(bursts_df, swt, buf=0.01, bursts_extents=False):

    df_subset = bursts_df[(bursts_df.swath == swt) & (bursts_df.polarization == "VV")]

    geoms = df_subset["geometry"]
    points = gpd.GeoSeries([geom.centroid for geom in geoms])

    pts = points.buffer(buf)
    mp = pts.unary_union
    centroids = []
    if isinstance(mp, Polygon):
        centroids.append(mp.centroid)
        bursts_numbers = 1
    else:
        _ = [centroids.append(p.centroid) for p in mp.geoms]
        bursts_numbers = len(mp.geoms)

    if bursts_extents:
        return [
            cascaded_union(
                [
                    geom
                    for geom in geoms
                    if centroid.buffer(buf).intersects(geom.centroid)
                ]
            )
            for centroid in centroids
        ]

    return bursts_numbers, centroids


def get_frame_df(csv_file):
    split_item = os.path.basename(csv_file[:-4]).split("_")
    frame_df = pd.read_csv(csv_file)
    gpd_df = gpd.GeoDataFrame(
        frame_df,
        crs={"init": "epsg:4326"},
        geometry=frame_df["geometry"].map(shapely.wkt.loads),
    )
    swath_extents = gpd_df.dissolve(by="swath")["geometry"]
    return {
        swt: {
            "track": int(split_item[1]),
            "frame": int(split_item[3]),
            "buffer": float(split_item[8]),
            "lat_width": float(split_item[6]),
            "swath": swt,
            "bursts_extents": count_bursts(frame_df, swt, bursts_extents=True),
            "centroids": count_bursts(frame_df, swt)[1],
            "total_bursts": count_bursts(frame_df, swt)[0],
            "extent": swath_extents[swt].wkt,
        }
        for swt in swath_extents.index.values
    }


def multiprocess_track_df(file_list, nprocs=1):
    track_data = pd.DataFrame()
    if nprocs == 1:
        for csv_file in file_list:
            data = get_frame_df(csv_file)
            for swt in data:
                track_data = track_data.append(data[swt], ignore_index=True)
        return track_data

    with pool(processes=nprocs) as proc:
        data = proc.starmap(get_frame_df, [(csv_file,) for csv_file in file_list])
        for dat in data:
            for swt in dat:
                track_data = track_data.append(dat[swt], ignore_index=True)
    return track_data


def check_swath_overlap(swath_df):
    swath_df.sort_values(by=["frame"])
    frames = swath_df["frame"].values
    swath_dict = dict()
    for idx, frame in enumerate(frames[:-1]):
        frame_dict = dict()
        extent_1 = shapely.wkt.loads(
            swath_df[swath_df.frame == frame]["extent"].values[0]
        )
        centroid_1 = swath_df[swath_df.frame == frame]["centroids"].values[0]
        extent_2 = shapely.wkt.loads(
            swath_df[swath_df.frame == frames[idx + 1]]["extent"].values[0]
        )
        # centroid_2 = swath_df[swath_df.frame == frames[idx+1]]['centroids'].values[0]
        extent = extent_1.intersection(extent_2)
        frame_dict["frame_overlap"] = frames[idx + 1]
        frame_dict["number_overlaps"] = len(
            [pt.within(extent) for pt in centroid_1 if pt.within(extent)]
        )
        frame_dict["number_bursts"] = swath_df[swath_df.frame == frame][
            "total_bursts"
        ].values[0]
        swath_dict[frame] = frame_dict
    return swath_dict


def get_all_tracks_data(rel_orbits, lat_widths, lat_buffers, csv_dir, nprocs=1):

    frame_names = list(range(1, 51))
    track_dict = dict()
    for i in range(len(rel_orbits)):
        tmp_dict = dict()
        for j in range(len(lat_widths)):
            for k in range(len(lat_buffers)):
                combinations = [
                    (lat_widths[j], lat_buffers[k], frame, rel_orbits[i])
                    for frame in frame_names
                ]
                csv_files = [
                    os.path.join(
                        csv_dir, "Track_{:03}_Frame_{:02}_D_lat_{}_buf_{}.csv"
                    ).format(val[3], val[2], str(val[0]), str(val[1]))
                    for val in combinations
                ]
                csv_files = [pth for pth in csv_files if os.path.exists(pth)]
                data_track = multiprocess_track_df(csv_files, nprocs=nprocs)
                print(
                    "done processing track {} {} {}".format(
                        rel_orbits[i], lat_widths[j], lat_buffers[k]
                    )
                )
                width_buff_key = "{}-{}".format(lat_widths[j], lat_buffers[k])
                temp_dict = dict()
                for swath in ["IW1", "IW2", "IW3"]:
                    swath_subset = data_track[data_track.swath == swath]
                    temp_dict[swath] = check_swath_overlap(swath_subset)
                tmp_dict[width_buff_key] = temp_dict
        track_dict[rel_orbits[i]] = tmp_dict

    df = pd.DataFrame()
    for track in track_dict:
        for width_buff in track_dict[track]:
            for swath in track_dict[track][width_buff]:
                for frame in track_dict[track][width_buff][swath]:
                    frame_data = track_dict[track][width_buff][swath][frame]
                    overlap_status = True
                    if not (float(frame) + 1.0 == float(frame_data["frame_overlap"])):
                        print(track, frame, frame_data["frame_overlap"])
                        overlap_status = False
                    df = df.append(
                        {
                            "track": track,
                            "lat_width": width_buff.split("-")[0],
                            "lat_buffer": width_buff.split("-")[1],
                            "swath": swath,
                            "frame": frame,
                            "overlap": overlap_status,
                            "intersect_frame": frame_data["frame_overlap"],
                            "number_bursts_overlap": frame_data["number_overlaps"],
                            "total_bursts": frame_data["number_bursts"],
                        },
                        ignore_index=True,
                    )
    return df


def get_frame_statistics(dataframe, track, lat_width, lat_buffer):
    def __stats(arr):
        return (
            np.rint(np.mean(arr)),
            np.rint(np.median(arr)),
            stats.mode(arr)[0][0],
            np.min(arr),
            np.max(arr),
        )

    if not isinstance(dataframe, pd.DataFrame):
        dataframe = pd.read_csv(dataframe)
    df_subset = dataframe[
        (dataframe.track == float(track))
        & (dataframe.lat_width == float(lat_width))
        & (dataframe.lat_buffer == float(lat_buffer))
        & (dataframe.overlap == 1.0)
    ]

    swath_summary = dict()
    for swath in set(df_subset["swath"].values):
        tmp_dict = dict()
        tmp_dict["total_bursts_stats"] = __stats(df_subset["total_bursts"].values)
        tmp_dict["overlap_bursts_stats"] = __stats(
            df_subset["number_bursts_overlap"].values
        )
        swath_summary[swath] = tmp_dict
    return swath_summary


def score_system(df):

    # condition 1 where minimum overlapped bursts between frames should be 1
    df.loc[df["minimum_overlap_bursts"] == 1.0, "c1"] = 5.0
    df.loc[df["minimum_overlap_bursts"] == 2.0, "c1"] = 4.0
    df.loc[df["minimum_overlap_bursts"] > 2.0, "c1"] = 0.0
    df.loc[df["minimum_overlap_bursts"] == 0.0, "c1"] = 0.0

    # condition 2 where mode total bursts in a frame should be >= 10
    df.loc[df["mode_total_bursts"] >= 10, "c2"] = 3.0
    df.loc[df["mode_total_bursts"] < 10, "c2"] = 0.0

    # condition 3 where mode overlapped bursts between frame is desired to be 2 or less (but greater than 1)
    df.loc[df["mode_overlap_bursts"] <= 2.0, "c3"] = 1.0
    df.loc[df["mode_overlap_bursts"] > 2.0, "c3"] = 0.0
    df.loc[df["mode_overlap_bursts"] < 1.0, "c3"] = 0.0

    # condition 4 minimum total bursts of width and buffer combination is
    # greater than the minimum from all the total bursts in a track
    df.loc[df["minimum_total_bursts"] > min(df["minimum_total_bursts"]), "c4"] = 1.0
    df.loc[df["minimum_total_bursts"] <= min(df["minimum_total_bursts"]), "c4"] = 0.0

    df["total_score"] = df.c1 + df.c2 + df.c3 + df.c4

    return df


def get_width_buffer_stat(df, lat_width, buffer):

    if not isinstance(df, pd.DataFrame):
        df = pd.read_csv(df)
    subset_df = df[
        (df.overlap == 1.0) & (df.lat_buffer == buffer) & (df.lat_width == lat_width)
    ]
    row_counts = len(subset_df.index)

    print(lat_width, buffer)
    total_bursts = subset_df.groupby(by=["total_bursts"]).count()["track"].to_dict()
    overlaps = (
        subset_df.groupby(by=["number_bursts_overlap"]).count()["track"].to_dict()
    )

    total_burst_percent = {
        burst: (total_bursts[burst] / row_counts) * 100 for burst in total_bursts
    }
    overlaps_percent = {
        overlap: (overlaps[overlap] / row_counts) * 100 for overlap in overlaps
    }

    return {"burst_percent": total_burst_percent, "overlap_percent": overlaps_percent}


def generate_report_summary(data, tracks, lat_widths, lat_buffers):
    df = pd.DataFrame()
    for track in tracks:
        for width in lat_widths:
            for buff in lat_buffers:
                results = get_frame_statistics(data, track, width, buff)
                if results:
                    for swath in results:
                        total_bursts_stats = results[swath]["total_bursts_stats"]
                        overlap_stats = results[swath]["overlap_bursts_stats"]
                        df = df.append(
                            {
                                "track": track,
                                "lat_width": width,
                                "lat_buffer": buff,
                                "swath": swath,
                                "mean_total_bursts": total_bursts_stats[0],
                                "median_total_bursts": total_bursts_stats[1],
                                "mode_total_bursts": total_bursts_stats[2],
                                "minimum_total_bursts": total_bursts_stats[3],
                                "maximum_total_bursts": total_bursts_stats[4],
                                "mean_overlap_bursts": overlap_stats[0],
                                "median_overlap_bursts": overlap_stats[1],
                                "mode_overlap_bursts": overlap_stats[2],
                                "minimum_overlap_bursts": overlap_stats[3],
                                "maximum_overlap_bursts": overlap_stats[4],
                            },
                            ignore_index=True,
                        )
    score_df = []
    high_score_df = []
    high_score_dict = dict()
    for track in tracks:
        temp = dict()
        for swath in ["IW1", "IW2", "IW3"]:
            sub_data = df[(df.swath == swath) & (df.track == track)]
            scored_df = score_system(sub_data)
            score_df.append(scored_df.sort_values(by=["total_score"], ascending=True))
            max_scores = sorted(set(scored_df["total_score"]))
            high_subset = scored_df[scored_df.total_score >= max_scores[-2]]
            temp[swath] = [
                "{}-{}".format(width, high_subset["lat_buffer"].values[idx])
                for idx, width in enumerate(high_subset["lat_width"].values)
            ]
            high_score_df.append(high_subset)

        high_score_dict[track] = temp
    # print(json.dumps(high_score_dict, indent=4))
    sets_of_width_buff = [
        set(high_score_dict[track][swath])
        for swath in high_score_dict[track]
        for track in high_score_dict
    ]
    common_vals = sets_of_width_buff[0].intersection(*sets_of_width_buff)

    for val in common_vals:
        val_dict = {
            val: get_width_buffer_stat(
                data, float(val.split("-")[0]), float(val.split("-")[1])
            )
        }
        print(json.dumps(val_dict, indent=4))

    # pd.concat(high_score_df).to_csv('high_score_summary_stats.csv')
    # pd.concat(score_df).to_csv('score_summary_stats.csv')

    for item in common_vals:
        width = float(item.split("-")[0])
        buff = float(item.split("-")[1])
        selected_df = df[(df.lat_width == width) & (df.lat_buffer == buff)]
        selected_df.sort_values(by=["track"]).to_csv("selected_csv_{}.csv".format(item))


def main():
    rel_orbits = [
        2,
        16,
        17,
        31,
        45,
        46,
        60,
        61,
        74,
        75,
        89,
        90,
        104,
        118,
        119,
        133,
        134,
        147,
        148,
        162,
        163,
    ]
    lat_widths = [1.25]
    lat_buffers = [0.01]
    dir_name = "/g/data/u46/users/pd1813/INSAR/dataframe_descending"
    df = get_all_tracks_data(
        rel_orbits[:], lat_widths[:], lat_buffers[:], dir_name, nprocs=1
    )
    # df.to_csv('all_track_frame_numbers.csv')
    # generate_report_summary('all_track_frame_numbers.csv', rel_orbits, lat_widths, lat_buffers)


if __name__ == "__main__":
    main()
