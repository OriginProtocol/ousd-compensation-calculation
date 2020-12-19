"""
Script to calculate OUSD hack compensation values.
"""
import sys
import csv
import locale
from math import floor
from enum import Enum
from pathlib import Path
from decimal import Decimal
from argparse import ArgumentParser
from web3 import Web3

locale.setlocale(locale.LC_ALL, '')
ME = Path(__file__).resolve()
VIRGOX_PROCEEDS = ME.parent.joinpath('metadata', 'virgox_proceeds.csv')

OUSD_ADDRESS = "0x2A8e1E676Ec238d8A992307B495b45B3fEAa5e86"
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
USDT_ADDRESS = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


class Direction(Enum):
    """ Direction of the trade.  OUSD is always on the left, so
    LEFT means "buy OUSD" and RIGHT means "sell OUSD"
    """
    LEFT = 0
    RIGHT = 1


class CalcParameters:
    def __init__(
        self,
        ousd_ogn_split=Decimal(0.5),
        ogn_price_usd=Decimal(15e16),  # $0.15
        eth_value_usd=int(600),  # 600 USD
        minimum_threshold=Decimal(0),
        split_threshold=Decimal(1000e18)  # 1000 USD
    ):
        self.split_threshold = split_threshold
        self.ousd_ogn_split = ousd_ogn_split
        self.ogn_price_usd = ogn_price_usd
        self.eth_value_usd = eth_value_usd
        self.minimum_threshold = minimum_threshold


