#!/bin/bash
###################################################################
# This is the motherscript that runs all the others to generate a
# complete dataset.
###################################################################

BLOCK_END="$1"
OUT_DIR="$2"
ADDRESS_LIST="$3"
JSONRPC_ENDPOINT="$4"

###
# Extract
###
./extract.sh $BLOCK_END $OUT_DIR $ADDRESS_LIST $JSONRPC_ENDPOINT

###
# Transform
###

# ./transform.sh

###
# Load
###

# ./load.sh