`addtrans`: add transactions fast
=================================

This program helps you enter new transactions as fast as possible.  With as little as two or three keystrokes (one for autocompletion, zero or one for date change, and one for confirmation), you can have a correct transaction entered into your ledger.

This is how `addtrans` assists you:

* autocompletion of old transactions based on the payee / description,
* autocompletion of existing accounts as you type,
* intelligent currency detection for amounts, based on the last currency used for the account associated with the amount,
* intelligent memory of the last dates used for a transaction,
* extensive keyboard shortcuts, both to focus on fields and to alter unfocused fields (see below for details).

We'll quickly show you how you can take advantage of `addtrans` in a few screenshots and words.

Entering data with `addtrans`: a quick tutorial
-----------------------------------------------

After you install the program onto your system, you can simply run the *Add transaction* program under your desktop's program menu.

The program will appear like this:

![Add transaction running](addtrans-started-up.png?raw=true "Add transaction running")

At this point you are ready to begin typing the payee or the description of a transaction.  As you type, a dropdown with all matching transactions will appear, and the closest match will be used as a model for the transaction you are about to enter.  You can ignore the dropdown and continue typing, or simply select one from the dropdown and then hit *Enter*.

Note how the preview field below shows you the transaction as it will be entered at the end of your ledger.  This lets you have 100% confidence that what you see is what you will get.

This is how the process looks like (minus the dropdown, as my desktop environment does not let me capture transient windows here):

![Add transaction typeahed search](addtrans-dropdown.png?raw=true "Add transaction typeahead search")

Don't worry too much about this.  It's pretty intuitive.  Anything that matches a previous transaction gets automatically entered as the transaction you are about to enter.  As long as you have not yet altered the account and amount entries below, this autocomplete will replace the entire transaction as you edit it.

At this point, you might want to set the right dates (main and / or auxiliary) on the transaction you are entering.  Suppose you want to backtrack three days from today.  There are a number of ways to do so:

1. You can click on the calendar icon next to the date you want to change, then select the date and confirming.
2. You can switch to the respective date entry with the shortcut key associated with the entry (see below), then type the date.
3. You can simply use the appropriate general shortcut key three times to backtrack the date three days (Control+Minus, see below for full reference).

We'll choose option 3 for speed.  After the main date has gone back 3 days, note that the keyboard focus remains on the *Payee* field.  This is excellent — you invested very little effort, and you already have an almost fully finished transaction, with very few changes that need to be made.

Now you are ready to finish the rest of the transaction.  Again, simple.  Tab your way out of the *Payee* field and into the first amount, then enter the amount and the first account on the line below:

![Add transaction add amount](addtrans-amount.png?raw=true "Add transaction add amount")

Note that you can specify any currencies there, but *you don't have to*.  If you do not, `addtrans` will recall the last currency you used for the corresponding account, then use that currency.  What this means is that, in practice, 99% of the transactions you enter will never require you to type any currency.

Tab yourself out of the amount field, and enter an account.  We'll change the asset account to a different one:

![Add transaction account entry](addtrans-account.png?raw=true "Add transaction account entry")

Note that autocomplete works for us here.  Either enter your full account, or select the account from the autocomplete suggestions.  Remember that you can use either the mouse or the arrow keys and *Enter* to choose an option.

Follow the same process for the rest of the records of the transaction, then hit *Add* to record the entire transaction on your ledger.  Note that you can also hit *Enter* at any point and, if the transaction is valid, it will be recorded.

After recording a transaction, `addtrans` will leave you ready to enter further transactions:

![Add transaction ready for more](addtrans-readyagain.png?raw=true "Add transaction ready for more")

Things to note:

* Just as ledger normally allows, you do not need to enter an amount on the last record of the transaction.  As long as all but one of your records has an amount, `addtrans` is good with you.
* Adding amounts with currency equivalencies (`xxx CUR1 @ yyy CUR2`) works as you would expect of any ledger entry.
* `addtrans` will note any validation errors on its status line next to the action buttons at the bottom.  Note that there is a limitation in ledger (a bug that has been fixed, but whose fix has not been released) that prevents `addtrans` from telling you exactly what's wrong with the transaction, but we're confident at this time that the bug fix will be released soon.  In the meantime, use the transaction preview as a guide to understand what might be wrong.
* You can learn to enter transactions at amazing speed and with very little effort.  See below for very useful key combinations to help you enter data extremely fast.

Thus, we come to the end of the quick tutorial.

How to get to `addtrans` really fast
------------------------------------

`addtrans` starts really quickly, and it's very convenient to come back to your laptop or workstation after an expense to enter it right away.  So we recommend you add a global keyboard shortcut on your desktop environment, such that `addtrans` can be started with a single key.

Instructions vary from environment to environment:

* KDE: use the `kmenuedit` program:
  * Right-click on the Application Menu of your desktop.
  * Select *Edit Applications...*.
  * Find and select the menu entry for *Add transaction* (usually under the *Financial* category).
  * Move to the *Advanced* tab on the right-side menu entry pane.
  * Click on the button next to the *Current shortcut key*.
  * Tap on the key you want to use to launch the program.
  * Exit the menu editor, saving the changes you just made.

Key combinations and other tricks for fast data entry
-----------------------------------------------------

Key combos:

* General:
  * Alt+C: close window without saving
  * Enter: save transaction as displayed in the preview
  * Alt+A: save transaction as displayed in the preview
  * Tab: go to the next field or control
  * Shift+Tab: go to the previous field or control
* While any of the entry fields is focused:
  * Arrow Up: focus on the field right above the one with focus.
  * Arrow Down: focus on the field right below the one with focus.
  * Alt+T: focus on the main date
  * Alt+L: focus on the auxiliary date
  * Alt+P: focus on the payee / description field
  * Control+Minus: previous day on the main date
  * Control+Plus: next day on the main date
  * Control+Page Up: same day previous month on the main date
  * Control+Plus Down: same day next month on the main date
  * Shift+Control+Minus: previous day on the auxiliary date
  * Shift+Control+Plus: next day on the auxiliary date
  * Shift+Control+Page Up: same day previous month on the auxiliary date
  * Shift+Control+Plus Down: same day next month on the auxiliary date
* While any of the date fields is focused:
  * Minus / Underscore: previous day
  * Plus / Equals: next day
  * Page Up: same day previous month
  * Page Down: same day next month
  * Home: beginning of month
  * End: end of month
  * Alt+Down: drop down a calendar picker
* While the calendar picker of one of the dates is focused:
  * Same control keys for date selection
  * Arrow keys: move around the calendar
  * Space: select the day framed by the dotted line
  * Enter: confirm and closes the popup
  * Alt+Up: hide the calendar picker
* While the transaction state button is focused:
  * Space: cycle through the different states
