from ledgerhelpers.legacy import get_terminal_width, \
print_line_ellipsized, read_one_character, go_cursor_up, blank_line, \
generate_record as generate_record_novalidate

import ledger


class LedgerParseError(ValueError):
    pass


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


def generate_record(title, date, auxdate, state, accountamounts,
                    validate=False):
    """Generates a transaction record.
    See callee.  Validate uses Ledger to validate the record.
    """
    lines = generate_record_novalidate(
        title, date, auxdate,
        state, accountamounts
    )

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
