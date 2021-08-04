# Build: docker build -t pygamma_workflow .
# Usage: docker run -v $(pwd):/usr/src/gamma_insar:ro -t -i pygamma_workflow pytest
#        docker run -v $(pwd):/usr/src/gamma_insar -t -i pygamma_workflow pytest --cov-report=html --cov=insar tests

FROM osgeo/gdal:ubuntu-small-latest

VOLUME ["/usr/src/gamma_insar"]

# Setup container environment
WORKDIR /usr/src/install
COPY requirements.txt ./
RUN apt-get update
RUN apt-get install -y python3-pip libfreetype-dev
RUN pip3 install --no-cache-dir -r requirements.txt

# Run pytest
ENV PYTHONPATH=${PYTHONPATH}:/usr/src/gamma_insar
WORKDIR /usr/src/gamma_insar
CMD [ "pytest" ]
