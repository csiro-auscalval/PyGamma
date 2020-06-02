#!/usr/bin/env python

import structlog
from insar.logs import COMMON_PROCESSORS

structlog.configure(processors=COMMON_PROCESSORS)
_LOG = structlog.get_logger("insar")


def get_expected_xml_dict():
    """
    Return
    ------
    xml_dict: dict
        A dictionary containing the expected keys
        and value data type in the xml dict.

    burst_dict: dict
        A dictionary containing the expected keys
        and value data type in each burst dict.
    """
    xml_dict = {
        "heading": float,
        "image_geometry": str,
        "incidence": float,
        "lines": int,
        "samples": int,
        "spacing": list,
    }

    burst_dict = {
        "angle": float,
        "azimuth_time": float,
        "burst_num": int,
        "coordinate": list,
        "delta_angle": float,
        "polarization": str,
        "rel_orbit": int,
        "swath": str,
    }
    return xml_dict, burst_dict


def get_expected_product_dict():
    """
    Return
    ------
    product_dict: dict
        A dictionary containing the expected keys
        and the data type of the values
    """
    product_dict = {
        "name": str,
        "url": str,
    }
    return product_dict


def get_expected_prop_dict():
    """
    Return
    ------
    properties_dict: dict
        A dictionary containing the expected keys
        and the data type of the values
    """
    properties_dict = {
        "IPF_version": float,
        "acquisition_mode": str,
        "acquisition_start_time": str,
        "acquisition_stop_time": str,
        "category": str,
        "coordinates": list,
        "crs": str,
        "cycleNumber": int,
        "frameNumber": int,
        "orbit": str,
        "orbitNumber_abs": int,
        "orbitNumber_rel": int,
        "orbitNumbers_abs": {"start": int, "stop": int,},
        "orbitNumbers_rel": {"start": int, "stop": int,},
        "polarizations": list,
        "product": str,
        "sensor": str,
        "sliceNumber": int,
        "totalSlices": int,
    }
    return properties_dict


def check_dict(
    expected_dict: dict, slc_dict: dict, key_name: str, s1_file: str,
):
    """
    Compare the "properties" or "product" dictionary extracted
    from the slc metadata & compare it with what it's expected
    to be. Here, both the dictionary keys and data type of the
    values are compared to expected.

    Parameters
    ----------
    expected_dict: dict
        the expected properties or product dictionary

    slc_dict: dict
        the slc metadata extracted from the S1 zip

    key_name: str {"propertes", "product"}
        the key name of the dictionary to check

    s1_file: str
        Path of sentinel-1 zip file

    Returns
    -------
        True or False for pass or failed checks
    """
    check_keys = True
    check_vals = True
    if not slc_dict:
        # empty dictionary
        _LOG.error(
            "empty dictionary in {}".format(key_name), s1_scene=s1_file,
        )
        return False

    for ukey in expected_dict:
        if ukey in slc_dict[key_name]:

            utype = type(slc_dict[key_name][ukey])
            if utype is dict:
                for mkey in expected_dict[ukey]:
                    if mkey in slc_dict[key_name][ukey]:

                        mtype = type(slc_dict[key_name][ukey][mkey])
                        if mtype != expected_dict[ukey][mkey]:
                            check_vals = False
                            _LOG.error(
                                "[{0}][{1}][{2}] value dtype mismatch".format(
                                    key_name, ukey, mkey,
                                ),
                                expected_dtype=expected_dict[ukey][mkey],
                                s1_scene=s1_file,
                            )

                    else:
                        check_keys = False
                        _LOG.error(
                            "missing [{0}] inside [{1}][{2}]".format(
                                mkey, key_name, ukey,
                            ),
                            s1_scene=s1_file,
                        )

            else:
                if utype != expected_dict[ukey]:
                    check_vals = False
                    _LOG.error(
                        "[{0}][{1}] value dtype mismatch".format(key_name, ukey,),
                        expected_dtype=expected_dict[ukey],
                        s1_scene=s1_file,
                    )
        else:
            check_keys = False
            _LOG.error(
                "missing [{0}] inside [{1}]".format(ukey, key_name,), s1_scene=s1_file,
            )

    if (not check_keys) or (not check_vals):  # one or both checks failed
        return False

    else:
        # both checks passed
        return True


