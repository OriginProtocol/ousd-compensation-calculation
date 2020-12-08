""" Outputs the Uniswap liquidity providers LPs for a token pair.

CSV format out:

token0,token1,lp_address,lp_balance,approx_token0,approx_token1
"""
import sys
import json
from decimal import Decimal
from math import floor
from pathlib import Path
from argparse import ArgumentParser
from web3 import Web3

ME = Path(__file__).resolve()
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
OUSD_ADDRESS = "0x2A8e1E676Ec238d8A992307B495b45B3fEAa5e86"
OUSD_ABI = json.load(
    ME.parent.joinpath('metadata/OUSD.json').open()
).get('abi')
FACTORY_ADDRESS = "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f"
FACTORY_ABI = json.load(
    ME.parent.joinpath('metadata/IUniswapV2Factory.json').open()
).get('abi')
PAIR_ABI = json.load(
    ME.parent.joinpath('metadata/IUniswapV2Pair.json').open()
).get('abi')
MINIMUM_LIQUIDITY = 1000
MAX_ROUNDING_DRIFT = 10

ADD_LIQUDITY_SIG = "0xe8e33700"
ADD_LIQUDITY_ETH_SIG = "0xf305d719"


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
    parser.add_argument('-b', '--block', dest='block', default="latest",
                        help='Block number to query for (default: latest)')
    parser.add_argument('-c', '--credits-per-token', dest='credits_per_token',
                        help='Credits per token override to calculate OUSD balances')
    parser.add_argument('-x', dest='token_x', required=True,
                        help='Address for the first token in the pair')
    parser.add_argument('-y', dest='token_y', required=True,
                        help='Address for the second token in the pair')
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
    factory = web3.eth.contract(address=FACTORY_ADDRESS, abi=FACTORY_ABI)

    block_number = int(args.block)
    a = Web3.toChecksumAddress(args.token_x)
    b = Web3.toChecksumAddress(args.token_y)

    pair_address = factory.functions.getPair(a, b).call(
        block_identifier=block_number
    )

    if not pair_address:
        print('Unable to find pair {}-{}'.format(a, b), file=sys.stderr)
        sys.exit(1)

    pair = web3.eth.contract(address=pair_address, abi=PAIR_ABI)

    total_supply = pair.functions.totalSupply().call(
        block_identifier=block_number
    )
    [a_supply, b_supply, blockstamp] = pair.functions.getReserves().call(
        block_identifier=block_number
    )

    ousd = None
    current_cpt = None
    to_cpt = None
    if a == OUSD_ADDRESS or b == OUSD_ADDRESS:
        ousd = web3.eth.contract(address=OUSD_ADDRESS, abi=OUSD_ABI)
        current_cpt = int(ousd.functions.rebasingCreditsPerToken().call(
            block_identifier=block_number
        ), 16)
        if args.credits_per_token:
            to_cpt = int(args.credits_per_token)

    addresses_of_interest = []

    mints_filter = pair.events.Mint.createFilter(
        fromBlock=0,
        toBlock=block_number
    )
    mints = mints_filter.get_all_entries()

    for mint in mints:
        mint_txhash = mint['transactionHash'].hex()
        minter = dict_get(mint, 'args.sender')

        # Need to get the TX because the Mint event doesn't have the tx origin
        tx = web3.eth.getTransaction(mint_txhash)

        if not (
            tx.get('input').startswith(ADD_LIQUDITY_SIG)
            or tx.get('input').startswith(ADD_LIQUDITY_ETH_SIG)
        ):
            print('UNKNOWN FUNCTION RESULTING IN EVENT:', tx['input'])
            sys.exit(1)
        else:
            lp_addr = tx.get('from', minter)

            # minter is probably always the V2 router
            if (
                lp_addr != ZERO_ADDRESS
                and lp_addr not in addresses_of_interest
            ):
                addresses_of_interest.append(lp_addr)

    transfers_filter = pair.events.Transfer.createFilter(
        fromBlock=0,
        toBlock=block_number
    )
    transfers = transfers_filter.get_all_entries()

    for transfer in transfers:
        to_address = dict_get(transfer, 'args.to')
        if (
            to_address != ZERO_ADDRESS
            and to_address not in addresses_of_interest
        ):
            addresses_of_interest.append(to_address)

    # Now that we have all the theoretical players, get their balance as of the
    # block
    running_total = 0
    running_total_a = 0
    running_total_b = 0
    for addr in addresses_of_interest:
        lp_balance = pair.functions.balanceOf(addr).call(
            block_identifier=block_number
        )

        a_balance = 0
        b_balance = 0
        if lp_balance != 0:
            ratio = Decimal(lp_balance) / Decimal(
                total_supply - MINIMUM_LIQUIDITY
            )
            #a_balance = floor(a_supply * ratio)
            #b_balance = floor(b_supply * ratio)
            a_balance = a_supply * ratio
            b_balance = b_supply * ratio

        running_total += lp_balance
        running_total_a += a_balance
        running_total_b += b_balance

        if args.credits_per_token:
            if a == OUSD_ADDRESS and a_balance:
                a_balance = ousd_value_adjustment(
                    a_balance,
                    current_cpt,
                    to_cpt
                )
            elif b == OUSD_ADDRESS and b_balance:
                b_balance = ousd_value_adjustment(
                    b_balance,
                    current_cpt,
                    to_cpt
                )

        # token0,token1,lp_address,lp_balance,token0_value,token1_value
        print('{},{},{},{},{},{}'.format(
            a,
            b,
            addr,
            lp_balance,
            floor(a_balance),
            floor(b_balance)
        ))

    """ To ameliorate rounding errors and increase the theoretical minimum
    tick size for liquidity provision, pairs burn the first MINIMUM_LIQUIDITY
    pool tokens. For the vast majority of pairs, this will represent a trivial
    value. The burning happens automatically during the first liquidity
    provision, after which point the totalSupply is forevermore bounded.
    """
    if running_total != total_supply - MINIMUM_LIQUIDITY:
        print('!!!!!!!!!!!!!!!!!!!!!! {} != {}  !!!!!!!!!!!!!!!!!!!!!!'.format(
            running_total,
            total_supply
        ), file=sys.stderr)
        sys.exit(1)

    if a_supply - running_total_a > MAX_ROUNDING_DRIFT:
        print('!!!!!!!!!!!!!!!!!!!!!! {} != {} (token0 supply) !!!!!!!'.format(
            running_total_a,
            a_supply
        ), file=sys.stderr)
        sys.exit(1)

    if b_supply - running_total_b > MAX_ROUNDING_DRIFT:
        print('!!!!!!!!!!!!!!!!!!!!!! {} != {} (token1 supply) !!!!!!!'.format(
            running_total_b,
            b_supply
        ), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
