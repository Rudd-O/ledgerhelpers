#!/usr/bin/env python

import argparse
import datetime
import collections
import subprocess
import tempfile

import ledgerhelpers
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
    bydates = collections.OrderedDict()
    for n, item in enumerate(items):
        try:
            later_item = item
            while not hasattr(later_item, "date"):
                n += 1
                later_item = items[n]
            date = later_item.date
        except (IndexError, AttributeError):
            date = datetime.date(3000, 1, 1)
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
        text = file(ledgerfile, 'rb').read()
        items = parser.lex_ledger_file_contents(text)
        sorted_items = sort_transactions(items)
        prevfile = tempfile.NamedTemporaryFile(prefix=ledgerfile + ".previous.")
        prevfile.write(text)
        prevfile.flush()
        newfile = tempfile.NamedTemporaryFile(prefix=ledgerfile + ".new.")
        for item in sorted_items:
            newfile.write(item.contents)
        newfile.flush()
        try:
            subprocess.check_call(
                ('meld', prevfile.name, ledgerfile, newfile.name)
            )
        except subprocess.CalledProcessError, e:
            if args.debug:
                raise
            ledgerhelpers.FatalError("Meld failed",
                       "Meld process failed with return code %s" % e.returncode,
                       outside_mainloop=True)
            return e.returncode
        finally:
            prevfile.close()
            newfile.close()
    except Exception, e:
        if args.debug:
            raise
        ledgerhelpers.FatalError("Transaction sort failed",
                   "An unexpected error took place:\n%s" % e,
                   outside_mainloop=True)
        return 9
