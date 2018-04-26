#! /bin/bash
# This is a example to run the S2-RUT with 2 products in parallel
# The following script can be run from any UNIX terminal by typing "bash s2_rut_parallel_test.sh"
# The users can use this as a template to accommodate more products, properties...

S2PRODUCTS=("S2A_MSIL1C_20180220T105051_N0206_R051_T30SYJ_20180221T134037.SAFE" "S2B_MSIL1C_20180225T105019_N0206_R051_T30SYJ_20180225T161518.SAFE")
basePath="/home/jg9/s2rutv2_testproduct/"

for prod in "${S2PRODUCTS[@]}";
do
    outpath=$basePath${prod:0:(-5)}_rut.dim
    /opt/snap/bin/gpt S2RutOp -Ssource=$basePath$prod -t $outpath -Pband_names="B1,B2,B3" &
done