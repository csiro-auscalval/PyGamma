import numpy as np
from PIL import Image
from pathlib import Path
from typing import Union, Optional

from insar.path_util import append_suffix

def convert(
    input_file: Union[Path, str],
    output_file: Optional[Union[Path, str]] = None,
    black_to_transparent: bool = True
):
    """
    Converts an image (eg: .bmp -> .png) with optional black/transparency conversion.

    :param input_file:
        The path to the input image to converted.
    :param output_file:
        The path to the converted output image.

        If this parameter is not provided, it defaults to creating a PNG image of
        the same name as the input file but in the current working directory.
    :param black_to_transparent:
        A flag which enables conversion of black input pixels into transparent pixels.

        This is useful for converting images w/ no transparency but maybe a 'no data'
        value, into a quicklook image where 'no data' becomes transparent.
    """

    if not output_file:
        output_file = append_suffix(Path(input_file.stem), ".png")

    # Convert the bitmap to a PNG w/ black pixels made transparent
    img = Image.open(input_file)
    img = np.array(img.convert('RGBA'))

    if black_to_transparent:
        img[(img[:, :, :3] == (0, 0, 0)).all(axis=-1)] = (0, 0, 0, 0)

    Image.fromarray(img).save(output_file)
