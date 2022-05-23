#!/bin/bash
# This script simply creates a .txt file with the CLI help output for every gamma command
# into the ./gamma_usage directory - for use by gamma_usage2py.py - intended to run on gadi

GAMMA_VERSION=20211208

mkdir -p ./gamma_usage_${GAMMA_VERSION}/{DIFF,DISP,ISP,LAT,MSP}

for m in DIFF DISP ISP LAT MSP; do
    for i in /g/data/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-${GAMMA_VERSION}/$m/bin/*; do
        echo $i
        timeout 7 $i &> ./gamma_usage_${GAMMA_VERSION}/$m/$(basename $i).txt
    done
done
