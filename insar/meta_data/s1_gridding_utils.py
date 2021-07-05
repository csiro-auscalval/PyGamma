#!/usr/bin/env python

import sys  # RG add
import os
import re
import uuid
import random
import structlog
from typing import Optional, Union, Dict, Iterable
from pathlib import Path
from datetime import datetime

import pandas as pd
import geopandas as gpd
import shapely.wkt
from shapely.geometry import Polygon
from shapely.ops import cascaded_union
import yaml
from insar.meta_data.s1_slc import Archive, SlcFrame, SlcMetadata, Generate_kml
from insar.logs import get_wrapped_logger
from insar.meta_data.metadata_diagnosis import diagnose

_LOG = structlog.get_logger("insar")


def generate_slc_metadata(
    slc_scene: Path,
    outdir: Optional[Path] = None,
    yaml_file: Optional[bool] = False,
    max_retries: Optional[int] = 30,
) -> Union[Dict, None]:
    """
    generate_slc_metadata extracts slc metadata from a S1 zip file
    denoted as slc_scene. This function is used in the 
    slc-ingestion and ard_insar commands.

    Intermittent issues with extracting burst metadata from xml files
    using pygamma has necessitated the creation of a slc metadata
    diagnosis tool. This tool has been successful at identifying
    slc metadata that does not have essential information. In the
    workflow, the generate_slc_metadata() function in
    insar.meta_data.s1_gridding_utils is used to insert slc metadata
    into either a yaml or directly into a sqlite database. As such,
    this is a potential place to include the diagnosis tool and
    retries.

    Parameters
    ----------

    slc_scene: Path
        Full path to a S1 zip file

    outdir: Path or None
        An output directory to store yaml_file

    yaml_file: {True | False} or None
        A bool flag to write a yaml file containing slc metadata

    max_retries: int
        The number of slc metadata extraction retries

    Returns
    -------
        if yaml_file is False then a  "dict"  containing slc
        metadata is returned, else the "dict" is dumped into
        a yaml file and None is returned.
    """
    # Do not exit the while loop until the slc-metadata has
    # all the necessary information or max_retries is reached
    retry_cnt = 0
    while retry_cnt < max_retries:
        _LOG.info(
            "creating slc-metadata", S1_scene=slc_scene, retry=retry_cnt,
        )

        # ----- get slc_metadata ----- #
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

        # diagnose slc_metadata dict to ensure that it has required metadata.
        if diagnose(slc_metadata, slc_scene):
            # returns True for pass, or False for fail
            # exit while look if slc_metadata has passed
            break

        retry_cnt += 1

    if retry_cnt >= max_retries:
        _LOG.error(
            "error: max. retries hit for slc-metadata creation",
            S1_scene=slc_scene,
            num_retries=retry_cnt,
        )
    else:
        _LOG.info(
            "slc-metadata created and passed checks",
            S1_scene=slc_scene,
            num_retries=retry_cnt,
        )

    # What should occur if max retries is reached? should
    # the slc-metadata be saved??

    # --------------------------- #
    #  Save slc-metadata as yaml  #
    #    or store in sqlite db    #
    # --------------------------- #
    if not yaml_file:
        return slc_metadata

    if outdir is None:
        outdir = os.getcwd()
    else:
        if not os.path.exists(outdir.as_posix()):
            os.makedirs(outdir.as_posix())
    with open(
        os.path.join(
            outdir, "{}.yaml".format(os.path.basename(slc_scene.as_posix())[:-4]),
        ),
        "w",
    ) as out_fid:
        yaml.dump(slc_metadata, out_fid)


