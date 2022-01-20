import pytest
from pathlib import Path
from unittest import mock

from tests.fixtures import *

import insar.coregister_secondary
from insar.coregister_secondary import  coregister_secondary, apply_coregistration
from insar.path_util import par_file
from insar.logs import logging_directory

def simple_coreg_outputs(secondary_slc):
    test_out_slc = secondary_slc.parent / "coreg.slc"
    test_out_mli = secondary_slc.parent / "coreg.mli"
    return test_out_slc, test_out_mli

def simple_coreg(proc_config, primary_slc, secondary_slc, out_slc, out_mli):
    # Note: We just run the unit tests on the same full resolution inputs,
    # to avoid producing fake MLIs for no real reason.  This is a valid
    # use case, even using the SLC as the DEM is valid - but would be pretty
    # useless to coregister a scene against itself in practice...
    # (should result in a 1:1 mapping in the LUTs)
    #
    # It's especially irrelevant in unit tests, where the contents of the file don't
    # matter as we don't have GAMMA licenses to process the data for real, it's all
    # just running through mocked PyGamma objects that do high-level validation and file
    # exists/touch operations only...
    with logging_directory(proc_config.job_path):
        coregister_secondary(
            proc_config,
            primary_slc,
            primary_slc,
            primary_slc,
            secondary_slc,
            secondary_slc,
            out_slc,
            out_mli,
            # Arbitrary choices for multi-look, shouldn't matter testing wise
            4,
            4
        )


def cleanup(secondary_slc):
    slc, mli = simple_coreg_outputs(secondary_slc)

    for p in [slc, par_file(slc), mli, par_file(mli)]:
        if p.exists():
            p.unlink()

def test_coregister_secondary_with_valid_data(pgp, pgmock, proc_config, rs2_slc):
    slc, mli = simple_coreg_outputs(rs2_slc)

    simple_coreg(proc_config, rs2_slc, rs2_slc, slc, mli)

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(len(pgp.call_sequence) > 0)
    assert(slc.exists())
    assert(mli.exists())

    # Clean up output for subsequent tests (as we share test_data for the whole module to reduce IO)
    cleanup(rs2_slc)


def test_coregister_secondary_with_missing_primary_input(pgp, pgmock, proc_config, rs2_slc):
    slc, mli = simple_coreg_outputs(rs2_slc)

    # Ensure coreg raises an exception w/ missing primary input
    with pytest.raises(FileNotFoundError):
        simple_coreg(proc_config, Path("missing_primary.slc"), rs2_slc, slc, mli)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not slc.exists())
    assert(not mli.exists())


def test_coregister_secondary_with_missing_secondary_input(pgp, pgmock, proc_config, rs2_slc):
    slc, mli = simple_coreg_outputs(rs2_slc)

    # Ensure coreg raises an exception w/ missing secondary input
    with pytest.raises(FileNotFoundError):
        simple_coreg(proc_config, rs2_slc, Path("missing_secondary.slc"), slc, mli)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not slc.exists())
    assert(not mli.exists())


def test_coregister_secondary_with_invalid_output_dir(pgp, pgmock, proc_config, rs2_slc):
    slc = Path("/path/does/not/exist/out.slc")
    mli = Path("/path/does/not/exist/out.mli")

    # Ensure coreg raises an exception w/ invalid output (missing dir)
    with pytest.raises(FileNotFoundError):
        simple_coreg(proc_config, rs2_slc, rs2_slc, slc, mli)

    # Ensure not a single GAMMA call occured & no output exists
    assert(len(pgp.call_sequence) == 0)
    assert(not slc.exists())
    assert(not mli.exists())


def test_apply_coregistration_with_valid_data(pgp, pgmock, proc_config, rs2_slc):
    # Note: Similar to simple_coreg, we use the same slc as both primary/secondary
    # and MLI - this is technically valid, but should do very little
    # (should produce near zero coreg to itself)

    slc, mli = simple_coreg_outputs(rs2_slc)

    # Make fake coreg inputs
    lut = rs2_slc.parent / "coreg.lt"
    off = rs2_slc.parent / "coreg.off"

    lut.touch()
    off.touch()

    apply_coregistration(
        rs2_slc,
        rs2_slc,
        rs2_slc,
        rs2_slc,
        slc,
        mli,
        lut,
        off,
        4,
        4
    )

    # Ensure the output is created and no errors occured
    assert(pgp.error_count == 0)
    assert(len(pgp.call_sequence) > 0)
    assert(slc.exists())
    assert(mli.exists())

    # Clean up output for subsequent tests (as we share test_data for the whole module to reduce IO)
    cleanup(rs2_slc)


def test_apply_coregistration_with_missing_slc(pgp, pgmock, rs2_slc):
    slc, mli = simple_coreg_outputs(rs2_slc)
    missing_input = rs2_slc / "does_not_exist.slc"

    # Make fake coreg inputs
    lut = rs2_slc.parent / "coreg.lt"
    off = rs2_slc.parent / "coreg.off"

    lut.touch()
    off.touch()

    # Ensure coreg raises an exception w/ invalid inputs
    with pytest.raises(FileNotFoundError):
        apply_coregistration(
            missing_input,
            missing_input,
            missing_input,
            missing_input,
            slc,
            mli,
            lut,
            off,
            4,
            4
        )

    # Ensure the processing never happens, no outputs exist
    assert(len(pgp.call_sequence) == 0)
    assert(not slc.exists())
    assert(not mli.exists())


def test_apply_coregistration_with_missing_lut(pgp, pgmock, rs2_slc):
    slc, mli = simple_coreg_outputs(rs2_slc)

    # Make fake coreg inputs
    lut = rs2_slc.parent / "coreg.lt"
    off = rs2_slc.parent / "coreg.off"

    # Note: we do NOT create the LUT in this test
    if lut.exists():
        lut.unlink()

    off.touch()

    # Ensure coreg raises an exception w/ invalid inputs
    with pytest.raises(FileNotFoundError):
        apply_coregistration(
            rs2_slc,
            rs2_slc,
            rs2_slc,
            rs2_slc,
            slc,
            mli,
            lut,
            off,
            4,
            4
        )

    # Ensure the processing never happens, no outputs exist
    assert(len(pgp.call_sequence) == 0)
    assert(not slc.exists())
    assert(not mli.exists())


def test_apply_coregistration_with_missing_offset(pgp, pgmock, rs2_slc):
    slc, mli = simple_coreg_outputs(rs2_slc)

    # Make fake coreg inputs
    lut = rs2_slc.parent / "coreg.lt"
    off = rs2_slc.parent / "coreg.off"

    # Note: we do NOT create the offset in this test
    if off.exists():
        off.unlink()

    lut.touch()

    # Ensure coreg raises an exception w/ invalid inputs
    with pytest.raises(FileNotFoundError):
        apply_coregistration(
            rs2_slc,
            rs2_slc,
            rs2_slc,
            rs2_slc,
            slc,
            mli,
            lut,
            off,
            4,
            4
        )

    # Ensure the processing never happens, no outputs exist
    assert(len(pgp.call_sequence) == 0)
    assert(not slc.exists())
    assert(not mli.exists())

