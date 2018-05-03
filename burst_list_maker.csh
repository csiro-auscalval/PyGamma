#!/bin/csh

# simple script to generate a burst list file for long Sentinel-1 stacks
# MCG 1 November 2017

set burst_start = 6
set burst_end = 10

echo >! burst.list

foreach scene (`awk '{print $1}' scenes.list`)

    echo $scene "1" $burst_start $burst_end >> burst.list
    echo $scene "2" $burst_start $burst_end >> burst.list
    echo $scene "3" $burst_start $burst_end >> burst.list

end

echo >> burst.list
