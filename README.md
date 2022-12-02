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

If you are on a Linux system and want to install it as an RPM package:

* Obtain the package with `git clone https://github.com/Rudd-O/ledgerhelpers`
* Change to the directory `cd ledgerhelpers`
* Create a source package with `python3 -m build --sdist`
* Create a source RPM with `rpmbuild --define "_srcrpmdir ./" --define "_sourcedir dist/" -bs *.spec`
  * You may need to install some dependencies at this point.  The process will tell you.
* Create an installable RPM with `rpmbuild --rebuild --nodeps --define "_rpmdir ./" *.src.rpm`
  * You may need to install some dependencies at this point.  The process will tell you.
* Install the package with `sudo rpm -Uvh noarch/*.noarch.rpm`

In other circumstances or Linux systems:

* Obtain the package with `git clone https://github.com/Rudd-O/ledgerhelpers`
* Change to the directory `cd ledgerhelpers`
* Create the source package directly with `python3 -m build --sdist`
* Install the package (to your user directory `~/.local`) with `pip3 install dist/*.tar.gz`
  * This will install a number of dependencies for you.  Your system should already
    have the GTK+ 3 library and the Python GObject introspection library.

The programs in `bin/` can generally run from the source directory, provided
that the PYTHONPATH points to the `src/` folder inside the source directory,
but you still need to install the right dependencies, such as GTK+ 3 or later,
and the Python GObject introspection library.

License
-------

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

See [full license terms](LICENSE.txt).
