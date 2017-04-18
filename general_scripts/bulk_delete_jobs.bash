#!/bin/bash


user=txf547

nqstat > list1 #create list of jobs
grep -wE "($user)" list1 > list2 #extract jobs for user
cut -c-7 list2 > list3 #extract job numbers

# delete jobs
while read job; do
    qdel $job
done < list3

rm -f list1 list2 list3
