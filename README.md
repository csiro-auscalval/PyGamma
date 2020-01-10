## EO Datasets

A tool process Sentinel-1 SLC to Aanalysis Ready Data using GAMMA SOFTWARE

## Installation

    python setup.py install --prefix=<prefix> 

Python 3.6+ is supported.

## Operating System tested
Linux

## GAMMA-SOFTWARE requirements

GAMMA-SOFTWARE must be installed and PATHS are in appended to a system PATH.
Only GAMMA-SOFTWARE released after June 2019 are supported. 
Python wrapper (pygamma) available in GAMMA-SOFTWARE is used in this gamma_insar
tools. 
Export the parent directory of pygamma.py file located in GAMMA-SOFTWARE. 
`export PYTHONPATH=<path-to-gamma-software>:$PYTHONPATH`

## Usage
`gamma_insar ARD --vector-file <path-to-vector-file> --start-date <start-date> --end-date <end-date> --workdir <path-to-workdir> --outdir <path-to-outdir> --workers <number of workers> --local-scheduler` 




