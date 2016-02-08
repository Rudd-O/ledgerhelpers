import datetime
import ledgerhelpers as m
import test.test_base as base
from unittest import TestCase as T


class TestJournal(T):

    def test_journal_with_simple_transaction(self):
        c = base.datapath("simple_transaction.dat")
        j = m.Journal.from_file(c, None)
        payees = j.all_payees()
        self.assertListEqual(payees, ["beer"])
        ts = j.transactions_with_payee("beer")
        self.assertEqual(ts[0].payee, "beer")


class TestGenerateRecord(T):

    def test_no_spurious_whitespace(self):
        title = "x"
        date = datetime.date(2014, 1, 1)
        cleared_date = None
        accountamounts = [
            ("assets", ["56 CHF"]),
            ("expenses", [""]),
        ]
        res = m.generate_record(title, date, cleared_date, accountamounts)
        self.assertListEqual(
            res,
            """
2014-01-01 x
    assets      56 CHF
    expenses

""".splitlines())
