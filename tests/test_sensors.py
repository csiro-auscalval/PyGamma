import pytest
from tests.fixtures import *

from insar.sensors import identify_data_source, get_data_swath_info, acquire_source_data
from insar.sensors.s1 import METADATA as S1_METADATA
from insar.sensors.rsat2 import METADATA as RS2_METADATA
from insar.sensors.tsx import METADATA as TSX_METADATA

import insar.sensors.s1 as s1
import insar.sensors.rsat2 as rs2
import insar.sensors.tsx as tsx


S1_DATA_PATH_EXAMPLE = "tests/data/S1A_IW_SLC__1SDV_20190918T200909_20190918T200936_029080_034CEE_C1F9.zip"
RS2_DATA_PATH_EXAMPLE = "tests/data/RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_HH_SLC.zip"
TSX_DATA_PATH_EXAMPLE = "tests/data/TSX/20170411_TSX_T041D.tar.gz"

S1_DATA_PATH_BAD_EXAMPLE = "tests/data/S3Z_IW_SLC__1SDV_20190918T200909_20190918T200936_029080_034CEE_C1F9.zip"
RS2_DATA_PATH_BAD_EXAMPLE = "tests/data/RS2_OK127568_PK1123201_DK1078370_F0W2_20170430_084253_OK_SLC.zip"
TSX_DATA_PATH_BAD_EXAMPLE = "tests/data/TSX/20170411_TSX_T041D_broken.tar.gz"


def test_s1_source_data_identification():
    constellation, sensor, scene_date = identify_data_source(S1_DATA_PATH_EXAMPLE)

    assert(constellation == S1_METADATA.constellation_name)
    assert(sensor == "S1A")
    assert(scene_date == "20190918")


def test_rs2_source_data_identification():
    constellation, sensor, scene_date = identify_data_source(RS2_DATA_PATH_EXAMPLE)

    assert(constellation == RS2_METADATA.constellation_name)
    assert(sensor == "RS2")
    assert(scene_date == "20170430")


def test_tsx_source_data_identification():
    constellation, sensor, scene_date = identify_data_source(TSX_DATA_PATH_EXAMPLE)

    assert (constellation == TSX_METADATA.constellation_name)
    assert (sensor == "TSX")
    assert (scene_date == "20170411")


def test_invalid_source_data_identification():
    # Unknown inputs should raise exceptions
    with pytest.raises(Exception):
        identify_data_source("What is data?")

    # Even if they look very close to what we want...
    with pytest.raises(Exception):
        identify_data_source(S1_DATA_PATH_BAD_EXAMPLE)

    with pytest.raises(Exception):
        identify_data_source(RS2_DATA_PATH_BAD_EXAMPLE)


def test_dispatch_swath_data_fails_for_missing_input():
    with pytest.raises(Exception):
        get_data_swath_info("does/not/exist")


def validate_subswath_info(
    subswath_info,
    expected_source,
    expected_sensor,
    expected_date,
    expected_pols
):
    # Should have a date/extent/sensor/pol/source-url
    assert("date" in subswath_info)
    assert("acquisition_datetime" in subswath_info)
    assert("swath_extent" in subswath_info)
    assert("sensor" in subswath_info)
    assert("polarization" in subswath_info)
    assert("url" in subswath_info)

    assert(subswath_info["date"].strftime("%Y%m%d") == expected_date)
    assert(subswath_info["acquisition_datetime"].strftime("%Y%m%d") == expected_date)

    # All our test data is in Australia, so just generally assert we're somewhere
    # in this region of the planet.  These are just arbitrary bounding points
    # I picked off a map (good enough for the sanity checking of this test)
    aus_extent = (
        (111.5426204243644, -9.422961279563507),
        (154.39182862611165, -44.792798109513356)
    )

    def point_in_aus(lon, lat):
        lon_in_bounds = lon >= aus_extent[0][0] and lon <= aus_extent[1][0]
        lat_in_bounds = lat <= aus_extent[0][1] and lat >= aus_extent[1][1]

        return lon_in_bounds and lat_in_bounds

    assert(point_in_aus(*subswath_info["swath_extent"][0]))
    assert(point_in_aus(*subswath_info["swath_extent"][1]))

    assert(subswath_info["sensor"] == expected_sensor)
    assert(str(subswath_info["url"]) == str(expected_source))
    assert(subswath_info["polarization"] in expected_pols)


