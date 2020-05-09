#!/usr/bin/env python

import sys  # RG add
import os
import re
import uuid
import random
from typing import Optional, Union, Dict, Iterable
from pathlib import Path
from datetime import datetime

import pandas as pd
import geopandas as gpd
import shapely.wkt
from shapely.geometry import Polygon
from shapely.ops import cascaded_union
import structlog
import yaml
from insar.meta_data.s1_slc import Archive, SlcFrame, SlcMetadata, Generate_kml
from insar.logs import get_wrapped_logger

_LOG = structlog.get_logger("insar")


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

    columns_name: str or None
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
    create_kml: bool,
    orbits: Optional[str] = "D",
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

    create_kml: bool
        True saves kml containing the bursts selected for each frame.
        False does not save kmls

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
    # create a random  hex that will be used
    # to color the burst polygons in the kml
    r = lambda: random.randint(0,255)
    random_hex = "FF%02X%02X%02X" % (r(),r(),r())  # replacing the leading # with FF

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

            if create_kml:
                # add frame extent polygon to kml
                master_kml.add_polygon(
                    polygon_name="Frame_{:02}".format(frame_num),
                    polygon_coords=frame_obj.get_frame_coords_list(frame_num),
                    polygon_width=4,
                    tranparency=0.1,
                    colour="ff0000ff",
                )

                burst_coord_list = [
                    list(shapely.wkt.loads(burst_polys).exterior.coords)
                    for burst_polys in gpd_df["AsText(bursts_metadata.burst_extent)"]
                ]
                # burst_coord_list = [poly1, ..., polyN]
                #    where poly1 = [(lon1,lat1), ..., (lonN,latN), (lon1,lat1)], etc

                # add polygons to kml with a random colour
                master_kml.add_multipolygon(
                    polygon_name="Bursts_in_Frame_{:02}".format(frame_num),
                    polygon_list=burst_coord_list,
                    polygon_width=3,
                    tranparency=0.3,
                    colour=random_hex,
                )

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
                bursts_extents = swath_bursts_extents(
                    bursts_df=gpd_df,
                    swt=swath,
                    buf=latitude_buffer,
                )  # pol='VV' ?
                # when pol (i.e. polarisation) is not specified, bursts_extents
                # defaults to 'VV'. If gpd_df does not contain bursts with 'VV'
                # polarisation then bursts_extents=[], and  nothing is appended
                # to grid_df. If this occurs for all  subswaths then grid_df is
                # empty and _frame_def returns None
                
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

            if grid_df.empty:
                _LOG.error(
                    "empty grid_df inside _frame_def() [/insar/meta_data/s1_gridding_utils.py]",
                    frame_num=frame_num,
                    rel_orbit=rel_orbit,
                    polarisations_in_grid=list(set(gpd_df.polarization)),
                    swaths=swaths,
                )
                return None

            else:
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

        grid_track = "T{:03}{}".format(rel_orbit, orbits)

        # Initiate kml even user doesn't want to save them
        # Creating a kml file per relative orbit to minimise the amount of files
        master_kml = Generate_kml()
        gpd_cnt = 0

        for frame_num in frame_obj.frame_numbers:

            grid_frame = "F{:02}".format(frame_num)
            grid_shapefile = os.path.join(
                out_dir, "{}_{}.shp".format(grid_track, grid_frame)
            )

            grid_gpd = _frame_def()
            if grid_gpd is not None:
                gpd_cnt+=1
                grid_gpd.to_file(grid_shapefile, driver="ESRI Shapefile")


        if create_kml and gpd_cnt > 0:
            # add ROI polygon
            ROI_lons = [bbox_wlon, bbox_elon, bbox_elon, bbox_wlon, bbox_wlon]
            ROI_lats = [bbox_nlat, bbox_nlat, bbox_slat, bbox_slat, bbox_nlat]
            master_kml.add_polygon(
                polygon_name="ROI",
                polygon_coords=[xy for xy in zip(ROI_lons, ROI_lats)],
                polygon_width=5,
                tranparency=0,
                colour="ffff0000",
            )

            # create kml filename, e.g. T060D_F01_to_F22.kml
            kml_filename = Path(
                os.path.join(out_dir, "{0}_F{1:02}_to_F{2:02}.kml".format(
                    grid_track,
                    frame_obj.frame_numbers[0],
                    frame_obj.frame_numbers[-1]
                    )
                )
            )

            # save kml
            master_kml.save_kml(kml_filename)

            if os.path.exists(kml_filename):
                _LOG.info(
                    "kml file created",
                    output_kml_file=kml_filename,
                )
            else:
                _LOG.error(
                    "failed to create kml file",
                    output_kml_file=kml_filename,
                )



