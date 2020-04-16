#!/usr/bin/env python

import sys  # RG add
import os
import re
import uuid
from typing import Optional, Union, Dict, Iterable
from pathlib import Path
from datetime import datetime

import structlog
import pandas as pd
import geopandas as gpd
import shapely.wkt
from shapely.geometry import Polygon
from shapely.ops import cascaded_union
import yaml
from insar.meta_data.s1_slc import Archive, SlcFrame, SlcMetadata

# _LOG = logging.getLogger(__name__)
_LOG = structlog.get_logger()


def generate_slc_metadata(
    slc_scene: Path, outdir: Optional[Path] = None, yaml_file: Optional[bool] = False
) -> Union[Dict, None]:
    """
    This method extracts slc metadata from scene.

    :param slc_scene: A 'Path' to slc scene
    :param outdir: A 'Path' to store yaml_file
    :param yaml_file: flag to write a yaml file with slc metadata

    :return:
        A 'dict' with slc metadata if not yaml_file else
        dumps to a yaml_file.
    """
    scene_obj = SlcMetadata(slc_scene)
    try:
        slc_metadata = scene_obj.get_metadata()
    except ValueError as err:
        raise ValueError(err)
    except AssertionError as err:
        raise AssertionError(err)

    keys = slc_metadata.keys()

    if "id" not in keys:
        slc_metadata["id"] = str(uuid.uuid4())
    if "product" not in keys:
        slc_metadata["product"] = {
            "name": "ESA_S1_{}".format(slc_metadata["properties"]["product"]),
            "url": scene_obj.scene,
        }

    if not yaml_file:
        return slc_metadata

    if outdir is None:
        outdir = os.getcwd()
    else:
        if not os.path.exists(outdir.as_posix()):
            os.makedirs(outdir.as_posix())
    with open(
        os.path.join(outdir, "{}.yaml".format(os.path.basename(slc_scene.as_posix())[:-4])), "w"
    ) as out_fid:
        yaml.dump(slc_metadata, out_fid)


def swath_bursts_extents(bursts_df, swt, buf=0.01, pol="VV") -> Iterable:
    """
    Method to form extents for overlapping bursts.

    Overlapped extents are formed if centroid with 'buf'
    degree buffer intersects with other centroid.

    :param bursts_df: geo-pandas data frame with burst information
    :param swt: name of the swath to subset this operations
    :param buf: buffer value to form buffer around the centroid point
    :param pol: name of polarization to subset this operation

    :return:
        A list of polygons formed as a result of this operation.
    """

    df_subset = bursts_df[(bursts_df.swath == swt) & (bursts_df.polarization == pol)]
    geoms = df_subset["geometry"]
    points = gpd.GeoSeries([geom.centroid for geom in geoms])

    pts = points.buffer(buf)
    mp = pts.unary_union
    centroids = []
    if isinstance(mp, Polygon):
        centroids.append(mp.centroid)
    else:
        for geom in mp.geoms:
            centroids.append(geom.centroid)
    return [
        cascaded_union(
            [geom for geom in geoms if centroid.buffer(buf).intersects(geom.centroid)]
        )
        for centroid in centroids
    ]


