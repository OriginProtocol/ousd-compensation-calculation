import sys
import json
from pathlib import Path
from argparse import ArgumentParser
from web3 import Web3

ME = Path(__file__).resolve()
OUSD_ABI = json.load(
    ME.parent.joinpath('metadata/OUSD.json').open()
).get('abi')


def parse_args(argv):
    parser = ArgumentParser()
    parser.add_argument('-b', '--block', dest='block', default="latest",
                        help='Block number to query at (default: latest)')
    parser.add_argument('-a', '--address', dest='address',
                        help='OUSD contract address')
    parser.add_argument('-u', '--url', dest='endpoint', type=str,
                        default="http://localhost:8545",
                        help='JSON-RPC endpoint to query')
    return parser.parse_args(argv)


def normalize_block(bn):
    if bn in ['latest', 'pending', 'earliest']:
        return bn
    elif bn.startswith('0x'):
        return int(bn, 16)
    return int(bn)


def main():
    args = parse_args(sys.argv[1:])
    web3 = Web3(Web3.HTTPProvider(args.endpoint))
    token = web3.eth.contract(address=args.address, abi=OUSD_ABI)
    print(
        int(token.functions.rebasingCreditsPerToken().call(
            block_identifier=normalize_block(args.block)
        ), 16)
    )


if __name__ == "__main__":
    main()
