from dataclasses import dataclass
from multiprocessing.dummy import Process
from pathlib import Path
from attr.setters import convert
import os
import json
import tempfile
import shutil

from insar.gamma.proxy import create_gamma_proxy
from insar.subprocess_utils import working_directory
from insar.sensors.palsar import METADATA as alos, parse_product_summary
from insar.project import ProcConfig
import insar.constant as const
from insar.process_utils import convert
from insar.path_util import append_suffix

from insar.logs import STATUS_LOGGER

# Customise Gamma shim to automatically handle basic error checking and logging
class ProcessSlcException(Exception):
    pass

pg = create_gamma_proxy(ProcessSlcException)

@dataclass
class ALOSPaths:
    sensor_par: Path
    msp_par: Path

    slc_name: str
    slc: Path
    slc_par: Path

    msp_antpat: Path
    sensor_par: Path
    msp_par: Path
    raw: Path

    @classmethod
    def create(cls, scene_date, stack_id, pol, output_slc_path):
        slc_name = output_slc_path.stem

        msp_antpat = f"{scene_date}_{pol}_antpat.dat"
        sensor_par = f"{scene_date}_{pol}_sensor.par"
        msp_par = f"p{slc_name}.slc.par"
        raw = f"{slc_name}.raw"

        return ALOSPaths(
            sensor_par,
            msp_par,
            slc_name,
            output_slc_path,
            append_suffix(output_slc_path, ".par"),
            msp_antpat,
            raw
        )


def level0_lslc(
    proc_config: ProcConfig,
    product_path: Path,
    scene_date: str,
    pol: str,
    mode: str,
    output_slc_path: Path
) -> ALOSPaths:
    leader_path = list(product_path.glob("LED-*"))
    img_path = list(product_path.glob(f"IMG-{pol}-*"))

    paths = ALOSPaths.create(scene_date, proc_config.stack_id, pol, output_slc_path)

    # Set polarisation (0 = H, 1 = V)
    tx_pol1 = 0 if pol[0] == "H" else 1
    rx_pol1 = 0 if pol[1] == "H" else 1

    if len(leader_path) == 0 or len(img_path) == 0:
        raise ProcessSlcException("Invalid product path, could not find LED and/or IMG data!")

    if len(leader_path) > 1 or len(img_path) > 1:
        raise ProcessSlcException("Invalid product path, multiple LED and/or IMG products detected!")

    leader_path = leader_path[0]
    img_path = img_path[0]

    with working_directory(output_slc_path.parent):
        pg.PALSAR_proc(
            leader_path,
            paths.sensor_par,
            paths.msp_par,
            img_path,
            paths.raw,
            tx_pol1,
            rx_pol1
        )

        # Note: If we need to support concatenation of many inputs, we PALSAR_proc all inputs
        # as above (not just the one input), and then cat_raw them together...
        #
        # eg: `cat_raw $raw_file_list $sensor_par $msp_par $raw 1 0 -`
        # where raw_file_list = line separated list of "$raw $sensor_par $msp_par" for each input

        # TODO: should probably abstract this in py_gamma_ga.py for easier testing/mocking
        MSP_HOME = os.environ.get("MSP_HOME")
        # Correction for antenna pattern
        sensor_antpat = f"{MSP_HOME}/sensors/palsar_ant_20061024.dat"

        pg.PALSAR_antpat(
            paths.sensor_par,
            paths.msp_par,
            sensor_antpat,
            paths.msp_antpat,
            const.NOT_PROVIDED,
            tx_pol1,
            rx_pol1
        )

        # Determine the Doppler Ambiguity
        # Use dop_mlcc instead of dop_ambig when number of raw echoes greater than 8192
        pg.dop_mlcc(
            paths.sensor_par,
            paths.msp_par,
            paths.raw,
            f"{paths.slc_name}.mlcc"
        )

        # Estimate the doppler centroid with cross correlation method
        # If result of 'doppler' shows that linear model is not good enough use 'azsp_IQ' to determine constant value
        pg.doppler(
            paths.sensor_par,
            paths.msp_par,
            paths.raw,
            f"{paths.slc_name}.dop"
        )

        # Estimate the range power spectrum
        # Look for potential radio frequency interference (RFI) to the SAR signal
        pg.rspec_IQ(
            paths.sensor_par,
            paths.msp_par,
            paths.raw,
            f"{paths.slc_name}.rspec"
        )

        # Range compression
        # second to last parameter is for RFI suppression.
        pg.pre_rc(
            paths.sensor_par,
            paths.msp_par,
            paths.raw,
            f"{paths.slc_name}.rc",
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            0,
            const.NOT_PROVIDED
        )

        # Autofocus estimation and Azimuth compression (af replaces autof)
        # run az_proc and af twice, DO NOT run af mutliple times before reprocessing image
        # default SNR threshold is 10
        # slc calibrated as sigma0 (assume 34.3 angle)
        if pol == "HH" and mode == "FBS":
            cal_const=-51.9
        elif pol == "HH" and mode == "FBD":
            cal_const=-51.8
        elif pol == "HV" and mode == "FBD":
            cal_const=-58.3

        pg.az_proc(
            paths.sensor_par,
            paths.msp_par,
            f"{paths.slc_name}.rc",
            paths.slc,
            16384,
            0,
            cal_const,
            0
        )

        pg.af(
            paths.sensor_par,
            paths.msp_par,
            paths.slc,
            1024,
            4096,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            10,
            1,
            0,
            0,
            f"{paths.slc_name}.af"
        )

        pg.az_proc(
            paths.sensor_par,
            paths.msp_par,
            f"{paths.slc_name}.rc",
            paths.slc,
            16384,
            0,
            cal_const,
            0
        )

        pg.af(
            paths.sensor_par,
            paths.msp_par,
            paths.slc,
            1024,
            4096,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            10,
            1,
            0,
            0,
            f"{paths.slc_name}.af"
        )

        # Generate ISP SLC parameter file from MSP SLC parameter file (for full SLC)
        pg.par_MSP(
            paths.sensor_par,
            paths.msp_par,
            paths.slc_par,
            0
        )

    return paths

