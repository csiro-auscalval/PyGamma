#!/bin/bash

## bulk delete PBS jobs. Option to exclude jobs for deletion.

user=$USER
qstat

echo ""
echo ""
echo "Enter PBS job number/s to exclude from bulk deletion, or press Enter to continue:"
echo "     eg. 8542499 for single job, or 8542500,8542501,... for multiple jobs"

read jobs

if [ -z $jobs ]; then
    echo ""
    echo "no jobs selected for exclusion, deleting all jobs for user: "$user
    echo ""
    qstat > list1 #create list of jobs
    grep -wE "($user)" list1 > list2 #extract jobs for user
    cut -c-8 list2 > list3 #extract job numbers
    # delete jobs
    while read job; do
	qdel $job
    done < list3
    rm -f list1 list2 list3
else
    for file in $jobs; do
	if [[ $file == *,* ]]; then # multiple jobs to exclude
	    echo $file > temp1
	    sed 's/,/\n/g' temp1 > temp2
	    qstat > list1 #create list of jobs
	    grep -wE "($user)" list1 > list2 #extract jobs for user
	    cut -c-7 list2 > list3 #extract job numbers
	    grep -v -f temp2 list3 > final_list
	    echo ""
	    echo "Deleting selected jobs for user: "$user
	    echo ""
            # delete jobs
	    while read job; do
		qdel $job
	    done < final_list
	    rm -f list1 list2 list3 temp1 temp2 final_list
	else # single job to exclude
	    echo $file > temp1
	    qstat > list1 #create list of jobs
	    grep -wE "($user)" list1 > list2 #extract jobs for user
	    cut -c-7 list2 > list3 #extract job numbers
	    grep -v -f temp1 list3 > final_list
	    echo ""
	    echo "Deleting selected jobs for user: "$user
	    echo ""
            # delete jobs
	    while read job; do
		qdel $job
	    done < final_list
	    rm -f list1 list2 list3 temp1 final_list
	fi
    done
fi