class Account:
    def __init__(self, address, params):
        self.address = address
        self.params = params

        self._ousd_balance_start = 0
        self._ousd_balance_end = 0

        # LP balances, USDC and USDT have only 6 decimals!
        self._usdt_balance_start = 0
        self._usdt_balance_end = 0
        self._usdc_balance_start = 0
        self._usdc_balance_end = 0
        self._weth_balance_start = 0
        self._weth_balance_end = 0
        self._ousd_lp_start = 0
        self._ousd_lp_end = 0
        self._usdt_lp_start = 0
        self._usdt_lp_end = 0
        self._usdc_lp_start = 0
        self._usdc_lp_end = 0
        self._weth_lp_start = 0
        self._weth_lp_end = 0

        self._usdt_swaps = []
        self._usdc_swaps = []
        self._weth_swaps = []

        self._virgox_proceeds = []

    def _eth_to_usd(self, eth_value):
        """ Convert to USD value (18 decimals) """
        return eth_value * self.params.eth_value_usd

    def add_ousd_balance_start(self, bal):
        self._ousd_balance_start += int(bal)

    def add_ousd_balance_end(self, bal):
        self._ousd_balance_end += int(bal)

    def add_usdt_balance_start(self, val):
        self._usdt_balance_start += int(val)

    def add_usdt_balance_end(self, val):
        self._usdt_balance_end += int(val)

    def add_usdc_balance_start(self, val):
        self._usdc_balance_start += int(val)

    def add_usdc_balance_end(self, val):
        self._usdc_balance_end += int(val)

    def add_weth_balance_start(self, val):
        self._weth_balance_start += int(val)

    def add_weth_balance_end(self, val):
        self._weth_balance_end += int(val)

    def add_ousd_lp_start(self, bal):
        self._ousd_lp_start += int(bal)

    def add_ousd_lp_end(self, bal):
        self._ousd_lp_end += int(bal)

    def add_usdt_lp_start(self, val):
        self._usdt_lp_start += int(val)

    def add_usdt_lp_end(self, val):
        self._usdt_lp_end += int(val)

    def add_usdc_lp_start(self, val):
        self._usdc_lp_start += int(val)

    def add_usdc_lp_end(self, val):
        self._usdc_lp_end += int(val)

    def add_weth_lp_start(self, val):
        self._weth_lp_start += int(val)

    def add_weth_lp_end(self, val):
        self._weth_lp_end += int(val)

    def add_usdt_swap(self, swap):
        """ Swaps are tuple (ousd_value, usdt_value, direction) """
        self._usdt_swaps.append(swap)

    def add_usdc_swap(self, swap):
        """ Swaps are tuple (ousd_value, usdc_value, direction) """
        self._usdc_swaps.append(swap)

    def add_weth_swap(self, swap):
        """ Swaps are tuple (ousd_value, weth_value, direction) """
        self._weth_swaps.append(swap)

    def add_virgox_proceed(self, usd_proceeds):
        """ Each "proceed" is a sale of OUSD for an unknown asset """
        self._virgox_proceeds.append(usd_proceeds)

    def to_list(self):
        """ Display this account in a list with these values:

        address, eligible_ousd_value_human, ousd_compensation_human,
        ogn_compensation_w_interest_human, ogn_compensation_human,
        eligible_ousd_value, ousd_compensation, ogn_compensation
        """
        return [
            self.address,
            locale.currency(
                Decimal(self.eligible_balance_usd) / Decimal(1e18),
                symbol=False,
                grouping=True
            ),
            locale.currency(
                Decimal(self.adjusted_ousd_compensation) / Decimal(1e18),
                symbol=False,
                grouping=True
            ),
            locale.currency(
                Decimal(self.adjusted_ogn_compensation) * Decimal(1.25) / Decimal(1e18),
                symbol=False,
                grouping=True
            ),
            locale.currency(
                Decimal(self.adjusted_ogn_compensation) / Decimal(1e18),
                symbol=False,
                grouping=True
            ),
            Decimal(self.eligible_balance_usd),
            Decimal(self.adjusted_ousd_compensation),
            Decimal(self.adjusted_ogn_compensation)
        ]

    def to_csv_row(self):
        """ Print a CSV row

        address, eligible_ousd_value_human, ousd_compensation_human,
        ogn_compensation_w_interest_human, ogn_compensation_human,
        eligible_ousd_value, ousd_compensation, ogn_compensation
        """
        return ','.join(['"{}"'.format(x) if ',' in str(x) else str(x) for x in self.to_list()])

    @property
    def usdt_swap_in(self):
        """ Incoming USDT from OUSD swaps """
        return sum(
            [int(x[1]) if x[2] == Direction.RIGHT else 0 for x in self._usdt_swaps]
        )

    @property
    def usdt_swap_out(self):
        """ Outgoing USDT from OUSD swaps """
        return sum(
            [int(x[1]) if x[2] == Direction.LEFT else 0 for x in self._usdt_swaps]
        )

    @property
    def usdc_swap_in(self):
        """ Incoming USDC from OUSD swaps """
        return sum(
            [int(x[1]) if x[2] == Direction.RIGHT else 0 for x in self._usdc_swaps]
        )

    @property
    def usdc_swap_out(self):
        """ Outgoing USDC from OUSD swaps """
        return sum(
            [int(x[1]) if x[2] == Direction.LEFT else 0 for x in self._usdc_swaps]
        )

    @property
    def weth_swap_in(self):
        """ Incoming WETH from OUSD swaps """
        return sum(
            [int(x[1]) if x[2] == Direction.RIGHT else 0 for x in self._weth_swaps]
        )

    @property
    def weth_swap_out(self):
        """ Outgoing WETH from OUSD swaps """
        return sum(
            [int(x[1]) if x[2] == Direction.LEFT else 0 for x in self._weth_swaps]
        )

    @property
    def trading_gain_usdt(self):
        """ Net USDT gains from trading OUSD after the hack """
        if (self._ousd_balance_start + self._ousd_lp_start) <= 0:
            return 0

        return self.usdt_swap_in - self.usdt_swap_out

    @property
    def trading_gain_usdc(self):
        """ Net USDC gains from trading OUSD after the hack """
        if (self._ousd_balance_start + self._ousd_lp_start) <= 0:
            return 0

        return self.usdc_swap_in - self.usdc_swap_out

    @property
    def trading_gain_weth(self):
        """ Net WETH gains from trading OUSD after the hack """
        if (self._ousd_balance_start + self._ousd_lp_start) <= 0:
            return 0

        return self.weth_swap_in - self.weth_swap_out

    @property
    def trading_gain_virgox(self):
        """ Gains trading OUSD after the hack """
        if not self._virgox_proceeds:
            return 0

        return sum([x for x in self._virgox_proceeds])

    @property
    def trading_gain_total_usd(self):
        """ Total gain in USD

        NOTE: We're just using $1 value for USDT and USDC
        """
        return (
            convert_decimals(self.trading_gain_usdt, 6, 18)
            + convert_decimals(self.trading_gain_usdc, 6, 18)
            + self._eth_to_usd(self.trading_gain_weth)
            + self.trading_gain_virgox
        )

    @property
    def eligible_balance_usd(self):
        """ Return the reimbursable balance """
        diff = (
            self._ousd_balance_start
            + self._ousd_lp_start
            - max(self.trading_gain_total_usd, 0)
        )

        if diff < self.params.minimum_threshold:
            return 0

        return diff

    @property
    def adjusted_ousd_compensation(self):
        """ Amount of OUSD this account can be compensated for """

        eligible = self.eligible_balance_usd

        # If their eligible compensation is less than the threshold,
        # compensation is 100% OUSD
        if eligible <= self.params.split_threshold:
            return eligible

        # The amount above the given threshold
        above_split = Decimal(eligible) - self.params.split_threshold

        return floor(
            self.params.split_threshold + (
                above_split * self.params.ousd_ogn_split
            )
        )

    @property
    def adjusted_ogn_compensation(self):
        """ Amount of OGN this account can be compensated for """

        eligible = self.eligible_balance_usd

        # If their eligible compensation is less than the threshold,
        # compensation is 100% OUSD
        if eligible <= self.params.split_threshold:
            return 0

        above_split = Decimal(eligible) - self.params.split_threshold

        # The OGN side of the original OUSD value split
        ogn_usd_value = above_split - floor(
            above_split * self.params.ousd_ogn_split
        )

        # Sanity check
        assert ogn_usd_value + self.adjusted_ousd_compensation == self.eligible_balance_usd

        # Actual OGN according to given price
        return floor(ogn_usd_value / self.params.ogn_price_usd * Decimal(1e18))


