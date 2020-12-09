# OUSD Compensation Calculation

## Usage

### Generate all data

    # ./run.sh END_BLOCK OUTPUT_DIR ADDRESS_LIST JSONRPC_ENDPOINT
    ./run.sh 11297907 data/ metadata/unique_addresses.txt http://eth-mainnet.alchemyapi.io/v1/asdf1234

### Extract data from Ethereum

    # ./extract.sh END_BLOCK OUTPUT_DIR ADDRESS_LIST JSONRPC_ENDPOINT
    ./extract.sh 11297907 data/ metadata/unique_addresses.txt http://eth-mainnet.alchemyapi.io/v1/asdf1234

### Run final calculations

    # python3 transform.py -o OUT_DIR -s BLOCK_START -e BLOCK_END -b metadata/blacklisted.txt
    python transform.py -o data/ -s 11272254 -e 11415240 -b metadata/blacklisted.txt

## Extracted Data

- OUSD balances at block `11272254` and given `END_BLOCK`
- Uniswap LP balances at block `11272254` and given `END_BLOCK`
- Sushiswap LP balances at block `11272254` and given `END_BLOCK`
- Mooniswap LP balances at block `11272254` and given `END_BLOCK`
- Snowswap Staker balances at block `11272254` and given `END_BLOCK`
- Uniswap Swap data after `11272254` until given `END_BLOCK`
- Sushiswap Swap data after `11272254` until given `END_BLOCK`
- Mooniswap Swap data after `11272254` until given `END_BLOCK` (semi-manual)
