#!/usr/bin/python3

import datetime
import ledger
import os
import sys
import ledgerhelpers
import ledgerhelpers.legacy as common
import ledgerhelpers.journal as journal


def main():
    s = ledgerhelpers.Settings.load_or_defaults(os.path.expanduser("~/.ledgerhelpers.ini"))
    j = journal.Journal.from_file(ledgerhelpers.find_ledger_file(), None)
    accts, commodities = j.accounts_and_last_commodity_for_account()

    when = common.prompt_for_date(
        sys.stdin, sys.stdout,
        "When?",
        s.get("last_date", datetime.date.today())
    )
    if when == datetime.date.today():
        del s["last_date"]
    else:
        s["last_date"] = when

    asset1 = common.prompt_for_account(
        sys.stdin, sys.stdout,
        accts, "From where?",
        s.get("last_withdrawal_account", None)
    )
    assert asset1, "Not an account: %s" % asset1
    s["last_withdrawal_account"] = asset1
    asset1_currency = commodities.get(asset1, ledger.Amount("$ 1"))

    asset2 = common.prompt_for_account(
        sys.stdin, sys.stdout,
        accts, "To where?",
        s.get("last_deposit_account", None)
    )
    assert asset2, "Not an account: %s" % asset2
    s["last_deposit_account"] = asset2
    asset2_currency = commodities.get(asset2, ledger.Amount("$ 1"))

    amount1 = common.prompt_for_amount(
        sys.stdin, sys.stdout,
        "How much?", asset1_currency
    )

    amount2 = common.prompt_for_amount(
        sys.stdin, sys.stdout,
        "What was deposited?", asset2_currency
    )

    lines = j.generate_record("Withdrawal", when, None, "", [
        (asset1, -1 * amount1),
        (asset2, amount2),
    ])
    print("========== Record ==========")
    print("\n".join(lines))
    save = common.yesno(
        sys.stdin, sys.stderr,
        "Hit ENTER or y to save it to the file, BACKSPACE or n to skip saving: "
    )
    if save:
        j.add_text_to_file(lines)
