#!/bin/bash
# This script simply creates a .txt file with the CLI help output for every gamma command
# into the ./gamma_usage directory - for use by gamma_usage2py.py - intended to run on gadi

mkdir ./gamma_usage/{DIFF,DISP,ISP,LAT,MSP}

for m in DIFF DISP ISP LAT MSP; do
    for i in /g/data/dg9/SOFTWARE/dg9-apps/GAMMA/GAMMA_SOFTWARE-20191203/$m/bin/*; do
        echo $i
        timeout 7 $i &> ./gamma_usage/$m/$(basename $i).txt
    done
done

