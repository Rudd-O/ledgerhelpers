#!/usr/bin/env python

import cPickle
import calendar
import codecs
import collections
import datetime
import fcntl
import ledger
import re
import os
import struct
import sys
import termios
import threading
import time
import tty

from gi.repository import GObject
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Pango

__version__ = "0.0.16"


CURSOR_UP = "\033[F"


def debug(string, *args):
    if args:
        string = string % args
    print >> sys.stderr, string


def debug_time(kallable):
    def f(*a, **kw):
        start = time.time()
        try:
            return kallable(*a, **kw)
        finally:
            end = time.time() - start
            print "Ran %s in %.3f seconds" % (kallable, end)
    return f


class LedgerConfigurationError(Exception):
    pass


class TransactionInputValidationError(ValueError):
    pass


class LedgerParseError(ValueError):
    pass


def find_ledger_file():
    """Returns main ledger file path or raise exception if it cannot be \
found."""
    ledgerrcpath = os.path.abspath(os.path.expanduser("~/.ledgerrc"))
    if "LEDGER_FILE" in os.environ:
        return os.path.abspath(os.path.expanduser(os.environ["LEDGER_FILE"]))
    elif os.path.exists(ledgerrcpath):
        # hacky
        ledgerrc = open(ledgerrcpath).readlines()
        pat = r"^--file\s+(.*)"
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


def find_ledger_price_file():
    """Returns main ledger file path or raise exception if it cannot be \
found."""
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


def generate_record(title, date, cleared_date, accountamounts, validate=False):
    """Generates a transaction record.

    date is a datetime.date
    title is a string describing the title of the transaction
    cleared_date is the date when the transaction cleared, or None
    accountamounts is a list of:
    (account, [amounts])
    """
    def resolve_amounts(amts):
        if len(amts) == 0:
            return ""
        if len(amts) == 1:
            return str(amts[0])
        return "( " + " + ".join(str(amt) for amt in amts) + " )"

    lines = [""]
    lines.append("%s%s %s" % (date,
                                ("=%s *" % cleared_date if cleared_date else ""),
                                title))

    try:
        longestaccount = max(list(len(a[0]) for a in accountamounts))
        longestamount = max(list(len(resolve_amounts(a[1])) for a in accountamounts))
    except ValueError:
        longestaccount = 30
        longestamount = 30
    pattern = "    %-" + str(longestaccount) + "s    %" + str(longestamount) + "s"
    for account, amounts in accountamounts:
        lines.append(pattern % (account, resolve_amounts(amounts)))
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


