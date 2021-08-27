#!/usr/bin/env python
from pathlib import Path
import structlog

from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.sensors.rsat2 import METADATA as rsat2

# Customise Gamma shim to automatically handle basic error checking and logging
class ProcessSlcException(Exception):
    pass

_LOG = structlog.get_logger("insar")
pg = GammaInterface(
    subprocess_func=auto_logging_decorator(subprocess_wrapper, ProcessSlcException, _LOG)
)

def process_rsat2_slc(
    product_path: Path,
    pol: str,
    output_slc_path: Path
):
    """
    This function very simply processes a RADARSAT-2 SLC acquisition product
    into a a GAMMA SLC product.

    :param product_path:
        The path to the RADARSAT-2 product directory.
    :param pol:
        The polarisation of the product to process.

        This must be VV, VH, HH, or HV - and an image with data of that
        polarisation be available within the product.
    :param output_slc_path:
        The path to store the GAMMA SLC output.
    """

    if pol not in rsat2.polarisations:
        raise RuntimeError(f"Invalid polarisation: {pol}")

    if not product_path.exists():
        raise RuntimeError("The provided product path does not exist!")

    prod_path = product_path / "product.xml"
    lut_path = product_path / "lutSigma.xml"
    image_path = product_path / f"imagery_{pol}.tif"

    for p in [prod_path, lut_path, image_path]:
        if not p.exists():
            raise RuntimeError(f"Product is missing a file: {p}")

    pg.par_RSAT2_SLC(
        prod_path,
        lut_path,
        image_path,
        pol,
        output_slc_path.with_suffix(output_slc_path.suffix + ".par"),
        output_slc_path
    )
