import datetime
import fcntl
import struct
import termios
import tty


CURSOR_UP = "\033[F"
QUIT = "quit"


yes_chars = "yY\n\r"
no_chars = "nN\x7f"
yesno_choices = dict()
for char in yes_chars:
    yesno_choices[char] = True
for char in no_chars:
    yesno_choices[char] = False
del char
del yes_chars
del no_chars


class Escaped(KeyboardInterrupt): pass


def go_cursor_up(fd):
    fd.write(CURSOR_UP)


def blank_line(fd, chars):
    fd.write(" " * chars)
    print()


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


def get_terminal_size(fd):
    def ioctl_GWINSZ(fd):
        return struct.unpack('hh', fcntl.ioctl(fd, termios.TIOCGWINSZ, '1234'))
    return ioctl_GWINSZ(fd)


def get_terminal_width(fd):
    return get_terminal_size(fd)[1]


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


def yesno(fdin, fdout, prompt):
    """Return True upon yY or ENTER, return False upon nN or BACKSPACE."""
    return choose(fdin, fdout, prompt, yesno_choices)


def prompt_for_expense(prompt):
    return input(prompt + " ").strip()


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


def prompt_for_date_optional(fdin, fdout, prompt, initial):
    return prompt_for_date(fdin, fdout, prompt, initial, True)


def parse_date(putative_date, return_format=False):
    """Returns a date substring in a ledger entry, parsed as datetime.date."""
    # FIXME: use Ledger functions to parse dates, not mine.
    formats = ["%Y-%m-%d", "%Y/%m/%d"]
    for f in formats:
        try:
            d = datetime.datetime.strptime(putative_date, f).date()
            break
        except ValueError as e:
            last_exception = e
            continue
    try:
        if return_format:
            return d, f
        else:
            return d
    except UnboundLocalError:
        raise ValueError("cannot parse date from format %s: %s" % (f, last_exception))


def format_date(date_obj, sample_date):
    _, fmt = parse_date(sample_date, True)
    return date_obj.strftime(fmt)


def generate_record(title, date, auxdate, state, accountamounts):
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
    return lines