def test_s1_swath_data_for_known_input(s1_test_data_zips, pgp, pgmock, logging_ctx):
    info = get_data_swath_info(s1_test_data_zips[0])

    # This is valid S1 data, so there should be 3x subswaths and 2x pols
    assert(len(info) == 3 * 2)

    for subswath_info in info:
        validate_subswath_info(
            subswath_info,
            s1_test_data_zips[0],
            "S1A",
            S1_TEST_DATA_DATES[0],
            ["VV", "VH"]
        )


def test_s1_swath_data_fails_for_missing_input():
    with pytest.raises(Exception):
        s1.get_data_swath_info("does/not/exist")


def test_s1_swath_data_fails_for_invalid_input(temp_out_dir, pgp, pgmock, logging_ctx, s1_test_data):
    # Make a copy of some test data...
    safe_name = s1_test_data[0].name
    safe_copy = temp_out_dir / safe_name
    safe_copy_zip = safe_copy.with_suffix(".zip")
    shutil.copytree(s1_test_data[0], safe_copy)

    # ... and then invalidate it by deleting an important manifest file
    shutil.rmtree(safe_copy / "annotation")

    # Convert it back into a .zip file (which S1 source data has to be currently...)
    shutil.make_archive(safe_copy_zip, 'zip', safe_copy)

    # Assert we fail to get swath info from invalid data products
    with pytest.raises(Exception):
        get_data_swath_info(safe_copy_zip)


def test_rs2_swath_data_for_known_input(rs2_test_data):
    info = get_data_swath_info(rs2_test_data[0])

    # This is valid RS2 data, which means there are no subswaths
    # - thus we expect just a single swath entry.
    assert(len(info) == 1)

    validate_subswath_info(
        info[0],
        rs2_test_data[0],
        "RS2",
        RS2_TEST_DATA_DATES[0],
        ["HH"]
    )


def test_rs2_swath_data_fails_for_missing_input():
    with pytest.raises(Exception):
        rs2.get_data_swath_info("does/not/exist")


def test_rs2_swath_data_fails_for_invalid_input(temp_out_dir, pgp, pgmock, logging_ctx, rs2_test_data):
    # Make a copy of some test data and
    safe_name = rs2_test_data[0].name
    safe_copy = temp_out_dir / safe_name
    shutil.copytree(rs2_test_data[0], safe_copy)

    # Sanity check it's all good by getting swath data (shouldn't except)
    get_data_swath_info(safe_copy)

    # Then invalidate it by deleting an important manifest file
    (safe_copy / "product.xml").unlink()

    # Assert we fail to get swath info from invalid data products
    with pytest.raises(Exception):
        get_data_swath_info(safe_copy)


def test_tsx_swath_data_for_known_input(tsx_test_tar_gzips):
    info = get_data_swath_info(tsx_test_tar_gzips[0])

    # TODO: does valid TSX data have only 1 swath/no subswaths?
    assert len(info) == 1

    validate_subswath_info(info[0],
                           expected_source=tsx_test_tar_gzips[0],
                           expected_sensor="TSX",
                           expected_date=TSX_TEST_DATA_DATES[0],
                           expected_pols=["HH"])  # TODO: verify


def test_tsx_swath_data_fails_for_missing_input():
    with pytest.raises(Exception):
        tsx.get_data_swath_info("tsx_does/not/exist")


def test_tsx_swath_data_fails_for_invalid_input(temp_out_dir, tsx_test_tar_gzips):
    # Duplicate PRE-broken test data (easier than modifying tar.gz files on the fly)
    safe_name = tsx_test_tar_gzips[0].name
    safe_copy = temp_out_dir / safe_name
    shutil.copy(TEST_DATA_BASE / "TSX/20170411_TSX_T041D_broken.tar.gz", safe_copy)

    # Assert we fail to get swath info from invalid data products
    with pytest.raises(Exception):
        get_data_swath_info(safe_copy)


