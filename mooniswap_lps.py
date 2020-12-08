""" Outputs the Mooniswap liquidity providers LPs for a token pair.

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

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
OUSD_ADDRESS = "0x2A8e1E676Ec238d8A992307B495b45B3fEAa5e86"

ME = Path(__file__).resolve()
OUSD_ABI = json.load(
    ME.parent.joinpath('metadata/OUSD.json').open()
).get('abi')
MOONISWAP_ABI = json.load(
    ME.parent.joinpath('metadata/Mooniswap.json').open()
).get('abi')
IERC20_ABI = json.load(
    ME.parent.joinpath('metadata/IERC20.json').open()
).get('abi')

MINIMUM_LIQUIDITY = 1000
MAX_ROUNDING_DRIFT = 10


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
    parser.add_argument('-a', '--address', dest='address', required=True,
                        help='Mooniswap pair address')
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

    block_number = int(args.block)
    addresses_of_interest = []

    mooniswap = web3.eth.contract(
        address=Web3.toChecksumAddress(args.address),
        abi=MOONISWAP_ABI
    )

    a = mooniswap.functions.tokens(0).call(block_identifier=block_number)
    b = mooniswap.functions.tokens(1).call(block_identifier=block_number)

    token_a = web3.eth.contract(address=a, abi=IERC20_ABI)
    token_b = web3.eth.contract(address=b, abi=IERC20_ABI)

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

    total_supply = mooniswap.functions.totalSupply().call(
        block_identifier=block_number
    )
    a_supply = token_a.functions.balanceOf(mooniswap.address).call(
        block_identifier=block_number
    )
    b_supply = token_b.functions.balanceOf(mooniswap.address).call(
        block_identifier=block_number
    )

    deposits_filter = mooniswap.events.Deposited.createFilter(
        fromBlock=0,
        toBlock=block_number
    )
    deposits = deposits_filter.get_all_entries()

    for deposit in deposits:
        account = dict_get(deposit, 'args.account')

        if account and account not in addresses_of_interest:
            addresses_of_interest.append(account)

    transfers_filter = mooniswap.events.Transfer.createFilter(fromBlock=0, toBlock=block_number)
    transfers = transfers_filter.get_all_entries()

    for transfer in transfers:
        account = dict_get(transfer, 'args.to')

        if account and account not in addresses_of_interest:
            addresses_of_interest.append(account)

    # Now that we have all the theoretical players, get their balance as of the block
    running_total = 0
    running_total_a = 0
    running_total_b = 0
    for addr in addresses_of_interest:

        lp_balance = mooniswap.functions.balanceOf(addr).call(
            block_identifier=block_number
        )

        a_balance = 0
        b_balance = 0
        if lp_balance != 0:
            ratio = Decimal(lp_balance) / Decimal(total_supply)
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
    # This just verifies we know about all funds
    if abs(a_supply - running_total_a) > MAX_ROUNDING_DRIFT:
        print('!!!!!!!!!!!!!!!!!!!!!! {} != {} (token0 supply) !!!!!!!'.format(
            running_total_a,
            a_supply
        ), file=sys.stderr)
        sys.exit(1)

    if abs(b_supply - running_total_b) > MAX_ROUNDING_DRIFT:
        print('!!!!!!!!!!!!!!!!!!!!!! {} != {} (token1 supply) !!!!!!!'.format(
            b_supply,
            running_total_b
        ), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