def check_measurement_dict(
    xml_dict: dict, burst_dict: dict, slc_dict: dict, s1_file: str,
):
    """
    Check if the measurement dictionary contains all
    the necessary burst information for each xml file

    Parameters
    ----------
    xml_dict: dict
        the expected xml dictionary with value data types

    burst_dict: dict
        the expected burst dictionary with value data types

    slc_dict: dict
        the slc metadata dict containing the
        xml and burst dictionaries

    s1_file: str
        Path of sentinel-1 zip file

    Returns
    -------
    """

    def _check_nested_dict(
        _exp_dict: dict, _slc_dict: dict, _xml_file: str, bkey,
    ):
        # _exp_dict: the expected xml dictionary
        # _slc_dict: the slc metadata dictionary
        # _xml_file: pathname of xml file
        #
        # iterate through keys in expected dict.
        _check = True
        for exp_key in _exp_dict:
            if exp_key in _slc_dict:
                slc_dtype = type(_slc_dict[exp_key])
                if slc_dtype != _exp_dict[exp_key]:
                    # value in slc dict has the wrong dtype
                    _check = False
                    _LOG.error(
                        "[measurement][xml] value dtype mismatch",
                        xml=_xml_file,
                        burst_key=bkey,
                        key=exp_key,
                        expected_dtype=_exp_dict[exp_key],
                        s1_scene=s1_file,
                    )
            else:
                # missing key in slc dict
                _check = False
                _LOG.error(
                    "missing key in [measurement][xml] dict",
                    xml=_xml_file,
                    burst_dict=bkey,
                    missing_key=exp_key,
                    s1_scene=s1_file,
                )

        return _check

    def _check_bursts(_slc_xml_dict: dict,):
        # return a list containing the bursts
        _b_keys = []
        for _key in _slc_xml_dict:
            if _key.lower().startswith("burst"):
                _b_keys.append(_key)
        return _b_keys

    pass_xml_dict = True
    pass_meas_xml = True
    pass_meas_burst = True
    pass_null_bursts = True
    pass_gt0_bursts = True

    num_xmls = 0
    for xml in slc_dict:
        # xml is a dict
        if type(slc_dict[xml]) is dict:
            pass_meas_xml = _check_nested_dict(xml_dict, slc_dict[xml], xml, None,)

            burst_keys = _check_bursts(slc_dict[xml])
            if len(burst_keys) == 0:
                pass_null_bursts = False
                _LOG.error(
                    "xml does not have any burst info",
                    num_burst_keys=0,
                    xml_file=xml,
                    s1_scene=s1_file,
                )
            else:
                # check that each burst dictionary
                # is as expected.
                for bkeys in burst_keys:
                    pass_meas_burst = _check_nested_dict(
                        burst_dict, slc_dict[xml][bkeys], xml, bkeys,
                    )
        else:
            pass_xml_dict = False
            _LOG.error(
                'xml in ["measurements"] are not dicts',
                xml=xml,
                xml_type=type(xml),
                s1_scene=s1_file,
            )

        num_xmls += 1

    if num_xmls == 0:
        pass_gt0_bursts = False
        _LOG.error(
            "slc metadata is missing dicts for xml files",
            num_xmls=num_xmls,
            s1_scene=s1_file,
        )

    if (
        (not pass_xml_dict)
        or (not pass_meas_xml)
        or (not pass_meas_burst)
        or (not pass_null_bursts)
        or (not pass_gt0_bursts)
    ):
        # one or more tests failed.
        return False

    else:
        return True


def diagnose(
    slc_dict, slc_scene,
):

    # get sets of expected dict keys
    toplevel_keys = set(["id", "measurements", "product", "properties"])
    product_dict = get_expected_product_dict()
    properties_dict = get_expected_prop_dict()
    xml_dict, burst_dict = get_expected_xml_dict()

    # ensure that slc dict has the required top level keys
    slc_toplevel = set(slc_dict.keys())
    if slc_toplevel != toplevel_keys:
        _LOG.error(
            "slc metadata is missing top level keys {}".format(
                toplevel_keys.difference(slc_toplevel),
            ),
            s1_scene=slc_scene,
        )
        return False

    # get list of missing or mis-matching data type in the
    # slc "id", "properties" and "product" dictionaries.
    check_id = True
    if type(slc_dict["id"]) is not str:
        check_id = False
        _LOG.error(
            'slc metadata "id" is not a str', s1_scene=slc_scene,
        )

    # compare slc_dict["properties"] with expected
    check_properties = check_dict(properties_dict, slc_dict, "properties", slc_scene,)

    # compare slc_dict["products"] with expected
    check_products = check_dict(product_dict, slc_dict, "product", slc_scene,)

    # compare slc_dict["measurements"] with expected
    check_xml_bursts = check_measurement_dict(
        xml_dict, burst_dict, slc_dict["measurements"], slc_scene,
    )

    if (
        (not check_id)
        or (not check_properties)
        or (not check_products)
        or (not check_xml_bursts)
    ):
        # failed one or more checks
        return False
    else:
        return True
