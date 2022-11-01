#!/usr/bin/python3

import pickle
import calendar
import codecs
import collections
import datetime
import fcntl
import fnmatch
import logging
import re
import os
import signal
import struct
import sys
import termios
import threading
import time
import tty

__version__ = "0.3.6"


log = logging.getLogger(__name__)


def debug(string, *args):
    log.debug(string, *args)


_debug_time = False


def debug_time(logger):
    def debug_time_inner(kallable):
        def f(*a, **kw):
            global _debug_time
            if not _debug_time:
                return kallable(*a, **kw)
            start = time.time()
            try:
                name = kallable.__name__
            except AttributeError:
                name = str(kallable)
            name = name + "@" + threading.currentThread().getName()
            try:
                logger.debug("* Timing:    %-55s  started", name)
                return kallable(*a, **kw)
            finally:
                end = time.time() - start
                logger.debug("* Timed:     %-55s  %.3f seconds", name, end)
        return f
    return debug_time_inner


def enable_debugging(enable):
    global _debug_time
    if enable:
        _debug_time = True
        fmt = "%(created)f:%(levelname)8s:%(name)20s: %(message)s"
        logging.basicConfig(level=logging.DEBUG, format=fmt)


def matches(string, options):
    """Returns True if the string case-insensitively glob-matches any of the
    globs present in options."""
    for option in options:
        if fnmatch.fnmatch(string, option):
            return True
    return False


class LedgerConfigurationError(Exception):
    pass


class TransactionInputValidationError(ValueError):
    pass


def find_ledger_file(ledger_file=None):
    """Returns main ledger file path or raise exception if it cannot be \
found.  If ledger_file is not None, use that path."""
    if ledger_file is not None:
        return os.path.abspath(ledger_file)
    ledgerrcpath = os.path.abspath(os.path.expanduser("~/.ledgerrc"))
    if "LEDGER_FILE" in os.environ:
        return os.path.abspath(os.path.expanduser(os.environ["LEDGER_FILE"]))
    elif os.path.exists(ledgerrcpath):
        # hacky
        ledgerrc = open(ledgerrcpath).readlines()
        pat = r"^--file\s+(.*?)\s*$"
        matches = [ re.match(pat, m) for m in ledgerrc ]
        matches = [ m.group(1) for m in matches if m ]
        if not matches:
            raise LedgerConfigurationError("LEDGER_FILE environment variable not set, and your .ledgerrc file does not contain a --file parameter.")
        return os.path.abspath(os.path.expanduser(matches[0]))
    else:
        raise LedgerConfigurationError("LEDGER_FILE environment variable not set, and no \
.ledgerrc file found.")


def add_months(sourcedate, months):
    month = sourcedate.month - 1 + months
    year = int(sourcedate.year + month / 12 )
    month = month % 12 + 1
    day = min(sourcedate.day,calendar.monthrange(year,month)[1])
    return datetime.date(year,month,day)


def find_ledger_price_file(price_file=None):
    """Returns main ledger file path or raise exception if it cannot be \
found.  If price_file is not None, use that path."""
    if price_file is not None:
        return os.path.abspath(price_file)
    ledgerrcpath = os.path.abspath(os.path.expanduser("~/.ledgerrc"))
    if "LEDGER_PRICE_DB" in os.environ:
        return os.path.abspath(os.path.expanduser(os.environ["LEDGER_PRICE_DB"]))
    elif os.path.exists(ledgerrcpath):
        # hacky
        ledgerrc = open(ledgerrcpath).readlines()
        pat = r"^--price-db\s+(.+)"
        matches = [ re.match(pat, m) for m in ledgerrc ]
        matches = [ m.group(1) for m in matches if m ]
        if not matches:
            raise LedgerConfigurationError("LEDGER_PRICE_DB environment variable not set, and your .ledgerrc file does not contain a --price-db parameter.")
        return os.path.abspath(os.path.expanduser(matches[0]))
    else:
        raise LedgerConfigurationError("LEDGER_PRICE_DB environment variable not set, and no \
.ledgerrc file found.")


def generate_price_records(records):
    """Generates a set of price records.

    records is a list containing tuples.  each tuple contains:
      commodity is a ledger commodity
      price is the price in ledger.Amount form
      date is a datetime.date
    """
    lines = [""]
    longestcomm = max(list(len(str(a[0])) for a in records))
    longestamount = max(list(len(str(a[1])) for a in records))
    for commodity, price, date in records:
        fmt = "P %s %-" + str(longestcomm) + "s %" + str(longestamount) + "s"
        lines.append(fmt % (
            date.strftime("%Y-%m-%d %H:%M:%S"),
            commodity,
            price,
        ))
    lines.append("")
    return lines


class Settings(dict):

    def __init__(self, filename):
        self.data = dict()
        self.filename = filename

    @classmethod
    def load_or_defaults(cls, filename):
        s = cls(filename)
        if os.path.isfile(s.filename):
            try:
                s.data = pickle.load(open(s.filename, "rb"))
            except Exception as e:
                log.error("Cannot load %s so loading defaults: %s", s.filename, e)
        try:
            unused_suggester = s["suggester"]
        except KeyError:
            s["suggester"] = AccountSuggester()
        return s

    def __setitem__(self, item, value):
        self.data[item] = value
        self.persist()

    def __getitem__(self, item):
        return self.data[item]

    def __delitem__(self, item):
        if item in self.data:
            del self.data[item]
            self.persist()

    def keys(self):
        return list(self.data.keys())

    def get(self, item, default):
        return self.data.get(item, default)

    def persist(self):
        p = open(self.filename, "wb")
        pickle.dump(self.data, p)
        p.flush()
        p.close()


class AccountSuggester(object):

    def __init__(self):
        self.account_to_words = dict()

    def __str__(self):
        dump = str(self.account_to_words)
        return "<AccountSuggester %s>" % dump

    def associate(self, words, account):
        words = [ w.lower() for w in words.split() ]
        account = str(account)
        if account not in self.account_to_words:
            self.account_to_words[account] = dict()
        for w in words:
            if w not in self.account_to_words[account]:
                self.account_to_words[account][w] = 0
            self.account_to_words[account][w] += 1

    def suggest(self, words):
        words = [ w.lower() for w in words.split() ]
        account_counts = dict()
        for account, ws in list(self.account_to_words.items()):
            for w, c in list(ws.items()):
                if w in words:
                    if not account in account_counts:
                        account_counts[account] = 0
                    account_counts[account] += c
        results = list(reversed(sorted(
            list(account_counts.items()), key=lambda x: x[1]
        )))
        if results:
            return results[0][0]
        return None


# ======================  GTK =======================


TransactionPosting = collections.namedtuple(
    'TransactionPosting',
    ['account', 'amount']
)
