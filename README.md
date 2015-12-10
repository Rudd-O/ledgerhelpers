Ledger helpers (ledgerhelpers)
============================

This is a collection of utilities that makes it easy for you to do accounting
with Ledger (ledger-cli).  Think of it as the batteries that were never
included with Ledger.

This package also contains a library with common functions that you can use
in your project to make it easier to develop software compatible with Ledger.

Tools included in this set
--------------------------

This package contains several tools:

1. `buy`: a straightforward GUI tool to record a purchase.
2. `sorttrans-cli`: a program to retroactively sort a Ledger file, which lets
   you view the sort results as a three-way merge (with Meld), so that
   you can choose whether to accept the sort as-is, partially, or with edits.
3. `withdraw-cli`: a command to record a withdrawal from a bank,
   which supports recording international (dual-currency) withdrawals.
4. `cleartrans-cli`: a command to clear previously-uncleared transactions.
