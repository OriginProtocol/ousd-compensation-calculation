#!/bin/bash
###################################################################
# This script extracts data form primary blockchain source to CSVs
# we will use in the next stages.
#
# Its main focus is on account balances, LP balances, and swap
# data for known AMMs.
#
# Usage
# -----
# ./extract.sh 11297907 data/ metadata/unique_addresses.txt http://eth-mainnet.alchemyapi.io/v1/asdf1234
###################################################################

LOG_LEVEL="INFO"

OUSD_ADDRESS="0x2A8e1E676Ec238d8A992307B495b45B3fEAa5e86"
WETH_ADDRESS="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDT_ADDRESS="0xdac17f958d2ee523a2206206994597c13d831ec7"
USDC_ADDRESS="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
SUSHISWAP_FACTORY_ADDRESS="0xc0aee478e3658e2610c5f7a4a2e1777ce9e4f2ac"
SNOWSWAP_FACTORY_ADDRESS="0x89042f84ae007433E863fE107C2BA1A9DA3cDC96"
SNOWSWAP_GEYSER_ADDRESS="0x7c2Fa8c30DB09e8B3c147Ac67947829447BF07bD"

BLOCK_START="11272254"
BLOCK_START_INCLUSIVE=$((BLOCK_START+1))
BLOCK_END="$1"
OUT_DIR="$2"
ADDRESS_LIST="$3"
JSONRPC_ENDPOINT="$4"

echo "Parameters"
echo "======================================"
echo "BLOCK_END: $BLOCK_END"
echo "OUT_DIR: $OUT_DIR"
echo "ADDRESS_LIST: $ADDRESS_LIST"
echo "JSONRPC_ENDPOINT: $JSONRPC_ENDPOINT"
echo "======================================"

if [[ -z "$BLOCK_END" ]]; then
    echo "Missing argument"
    exit 1
fi
if [[ -z "$OUT_DIR" ]]; then
    echo "Missing argument"
    exit 1
fi
if [[ -z "$ADDRESS_LIST" ]]; then
    echo "Missing argument"
    exit 1
fi
if [[ -z "$JSONRPC_ENDPOINT" ]]; then
    echo "Missing argument"
    exit 1
fi

# Make user verify
read -r -p "Continue? [Y/n] " continue

case $continue in
    [yY][eE][sS]|[yY])
    : # noop
    ;;

    [nN][oO]|[nN])
    exit 1
    ;;

    *)
    exit 1
    ;;
esac

# These files are referenced in transform scripts.  Beware chancing them.
OUSD_BALANCES_BEFORE="$OUT_DIR/ousd_balances_$BLOCK_START.csv"
OUSD_BALANCES_AFTER="$OUT_DIR/ousd_balances_$BLOCK_END.csv"
UNISWAP_LP_BEFORE="$OUT_DIR/uniswap_lp_$BLOCK_START.csv"
UNISWAP_LP_AFTER="$OUT_DIR/uniswap_lp_$BLOCK_END.csv"
SUSHISWAP_LP_BEFORE="$OUT_DIR/sushiswap_lp_$BLOCK_START.csv"
SUSHISWAP_LP_AFTER="$OUT_DIR/sushiswap_lp_$BLOCK_END.csv"
MOONISWAP_LP_BEFORE="$OUT_DIR/mooniswap_lp_$BLOCK_START.csv"
MOONISWAP_LP_AFTER="$OUT_DIR/mooniswap_lp_$BLOCK_END.csv"
SNOWSWAP_STAKING_BEFORE="$OUT_DIR/snowswap_stakers_$BLOCK_START.csv"
SNOWSWAP_STAKING_AFTER="$OUT_DIR/snowswap_stakers_$BLOCK_END.csv"

UNISWAP_SWAPS="$OUT_DIR/uniswap_swaps_$BLOCK_START-$BLOCK_END.csv"
SUSHISWAP_SWAPS="$OUT_DIR/sushiswap_swaps_$BLOCK_START-$BLOCK_END.csv"
MOONISWAP_SWAPS="$OUT_DIR/mooniswap_swaps_$BLOCK_START-$BLOCK_END.csv"

# Do not reuse directories to prevent overwriting
test -d $OUT_DIR
if [[ "$?" -eq "0" ]]; then
    echo "$OUT_DIR/ exists!"
    exit 1
fi

echo "Creating output directory $OUT_DIR/"

mkdir -p $OUT_DIR

echo "Generating comparison data between blocks $BLOCK_START to $BLOCK_END..."

CREDITS_PER_TOKEN_ADJUSTMENT=$(python3 credits_per_token.py -b $BLOCK_START -a $OUSD_ADDRESS -u $JSONRPC_ENDPOINT)

echo "Using CPT of $CREDITS_PER_TOKEN_ADJUSTMENT for OUSD price correction."

###
# Uniswap
###

echo "Extracting account balance data..."

# OUSD Balances
cat $ADDRESS_LIST | python ousd_balances.py \
    -b $BLOCK_START \
    -u $JSONRPC_ENDPOINT > $OUSD_BALANCES_BEFORE

cat $ADDRESS_LIST | python ousd_balances.py \
    -b $BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -u $JSONRPC_ENDPOINT > $OUSD_BALANCES_AFTER

echo "Extracting Uniswap LP data (OUSD-WETH)..."

# OUSD-WETH
python uniswap_lps.py \
    -b $BLOCK_START \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $WETH_ADDRESS >> $UNISWAP_LP_BEFORE

python uniswap_lps.py \
    -b $BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $WETH_ADDRESS >> $UNISWAP_LP_AFTER

echo "Extracting Uniswap LP data (OUSD-USDT)..."

