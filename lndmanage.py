#!/usr/bin/env python
import argparse
import _settings

from lib.node import LndNode
from lib.node_info import print_node_status, print_unbalanced_channels
from lib.rebalance import Rebalancer
from lib.exceptions import DryRunException, PaymentTimeOut, TooExpensive


def range_limited_float_type(arg):
    """ Type function for argparse - a float within some predefined bounds """
    try:
        f = float(arg)
    except ValueError:
        raise argparse.ArgumentTypeError("Must be a floating point number")
    if f < 1E-6 or f > 1:
        raise argparse.ArgumentTypeError("Argument must be < " + str(1E-6) + " and > " + str(1))
    return f


def parse_arguments():
    # setup the command line parser
    parser = argparse.ArgumentParser(prog='lndmanage.py')
    parser.add_argument('--loglevel', default='INFO', choices=['INFO', 'DEBUG'])
    subparsers = parser.add_subparsers(dest='cmd')

    # getinfo
    parser_status = subparsers.add_parser('status', help='display node status and channel list',
                                          formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_status.add_argument(
        '--unbalancedness', type=float,
        default=0.0,
        help='Unbalancedness is a way to express how balanced a channel is,'
             ' a value between [-1, 1] (a perfectly balanced channel has a value of 0).'
             ' The flag excludes channels with an absolute unbalancedness smaller than UNBALANCEDNESS.')

    # rebalance-channel
    parser_rebalance = subparsers.add_parser(
        'rebalance', help='rebalance a channel', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_rebalance.add_argument('channel', type=int, help='channel_id')
    parser_rebalance.add_argument(
        '--max-fee-sat', type=int, default=20, help='Sets the maximal fees in satoshis to be paid.')
    parser_rebalance.add_argument(
        '--chunksize', type=float, default=1.0, help='Specifies if the individual rebalance attempts should be '
                                                     'split into smaller relative amounts. This increases success'
                                                     ' rates, but also increases costs!')
    parser_rebalance.add_argument(
        '--max-fee-rate', type=range_limited_float_type, default=5E-5,
        help='Sets the maximal effective fee rate to be paid.'
             ' The effective fee rate is defined by (base_fee + amt * fee_rate) / amt.')
    parser_rebalance.add_argument(
        '--dry', help='A dry run is performed.', action='store_true'
    )

    # circular payment
    parser_circle = subparsers.add_parser(
        'circle', help='circular self-payment', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser_circle.add_argument('channel_from', type=int, help='channel_from')
    parser_circle.add_argument('channel_to', type=int, help='channel_from')
    parser_circle.add_argument('amt_sats', type=int, help='amount in satoshis')
    parser_circle.add_argument(
        '--max-fee-sat', type=int, default=20, help='Sets the maximal fees in satoshis to be paid.')
    parser_circle.add_argument(
        '--max-fee-rate', type=range_limited_float_type, default=5E-5,
        help='Sets the maximal effective fee rate to be paid.'
             ' The effective fee rate is defined by (base_fee + amt * fee_rate) / amt.')
    parser_circle.add_argument(
        '--dry', help='A dry run is performed.', action='store_true'
    )

    return parser.parse_args()


def main():
    args = parse_arguments()

    # program execution
    if args.loglevel:
        # update the loglevel of the stdout handler to the user choice
        logger.handlers[0].setLevel(args.loglevel)

    node = LndNode()
    if args.cmd == 'status':
        print_node_status(node)
        print_unbalanced_channels(node, args.unbalancedness)
    elif args.cmd == 'rebalance':
        rebalancer = Rebalancer(node, args.max_fee_rate, args.max_fee_sat)
        rebalancer.rebalance(args.channel, dry=args.dry, chunksize=args.chunksize)
    elif args.cmd == 'circle':
        rebalancer = Rebalancer(node, args.max_fee_rate, args.max_fee_sat)
        invoice_r_hash = node.get_rebalance_invoice(memo='circular payment')
        try:
            rebalancer.rebalance_two_channels(
                args.channel_from, args.channel_to,
                args.amt_sats, invoice_r_hash, args.max_fee_sat, dry=args.dry)
        except DryRunException:
            logger.info("This was just a dry run.")
        except TooExpensive:
            logger.error("Payment failed. This is likely due to a too low default --max-fee-rate.")
        except PaymentTimeOut:
            logger.error("Payment failed because the payment timed out. This is an unresolved issue.")


if __name__ == '__main__':
    import logging.config
    logging.config.dictConfig(_settings.logger_config)
    logger = logging.getLogger()

    main()