class Journal(GObject.GObject):

    __gsignals__ = {
        'loaded': (GObject.SIGNAL_RUN_LAST, None, ()),
        'load-failed': (GObject.SIGNAL_RUN_LAST, None, (object,)),
    }

    __name__ = "Journal"

    def __init__(self):
        GObject.GObject.__init__(self)
        """Do not instantiate directly.  Use class methods."""
        self.path = None
        self.price_path = None
        self.session = None
        self.journal = None
        self.internal_parsing = []

    @classmethod
    @debug_time
    def from_file(klass, journal_file, price_file):
        j = klass()
        j.path = journal_file
        j.price_path = price_file
        j.reread_files()
        return j

    @classmethod
    @debug_time
    def from_file_unloaded(klass, journal_file, price_file):
        j = klass()
        j.path = journal_file
        j.price_path = price_file
        return j

    @debug_time
    def reread_files(self):
        try:
            files = []
            if self.price_path:
                files.append(self.price_path)
            if self.path:
                files.append(self.path)
            text = "\n".join(file(x).read() for x in files)

            if self.path:
                unitext = "\n".join(
                    codecs.open(x, "rb", "utf-8").read()
                    for x in [self.path]
                )
            else:
                unitext = u""

            session = ledger.Session()
            journal = session.read_journal_from_string(text)
            from ledgerhelpers import parser
            internal_parsing = parser.lex_ledger_file_contents(unitext)

            self.session = session
            self.journal = journal
            self.internal_parsing = internal_parsing
            GObject.idle_add(lambda: self.emit("loaded"))
        except Exception as e:
            GObject.idle_add(lambda: self.emit("load-failed", e))
            raise

    @debug_time
    def reread_files_async(self):
        t = threading.Thread(target=self.reread_files)
        t.start()

    def commodities(self):
        pool = None
        for post in self.journal.query(""):
            for post in post.xact.posts():
                pool = post.amount.commodity.pool()
        if pool is None:
            pool = ledger.Amount("$ 1").commodity.pool()
        for n in pool.iterkeys():
            if n in "%hms" or not n:
                continue
            c = pool.find(n)
            yield c

    def commodity(self, label, create=False):
        pool = ledger.Amount("$ 1").commodity.pool()
        if create:
            return pool.find_or_create(label)
        else:
            return pool.find(label)

    def accounts_and_last_commodities(self):
        # Commodities returned by this method do not contain any annotations.
        accts = []
        commos = dict()
        for post in self.journal.query(""):
            for post in post.xact.posts():
                if str(post.account) not in accts:
                    accts.append(str(post.account))
                comm = post.amount / post.amount
                comm.commodity = comm.commodity.strip_annotations()
                commos[str(post.account)] = comm
        return accts, commos

    def all_payees(self):
        """Returns a list of strings with payees (transaction titles)."""
        titles = collections.OrderedDict()
        for xact in self.internal_parsing:
            if hasattr(xact, "payee") and xact.payee not in titles:
                titles[xact.payee] = xact.payee
        return titles.keys()

    def transactions_with_payee(self, payee, case_sensitive=True):
        transes = []
        for xact in self.internal_parsing:
            if not hasattr(xact, "payee"):
                continue
            left = xact.payee
            right = payee
            if not case_sensitive:
                left = left.lower()
                right = right.lower()
            if left == right:
                transes.append(xact)
        return transes

    def query(self, querystring):
        return self.journal.query(querystring)

    def raw_xacts_iter(self):
        for p in self.journal.xacts():
            yield p

    def balance_in_single_commodity(self, querystring):
        amount1 = ledger.Balance()
        for post in self.journal.query(querystring):
            amount1 += post.amount
        return amount1.commodity_amount()

    def generate_record(self, *args):
        return generate_record(*args)

    def generate_price_records(self, prices):
        return generate_price_records(prices)

    def add_lines_to_file(self, lines):
        f = open(self.path, "a")
        print >> f, "\n".join(lines),
        f.close()
        self.reread_files()

    def add_lines_to_price_file(self, lines):
        f = open(self.price_path, "a")
        print >> f, "\n".join(lines),
        f.close()
        self.reread_files()

    def add_text_to_file(self, text):
        f = open(self.path, "a")
        print >> f, text,
        f.close()
        self.reread_files()

    def add_text_to_file_async(self, text):
        f = open(self.path, "a")
        print >> f, text,
        f.close()
        self.reread_files_async()


class Settings(dict):

    def __init__(self, filename):
        self.data = dict()
        self.filename = filename

    @classmethod
    def load_or_defaults(cls, filename):
        s = cls(filename)
        if os.path.isfile(s.filename):
            s.data = cPickle.load(open(s.filename, "rb"))
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

    def get(self, item, default):
        return self.data.get(item, default)

    def persist(self):
        p = open(self.filename, "wb")
        cPickle.dump(self.data, p)
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
    print


def prompt_for_expense(prompt):
    return raw_input(prompt + " ").strip()


def go_cursor_up(fd):
    fd.write(CURSOR_UP)


def blank_line(fd, chars):
    fd.write(" " * chars)
    print


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
        for account, ws in self.account_to_words.items():
            for w, c in ws.items():
                if w in words:
                    if not account in account_counts:
                        account_counts[account] = 0
                    account_counts[account] += c
        results = list(reversed(sorted(
            account_counts.items(), key=lambda x: x[1]
        )))
        if results:
            return results[0][0]
        return None


# ======================  GTK =======================


EVENT_PLUS = 65451
EVENT_MINUS = 65453
EVENT_PAGEUP = 65365
EVENT_PAGEDOWN = 65366
EVENT_ESCAPE = 65307
EVENT_ENTER = 65293
EVENT_TAB = 65289
EVENT_SHIFTTAB = 65056