def db_query(
    archive: Archive,
    frame_num: int,
    frame_object: SlcFrame,
    query_args: Optional[Dict] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    columns_name: Optional[str] = None,
) -> gpd.GeoDataFrame:
    """
    A helper method to query into a database.

    Parameters
    ----------

    archive:
        An Archive object (/insar/metadata/s1_slc.py) initialised with a database.

    frame_num:
        Frame number associated with a track_frame of spatial query.

    frame_object:
        Frame definition object from SlcFrame.

    query_args:
        Optional query pair formed of database fieldnames and value to be queried.

    start_date: datetime object or None
        Optional start date of SLC acquisition to be queried.

    end_date: datetime object or None
        Optional end date of SLC acquisition to be queried.

    columns_name:
        field names associated with table in a database to be returned.

    Returns
    -------
        None or Geopandas dataframe of the Archive query of a frame associated with the frame number.
    """

    if columns_name is None:
        columns_name = [
            "{}.burst_number".format(archive.bursts_table_name),
            "{}.sensor".format(archive.slc_table_name),
            "{}.burst_extent".format(archive.bursts_table_name),
            "{}.swath_name".format(archive.swath_table_name),
            "{}.swath".format(archive.bursts_table_name),
            "{}.orbit".format(archive.slc_table_name),
            "{}.polarization".format(archive.bursts_table_name),
            "{}.acquisition_start_time".format(archive.slc_table_name),
            "{}.url".format(archive.slc_table_name),
        ]

    tables_join_string = (
        "{0} INNER JOIN {1} on {0}.swath_name = {1}.swath_name INNER JOIN {2} "
        "on {2}.id = {1}.id".format(
            archive.bursts_table_name, archive.swath_table_name, archive.slc_table_name
        )
    )

    min_date_arg = max_date_arg = None
    if start_date:
        min_date_arg = '{}.acquisition_start_time>=Datetime("{}")'.format(
            archive.slc_table_name, start_date
        )

    if end_date:
        max_date_arg = '{}.acquisition_start_time<=Datetime("{}")'.format(
            archive.slc_table_name, end_date
        )

    return archive.select(
        tables_join_string,
        orbit=None,
        args=query_args,
        min_date_arg=min_date_arg,
        max_date_arg=max_date_arg,
        columns=columns_name,
        frame_num=frame_num,
        frame_obj=frame_object,
        shapefile_name=None,
    )


