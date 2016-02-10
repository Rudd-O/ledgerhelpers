Ledger helpers (ledgerhelpers)
============================

This is a collection of small single-purpose programs to aid your accounting
with [Ledger](https://github.com/ledger/ledger) (ledger-cli).  Think of it
as the batteries that were never included with Ledger.

Why should you use them?  Because:


* All the ledgerhelpers have been designed with fast data entry in mind,
  and they will remember or evoke existing data as needed, to help you minimize
  typing and other drudgery.
* They all have launcher icons in your desktop environment -- this makes it
  very easy to add icons or shortcuts for them, so you can run them on the spot.

This package also contains a library with common functions that you can use
in your project to make it easier to develop software compatible with Ledger.

What can you do with these programs
-----------------------------------

* Enter simple purchases and other two-line items with
  [buy](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/buy).
* Enter multiline transactions with
  [addtrans](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/addtrans).
* Update your price quotes with
  [updateprices](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/updateprices).
* Record multi-currency ATM withdrawals with
  [withdraw-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/withdraw-cli).
* Record FIFO stock or commodity sales with
  [sellstock-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/sellstock).
* Interactively clear transactions with
  [cleartrans-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/cleartrans-cli).
* Keep your ledger chronologically sorted with
  [sottrans-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/sorttrans-cli).
