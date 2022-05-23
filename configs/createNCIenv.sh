#!/bin/bash

ENV_PATH=$1
SCRIPT_PATH=$(basename "$0")
REPO_ROOT=$(dirname $(dirname "$0"))

if [[ -z "$ENV_PATH" ]]; then
  echo "Usage: $SCRIPT_PATH <path_to_new_env_dir>"
  exit 1
fi

if [[ -e "$ENV_PATH" ]]; then
  echo "Error: env path already exists!"
  exit 1
fi

# Activate NCI base env
pushd $REPO_ROOT > /dev/null
source configs/activateNCI.env

# Create new venv
python3 -m venv $ENV_PATH
source $ENV_PATH/bin/activate
pushd $ENV_PATH > /dev/null

export PATH=$ENV_PATH/bin:$PATH
export LD_LIBRARY_PATH=$ENV_PATH/lib:$LD_LIBRARY_PATH

# Add stand-alone env script for gamma_insar
sed -e 's|VENV_PATH=$1'"|VENV_PATH=$ENV_PATH|" $REPO_ROOT/configs/activateNCI.env > $ENV_PATH/NCI.env

# Upgrade pip (very important, wrong package version resolution with older PIP versions)
python -m pip install --upgrade pip wheel

# TODO: zlib and libtiff
# See: https://github.com/GeoscienceAustralia/gamma_insar/issues/368

# Download and extract sources
mkdir -p $ENV_PATH/build
pushd $ENV_PATH/build

wget https://github.com/OSGeo/gdal/releases/download/v${GDAL_VERSION}/gdal-${GDAL_VERSION}.tar.gz
tar -xf gdal-${GDAL_VERSION}.tar.gz

wget http://download.osgeo.org/geos/geos-${GEOS_VERSION}.tar.bz2
tar -xf geos-${GEOS_VERSION}.tar.bz2

wget https://download.osgeo.org/proj/proj-${PROJ_VERSION}.tar.gz
tar -xf proj-${PROJ_VERSION}.tar.gz

wget http://www.gaia-gis.it/gaia-sins/libspatialite-${SPATIALITE_VERSION}.tar.gz
tar -xf libspatialite-${SPATIALITE_VERSION}.tar.gz

wget https://www.sqlite.org/2022/sqlite-${SQLITE_VERSION}.tar.gz
tar -xf sqlite-${SQLITE_VERSION}.tar.gz

wget https://www.fftw.org/fftw-${FFTW_VERSION}.tar.gz
tar -xf fftw-${FFTW_VERSION}.tar.gz

popd

# Install GDAL native dependencies
# PROJ4 native
mkdir -p $ENV_PATH/build/proj-$PROJ_VERSION/build
pushd $ENV_PATH/build/proj-$PROJ_VERSION/build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$ENV_PATH ..
make -j4
make install
popd

# GEOS native
mkdir -p $ENV_PATH/build/geos-$GEOS_VERSION/build
pushd $ENV_PATH/build/geos-$GEOS_VERSION/build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$ENV_PATH ..
make -j4
make install
popd

# FFTW single precision (fftwf)
pushd $ENV_PATH/build/fftw-$FFTW_VERSION
./configure --prefix=$ENV_PATH --enable-single --disable-static --enable-shared
make -j4
make install
popd

# GDAL native
pushd $ENV_PATH/build/gdal-$GDAL_VERSION
./configure --prefix=$ENV_PATH --with-proj=$ENV_PATH --with-geos=geos-config
make -j4
make install
popd

# sqlite
pushd $ENV_PATH/build/sqlite-$SQLITE_VERSION
CFLAGS="-DSQLITE_ENABLE_COLUMN_METADATA=1" ./configure --prefix=$ENV_PATH
make -j4
make install
popd

# spatialite
pushd $ENV_PATH/build/libspatialite-$SPATIALITE_VERSION
CFLAGS="-I$ENV_PATH/include -L$ENV_PATH/lib64 -lgeos_c -lgeos" ./configure --prefix=$ENV_PATH --disable-freexl --enable-module-only --with-geosconfig=$ENV_PATH/bin/geos-config --disable-rttopo --disable-minizip --disable-libxml2 --disable-geopackage --disable-examples
make -j4
make install
popd

# Install GDAL python dependencies
python -m pip install --upgrade --force-reinstall numpy

# Install pinned GDAL dependency for our environment ensuring that numpy extensions get installed
python -m pip install --upgrade --force-reinstall "GDAL~=$GDAL_VERSION" --global-option=build_ext --global-option="$(gdal-config --cflags)"

popd > /dev/null

# Install dependencies and gamma_insar into venv
python3 -m pip install -r requirements.txt
python setup.py install

echo "Environment successfully created!"
popd > /dev/null