def level1_slc(
    proc_config: ProcConfig,
    product_path: Path,
    scene_date: str,
    pol: str,
    output_slc_path: Path
) -> ALOSPaths:
    leader_path = list(product_path.glob("LED-*"))
    img_path = list(product_path.glob(f"IMG-{pol}-*"))

    if len(leader_path) == 0 or len(img_path) == 0:
        raise ProcessSlcException("Invalid product path, could not find LED and/or IMG data!")

    if len(leader_path) > 1 or len(img_path) > 1:
        raise ProcessSlcException("Invalid product path, multiple LED and/or IMG products detected!")

    leader_path = leader_path[0]
    img_path = img_path[0]

    paths = ALOSPaths.create(scene_date, proc_config.stack_id, pol, output_slc_path)

    with working_directory(output_slc_path.parent):
        pg.par_EORC_PALSAR(
            leader_path,
            paths.slc_par,
            img_path,
            paths.slc
        )

        # Note: If we need to do this with multiple inputs, we would par_EORC_PALSAR fo all inputs
        # similar to above, and then we would need to implemenet an S1-style concatenate() approach
        # using `SLC_cat_all`
        #
        # eg: for each pair of tab files in the set that needs concatenating:
        #
        # # create offset parameter files for estimation of the offsets
        # SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 0
        # # measure initial range and azimuth offsets using orbit information
        # SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 1
        # # estimate range and azimuth offset models using correlation of image intensities
        # SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 3
        # # concatenate SLC images using offset polynomials determined above
        # SLC_cat_all tab1 tab2 cat_slc cat_slc_tab 4

        # Compute the azimuth Doppler spectrum and the Doppler centroid from SLC data
        _, az_spec_SLC_out, _ = pg.az_spec_SLC(
            paths.slc,
            paths.slc_par,
            f"{paths.slc_name}.dop",
            const.NOT_PROVIDED,
            0
        )

        new_doppler_estimate = None

        for line in az_spec_SLC_out:
            # Note: Bash used "new estimated Doppler centroid frequency (Hz):" - but
            # I think they were using an older GAMMA version, az_spec_SLC_out does not
            # match that original text.
            if line.startswith("new Doppler centroid estimate (Hz):"):
                new_doppler_estimate = line.split()[-1]
                break

        if not new_doppler_estimate:
            raise ProcessSlcException("Failed to determine new doppler estimate")

        # update ISP file with new estimated doppler centroid frequency (must be done manually)
        doppler_polynomial = pg.ParFile(paths.slc_par).get_value("doppler_polynomial", index=0)

        slc_par_text = paths.slc_par.read_text().replace(doppler_polynomial, new_doppler_estimate)
        with paths.slc_par.open("w") as file:
            file.write(slc_par_text)

        return paths


