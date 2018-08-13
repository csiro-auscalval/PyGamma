#!/bin/bash

# export files from NCI for Pyrate

user=sll547
project=SURAT
sensor=PALSAR1
track=T365A

nci_dir=/g/data1/dg9/INSAR_ANALYSIS/$project/$sensor/GAMMA/$track
ga_dir=/nas/gemd/insar/INSAR_ANALYSIS/$project/$sensor/PIRATE/$track

#cd $ga_dir

# Extract plot PDFs
unw_ifm=$project"_"$sensor"_"$track"_"*"_unw_ifms.pdf"
filt_ifm=$project"_"$sensor"_"$track"_"*"_filt_ifms.pdf"
filt_cc=$project"_"$sensor"_"$track"_"*"_filt_cc.pdf"
flat_cc=$project"_"$sensor"_"$track"_"*"_flat_cc.pdf"

scp $user@raijin.nci.org.au:$nci_dir/$unw_ifm .
scp $user@raijin.nci.org.au:$nci_dir/$filt_ifm .
scp $user@raijin.nci.org.au:$nci_dir/$filt_cc .
scp $user@raijin.nci.org.au:$nci_dir/$flat_cc .


# Make directories
mkdir -p nci_pyrate_files
cd nci_pyrate_files
mkdir -p unw_ifms
mkdir -p dem_files
mkdir -p filt_ifms
mkdir -p filt_cc_files
mkdir -p flat_cc_files


# Extract Pyrate files
pyrate_dir=$nci_dir/pyrate_files

# unw files
cd unw_ifms
scp $user@raijin.nci.org.au:$pyrate_dir/unw_ifms/ifg.rsc .
scp $user@raijin.nci.org.au:$pyrate_dir/unw_ifms/unw_list .
while read file; do
    scp $user@raijin.nci.org.au:$pyrate_dir/unw_ifms/$file .
done < unw_list
cd ../

# dem files
cd dem_files
scp $user@raijin.nci.org.au:$pyrate_dir/dem_files/dem_list .
while read file; do
    scp $user7@raijin.nci.org.au:$pyrate_dir/dem_files/$file .
done < dem_list
cd ../

# int files
cd filt_ifms
scp $user@raijin.nci.org.au:$pyrate_dir/filt_ifms/int_list .
while read file; do
    scp $user@raijin.nci.org.au:$pyrate_dir/filt_ifms/$file .
done < int_list
cd ../

# filt_cc files
cd filt_cc_files
scp $user@raijin.nci.org.au:$pyrate_dir/filt_cc_files/filt_cc_list .
while read file; do
    scp $user@raijin.nci.org.au:$pyrate_dir/filt_cc_files/$file .
done < filt_cc_list
cd ../

# flat_cc files
cd flat_cc_files
scp $user@raijin.nci.org.au:$pyrate_dir/flat_cc_files/flat_cc_list .
while read file; do
    scp $user@raijin.nci.org.au:$pyrate_dir/flat_cc_files/$file .
done < flat_cc_list
cd ../


# Extract bperp files
# do later