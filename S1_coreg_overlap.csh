#! /bin/csh -f

echo "S1_coreg_overlap: Script to determine a co-registration offset based on the burst overlap v1.1 23-Nov-2015 uw"
echo " "
if ($#argv < 5)then
  echo "usage: S1_coreg_overlap <RSLC1_tab> <RSLC2_tab> <pair> <off> <off_out> [cc_thresh] [fraction_thresh] [ph_stdev_thresh] [cleaning] [RSLC3_tab]"
  echo "       RSLC1_tab   (input) 3 column list of TOPS master image (SLC, SLC_par, TOPS_par; row order IW1, IW2, IW3)"
  echo "       RSLC2_tab   (input) 3 column list of TOPS slave image (SLC, SLC_par, TOPS_par; row order IW1, IW2, IW3)"
  echo "       pair        (input) ID used for InSAR (e.g. 20141003_20141015)"
  echo "       off         (input) offset parameter file (with refinement offset polynomials)"
  echo "       off_out     (output) corrected offset parameter file (with refinement offset polynomials)"
  echo "       cc_thresh   coherence threshold used (default = 0.8)"
  echo "       fraction_thresh   minimum valid fraction of unwrapped phase values used (default = 0.01)"
  echo "       ph_stdev_thresh   phase standard deviation threshold (default = 0.8 radian)"
  echo "       cleaning    flag to indicate if intermediate files are deleted (default = 1 --> deleted,  0: not deleted)"
  echo "       RSLC3_tab   (input) 3 column list of already available  co-registered TOPS slave image to use for overlap interferograms"
  echo " "
  exit
endif

# History:
# 14-Jan-2015: checked that SLC and TOPS_par in RSLC2_tab are correctly used
#              only the burst SLC name but not the burst SLC parameter filename or TOPS_par are used
#              --> correct even with corrupt TOPS_par in RSLC2_tab
# 15-Jan-2015: activitated deleting of files used
# 16-Jan-2015: avoid division by 0.0 for overlap regions with no valid samples
# 6-May-2015: add weighting with ph_fraction
#             added cc_thresh, ph_stdev_thresh, ph_stdev_thresh to command line
# 8-Jun-2015: added 
# 10-Jun-2015: offset_lines is now determined for each sub-swath based on the starting times of the first two bursts
# 10-Aug-2015: modifed SLC_copy command line to support both FCOMPLEX and SCOMPLEX SLC format
# 23-Nov-2015: checking existance and size of unwrapped phase files to avoid error messages


# defaults for input parameters
set samples = "0"
set sum = "0.0"
set samples_all = "0"
set sum_all = "0.0"
set sum_weight_all = "0.0"
set cc_thresh = "0.8"
set fraction_thresh = "0.01"
set stdev_thresh = "0.8"   # phase offset estimation standard deviation in a burst overlap region in radian
set cleaning = "1"   # 1: yes

# read input parameters from command line
set RSLC1_tab = $1
set RSLC2_tab = $2
set p = $3
set off = $4
set off_out = $5

if ($#argv >= 6) set cc_thresh = $6
if ($#argv >= 7) set fraction_thresh = $7
if ($#argv >= 8) set stdev_thresh = $8
if ($#argv >= 9) set cleaning = $9
if ($#argv >= 10) set RSLC3_tab = $10

set fraction10000_thresh = `echo "$fraction_thresh" | awk '{printf "%d", $1*10000}'`
set stdev10000_thresh = `echo "$stdev_thresh" | awk '{printf "%d", $1*10000}'`

# initialize the output text file $p.results
echo "$p.results" > $p.results
echo "thresholds applied: cc_thresh: $cc_thresh,  ph_fraction_thresh: $fraction_thresh, ph_stdev_thresh (rad): $stdev_thresh"  >> $p.results
echo ""  >> $p.results
echo "IW  overlap  ph_mean ph_stdev ph_fraction   (cc_mean cc_stdev cc_fraction)    weight" >> $p.results

# check if indicated files exist
echo "test if required input/output files and directories exist"
if (-e "$1" == 0) then 
  echo "ERROR: RSLC1_tab file ($1) does not exist"; exit(-1)
endif 
if (-e "$2" == 0) then 
  echo "ERROR: RSLC2_tab parameter file ($2) does not exist"; exit(-1)
endif 
if (-e "$4" == 0) then 
  echo "ERROR: offset parameter file ($4) does not exist"; exit(-1)
endif 
if ( ($#argv >= 10) && (-e "$10" == 0 ) ) then 
  echo "ERROR: RSLC3_tab parameter file ($10) does not exist"; exit(-1)
endif 

###################################################################################################################

# determine number of rows of RSLC1_tab file
set tmp=`echo "$RSLC1_tab"  | awk '(NR>=1){print NF}' $1 `
set nrows=`echo "$tmp" | awk '(NR==1){print NF}'`

# determine number of colums of RSLC1_tab file
set ncols=`echo "$RSLC1_tab"  | awk '(NR==1){print NF}' $1`
echo "$RSLC1_tab nrows: $nrows   ncols: $ncols"

# determine number of rows of RSLC2_tab file
set tmp=`echo "$RSLC2_tab"  | awk '(NR>=1){print NF}' $1 `
set nrows=`echo "$tmp" | awk '(NR==1){print NF}'`

# determine number of colums of RSLC2_tab file
set ncols=`echo "$RSLC2_tab"  | awk '(NR==1){print NF}' $1`
echo "$RSLC2_tab nrows: $nrows   ncols: $ncols"

# read burst SLC filenames from first line of $RSLC1_tab
set RSLC1_IW1_slc=`awk '(NR==1){print $1}' $RSLC1_tab`
set RSLC1_IW1_par=`awk '(NR==1){print $2}' $RSLC1_tab`
set RSLC1_IW1_TOPS=`awk '(NR==1){print $3}' $RSLC1_tab`
echo "RSLC1_IW1: $RSLC1_IW1_slc $RSLC1_IW1_par $RSLC1_IW1_TOPS"

# read burst SLC filenames from first line of  $RSLC2_tab
set RSLC2_IW1_slc=`awk '(NR==1){print $1}' $RSLC2_tab`
set RSLC2_IW1_par=`awk '(NR==1){print $2}' $RSLC2_tab`
set RSLC2_IW1_TOPS=`awk '(NR==1){print $3}' $RSLC2_tab`
echo "RSLC2_IW1: $RSLC2_IW1_slc $RSLC2_IW1_par $RSLC2_IW1_TOPS"

if ($#argv >= 10) then
  # read burst SLC filenames from first line of  $RSLC3_tab
  set RSLC3_IW1_slc=`awk '(NR==1){print $1}' $RSLC3_tab`
  set RSLC3_IW1_par=`awk '(NR==1){print $2}' $RSLC3_tab`
  set RSLC3_IW1_TOPS=`awk '(NR==1){print $3}' $RSLC3_tab`
  echo "RSLC3_IW1: $RSLC3_IW1_slc $RSLC3_IW1_par $RSLC3_IW1_TOPS"
endif

# read burst SLC filenames from second line of $RSLC1_tab
if ( "$nrows" > "1" ) then
  set RSLC1_IW2_slc=`awk '(NR==2){print $1}' $RSLC1_tab`
  set RSLC1_IW2_par=`awk '(NR==2){print $2}' $RSLC1_tab`
  set RSLC1_IW2_TOPS=`awk '(NR==2){print $3}' $RSLC1_tab`
  echo "RSLC1_IW2: $RSLC1_IW2_slc $RSLC1_IW2_par $RSLC1_IW2_TOPS"
endif

# read burst SLC filenames from second line of $RSLC2_tab
if ( "$nrows" > "1" ) then
  set RSLC2_IW2_slc=`awk '(NR==2){print $1}' $RSLC2_tab`
  set RSLC2_IW2_par=`awk '(NR==2){print $2}' $RSLC2_tab`
  set RSLC2_IW2_TOPS=`awk '(NR==2){print $3}' $RSLC2_tab`
  echo "RSLC2_IW2: $RSLC2_IW2_slc $RSLC2_IW2_par $RSLC2_IW2_TOPS"
endif

if ($#argv >= 10) then
  # read burst SLC filenames from second line of $RSLC3_tab
  if ( "$nrows" > "1" ) then
    set RSLC3_IW2_slc=`awk '(NR==2){print $1}' $RSLC3_tab`
    set RSLC3_IW2_par=`awk '(NR==2){print $2}' $RSLC3_tab`
    set RSLC3_IW2_TOPS=`awk '(NR==2){print $3}' $RSLC3_tab`
    echo "RSLC3_IW2: $RSLC3_IW2_slc $RSLC3_IW2_par $RSLC3_IW2_TOPS"
  endif
endif

# read burst SLC filenames from third line of $RSLC1_tab
if ( "$nrows" > "2" ) then
  set RSLC1_IW3_slc=`awk '(NR==3){print $1}' $RSLC1_tab`
  set RSLC1_IW3_par=`awk '(NR==3){print $2}' $RSLC1_tab`
  set RSLC1_IW3_TOPS=`awk '(NR==3){print $3}' $RSLC1_tab`
  echo "RSLC1_IW3: $RSLC1_IW3_slc $RSLC1_IW3_par $RSLC1_IW3_TOPS"
endif

# read burst SLC filenames from third line of $RSLC2_tab
if ( "$nrows" > "2" ) then
  set RSLC2_IW3_slc=`awk '(NR==3){print $1}' $RSLC2_tab`
  set RSLC2_IW3_par=`awk '(NR==3){print $2}' $RSLC2_tab`
  set RSLC2_IW3_TOPS=`awk '(NR==3){print $3}' $RSLC2_tab`
  echo "RSLC2_IW3: $RSLC2_IW3_slc $RSLC2_IW3_par $RSLC2_IW3_TOPS"
endif

if ($#argv >= 10) then
  # read burst SLC filenames from thrid line of $RSLC3_tab
  if ( "$nrows" > "2" ) then
    set RSLC3_IW3_slc=`awk '(NR==3){print $1}' $RSLC3_tab`
    set RSLC3_IW3_par=`awk '(NR==3){print $2}' $RSLC3_tab`
    set RSLC3_IW3_TOPS=`awk '(NR==3){print $3}' $RSLC3_tab`
    echo "RSLC3_IW3: $RSLC3_IW3_slc $RSLC3_IW3_par $RSLC3_IW3_TOPS"
  endif
endif

# set some parameters used

# determine lines offset between start of burst1 and start of burst2
set azimuth_line_time = `awk '$1 == "azimuth_line_time:" {print $2}' $RSLC1_IW1_par`      
set burst_start_time_1 = `awk '$1 == "burst_start_time_1:" {print $2}' $RSLC1_IW1_TOPS`      
set burst_start_time_2 = `awk '$1 == "burst_start_time_2:" {print $2}' $RSLC1_IW1_TOPS`      
set lines_offset_float = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%f", (($2-$1)/$3)}'`
set lines_offset_IW1 = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
echo "lines_offset_IW1: $lines_offset_float $lines_offset_IW1"   # lines offset between start of burst1 and start of burst2

if ( "$nrows" > "1" ) then
  set azimuth_line_time = `awk '$1 == "azimuth_line_time:" {print $2}' $RSLC1_IW2_par`      
  set burst_start_time_1 = `awk '$1 == "burst_start_time_1:" {print $2}' $RSLC1_IW2_TOPS`      
  set burst_start_time_2 = `awk '$1 == "burst_start_time_2:" {print $2}' $RSLC1_IW2_TOPS`      
  set lines_offset_float = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%f", (($2-$1)/$3)}'`
  set lines_offset_IW2 = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
  echo "lines_offset_IW2: $lines_offset_float $lines_offset_IW2"   # lines offset between start of burst1 and start of burst2
endif

if ( "$nrows" > "2" ) then
  set azimuth_line_time = `awk '$1 == "azimuth_line_time:" {print $2}' $RSLC1_IW3_par`      
  set burst_start_time_1 = `awk '$1 == "burst_start_time_1:" {print $2}' $RSLC1_IW3_TOPS`      
  set burst_start_time_2 = `awk '$1 == "burst_start_time_2:" {print $2}' $RSLC1_IW3_TOPS`      
  set lines_offset_float = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%f", (($2-$1)/$3)}'`
  set lines_offset_IW3 = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
  echo "lines_offset_IW3: $lines_offset_float $lines_offset_IW3"   # lines offset between start of burst1 and start of burst2
endif

if (1) then # calculate lines_offset for the second scene (for compariosn)
  set azimuth_line_time = `awk '$1 == "azimuth_line_time:" {print $2}' $RSLC2_IW1_par`      
  set burst_start_time_1 = `awk '$1 == "burst_start_time_1:" {print $2}' $RSLC2_IW1_TOPS`      
  set burst_start_time_2 = `awk '$1 == "burst_start_time_2:" {print $2}' $RSLC2_IW1_TOPS`      
  set lines_offset_float = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%f", (($2-$1)/$3)}'`
  set lines_offset = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
  echo "lines_offset_IW1: $lines_offset_float $lines_offset"   # lines offset between start of burst1 and start of burst2

  if ( "$nrows" > "1" ) then
    set azimuth_line_time = `awk '$1 == "azimuth_line_time:" {print $2}' $RSLC2_IW2_par`      
    set burst_start_time_1 = `awk '$1 == "burst_start_time_1:" {print $2}' $RSLC2_IW2_TOPS`      
    set burst_start_time_2 = `awk '$1 == "burst_start_time_2:" {print $2}' $RSLC2_IW2_TOPS`      
    set lines_offset_float = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%f", (($2-$1)/$3)}'`
    set lines_offset = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
    echo "lines_offset_IW2: $lines_offset_float $lines_offset"   # lines offset between start of burst1 and start of burst2
  endif
  
  if ( "$nrows" > "2" ) then
    set azimuth_line_time = `awk '$1 == "azimuth_line_time:" {print $2}' $RSLC2_IW3_par`      
    set burst_start_time_1 = `awk '$1 == "burst_start_time_1:" {print $2}' $RSLC2_IW3_TOPS`      
    set burst_start_time_2 = `awk '$1 == "burst_start_time_2:" {print $2}' $RSLC2_IW3_TOPS`      
    set lines_offset_float = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%f", (($2-$1)/$3)}'`
    set lines_offset = `echo "$burst_start_time_1 $burst_start_time_2 $azimuth_line_time" | awk '{printf "%d", (0.5+($2-$1)/$3)}'`
    echo "lines_offset_IW3: $lines_offset_float $lines_offset"   # lines offset between start of burst1 and start of burst2
  endif
endif

# set some parameters used
set azimuth_line_time = `awk '$1 == "azimuth_line_time:" {print $2}' $RSLC1_IW1_par`      
set dDC = `echo "$azimuth_line_time $lines_offset_IW1" | awk '{printf "%f", 1739.43*$1*$2}'`
echo "dDC $dDC Hz"
set dt = `echo "$dDC " | awk '{printf "%f", 0.159154/$1}'`
echo "dt $dt s"
set dpix_factor = `echo "$dt $azimuth_line_time" | awk '{printf "%f", $1/$2}'`
echo "dpix_factor $dpix_factor azimuth pixel"
echo "azimuth pixel offset = $dpix_factor * average_phase_offset"

###################################################################################################################

# determine phase offsets for sub-swath overlap regions of first/second sub-swaths

# IW1: 
set number_of_bursts_IW1 = `awk '$1 == "number_of_bursts:" {print $2}' $RSLC1_IW1_TOPS`      
set lines_per_burst = `awk '$1 == "lines_per_burst:" {print $2}' $RSLC1_IW1_TOPS`      
set lines_offset = $lines_offset_IW1 
set lines_overlap = `echo "$lines_per_burst $lines_offset" | awk '{printf "%d", $1-$2}'`
set range_samples = `awk '$1 == "range_samples:" {print $2}' $RSLC1_IW1_par`      

set samples = "0"
set sum = "0.0"
set sum_weight = "0.0"

set i="1"
while ( "$i" < "$number_of_bursts_IW1" )
  set starting_line1 = `echo "$i $lines_offset $lines_per_burst" | awk '{printf "%d", $2+($1-1)*$3}'`
  set starting_line2 = `echo "$i $lines_offset $lines_per_burst" | awk '{printf "%d", $1*$3}'`
  echo "$i $starting_line1 $starting_line2"

  # extract SLC sections for overlap region i (i=1 --> overlap between bursts 1 and 2)
if ($#argv >= 10) then
  SLC_copy $RSLC3_IW1_slc $RSLC1_IW1_slc.par $RSLC1_IW1_slc.$i.1  $RSLC1_IW1_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap 
  SLC_copy $RSLC3_IW1_slc $RSLC1_IW1_slc.par $RSLC1_IW1_slc.$i.2  $RSLC1_IW1_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap
else
  SLC_copy $RSLC1_IW1_slc $RSLC1_IW1_slc.par $RSLC1_IW1_slc.$i.1  $RSLC1_IW1_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap 
  SLC_copy $RSLC1_IW1_slc $RSLC1_IW1_slc.par $RSLC1_IW1_slc.$i.2  $RSLC1_IW1_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap
endif

  SLC_copy $RSLC2_IW1_slc $RSLC1_IW1_slc.par $RSLC2_IW1_slc.$i.1  $RSLC2_IW1_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap
  SLC_copy $RSLC2_IW1_slc $RSLC1_IW1_slc.par $RSLC2_IW1_slc.$i.2  $RSLC2_IW1_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap 

  # calculate the 2 single look interferograms for the burst overlap region i
  # using the earlier burst --> *.int1, using the later burst --> *.int2
  if ( -e "$p.IW1.$i.off1" ) rm -f $p.IW1.$i.off1
  create_offset $RSLC1_IW1_slc.$i.1.par $RSLC1_IW1_slc.$i.1.par $p.IW1.$i.off1 1 1 1 0
  SLC_intf $RSLC1_IW1_slc.$i.1 $RSLC2_IW1_slc.$i.1 $RSLC1_IW1_slc.$i.1.par $RSLC1_IW1_slc.$i.1.par  $p.IW1.$i.off1  $p.IW1.$i.int1 1 1 0 - 0 0

  if ( -e "$p.IW1.$i.off2" ) rm -f $p.IW1.$i.off2
  create_offset $RSLC1_IW1_slc.$i.2.par $RSLC1_IW1_slc.$i.2.par $p.IW1.$i.off2 1 1 1 0
  SLC_intf $RSLC1_IW1_slc.$i.2 $RSLC2_IW1_slc.$i.2 $RSLC1_IW1_slc.$i.2.par $RSLC1_IW1_slc.$i.2.par  $p.IW1.$i.off2  $p.IW1.$i.int2 1 1 0 - 0 0

  # calculate the single look double difference interferogram for the burst overlap region i
  # insar phase of earlier burst is subtracted from interferogram of later burst
  if ( -e "$p.IW1.$i.diff_par" ) rm -f $p.IW1.$i.diff_par
  create_diff_par $p.IW1.$i.off1 $p.IW1.$i.off2 $p.IW1.$i.diff_par 0 0
  cpx_to_real $p.IW1.$i.int1 tmp $range_samples 4
  sub_phase $p.IW1.$i.int2 tmp $p.IW1.$i.diff_par $p.IW1.$i.diff 1 0

  # multi-look the double difference interferogram (200 range x 4 azimuth looks)
  multi_cpx $p.IW1.$i.diff $p.IW1.$i.off1 $p.IW1.$i.diff20 $p.IW1.$i.off20 200 4
  set range_samples20 = `awk '$1 == "interferogram_width:" {print $2}' $p.IW1.$i.off20`      
  set azimuth_lines20 = `awk '$1 == "interferogram_azimuth_lines:" {print $2}' $p.IW1.$i.off20`      
  set range_samples20_half = `awk '$1 == "interferogram_width:" {printf "%d", $2/2}' $p.IW1.$i.off20`      
  set azimuth_lines20_half = `awk '$1 == "interferogram_azimuth_lines:" {printf "%d", $2/2}' $p.IW1.$i.off20`      
  echo "range_samples20_half: $range_samples20_half"
  echo "azimuth_samples20_half: $azimuth_lines20_half"
  echo "to display double difference interferogram use:    dismph $p.IW1.$i.diff20 $range_samples20"
   
  # determine coherence and coherence mask based on unfiltered double differential interferogram
  cc_wave $p.IW1.$i.diff20  - - $p.IW1.$i.diff20.cc $range_samples20 5 5 0 
  rascc_mask $p.IW1.$i.diff20.cc - $range_samples20 1 1 0 1 1 $cc_thresh - 0.0 1.0 1. .35 1 $p.IW1.$i.diff20.cc.ras

  # adf filtering of double differential interferogram
  adf $p.IW1.$i.diff20 $p.IW1.$i.diff20.adf -  $range_samples20 0.4 16 7 2 

  # unwrapping of filtered phase considering coherence and mask determined from unfiltered double differential interferogram
  mcf $p.IW1.$i.diff20.adf $p.IW1.$i.diff20.cc $p.IW1.$i.diff20.cc.ras $p.IW1.$i.diff20.phase $range_samples20 1 0 0 - - 1 1 512 $range_samples20_half $azimuth_lines20_half

  set size = `du $p.IW1.$i.diff20.phase | awk '{print $1}'`
  echo "size: $size"

  if ( "$cleaning" == "0" ) then
    rasmph $p.IW1.$i.diff20 $range_samples20
    rasmph $p.IW1.$i.diff20.adf $range_samples20
    if (  (-e "$p.IW1.$i.diff20.phase") && ("$size" > "0") ) then
      rasrmg $p.IW1.$i.diff20.phase -  $range_samples20 1 1 0 1 1 0.333
    endif
  endif
  
  # determine overlap phase average (in radian), standard deviation (in radian), and valid data fraction
  if ( -e "$p.IW1.$i.diff20.cc" ) then
    image_stat $p.IW1.$i.diff20.cc $range_samples20 - - - - $p.IW1.$i.diff20.cc.stat
    set cc_mean = `awk '$1 == "mean:" {print $2}' $p.IW1.$i.diff20.cc.stat`      
    set cc_stdev = `awk '$1 == "stdev:" {print $2}' $p.IW1.$i.diff20.cc.stat`      
    set cc_fraction = `awk '$1 == "fraction_valid:" {print $2}' $p.IW1.$i.diff20.cc.stat`      
    set cc_fraction1000 = `echo "$cc_fraction" | awk '{printf "%d", $1*1000.}'`
  else
    set cc_mean = "0"      
    set cc_stdev =  "0"      
    set cc_fraction = "0"      
    set cc_fraction1000 = "0"
  endif
  echo "cc_fraction1000: $cc_fraction1000"

  if (  (-e "$p.IW1.$i.diff20.phase") && ("$size" > "0") ) then
    image_stat $p.IW1.$i.diff20.phase $range_samples20 - - - - $p.IW1.$i.diff20.phase.stat
    set mean = `awk '$1 == "mean:" {print $2}' $p.IW1.$i.diff20.phase.stat`	 
    set stdev = `awk '$1 == "stdev:" {print $2}' $p.IW1.$i.diff20.phase.stat`	   
    set fraction = `awk '$1 == "fraction_valid:" {print $2}' $p.IW1.$i.diff20.phase.stat`      
    set fraction1000 = `echo "$fraction" | awk '{printf "%d", $1*1000.}'`
  else
    set mean = "0"       
    set stdev = "0"       
    set fraction = "0"     
    set fraction1000 = "0"
  endif
  
  # determine fraction10000 and stdev10000 to be used for integer comparisons
  if ( "$cc_fraction1000" == "0" ) then
    set fraction10000 = "0"
  else
    set fraction10000 = `echo "$fraction $cc_fraction" | awk '{printf "%d", $1*10000./$2}'`
  endif
  set stdev10000 = `echo "$stdev" | awk '{printf "%d", $1*10000.}'`

  if ( ( "$fraction10000" > "$fraction10000_thresh" ) && ( "$stdev10000" < "$stdev10000_thresh" ) ) then    	# only for overlap regions with a significant area with high coherence
														# and phase standard deviation < stdev10000_thresh
    # set weight = "$fraction"
    set weight = `echo "$fraction $stdev" | awk '{printf "%f", $1/($2+0.1)/($2+0.1)}'`    # +0.1 to limit maximum weights for very low stdev
    set sum = `echo "$sum $mean $fraction" | awk '{printf "%f", $1+($2*$3)}'`
    set samples = `echo "$samples" | awk '{printf "%d", $1+1}'`
    set sum_weight = `echo "$sum_weight $fraction" | awk '{printf "%f", $1+$2}'`
    set sum_all = `echo "$sum_all $mean $fraction" | awk '{printf "%f", $1+($2*$3)}'`
    set samples_all = `echo "$samples_all" | awk '{printf "%d", $1+1}'`
    set sum_weight_all = `echo "$sum_weight_all $fraction" | awk '{printf "%f", $1+$2}'`
  else
    set weight = "0.000000"
  endif

# calculate average over the first sub-swath and print it out to $p.results and to the screen
if ( "$fraction1000" > "0" ) then
  echo "IW1 $i $mean $stdev $fraction ($cc_mean $cc_stdev $cc_fraction) $weight" 
  echo "IW1 $i $mean $stdev $fraction ($cc_mean $cc_stdev $cc_fraction) $weight" >> $p.results
else
  echo "IW1 $i 0.00000 0.00000 0.00000 ($cc_mean $cc_stdev $cc_fraction) $weight" 
  echo "IW1 $i 0.00000 0.00000 0.00000 ($cc_mean $cc_stdev $cc_fraction) $weight" >> $p.results
endif

  # increase overlap region counter
  set i = `echo "$i" | awk '{printf "%d", $1+1}'`
end

if ( "$samples" > "0" ) then
  set average = `echo "$sum $sum_weight" | awk '{printf "%f", $1/$2}'`
else
  set average = 0.0
endif
echo "IW1 $average" >> $p.results
echo "IW1 $average" 


###################################################################################################################

# determine phase offsets for burst overlap regions of second sub-swath

# IW2: 
if ( "$nrows" > "1" ) then  # only do this if there is more than 1 sub-swath

set number_of_bursts_IW2 = `awk '$1 == "number_of_bursts:" {print $2}' $RSLC1_IW2_TOPS`      
set lines_per_burst = `awk '$1 == "lines_per_burst:" {print $2}' $RSLC1_IW2_TOPS`      
set lines_offset = $lines_offset_IW2 
set lines_overlap = `echo "$lines_per_burst $lines_offset" | awk '{printf "%d", $1-$2}'`
set range_samples = `awk '$1 == "range_samples:" {print $2}' $RSLC1_IW2_par`      

set samples = "0"
set sum = "0.0"
set sum_weight = "0.0"

set i="1"
while ( "$i" < "$number_of_bursts_IW2" )
  set starting_line1 = `echo "$i $lines_offset $lines_per_burst" | awk '{printf "%d", $2+($1-1)*$3}'`
  set starting_line2 = `echo "$i $lines_offset $lines_per_burst" | awk '{printf "%d", $1*$3}'`
  echo "$i $starting_line1 $starting_line2"

  if ($#argv >= 10) then
    SLC_copy $RSLC3_IW2_slc $RSLC1_IW2_slc.par $RSLC1_IW2_slc.$i.1  $RSLC1_IW2_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap 
    SLC_copy $RSLC3_IW2_slc $RSLC1_IW2_slc.par $RSLC1_IW2_slc.$i.2  $RSLC1_IW2_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap
  else
    SLC_copy $RSLC1_IW2_slc $RSLC1_IW2_slc.par $RSLC1_IW2_slc.$i.1  $RSLC1_IW2_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap 
    SLC_copy $RSLC1_IW2_slc $RSLC1_IW2_slc.par $RSLC1_IW2_slc.$i.2  $RSLC1_IW2_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap
  endif

  SLC_copy $RSLC2_IW2_slc $RSLC1_IW2_slc.par $RSLC2_IW2_slc.$i.1  $RSLC2_IW2_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap
  SLC_copy $RSLC2_IW2_slc $RSLC1_IW2_slc.par $RSLC2_IW2_slc.$i.2  $RSLC2_IW2_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap 

  if ( -e "$p.IW2.$i.off1" ) rm -f $p.IW2.$i.off1
  create_offset $RSLC1_IW2_slc.$i.1.par $RSLC1_IW2_slc.$i.1.par $p.IW2.$i.off1 1 1 1 0
  SLC_intf $RSLC1_IW2_slc.$i.1 $RSLC2_IW2_slc.$i.1 $RSLC1_IW2_slc.$i.1.par $RSLC1_IW2_slc.$i.1.par  $p.IW2.$i.off1  $p.IW2.$i.int1 1 1 0 - 0 0
  if ( -e "$p.IW2.$i.off2" ) rm -f $p.IW2.$i.off2
  create_offset $RSLC1_IW2_slc.$i.2.par $RSLC1_IW2_slc.$i.2.par $p.IW2.$i.off2 1 1 1 0
  SLC_intf $RSLC1_IW2_slc.$i.2 $RSLC2_IW2_slc.$i.2 $RSLC1_IW2_slc.$i.2.par $RSLC1_IW2_slc.$i.2.par  $p.IW2.$i.off2  $p.IW2.$i.int2 1 1 0 - 0 0

  if ( -e "$p.IW2.$i.diff_par" )  rm -f $p.IW2.$i.diff_par
  create_diff_par $p.IW2.$i.off1 $p.IW2.$i.off2 $p.IW2.$i.diff_par 0 0
  cpx_to_real $p.IW2.$i.int1 tmp $range_samples 4
  sub_phase $p.IW2.$i.int2 tmp $p.IW2.$i.diff_par $p.IW2.$i.diff 1 0

  multi_cpx $p.IW2.$i.diff $p.IW2.$i.off1 $p.IW2.$i.diff20 $p.IW2.$i.off20 200 4
  set range_samples20 = `awk '$1 == "interferogram_width:" {print $2}' $p.IW2.$i.off20`      
  set azimuth_lines20 = `awk '$1 == "interferogram_azimuth_lines:" {print $2}' $p.IW2.$i.off20`      
  set range_samples20_half = `awk '$1 == "interferogram_width:" {printf "%d", $2/2}' $p.IW2.$i.off20`      
  set azimuth_lines20_half = `awk '$1 == "interferogram_azimuth_lines:" {printf "%d", $2/2}' $p.IW2.$i.off20`      
  echo "to display double difference interferogram use:    dismph $p.IW1.$i.diff20 $range_samples20"

  # determine coherence and coherence mask based on unfiltered double differential interferogram
  cc_wave $p.IW2.$i.diff20  - - $p.IW2.$i.diff20.cc $range_samples20 5 5 0 
  rascc_mask $p.IW2.$i.diff20.cc - $range_samples20 1 1 0 1 1 $cc_thresh - 0.0 1.0 1. .35 1 $p.IW2.$i.diff20.cc.ras

  # adf filtering of double differential interferogram
  adf $p.IW2.$i.diff20 $p.IW2.$i.diff20.adf -  $range_samples20 0.4 16 7 2 

  # unwrapping of filtered phase considering coherence and mask determined from unfiltered double differential interferogram
  mcf $p.IW2.$i.diff20.adf $p.IW2.$i.diff20.cc $p.IW2.$i.diff20.cc.ras $p.IW2.$i.diff20.phase $range_samples20 1 0 0 - - 1 1 512 $range_samples20_half $azimuth_lines20_half
   
  set size = `du $p.IW2.$i.diff20.phase | awk '{print $1}'`
  echo "size: $size"

  if ( "$cleaning" == "0" ) then
    rasmph $p.IW2.$i.diff20 $range_samples20
    rasmph $p.IW2.$i.diff20.adf $range_samples20
    if (  (-e "$p.IW1.$i.diff20.phase") && ("$size" > "0") ) then
      rasrmg $p.IW2.$i.diff20.phase -  $range_samples20 1 1 0 1 1 0.333
    endif
  endif
  
  # determine overlap phase average (in radian), standard deviation (in radian), and valid data fraction
  if ( -e "$p.IW2.$i.diff20.cc" ) then
    image_stat $p.IW2.$i.diff20.cc $range_samples20 - - - - $p.IW2.$i.diff20.cc.stat
    set cc_mean = `awk '$1 == "mean:" {print $2}' $p.IW2.$i.diff20.cc.stat`      
    set cc_stdev = `awk '$1 == "stdev:" {print $2}' $p.IW2.$i.diff20.cc.stat`      
    set cc_fraction = `awk '$1 == "fraction_valid:" {print $2}' $p.IW2.$i.diff20.cc.stat`      
    set cc_fraction1000 = `echo "$cc_fraction" | awk '{printf "%d", $1*1000.}'`
  else
    set cc_mean = "0"      
    set cc_stdev =  "0"      
    set cc_fraction = "0"      
    set cc_fraction1000 = "0"
  endif
  echo "cc_fraction1000: $cc_fraction1000"

  if (  (-e "$p.IW2.$i.diff20.phase") && ("$size" > "0") ) then
    image_stat $p.IW2.$i.diff20.phase $range_samples20 - - - - $p.IW2.$i.diff20.phase.stat
    set mean = `awk '$1 == "mean:" {print $2}' $p.IW2.$i.diff20.phase.stat`      
    set stdev = `awk '$1 == "stdev:" {print $2}' $p.IW2.$i.diff20.phase.stat`      
    set fraction = `awk '$1 == "fraction_valid:" {print $2}' $p.IW2.$i.diff20.phase.stat`      
    set fraction1000 = `echo "$fraction" | awk '{printf "%d", $1*1000.}'`
  else
    set mean = "0"       
    set stdev = "0"       
    set fraction = "0"     
    set fraction1000 = "0"
  endif

  # determine fraction10000 and stdev10000 to be used for integer comparisons
  if ( "$cc_fraction1000" == "0" ) then
    set fraction10000 = "0"
  else
    set fraction10000 = `echo "$fraction $cc_fraction" | awk '{printf "%d", $1*10000./$2}'`
  endif
  set stdev10000 = `echo "$stdev" | awk '{printf "%d", $1*10000.}'`


  if ( ( "$fraction10000" > "$fraction10000_thresh" ) && ( "$stdev10000" < "$stdev10000_thresh" ) ) then       	# only for overlap regions with a significant area with high coherence
													# and phase standard deviation < stdev10000_thresh
    # set weight = "$fraction"
    set weight = `echo "$fraction $stdev" | awk '{printf "%f", $1/($2+0.1)/($2+0.1)}'`
    set sum = `echo "$sum $mean $fraction" | awk '{printf "%f", $1+($2*$3)}'`
    set samples = `echo "$samples" | awk '{printf "%d", $1+1}'`
    set sum_weight = `echo "$sum_weight $fraction" | awk '{printf "%f", $1+$2}'`
    set sum_all = `echo "$sum_all $mean $fraction" | awk '{printf "%f", $1+($2*$3)}'`
    set samples_all = `echo "$samples_all" | awk '{printf "%d", $1+1}'`
    set sum_weight_all = `echo "$sum_weight_all $fraction" | awk '{printf "%f", $1+$2}'`
  else
    set weight = "0.000000"
  endif

if ( "$fraction1000" > "0" ) then
  echo "IW2 $i $mean $stdev $fraction ($cc_mean $cc_stdev $cc_fraction) $weight" 
  echo "IW2 $i $mean $stdev $fraction ($cc_mean $cc_stdev $cc_fraction) $weight" >> $p.results
else
  echo "IW2 $i 0.00000 0.00000 0.00000 ($cc_mean $cc_stdev $cc_fraction) $weight" 
  echo "IW2 $i 0.00000 0.00000 0.00000 ($cc_mean $cc_stdev $cc_fraction) $weight" >> $p.results
endif

  # increase overlap region counter
  set i = `echo "$i" | awk '{printf "%d", $1+1}'`
end

# calculate average over the second sub-swath and print it out to $p.results and to the screen
if ( "$samples" > "0" ) then
  set average = `echo "$sum $sum_weight" | awk '{printf "%f", $1/$2}'`
else
  set average = 0.0
endif
echo "IW2 $average" >> $p.results
echo "IW2 $average" 
endif

###################################################################################################################

# determine phase offsets for burst overlap regions of third sub-swath

# IW3: 
if ( "$nrows" > "2" ) then
set number_of_bursts_IW3 = `awk '$1 == "number_of_bursts:" {print $2}' $RSLC1_IW3_TOPS`      
set lines_per_burst = `awk '$1 == "lines_per_burst:" {print $2}' $RSLC1_IW3_TOPS`      
set lines_offset = $lines_offset_IW3
set lines_overlap = `echo "$lines_per_burst $lines_offset" | awk '{printf "%d", $1-$2}'`
set range_samples = `awk '$1 == "range_samples:" {print $2}' $RSLC1_IW3_par`      

set samples = "0"
set sum = "0.0"
set sum_weight = "0.0"

set i="1"
while ( "$i" < "$number_of_bursts_IW3" )
  set starting_line1 = `echo "$i $lines_offset $lines_per_burst" | awk '{printf "%d", $2+($1-1)*$3}'`
  set starting_line2 = `echo "$i $lines_offset $lines_per_burst" | awk '{printf "%d", $1*$3}'`
  echo "$i $starting_line1 $starting_line2"

  if ($#argv >= 10) then
    SLC_copy $RSLC3_IW3_slc $RSLC1_IW3_slc.par $RSLC1_IW3_slc.$i.1  $RSLC1_IW3_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap 
    SLC_copy $RSLC3_IW3_slc $RSLC1_IW3_slc.par $RSLC1_IW3_slc.$i.2  $RSLC1_IW3_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap
  else
    SLC_copy $RSLC1_IW3_slc $RSLC1_IW3_slc.par $RSLC1_IW3_slc.$i.1  $RSLC1_IW3_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap 
    SLC_copy $RSLC1_IW3_slc $RSLC1_IW3_slc.par $RSLC1_IW3_slc.$i.2  $RSLC1_IW3_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap
  endif

  SLC_copy $RSLC2_IW3_slc $RSLC1_IW3_slc.par $RSLC2_IW3_slc.$i.1  $RSLC2_IW3_slc.$i.1.par - 1. 0 $range_samples $starting_line1 $lines_overlap
  SLC_copy $RSLC2_IW3_slc $RSLC1_IW3_slc.par $RSLC2_IW3_slc.$i.2  $RSLC2_IW3_slc.$i.2.par - 1. 0 $range_samples $starting_line2 $lines_overlap 

  if ( -e "$p.IW3.$i.off1" ) rm -f $p.IW3.$i.off1
  create_offset $RSLC1_IW3_slc.$i.1.par $RSLC1_IW3_slc.$i.1.par $p.IW3.$i.off1 1 1 1 0
  SLC_intf $RSLC1_IW3_slc.$i.1 $RSLC2_IW3_slc.$i.1 $RSLC1_IW3_slc.$i.1.par $RSLC1_IW3_slc.$i.1.par  $p.IW3.$i.off1  $p.IW3.$i.int1 1 1 0 - 0 0
  if ( -e "$p.IW3.$i.off2" ) rm -f $p.IW3.$i.off2
  create_offset $RSLC1_IW3_slc.$i.2.par $RSLC1_IW3_slc.$i.2.par $p.IW3.$i.off2 1 1 1 0
  SLC_intf $RSLC1_IW3_slc.$i.2 $RSLC2_IW3_slc.$i.2 $RSLC1_IW3_slc.$i.2.par $RSLC1_IW3_slc.$i.2.par  $p.IW3.$i.off2  $p.IW3.$i.int2 1 1 0 - 0 0

  if ( -e "$p.IW3.$i.diff_par" )  rm -f $p.IW3.$i.diff_par
  create_diff_par $p.IW3.$i.off1 $p.IW3.$i.off2 $p.IW3.$i.diff_par 0 0
  cpx_to_real $p.IW3.$i.int1 tmp $range_samples 4
  sub_phase $p.IW3.$i.int2 tmp $p.IW3.$i.diff_par $p.IW3.$i.diff 1 0
  # dismph $p.IW3.$i.diff $range_samples 5
  multi_cpx $p.IW3.$i.diff $p.IW3.$i.off1 $p.IW3.$i.diff20 $p.IW3.$i.off20 200 4
  set range_samples20 = `awk '$1 == "interferogram_width:" {print $2}' $p.IW3.$i.off20`      
  set azimuth_lines20 = `awk '$1 == "interferogram_azimuth_lines:" {print $2}' $p.IW3.$i.off20`      
  set range_samples20_half = `awk '$1 == "interferogram_width:" {printf "%d", $2/2}' $p.IW3.$i.off20`      
  set azimuth_lines20_half = `awk '$1 == "interferogram_azimuth_lines:" {printf "%d", $2/2}' $p.IW3.$i.off20`      
  echo "to display double difference interferogram use:    dismph $p.IW1.$i.diff20 $range_samples20"
  
  # determine coherence and coherence mask based on unfiltered double differential interferogram
  cc_wave $p.IW3.$i.diff20  - - $p.IW3.$i.diff20.cc $range_samples20 5 5 0 
  rascc_mask $p.IW3.$i.diff20.cc - $range_samples20 1 1 0 1 1 $cc_thresh - 0.0 1.0 1. .35 1 $p.IW3.$i.diff20.cc.ras

  # adf filtering of double differential interferogram
  adf $p.IW3.$i.diff20 $p.IW3.$i.diff20.adf -  $range_samples20 0.4 16 7 2 

  # unwrapping of filtered phase considering coherence and mask determined from unfiltered double differential interferogram
  mcf $p.IW3.$i.diff20.adf $p.IW3.$i.diff20.cc $p.IW3.$i.diff20.cc.ras $p.IW3.$i.diff20.phase $range_samples20 1 0 0 - - 1 1 512 $range_samples20_half $azimuth_lines20_half
   
  set size = `du $p.IW3.$i.diff20.phase | awk '{print $1}'`
  echo "size: $size"

  if ( "$cleaning" == "0" ) then
    rasmph $p.IW3.$i.diff20 $range_samples20
    rasmph $p.IW3.$i.diff20.adf $range_samples20
    if (  (-e "$p.IW3.$i.diff20.phase") && ("$size" > "0") ) then
      rasrmg $p.IW3.$i.diff20.phase -  $range_samples20 1 1 0 1 1 0.333
    endif
  endif
  
  # determine overlap phase average (in radian), standard deviation (in radian), and valid data fraction
  if ( -e "$p.IW3.$i.diff20.cc" ) then
    image_stat $p.IW3.$i.diff20.cc $range_samples20 - - - - $p.IW3.$i.diff20.cc.stat
    set cc_mean = `awk '$1 == "mean:" {print $2}' $p.IW3.$i.diff20.cc.stat`      
    set cc_stdev = `awk '$1 == "stdev:" {print $2}' $p.IW3.$i.diff20.cc.stat`      
    set cc_fraction = `awk '$1 == "fraction_valid:" {print $2}' $p.IW3.$i.diff20.cc.stat`      
    set cc_fraction1000 = `echo "$cc_fraction" | awk '{printf "%d", $1*1000.}'`
  else
    set cc_mean = "0"      
    set cc_stdev =  "0"      
    set cc_fraction = "0"      
    set cc_fraction1000 = "0"
  endif
  echo "cc_fraction1000: $cc_fraction1000"

  if (  (-e "$p.IW3.$i.diff20.phase") && ("$size" > "0") ) then
    image_stat $p.IW3.$i.diff20.phase $range_samples20 - - - - $p.IW3.$i.diff20.phase.stat
    set mean = `awk '$1 == "mean:" {print $2}' $p.IW3.$i.diff20.phase.stat`      
    set stdev = `awk '$1 == "stdev:" {print $2}' $p.IW3.$i.diff20.phase.stat`      
    set fraction = `awk '$1 == "fraction_valid:" {print $2}' $p.IW3.$i.diff20.phase.stat`      
    set fraction1000 = `echo "$fraction" | awk '{printf "%d", $1*1000.}'`
  else
    set mean = "0"       
    set stdev = "0"       
    set fraction = "0"     
    set fraction1000 = "0"
  endif

  # determine fraction10000 and stdev10000 to be used for integer comparisons
  if ( "$cc_fraction1000" == "0" ) then
    set fraction10000 = "0"
  else
    set fraction10000 = `echo "$fraction $cc_fraction" | awk '{printf "%d", $1*10000./$2}'`
  endif
  set stdev10000 = `echo "$stdev" | awk '{printf "%d", $1*10000.}'`


  if ( ( "$fraction10000" > "$fraction10000_thresh" ) && ( "$stdev10000" < "$stdev10000_thresh" ) ) then      	# only for overlap regions with a significant area with high coherence
													# and phase standard deviation < stdev10000_thresh  
    # set weight = "$fraction"
    set weight = `echo "$fraction $stdev" | awk '{printf "%f", $1/($2+0.1)/($2+0.1)}'`
    set sum = `echo "$sum $mean $fraction" | awk '{printf "%f", $1+($2*$3)}'`
    set samples = `echo "$samples" | awk '{printf "%d", $1+1}'`
    set sum_weight = `echo "$sum_weight $fraction" | awk '{printf "%f", $1+$2}'`
    set sum_all = `echo "$sum_all $mean $fraction" | awk '{printf "%f", $1+($2*$3)}'`
    set samples_all = `echo "$samples_all" | awk '{printf "%d", $1+1}'`
    set sum_weight_all = `echo "$sum_weight_all $fraction" | awk '{printf "%f", $1+$2}'`
  else
    set weight = "0.000000"
  endif
  
if ( "$fraction1000" > "0" ) then
  echo "IW3 $i $mean $stdev $fraction ($cc_mean $cc_stdev $cc_fraction) $weight" 
  echo "IW3 $i $mean $stdev $fraction ($cc_mean $cc_stdev $cc_fraction) $weight" >> $p.results
else
  echo "IW3 $i 0.00000 0.00000 0.00000 ($cc_mean $cc_stdev $cc_fraction) $weight" 
  echo "IW3 $i 0.00000 0.00000 0.00000 ($cc_mean $cc_stdev $cc_fraction) $weight" >> $p.results
endif

  # increase overlap region counter
  set i = `echo "$i" | awk '{printf "%d", $1+1}'`
end

# calculate average over the third sub-swath and print it out to $p.results and to the screen
if ( "$samples" > "0" ) then
  set average = `echo "$sum $sum_weight" | awk '{printf "%f", $1/$2}'`
else
  set average = 0.0
endif
echo "IW3 $average" >> $p.results
echo "IW3 $average" 
endif

###################################################################################################################

# calculate global average and print it out to $p.results and the screen
if ( "$samples_all" > "0" ) then
  set average_all = `echo "$sum_all $sum_weight_all" | awk '{printf "%f", $1/$2}'`
else
  set average_all = 0.0
endif
echo "all $average_all" >> $p.results
echo "all $average_all" 

###################################################################################################################

# printout $p.results to the screen
echo ""
echo ""
more $p.results

# conversion of phase offset (in radian) to azimuth offset (in SLC pixel)
set azimuth_pixel_offset = `echo "$dpix_factor $average_all" | awk '{printf "%f", -$1*$2}'`
echo "azimuth_pixel_offset $azimuth_pixel_offset [azimuth SLC pixel]" >> $p.results
echo "azimuth_pixel_offset $azimuth_pixel_offset [azimuth SLC pixel]" 

# correct offset file for determined additional azimuth offset 
set azpol_1 = `awk '$1 == "azimuth_offset_polynomial:" {print $2}' $off`
set azpol_2 = `awk '$1 == "azimuth_offset_polynomial:" {print $3}' $off`
set azpol_3 = `awk '$1 == "azimuth_offset_polynomial:" {print $4}' $off`
set azpol_4 = `awk '$1 == "azimuth_offset_polynomial:" {print $5}' $off`
set azpol_5 = `awk '$1 == "azimuth_offset_polynomial:" {print $6}' $off`
set azpol_6 = `awk '$1 == "azimuth_offset_polynomial:" {print $7}' $off`
set azpol_1_out = `echo "$azpol_1 $azimuth_pixel_offset" | awk '{printf "%f", $1+$2}'`
echo "azpol_1_out  $azpol_1_out $azpol_2 $azpol_3 $azpol_4 $azpol_5 $azpol_6"
set_value $off $off_out "azimuth_offset_polynomial" "$azpol_1_out $azpol_2 $azpol_3 $azpol_4 $azpol_5 $azpol_6" 0

###################################################################################################################

# cleaning

if ( "$cleaning" ) then
  rm -f $p.IW?.?.*
  rm -f $RSLC1_IW1_slc.?.?
  rm -f $RSLC1_IW1_slc.?.?.par
  rm -f $RSLC2_IW1_slc.?.?
  rm -f $RSLC2_IW1_slc.?.?.par
  if ( "$number_of_bursts_IW1" > "9" ) then
    rm -f $RSLC1_IW1_slc.??.?
    rm -f $RSLC1_IW1_slc.??.?.par
    rm -f $RSLC2_IW1_slc.??.?
    rm -f $RSLC2_IW1_slc.??.?.par
 endif
endif

if ( ( "$cleaning" ) && ( "$nrows" > "1") ) then
  rm -f $RSLC1_IW2_slc.?.?
  rm -f $RSLC1_IW2_slc.?.?.par
  rm -f $RSLC2_IW2_slc.?.?
  rm -f $RSLC2_IW2_slc.?.?.par
  if ( "$number_of_bursts_IW2" > "9" ) then
    rm -f $RSLC1_IW2_slc.??.?
    rm -f $RSLC1_IW2_slc.??.?.par
    rm -f $RSLC2_IW2_slc.??.?
    rm -f $RSLC2_IW2_slc.??.?.par
 endif
endif

if ( ( "$cleaning" ) && ( "$nrows" > "2") ) then
  rm -f $RSLC1_IW3_slc.?.?
  rm -f $RSLC1_IW3_slc.?.?.par
  rm -f $RSLC2_IW3_slc.?.?
  rm -f $RSLC2_IW3_slc.?.?.par
  if ( "$number_of_bursts_IW3" > "9" ) then
    rm -f $RSLC1_IW3_slc.??.?
    rm -f $RSLC1_IW3_slc.??.?.par
    rm -f $RSLC2_IW3_slc.??.?
    rm -f $RSLC2_IW3_slc.??.?.par
 endif
endif

exit


