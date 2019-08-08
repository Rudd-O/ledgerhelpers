#!/usr/bin/python3

import pickle
import calendar
import codecs
import collections
import datetime
import fcntl
import fnmatch
import ledger
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

__version__ = "0.3.0"


CURSOR_UP = "\033[F"


def debug(string, *args):
    if args:
        string = string % args
    print(string, file=sys.stderr)


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


class LedgerParseError(ValueError):
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


def format_date(date_obj, sample_date):
    _, fmt = parse_date(sample_date, True)
    return date_obj.strftime(fmt)


def generate_record(title, date, auxdate, state, accountamounts,
                    validate=False):
    """Generates a transaction record.

    date is a datetime.date
    title is a string describing the title of the transaction
    auxdate is the date when the transaction cleared, or None
    statechar is a char from parser.CHAR_* or empty string
    accountamounts is a list of:
    (account, amount)
    """
    def stramt(amt):
        assert type(amt) not in (tuple, list), amt
        if not amt:
            return ""
        return str(amt).strip()

    if state:
        state = state + " "
    else:
        state = ""

    lines = [""]
    linesemptyamts = []
    if auxdate:
        if auxdate != date:
            lines.append("%s=%s %s%s" % (date, auxdate, state, title))
        else:
            lines.append("%s %s%s" % (date, state, title))
    else:
        lines.append("%s %s%s" % (date, state, title))

    try:
        longest_acct = max(list(len(a) for a, _ in accountamounts))
        longest_amt = max(list(len(stramt(am)) for _, am in accountamounts))
    except ValueError:
        longest_acct = 30
        longest_amt = 30
    pattern = "    %-" + str(longest_acct) + "s    %" + str(longest_amt) + "s"
    pattern2 = "    %-" + str(longest_acct) + "s"
    for account, amount in accountamounts:
        if stramt(amount):
            lines.append(pattern % (account, stramt(amount)))
        else:
            linesemptyamts.append((pattern2 % (account,)).rstrip())
    lines = lines + linesemptyamts
    lines.append("")

    if validate:
        sess = ledger.Session()
        try:
            sess.read_journal_from_string("\n".join(lines))
        except RuntimeError as e:
            lines = [x.strip() for x in str(e).splitlines() if x.strip()]
            lines = [x for x in lines if not x.startswith("While")]
            lines = [x + ("." if not x.endswith(":") else "") for x in lines]
            lines = " ".join(lines)
            if lines:
                raise LedgerParseError(lines)
            else:
                raise LedgerParseError("Ledger could not validate this transaction")

    return lines


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
            s.data = pickle.load(open(s.filename, "rb"))
        try:
            suggester = s["suggester"]
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


def get_terminal_size(fd):
    def ioctl_GWINSZ(fd):
        return struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    return ioctl_GWINSZ(fd)


def get_terminal_width(fd):
    return get_terminal_size(fd)[1]


class Escaped(KeyboardInterrupt): pass


def read_one_character(from_):        
    old_settings = termios.tcgetattr(from_.fileno())
    try:
        tty.setraw(from_.fileno())
        char = from_.read(1)
        if char == "\x1b":
            raise Escaped()
        if char == "\x03":
            raise KeyboardInterrupt()
    finally:
        termios.tcsetattr(from_.fileno(), termios.TCSADRAIN, old_settings)
    return char


def print_line_ellipsized(fileobj, maxlen, text):
    if len(text) > maxlen:
        text = text[:maxlen]
    fileobj.write(text)
    print()


def prompt_for_expense(prompt):
    return input(prompt + " ").strip()


def go_cursor_up(fd):
    fd.write(CURSOR_UP)


def blank_line(fd, chars):
    fd.write(" " * chars)
    print()


def prompt_for_date_optional(fdin, fdout, prompt, initial):
    return prompt_for_date(fdin, fdout, prompt, initial, True)


