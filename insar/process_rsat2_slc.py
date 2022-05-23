#!/usr/bin/env python
from pathlib import Path

from insar.gamma.proxy import create_gamma_proxy
from insar.sensors.rsat2 import METADATA as rsat2
import json

# Customise Gamma shim to automatically handle basic error checking and logging
class ProcessSlcException(Exception):
    pass

pg = create_gamma_proxy(ProcessSlcException)

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

    # Identify source data URL
    src_url = product_path / "src_url"
    # - if this is raw_data we've extracted from a source archive, a src_url file will exist
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
