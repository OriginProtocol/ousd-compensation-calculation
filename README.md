# OUSD Compensation Calculation

To generate all data:

    # ./run.sh END_BLOCK OUTPUT_DIR ADDRESS_LIST JSONRPC_ENDPOINT
    ./run.sh 11297907 data/ metadata/unique_addresses.txt http://eth-mainnet.alchemyapi.io/v1/asdf1234

To extract all data from blockchain untransformed:

    # ./extract.sh END_BLOCK OUTPUT_DIR ADDRESS_LIST JSONRPC_ENDPOINT
    ./extract.sh 11297907 data/ metadata/unique_addresses.txt http://eth-mainnet.alchemyapi.io/v1/asdf1234

## Data

- OUSD balances at block `11272254` and given `END_BLOCK`
- Uniswap LP balances at block `11272254` and given `END_BLOCK`
- Sushiswap LP balances at block `11272254` and given `END_BLOCK`
- Mooniswap LP balances at block `11272254` and given `END_BLOCK`
- Snowswap Staker balances at block `11272254` and given `END_BLOCK`
- Uniswap Swap data after `11272254` until given `END_BLOCK`
- Sushiswap Swap data after `11272254` until given `END_BLOCK`
- Mooniswap Swap data after `11272254` until given `END_BLOCK` (semi-manual)