def grid_definition(
    dbfile: Union[Path, str],
    out_dir: Union[Path, str],
    rel_orbit: int,
    sensor: Union[str, None],
    orbits: str,
    latitude_width: Optional[float] = -1.25,
    latitude_buffer: Optional[float] = 0.01,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    bbox_nlat: Optional[float] = 0.0,
    bbox_wlon: Optional[float] = 100.0,
    bbox_slat: Optional[float] = -50.0,
    bbox_elon: Optional[float] = 179.0,
    frame_numbers: Optional[Iterable] = None,
) -> None:
    """
    Generates a shape file for frame numbers associated with a rel orbit.

    A grid definition generated with available SLC bursts in dbfile for
    given sensor, orbit for particular relative orbit and frame numbers.

    Parameters
    ----------

    dbfile: Path, str
        A full path to a sqlite database with SLC metadata information.

    out_dir: Path, str
        A full path to store the grid-definition shape files.

    rel_orbit: int
        A Sentinel-1 relative orbit number.

    sensor: str, None
        Sentinel-1 (S1A) or (S1B) sensor. If None then both sensor's
        information are used to form a grid definition.

    orbits: str
        Ascending (A) or descending overpass to form the grid definition.

    latitude_width: float (default = -1.25)
        How wide the grid should span in latitude (in decimal degrees).

    latitude_buffer: float (default = 0.01)
        The buffer to include in latitude width to facilitate the overlaps needed
        between two grids along a relative orbit.

    start_date: datetime or None
        Optional start date of acquisition to account in forming a grid definition.

    end_date: datetime or None
        Optional end date of acquisition to account in forming a grid definition.

    bbox_nlat: float (default = 0.0)
        Northern latitude (decimal degrees) of bounding box

    bbox_wlon: float (default = 100.0)
        Western longitude (decimal degrees) of bounding box

    bbox_slat: float (default = -50.0)
        Southern latitude (decimal degrees) of bounding box

    bbox_elon: float (default = 179.0)
        Eastern longitude (decimal degrees) of bounding box

    frame_numbers: list or None
        Optional frame numbers to generate a grid definition.

    Returns
    -------
        None, however an ERSI shapefile is created
    """

    def _frame_def():
        bursts_query_args = {
            "bursts_metadata.relative_orbit": rel_orbit,
            "slc_metadata.orbit": orbits,
        }
        if sensor:
            bursts_query_args["slc_metadata.sensor"] = sensor

        gpd_df = db_query(
            archive=archive,
            frame_num=frame_num,
            frame_object=frame_obj,
            start_date=start_date,
            end_date=end_date,
            query_args=bursts_query_args,
        )

        if gpd_df is not None:
            grid_df = pd.DataFrame()
            swaths = gpd_df.swath.unique()

            # subsequent grid adjustment will not include the shapefile if
            # len(swaths) != 3. Hence a warning is provided for traceback
            if len(swaths) != 3:
                #print(gpd_df.columns.values)
                _LOG.warning(
                    "number of swaths != 3",
                    grid_shapefile=grid_shapefile,
                    swaths=swaths,
                    swath_number=len(swaths),
                    sentinel_files=", ".join(gpd_df.url.unique()),
                    xml_files=", ".join(gpd_df.swath_name.unique()),
                )

            for swath in swaths:
                bursts_extents = swath_bursts_extents(gpd_df, swath)
                sorted_extents = sorted(
                    [(burst, burst.centroid.y) for burst in bursts_extents],
                    key=lambda tup: tup[1],
                    reverse=True,
                )
                for idx, extent in enumerate(sorted_extents):
                    grid_df = grid_df.append(
                        {
                            "track": grid_track,
                            "frame": grid_frame,
                            "swath": swath,
                            "burst_num": idx + 1,
                            "extent": extent[0].wkt,
                        },
                        ignore_index=True,
                    )
            return gpd.GeoDataFrame(
                grid_df,
                crs={"init": "epsg:4326"},
                geometry=grid_df["extent"].map(shapely.wkt.loads),
            )

    with Archive(dbfile) as archive:
        if not os.path.exists(out_dir):
            os.mkdir(out_dir)

        # define SLC Frames once based on 
        # latitude width, buffer (overlap)
        # amount, and lat/lon of the 
        # region of interest
        frame_obj = SlcFrame(
            bbox_nlat=bbox_nlat,
            bbox_wlon=bbox_wlon,
            bbox_slat=bbox_slat,
            bbox_elon=bbox_elon,
            width_lat=latitude_width,
            buffer_lat=latitude_buffer
        )

        for frame_num in frame_obj.frame_numbers:

            grid_track = "T{:03}{}".format(rel_orbit, orbits)
            grid_frame = "F{:02}".format(frame_num)
            grid_shapefile = os.path.join(
                out_dir, "{}_{}.shp".format(grid_track, grid_frame)
            )
            grid_gpd = _frame_def()
            if grid_gpd is not None:
                grid_gpd.to_file(grid_shapefile, driver="ESRI Shapefile")


