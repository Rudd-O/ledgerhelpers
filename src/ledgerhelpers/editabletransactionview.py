#!/usr/bin/python3
# coding: utf-8

from gi.repository import GObject
import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk
from gi.repository import Gtk

import ledgerhelpers as h
import ledgerhelpers.legacy_needsledger as hln
from ledgerhelpers import gui
from ledgerhelpers.dateentry import DateEntry
from ledgerhelpers.transactionstatebutton import TransactionStateButton


class EditableTransactionView(Gtk.Grid):

    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_LAST, None, ()),
        'payee-focus-out-event': (GObject.SIGNAL_RUN_LAST, None, ()),
        'payee-changed': (GObject.SIGNAL_RUN_LAST, None, ()),
    }

    css = b"""
editabletransactionview {
  border: 1px @borders inset;
  background: #fff;
}

editabletransactionview grid {
  border: none;
}

editabletransactionview entry {
  background: transparent;
  border: none;
}

editabletransactionview button {
  background: transparent;
  border: 1px solid transparent;
}
"""

    def __init__(self):
        gui.add_css(self.css)
        Gtk.Grid.__init__(self)
        self.set_column_spacing(0)

        self._postings_modified = False

        row = 0

        container = Gtk.Grid()
        container.set_hexpand(False)
        container.set_column_spacing(0)

        self.when = DateEntry()
        self.when.set_activates_default(True)
        self.when.set_hexpand(False)
        container.attach(self.when, 0, 0, 1, 1)
        self.when.connect("changed", self.child_changed)

        self.clearing_when = DateEntry()
        self.clearing_when.set_activates_default(True)
        self.clearing_when.set_hexpand(False)
        self.clearing_when.follow(self.when)
        container.attach(self.clearing_when, 1, 0, 1, 1)
        self.clearing_when.connect("changed", self.child_changed)

        self.clearing = TransactionStateButton()
        container.attach(self.clearing, 2, 0, 1, 1)
        self.clearing.connect("clicked", self.child_changed)

        self.payee = gui.EagerCompletingEntry()
        self.payee.set_hexpand(True)
        self.payee.set_activates_default(True)
        self.payee.set_size_request(300, -1)
        self.payee.set_placeholder_text(
            "Payee or description (type for completion)"
        )
        container.attach(self.payee, 3, 0, 1, 1)
        self.payee.connect("changed", self.payee_changed)
        self.payee.connect("changed", self.child_changed)
        self.payee.connect("focus-out-event", self.payee_focused_out)

        container.set_focus_chain(
            [self.when, self.clearing_when, self.clearing, self.payee]
        )

        container_evbox = Gtk.EventBox()
        container_evbox.add(container)
        self.attach(container_evbox, 0, row, 1, 1)

        row += 1

        self.lines_grid = Gtk.Grid()
        self.lines_grid.set_column_spacing(0)

        lines_evbox = Gtk.EventBox()
        lines_evbox.add(self.lines_grid)
        self.attach(lines_evbox, 0, row, 1, 1)

        self.lines = []
        self.accounts_for_completion = Gtk.ListStore(GObject.TYPE_STRING)
        self.payees_for_completion = Gtk.ListStore(GObject.TYPE_STRING)
        self.add_line()

        for x in container_evbox, lines_evbox:
            x.connect("key-press-event", self.handle_keypresses)
            x.add_events(Gdk.EventMask.KEY_PRESS_MASK)

    def handle_keypresses(self, obj, ev):
        if (
            ev.state & Gdk.ModifierType.CONTROL_MASK and
            (ev.keyval in (
                Gdk.KEY_plus, Gdk.KEY_KP_Add,
                Gdk.KEY_equal, Gdk.KEY_KP_Equal,
                Gdk.KEY_minus, Gdk.KEY_KP_Subtract, Gdk.KEY_underscore,
                Gdk.KEY_Page_Up, Gdk.KEY_KP_Page_Up,
                Gdk.KEY_Page_Down, Gdk.KEY_KP_Page_Down,
            ))
        ):
            if ev.state & Gdk.ModifierType.SHIFT_MASK:
                return self.clearing_when._on_entry__key_press_event(obj, ev)
            else:
                return self.when._on_entry__key_press_event(obj, ev)

        if (ev.state & Gdk.ModifierType.MOD1_MASK):
            keybobjects = {
                Gdk.KEY_t: self.when,
                Gdk.KEY_l: self.clearing_when,
                Gdk.KEY_p: self.payee,
            }
            for keyval, obj in list(keybobjects.items()):
                if ev.keyval == keyval:
                    obj.grab_focus()
                    return True

    def set_transaction_date(self, date):
        self.when.set_date(date)

    def set_accounts_for_completion(self, account_list):
        accounts = Gtk.ListStore(GObject.TYPE_STRING)
        [accounts.append((str(a),)) for a in account_list]
        for account, unused_amount in self.lines:
            account.get_completion().set_model(accounts)
        self.accounts_for_completion = accounts

    def set_payees_for_completion(self, payees_list):
        payees = Gtk.ListStore(GObject.TYPE_STRING)
        [payees.append((a,)) for a in payees_list]
        self.payee.get_completion().set_model(payees)
        self.payees_for_completion = payees

    def handle_data_changes(self, widget, unused_eventfocus):
        numlines = len(self.lines)
        for n, (account, amount) in reversed(list(enumerate(self.lines))):
            if n + 1 == numlines:
                continue
            p = amount.get_amount_and_price_formatted()
            if not account.get_text().strip() and not p:
                self.remove_line(n)
        last_account = self.lines[-1][0]
        last_amount = self.lines[-1][1]
        a, p = last_amount.get_amount_and_price()
        if (a or p) and last_account.get_text().strip():
            self.add_line()
        acctswidgets = dict((w[0], n) for n, w in enumerate(self.lines))
        if widget in acctswidgets:
            # If the account in the account widget has an associated
            # default commodity, then we set the default commodity of the
            # amount widget to the commodity for the account.
            account = widget.get_text().strip()
            amountwidget = self.lines[acctswidgets[widget]][1]
            c = self._get_default_commodity(account)
            if c:
                amountwidget.set_default_commodity(c)
        amtwidgets = dict((w[1], n) for n, w in enumerate(self.lines))
        if widget in amtwidgets:
            # If the amount widget has an amount, and the account associated
            # with it does not have a default commodity, and the widget itself
            # has a default commodity that differs from its current amount's
            # commodity, then we set the default commodity of the amount widget
            # to match the commodity of the amount entered in it.
            # This is extremely useful when clients of this data entry grid
            # are autofilling this grid, but haven't yet given us a default
            # commodity getter to discover account commodities.
            if widget.get_amount():
                currdef = widget.get_default_commodity()
                currcom = widget.get_amount().commodity
                accountwidget = self.lines[amtwidgets[widget]][0]
                account = accountwidget.get_text().strip()
                c = self._get_default_commodity(account)
                if not c and str(currdef) != str(currcom):
                    widget.set_default_commodity(currcom)
        if widget in [x[0] for x in self.lines] + [x[1] for x in self.lines]:
            self._postings_modified = True

    def set_default_commodity_getter(self, getter):
        """Records the new commodity getter.

        A getter is a callable that takes one account name and returns
        one commodity to be used as default for that account.  If the
        getter cannot find a default commodity, it must return None.
        """
        self._default_commodity_getter = getter
        for line in self.lines:
            accountwidget = line[0]
            amountwidget = line[1]
            account = accountwidget.get_text().strip()
            c = self._get_default_commodity(account)
            if c:
                amountwidget.set_default_commodity(c)

    def _get_default_commodity(self, account_name):
        getter = getattr(self, "_default_commodity_getter", None)
        if getter:
            return getter(account_name)

    def child_changed(self, w, unused=None):
        self.handle_data_changes(w, None)
        self.emit("changed")

    def payee_changed(self, unused_w, unused=None):
        self.emit("payee-changed")

    def payee_focused_out(self, unused_w, unused=None):
        self.emit("payee-focus-out-event")

    def get_payee_text(self):
        return self.payee.get_text()

    def remove_line(self, number):
        account, amount = self.lines[number]
        account_is_focus = account.is_focus()
        amount_is_focus = amount.is_focus()
        for hid in account._handler_ids:
            account.disconnect(hid)
        for hid in amount._handler_ids:
            amount.disconnect(hid)
        self.lines.pop(number)
        self.lines_grid.remove_row(number)
        try:
            account, amount = self.lines[number]
        except IndexError:
            account, amount = self.lines[number - 1]
        if account_is_focus:
            account.grab_focus()
        if amount_is_focus:
            amount.grab_focus()

    def postings_modified(self):
        return self._postings_modified

    def postings_empty(self):
        return (
            len(self.lines) < 2 and
            not self.lines[0][0].get_text() and
            not self.lines[0][0].get_text()
        )

    def _clear_postings(self):
        while len(self.lines) > 1:
            self.remove_line(0)
        self.lines[0][0].set_text("")
        self.lines[0][1].set_amount_and_price(None, None)

    def clear(self):
        self._clear_postings()
        self.payee.set_text("")
        self._postings_modified = False

    def set_clearing(self, clearingstate):
        self.clearing.set_state(clearingstate)

    def replace_postings(self, transactionpostings):
        """Replace postings with a list of TransactionPosting."""
        self._clear_postings()
        for n, tp in enumerate(transactionpostings):
            self.add_line()
            self.lines[n][0].set_text(tp.account)
            self.lines[n][1].set_text(tp.amount)
        self._postings_modified = False

    def add_line(self):
        account = gui.EagerCompletingEntry()
        account.set_hexpand(True)
        account.set_width_chars(40)
        account.set_activates_default(True)
        account.get_completion().set_model(self.accounts_for_completion)
        account.set_placeholder_text(
            "Account (type for completion)"
        )
        hid3 = account.connect("changed", self.child_changed)
        account._handler_ids = [hid3]

        amount = gui.LedgerAmountWithPriceEntry(display=False)
        amount.set_activates_default(True)
        amount.set_placeholder_text("Amount")
        hid3 = amount.connect("changed", self.child_changed)
        amount._handler_ids = [hid3]

        row = len(self.lines)

        if amount.display:
            amount.remove(amount.display)
            self.lines_grid.attach(amount.display, 0, row, 1, 1)
            amount.remove(amount.entry)
            self.lines_grid.attach(amount.entry, 1, row, 1, 1)
        else:
            amount.remove(amount.entry)
            self.lines_grid.attach(amount.entry, 0, row, 1, 1)
        self.lines_grid.attach(account, 2, row, 1, 1)

        account.show()
        amount.show()

        self.lines.append((account, amount))

    def title_grab_focus(self):
        self.payee.grab_focus()

    def lines_grab_focus(self):
        for account, amount in self.lines:
            if not account.get_text().strip():
                account.grab_focus()
                return
            if not amount.get_amount_and_price_formatted():
                amount.grab_focus()
                return
        else:
            if self.lines:
                self.lines[0][1].grab_focus()
            pass

    def get_data_for_transaction_record(self):
        title = self.payee.get_text().strip()
        date = self.when.get_date()
        clearing_state = self.clearing.get_state_char()
        clearing_when = self.clearing_when.get_date()

        def get_entries():
            entries = []
            for account, amount in self.lines:
                account = account.get_text().strip()
                p = amount.get_amount_and_price_formatted()
                if account or p:
                    entries.append((account, p))
            return entries

        accountamounts = [(x, y) for x, y in get_entries()]
        return title, date, clearing_when, clearing_state, accountamounts

    def validate(self, grab_focus=False):
        """Raises ValidationError if the transaction is not valid."""
        title, date, auxdate, statechar, lines = (
            self.get_data_for_transaction_record()
        )
        if not title:
            if grab_focus:
                self.payee.grab_focus()
            raise h.TransactionInputValidationError(
                "Transaction title cannot be empty"
            )
        if len(lines) < 2:
            if grab_focus:
                self.lines_grab_focus()
            raise h.TransactionInputValidationError(
                "Enter at least two transaction entries"
            )
        try:
            hln.generate_record(title, date, auxdate, statechar, lines,
                              validate=True)
        except hln.LedgerParseError as e:
            raise h.TransactionInputValidationError(str(e))


EditableTransactionView.set_css_name("editabletransactionview")
