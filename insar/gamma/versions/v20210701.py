# We base the 20210701 proxy off of the 20191203 release
import os
import inspect
from pathlib import Path

from insar.gamma.versions.v20191203 import PyGammaProxy as PyGammaProxy_v20191203
from PIL import Image
import numpy as np
import insar.constant as const

class PyGammaProxy(PyGammaProxy_v20191203):

    # Note: This is not the only set of functions that changed in 20210701
    # - this is just the subset of functions that we use in `gamma_insar` that changed.
    # - we don't port versions we don't use.

    # The main issue of this release is all of the rasterisation programs were deleted and replaced with a few more-generic versions
    # rasdt_pwr is the main program for rasterising linear data now, rascpx and rasmph_pwr for complex data
    #
    # These programs are more generic, and use custom colour ramps to basically implement all the different raster program logic in just
    # a few simpler programs.

    def rashgt(self, hgt, pwr, width, start_hgt = None, start_pwr = None, nlines = None, pixavr = None, pixavaz = None, m_cycle = None, scale = None, exp = None, LR = None, rasf: str = None):
        supplied_args = self._clean_call_args(locals(), inspect.signature(self.rashgt))

        # Validate & mock normally
        if self.validate_inputs:
            self._validate_rashgt(*supplied_args)

        if self.mock_outputs:
            self._mock_rashgt_outputs(*supplied_args)

        # LR parameter was removed, thankfully we never use it.
        if LR and LR != const.NOT_PROVIDED and str(LR) != "1":
            raise ValueError("LR parameter is no longer supported!")

        # But translate to new rasdt_pwr program
        translated_args = {
            "data": hgt,
            "pwr": pwr,
            "width": width,
            "start": start_pwr,
            "nlines": nlines,
            "pixavx": pixavr,
            "pixavy": pixavaz,
            # Cycle gradient every `m_cycle` units
            "min": 0,
            "max": m_cycle,
            # rasght repeated the colour ramp (value wrapping w/ modulo)
            "cflg": 1,
            # rashgt just did a grayscale colour ramp
            "cmap": "gray.cm",
            "rasf": rasf,
            "scale": scale,
            "exp": exp,
            "bits": None
        }

        return self._gamma_call("DISP", "rasdt_pwr", list(translated_args.values()))


    def rasrmg(self, unw, pwr, width, start_unw = None, start_pwr = None, nlines = None, pixavr = None, pixavaz = None, ph_scale = None, scale = None, exp = None, ph_offset = None, LR = None, rasf: str = None, cc = None, start_cc = None, cc_min = None):
        supplied_args = self._clean_call_args(locals(), inspect.signature(self.rasrmg))

        # Validate & mock normally
        if self.validate_inputs:
            self._validate_rasrmg(*supplied_args)

        if self.mock_outputs:
            self._mock_rasrmg_outputs(*supplied_args)

        # LR parameter was removed, thankfully we never use it.
        if LR and LR != const.NOT_PROVIDED and str(LR) != "1":
            raise ValueError("LR parameter is no longer supported!")

        # GAMMA doesn't let you raster different regions of the phase/intensity images,
        # presumably because they really SHOULD line up pixel to pixel.
        if start_unw != start_pwr:
            raise ValueError("Must refer to same region in both images (start_unw must equal start_pwr)")

        # We don't support correlation inputs anymore either
        if cc or cc_min or start_cc:
            raise ValueError("Correlation input data no longer supported! (eg:, cc, cc_min, start_cc)")

        # We don't implement power/intensity scaling (see justification below)
        if pwr and str(pwr) != "-":
            raise NotImplementedError("pwr intensity scaling not implemented!")

        # Load colour map
        cmap = Path(os.environ["DISP_HOME"]) / "cmaps" / "rmg.cm"
        if not cmap.exists():
            raise FileNotFoundError("rmg.cm colour map is missing!")

        cmap = cmap.read_text().splitlines()
        cmap = [list(map(int, i.split())) for i in cmap]
        cmap = np.array(cmap, dtype=object).astype(np.uint8)

        # Implementation justification:
        #
        # Newer versions of GAMMA can only raster FLOAT data with ras_linear or rasdt_pwr, unfortunately while
        # rasdt_pwr would be ideal for us... it only applies offset/scaling to the "display" data (not the source data)
        # and as such can't implement the modulo/scaling we used to do faithfully.
        #
        # Additionally, their `float_math` program also lacks a modulo operation - so it's simpler for us to just
        # load the data and raster it ourselves...
        #
        # To keep this manual implementation simpler, we do NOT implement the intensity scaling logic - we only
        # raster the original data.

        #
        # Step 1. Read the data
        # - this is easy, GAMMA simply stores it as a raw sequence of float values (FLOAT data is a requirement of rasrmg thankfully)
        #
        data = np.fromfile(unw, dtype='>f4', count=-1)
        data = data.reshape((-1, width))
        height = data.shape[0]

        #
        # Step 2. apply downsampling (via PIL)
        #
        if pixavr or pixavaz:
            downsample_x = int(pixavr)
            downsample_y = int(pixavaz)

            downsampled = Image.fromarray(data).resize((width // downsample_x, height // downsample_y), Image.BOX)
            data = np.asarray(downsampled)

        # Create a mask for later
        mask = data == 0.0

        #
        # Step 3. apply data scaling
        #

        # Apply phase offset & scale
        if ph_offset:
            data -= ph_offset

        if ph_scale:
            data *= ph_scale

        # Cycle colour every 2pi radians (starting from -pi)
        data = np.mod(data + np.pi, np.pi * 2)

        #
        # Step 4. apply the final colour map (data is currently in grayscale / gray.cm)
        #
        # Note: This would typically done by GAMMA's `ras2ras` but even THAT seems to be completely broken / doesn't apply colour maps...
        # so we ALSO do this ourselves...
        #
        data /= (np.pi * 2)
        data *= 255.0
        data = cmap[data.astype(np.uint8)]
        data[mask] = [0, 0, 0]

        Image.fromarray(data).save(rasf)

        return 0, [], []

    def rascc(self, cc, pwr, width, start_cc = None, start_pwr = None, nlines = None, pixavr = None, pixavaz = None, cmin = None, cmax = None, scale = None, exp = None, LR = None, rasf: str = None):
        supplied_args = self._clean_call_args(locals(), inspect.signature(self.rascc))

        # Validate & mock normally
        if self.validate_inputs:
            self._validate_rascc(*supplied_args)

        if self.mock_outputs:
            self._mock_rascc_outputs(*supplied_args)

        # LR parameter was removed, thankfully we never use it.
        if LR and LR != const.NOT_PROVIDED and str(LR) != "1":
            raise ValueError("LR parameter is no longer supported!")

        # GAMMA doesn't let you raster different regions of the correlation/intensity images,
        # presumably because they really SHOULD line up pixel to pixel.
        if start_cc != start_pwr:
            raise ValueError("Must refer to same region in both images (start_unw must equal start_pwr)")

        translated_args = {
            "data": cc,
            "pwr": pwr,
            "width": width,
            "start": start_pwr,
            "nlines": nlines,
            "pixavx": pixavr,
            "pixavy": pixavaz,
            # rascc used default [0.1,0.9] scaling by default
            "min": cmin if cmin is not None else 0.1,
            "max": cmax if cmax is not None else 0.9,
            "cflg": 1,
            # rashcc uses cc ramp
            "cmap": "cc.cm",
            "rasf": rasf,
            "scale": scale,
            "exp": exp,
            # Using whatever output format GAMMA thinks is appropriate for rascc
            "bits": None
        }

        return self._gamma_call("DISP", "rasdt_pwr", list(translated_args.values()))

    def rasSLC(self, SLC: str, width, start = None, nlines = None, pixavr = None, pixavaz = None, scale = None, exp = None, LR = None, data_type = None, header = None, rasf: str = None):
        supplied_args = self._clean_call_args(locals(), inspect.signature(self.rasSLC))

        # Validate & mock normally
        if self.validate_inputs:
            self._validate_rasSLC(*supplied_args)

        if self.mock_outputs:
            self._mock_rasSLC_outputs(*supplied_args)

        # This parameter was removed, and we never used it.
        if header:
            raise ValueError("header parameter is not supported!")

        translated_args = {
            "data": SLC,
            "width": width,
            "start": start,
            "nlines": nlines,
            "pixavx": pixavr,
            "pixavy": pixavaz,
            "scale": scale,
            "exp": exp,
            "rasf": rasf,
            "dtype": data_type
        }

        return self._gamma_call("DISP", "rasSLC", list(translated_args.values()))
