import datetime
import ledgerhelpers as m
import ledgerhelpers.journal as journal
import test.test_base as base
import tempfile
from unittest import TestCase as T


class TestJournal(T):

    def test_journal_with_simple_transaction(self):
        c = base.datapath("simple_transaction.dat")
        j = journal.Journal.from_file(c, None)
        payees = j.all_payees()
        self.assertListEqual(payees, ["beer"])
        accts, commos = j.accounts_and_last_commodity_for_account()
        expaccts = ["Accounts:Cash", "Expenses:Drinking"]
        self.assertListEqual(accts, expaccts)
        self.assertEqual(commos["Expenses:Drinking"], "1.00 CHF")

    def test_reload_works(self):
        with tempfile.NamedTemporaryFile() as f:
            data = file(base.datapath("simple_transaction.dat")).read()
            f.write(data)
            f.flush()
            j = journal.Journal.from_file(f.name, None)
            _, commos = j.accounts_and_last_commodity_for_account()
            self.assertEqual(commos["Expenses:Drinking"], "1.00 CHF")
            data = data.replace("CHF", "EUR")
            f.write(data)
            f.flush()
            _, commos = j.accounts_and_last_commodity_for_account()
            self.assertEqual(commos["Expenses:Drinking"], "1.00 EUR")

    def test_transactions_with_payee_match(self):
        c = base.datapath("simple_transaction.dat")
        j = journal.Journal.from_file(c, None)
        ts = journal.transactions_with_payee("beer", j.internal_parsing())
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
