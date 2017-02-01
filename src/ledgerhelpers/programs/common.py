#!/usr/bin/env python

import argparse


def get_common_argparser():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--file', dest='file', action='store',
                        help='specify path to ledger file to work with')
    parser.add_argument('--price-db', dest='pricedb', action='store',
                        help='specify path to ledger price database to work with')
    return parser
