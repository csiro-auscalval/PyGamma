#!/bin/bash

user=sll547
list=list

grep -F "$user" $list | awk '{print $1}' > list2

while read job; do
    qdel $job
done < list2




