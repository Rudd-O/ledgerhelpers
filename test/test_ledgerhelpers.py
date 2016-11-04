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
            ("assets", "56 CHF"),
            ("expenses", ""),
        ]
        res = m.generate_record(title, date, cleared_date, "", accountamounts)
        self.assertListEqual(
            res,
            """
2014-01-01 x
    assets      56 CHF
    expenses

""".splitlines())

    def test_no_cleared_date_when_cleared_date_not_supplied(self):
        cases = [
            ("2014-01-01 x", (datetime.date(2014, 1, 1), None), ""),
            ("2014-01-01 * x", (datetime.date(2014, 1, 1), datetime.date(2014, 1, 1)), "*"),
            ("2014-01-01=2015-01-01 ! x", (datetime.date(2014, 1, 1), datetime.date(2015, 1, 1)), "!"),
        ]
        accountamounts = [("assets", "56 CHF"), ("expenses", "")]
        for expected_line, (date, cleared), statechar in cases:
            res = m.generate_record("x", date, cleared, statechar, accountamounts)[1]
            self.assertEqual(res, expected_line)

    def test_empty_record_auto_goes_last(self):
        accountamounts = [("expenses", ""), ("assets:cash", "56 CHF")]
        res = m.generate_record("x", datetime.date(2014, 1, 1),
                                None, "", accountamounts)
        self.assertListEqual(
            res,
            """
2014-01-01 x
    assets:cash    56 CHF
    expenses

""".splitlines())
