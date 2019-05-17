#!/bin/bash


##### DRAFT SCRIPT, NOT TESTED YET #####

display_usage() {
    echo ""
    echo "*******************************************************************************"
    echo "* create_bridges:  View unwrapped ifg with wrapped ifg and unwrapping flag    *"
    echo "*                  file to determine if any bridges need to be created (for   *"
    echo "*                  branch-cut unwrapping method only).                        *"
    echo "*                                                                             *"
    echo "*                  NOTE:                                                      *"
    echo "*                  Will automatically open the bridges text file for editing  *"
    echo "*                  Run script from individual interferogram directory         *"
    echo "*                                                                             *"
    echo "* input:  [flag_file]  phase unwrapping flag file (*_filt_cc.flag)            *"
    echo "*                                                                             *"
    echo "* author: Sarah Lawrie @ GA       07/01/2016, v1.0                            *"
    echo "*******************************************************************************"
    echo -e "Usage: create_bridges.bash [flag_file]"
    }

if [ $# -lt 1 ]
then 
    display_usage
    exit 1
fi

proc_file=$1

if [ $2 -lt "10000000" -o $3 -lt "10000000" ]; then
    echo "ERROR: Scene ID needed in YYYYMMDD format"
    exit 1
else
    master=$2
    slave=$3
fi



# Load generic GAMMA functions
source ~/repo/gamma_insar/gamma_functions

# Load variables and directory paths
proc_variables $proc_file
final_file_loc

# Load GAMMA to access GAMMA programs
source $config_file

# Print processing summary to .o & .e files
PBS_processing_details $project $track $master-$slave

######################################################################

# File names
dem_master_names
dem_file_names
ifg_file_names


master=20180914
slave=20180926
track_dir=/g/data1a/dg9/INSAR_ANALYSIS/WA_EQ_SEPT2018/S1/GAMMA/T090D
ifg_dir=$track_dir/INT/$master-$slave

r_master_mli=/g/data1a/dg9/INSAR_ANALYSIS/WA_EQ_SEPT2018/S1/GAMMA/T090D/SLC/20180914/r20180914_VV_4rlks.mli
r_master_mli_par=$r_master_mli.par
ifg_filt_cc=$ifg_dir/20180914-20180926_VV_4rlks_filt.cc
ifg_filt=$ifg_dir/20180914-20180926_VV_4rlks_filt.int

cd $ifg_dir

ifg_width=`grep range_samples $r_master_mli_par | awk '{print $2}'`
ifg_coh_thres=0.5










# multiples of the average intensity for neutrons
neutron_thres=6


# starting range pixel for unwrapping (default is image centre)
#start_x=975
#start_y=845


corr_flag=$ifg_dir/branch_corr.flag

corr_org_flag=$ifg_dir/"corr_org_"$ifg_coh_thres.flag
corr_neut_flag=$ifg_dir/"corr_neut_"$ifg_coh_thres.flag
corr_rescc_flag=$ifg_dir/"corr_rescc_"$ifg_coh_thres.flag
corr_treecc_flag=$ifg_dir/"corr_treecc_"$ifg_coh_thres.flag


# 1. Mask low correlation areas (orange)
#      - create initial flagfile based on coherence threshold
#      - low correlation areas identified (low SNR)   
#corr_flag $ifg_filt_cc $corr_org_flag $ifg_width $ifg_coh_thres 
#disflag $corr_org_flag $ifg_width
corr_flag $ifg_filt_cc $corr_flag $ifg_width $ifg_coh_thres 


# 2. Generate neutrons (using master scene's intensity image) (white)
#      - neutron is placed in flag file if the intensity is 'neutron_thres' times the average image intensity
#      - reduces search area size around residues for generating branches and creates dense network of branch cuts
#cp $corr_org_flag $corr_neut_flag
#neutron $r_master_mli $corr_neut_flag $ifg_width $neutron_thres
#disflag $corr_neut_flag $ifg_width

neutron $r_master_mli $corr_flag $ifg_width 6



# 3. Determine phase residues (blue and red)
#      - residues are areas of discontinuities in the wrapped phase field
#      - use of 'cc' does not consider phases in low coherence areas
#cp $corr_neut_flag $corr_rescc_flag
#residue_cc $ifg_filt $corr_rescc_flag $ifg_width
#disflag $corr_rescc_flag $ifg_width
residue_cc $ifg_filt $corr_flag $ifg_width


# 4. Use marked areas (low SNR, neutrons, residues) to construct branch cuts (yellow)
#      - cuts are drawn between residues (regardless of +/- sign)
#      - cuts are not crossed during phase unwrapping
#cp $corr_rescc_flag $corr_treecc_flag
#tree_cc $corr_treecc_flag $ifg_width 64
#disflag $corr_treecc_flag $ifg_width
tree_cc $corr_flag $ifg_width 64

# 5. Unwrap interferogram
#      - starts at user-defined location (default is image centre) and continued by region growing for the entire area connected 
#        to the starting location avoiding low correlation areas and without crossing neutral trees.
#      - start unwrapping at pixel location which has high coherence and lies within an area of high coherence (dark area in flag file).
#grasses $ifg_filt $corr_treecc_flag $ifg_unw $ifg_width - - - - $start_x $start_y 
#grasses $ifg_filt $corr_flag branch_unw $ifg_width - - - - $start_x $start_y 

grasses $ifg_filt $corr_flag branch_unw $ifg_width - - - - - -



############

# 6. Construct bridges between disconnected regions
#      - unwrapping may be continued in areas disconected from the already unwrapped area by constructing bridges between unwrapped and wrapped locations

rastree $corr_flag branch_unw $ifg_filt $ifg_width - - - tree.ras
disras tree.ras



# 7. Unwrap disconnected areas using user defined bridges
#      - bridge reads smoothed interferogram, flagfile, the unwrapped phase (unwrapped previously using grasses) and the bridges 
#        file (containing location coordinates of starting and ending location of bridges and expected multiple of 2PI phase offset between the two locations).

bridge $ifg_flit $corr_flag branch_unw bridges.txt $ifg_width























UNW


 ## Produce unwrapping validity mask based on smoothed coherence
    GM rascc_mask $ifg_filt_cc - $ifg_width 1 1 0 1 1 $ifg_coh_thres 0 - - - - 1 $ifg_mask

# offset to phase reference location pixel
#ifg_refrg=1694
#ifg_refaz=1173


 ## Use model to unwrap filtered interferogram
	GM unw_model $ifg_filt branch_unw_model $ifg_unw $ifg_width $ifg_refrg $ifg_refaz 0.0






ifg_coh_thres=0.3
rascc_mask $ifg_filt_cc - $ifg_width 1 1 0 1 1 $ifg_coh_thres 0 - - - - 1 $ifg_mask
mcf $ifg_filt - $ifg_mask $ifg_unw $ifg_width 1 - - - - $ifg_patch_r $ifg_patch_az - $ifg_refrg $ifg_refaz 1


mcf $ifg_filt $ifg_filt_cc $ifg_mask $ifg_unw $ifg_width 1 - - - - $ifg_patch_r $ifg_patch_az - $ifg_refrg $ifg_refaz 1






############################################

# ref point same for both methods

ifg_refrg=2069
ifg_refaz=619















###################################




# geocode and geotiff branch-cut unw results

width_in=`grep range_samp_1: $dem_diff | awk '{print $2}'`
width_out=`grep width: $eqa_dem_par | awk '{print $2}'`
geocode_back branch_unw $width_in $dem_lt_fine branch_unw_eqa $width_out - 1 0 - -
data2geotiff $eqa_dem_par branch_unw_eqa 2 branch_unw_eqa.tif








# use unw model with eq area replaced with branch-cut results

rascc_mask $ifg_filt_cc - $ifg_width 1 1 0 1 1 $ifg_coh_thres 0 - - - - 1 $ifg_mask
thres_1=`echo $ifg_coh_thres + 0.2 | bc`
thres_max=`echo $thres_1 + 0.2 | bc`

rascc_mask_thinning $ifg_mask $ifg_filt_cc $ifg_width $ifg_mask_thin 3 $ifg_coh_thres $thres_1 $thres_max

mcf $ifg_filt $ifg_filt_cc $ifg_mask_thin $ifg_unw_thin $ifg_width 1 - - - - $ifg_patch_r $ifg_patch_az - $ifg_refrg $ifg_refaz 1

interp_ad $ifg_unw_thin $ifg_unw_model $ifg_width 32 8 16 2


# geocode and geotiff model

geocode_back $ifg_unw_model $width_in $dem_lt_fine mcf_model_eqa $width_out - 1 0 - -
data2geotiff $eqa_dem_par mcf_model_eqa 2 mcf_model_eqa.tif


# ifg_unw_model merged with branch-cut




unw_model $ifg_filt branch_unw_model2 $ifg_unw $ifg_width $ifg_refrg $ifg_refaz 0.0






mcf $ifg_filt $ifg_filt_cc $ifg_mask $ifg_unw"0" $ifg_width 1 - - - - $ifg_patch_r $ifg_patch_az - $ifg_refrg $ifg_refaz 1
interp_ad $ifg_unw"0" $ifg_unw_model $ifg_width 32 8 16 2



























# create image of flag file
rastree $corr_treecc_flag - - $ifg_width - - - $corr_treecc_flag.ras
















# bridges

bridge











# construction of bridges between disconnected regions

# unwrapping may be continued in areas disconected from teh already unwrapped area by constructing bridges between unwrapped and not unwrapped locations

rastree 







# unwrap disconnected areas using user defined bridges


# bridge reads smoothed interferogram, flagfile, the unwrapped phase (unwrapped previously using grasses) and the bridges file (containing location coordinates of starting and ending location of bridges and expected multiple of 2PI  phase offset between the two locations).

bridge 











# tree generation program (e.g. tree_cc or tree_gzw) connects these changes to create neutral trees that will not generate large global unwrapping errors




tree_edit








        # phase unwrapping of disconnected areas using user defined bridges (done after initial unwrapping with 'grasses')
	if [ $bridge_flag == yes ]; then
	   if [ ! -e $int_unw ]; then
		echo "ERROR: Cannot locate unwrapped interferogram (*.unw). Please run this script from with bridge flag set to 'no' and then re-run with flag set to 'yes'"
		exit 1
	   else
		cp -f $int_unw $int_unw_org #save original unw ifg
		bridge $int_filt $cc_flag $int_unw $bridge $int_width
           fi
	else
	    :
	fi






































exit

int_dir=pwd
cd $int_dir

flag_file=`echo $1 | cut -d'.' -f1`
mas_slv=`echo $flag_file | awk -F _ '{print $1}'`
polar=`echo $flag_file | awk -F _ '{print $2}'`
ifm_rlks=`echo $flag_file | awk -F _ '{print $3}'`
mas_slv_name=$mas_slv"_"$polar"_"$ifm_rlks

# files 
int_unw=$int_dir/$mas_slv_name.unw
int_filt=$int_dir/$mas_slv_name"_filt.int"
flag_ras=$int_dir/$mas_slv_name"_filt_cc_flag.ras"

# file width
dem_dir= ../DEM
diff_dem=$dem_dir/"diff_"*$polar*$ifm_rlks.par
int_width=`grep range_samp_1 $diff_dem | awk '{print $2}'`

# bridge file
bridge=$int_dir/$mas_slv_name.bridges


# view flag file and images
rastree $flag_file $int_unw $int_filt $int_width - - - $flag_ras

# open bridges file for editing
if [ ! -f $bridge ]; then
    echo "col_unw " > temp1
    echo "row_unw " > temp2
    echo "col_wrp " > temp3
    echo "row_wrp " > temp4
    echo "phs_offset" > temp5
    paste temp1 temp2 temp3 temp4 temp5 > $bridge
    rm -f temp1 temp2 temp3 temp4 temp5
    emacs $bridge
else
    emacs $bridge
fi








# dark pixels will be unwrapped, pixels in any other colour will not be unwrapped (neutrons, residues)


	## Mask low correlation areas

	# create flagfile (0 below threshold, 1 above threshold)
corr_flag $ifg_filt_cc corr_org.flag $ifg_width $ifg_coh_thres 

disflag corr_org.flag $ifg_width



	## Generation of neutrons (using master scene's intensity image)
# neutrons = neutrons based upon intensity used for guiding the generation of branch cuts (trees) in phase unwrapping

cp corr_org015.flag corr_neut.flag
neutron $r_master_mli corr_neut.flag $ifg_width 6

disflag corr_neut.flag $ifg_width



# Determine phase residues under consideration of low coherence areas
# residues are important for the phase unwrapping process. Growing the phase around a residue leads to an inconsistency of 2P

cp corr_neut.flag corr_rescc.flag
residue_cc $ifg_filt corr_rescc.flag $ifg_width

disflag corr_rescc.flag $ifg_width


# determines phase residues
cp corr_neut.flag corr_res.flag
residue $ifg_filt corr_res.flag $ifg_width

disflag corr_res.flag $ifg_width




# uses the low correlation areas and the residues to construct a tree-like structure. The tree-like structure will not be crossed during the phase unwrapping to localize phase jumps to the regions defined by the cuts
cp corr_res.flag corr_treecc.flag
tree_cc corr_treecc.flag $ifg_width 64

disflag corr_treecc.flag $ifg_width


# uses residues and neutrons to construct a tree-like structure of branch cuts connecting residues and neutrons. Phase discontinuities are localized to the branch cuts.
cp corr_res2.flag corr_tree.flag
tree_gzw corr_tree.flag $ifg_width 64

disflag corr_tree.flag $ifg_width




# Unwrapping of the interferometric phase based on the complex valued interferogram, the phase unwrapping flag file, and, if existing, the already partially unwrapped phse file

# upwraping starts at uer-defined location and continued by region growing for the entire area connected to the starting location avoiding low correlation areas and without crossing neutral trees.

# start unwrapping at pixel location whic has high coherence and lies within an area of high coherence.
# starting range pixel for unwrapping (default is image centre)
start_x=
start_y=



grasses $ifg_filt corr.flag - $ifg_width - - - - $start_x $start_y 1






# construction of bridges between disconnected regions

# unwrapping may be continued in areas disconected from teh already unwrapped area by constructing bridges between unwrapped and not unwrapped locations

rastree 

















# tree generation program (e.g. tree_cc or tree_gzw) connects these changes to create neutral trees that will not generate large global unwrapping errors




tree_edit








        # phase unwrapping of disconnected areas using user defined bridges (done after initial unwrapping with 'grasses')
	if [ $bridge_flag == yes ]; then
	   if [ ! -e $int_unw ]; then
		echo "ERROR: Cannot locate unwrapped interferogram (*.unw). Please run this script from with bridge flag set to 'no' and then re-run with flag set to 'yes'"
		exit 1
	   else
		cp -f $int_unw $int_unw_org #save original unw ifg
		bridge $int_filt $cc_flag $int_unw $bridge $int_width
           fi
	else
	    :
	fi





