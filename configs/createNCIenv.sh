#!/bin/bash

ENV_PATH=$1
SCRIPT_PATH=$(basename "$0")
REPO_ROOT=$(cd $(dirname $(dirname "$0")); pwd)

if [[ -z "$ENV_PATH" ]]; then
  echo "Usage: $SCRIPT_PATH <path_to_new_env_dir>"
  exit 1
fi

if [[ -e "$ENV_PATH" ]]; then
  echo ""
  echo "Error: Environment path ($ENV_PATH) already exists!"
  read -p "Hit Ctrl-C to cancel, otherwise press any key to continue... " -n1 -s
fi

# Create the directory and convert to absolute path
mkdir -p $ENV_PATH
ENV_PATH=$(cd "$ENV_PATH"; pwd)
echo ""
echo "Installing environment in $ENV_PATH"
echo ""


function cancelled {
  echo ""
  echo "Environment creation was cancelled, removing $ENV_PATH"
  rm -fr $ENV_PATH
  exit 1
}

trap cancelled SIGINT

function fail {
  echo ""
  echo "Compiling of one of the dependencies failed. Environment creation was not successful."
  exit 1
}

trap fail EXIT

NPROC=$((`nproc` > 4? `nproc` : 4))

echo "Compilers being used to generate environment:"
echo "  - $(python3 --version) [$(which python3)]"
echo "  - $(gcc --version | head -1) [$(which gcc)]"
echo ""
echo "Using $NPROC cores for compilation."
echo ""

# Activate NCI base env
pushd $REPO_ROOT > /dev/null
source configs/activateNCI.env

# Create new venv
python3 -m venv $ENV_PATH
source $ENV_PATH/bin/activate
pushd $ENV_PATH > /dev/null

# Setup environment
export PATH=$ENV_PATH/bin:$PATH
export LD_LIBRARY_PATH=${ENV_PATH}/lib:$LD_LIBRARY_PATH
export PKG_CONFIG_PATH=${ENV_PATH}/lib/pkgconfig
export CPPFLAGS="-I$ENV_PATH/include"
export CFLAGS="-I${ENV_PATH}/include"
export LDFLAGS="-L${ENV_PATH}/lib"

echo "PATH=${PATH}"
echo "CFLAGS=${CFLAGS}"
echo "LDFLAGS=${LDFLAGS}"
echo "LD_LIBRARY_PATH=${LD_LIBRARY_PATH}"
echo "PKG_CONFIG_PATH=${PKG_CONFIG_PATH}"

# Add stand-alone env script for PyGamma
sed -e 's|VENV_PATH=$1'"|VENV_PATH=$ENV_PATH|" $REPO_ROOT/configs/activateNCI.env > $ENV_PATH/NCI.env

# Upgrade pip (very important, wrong package version resolution with older PIP versions)
python -m pip install --upgrade pip wheel

# TODO: zlib and libtiff
# See: https://github.com/GeoscienceAustralia/PyGamma/issues/368

# Download and extract sources
mkdir -p $ENV_PATH/build
pushd $ENV_PATH/build

wget -nc https://zlib.net/zlib-${ZLIB_VERSION}.tar.gz || exit 1
tar -xf zlib-${ZLIB_VERSION}.tar.gz

wget -nc https://download.osgeo.org/libtiff/tiff-${TIFF_VERSION}.tar.gz || exit 1
tar -xf tiff-${TIFF_VERSION}.tar.gz

wget -nc https://github.com/OSGeo/libgeotiff/releases/download/1.7.1/libgeotiff-${GEOTIFF_VERSION}.tar.gz || exit 1
tar -xf libgeotiff-${GEOTIFF_VERSION}.tar.gz

wget -nc https://github.com/OSGeo/gdal/releases/download/v${GDAL_VERSION}/gdal-${GDAL_VERSION}.tar.gz || exit 1
tar -xf gdal-${GDAL_VERSION}.tar.gz

wget -nc http://download.osgeo.org/geos/geos-${GEOS_VERSION}.tar.bz2 || exit 1
tar -xf geos-${GEOS_VERSION}.tar.bz2

wget -nc https://download.osgeo.org/proj/proj-${PROJ_VERSION}.tar.gz || exit 1
tar -xf proj-${PROJ_VERSION}.tar.gz

wget -nc http://www.gaia-gis.it/gaia-sins/libspatialite-${SPATIALITE_VERSION}.tar.gz || exit 1
tar -xf libspatialite-${SPATIALITE_VERSION}.tar.gz

wget -nc https://www.sqlite.org/2022/sqlite-${SQLITE_VERSION}.tar.gz || exit 1
tar -xf sqlite-${SQLITE_VERSION}.tar.gz

wget -nc https://www.fftw.org/fftw-${FFTW_VERSION}.tar.gz || exit 1
tar -xf fftw-${FFTW_VERSION}.tar.gz

popd

# zlib
pushd $ENV_PATH/build/zlib-$ZLIB_VERSION
./configure --prefix=$ENV_PATH
make -j$NPROC || exit
make install || exit
popd

