""" Outputs the SnowSwap stakers for a "geyser".

CSV format out:

staker_address, credit_balance, ousd_balance, ratioed_ousd_balance
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
SNOWSWAP_GEYSER_ADDRESS = "0x7c2Fa8c30DB09e8B3c147Ac67947829447BF07bD"

ME = Path(__file__).resolve()
SNOWSWAP_STAKING_ABI = json.load(
    ME.parent.joinpath('metadata/SnowswapStakingRewards.json').open()
).get('abi')
OUSD_ABI = json.load(
    ME.parent.joinpath('metadata/OUSD.json').open()
).get('abi')
IERC20_ABI = json.load(
    ME.parent.joinpath('metadata/IERC20.json').open()
).get('abi')

MAX_ROUNDING_DRIFT = 1e8
MAX_CREDIT_DRIFT = 50


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
    parser.add_argument('-t', '--token', dest='address', required=True,
                        default=OUSD_ADDRESS, help='Token address')
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

    token_address = Web3.toChecksumAddress(args.address)
    block_number = int(args.block)
    addresses_of_interest = []

    ousd = web3.eth.contract(address=token_address, abi=OUSD_ABI)
    snowswap_geyser = web3.eth.contract(
        address=SNOWSWAP_GEYSER_ADDRESS,
        abi=SNOWSWAP_STAKING_ABI
    )

    # Snowswap does internal accounting on credits for whatever reason
    current_cpt = int(ousd.functions.rebasingCreditsPerToken().call(
        block_identifier=block_number
    ), 16)
    credits_per_token = current_cpt
    if args.credits_per_token:
        credits_per_token = int(args.credits_per_token)

    total_supply = snowswap_geyser.functions.totalSupply().call(
        block_identifier=block_number
    )
    known_balance = ousd.functions.balanceOf(snowswap_geyser.address).call(
        block_identifier=block_number
    )
    if args.credits_per_token:
        known_balance = ousd_value_adjustment(
            known_balance,
            current_cpt,
            credits_per_token
        )
    known_credit_balance = ousd.functions.creditsBalanceOf(
        snowswap_geyser.address
    ).call(block_identifier=block_number)

    # The tiny drift here is from internal contract math leaving behind tiny
    # fractions of an indivisible unit
    #
    # amount.mul(ousd.rebasingCreditsPerToken()).div(1e18)
    assert abs(total_supply - known_credit_balance) < MAX_CREDIT_DRIFT, \
        "total_supply != known_credit_balance ({} != {})".format(
            total_supply,
            known_credit_balance
        )

    stakes_filter = snowswap_geyser.events.Staked.createFilter(
        fromBlock=0,
        toBlock=block_number
    )
    stakes = stakes_filter.get_all_entries()

    for stake in stakes:
        account = dict_get(stake, 'args.user')
        if account and account not in addresses_of_interest:
            addresses_of_interest.append(account)

    # Now that we have all the theoretical players, get their balance as of the block
    running_total = 0
    usd_running_total = 0
    ousd_running_total = 0
    ratioed_ousd_running_total = 0

    for addr in addresses_of_interest:
        usd_balance = 0
        ousd_balance = 0
        ratioed_ousd_balance = 0
        credit_balance = snowswap_geyser.functions.balanceOf(addr).call(
            block_identifier=block_number
        )

        if credit_balance != 0:
            ousd_balance = floor(credit_balance  * 1e18 / credits_per_token)
            usd_balance = Decimal(ousd_balance) / Decimal(1e18)
            ratio = Decimal(credit_balance / total_supply)
            ratioed_ousd_balance = floor(known_balance * ratio)

        running_total += credit_balance
        ousd_running_total += ousd_balance
        usd_running_total += usd_balance
        ratioed_ousd_running_total += ratioed_ousd_balance

        print('{},{},{},{}'.format(
            addr,
            credit_balance,
            ousd_balance,
            ratioed_ousd_balance
        ))

    # General verification of maths
    if total_supply != running_total:
        print('total_supply !!!!!!!!!!!!!!!!!!!!!! {} != {} !!!!!!!!!!'.format(
            total_supply,
            running_total
        ), file=sys.stderr)
        sys.exit(1)

    bal_dust = known_balance - ousd_running_total
    if bal_dust < 0 or bal_dust > MAX_ROUNDING_DRIFT:
        print('ousd balance !!!!!!!!!!!!!!!!!!!!!! {} != {} !!!!!!!!!!'.format(
            known_balance,
            ousd_running_total
        ), file=sys.stderr)
        sys.exit(1)

    ousd_dust = known_balance - ratioed_ousd_running_total
    if ousd_dust > MAX_ROUNDING_DRIFT:
        print('known_balance !!!!!!!!!!!!!!!!!!!!!! {} != {} !!!!!!!!!'.format(
            ratioed_ousd_running_total,
            known_balance
        ), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
