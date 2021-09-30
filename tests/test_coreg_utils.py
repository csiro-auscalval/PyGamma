from pathlib import Path
from insar import coreg_utils

from unittest import mock
import pytest


def test_read_land_center_coords():
    shape_path = Path("tests/data/T147D_F28S_S1A.shp")
    coords = coreg_utils.read_land_center_coords(shape_path)

    # from manual extraction using ogr2ogr
    assert coords == (-28.129263619, 152.169759163), "Got: " + str(coords)


def test_read_land_center_coords_missing_file():
    shape_path = Path("/tmp/this-is-fake/dummy.shp")

    with pytest.raises(FileNotFoundError):
        coreg_utils.read_land_center_coords(shape_path)


def test_missing_land_centre_attrs():
    with mock.patch("pathlib.Path.exists") as exists_mock:
        exists_mock.return_value = True

        with mock.patch("geopandas.GeoDataFrame.from_file") as from_file_mock:
            for attr in ("land_cen_l", "land_cen_1"):
                m = object()
                assert not hasattr(m, attr)  # need obj without land centre attrs
                from_file_mock.return_value = m

                path = Path("fake/file/path")
                assert coreg_utils.read_land_center_coords(path) is None


def test_zero_land_centre_attrs():
    with mock.patch("pathlib.Path.exists") as exists_mock:
        exists_mock.return_value = True

        with mock.patch("geopandas.GeoDataFrame.from_file") as from_file_mock:
            # test multiple forms of having a "0" coordinate in DBF data
            for values in (("0", "149.1"), ("35.4", "0"), ("0", "0")):
                m_dbf = mock.NonCallableMock()
                m_dbf.land_cen_l = [values[0]]
                m_dbf.land_cen_1 = [values[1]]

                from_file_mock.return_value = m_dbf

                path = Path("fake/file/path")
                assert coreg_utils.read_land_center_coords(path) is None


def test_latlon_to_px():
    # NB: latlon_to_px() also tested in test_coregister_dem.py / test_offset_calc()
    line = "SLC/MLI range, azimuth pixel (int):         7340        17060 "

    m_pg = mock.NonCallableMock()
    m_pg.coord_to_sarpix.return_value = None, ["garbage", line, "refuse"], None
    mli_path = Path("path/to/non/existent/file.mli")
    lat, lon = "35.0", "149.0"

    rpos, azpos = coreg_utils.latlon_to_px(m_pg, mli_path, lat, lon)
    assert m_pg.coord_to_sarpix.called
    assert rpos == 7340
    assert azpos == 17060


def test_latlon_to_px_bad_mli():
    # ensure error if the MLI file is missing required content
    m_pg = mock.NonCallableMock()
    m_pg.coord_to_sarpix.return_value = None, ["no range here", "garbage"], None
    mli_path = Path("path/to/non/existent/file.mli")
    lat, lon = "37.0", "147.0"

    with pytest.raises(Exception):
        coreg_utils.latlon_to_px(m_pg, mli_path, lat, lon)


def test_create_diff_par_sans_optional_args():
    with mock.patch("insar.coreg_utils.run_command") as m_run_cmd:
        fake_par_path = mock.Mock(name="this/is/a/fake/file.par")
        fake_diff_par_path = mock.Mock(name="another/fake/diff_file.par")

        m_file = mock.MagicMock(name='manual mock for fid')
        m_open = mock.mock_open()
        m_open.return_value = m_file

        with mock.patch("insar.coreg_utils.Path.open", m_open):
            # test calling diff par without optional args
            coreg_utils.create_diff_par(fake_par_path,
                                        None,  # 2nd par path
                                        fake_diff_par_path,
                                        None,  # offset
                                        None,  # num measurements
                                        None,  # window sizes
                                        None)  # cc threshold

            m_run_cmd.assert_called()
            m_write = m_file.__enter__().write
            m_write.assert_called()

            newline_call = mock.call("\n")
            newline_calls = [n for n in m_write.call_args_list if n == newline_call]
            assert len(newline_calls) >= 4


# NB: grep_stdout() part tested in coregister_secondary & coregister_slc, exceptions untested
