import insar.logs as logs
import importlib
import os

from typing import Type, cast
from insar.logs import GAMMA_LOGGER as LOG
from insar.py_gamma_ga import GammaInterface, auto_logging_decorator, subprocess_wrapper
from insar.gamma.generated import PyGammaProxy


def get_gamma_version() -> str:
    """
    Get the version of GAMMA being used by the `PyGamma` workflow.

    This is simply a wrapper around getting the `GAMMA_VER` env var currently, which is how
    `gammar_insar` is designed to work with it's virtual environment / configuration setup scripts.

    See `configs/activate.env` for details.
    """
    version = os.environ.get("GAMMA_VER")
    if not version:
        raise RuntimeError("Failed to detect GAMMA version (expected 'GAMMA_VER' env var)")
    return version


def create_versioned_gamma_proxy(gamma_ver: str, base_wrapper: object, exception_type: Type[Exception]) -> PyGammaProxy:
    """
    Creates a GAMMA proxy object for a specific version of GAMMA, which translates from the API for
    GAMMA version 20191203 into the user specified GAMMA version.

    This is used so `PyGamma` can be written for one specific GAMMA version without having to
    be re-written or constantly re-ported to newer versions, by instead using these translation
    layers / proxy objects.
    """
    wrapper_module = importlib.import_module(f"insar.gamma.versions.v{gamma_ver}")
    return cast(PyGammaProxy, wrapper_module.PyGammaProxy(exception_type, base_wrapper))


def create_gamma_proxy(exception_type: Type[Exception]) -> PyGammaProxy:
    """
    A convenience function for `create_versioned_gamma_proxy` that creates a proxy object for the
    currently installed version of GAMMA that wraps the `insar.py_gamma_ga` GAMMA call dispatch interface.
    """
    pg = GammaInterface(subprocess_func=auto_logging_decorator(subprocess_wrapper, exception_type, LOG))
    return create_versioned_gamma_proxy(get_gamma_version(), pg, exception_type)