def convert_decimals(val, decin, decout):
    return int(val * pow(10, decout - decin))


def parse_args(argv):
    parser = ArgumentParser()
    parser.add_argument('-o', '--outdir', dest='outdir',
                        help='Directory with the output files to read from')
    parser.add_argument('-s', '--start', dest='start',
                        help='Start block')
    parser.add_argument('-e', '--end', dest='end',
                        help='End block')
    parser.add_argument('-b', '--blacklist', dest='blacklist',
                        help='File with blacklisted addresses')
    parser.add_argument('-a', '--account', dest='account',
                        help='Output data for a specific account only')
    return parser.parse_args(argv)


def csv_to_list(fname, discard_first_row=False):
    csvdata = list(csv.reader(Path(fname).resolve().open()))

    if discard_first_row:
        return csvdata[1:]

    return csvdata


def create_account_if_not_exists(accounts_dict, address, params):
    address = Web3.toChecksumAddress(address)
    if accounts_dict.get(address) is None:
        accounts_dict[address] = Account(address, params)


def process_uniswap_lp_data(csvdata, accounts, params, is_start=True):
    """  These should all be in the format of the following with token0 always
    being OUSD:

    token0,token1,lp_address,lp_balance,approx_token0,approx_token1
    """

    for lp in csvdata:
        [
            token0,
            token1,
            lp_address,
            lp_balance,
            token0_value,
            token1_value
        ] = lp

        create_account_if_not_exists(accounts, lp_address, params)

        if is_start:
            accounts[lp_address].add_ousd_lp_start(token0_value)

            if token1 == USDT_ADDRESS:
                accounts[lp_address].add_usdt_lp_start(token1_value)
            elif token1 == USDC_ADDRESS:
                accounts[lp_address].add_usdc_lp_start(token1_value)
            elif token1 == WETH_ADDRESS:
                accounts[lp_address].add_weth_lp_start(token1_value)
            else:
                print(
                    '{} is part of an unknown token pair!'.format(token1),
                    file=sys.stderr
                )
                # Something's fucky, bail
                sys.exit(1)

        else:
            accounts[lp_address].add_ousd_lp_end(token0_value)

            if token1 == USDT_ADDRESS:
                accounts[lp_address].add_usdt_lp_end(token1_value)
            elif token1 == USDC_ADDRESS:
                accounts[lp_address].add_usdc_lp_end(token1_value)
            elif token1 == WETH_ADDRESS:
                accounts[lp_address].add_weth_lp_end(token1_value)
            else:
                print(
                    '{} is part of an unknown token pair!'.format(token1),
                    file=sys.stderr
                )
                # Something's fucky, bail
                sys.exit(1)


