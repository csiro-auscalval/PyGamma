import json
import tempfile
from pathlib import Path

from insar import constant
from insar.process_utils import convert
from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper

import structlog


# Customise GAMMA shim to automatically handle basic error checking and logging
class ProcessSlcException(Exception):
    pass


_LOG = structlog.get_logger("insar")
pg = GammaInterface(
    subprocess_func=auto_logging_decorator(subprocess_wrapper, ProcessSlcException, _LOG)
)


# TODO: does there need to be any polarisation filtering?

# TAR gzip file path validation funcs
def _verify_tsx_annotation_path(xmls, tsx_dir):
    if len(xmls) == 0:
        msg = f"No annotation XML file found in {tsx_dir}\nDir contents: {list(tsx_dir.glob('*'))}"
        raise ProcessSlcException(msg)
    elif len(xmls) > 1:
        msg = f"Multiple XML files found in {tsx_dir}, should only contain 1:\n{xmls}"
        raise ProcessSlcException(msg)


def _verify_cosar_path(cos_files, image_dir):
    if len(cos_files) == 0:
        msg = f"No COSAR file found in {image_dir}"
        raise ProcessSlcException(msg)
    elif len(cos_files) > 1:
        msg = f"Multiple COSAR files found in {image_dir}, should only contain 1:\n{cos_files}"
        raise ProcessSlcException(msg)


def process_tsx_slc(
    product_path: Path,
    polarisation: str,
    output_slc_path: Path
):
    """
    Process source TSX/TDX data into GAMMA SLC files.

    :param product_path:
        Path to extracted TSX product dir. From acquire_source_data() it's expected to be the base TSX filename subdir,
         e.g. "<scene_date>/<scene_date>/TDX1_SAR__SSC______SM_S_SRA_20170411T192821_20170411T192829" (i.e. automatic
         descent into one level of )
    :param polarisation:
        scene polarisation value
    :param output_slc_path:
        Path to default SLC output file.
    """
    if not product_path.exists():
        raise ProcessSlcException(f"product_path does not exist! product_path={product_path}")

    if output_slc_path is None:
        raise ValueError("output_slc_path cannot be None")

    # NB: manual path manipulation not ideal, but results in simpler calling code & tests
    output_slc_par_path = output_slc_path.with_suffix(".slc.par")

    # find the annotation XML file
    pattern = "T[SD]X[0-9]_SAR_*T[0-9][0-9][0-9][0-9][0-9][0-9]"
    xmls = list(product_path.glob(pattern + ".xml"))
    _verify_tsx_annotation_path(xmls, product_path)
    xml_meta = xmls[0]

    # locate the image data file
    image_dir = product_path / "IMAGEDATA"
    cos_files = list(image_dir.glob("IMAGE_*.cos"))
    _verify_cosar_path(cos_files, image_dir)
    cosar = cos_files[0]

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        base_name = output_slc_path.name
        gamma_slc = tdir / f"gamma_{str(base_name)}"
        gamma_slc_par = tdir / f"gamma_{str(base_name)}.par"

        # Read TSX data and produce SLC and parameter files in GAMMA format
        pg.par_TX_SLC(xml_meta,  # TSX product annotation file
                      cosar,  # COSAR SSC stripmap
                      gamma_slc_par,  # output param file
                      gamma_slc,  # output SLC data
        )

        # Apply stated calFactor from the xml file, scale according to sin(inc_angle) and
        # convert from scomplex to fcomplex. Output is sigma0
        # NB: This does the file mv step inline unlike the BASH version
        pg.radcal_SLC(gamma_slc,
                      gamma_slc_par,
                      output_slc_path,  # SLC output file, the sigma0
                      output_slc_par_path,  # SLC PAR output file, the sigma0 par
                      3,  # fcase: scomplex --> fcomplex
                      constant.NOT_PROVIDED,  # antenna gain file
                      0,  # rloss_flag
                      0,  # ant_flag
                      1,  # refarea_flag
                      0,  # sc_dB
                      constant.NOT_PROVIDED,  # K_dB
        )

        # Make quick-look png image of SLC
        par = pg.ParFile(output_slc_par_path.as_posix())
        width = par.get_value("range_samples", dtype=int, index=0)
        lines = par.get_value("azimuth_lines", dtype=int, index=0)
        bmp_path = output_slc_path.with_suffix(".slc.bmp")
        png_path = output_slc_path.with_suffix(".slc.png")

        pg.rasSLC(output_slc_path,
                  width,
                  1,
                  lines,
                  50,
                  20,
                  constant.NOT_PROVIDED,
                  constant.NOT_PROVIDED,
                  1,
                  0,
                  0,
                  bmp_path,
        )

        convert(bmp_path, png_path)
        bmp_path.unlink()

    # write metadata for stack.py / ard Luigi task
    src_url = product_path / "src_url"
    # - if this is raw_data we've extracted from a source archive, a src_url file will exist
    if src_url.exists():
        src_url = src_url.read_text()  # should get TAR file here, otherwise a src data dir provided by the user
    else:
        src_url = product_path.as_posix()

    # Write metadata used to produce this SLC
    metadata_path = output_slc_path.parent / f"metadata_{polarisation}.json"

    metadata = {
        product_path.name: {
            "src_url": src_url
        }
    }

    with metadata_path.open("w") as file:
        json.dump(metadata, file, indent=2)