class NavigatableCalendar(Gtk.Calendar):

    def __init__(self, *args):
        Gtk.Calendar.__init__(self, *args)
        self.followed = None
        self.followed_last_value = None
        self.connect("key-press-event", self.keyboard_nav)
        self.connect("day-selected", self.process_select_day)

    def set_datetime_date(self, date):
        if isinstance(date, basestring):
            date = datetime.datetime.strptime(date_string, "%Y-%m-%d").date()
        if self.followed and self.followed.get_datetime_date() > date:
            date = self.followed.get_datetime_date()

        self.select_month(date.month - 1, date.year)
        self.select_day(date.day)

    def process_select_day(self, *args):
        if self.followed and self.followed.get_datetime_date() > self.get_datetime_date():
            self.set_datetime_date(self.followed.get_datetime_date())

    def get_datetime_date(self):
        return datetime.date(self.props.year,
                             self.props.month+1, self.props.day)

    def keyboard_nav(self, cal, event, user_data=None):
        c = cal.get_datetime_date()
        if event.keyval == EVENT_PLUS:
            n = c + datetime.timedelta(1)
            cal.set_datetime_date(n)
            return True
        elif event.keyval == EVENT_MINUS:
            n = c - datetime.timedelta(1)
            cal.set_datetime_date(n)
            return True
        elif event.keyval == EVENT_PAGEUP:
            cal.set_datetime_date(add_months(c, -1))
            return True
        elif event.keyval == EVENT_PAGEDOWN:
            cal.set_datetime_date(add_months(c, 1))
            return True
        return False

    def follow(self, other_calendar):
        self.followed = other_calendar
        self.followed_last_value = other_calendar.get_datetime_date()
        def copy_when(other_calendar, *args):
            if self.get_datetime_date() == self.followed_last_value or other_calendar.get_datetime_date() > self.get_datetime_date():
                self.set_datetime_date(other_calendar.get_datetime_date())
            self.followed_last_value = other_calendar.get_datetime_date()
        other_calendar.connect("day-selected", copy_when)


class EagerCompletion(Gtk.EntryCompletion):
    """Completion class that substring matches within a builtin ListStore."""

    def __init__(self, *args):
        Gtk.EntryCompletion.__init__(self, *args)
        self.set_model(Gtk.ListStore(GObject.TYPE_STRING))
        self.set_match_func(self.iter_points_to_matching_entry)
        self.set_text_column(0)
        self.set_inline_completion(True)

    def iter_points_to_matching_entry(self, c, k, i, u=None):
        model = self.get_model()
        acc = model.get(i, 0)[0].lower()
        if k.lower() in acc:
            return True
        return False


class EagerCompletingEntry(Gtk.Entry):
    """Entry that substring-matches eagerly using a builtin ListStore-based
    Completion, and also accepts defaults.
    """

    prevent_completion = False

    def __init__(self, *args):
        Gtk.Entry.__init__(self, *args)
        self.default_text = ''
        self.old_default_text = ''
        self.set_completion(EagerCompletion())

    def set_default_text(self, default_text):
        self.old_default_text = self.default_text
        self.default_text = default_text
        if not self.get_text() or self.get_text() == self.old_default_text:
            self.set_text(self.default_text)


class LedgerAmountEntry(Gtk.Grid):

    __gsignals__ = {
        'changed' : (GObject.SIGNAL_RUN_LAST, None,
                    ())
    }

    def show(self):
        Gtk.Grid.show(self)
        self.entry.show()
        self.display.show()

    def do_changed(self):
        pass

    def __init__(self, *args):
        Gtk.Grid.__init__(self)
        self.amount = None
        self.entry = Gtk.Entry()
        self.entry.set_width_chars(8)
        self.display = Gtk.Label()
        self.entry.set_alignment(1.0)
        self.attach(self.entry, 0, 0, 1, 1)
        self.attach(self.display, 1, 0, 1, 1)
        self.display.set_xalign(1.0)
        self.display.set_justify(Gtk.Justification.RIGHT)
        self.set_column_spacing(4)
        self.donotreact = False
        self.entry.connect("changed", self.entry_changed)
        self.set_default_commodity(ledger.Amount("$ 1").commodity)
        self.set_activates_default = self.entry.set_activates_default

    def set_default_commodity(self, commodity):
        if isinstance(commodity, ledger.Amount):
            commodity = commodity.commodity
        self.default_commodity = commodity
        self.entry_changed(self.entry)

    def is_focus(self):
        return self.entry.is_focus()

    def grab_focus(self):
        self.entry.grab_focus()

    def get_amount(self):
        return self.amount

    def set_amount(self, amount, skip_entry_update=False):
        self.amount = amount
        self.display.set_text(str(amount) if amount is not None else "")
        self.donotreact = True
        if not skip_entry_update:
            self.entry.set_text(str(amount) if amount is not None else "")
        self.donotreact = False
        self.emit("changed")

    def set_text(self, text):
        self.entry.set_text(text)

    def entry_changed(self, w, *args):
        if self.donotreact:
            return

        text = self.entry.get_text()

        try:
            p = ledger.Amount(text)
        except ArithmeticError:
            self.set_amount(None, True)
            self.emit("changed")
            return

        if not str(p.commodity):
            p.commodity = self.default_commodity
        if str(p):
            self.set_amount(p, True)
        else:
            self.set_amount(None, True)

        self.emit("changed")


