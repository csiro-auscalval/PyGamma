import insar.constant as const
import numpy as np
import inspect
import os

from insar.gamma.generated import PyGammaProxy as PyGammaProxyBase
from insar.logs import STATUS_LOGGER

print(f"Interfacing with GAMMA Proxy {__file__}")

class PyGammaProxy(PyGammaProxyBase):

#    def create_offset(self, SLC1_par: str, SLC2_par: str, OFF_par: str, algorithm = None, rlks = None, azlks = None, iflg = 0):
#        supplied_args = self._clean_call_args(locals(), inspect.signature(self.create_offset))
#
#        if self.validate_inputs:
#            self._validate_create_offset(*supplied_args)
#
#        if self.mock_outputs:
#            self._mock_create_offset_outputs(*supplied_args)
#
#        return self._gamma_call("ISP", "create_offset", supplied_args)

    def SLC_mosaic_S1_TOPS(self, SLC_tab: str, SLC: str, SLC_par: str, rlks, azlks, bflg = None, SLCR_tab: str = None):
        supplied_args = self._clean_call_args(locals(), inspect.signature(self.SLC_mosaic_S1_TOPS))

        return self._gamma_call("ISP", "SLC_mosaic_ScanSAR", supplied_args)
