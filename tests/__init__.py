"""Unit test package for insar."""

import atexit
import sys
import os

from unittest import mock


PY_GAMMA_MODULE = "py_gamma"

if PY_GAMMA_MODULE not in sys.modules:
    try:
        os.environ['GAMMA_VER']
    except KeyError:
        os.environ['GAMMA_VER'] = '20191203'
        def warn():
            print(f"WARNING: Environment variable GAMMA_VER was not set so it was defaulted to GAMMA_VER={os.environ['GAMMA_VER']} for mocking GAMMA and running tests.")
        if sys.stdout != sys.__stdout__:
            atexit.register(warn)
        
    # mock Gamma for local testing
    py_gamma_mock = mock.Mock()
    sys.modules[PY_GAMMA_MODULE] = py_gamma_mock