class EditableTabFocusFriendlyTextView(Gtk.TextView):

    def __init__(self, *args):
        Gtk.TextView.__init__(self, *args)
        self.connect("key-press-event", self.handle_tab)

    def handle_tab(self, widget, event):
        if event.keyval == EVENT_TAB:
            widget.get_toplevel().child_focus(Gtk.DirectionType.TAB_FORWARD)
            return True
        elif event.keyval == EVENT_SHIFTTAB:
            widget.get_toplevel().child_focus(Gtk.DirectionType.TAB_BACKWARD)
            return True
        return False


class LedgerTransactionView(EditableTabFocusFriendlyTextView):

    def __init__(self, *args):
        EditableTabFocusFriendlyTextView.__init__(self, *args)
        self.override_font(
            Pango.font_description_from_string('monospace')
        )

    def generate_record(self, what, when, cleared, accountamounts):
        lines = generate_record(
            what, when, cleared, accountamounts,
        )
        self.get_buffer().set_text("\n".join(lines))


class EscapeHandlingMixin(object):

    escape_handling_suspended = False

    def activate_escape_handling(self):
        self.connect("key-press-event", self.handle_escape)

    def suspend_escape_handling(self):
        self.escape_handling_suspended = True

    def resume_escape_handling(self):
        self.escape_handling_suspended = False

    def handle_escape(self, window, event, user_data=None):
        if (
            not self.escape_handling_suspended and
            event.keyval == EVENT_ESCAPE
        ):
            self.emit('delete-event', None)
            return True
        return False


def FatalError(message, secondary=None, outside_mainloop=False, parent=None):
    d = Gtk.MessageDialog(
        parent,
        Gtk.DialogFlags.DESTROY_WITH_PARENT,
        Gtk.MessageType.ERROR,
        Gtk.ButtonsType.CLOSE,
        message,
    )
    if secondary:
        d.format_secondary_text(secondary)
    d.run()


cannot_start_dialog = lambda msg: FatalError("Cannot start program", msg, outside_mainloop=True)


@debug_time
def load_journal_and_settings_for_gui(price_file_mandatory=False,
                                      read_journal=True):
    try:
        ledger_file = find_ledger_file()
    except Exception, e:
        cannot_start_dialog(str(e))
        sys.exit(4)
    try:
        price_file = find_ledger_price_file()
    except LedgerConfigurationError, e:
        if price_file_mandatory:
            cannot_start_dialog(str(e))
            sys.exit(4)
        else:
            price_file = None
    except Exception, e:
        cannot_start_dialog(str(e))
        sys.exit(4)
    try:
        if read_journal:
            journal = Journal.from_file(ledger_file, price_file)
        else:
            journal = Journal.from_file_unloaded(ledger_file, price_file)
    except Exception, e:
        cannot_start_dialog("Cannot open ledger file: %s" % e)
        sys.exit(5)
    s = Settings.load_or_defaults(os.path.expanduser("~/.ledgerhelpers.ini"))
    return journal, s


def find_ledger_file_for_gui():
    try:
        ledger_file = find_ledger_file()
        return ledger_file
    except Exception, e:
        cannot_start_dialog(str(e))
        sys.exit(4)


def parse_date(putative_date, return_format=False):
    """Returns a date substring in a ledger entry, parsed as datetime.date."""
    # FIXME: use Ledger functions to parse dates, not mine.
    formats = ["%Y-%m-%d", "%Y/%m/%d"]
    for f in formats:
        try:
            d = datetime.datetime.strptime(putative_date, f).date()
            break
        except ValueError, e:
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