def grid_adjustment(
    in_grid_shapefile: Union[Path, str],
    out_grid_shapefile: Union[Path, str],
    create_kml: bool,
    track: str,
    frame: str,
    grid_before_shapefile: Optional[Path] = None,
    grid_after_shapefile: Optional[Path] = None,
):
    """
    Adjustment of a grid definition.

    Let the current grid be indexed as k, while the grids before and
    after the current grid indexed as k-1 and k+1 respectively.

    This grid adjustment method begins by removing the first burst from swath 1
    (IW1)  and the last burst from swath 3 (IW3), depending on the availability
    of the k-1 or  the k+1 grids:  (a)  if the k-1 grid  is available, then the
    last overlapping burst from the k-1 grid is added to IW3 of grid k;  (b) if
    k+1 is  available, the first  overlapping burst from k+1 is added to IW1 of
    grid k; (c) finally, the northern-most burst from each swath of a grid are
    removed. This was deemed appropriate after observing that there were a
    minimum of two overlapping bursts between the grids in each swath. Whereas
    the requirement is to have at least one burst overlap to allow mosaic
    formation

    Parameters
    ----------

    in_grid_shapefile: Path
        A full path to a shape file that needs adjustment.

    out_grid_shapefile: Path
        A full path to output shapefile.

    create_kml: bool
        Create kml (True or False). kml files are created in out_grid_shapefile

    track: str
        A track name associated with in_grid_shapefile.

    frame: str
        A frame name associated with in_grid_shapefile.

    grid_before_shapefile: Path or None
        A full path to a shapefile for grid definition before the
        in_grid_shapefile. The frame number should be one less than
        the in_grid_shapefile's frame number for descending overpass.

    grid_after_shapefile: Path or None
        A full path to a shapefile for grid definition after the
        in_grid_shapefile. The frame number should be one more than
        the in_grid_shapefile's frame number for descending overpass.

    """

    # create a random  hex that will be used
    # to color the burst polygons in the kml
    r = lambda: random.randint(0,255)
    random_hex = "FF%02X%02X%02X" % (r(),r(),r())  # replacing the leading # with FF

    def _add_overlapping_burst_to_grid_k(
        iw_df,
        iw_name,
        adjacent_grid_shp
    ):
        """

        Parameters
        ----------

        iw_df: geopandas dataframe
           dataframe of grid k
           
        iw_name: str
           subswath name {IW1 or IW3}

        adjacent_grid_shp: Path or None
           Path of the shapefile of the k-1 or k+1 grid.

        Return
        ------

        new_iw_df: geopandas dataframe
            the modified geopandas dataframe that has the additional burst(s)
        """
        if iw_name == "IW1":
            # if IW1: remove the first burst from swath 1
            new_iw_df = iw_df.drop(
                iw_df[iw_df.burst_num == min(iw_df.burst_num.values)].index
            )
        elif iw_name == "IW3":
            # if IW3: remove last burst from swath 3
            new_iw_df = iw_df.drop(
                iw_df[iw_df.burst_num == max(iw_df.burst_num.values)].index
            )
        else:
            return None

        if adjacent_grid_shp:
            # append burst to new_iw_df
            iw_extents = cascaded_union([geom for geom in new_iw_df.geometry])

            adjacent_gpd = gpd.read_file(Path(adjacent_grid_shp).as_posix())
            adjacent_iw = adjacent_gpd[adjacent_gpd.swath == iw_name].copy()

            bursts_numbers = list(adjacent_iw.burst_num.values)

            for idx, row in adjacent_iw.iterrows():
                row_centroid = row.geometry.centroid
                if iw_extents.contains(row_centroid):
                    bursts_numbers.remove(row.burst_num)

            if bursts_numbers:
                match_burst_num = max(bursts_numbers)  # append last burst for IW3

                if iw_name == "IW1":
                    match_burst_num = min(bursts_numbers)  # append first burst for IW1

                new_iw_df = new_iw_df.append(
                    adjacent_iw[adjacent_iw.burst_num == match_burst_num],
                    ignore_index=True,
               )

        return new_iw_df


    gpd_df = gpd.read_file(in_grid_shapefile)
    swaths = gpd_df.swath.unique()

    # only grids containing IW1, IW2 and IW3 swaths will be processed
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

    # if k-1 grid exists: add the last overlapping burst to IW3 of current grid
    iw3_new = _add_overlapping_burst_to_grid_k(iw3_df, "IW3", grid_before_shapefile)

    # if k+1 grid exists: add first overlapping burst to IW1 of current grid
    iw1_new = _add_overlapping_burst_to_grid_k(iw1_df, "IW1", grid_after_shapefile)

    # remove the northern-most burst in each swath to minimise overlaps
    grid_df = pd.DataFrame()
    for df in [iw1_new, iw2_df, iw3_new]:

        iw_df = pd.DataFrame()
        northernmost_lat = max([geom.centroid.y for geom in df.geometry])

        for idx, row in df.iterrows():
            if row.geometry.centroid.y != northernmost_lat:
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

    if create_kml:
        out_kmlfile = Path(os.path.splitext(out_grid_shapefile)[0]+"_adj.kml")

        burst_coord_list = [
            list(shapely.wkt.loads(burst_polys).exterior.coords)
            for burst_polys in new_gpd_df["extent"]
        ]
        # burst_coord_list = [poly1, ..., polyN]
        #    where poly1 = [(lon1,lat1), ..., (lonN,latN), (lon1,lat1)], etc

        # add polygons to kml with a random colour
        adj_kml = Generate_kml()
        adj_kml.add_multipolygon(
            polygon_name="Bursts_in_{}".format(frame),
            polygon_list=burst_coord_list,
            polygon_width=3,
            tranparency=0.3,
            colour=random_hex,
        )

        # save kml
        adj_kml.save_kml(out_kmlfile)

        if os.path.exists(out_kmlfile):
            _LOG.info(
                "kml file created",
                output_kml_file=out_kmlfile,
            )
        else:
            _LOG.error(
                "failed to create kml file",
                output_kml_file=out_kmlfile,
            ) 