def process_uniswap_swap_data(csvdata, accounts, params):
    """ Process uniswap-type swap data

    Expected CSV format: token0,token1,block_number,in_address,out_address,
    swap_direction,token0_amount,token1_amount,token_in,token_out,
    token0_relevance,tx_hash
    """
    for swap in csvdata:
        [
            token0,
            token1,
            block_number,
            in_address,
            out_address,
            swap_direction,
            token0_amount,
            token1_amount,
            token_in,
            token_out,
            token0_relevance,
            tx_hash
        ] = swap

        create_account_if_not_exists(accounts, in_address, params)
        create_account_if_not_exists(accounts, out_address, params)

        direction = Direction.RIGHT

        if swap_direction == 'buy':
            direction = Direction.LEFT

        # Swap tuple format: (ousd_value, usdt_value, direction)
        if token1 == USDT_ADDRESS:
            accounts[in_address].add_usdt_swap(
                (token0_amount, token1_amount, direction)
            )
        elif token1 == USDC_ADDRESS:
            accounts[in_address].add_usdc_swap(
                (token0_amount, token1_amount, direction)
            )
        elif token1 == WETH_ADDRESS:
            accounts[in_address].add_weth_swap(
                (token0_amount, token1_amount, direction)
            )
        else:
            print(
                '{} is part of an unknown token pair!'.format(token1),
                file=sys.stderr
            )
            # Something's fucky, bail
            sys.exit(1)


def load_address_list(fname):
    addresslist_file = Path(fname).resolve()
    addresses = []

    if not addresslist_file.is_file():
        return addresses

    for x in addresslist_file.read_text().split('\n'):
        if x and not x.startswith('#'):
            addresses.append(Web3.toChecksumAddress(x))

    return addresses