def test_s1_acquisition_for_good_input(temp_out_dir, pgp, pgmock, logging_ctx, s1_test_data_zips, s1_proc):
    with s1_proc.open('r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    # Acquire some test data into a temp dir...
    acquire_source_data(
        s1_test_data_zips[0],
        temp_out_dir,
        poeorb_path=proc_config.poeorb_path,
        resorb_path=proc_config.resorb_path
    )

    # Assert we got some source data with at least 3 tif files (eg: a full swath of 3x subswaths)
    assert(len(list(temp_out_dir.glob("**/s1a*slc*.tiff"))) >= 3)

    # Assert we also have annotation files for subswaths
    assert(len(list(temp_out_dir.glob("**/annotation/*.xml"))) >= 3)


def test_s1_acquisition_for_corrupt_xml_in_zip(temp_out_dir, pgp, pgmock, logging_ctx, s1_test_data_zips, s1_proc):
    with s1_proc.open('r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    # Make a copy of some test data and corrupt some if it's data
    zip_file = temp_out_dir / f"corrupt_{s1_test_data_zips[0].name}"
    shutil.copyfile(s1_test_data_zips[0], zip_file)

    # Corrupt all the .xml files
    corruption_zones = []
    with ZipFile(zip_file, "r") as zf:
        for info in zf.infolist():
            if ".xml" in info.filename:
                corruption_zones.append((info.header_offset, info.compress_size))

    with zip_file.open("ab") as zf:
        for offset, size in corruption_zones:
            zf.seek(offset, 0)
            zf.write(bytearray([0] * size))

    # Assert we fail to get swath info from a corrupt product
    with pytest.raises(Exception):
        acquire_source_data(
            zip_file,
            temp_out_dir,
            poeorb_path=proc_config.poeorb_path,
            resorb_path=proc_config.resorb_path
        )


def test_s1_acquisition_for_incomplete_data(temp_out_dir, pgp, pgmock, logging_ctx, s1_test_data_zips, s1_proc):
    with s1_proc.open('r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    # Acquire some test data into a temp dir...
    # EXCEPT... request data that doesn't exist in that source data file
    # (eg: pretend it's incomplete by asking for something that's not there)
    acquire_source_data(
        s1_test_data_zips[0],
        temp_out_dir,
        ["HH"],
        poeorb_path=proc_config.poeorb_path,
        resorb_path=proc_config.resorb_path
    )

    # Assert we got nothing out of it... because it's incomplete / lacks the data we want.
    assert(len(list(temp_out_dir.glob("**/s1a*slc*.tiff"))) == 0)
    assert(len(list(temp_out_dir.glob("**/annotation/*.xml"))) == 0)


def test_s1_acquisition_missing_input(temp_out_dir, pgp, pgmock, logging_ctx, s1_proc):
    with s1_proc.open('r') as fileobj:
        proc_config = ProcConfig.from_file(fileobj)

    # Assert we fail to get swath info from a non-existent product
    with pytest.raises(Exception):
        acquire_source_data(
            temp_out_dir / "this_does_not_exist",
            temp_out_dir,
            poeorb_path=proc_config.poeorb_path,
            resorb_path=proc_config.resorb_path
        )


def test_rs2_acquisition_for_good_input(temp_out_dir, pgp, pgmock, logging_ctx, rs2_test_data):
    # Acquire some test data into a temp dir...
    acquire_source_data(rs2_test_data[0], temp_out_dir)

    # Assert we got some source data with at least 1 tiff (eg: a full swath for some polarisation)
    assert(len(list(temp_out_dir.glob("**/imagery*.tif"))) >= 1)

    # Assert we also have a product xml
    assert(len(list(temp_out_dir.glob("**/product.xml"))) >= 1)


def test_rs2_acquisition_for_corrupt_xml_in_zip(temp_out_dir, pgp, pgmock, logging_ctx, rs2_test_zips):
    # Make a copy of some test data and corrupt some if it's data
    zip_file = temp_out_dir / f"corrupt_{rs2_test_zips[0].name}"
    shutil.copyfile(rs2_test_zips[0], zip_file)

    # Corrupt all the .xml files
    corruption_zones = []
    with ZipFile(zip_file, "r") as zf:
        for info in zf.infolist():
            if ".xml" in info.filename:
                corruption_zones.append((info.header_offset, info.compress_size))

    with zip_file.open("ab") as zf:
        for offset, size in corruption_zones:
            zf.seek(offset, 0)
            zf.write(bytearray([0] * size))

    # Assert we fail to get swath info from a corrupt product
    with pytest.raises(Exception):
        acquire_source_data(zip_file, temp_out_dir)


def test_rs2_acquisition_for_incomplete_data(temp_out_dir, pgp, pgmock, logging_ctx, rs2_test_data):
    # Acquire some test data into a temp dir...
    # EXCEPT... request data that doesn't exist in that source data file
    # (eg: pretend it's incomplete by asking for something that's not there)
    acquire_source_data(rs2_test_data[0], temp_out_dir, ["VV"])

    # Assert we got nothing out of it... because it doesn't have the data we want / is incomplete...
    assert(len(list(temp_out_dir.glob("**/imagery*.tif"))) == 0)


def test_rs2_acquisition_missing_input(temp_out_dir, pgp, pgmock, logging_ctx):
    # Assert we fail to get swath info from a non-existent product
    with pytest.raises(Exception):
        acquire_source_data(
            temp_out_dir / "this_is_not_the_data_you_are_looking_for",
            temp_out_dir
        )


def test_tsx_acquisition_for_good_input(temp_out_dir, pgp, pgmock, logging_ctx, tsx_test_tar_gzips):
    acquire_source_data(tsx_test_tar_gzips[0], temp_out_dir)

    # ensure a core dir tree & data files exist
    date_dir = temp_out_dir / "20170411"
    assert date_dir.exists()

    tdx_dir = date_dir / "TDX1_SAR__SSC______SM_S_SRA_20170411T192821_20170411T192829"
    assert tdx_dir.exists()

    tdx_xml = tdx_dir / "TDX1_SAR__SSC______SM_S_SRA_20170411T192821_20170411T192829.xml"
    assert tdx_xml.exists()

    data_cos = tdx_dir / "IMAGEDATA" / "IMAGE_HH_SRA_strip_009.cos"
    assert data_cos.exists()


def test_tsx_acquisition_for_corrupt_tar_gz(temp_out_dir, pgp, pgmock, logging_ctx, tsx_test_tar_gzips):
    # this file is pre-broken as the XML metadata files do not contain XML
    source = TEST_DATA_BASE / "TSX" / "20170411_TSX_T041D_broken_xml_meta.tar.gz"

    dst = temp_out_dir / tsx_test_tar_gzips[0].name
    shutil.copyfile(source, dst)

    # NB: this test is fairly lame, it breaks the entire tarfile, unlike the corrupted XML in the RS2 tests
    # acquire_source_data() decompresses the data but doesn't check if the XML is invalid
    # leaving it in for what it's worth..
    with open(dst, "w") as df:
        df.seek(512)  # file is only 1.7kb
        df.write('\0' * 64)  # jam in some nulls to break the data file

    with pytest.raises(Exception):
        acquire_source_data(dst, temp_out_dir)


# def test_tsx_acquisition_for_incomplete_data(temp_out_dir, pgp, pgmock, logging_ctx, tsx_test_tar_gzips):
#      # test skipped for now as there's no polarisation filtering at present


def test_tsx_acquisition_missing_input(temp_out_dir, pgp, pgmock, logging_ctx):
    # Assert we fail to get swath info from a non-existent product
    with pytest.raises(Exception):
        acquire_source_data(
            temp_out_dir / "not_the_TSX_data_you_are_looking_for",
            temp_out_dir
        )
