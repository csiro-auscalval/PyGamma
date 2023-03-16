## Installation

`PyGamma` wraps the commercial software [GAMMA](https://www.gamma-rs.ch). As such, installation typically assumes existence of various software dependencies are installed on the system prior to installation. Apart from Gamma, many of these are easily installed through your operating system package manager as they are open-source and commonly available. Overall, at a high-level, the dependencies are:

 * [GAMMA](https://www.gamma-rs.ch)
 * [GDAL](https://gdal.org/) (2.4+ and 3.0+ have been tested)
 * [sqlite3](https://www.sqlite.org/index.html) with [spatialite](https://www.gaia-gis.it/fossil/libspatialite/index) extension
 * [PROJ](https://proj.org/) (for GAMMA/GDAL)
 * [FFTW](https://www.fftw.org/) (for GAMMA)
 * [Python](https://www.python.org/) (3.6+)
   * Plus all the python dependencies in `requirements.txt`. The exact python package versions required is tied to the GAMMA version being used (and `requirements.txt` is as loosely as possible frozen to the versions supported by the GAMMA version used in GA's production NCI environment).

Most of those software packages above have their own dependencies but in most situations this is not an issue as your package manager will take care of those. 

## Various ways to install PyGamma

In platform agnostic terms, PyGamma should work in any environment in which its dependencies (both native + python) are installed and found in the `PATH`/`PYTHONPATH`/`LD_LIBRARY_PATH` (or relevant platform specific analogues). That said, for operational environments, two spproaches to setup all the dependencies have been developed:

1. *Virtual environment:* Two scripts have been developed (found under `configs/`) to build and initialise a virtual environment that contains all the dependencies. These dependencies are compiled from source (except GAMMA). This script has been tested on Linux and Mac. This allows a user to freeze the version of GAMMA and all its dependencies without relying on system versions of those pieces of software. This also allows testing various versions of GAMMA with various versions of dependencies in an automated way. 

2. *Docker:* `PyGamma` provides a Dockerfile (based on OSGEO/DAL ubuntu images) as a simple method for bringing up a compatible environment on any platform which supports Docker.

## Installation on the [NCI](https://www.nci.org.au)

At [Geoscience Australia](https://www.ga.gov.au) we use the *virtual environment* approach for running PyGamma on the NCI. This allows us to freeze requirements and load various versions easily. 

For an introduction into NCI, their [wiki covers quite a lot](https://opus.nci.org.au/display/Help/0.+Welcome+to+Gadi). Before starting to operate PyGamma at the NCI, you will need an NCI user account and membership of to several NCI projects. Once you have a user account, login to [this page](https://my.nci.org.au/) to request membership access to the following groups:
```
fj7: Copernicus Australia Regional Data Hub
dg9: InSAR research
```
and optionally, the following groups:
```
v10: DEA Operations and code repositories
u46: DEA Development and Science (GA internal)
up71: Storage resources for GA ARD development
```

The `fj7` project gives you access to the directory `/g/data/fj7` where all the [ESA](https://www.esa.int) data for our local region is stored. This path has folders containing the raw observational data for the various satellite missions such as Sentinel-1, Sentinel-2, Sentinel-3, etc. The managers of the Copernicus Hub run automated scripts to update this directory with any new observations that are acquired from any of these ESA satellite missions. For PyGamma, the particular mission we are concerned with is [Sentinel-1](https://en.wikipedia.org/wiki/Sentinel-1) which captures Synthetic Aperture Radar (SAR) data.

The aim of PyGamma is to take a SAR raw data (at a date / time / location) and generate various end products such as land displacement map.

After getting NCI access, you will need a release of the `PyGamma` code somewhere on NCI to install, such as by cloning this github repo as follows:

```BASH
# Our examples install into your home dir, change if required.
cd ~

# Note: This gets the latest development version, you might want to get a stable release instead, eg: v0.9.0
git clone -b pygamma_workflow git@github.com:GeoscienceAustralia/PyGamma.git
```

We use Python virtual environments on gadi (using DEA modules for native dependencies) to manage installations of `PyGamma`.  Scripts for creation and entering these environments are provided in `configs/createNCIenv.sh` and `configs/activateNCI.env` respectively.

Once logged into `gadi`, use the following command to create a new installation (assumes `~/PyGamma` from above):

```BASH
bash ~/PyGamma/configs/createNCIenv.sh ~/PyGamma_install
```

The install step can take some time to download and install all the dependencies. If the command does not complete cleanly (e.g. cannot find a dir of modules), check your group memberships.

`configs/createNCIenv.sh` installs several dependencies into your venv directory, **including** a copy of the `PyGamma` code from your release/repo. Any changes to files in your git repo **do not** automatically appear in the installation environment.

To "activate" the installation environment installed above (bringing all of the `PyGamma` modules/scripts and it's dependencies into the environment) simply run:

```BASH
# Note: assumes you used paths from examples above
source ~/PyGamma/configs/activateNCI.env ~/PyGamma_install
```

All commands hence forth will be able to see the installation and it's dependencies, and all `python` and `pip` commands will also refer to the virtual environment of the `PyGamma` installation.


Any time you want to update the `PyGamma` code of an "active" installation environment (see above), simply run:

```BASH
cd ~/PyGamma  # Or where ever your PyGamma release/repo is
python setup.py install
```

This takes typically less than 30 seconds and will install the latest code from your `PyGamma` release/repo into your installation environment (overriding the old version that was installed).
