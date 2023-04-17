# Note: Due to the fact the minimum version we support is 20191203 - we just import the proxy unmodified (as the machine generated proxy is for this version already)
import insar.gamma.generated.py_gamma_proxy
import inspect

PyGammaProxyBase = insar.gamma.generated.py_gamma_proxy.PyGammaProxy

class PyGammaProxy(PyGammaProxyBase):

    def create_offset(self, SLC1_par: str, SLC2_par: str, OFF_par: str, algorithm = None, rlks = None, azlks = None, iflg = 0):
        supplied_args = self._clean_call_args(locals(), inspect.signature(self.create_offset))

        if self.validate_inputs:
            self._validate_create_offset(*supplied_args)

        if self.mock_outputs:
            self._mock_create_offset_outputs(*supplied_args)

        return self._gamma_call("ISP", "create_offset", supplied_args)
