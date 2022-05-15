## Installation

`gamma_insar` assumes some pre-existing native dependencies are installed on the system prior to installation:
 * [Python](https://www.python.org/) (3.6+)
 * [sqlite3](https://www.sqlite.org/index.html) with [spatialite](https://www.gaia-gis.it/fossil/libspatialite/index) extension
 * [GAMMA](http://www/gamma-rs.ch)
 * [GDAL](https://gdal.org/) (2.4+ and 3.0+ have been tested)
   * Note: version required is dictated by GAMMA release
 * [PROJ](https://proj.org/) (for GAMMA/GDAL)
 * [FFTW](https://www.fftw.org/) (for GAMMA)

In addition to the above native dependencies, gamma_insar has various python dependencies listed in `requirements.txt` - the exact python package versions required is tied to the GAMMA version being used (and `requirements.txt` is as loosely as possible frozen to the versions supported by the GAMMA version used in GA's production NCI environment).

## Installation on arbitrary platforms

In platform agnostic terms, gamma_insar should work in any environment in which it's dependencies (both native + python) are installed and found in the `PATH`/`PYTHONPATH`/`LD_LIBRARY_PATH` (or relevant platform specific analgoues).

`gamma_insar` provides a Dockerfile (based on OSGEO/DAL ubuntu images) a a simple method for bringing up a compatible environment on any platform which supports Docker.

`gamma_insar` also has various scripts (found under `configs/`) in which Python virtual environments are used to setup compatible environments on platforms where native dependencies already exist (such as the NCI environment), which may be used as a reference for those wanting to create similar venvs on other platforms.

## Installation on NCI

Using `gamma_insar` on NCI of course requires a user account (to access the NCI) & membership of several NCI groups. Use [Mancini](https://my.nci.org.au/) to request membership access to the following groups:

```
v10: DEA Operations and code repositories
up71: Storage resources for GA ARD development
dg9: InSAR research
u46: DEA Development and Science (GA internal)
fj7: Sentinel Data
```

For an introduction into NCI, their [wiki covers quite a lot](https://opus.nci.org.au/display/Help/0.+Welcome+to+Gadi).

After getting NCI access, you will need a release of the `gamma_insar` code somewhere on NCI to install, such as by cloning this github repo as follows:

```BASH
# Our examples install into your home dir, change if required.
cd ~

# Note: This gets the latest development version, you might want to get a stable release instead, eg: v0.9.0
git clone -b pygamma_workflow git@github.com:GeoscienceAustralia/gamma_insar.git
```

We use Python virtual environments on gadi (using DEA modules for native dependencies) to manage installations of `gamma_insar`.  Scripts for creation and entering these environments are provided in `configs/createNCIenv.sh` and `configs/activateNCI.env` respectively.

Once logged into `gadi`, use the following command to create a new installation (assumes `~/gamma_insar` from above):

```BASH
bash ~/gamma_insar/configs/createNCIenv.sh ~/gamma_insar_install
```

The install step can take some time to download and install all the dependencies. If the command does not complete cleanly (e.g. cannot find a dir of modules), check your group memberships.

`configs/createNCIenv.sh` installs several dependencies into your venv directory, **including** a copy of the `gamma_insar` code from your release/repo. Any changes to files in your git repo **do not** automatically appear in the installation environment.

To "activate" the installation environment installed above (bringing all of the `gamma_insar` modules/scripts and it's dependencies into the environment) simply run:

```BASH
# Note: assumes you used paths from examples above
source ~/gamma_insar/configs/activateNCI.env ~/gamma_insar_install
```

All commands hence forth will be able to see the installation and it's dependencies, and all `python` and `pip` commands will also refer to the virtual environment of the `gamma_insar` installation.


Any time you want to update the `gamma_insar` code of an "active" installation environment (see above), simply run:

```BASH
cd ~/gamma_insar  # Or where ever your gamma_insar release/repo is
python setup.py install
```

This takes typically less than 30 seconds and will install the latest code from your `gamma_insar` release/repo into your installation environment (overriding the old version that was installed).