# OUSD-USDT
python uniswap_lps.py \
    -b $BLOCK_START \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $USDT_ADDRESS >> $UNISWAP_LP_BEFORE

python uniswap_lps.py \
    -b $BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $USDT_ADDRESS >> $UNISWAP_LP_AFTER

echo "Extracting Uniswap LP data (OUSD-USDC)..."

# OUSD-USDC
python uniswap_lps.py \
    -b $BLOCK_START \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $USDC_ADDRESS >> $UNISWAP_LP_BEFORE

python uniswap_lps.py \
    -b $BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $USDC_ADDRESS >> $UNISWAP_LP_AFTER

###
# Sushiswap
###

echo "Extracting Sushiswap LP data (OUSD-USDT)..."

# SushiSwap OUSD-USDT
python sushiswap_lps.py \
    -b $BLOCK_START \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $USDT_ADDRESS > $SUSHISWAP_LP_BEFORE

python sushiswap_lps.py \
    -b $BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -u $JSONRPC_ENDPOINT \
    -x $OUSD_ADDRESS \
    -y $USDT_ADDRESS > $SUSHISWAP_LP_AFTER

###
# Mooniswap
###

echo "Extracting Mooniswap LP data (OUSD-USDT)..."

# Mooniswap OUSD-USDT
python mooniswap_lps.py \
    -a 0x20d01749ccf2b689b758e07c597d9bb35370c378 \
    -b $BLOCK_START \
    -u $JSONRPC_ENDPOINT > $MOONISWAP_LP_BEFORE

python mooniswap_lps.py \
    -a 0x20d01749ccf2b689b758e07c597d9bb35370c378 \
    -b $BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -u $JSONRPC_ENDPOINT > $MOONISWAP_LP_AFTER

###
# Snowswap staking
###

echo "Extracting Snowswap staking data..."

# Snowswap
python snowswap_stakers.py \
    -b $BLOCK_START \
    -t $OUSD_ADDRESS \
    -u $JSONRPC_ENDPOINT > $SNOWSWAP_STAKING_BEFORE

python snowswap_stakers.py \
    -b $BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -t $OUSD_ADDRESS \
    -u $JSONRPC_ENDPOINT > $SNOWSWAP_STAKING_AFTER

###
# Uniswap atomic swaps/trades
###

echo "Extracting Uniswap swap data (OUSD-WETH)..."

# Uniswap swaps
python uniswap_swaps.py \
    --start=$BLOCK_START_INCLUSIVE \
    --end=$BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -x $OUSD_ADDRESS \
    -y $WETH_ADDRESS \
    -u $JSONRPC_ENDPOINT > $UNISWAP_SWAPS

echo "Extracting Uniswap swap data (OUSD-USDT)..."

python uniswap_swaps.py \
    --start=$BLOCK_START_INCLUSIVE \
    --end=$BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -x $OUSD_ADDRESS \
    -y $USDT_ADDRESS \
    -u $JSONRPC_ENDPOINT >> $UNISWAP_SWAPS

echo "Extracting Uniswap swap data (OUSD-USDC)..."

python uniswap_swaps.py \
    --start=$BLOCK_START_INCLUSIVE \
    --end=$BLOCK_END \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -x $OUSD_ADDRESS \
    -y $USDC_ADDRESS \
    -u $JSONRPC_ENDPOINT >> $UNISWAP_SWAPS

###
# Sushiswap atomic swaps/trades
###

echo "Extracting Sushiswap swap data (OUSD-USDT)..."

python uniswap_swaps.py \
    --start=$BLOCK_START_INCLUSIVE \
    --end=$BLOCK_END \
    -f $SUSHISWAP_FACTORY_ADDRESS \
    -c $CREDITS_PER_TOKEN_ADJUSTMENT \
    -x $OUSD_ADDRESS \
    -y $USDT_ADDRESS \
    -u $JSONRPC_ENDPOINT > $SUSHISWAP_SWAPS

###
# Mooniswap swaps
###

echo "\"Extracting\" Mooniswap swap data (OUSD-USDT)..."

# There was only one relevant swap after the attack (0xecc04494bfe9c4499ac79a2b7de5f2f919867df482c9f62e9a73643d17afbbe6)
#
# Function: swap(address fromToken, address toToken, uint256 amount, uint256 minReturn, address referrer) ***
# 
# MethodID: 0xd5bcb9b5
# [0]:  0000000000000000000000002a8e1e676ec238d8a992307b495b45b3feaa5e86
# [1]:  000000000000000000000000dac17f958d2ee523a2206206994597c13d831ec7
# [2]:  0000000000000000000000000000000000000000000000363232fc22560f90a3 (999741410655450665123) (corrected: 388691629789658673248)
# [3]:  0000000000000000000000000000000000000000000000000000000008bd1ec1 (146611905)
# [4]:  00000000000000000000000068a17b587caf4f9329f0e372e3a78d23a46de6b5
#
# token0,token1,block_number,in_address,out_address,swap_direction,token0_value,token1_value,token_in,token_out,token0_relevance,tx_hash
echo '"0x2A8e1E676Ec238d8A992307B495b45B3fEAa5e86","0xdAC17F958D2ee523a2206206994597C13D831ec7","11273269","0x578bc5366c0fd5cf0f399314c73ab10c626ab413","0x578bc5366c0fd5cf0f399314c73ab10c626ab413","sell","388691629789658673248","500000","0x2A8e1E676Ec238d8A992307B495b45B3fEAa5e86","0xdac17f958d2ee523a2206206994597c13d831ec7","in","0xecc04494bfe9c4499ac79a2b7de5f2f919867df482c9f62e9a73643d17afbbe6"' > $MOONISWAP_SWAPS

