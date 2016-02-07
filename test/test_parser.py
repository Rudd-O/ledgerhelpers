import datetime
import ledgerhelpers.parser as parser
import test.test_base as base
from unittest import TestCase as T


class TestParser(T):

    def test_simple_transaction(self):
        c = base.data("simple_transaction.dat")
        items = parser.lex_ledger_file_contents(c)
        self.assertEqual(len(items), 3)
        for n, tclass in enumerate([
            parser.TokenWhitespace,
            parser.TokenTransaction,
            parser.TokenWhitespace,
        ]):
            self.assertIsInstance(items[n], tclass)
        transaction = items[1]
        self.assertEqual(transaction.date, datetime.date(2015, 3, 12))
        self.assertEqual(transaction.clearing_date, datetime.date(2015, 3, 15))
        self.assertEqual(transaction.payee, "beer")
        for n, (ac, am) in enumerate([
            ("Accounts:Cash", "-6.00 CHF"),
            ("Expenses:Drinking", "6.00 CHF"),
        ]):
            self.assertEqual(transaction.postings[n].account, ac)
            self.assertEqual(transaction.postings[n].amount, am)

    def test_no_end_value(self):
        c = base.data("no_end_value.dat")
        items = parser.lex_ledger_file_contents(c)
        self.assertEqual(len(items), 5)
        for n, tclass in enumerate([
            parser.TokenWhitespace,
            parser.TokenTransaction,
            parser.TokenWhitespace,
            parser.TokenTransaction,
            parser.TokenWhitespace,
        ]):
            self.assertIsInstance(items[n], tclass)
        for transaction in (items[1], items[3]):
            self.assertEqual(transaction.payee, "beer")
            for n, (ac, am) in enumerate([
                ("Accounts:Cash", "-6.00 CHF"),
                ("Expenses:Drinking", ""),
            ]):
                self.assertEqual(transaction.postings[n].account, ac)
                self.assertEqual(transaction.postings[n].amount, am)

    def test_with_comments(self):
        c = base.data("with_comments.dat")
        items = parser.lex_ledger_file_contents(c)
        self.assertEqual(len(items), 3)
        for n, tclass in enumerate([
            parser.TokenWhitespace,
            parser.TokenTransaction,
            parser.TokenWhitespace,
        ]):
            self.assertIsInstance(items[n], tclass)
        transaction = items[1]
        self.assertEqual(transaction.date, datetime.date(2011, 12, 25))
        self.assertEqual(transaction.clearing_date, datetime.date(2011, 12, 25))
        self.assertEqual(transaction.payee, "a gift!")
        self.assertEqual(transaction.state, parser.STATE_CLEARED)
        for n, (ac, am) in enumerate([
            ("Assets:Metals", "1 \"silver coin\"    @ $55"),
            ("Income:Gifts", "$        -55"),
        ]):
            self.assertEqual(transaction.postings[n].account, ac)
            self.assertEqual(transaction.postings[n].amount, am)

    def test_my_data_file(self):
        try:
            c = base.data("/home/user/.ledger")
        except IOError:
            return
        items = parser.lex_ledger_file_contents(c)
