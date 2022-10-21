.. PyGamma documentation master file, created by
   sphinx-quickstart on Thu Jan 23 07:57:00 2020.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

PyGamma
===========

PyGamma is a workflow managers designed to generate SAR/InSAR analysis ready data using
`GAMMA SOFTWARE`_

.. _GAMMA SOFTWARE: http://www.gamma-rs.ch/


Extract Sentinel-1 SLC metadata
###############################
Here is a simple example of extracting Sentinel-1 SLC metadata. The returned metadata
will contain IW-swaths and manifest safe file's informations::

    from insar.meta_data.s1_slc import SlcMetadata

    scene_path = Path('/path/to/SLC/zip/file')
    slc = SlcMetadata(scene_path)
    slc_metadata = slc.get_metadata()


Archive Sentinel-1 SLC
######################
sqlite database is setup (if database does not exist) and Sentinel-1 SLC's metadata are
archived into a database. Extracted slc metadata can be supplied to be archived::

    from insar.meta_data.s1_slc import Arhcive, SlcMetadata

    database_file = Path('/path/to/database')
    scene_path = Path('/path/to/SLC/zip/file')
    slc_metadata = SlcMetadata(scene_path).get_metadata()
    with Archive(database_file) as archive:
        archive.archive_scene(slc_metadata)


Query Sqlite SLC archive database
#################################
Example to query database for to generate input files needed to form SLC input for
SAR / InSAR processing using PyGamma module::

    from datetime import datetime
    from insar.s1_slc_metadata import Archive
    from spatialist import Vector

    dbfile = Path('/path/to/database')
    shape_file = Vector(Path('/path/to/shape_file'))
    start_date = datetime(YYYY, MM, DD, HH, MM, SS)
    end_date = datetime(YYYY, MM, DD, HH, MM, SS)
    orbit = 'D'
    track = shape file's relative orbit number

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
            spatial_subset=spatial_subset,
            columns=columns,
            min_date_arg=min_date_arg,
            max_date_arg=max_date_arg,
        )



API / CLASS
===========
.. autoclass:: insar.meta_data.s1_slc.SlcMetadata
   :members: get_metadata, metadata_manifest_safe, metadata_swath, extract_archive_member
   :special-members: __init__

.. autoclass:: insar.meta_data.s1_slc.Archive
   :members: archive_scene, select, select_duplicates
   :special-members: __init__

.. autoclass:: insar.meta_data.s1_slc.SlcFrame
   :members:
   :special-members: __init__

.. autoclass:: insar.calc_baselines_new.BaselineProcess
   :members:
   :special-members: __init__

.. autoclass:: insar.process_s1_slc.SlcProcess
   :members: main
   :special-members: __init__

.. autoclass:: insar.coregister_slc.CoregisterSlc
   :members: main
   :special-members: __init__

.. autoclass:: insar.coregister_dem.CoregisterDem
   :members: main
   :special-members: __init__



