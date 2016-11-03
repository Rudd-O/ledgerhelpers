#!/usr/bin/env python

import datetime

from gi.repository import GObject
import gi; gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from gi.repository import Pango

import ledgerhelpers as common
import ledgerhelpers.editabletransactionview as ed


class AddTransWindow(Gtk.Window, common.EscapeHandlingMixin):

    def __init__(self):
        Gtk.Window.__init__(self, title="Add transaction")
        self.set_border_width(12)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(8)
        self.add(grid)

        row = 0

        self.transholder = ed.EditableTransactionView()
        self.transholder.set_column_spacing(8)
        self.transholder.set_row_spacing(8)
        grid.attach(self.transholder, 0, row, 2, 1)

        row += 1

        self.transaction_view = common.LedgerTransactionView()
        self.transaction_view.set_vexpand(True)
        grid.attach(self.transaction_view, 0, row, 2, 1)

        row += 1

        self.status = Gtk.Label()
        self.status.set_line_wrap(True)
        self.status.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.status.set_hexpand(True)
        grid.attach(self.status, 0, row, 2, 1)

        row += 1

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.END)
        button_box.set_spacing(12)
        button_box.set_hexpand(True)
        self.close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        button_box.add(self.close_button)
        self.add_button = Gtk.Button(stock=Gtk.STOCK_ADD)
        button_box.add(self.add_button)
        grid.attach(button_box, 1, row, 1, 1)
        self.add_button.set_can_default(True)
        self.add_button.grab_default()


class AddTransApp(AddTransWindow, common.EscapeHandlingMixin):

    def __init__(self, journal, preferences):
        AddTransWindow.__init__(self)
        self.journal = journal
        self.preferences = preferences
        self.successfully_loaded_accounts_and_commodities = False

        self.accounts = []
        self.commodities = dict()
        self.payees = []

        self.activate_escape_handling()

        self.journal.connect("loaded", self.journal_loaded)
        self.journal.connect("load-failed", self.journal_load_failed)
        self.close_button.connect("clicked",
                                  lambda _: self.emit('delete-event', None))
        self.add_button.connect("clicked",
                                lambda _: self.process_transaction())
        self.transholder.set_transaction_date(
            self.preferences.get("last_date", datetime.date.today())
        )
        self.transholder.connect(
            "payee-changed",
            self.payee_changed
        )
        self.transholder.connect(
            "changed",
            self.update_transaction_view
        )

        self.add_button.set_sensitive(False)
        self.transholder.title_grab_focus()
        self.journal.reread_files_async()
        self.connect("delete-event", lambda _, _a: self.save_preferences())

    @common.debug_time
    def journal_loaded(self, journal):
        accts, commodities = self.journal.accounts_and_last_commodities()
        payees = self.journal.all_payees()

        self.accounts = accts
        self.commodities = commodities
        self.payees = payees

        self.transholder.set_payees_for_completion(payees)
        self.transholder.set_accounts_for_completion(accts)
        self.transholder.set_default_commodity_getter(
            self.get_commodity_for_account
        )
        self.successfully_loaded_accounts_and_commodities = True

    def journal_load_failed(self, journal, e):
        common.FatalError(
            "Add transaction loading failed",
            "An unexpected error took place:\n%s" % e,
        )
        self.emit('delete-event', None)

    def get_commodity_for_account(self, account_name):
        try:
            return self.commodities[account_name]
        except KeyError:
            pass

    def payee_changed(self, emitter=None):
        if emitter.postings_modified() and not emitter.postings_empty():
            return
        text = emitter.get_payee_text()
        self.try_autofill(emitter, text)

    def try_autofill(self, transaction_view, autofill_text):
        ts = self.journal.transactions_with_payee(
            autofill_text,
            case_sensitive=False
        )
        if not ts:
            return
        return self.autofill_transaction_view(transaction_view, ts[-1])

    def autofill_transaction_view(self, transaction_view, transaction):
        transaction_view.replace_postings(transaction.postings)
        transaction_view.set_clearing(bool(transaction.state))

    def update_transaction_view(self, ignored=None):
        self.update_validation()
        k = self.transholder.get_data_for_transaction_record
        title, date, clear, lines = k()
        self.transaction_view.generate_record(
             title, date, clear, lines
         )

    def update_validation(self, grab_focus=False):
        try:
            self.transholder.validate(grab_focus=grab_focus)
            self.status.set_text("")
            self.add_button.set_sensitive(True)
            return True
        except common.TransactionInputValidationError as e:
            self.status.set_text(str(e))
            self.add_button.set_sensitive(False)
            return False

    def process_transaction(self):
        if not self.update_validation(True):
            return
        buf = self.transaction_view.get_buffer()
        text = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)
        self.save_transaction(text)
        self.reset_after_save()

    def save_transaction(self, text):
        self.journal.add_text_to_file_async(text)

    def reset_after_save(self):
        self.transholder.clear()
        self.transholder.title_grab_focus()
        self.status.set_text("Transaction saved")

    def save_preferences(self):
        if not self.successfully_loaded_accounts_and_commodities:
            return
        self.preferences["default_to_clearing"] = (
            self.transholder.clearing.get_active()
        )
        if self.transholder.when.get_date() == datetime.date.today():
            del self.preferences["last_date"]
        elif not self.transholder.when.get_date():
            del self.preferences["last_date"]
        else:
            self.preferences["last_date"] = (
                self.transholder.when.get_date()
            )
        self.preferences.persist()


def main():
    journal, s = common.load_journal_and_settings_for_gui(read_journal=False)
    klass = AddTransApp
    win = klass(journal, s)
    win.connect("delete-event", Gtk.main_quit)
    GObject.idle_add(win.show_all)
    Gtk.main()
