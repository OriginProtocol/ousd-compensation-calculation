import sys
import json
from math import floor
from decimal import Decimal
from pathlib import Path
from argparse import ArgumentParser
from web3 import Web3
from web3.logs import DISCARD

OUSD_ADDRESS = "0x2A8e1E676Ec238d8A992307B495b45B3fEAa5e86"
FACTORY_ADDRESS = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"

ME = Path(__file__).resolve()
OUSD_ABI = json.load(
    ME.parent.joinpath('metadata/OUSD.json').open()
).get('abi')
FACTORY_ABI = json.load(
    ME.parent.joinpath('metadata/IUniswapV2Factory.json').open()
).get('abi')
PAIR_ABI = json.load(
    ME.parent.joinpath('metadata/IUniswapV2Pair.json').open()
).get('abi')


def dict_get(d, path):
    pparts = path.split('.')
    lp = len(pparts)
    if lp < 1:
        return None
    elif lp > 1:
        return dict_get(d.get(pparts[0]), '.'.join(pparts[1:]))
    return d.get(path)


def parse_args(argv):
    parser = ArgumentParser()
    parser.add_argument('-s', '--start', dest='start_block', required=True,
                        help='Start of block range, inclusive')
    parser.add_argument('-e', '--end', dest='end_block', required=True,
                        help='End of block range, inclusive')
    parser.add_argument('-f', '--factory', dest='factory', default=FACTORY_ADDRESS,
                        help='Uniswap Factory address override')
    parser.add_argument('-x', dest='token_x', required=True,
                        help='Address for the first token in the pair')
    parser.add_argument('-y', dest='token_y', required=True,
                        help='Address for the second token in the pair')
    parser.add_argument('-c', '--credits-per-token', dest='credits_per_token',
                        help='Credits per token override to calculate OUSD balances')
    parser.add_argument('-u', '--url', dest='endpoint', type=str,
                        default="http://localhost:8545",
                        help='JSON-RPC endpoint to query')
    return parser.parse_args(argv)


def ousd_value_adjustment(token_balance, from_cpt, to_cpt):
    token_balance = Decimal(token_balance)
    from_cpt = Decimal(from_cpt)
    to_cpt = Decimal(to_cpt)
    credits = floor(token_balance * from_cpt / Decimal(1e18))
    return floor(credits * Decimal(1e18) / to_cpt)


def main():
    args = parse_args(sys.argv[1:])
    web3 = Web3(Web3.HTTPProvider(args.endpoint))
    ousd = web3.eth.contract(address=OUSD_ADDRESS, abi=OUSD_ABI)
    factory = web3.eth.contract(
        address=Web3.toChecksumAddress(args.factory),
        abi=FACTORY_ABI
    )

    a = Web3.toChecksumAddress(args.token_x)
    b = Web3.toChecksumAddress(args.token_y)
    start_block = int(args.start_block)
    end_block = int(args.end_block)
    credits_per_token = None

    if args.credits_per_token:
        credits_per_token = int(args.credits_per_token)

    pair_address = factory.functions.getPair(a, b).call(
        block_identifier=start_block
    )

    if not pair_address:
        print('Unable to find pair {}-{}'.format(a, b), file=sys.stderr)
        sys.exit(1)

    pair = web3.eth.contract(address=pair_address, abi=PAIR_ABI)

    # Token addresses
    token0 = pair.functions.token0().call()
    token1 = pair.functions.token1().call()

    # Zero reason this shouldn't match args
    assert token0 == a, "token0 != a"
    assert token1 == b, "token1 != b"

    swap_filter = pair.events.Swap().createFilter(
        fromBlock=start_block,
        toBlock=end_block
    )

    for event in swap_filter.get_all_entries():
        tx_hash = event.transactionHash.hex()

        # Get the receipt for the tx
        receipt = web3.eth.getTransactionReceipt(tx_hash)

        # Skip failed transactions
        if not receipt.status:
            continue

        # We don't use the address from the event because it may be a contract
        # (e.g. UniswapRouterV02)
        in_address = receipt['from']
        out_address = event.args.to

        direction = 'right'
        if event.args.amount0Out > event.args.amount1Out:
            direction = 'left'

        # Weird math, unexpected "in" value can sometimes be due to unexpected
        # balance in the pair contract that gets included in the swap
        a_change = event.args.amount0In
        b_change = event.args.amount1Out - event.args.amount1In

        if direction == 'left':
            a_change = event.args.amount0Out - event.args.amount0In
            b_change = event.args.amount1In

        token_in = token1 if direction == 'left' else token0
        token_out = token0 if direction == 'left' else token1

        token0_relevance = 'unknown'

        # Get all the swaps as part of this tx
        tx_swaps = pair.events.Swap().processReceipt(receipt, errors=DISCARD)

        if len(tx_swaps) > 0:
            # Is first or last our pair?
            first_is_pair = tx_swaps[0].address == pair_address
            last_is_pair = tx_swaps[-1].address == pair_address
            from_ousd = first_is_pair and direction == 'right'
            to_ousd = last_is_pair and direction == 'left'

            # Attempts to figure out the relevance that OUSD has to this tx
            if from_ousd and to_ousd:
                token0_relevance = 'in+out'
            elif from_ousd:  # From OUSD
                token0_relevance = 'in'
            elif first_is_pair and direction == 'left':  # Through OUSD
                token0_relevance = 'through'
            elif to_ousd:  # To OUSD
                token0_relevance = 'out'
            elif last_is_pair and direction == 'right':  # Through OUSD
                token0_relevance = 'through'
            else:
                # Deep middle kinda
                token0_relevance = 'through'

            # Get the actual final token input/output
            if not (from_ousd or to_ousd):
                if not from_ousd:
                    first_pair = web3.eth.contract(
                        address=tx_swaps[0].address,
                        abi=PAIR_ABI
                    )
                    if tx_swaps[0].args.amount0In > tx_swaps[0].args.amount1In:
                        token_in = first_pair.functions.token0().call()
                    else:
                        token_in = first_pair.functions.token1().call()
                else:
                    last_pair = web3.eth.contract(
                        address=tx_swaps[-1].address,
                        abi=PAIR_ABI
                    )
                    if tx_swaps[-1].args.amount0Out > tx_swaps[-1].args.amount1Out:
                        token_out = last_pair.functions.token0().call()
                    else:
                        token_out = last_pair.functions.token1().call()

            # Update the out_address if there's a swap chain
            for swap in tx_swaps:
                if swap.args.to != out_address:
                    out_address = swap.args.to

        # OUSD price adjustment to get around after-hack craziness
        if credits_per_token:
            block_cpt = int(ousd.functions.rebasingCreditsPerToken().call(
                block_identifier=event.blockNumber
            ), 16)

            a_change = ousd_value_adjustment(
                a_change,
                block_cpt,
                credits_per_token
            )

        # token0,token1,block_number,in_address,out_address,swap_direction,token0_amount,token1_amount,token_in,token_out,token0_relevance,tx_hash
        print('{},{},{},{},{},{},{},{},{},{},{},{}'.format(
            a,
            b,
            event.blockNumber,
            in_address,
            out_address,
            'buy' if direction == 'left' else 'sell',
            a_change,
            b_change,
            token_in,
            token_out,
            token0_relevance,
            tx_hash,
        ))


if __name__ == "__main__":
    main()
