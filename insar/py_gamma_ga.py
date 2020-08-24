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

    :param install_dir: base dir str of the Gamma install
    :param packages: sequence of strings of Gamma packages ("ISP", "DIFF" etc)
    :returns: mapping {k=exe_name: v=exe_relative_path}.
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
    """Shim to map GammaInterface methods to subprocess.run() calls for running Gamma EXEs."""
    cmd_list = [cmd, " ".join(args)]

    p = subprocess.run(
        cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True
    )

    if COUT in kwargs:
        kwargs[COUT].extend(p.stdout.split("\n"))

    if CERR in kwargs:
        kwargs[CERR].extend(p.stderr.split("\n"))

    return p.returncode


class GammaInterface:
    """
    Alternate interface class/shim to temporarily(?) replace the official py_gamma.py module.

    The GAMMA supplied py_gamma.py module is fairly new (as of July/Aug 2020) & has problems which
    this module is designed to work around.
    """

    # map through to the original
    ParFile = py_gamma_broken.ParFile

    def __init__(self, install_dir=None, gamma_exes=None, subprocess_func=None):
        """
        Create an GammaInterface shim class.
        :param install_dir: base install dir str of Gamma. If None is specified, the install dir must
                            be configured elsewhere for the dynamic
        :param gamma_exes: Mapping of {k=exe_name: v=exe_relative_path}
        :param subprocess_func: function to call Gamma exes, with signature (gamma_cmd_name, *args, **kwargs)
                                see subprocess_wrapper() in this module for an example.
        """
        # k=program, v=exe path relative to install dir
        self._gamma_exes = gamma_exes if gamma_exes else {}
        self.install_dir = install_dir
        self.subprocess_func = (
            subprocess_wrapper if subprocess_func is None else subprocess_func
        )

    def __getattr__(self, name):
        """Dynamically lookup Gamma programs as methods to avoid hardcoding."""
        if self.install_dir is None:
            msg = (
                "GammaInterface shim install_dir not set. Check for the GAMMA_INSTALL_DIR environ var, "
                "or ensure the setup code manually sets the install dir."
            )
            raise AltGammaException(msg)

        if name not in self._gamma_exes:
            msg = (
                "Unrecognised attribute '{}'. Check the calling function name, or for unimplemented"
                "attributes.\nKnown GAMMA exes for this shim are:\n{}"
            )
            raise AttributeError(msg.format(name, self._gamma_exes))

        cmd = os.path.join(self.install_dir, self._gamma_exes[name])
        return functools.partial(self.subprocess_func, cmd)


try:
    GAMMA_INSTALL_DIR = os.environ["GAMMA_INSTALL_DIR"]
except KeyError:
    # skip this under the assumption users will manually configure the shim
    pass

if GAMMA_INSTALL_DIR:
    GAMMA_INSTALLED_PACKAGES = find_gamma_installed_packages(GAMMA_INSTALL_DIR)
    GAMMA_INSTALLED_EXES = find_gamma_installed_exes(
        GAMMA_INSTALL_DIR, GAMMA_INSTALLED_PACKAGES
    )
    pg = GammaInterface(GAMMA_INSTALL_DIR, GAMMA_INSTALLED_EXES)

    # HACK: InSAR packaging workflow requires pg.__file__, fake it so the GammaInterface shim looks
    # like the actual py_gamma module. Hopefully this shouldn't break anything.
    pg.__file__ = os.path.join(GAMMA_INSTALL_DIR, "py_gamma.py")
else:
    # assume user will configure manually
    warnings.warn("GAMMA_INSTALL_DIR not set, user needs to configure this in code...")
    pg = GammaInterface()
