"""Unit test package for insar."""

import sys
from unittest import mock


PY_GAMMA_MODULE = "py_gamma"

if PY_GAMMA_MODULE not in sys.modules:
    # mock Gamma for local testing
    py_gamma_mock = mock.Mock()
    msg = "This is a mock py_gamma, Gamma not found/installed on this platform"
    sys.modules[PY_GAMMA_MODULE] = py_gamma_mock
