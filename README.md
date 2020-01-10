## GAMMA-INSAR

A tool to process Sentinel-1 SLC to Aanalysis Ready Data using GAMMA SOFTWARE.

## Installation

    python setup.py install --prefix=<prefix> 

Python 3.6+ is supported.

## Operating System tested
Linux

## Supported Satellites and Sensors
* Sentinel-1A/B

## Requirements
* [attrs>=17.4.0]
* [Click>=7.0]
* [GDAL>=2.4]
* [geopandas>=0.4.1]
* [luigi>=2.8.3]
* [matplotlib>=3.0.3]
* [numpy>=1.8]
* [pandas>-0.24.2]
* [pyyaml>=3.11]
* [rasterio>=1,!=1.0.3.post1,!=1.0.3]
* [structlog>-16.1.0]
* [shapely>=1.5.13]
* [spatialist==0.4]
* [GAMMA-SOFTWARE >= June 2019 release]

`export PYTHONPATH=<path-to-gamma-software>:$PYTHONPATH`

## Usage
`gamma_insar ARD --vector-file <path-to-vector-file> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --workers <number-of-workers> --local-scheduler` 