def prompt_for_date(fdin, fdout, prompt, initial, optional=False):
    """Return None if bool(optional) evaluates to True."""
    cols = get_terminal_width(fdin)
    if optional:
        opt = "[+/- changes, n skips, ENTER/tab accepts]"
    else:
        opt = "[+/- changes, ENTER/tab accepts]"
    line = prompt + ("" if not initial else " %s" % initial)
    print_line_ellipsized(fdout, cols, line + " " + opt)
    while True:
        char = read_one_character(fdin)
        if char in "\n\r\t":
            break
        elif char == "+":
            initial = initial + datetime.timedelta(1)
        elif char == "-":
            initial = initial + datetime.timedelta(-1)
        elif char in "nN" and optional:
            return None
        cols = get_terminal_width(fdin)
        go_cursor_up(fdout)
        blank_line(fdout, cols)
        go_cursor_up(fdout)
        line = prompt + " " + "%s" % initial
        print_line_ellipsized(fdout, cols, line + " " + opt)
    return initial


def prompt_for_account(fdin, fdout, accounts, prompt, default):
    cols = get_terminal_width(fdin)
    line = prompt + ("" if not default else " '': %s" % default)
    print_line_ellipsized(fdout, cols, line)
    x = []
    match = default
    while True:
        char = read_one_character(fdin)
        if char in "\n\r\t":
            break
        elif char == "\x7f":
            if x: x.pop()
        else:
            x.append(char)
        inp = "".join(x)
        if not inp:
            match = default
        else:
            matches = [ a for a in accounts if inp.lower() in a.lower() ]
            match = matches[0] if matches else inp if inp else default
        cols = get_terminal_width(fdin)
        go_cursor_up(fdout)
        blank_line(fdout, cols)
        go_cursor_up(fdout)
        line = prompt + " " + "'%s': %s" % (inp, match)
        print_line_ellipsized(fdout, cols, line)
    return match


def choose(fdin, fdout, prompt, map_choices):
    """Based on single-char input, return a value from map_choices."""
    cols = get_terminal_width(fdin)
    line = prompt
    print_line_ellipsized(fdout, cols, line)
    while True:
        char = read_one_character(fdin)
        if char in map_choices:
            return map_choices[char]


QUIT = "quit"

yes_chars = "yY\n\r"
no_chars = "nN\x7f"

yesno_choices = dict()
for char in yes_chars:
    yesno_choices[char] = True
for char in no_chars:
    yesno_choices[char] = False
del char


def yesno(fdin, fdout, prompt):
    """Return True upon yY or ENTER, return False upon nN or BACKSPACE."""
    return choose(fdin, fdout, prompt, yesno_choices)


def prompt_for_amount(fdin, fdout, prompt, commodity_example):
    cols = get_terminal_width(fdin)
    line = prompt + ("" if not commodity_example else " '': %s" % commodity_example)
    print_line_ellipsized(fdout, cols, line)
    x = []
    match = commodity_example
    while True:
        char = read_one_character(fdin)
        if char in "\n\r\t":
            break
        elif char == "\x7f":
            if x: x.pop()
        else:
            x.append(char)
        inp = "".join(x)
        try:
            match = ledger.Amount(inp) * commodity_example
        except ArithmeticError:
            try:
                match = ledger.Amount(inp)
            except ArithmeticError:
                match = ""
        cols = get_terminal_width(fdin)
        go_cursor_up(fdout)
        blank_line(fdout, cols)
        go_cursor_up(fdout)
        line = prompt + " " + "'%s': %s" % (inp, match)
        print_line_ellipsized(fdout, cols, line)
    assert match is not None
    return match


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


def parse_date(putative_date, return_format=False):
    """Returns a date substring in a ledger entry, parsed as datetime.date."""
    # FIXME: use Ledger functions to parse dates, not mine.
    formats = ["%Y-%m-%d", "%Y/%m/%d"]
    for f in formats:
        try:
            d = datetime.datetime.strptime(putative_date, f).date()
            break
        except ValueError as e:
            continue
    try:
        if return_format:
            return d, f
        else:
            return d
    except UnboundLocalError:
        raise ValueError("cannot parse date from format %s: %s" % (f, e))


TransactionPosting = collections.namedtuple(
    'TransactionPosting',
    ['account', 'amount']
)
