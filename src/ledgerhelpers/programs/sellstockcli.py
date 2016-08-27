#!/usr/bin/env python

import datetime
import fnmatch
import ledger
import re
import subprocess
import sys
import ledgerhelpers as common


class Lot(object):

    def __init__(self, number, date, amount, acct):
        self.number = number
        self.date = date
        self.amount = amount
        quantity = ledger.Amount(amount.strip_annotations())
        self.price = self.amount.price() / quantity
        self.account = acct

    def __str__(self):
        return (
            "<Lot %s of %s at price %s in acct "
            "%s with date %s>"
        ) % (
            self.number, self.amount, self.price, self.account,
            self.date
        )


class NotEnough(Exception):
    pass


class Lots(object):

    def __init__(self):
        self.lots = []
        self.unfinished = []

    def __getitem__(self, idx):
        return list(self)[idx]

    def __iter__(self):
        return iter(sorted(
            self.lots,
            key=lambda l: "%s" % (l.date,)
        ))

    def parse_ledger_bal(self, text):
        """Demands '--balance-format=++ %(account)\n%(amount)\n' format.
        Demands '--date-format=%Y-%m-%d' date format."""
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        account = None
        for line in lines:
            if line.startswith("++ "):
                account = line[3:]
            else:
                amount = ledger.Amount(line)
                date = re.findall(r'\[\d\d\d\d-\d\d-\d\d]', line)
                assert len(date) < 2
                if date:
                    date = common.parse_date(date[0][1:-1])
                else:
                    date = None
                try:
                    lot = Lot(self.nextnum(),
                            date,
                            amount,
                            account)
                    self.lots.append(lot)
                except TypeError:
                    # At this point, we know the commodity does not have a price.
                    # So we ignore this.
                    pass

    def nextnum(self):
        if not self.lots:
            return 1
        return max([l.number for l in self.lots]) + 1

    def first_lot_by_commodity(self, commodity):
        return [s for s in self if str(s.amount.commodity) == str(commodity)][0]

    def subtract(self, amount):
        lots = []
        subtracted = amount - amount
        while subtracted < amount:
            try:
                l = self.first_lot_by_commodity(amount.commodity)
            except IndexError:
                raise NotEnough(amount - subtracted)
            to_reduce = min([l.amount.strip_annotations(), amount - subtracted])
            if str(to_reduce) == str(l.amount.strip_annotations()):
                lots.append(l)
                self.lots.remove(l)
            else:
                l.amount -= to_reduce.number()
                new_amount = l.amount - l.amount + to_reduce.number()
                lots.append(Lot(l.number,
                                l.date,
                                new_amount,
                                l.account))
            subtracted += to_reduce
        return lots


def matches(string, options):
    for option in options:
        if fnmatch.fnmatch(string, option):
            return True
    return False


def main():
    journal, s = common.load_journal_and_settings_for_gui()
    accts, commodities = journal.accounts_and_last_commodities()

    saleacct = common.prompt_for_account(
        sys.stdin, sys.stdout,
        accts, "Which account was the sold commodity stored in?",
        s.get("last_sellstock_account", None)
    )
    assert saleacct, "Not an account: %s" % saleacct
    s["last_sellstock_account"] = saleacct

    commissionsaccount = common.prompt_for_account(
        sys.stdin, sys.stdout,
        accts, "Which account to account for commissions?",
        s.get("last_commissions_account", None)
    )
    assert commissionsaccount, "Not an account: %s" % commissionsaccount
    s["last_commissions_account"] = commissionsaccount

    gainslossesacct = common.prompt_for_account(
        sys.stdin, sys.stdout,
        accts, "Which account to credit gains and losses?",
        s.get("last_gainslosses_account",
              "Capital:Recognized gains and losses")
    )
    assert gainslossesacct, "Not an account: %s" % gainslossesacct
    s["last_gainslosses_account"] = gainslossesacct

    target_amount = common.prompt_for_amount(
        sys.stdin, sys.stdout,
        "How many units of what commodity?", ledger.Amount("$ 1")
    )
    target_sale_price = common.prompt_for_amount(
        sys.stdin, sys.stdout,
        "What is the sale price of the commodity?", ledger.Amount("$ 1")
    )
    commission = common.prompt_for_amount(
        sys.stdin, sys.stdout,
        "What was the commission of the trade?", ledger.Amount("$ 1")
    )

    all_lots = Lots()
    lots_text = subprocess.check_output([
        'ledger', 'bal',
        '--lots', '--lot-dates', '--lot-prices',
        '--date-format=%Y-%m-%d', '--sort=date',
        '--balance-format=++ %(account)\n%(amount)\n',
        saleacct
    ])
    all_lots.parse_ledger_bal(lots_text)

    print "=========== Read ==========="
    for l in all_lots:
        print l

    lots_produced = all_lots.subtract(target_amount)

    print "========= Computed ========="
    for l in lots_produced:
        print l

    print "=========== Left ==========="
    for l in all_lots:
        print l

    lines = []
    tpl = "%s {%s}%s @ %s"
    datetpl = ' [%s]'
    for l in lots_produced:
        m = -1 * l.amount
        if m.commodity.details.date:
            datetext = datetpl % m.commodity.details.date.strftime("%Y-%m-%d")
        else:
            datetext = ''
        lines.append((
            l.account,
            [tpl % (m.strip_annotations(),
                    m.commodity.details.price,
                    datetext,
                    target_sale_price)]
        ))
        diff = (l.price - target_sale_price) * l.amount
        lines.append((gainslossesacct, [diff]))
    totalsale = target_sale_price * sum(
        l.amount.number() for l in lots_produced
    )
    lines.append((saleacct, totalsale - commission))
    lines.append((commissionsaccount, commission))

    lines = journal.generate_record(
        "Sale of %s" % (target_amount),
        datetime.date.today(), None,
        lines,
    )
    print "========== Record =========="
    print "\n".join(lines)
    save = common.yesno(
        sys.stdin, sys.stderr,
        "Hit ENTER or y to save it to the file, BACKSPACE or n to skip saving: "
    )
    if save:
        journal.add_text_to_file(lines)
