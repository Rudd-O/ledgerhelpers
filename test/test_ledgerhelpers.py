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
