"""
Geoscience Australia module to temporarily replace or substitute py_gamma.py.

Gamma's py_gamma module has a race condition which affects the data returned
when calling executables. This module replaces the py_gamma's threaded approach
with a serial interface to avoid race conditions & ensure the data is returned.
"""

import os
import functools
import subprocess
import warnings

import py_gamma as py_gamma_broken


class AltGammaException(Exception):
    """Generic exception class for the alternate Gamma interface."""

    pass


# potentially installed gamma packages
_GAMMA_PACKAGES = ("DISP", "DIFF", "IPTA", "ISP", "LAT", "MSP", "GEO")

GAMMA_INSTALL_DIR = None
GAMMA_INSTALLED_PACKAGES = None
GAMMA_INSTALLED_EXES = None

COUT = "cout"
CERR = "cerr"


def find_gamma_installed_packages(install_dir):
    """Search install_dir for Gamma pkgs. Return list of packages."""
    res = tuple(n for n in _GAMMA_PACKAGES if n in os.listdir(install_dir))

    if res is None or len(res) == 0:
        msg = "No Gamma packages found in {}"
        raise AltGammaException(msg.format(install_dir))

    return res


def find_gamma_installed_exes(install_dir, packages):
    """
    Search package dirs for Gamma exes.

    Returns {k=exe_name: v=exe_relative_path}.
    """
    ignored_exes = ["ASAR_XCA"]  # duplicate program, for unrelated Envisat data
    dirs = [os.path.join(install_dir, p, "bin") for p in packages]

    exes = {}
    for d in dirs:
        for dirpath, _, filenames in os.walk(d):
            for f in filenames:
                fullpath = os.path.join(dirpath, f)

                if os.access(fullpath, os.R_OK):  # only add executables
                    if f in exes and f not in ignored_exes:
                        msg = "{} duplicate in Gamma exe lookup under {}. Skipped!"
                        warnings.warn(msg.format(f, exes[f]))
                    else:
                        exes[f] = fullpath

    return exes


def subprocess_wrapper(cmd, *args, **kwargs):
    """Shim function to map py_gamma args to subprocess.run()."""
    cmd_list = [cmd, " ".join(args)]

    p = subprocess.run(
        cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )

    if COUT in kwargs:
        kwargs[COUT].extend(p.stdout.split("\n"))

    if CERR in kwargs:
        kwargs[CERR].extend(p.stderr.split("\n"))

    return p.returncode


class AltGamma:
    """Alternate interface class to temporarily(?) replace the py_gamma.py module."""

    # map through to the original
    ParFile = py_gamma_broken.ParFile

    def __init__(self, install_dir=None, gamma_exes=None):
        # k=program, v=exe path relative to install dir
        self._gamma_exes = gamma_exes if gamma_exes else {}
        self.install_dir = install_dir

    def __getattr__(self, name):
        """Dynamically lookup Gamma programs as methods to avoid hardcoding."""
        if self.install_dir is None:
            msg = 'Gamma install_dir not set. Check the GAMMA_INSTALL_DIR env var, or the setup code!'
            raise AltGammaException(msg)

        if name not in self._gamma_exes:
            msg = "Unrecognised Gamma program '{}', check calling function.\nKnown GAMMA exes:\n{}"
            raise AttributeError(msg.format(name, self._gamma_exes))

        cmd = os.path.join(self.install_dir, self._gamma_exes[name])
        return functools.partial(subprocess_wrapper, cmd)


try:
    GAMMA_INSTALL_DIR = os.environ["GAMMA_INSTALL_DIR"]
except KeyError:
    pass

if GAMMA_INSTALL_DIR:
    GAMMA_INSTALLED_PACKAGES = find_gamma_installed_packages(GAMMA_INSTALL_DIR)
    GAMMA_INSTALLED_EXES = find_gamma_installed_exes(
        GAMMA_INSTALL_DIR, GAMMA_INSTALLED_PACKAGES
    )
    pg = AltGamma(GAMMA_INSTALL_DIR, GAMMA_INSTALLED_EXES)

    # HACK: InSAR packaging workflow requires pg.__file__, fake it so the AltGamma shim looks
    # like the actual py_gamma module. Hopefully this shouldn't break anything.
    pg.__file__ = os.path.join(GAMMA_INSTALL_DIR, "py_gamma.py")
else:
    # assume user will configure manually
    warnings.warn('GAMMA_INSTALL_DIR not set, user needs to configure this in code...')
    pg = AltGamma()
