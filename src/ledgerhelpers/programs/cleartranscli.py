#!/usr/bin/python2

import datetime
import os
import re
import sys
sys.path.append(os.path.dirname(__file__))
import ledgerhelpers as common
from ledgerhelpers import gui


date_re = "^([0-9][0-9][0-9][0-9].[0-9][0-9].[0-9][0-9])(=[0-9][0-9][0-9][0-9].[0-9][0-9].[0-9][0-9]|)\\s+(.+)"
date_re = re.compile(date_re, re.DOTALL)


def clear(f):
    changed = False
    lines = file(f).readlines()

    for n, line in enumerate(lines):
        m = date_re.match(line)
        if not m:
            continue
        if m.group(3).strip().startswith("*"):
            continue
        lines_to_write = [line]
        originaln = n
        while True:
            n = n + 1
            try:
                nextline = lines[n]
            except IndexError:
                break
            if nextline.startswith(" ") or nextline.startswith("\t"):
                lines_to_write.append(nextline)
            else:
                break
        initial_unparsed = m.group(2)[1:] if m.group(2) else m.group(1)
        initial = common.parse_date(initial_unparsed)
        if initial > datetime.date.today():
            continue
        for line in lines_to_write:
            sys.stdout.write(line)
        sys.stdout.flush()
        choice = common.prompt_for_date_optional(
            sys.stdin, sys.stdout,
            "Mark cleared at this date?",
            initial,
        )
        if choice is not None:
            choice_formatted = common.format_date(choice, initial_unparsed)
            if m.group(1) == choice_formatted:
                lines[originaln] = "%s * %s" % (
                    m.group(1),
                    m.group(3)
                )
            else:
                lines[originaln] = "%s=%s * %s" % (
                    m.group(1),
                    choice_formatted,
                    m.group(3)
                )
            for number in range(originaln + 1, n):
                # remove cleared bits on legs of the transaction
                lines[number] = re.sub("^(\\s+)\\*\\s+", "\\1", lines[number])
            changed = True
        else:
            pass
    if changed:
        y = file(f + ".new",  "w")
        y.write("".join(lines))
        y.flush()
        try:
            os.rename(f + ".new", f)
        except Exception:
            os.unlink(f + ".new")
            raise


def main():
    ledger_file = gui.find_ledger_file_for_gui()
    return clear(ledger_file)