def main():
    args = parse_args(sys.argv[1:])
    outdir = Path(args.outdir).resolve()

    params = CalcParameters(
        split_threshold=Decimal(1000e18),
        ousd_ogn_split=Decimal(0.25),  # 25% OUSD / 75% OGN
        ogn_price_usd=Decimal(1492e14),  # $0.1492
        eth_value_usd=578.24,  # USD
        minimum_threshold=1e16  # $0.01
    )

    blacklist = []
    if args.blacklist:
        blacklist = load_address_list(args.blacklist)

    # address => Account
    accounts = {}

    """
    LOAD ACCOUNT OUSD BALANCES
    """

    # CSV format: address,ousd_balance,is_contract
    account_balances_before = csv_to_list(
        outdir.joinpath('ousd_balances_{}.csv'.format(args.start))
    )

    for account in account_balances_before:
        [address, ousd_balance, is_contract] = account
        create_account_if_not_exists(accounts, address, params)
        accounts[address].add_ousd_balance_start(ousd_balance)

    # CSV format: address,ousd_balance,is_contract
    account_balances_after = csv_to_list(
        outdir.joinpath('ousd_balances_{}.csv'.format(args.end))
    )

    for account in account_balances_after:
        [address, ousd_balance, is_contract] = account
        create_account_if_not_exists(accounts, address, params)
        accounts[address].add_ousd_balance_end(ousd_balance)

    """
    LOAD LIQUIDITY PROVIDER BALANCES
    """

    # CSV format: token0,token1,lp_address,lp_balance,token0_value,token1_value
    uniswap_lp_balances_before = csv_to_list(
        outdir.joinpath('uniswap_lp_{}.csv'.format(args.start))
    )

    process_uniswap_lp_data(uniswap_lp_balances_before, accounts, params)

    uniswap_lp_balances_after = csv_to_list(
        outdir.joinpath('uniswap_lp_{}.csv'.format(args.end))
    )

    process_uniswap_lp_data(
        uniswap_lp_balances_after,
        accounts,
        params,
        is_start=False
    )

    sushiswap_lp_balances_before = csv_to_list(
        outdir.joinpath('sushiswap_lp_{}.csv'.format(args.start))
    )

    process_uniswap_lp_data(sushiswap_lp_balances_before, accounts, params)

    sushiswap_lp_balances_after = csv_to_list(
        outdir.joinpath('sushiswap_lp_{}.csv'.format(args.end))
    )

    process_uniswap_lp_data(
        sushiswap_lp_balances_after,
        accounts,
        params,
        is_start=False
    )

    mooniswap_lp_balances_before = csv_to_list(
        outdir.joinpath('mooniswap_lp_{}.csv'.format(args.start))
    )

    process_uniswap_lp_data(mooniswap_lp_balances_before, accounts, params)

    mooniswap_lp_balances_after = csv_to_list(
        outdir.joinpath('mooniswap_lp_{}.csv'.format(args.end))
    )

    process_uniswap_lp_data(
        mooniswap_lp_balances_after,
        accounts,
        params,
        is_start=False
    )

    """
    LOAD SNOWSWAP STAKER BALANCES
    """

    snowswap_staker_balances_before = csv_to_list(
        outdir.joinpath('snowswap_stakers_{}.csv'.format(args.start))
    )

    for stake in snowswap_staker_balances_before:
        [
            staker_address,
            credit_balance,
            ousd_balance,
            ratioed_ousd_balance
        ] = stake

        create_account_if_not_exists(accounts, staker_address, params)

        accounts[staker_address].add_ousd_balance_start(ratioed_ousd_balance)

    snowswap_staker_balances_after = csv_to_list(
        outdir.joinpath('snowswap_stakers_{}.csv'.format(args.end))
    )

    for stake in snowswap_staker_balances_after:
        [
            staker_address,
            credit_balance,
            ousd_balance,
            ratioed_ousd_balance
        ] = stake

        create_account_if_not_exists(accounts, staker_address, params)

        accounts[staker_address].add_ousd_balance_end(ratioed_ousd_balance)

    """
    LOAD VIRGOX TRADING GAINS (POST-HACK)
    """

    # Address,Amount,Price,Proceeds
    virgox_proceeds = csv_to_list(VIRGOX_PROCEEDS, discard_first_row=True)

    for vp in virgox_proceeds:
        [address, amount, price, usd_proceeds] = vp

        address = Web3.toChecksumAddress(address)

        create_account_if_not_exists(accounts, address, params)

        accounts[address].add_virgox_proceed(
            # Since we're working with integers
            int(Decimal(usd_proceeds) * Decimal(1e18))
        )

    """
    LOAD SWAPS (POST-HACK)
    """

    uniswap_swaps = csv_to_list(
        outdir.joinpath('uniswap_swaps_{}-{}.csv'.format(args.start, args.end))
    )

    process_uniswap_swap_data(uniswap_swaps, accounts, params)

    sushiswap_swaps = csv_to_list(
        outdir.joinpath('sushiswap_swaps_{}-{}.csv'.format(
            args.start,
            args.end
        ))
    )

    process_uniswap_swap_data(sushiswap_swaps, accounts, params)

    mooniswap_swaps = csv_to_list(
        outdir.joinpath('mooniswap_swaps_{}-{}.csv'.format(
            args.start,
            args.end
        ))
    )

    process_uniswap_swap_data(mooniswap_swaps, accounts, params)

    if args.account:
        account = Web3.toChecksumAddress(args.account)
        print('ousd_balance_start: {} ({})'.format(
            accounts[account]._ousd_balance_start,
            accounts[account]._ousd_balance_start / 1e18
        ))
        print('ousd_lp_start: {} ({})'.format(
            accounts[account]._ousd_lp_start,
            accounts[account]._ousd_lp_start / 1e18
        ))
        print('eligible balance: {} (${})'.format(
            accounts[account].eligible_balance_usd,
            accounts[account].eligible_balance_usd / 1e18
        ))
        print(
            'adjusted_ousd_compensation: {} ({})'.format(
                accounts[account].adjusted_ousd_compensation,
                accounts[account].adjusted_ousd_compensation / 1e18
            )
        )
        print(
            'adjusted_ogn_compensation: {} ({})'.format(
                accounts[account].adjusted_ogn_compensation,
                accounts[account].adjusted_ogn_compensation / 1e18
            )
        )
        print('USDT swaps:', accounts[account]._usdt_swaps)
        print('USDC swaps:', accounts[account]._usdc_swaps)
        print('WETH swaps:', accounts[account]._weth_swaps)

    else:
        # CSV out compensation numbers
        # address, eligible_ousd_value_human, ousd_compensation_human,
        # ogn_compensation_w_interest_human, ogn_compensation_human, eligible_ousd_value,
        # ousd_compensation, ogn_compensation
        print('address,eligible_ousd_value_human,ousd_compensation_human,ogn_compensation_w_interest_human,ogn_compensation_human,eligible_ousd_value,ousd_compensation,ogn_compensation')
        for addr in accounts.keys():
            if addr in blacklist or accounts[addr].eligible_balance_usd == 0:
                continue

            print(accounts[addr].to_csv_row())


if __name__ == "__main__":
    main()
