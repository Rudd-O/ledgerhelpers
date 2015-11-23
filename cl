#!/usr/bin/env python

import datetime
import ledger
import os
import re
import sys
sys.path.append(os.path.dirname(__file__))
import common


date_re = re.compile("^([0-9][0-9][0-9][0-9].[0-9][0-9].[0-9][0-9])(=[0-9][0-9][0-9][0-9].[0-9][0-9].[0-9][0-9]|)( +\\*| +)")


def clear(f):
    changed = False
    lines = file(f).readlines()

    for n, line in enumerate(lines):
        m = date_re.match(line)
        if not m:
            continue
        if "*" in m.group(3):
            continue
        sys.stdout.write(line)
        originaln = n
        while True:
            n = n + 1
            try:
                nextline = lines[n]
            except IndexError:
                break
            if nextline.startswith(" ") or nextline.startswith("\t"):
                sys.stdout.write(nextline)
            else:
                break
        if m.group(2):
            initial = datetime.datetime.strptime(m.group(2)[1:], "%Y-%m-%d").date()
        else:
            initial = datetime.datetime.strptime(m.group(1), "%Y-%m-%d").date()
        choice = common.prompt_for_date_optional(
            sys.stdin, sys.stdout,
            "Mark cleared at this date?",
            initial,
        )
        if choice is not None:
            lines[originaln] = "%s=%s * %s" % (m.group(1), choice, date_re.sub("", line))
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


if __name__ == "__main__":
    sys.exit(clear(common.find_ledger_file()))