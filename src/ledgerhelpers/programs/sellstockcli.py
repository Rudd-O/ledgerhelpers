#!/usr/bin/env python

import datetime
import itertools
import ledger
import os
import sys
import ledgerhelpers as common
from ledgerhelpers import debug


class Lot(object):

    def __init__(self, number, dates, price, amt, accts):
        self.number = number
        self.dates_seen = [str(date) for date in dates]
        self.amount = ledger.Amount(str(amt) + " {%s}" % price)
        self.price = self.amount.price() / amt
        self.amount = amt
        self.accounts_seen = [str(a) for a in accts]

    def __str__(self):
        return (
            "<Lot %s of %s at price %s in accts"
            "%s and seen on dates %s>"
        ) % (
            self.number, self.amount, self.price, self.accounts_seen,
            self.dates_seen
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
            key=lambda l: "%6s%s" % (l.number, l.dates_seen[-1])
        ))

    def locate_lot(self, price, account, amount=None):
        thelot = [
            l for l in self
            if (str(l.price) == str(price)) and
            (l.accounts_seen[-1] == account)
        ]
        if len(thelot) > 1 and amount is not None:
            srch = [l for l in thelot if l.amount == amount]
            if len(srch) > 0:
                thelot = srch
        assert len(thelot) < 2, [str(x) for x in thelot]
        return thelot[0]

    def nextnum(self):
        if not self.lots:
            return 1
        return max([l.number for l in self.lots]) + 1

    def register(self, date, amount, price, account):
        l = (date, amount, price, str(account))
        self.unfinished.append(l)

    def commit(self):
        for _, unfinished in itertools.groupby(
            self.unfinished, lambda x: str(x[2])
        ):
            unfinished = list(unfinished)
            inputs = [l for l in unfinished if l[1] < 0]
            outputs = [l for l in unfinished if l not in inputs]
            for i in inputs[:]:
                debug("Registering input %s", i)
                _, iam, ip, iac = i
                ilot = self.locate_lot(ip, iac, -iam)
                debug("Corresponding input lot located %s", ilot)
                debug("reducing lot amount by %s", iam)
                ilot.amount += iam
                debug("Detecting which lots it should output to")
                for o in outputs[:]:
                    debug("Trying lot %s", o)
                    od, oam, op, oac = o
                    toinc = min([-iam, oam])
                    debug("Must increment lot by %s", toinc)
                    try:
                        olot = self.locate_lot(op, oac)
                        debug("Located target lot %s", olot)
                        olot.dates_seen += [od]
                        olot.amount += toinc
                        debug("Lot incremented by %s", toinc)
                    except IndexError:
                        olot = Lot(ilot.number,
                                   ilot.dates_seen + [od],
                                   op,
                                   toinc,
                                   ilot.accounts_seen + [oac])
                        debug("Created new target lot %s", olot)
                        self.lots.append(olot)
                    iam += toinc
                    if toinc == oam:
                        debug("This output is spent %s", o)
                        outputs.remove(o)
                    else:
                        debug("Reducing this output for future use %s", o)
                        outputs[outputs.index(o)] = (od, oam - toinc, op, oac)
                    if iam == 0:
                        break
                if ilot.amount == 0:
                    debug("Lot reached zero, removing %s", ilot)
                    self.lots.remove(ilot)
                inputs.remove(i)
            for o in outputs[:]:
                debug("Registering output %s", o)
                od, oam, op, oac = o
                olot = Lot(self.nextnum(),
                           [od],
                           op,
                           oam,
                           [oac])
                self.lots.append(olot)
                outputs.remove(o)
            assert not inputs, inputs
            assert not outputs, outputs
        self.unfinished = []

    def subtract(self, amount):
        lots = []
        subtracted = amount - amount
        while subtracted < amount:
            try:
                l = self[0]
            except IndexError:
                raise NotEnough(amount - subtracted)
            to_reduce = min([l.amount, amount - subtracted])
            if to_reduce == l.amount:
                lots.append(l)
                self.lots.remove(l)
            else:
                l.amount -= to_reduce
                lots.append(Lot(l.number,
                                l.dates_seen,
                                l.price,
                                to_reduce,
                                l.accounts_seen))
            subtracted += to_reduce
        return lots


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

    ignoreaccts = ["Funding:Stock vesting"]

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
    last_xact = None
    for post in journal.query(""):
        if post.xact != last_xact:
            for post in post.xact.posts():
                if str(post.account) in ignoreaccts:
                    continue
                if str(post.amount.commodity) == "$":
                    continue
                if str(post.amount.commodity) != str(target_amount.commodity):
                    continue
                trueamount = ledger.Amount(post.amount.strip_annotations())
                lotprice = post.amount.price() / trueamount
                account = post.account
                date = post.date
                all_lots.register(date, trueamount, lotprice, account)
            all_lots.commit()
            last_xact = post.xact

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
    for l in lots_produced:
        lines.append((
            l.accounts_seen[-1],
            ["%s {%s} @ %s" % (-1 * l.amount, l.price, target_sale_price)]
        ))
        diff = (l.price - target_sale_price) * l.amount
        lines.append((gainslossesacct, [diff]))
    totalsale = target_sale_price * sum(
        l.amount.number() for l in lots_produced
    )
    lines.append((saleacct, [totalsale - commission]))
    lines.append((commissionsaccount, [commission]))

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
