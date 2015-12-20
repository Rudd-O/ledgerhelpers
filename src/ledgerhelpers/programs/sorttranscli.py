#!/usr/bin/env python

import argparse
import collections
import datetime
import itertools
import subprocess
import tempfile

import ledgerhelpers
from ledgerhelpers import diffing
from ledgerhelpers import parser


def get_argparser():
    parser = argparse.ArgumentParser(
        'Sort transactions in a ledger file chronologically'
    )
    parser.add_argument('-y', dest='assume_yes', action='store_true',
                        help='record changes immediately, instead of '
                        'showing a three-way diff for you to resolve')
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help='do not capture exceptions into a dialog box')
    return parser


def sort_transactions(items):
    smallest_date = datetime.date(1000, 1, 1)
    largest_date = datetime.date(3000, 1, 1)
    bydates = collections.OrderedDict()
    first_transaction_seen = False
    for n, item in enumerate(items):
        if hasattr(item, "date"):
            first_transaction_seen = True
        if first_transaction_seen:
            later_dates = itertools.chain(
                (getattr(items[i], "date", None) for i in xrange(n, len(items))),
                [largest_date]
            )
            for date in later_dates:
                if date is not None:
                    break
        else:
            date = smallest_date
        if date not in bydates:
            bydates[date] = []
        bydates[date] += [item]
    for date in sorted(bydates):
        for item in bydates[date]:
            yield item


def main(argv):
    p = get_argparser()
    args = p.parse_args(argv[1:])
    assert not args.assume_yes
    ledgerfile = ledgerhelpers.find_ledger_file_for_gui()
    try:
        leftcontents = open(ledgerfile, "rb").read()
        items = parser.lex_ledger_file_contents(leftcontents, debug=args.debug)
        rightcontents = u"".join(i.contents for i in sort_transactions(items))
        try:
            diffing.three_way_diff(ledgerfile, leftcontents, rightcontents)
        except subprocess.CalledProcessError, e:
            if args.debug:
                raise
            ledgerhelpers.FatalError("Meld failed",
                       "Meld process failed with return code %s" % e.returncode,
                       outside_mainloop=True)
            return e.returncode
    except Exception, e:
        if args.debug:
            raise
        ledgerhelpers.FatalError("Transaction sort failed",
                   "An unexpected error took place:\n%s" % e,
                   outside_mainloop=True)
        return 9
