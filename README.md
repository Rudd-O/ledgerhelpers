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

* Enter transactions easily with
  [addtrans](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/addtrans).
* Update your price quotes with
  [updateprices](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/updateprices).
* Record multi-currency ATM withdrawals with
  [withdraw-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/withdraw-cli).
* Record FIFO stock or commodity sales with
  [sellstock-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/sellstock-cli).
* Interactively clear transactions with
  [cleartrans-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/cleartrans-cli).
* Keep your ledger chronologically sorted with
  [sorttrans-cli](https://github.com/Rudd-O/ledgerhelpers/blob/master/bin/sorttrans-cli).

Usage and manuals
-----------------

* [How to add transactions with `addtrans`](doc/addtrans.md)

See also individual [manual pages](man/) in NROFF format.

How to download and install
---------------------------

Here are instructions to install the very latest iteration of ledgerhelpers:

On Linux systems that support RPM packages:

* Obtain the package with `git clone https://github.com/Rudd-O/ledgerhelpers`
* Change to the directory `cd ledgerhelpers`
* Create an installable package with `python setup.py bdist_rpm`
* Install the package with `sudo rpm -Uvh dist/*noarch.rpm`

On other Linux systems:

* Obtain the package with `git clone https://github.com/Rudd-O/ledgerhelpers`
* Change to the directory `cd ledgerhelpers`
* Install directly with `sudo python setup.py install`

On Mac OS X, the `python setup.py install` routine appears to have some problems,
however this should be reasonably easy to fix by excluding the files in
`/usr/share/applications` from being installed.  I await for more information
on how to mitigate this issue.  In the meantime, the programs in `bin/` can run
from the source directory, but you still need to install the right dependencies,
such as GTK+ 3 or later, and the Python GObject introspection library.

License
-------

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

See [full license terms](LICENSE.txt).