def process_alos_slc(
    proc_config: ProcConfig,
    product_path: Path,
    scene_date: str,
    sensor: str,
    pol: str,
    output_slc_path: Path
):
    log = STATUS_LOGGER.bind(stack_id=proc_config.stack_id)

    summary = list(product_path.glob("summary.txt"))

    if len(summary) == 0:
        raise ProcessSlcException("Invalid product path, no summary.txt found!")
    elif len(summary) > 1:
        raise ProcessSlcException("Invalid product path, more than one summary.txt found!")

    summary = parse_product_summary(summary[0].read_text())
    processing_level = summary["Lbi_ProcessLevel"]

    if "1.0" in processing_level:
        processing_level = 0
    elif "1.1" in processing_level:
        processing_level = 1
    else:
        raise RuntimeError(f"Unsupported ALOS 'Lbi_ProcessLevel': {processing_level}")

    # Inentify ALOS 1 or 2... (this function supports both as they share logic)
    alos1_acquisitions = list(product_path.glob("IMG-*-ALP*"))
    alos2_acquisitions = list(product_path.glob("IMG-*-ALOS*"))

    if not alos1_acquisitions and not alos2_acquisitions:
        raise ProcessSlcException(f"Provided product does not contain any ALOS data")

    # Raise errors if things don't match up / make sense...
    alos1_pol_acquisitions = list(product_path.glob(f"IMG-{pol}-ALP*"))
    alos2_pol_acquisitions = list(product_path.glob(f"IMG-{pol}-ALOS*"))

    if not alos1_pol_acquisitions and not alos2_pol_acquisitions:
        raise ProcessSlcException(f"Product path does not contain any data for requested polarisation ({pol})")

    if len(alos1_acquisitions) > 0 and len(alos2_acquisitions) > 0:
        raise ProcessSlcException("Unsupported ALOS product, has a mix of both PALSAR 1 and 2 products")

    product_sensor = "PALSAR1" if alos1_acquisitions else "PALSAR2"
    if sensor != product_sensor:
        raise ProcessSlcException(f"Mismatch between requested {sensor} sensor and provided {product_sensor} product")

    num_hv = len(list(product_path.glob("IMG-HV-A*")))
    mode = None

    # Determine mode
    # Note: BASH impl only did this in L0, or L1 when ALOS1 (not ALOS2)
    if product_sensor == "PALSAR1" or processing_level == 0:
        if num_hv == 0 and pol == "HH":
            mode = "FBS"
        elif num_hv > 0 and pol == "HH":
            mode = "FBD"
        elif pol == "HV":
            mode = "FBD"

        log.info("ALOS product status", product_sensor=product_sensor, mode=mode, num_hv=num_hv)

    # Generate SLC
    if processing_level == 0:
        paths = level0_lslc(
            proc_config,
            product_path,
            scene_date,
            pol,
            mode,
            output_slc_path
        )

    elif processing_level == 1:
        paths = level1_slc(
            proc_config,
            product_path,
            scene_date,
            pol,
            output_slc_path
        )

    else:
        raise RuntimeError(f"Unsupported ALOS processing level: {processing_level}")

    # FBD -> FBS conversion
    if pol == "HH" and mode == "FBD":
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            temp_slc = tmpdir / "temp.slc"
            temp_slc_par = tmpdir / "temp.slc.par"

            pg.SLC_ovr(
                paths.slc,
                paths.slc_par,
                temp_slc,
                temp_slc_par,
                2
            )

            paths.slc.unlink()
            paths.slc_par.unlink()

            shutil.move(temp_slc, paths.slc)
            shutil.move(temp_slc_par, paths.slc_par)

    # Generate quicklook
    slc_par = pg.ParFile(paths.slc_par)
    width = slc_par.get_value("range_samples", dtype=int, index=0)
    lines = slc_par.get_value("azimuth_lines", dtype=int, index=0)


    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        temp_bmp = tmpdir / "temp.bmp"

        pg.rasSLC(
            paths.slc,
            width,
            1,
            lines,
            50,
            20,
            const.NOT_PROVIDED,
            const.NOT_PROVIDED,
            1,
            0,
            0,
            temp_bmp
        )

        convert(temp_bmp, paths.slc.with_suffix(".png"))

    # Identify source data URL
    src_url = product_path / "src_url"
    # - if this is raw_data we've extracted from a source archive, a src_url file will exist (in parent dir for ALOS)
    if src_url.exists():
        src_url = src_url.read_text()
    # - otherwise it's a source data directory that's been provided by the user
    else:
        src_url = product_path.as_posix()

    # Write metadata used to produce this SLC
    metadata_path = output_slc_path.parent / f"metadata_{pol}.json"

    metadata = {
        product_path.name: {
            "src_url": src_url
        }
    }

    with metadata_path.open("w") as file:
        json.dump(metadata, file, indent=2)
