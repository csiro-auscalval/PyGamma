# Build: docker build -t pygamma_workflow .
# Usage: docker run -v $(pwd):/usr/src/gamma_insar:ro -t -i pygamma_workflow pytest
#        docker run -v $(pwd):/usr/src/gamma_insar -t -i pygamma_workflow pytest --cov-report=html --cov=insar tests

FROM osgeo/gdal:ubuntu-small-latest
#FROM osgeo/gdal:ubuntu-small-3.3.1

VOLUME ["/usr/src/gamma_insar"]

# Setup container environment
WORKDIR /usr/src/install
COPY requirements.txt ./
RUN apt-get update

# Note: freetype/postgress dev requirements are weird native dependencies of some of our python deps...
RUN apt-get install -y python3-pip libfreetype-dev libpq-dev sqlite3 libsqlite3-mod-spatialite

# Install python GDAL bindings for 3.3 (as that's what gdal:ubuntu-small-3.3.1 uses)
RUN pip3 install --no-cache-dir GDAL~=3.3

# Install our general requirements after pinned-versions have been installed
RUN pip3 install --no-cache-dir -r requirements.txt

# Pretend we're running GAMMA 20191203
ENV GAMMA_VER 20191203

# Run pytest by default (if not given any other command)
ENV PYTHONPATH=${PYTHONPATH}:/usr/src/gamma_insar
WORKDIR /usr/src/gamma_insar
CMD [ "pytest" ]