# libtiff
mkdir -p $ENV_PATH/build/tiff-$TIFF_VERSION/build
pushd $ENV_PATH/build/tiff-$TIFF_VERSION/build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$ENV_PATH ..
make -j$NPROC || exit
make install || exit
popd

# sqlite
pushd $ENV_PATH/build/sqlite-$SQLITE_VERSION
#CFLAGS="-DSQLITE_ENABLE_COLUMN_METADATA=1" ./configure --prefix=$ENV_PATH --enable-rtree
./configure --prefix=$ENV_PATH --enable-rtree
make -j$NPROC || exit
make install || exit
popd

# PROJ4
mkdir -p $ENV_PATH/build/proj-$PROJ_VERSION/build
pushd $ENV_PATH/build/proj-$PROJ_VERSION/build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$ENV_PATH ..
make -j$NPROC || exit
make install || exit
popd

cat << EOF | envsubst \$ENV_PATH > $ENV_PATH/lib/pkgconfig/proj.pc
prefix=$ENV_PATH
exec_prefix=$ENV_PATH
libdir=$ENV_PATH/lib
includedir=$ENV_PATH/include
datadir=$ENV_PATH/share/proj

Name: proj
Description: Cartographic Projections Library.
Requires:
Version: $PROJ_VERSION
Libs: -L$ENV_PATH/lib -lproj
Libs.Private: -lsqlite3 -lstdc++
Cflags: -I${ENV_PATH}/include
EOF

# libgeotiff
mkdir -p $ENV_PATH/build/libgeotiff-$GEOTIFF_VERSION/build
pushd $ENV_PATH/build/libgeotiff-$GEOTIFF_VERSION/build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$ENV_PATH ..
make -j$NPROC || exit
make install || exit
popd

# GEOS
mkdir -p $ENV_PATH/build/geos-$GEOS_VERSION/build
pushd $ENV_PATH/build/geos-$GEOS_VERSION/build
cmake -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$ENV_PATH ..
make -j$NPROC || exit
make install || exit
popd

# FFTW single precision (fftwf)
pushd $ENV_PATH/build/fftw-$FFTW_VERSION
./configure --prefix=$ENV_PATH --enable-single --disable-static --enable-shared --disable-dependency-tracking
make -j$NPROC || exit
make install || exit
popd

# spatialite
pushd $ENV_PATH/build/libspatialite-$SPATIALITE_VERSION
./configure --prefix=$ENV_PATH --with-sysroot=$ENV_PATH --with-geosconfig=$ENV_PATH/bin/geos-config --disable-rttopo --disable-freexl --disable-minizip --disable-libxml2 --disable-geopackage --disable-examples --disable-gcp --disable-dependency-tracking
make -j$NPROC || exit
make install || exit
popd

# GDAL
function version { echo "$@" | awk -F. '{ printf("%d%03d%03d%03d\n", $1,$2,$3,$4); }'; }
pushd $ENV_PATH/build/gdal-$GDAL_VERSION
if [ $(version $GDAL_VERSION) -lt $(version "3.5.0") ]; then
  echo "Building GDAL using autoconf"
  ./configure --prefix=$ENV_PATH --with-geos=$ENV_PATH/bin/geos-config
  make -j$NPROC || exit
  make install || exit
else
  echo "Building GDAL using CMake"
  mkdir -p build
  pushd build
  #cmake .. -DCMAKE_INSTALL_RPATH=$ENV_PATH/lib -DCMAKE_INSTALL_PREFIX=$ENV_PATH -DGEOS_LIBRARY=$ENV_PATH/lib -DCMAKE_PREFIX_PATH=$ENV_PATH -DPython_ROOT=$ENV_PATH -DPython_FIND_VIRTUALENV=ONLY -DGDAL_PYTHON_INSTALL_PREFIX=$ENV_PATH -DPROJ_LIBRARY=$ENV_PATH -DZLIB_INCLUDE_DIR=$ENV_PATH/include -DZLIB_LIBRARY_RELEASE=$ENV_PATH/lib -DSQLite3_INCLUDE_DIR=$ENV_PATH/include
  cmake .. -DCMAKE_INSTALL_PREFIX=$ENV_PATH -DCMAKE_PREFIX_PATH=$ENV_PATH 
  make -j$NPROC || exit
  make install || exit
  popd
fi
popd

# Install GDAL python dependencies
python -m pip install --upgrade --force-reinstall numpy || exit

# Install pinned GDAL dependency for our environment ensuring that numpy extensions get installed
python -m pip install --upgrade --force-reinstall "GDAL~=$GDAL_VERSION" --global-option=build_ext --global-option="$(gdal-config --cflags)"

popd > /dev/null

# Install dependencies and PyGamma into venv
python3 -m pip install -r requirements.txt || exit
python setup.py install || exit

trap EXIT

echo ""
echo "Environment successfully created!"

popd > /dev/null