def swath_bursts_extents(bursts_df, swt, buf=0.01, pol="VV",) -> Iterable:
    """
    Method to form extents for overlapping bursts.

    Overlapped extents are formed if centroid with 'buf'
    degree buffer intersects with other centroid.

    Parameters
    ----------

    bursts_df: gpd.GeoDataFrame
        geo-pandas data frame with burst information

    swt: str
        name of the swath to subset this operations

    buf: float
        buffer value (decimal degrees) to form buffer
        around the centroid point

    pol: str
        name of polarization to subset this operation

    Returns
    -------
        A list of polygons formed as a result of this
        operation.
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
        An Archive object (/insar/metadata/s1_slc.py) initialised with
        a database.

    frame_num:
        Frame number associated with a track_frame of spatial query.

    frame_object:
        Frame definition object from SlcFrame.

    query_args:
        Optional query pair formed of database fieldnames and value to
        be queried.

    start_date: datetime object or None
        Optional start date of SLC acquisition to be queried.

    end_date: datetime object or None
        Optional end date of SLC acquisition to be queried.

    columns_name: str or None
        field names associated with table in a database to be returned.

    Returns
    -------
        None or Geopandas dataframe of the Archive query of a frame
        associated with the frame number.
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
            "{}.slc_extent".format(archive.slc_table_name),
            "{}.row_extent".format(archive.slc_rows_table_name),
            "{}.row_id".format(archive.slc_rows_table_name),
        ]

    tables_join_string = (
        "{0} "
        "INNER JOIN {1} ON {0}.swath_name = {1}.swath_name "
        "INNER JOIN {2} ON {2}.id = {1}.id "
        "INNER JOIN {3} ON {3}.row_id = {0}.row_id ".format(
            archive.bursts_table_name,
            archive.swath_table_name,
            archive.slc_table_name,
            archive.slc_rows_table_name,
        )
    )

    min_date_arg = max_date_arg = None
    if start_date:
        min_date_arg = '{}.acquisition_start_time>=Datetime("{}")'.format(
            archive.slc_table_name, start_date,
        )

    if end_date:
        max_date_arg = '{}.acquisition_start_time<=Datetime("{}")'.format(
            archive.slc_table_name, end_date,
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


def grid_from_frame(
    archive,
    frame_object,
    frame_num,
    rel_orbit,
    sensor,
    orbits,
    latitude_buffer,
    start_date,
    end_date,
    grid_track,
    grid_frame,
    grid_shapefile,
) -> Union[gpd.GeoDataFrame, None]:
    """
    Generates a grid from the frame number, slc database (via the
    variable named archive), relative orbit number, sensor, orbit
    mode, latitude buffer and start and end query dates.

    Parameters
    ----------

    archive: s1_slc.Archive object
        An Archive object (/insar/metadata/s1_slc.py) initialised with
        a database.

    frame_object: SlcFrame object
        Frame definition object from SlcFrame.

    frame_num: int
        Frame number associated with a track_frame of spatial query.

    rel_orbit: int
        A Sentinel-1 relative orbit number.

    sensor: str, None
        Sentinel-1 (S1A) or (S1B) sensor. If None then both sensor's
        information are used to form a grid definition.

    orbits: str
        Ascending (A) or descending (D) overpass to form the grid
        definition.

    latitude_buffer: float (default = 0.01)
        The buffer (decimal degrees) used to facilitate the
        overlaps needed between two grids along a relative orbit.

    start_date: datetime or None
        Start date of acquisition to account in forming a
        grid definition.

    end_date: datetime or None
        End date of acquisition to account in forming a grid
        definition.

    grid_track: str
        Name of track as string, e.g T118D

    grid_frame: str
        Frame number as string, e.g. F01, F02, etc

    grid_shapefile: str
        filename of shapefile

    Returns
    -------
        None or geopandas dataframe
    """

    bursts_query_args = {
        "bursts_metadata.relative_orbit": rel_orbit,
        "slc_metadata.orbit": orbits,
    }
    if sensor:
        bursts_query_args["slc_metadata.sensor"] = sensor

    # query the database to get bursts
    # that intersect the current frame
    bursts_df = db_query(
        archive=archive,
        frame_num=frame_num,
        frame_object=frame_object,
        start_date=start_date,
        end_date=end_date,
        query_args=bursts_query_args,
    )
    # bursts_df has the following column names:
    #   burst_number, sensor, AsText(bursts_metadata.burst_extent),
    #   swath_name, swath, orbit, polarization, acquisition_start_time
    #   url, geometry

    if bursts_df is not None:
        grid_df = pd.DataFrame()
        swaths = bursts_df.swath.unique()

        # subsequent grid adjustment will not include the shapefile if
        # len(swaths) != 3. Hence a warning is provided for traceback
        if len(swaths) != 3:
            _LOG.warning(
                "number of swaths != 3",
                grid_shapefile=grid_shapefile,
                swaths=swaths,
                swath_number=len(swaths),
                sentinel_files=", ".join(bursts_df.url.unique()),
                xml_files=", ".join(bursts_df.swath_name.unique()),
            )

        for swath in swaths:
            bursts_extents = swath_bursts_extents(
                bursts_df=bursts_df, swt=swath, buf=latitude_buffer,
            )
            # when pol (i.e. polarisation) is not specified,
            # bursts_extents defaults to 'VV'. If bursts_df
            # does not contain  bursts with 'VV' pol. then
            # bursts_extents = [], and nothing is appended
            # to grid_df. If this occurs for all subswaths
            # then grid_df is empty and grid_from_frame
            # returns None

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
                "empty grid dataframe in s1_gridding_utils.grid_from_frame()",
                frame_num=frame_num,
                rel_orbit=rel_orbit,
                polarisations_in_grid=list(set(bursts_df.polarization)),
                swaths=swaths,
            )
            return None

        else:
            return gpd.GeoDataFrame(
                grid_df,
                crs={"init": "epsg:4326"},
                geometry=grid_df["extent"].map(shapely.wkt.loads),
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
    Generates a shapefile for all frames contained in the specified
    relative orbit number. These  shapefiles contain information of
    the  SLC grids. These grids  are generated  with available  SLC
    bursts contained  in the dbfile  for a specified  sensor, orbit
    mode.  Factors influencing  the size of the  grids include  its
    latitude width and overlap (or buffer) with adjacent grids. The
    grid definition  is unique to the region  of interest, which is
    defined by lat/lon coordinates (bbox_nlat, bbox_wlon, bbox_slat
    bbox_elon). Along  with shapefiles, the user  may opt to create
    kml files for easy viewing on Google Earth.

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
        Ascending (A) or descending (D) overpass to form the grid
        definition.

    create_kml: bool
        True saves kml containing the bursts selected for each frame.
        False does not save kmls

    latitude_width: float (default = -1.25)
        How wide the grid should span in latitude (in decimal degrees).

    latitude_buffer: float (default = 0.01)
        The buffer to include in latitude width to facilitate the
        overlaps needed between two grids along a relative orbit.

    start_date: datetime or None
        Optional start date of acquisition to account in forming a grid
        definition.

    end_date: datetime or None
        Optional end date of acquisition to account in forming a grid
        definition.

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
        The code currently extracts the frame numbers from
        the SlcFrame class. Hence, even if the frame numbers
        are supplied here, they will not be used.

    Returns
    -------
        None, however an ERSI shapefile is created
    """

    def _move_failed_shp(
        shp_outdir, failed_grid_shapefile,
    ):
        # move shapefiles to a folder called "unsuitable" so that
        # they are not included in the search duing grid adjustment.
        shp_base = os.path.splitext(os.path.basename(failed_grid_shapefile))[0]
        # shp_base = T118D_F16 etc

        unsuit_dir = os.path.join(shp_outdir, "unsuitable")
        if not os.path.exists(unsuit_dir):
            os.mkdir(unsuit_dir)

        # find all shape files that match _shpbase
        for f in os.listdir(shp_outdir):
            if f.startswith(shp_base):
                # use os.rename to move file. Apparently,
                # shutil.move calls os.rename in most cases
                os.rename(
                    os.path.join(shp_outdir, f), os.path.join(unsuit_dir, f),
                )
                # log
                _LOG.info(
                    "moving shapefile with an unsatisfactory grid",
                    shapefile=f,
                    moved_dir=unsuit_dir,
                )

    def _remove_duplicates(
        _adjacent_gdf, _current_grid_shp,
    ):
        # Remove rows in _current_grid that exist in
        # _adjacent_gdf. To do this, the geometry
        # column name is used.
        # geometry:
        #     POLYGON ((lon1 lat1, lon2 lat2, ..., lonN latN))
        # Because these burst polygons are very similar in
        # shape and footprint and only partially overlap,
        # the centroid can be used to identify duplicate
        # polygons.
        _current_gdf = gpd.read_file(_current_grid_shp)

        _adjacent_centroid_list = [
            list(x.centroid.coords)[0] for x in _adjacent_gdf.geometry
        ]

        _current_centroid_list = [
            list(x.centroid.coords)[0] for x in _current_gdf.geometry
        ]

        duplicate_index = []
        for _i, _current_centroid in enumerate(_current_centroid_list):
            if _current_centroid in _adjacent_centroid_list:
                duplicate_index.append(_i)

        # remove these rows from _current_gdf
        _current_gdf.drop(index=duplicate_index, inplace=True)
        return _current_gdf

    # Create a random  hex that will be used to colour
    # the burst polygons in the kml. For Google Earth,
    # the leading # needs to be replaced with 'FF'
    r = lambda: random.randint(0, 255)
    random_hex = "FF%02X%02X%02X" % (r(), r(), r())

    # load the dbfile using s1_slc.Archive
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
            buffer_lat=latitude_buffer,
        )

        grid_track = "T{:03}{}".format(rel_orbit, orbits)

        gpd_cnt = 0
        grid_shp_list = []
        grid_meet_req = []
        grid_shp_move = []
        for frame_num in frame_obj.frame_numbers:

            grid_frame = "F{:02}".format(frame_num)
            grid_shapefile = os.path.join(
                out_dir, "{}_{}.shp".format(grid_track, grid_frame),
            )

            # create grids based on frames
            grid_gpd = grid_from_frame(
                archive,
                frame_obj,
                frame_num,
                rel_orbit,
                sensor,
                orbits,
                latitude_buffer,
                start_date,
                end_date,
                grid_track,
                grid_frame,
                grid_shapefile,
            )

            if grid_gpd is not None:
                gpd_cnt += 1
                grid_gpd.to_file(grid_shapefile, driver="ESRI Shapefile")

                grid_shp_list.append(grid_shapefile)
                swath_series = grid_gpd.swath.to_list()
                num_iw1 = swath_series.count("IW1")
                num_iw2 = swath_series.count("IW2")
                num_iw3 = swath_series.count("IW3")
                if (num_iw1 < 9) or (num_iw2 < 9) or (num_iw3 < 9):
                    grid_meet_req.append(False)
                    grid_shp_move.append(grid_shapefile)
                    # grid_meet_req.append(True)
                else:
                    grid_meet_req.append(True)
                    # create kml file

        # ----------------------------------------------------- #
        #  Merge those grids that have < 9 bursts  along-track  #
        #  to adjacent grids. This is done here rather than in  #
        #  grid_adjustment in case adjustment  stage is deemed  #
        #  unecessary later.                                    #
        # ----------------------------------------------------- #
        for k, grid_shapefile in enumerate(grid_shp_list):
            if grid_meet_req[k] is False:
                # merge with adjacent k-1 grid if it exists.
                # else merge with adjacent k+1
                if k == 0:
                    adjacent_grid_shp = grid_shp_list[k + 1]
                else:
                    adjacent_grid_shp = grid_shp_list[k - 1]

                adjacent_grid_df = gpd.read_file(adjacent_grid_shp)

                # Remove rows in current grid that exist in adjacent
                # grid. Note, new_adjacent_grid_df.drop_duplicates()
                # didn't seem to work.
                current_grid_df = _remove_duplicates(adjacent_grid_df, grid_shapefile,)

                # append kth grid to adjacent grid
                new_adjacent_grid_df = adjacent_grid_df.append(
                    current_grid_df, ignore_index=True,
                )

                # overwrite adjacent grid
                new_adjacent_grid_df.to_file(
                    adjacent_grid_shp, driver="ESRI Shapefile",
                )

                # add to log
                _LOG.info(
                    "grid does not meet requirement, merging with adjacent",
                    current_grid_shp=grid_shapefile,
                    adjacent_grid_shp=adjacent_grid_shp,
                )

        # rename associated shapefiles and log
        for grid_shapefile in grid_shp_move:
            _move_failed_shp(out_dir, grid_shapefile)

        # remove these "unsatisfactory" shapefiles from list
        updated_grid_shp = [
            f_shp for f_shp in grid_shp_list if f_shp not in grid_shp_move
        ]

        # ------------------------------- #
        #           create kmls           #
        # create kmls if >= 1 frame exist #
        # ------------------------------- #
        if create_kml and gpd_cnt > 0:
            primary_kml = Generate_kml()

            # add ROI polygon
            ROI_lons = [bbox_wlon, bbox_elon, bbox_elon, bbox_wlon, bbox_wlon]
            ROI_lats = [bbox_nlat, bbox_nlat, bbox_slat, bbox_slat, bbox_nlat]
            primary_kml.add_polygon(
                polygon_name="ROI",
                polygon_coords=[xy for xy in zip(ROI_lons, ROI_lats)],
                polygon_width=5,
                tranparency=0,
                colour="ffff0000",
            )

            # add Frames
            for frame_num in frame_obj.frame_numbers:
                primary_kml.add_polygon(
                    polygon_name="Frame_{:02}".format(frame_num),
                    polygon_coords=frame_obj.get_frame_coords_list(frame_num),
                    polygon_width=4,
                    tranparency=0.1,
                    colour="ff0000ff",
                )

            # add bursts:
            for grid_shapefile in updated_grid_shp:
                grid_gpd = gpd.read_file(grid_shapefile)
                Frames_in_grid = "_".join(list(set(grid_gpd.frame)))

                burst_coord_list = [
                    list(burst_polys.exterior.coords) for burst_polys in grid_gpd.geometry
                ]
                # burst_coord_list = [poly1, ..., polyN]
                #    poly1 = [(lon1,lat1),
                #              ...,
                #             (lonN,latN),
                #             (lon1,lat1)]

                # add polygons to kml with a random colour
                primary_kml.add_multipolygon(
                    polygon_name="Bursts_in_{}".format(Frames_in_grid),
                    polygon_list=burst_coord_list,
                    polygon_width=3,
                    tranparency=0.3,
                    colour=random_hex,
                )

            # create kml filename, e.g. T060D_F01_to_F22.kml
            kml_filename = Path(
                os.path.join(
                    out_dir,
                    "{0}_F{1:02}_to_F{2:02}.kml".format(
                        grid_track,
                        frame_obj.frame_numbers[0],
                        frame_obj.frame_numbers[-1],
                    ),
                )
            )

            # save kml
            primary_kml.save_kml(kml_filename)

            if os.path.exists(kml_filename):
                _LOG.info(
                    "kml file created", output_kml_file=kml_filename,
                )
            else:
                _LOG.error(
                    "failed to create kml file", output_kml_file=kml_filename,
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
    after the current grid indexed as k-1 and k+1 respectively. Each
    grid must have three sub-swaths (IW1, IW2 and IW3) with at least
    nine bursts along-track.

    This grid  adjustment method  begins by removing the first  burst
    from sub-swath 1 (IW1) and the last burst from sub-swath 3 (IW3),
    depending on the availability of the k-1 or k+1 grids: (a) if the
    k-1  grid is available, then the last  overlapping burst from the
    k-1 grid is added to IW3 of grid k; (b) if k+1 is  available, the
    first overlapping  burst from k+1 is added  to IW1 of grid k; (c)
    finally,  the northern-most burst  from each swath of  a grid are
    removed. This was deemed  appropriate after  observing that there
    were a minimum of two  overlapping bursts  between grids in  each
    swath. The requirement is to have at least one burst overlap to
    allow mosaic formation

    Parameters
    ----------

    in_grid_shapefile: Path
        A full path to a shape file that needs adjustment.

    out_grid_shapefile: Path
        A full path to output kml and shapefiles.

    create_kml: bool
        Create kml (True or False). kml files are created in the
        directory out_grid_shapefile

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

    # Create a random  hex that will be used to colour
    # the burst polygons in the kml. For Google Earth,
    # the leading # needs to be replaced with 'FF'
    r = lambda: random.randint(0, 255)
    random_hex = "FF%02X%02X%02X" % (r(), r(), r())

    def _add_overlapping_burst_to_grid_k(
        iw_df, iw_name, adjacent_grid_shp,
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
            the modified geopandas dataframe that has the
            additional burst(s)
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
                # append last burst for IW3
                match_burst_num = max(bursts_numbers)

                if iw_name == "IW1":
                    # append first burst for IW1
                    match_burst_num = min(bursts_numbers)

                new_iw_df = new_iw_df.append(
                    adjacent_iw[adjacent_iw.burst_num == match_burst_num],
                    ignore_index=True,
                )

        return new_iw_df

    gpd_df = gpd.read_file(in_grid_shapefile)
    swath_series = gpd_df.swath.to_list()
    uniq_swaths = set(swath_series)

    # Check that this grid has IW1, IW2 and IW3 sub-swaths.
    # if not then grid won't be adjusted.
    if len(uniq_swaths) != 3:
        _LOG.error(
            "number of swaths != 3",
            input_shapefile=in_grid_shapefile,
            swaths=uniq_swaths,
            swath_number=len(uniq_swaths),
        )
        raise ValueError

    iw1_df = gpd_df[gpd_df.swath == "IW1"].copy()
    iw2_df = gpd_df[gpd_df.swath == "IW2"].copy()
    iw3_df = gpd_df[gpd_df.swath == "IW3"].copy()

    # k-1 grid exists: add the last overlapping burst to IW3 of grid k
    iw3_new = _add_overlapping_burst_to_grid_k(iw3_df, "IW3", grid_before_shapefile,)

    # k+1 grid exists: add first overlapping burst to IW1 of grid k
    iw1_new = _add_overlapping_burst_to_grid_k(iw1_df, "IW1", grid_after_shapefile,)

    # Remove the northernmost burst in each swath to minimise overlaps.
    # Idealy there should be a check to see if overlaps occur between
    # adjacent grids.
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

    # -------------------- #
    #      Create kml      #
    # -------------------- #
    if create_kml:
        out_kmlfile = Path(os.path.splitext(out_grid_shapefile)[0] + "_adj.kml",)

        burst_coord_list = [
            list(shapely.wkt.loads(burst_polys).exterior.coords)
            for burst_polys in new_gpd_df["extent"]
        ]
        # burst_coord_list = [poly1, ..., polyN]
        #    poly1 = [(lon1,lat1), ..., (lonN,latN), (lon1,lat1)], etc

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
                "kml file created", output_kml_file=out_kmlfile,
            )
        else:
            _LOG.error(
                "failed to create kml file", output_kml_file=out_kmlfile,
            )