def grid_adjustment(
    in_grid_shapefile: Union[Path, str],
    out_grid_shapefile: Union[Path, str],
    track: str,
    frame: str,
    grid_before_shapefile: Optional[Path] = None,
    grid_after_shapefile: Optional[Path] = None,
):
    """
    Adjustment of a grid definition.

    This method performs a grid adjustment by removing first burst in swath 1
    and last burst from swath 3. Depending on the availability of grid before
    or after the grid that is being adjusted, a) if the grid before the current
    grid is available, then the last overlapping burst from grid before is
    added to current grid in swath 3, b) if grid after the current grid is
    available, then the first overlapping burst from grid after is added to the
    current grid in swath 1. c) Finally, one burst from each swath from the
    start (geographic north) of the grid are removed (this was deemed appropriate
    after observing the adjusted grid that there was minimum of two overlaps
    between the grids in each swaths. The requirement is to have at least one
    bursts overlap to allow mosaic formation in the post processing).

    :param in_grid_shapefile:
        A full path to a shape file that needs adjustment.
    :param out_grid_shapefile:
        A full path to output shapefile.
    :param track:
        A track name associated with in_grid_shapefile.
    :param frame:
        A frame name associated with in_grid_shapefile.
    :param grid_before_shapefile:
        A full path to a shapefile for grid definition before the
        in_grid_shapefile. The frame number should be one less than
        the in_grid_shapefile's frame number for descending overpass.
    :param grid_after_shapefile:
        A full path to a shapefile for grid definition after the
        in_grid_shapefile. The frame number should be one more than
        the in_grid_shapefile's frame number for descending overpass.
    """

    gpd_df = gpd.read_file(in_grid_shapefile)
    swaths = gpd_df.swath.unique()

    # only grid with all three swaths will be processed
    if len(swaths) != 3:
        _LOG.error(
            "number of swaths != 3",
            input_shapefile=in_grid_shapefile,
            swaths=swaths,
            swath_number=len(swaths),
        )
        raise ValueError

    iw1_df = gpd_df[gpd_df.swath == "IW1"].copy()
    iw2_df = gpd_df[gpd_df.swath == "IW2"].copy()
    iw3_df = gpd_df[gpd_df.swath == "IW3"].copy()

    # from swath 1 remove first burst number
    iw1_new = iw1_df.drop(
        iw1_df[iw1_df.burst_num == min(iw1_df.burst_num.values)].index
    )

    # from swath 3 remove last burst number
    iw3_new = iw3_df.drop(
        iw3_df[iw3_df.burst_num == max(iw3_df.burst_num.values)].index
    )

    # if grid exists before the current grid then add the last overlapping burst
    # from grid before to the current grid in swath 3
    if grid_before_shapefile:
        iw3_extents = cascaded_union([geom for geom in iw3_new.geometry])
        gpd_before = gpd.read_file(Path(grid_before_shapefile).as_posix())
        iw3_before = gpd_before[gpd_before.swath == "IW3"].copy()
        bursts_numbers = list(iw3_before.burst_num.values)

        for idx, row in iw3_before.iterrows():
            row_centroid = row.geometry.centroid
            if iw3_extents.contains(row_centroid):
                bursts_numbers.remove(row.burst_num)

        if bursts_numbers:
            iw3_new = iw3_new.append(
                iw3_before[iw3_before.burst_num == max(bursts_numbers)],
                ignore_index=True,
            )

    # if grid after exists before the current grid then add first overlapping burst
    # from grid after to the current grid in swath 1
    if grid_after_shapefile:
        iw1_extents = cascaded_union([geom for geom in iw1_new.geometry])
        gpd_after = gpd.read_file(Path(grid_after_shapefile).as_posix())
        iw1_after = gpd_after[gpd_after.swath == "IW1"].copy()
        bursts_numbers = list(iw1_after.burst_num.values)

        for idx, row in iw1_after.iterrows():
            row_centroid = row.geometry.centroid
            if iw1_extents.contains(row_centroid):
                bursts_numbers.remove(row.burst_num)
        if bursts_numbers:
            iw1_new = iw1_new.append(
                iw1_after[iw1_after.burst_num == min(bursts_numbers)], ignore_index=True
            )

    grid_df = pd.DataFrame()

    # remove one bursts each in swaths to minimise overlaps
    for df in [iw1_new, iw2_df, iw3_new]:
        iw_df = pd.DataFrame()
        for idx, row in df.iterrows():
            if row.geometry.centroid.y != max(
                [geom.centroid.y for geom in df.geometry]
            ):
                iw_df = iw_df.append(row, ignore_index=True)
        try:
            sorted_bursts = sorted(
                [(geom, geom.centroid.y) for geom in iw_df.geometry],
                key=lambda tup: tup[1],
                reverse=True,
            )
        except AttributeError as err:
            raise err

        for idx, burst in enumerate(sorted_bursts):
            grid_df = grid_df.append(
                {
                    "track": track,
                    "frame": frame,
                    "swath": iw_df.swath.unique()[0],
                    "burst_num": idx + 1,
                    "extent": burst[0].wkt,
                },
                ignore_index=True,
            )
    new_gpd_df = gpd.GeoDataFrame(
        grid_df,
        crs={"init": "epsg:4326"},
        geometry=grid_df["extent"].map(shapely.wkt.loads),
    )
    new_gpd_df.to_file(out_grid_shapefile, driver="ESRI Shapefile")
