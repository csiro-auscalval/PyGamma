"""
TODO: Shim to substitute for py_gamma.py module which has race condition.
"""

import os
import functools
import subprocess
import warnings


class AltGammaException(Exception):
    """Generic exception class for the alternate Gamma interface."""

    pass


# potential gamma packages
_GAMMA_PACKAGES = ("DISP", "DIFF", "IPTA", "ISP", "LAT", "MSP", "GEO")

GAMMA_INSTALL_DIR = None
GAMMA_INSTALLED_PACKAGES = None
GAMMA_INSTALLED_EXES = None

COUT = "cout"
CERR = "cerr"


def find_gamma_installed_packages(install_dir):
    res = tuple(n for n in _GAMMA_PACKAGES if n in os.listdir(install_dir))

    if res is None or len(res) == 0:
        msg = "No Gamma packages found in {}"
        raise AltGammaException(msg.format(install_dir))

    return res


def find_gamma_installed_exes(install_dir, packages):
    ignored_exes = ["ASAR_XCA"]  # duplicate program, for unrelated Envisat data
    dirs = [os.path.join(install_dir, p, "bin") for p in packages]

    exes = {}
    for d in dirs:
        for dirpath, _, filenames in os.walk(d):
            for f in filenames:
                fullpath = os.path.join(dirpath, f)

                if os.access(fullpath, os.R_OK):
                    # only add executables
                    if f in exes and f not in ignored_exes:
                        msg = (
                            "{} already exists in the Gamma exe lookup under {}. Skipped!"
                        )
                        warnings.warn(msg.format(f, exes[f]))

                    exes[f] = fullpath

    return exes


def subprocess_wrapper(cmd, *args, **kwargs):
    """Shim function to map py_gamma args to subprocess.run()."""
    cmd_list = [cmd]
    cmd_list.append(" ".join(args))

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

    def __init__(self, install_dir=None, gamma_exes=None):
        self._gamma_exes = {}  # dict k= program, v=exe path relative to install dir
        self.install_dir = install_dir

    def __getattr__(self, name):
        """Dynamic lookup of Gamma functions to methods to avoid hardcoding."""
        if name not in self._gamma_exes:
            msg = "Unrecognised Gamma program '{}', check calling function"
            raise AttributeError(msg.format(name))

        cmd = os.path.join(self.install_dir, self._gamma_exes[name])
        return functools.partial(subprocess_wrapper, cmd)


try:
    GAMMA_INSTALL_DIR = os.environ["GAMMA_INSTALL_DIR"]
    # TODO: add exes here
except KeyError:
    # let user specify
    pass

if GAMMA_INSTALL_DIR:
    GAMMA_INSTALLED_PACKAGES = find_gamma_installed_packages(GAMMA_INSTALL_DIR)
    GAMMA_INSTALLED_EXES = find_gamma_installed_exes(
        GAMMA_INSTALL_DIR, GAMMA_INSTALLED_PACKAGES
    )
    pg = AltGamma(GAMMA_INSTALL_DIR, GAMMA_INSTALLED_EXES)
else:
    # assume user will configure manually
    pg = AltGamma()
