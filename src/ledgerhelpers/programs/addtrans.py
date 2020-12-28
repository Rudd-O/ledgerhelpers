#!/usr/bin/python3

import argparse
import datetime
import logging
import traceback

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

import ledgerhelpers as common
from ledgerhelpers import gui
from ledgerhelpers import journal
from ledgerhelpers.programs import common as common_programs
import ledgerhelpers.editabletransactionview as ed


ASYNC_LOAD_MESSAGE = "Loading completion data from your ledger..."
ASYNC_LOADING_ACCOUNTS_MESSAGE = (
    "Loading account and commodity data from your ledger..."
)


class AddTransWindow(Gtk.Window, gui.EscapeHandlingMixin):

    def __init__(self):
        Gtk.Window.__init__(self, title="Add transaction")
        self.set_border_width(12)

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(12)
        self.add(grid)

        row = 0

        self.transholder = ed.EditableTransactionView()
        grid.attach(self.transholder, 0, row, 2, 1)

        row += 1

        self.transaction_view = gui.LedgerTransactionView()
        self.transaction_view.set_vexpand(True)
        self.transaction_view.get_accessible().set_name("Transaction preview")
        grid.attach(self.transaction_view, 0, row, 2, 1)

        row += 1

        self.status = Gtk.Label()
        self.status.set_line_wrap(True)
        self.status.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.status.set_hexpand(True)
        grid.attach(self.status, 0, row, 1, 1)

        button_box = Gtk.ButtonBox()
        button_box.set_layout(Gtk.ButtonBoxStyle.END)
        button_box.set_spacing(12)
        button_box.set_hexpand(False)
        self.close_button = Gtk.Button(stock=Gtk.STOCK_CLOSE)
        button_box.add(self.close_button)
        self.add_button = Gtk.Button(stock=Gtk.STOCK_ADD)
        button_box.add(self.add_button)
        grid.attach(button_box, 1, row, 1, 1)
        self.add_button.set_can_default(True)
        self.add_button.grab_default()


class AddTransApp(AddTransWindow, gui.EscapeHandlingMixin):

    logger = logging.getLogger("addtrans")
    internal_parsing = []

    def __init__(self, journal, preferences):
        AddTransWindow.__init__(self)
        self.journal = journal
        self.preferences = preferences
        self.successfully_loaded_accounts_and_commodities = False

        self.accounts = []
        self.commodities = dict()
        self.internal_parsing = []
        self.payees = []

        self.activate_escape_handling()

        self.close_button.connect("clicked",
                                  lambda _: self.emit('delete-event', None))
        self.add_button.connect("clicked",
                                lambda _: self.process_transaction())
        date = self.preferences.get("last_date", datetime.date.today())
        self.transholder.set_transaction_date(date)
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
        self.status.set_text(ASYNC_LOAD_MESSAGE)

        self.connect("delete-event", lambda _, _a: self.save_preferences())
        self.reload_completion_data()

    def reload_completion_data(self):
        gui.g_async(
            lambda: self.journal.internal_parsing(),
            lambda payees: self.internal_parsing_loaded(payees),
            self.journal_load_failed,
        )

    def internal_parsing_loaded(self, internal_parsing):
        self.internal_parsing = internal_parsing
        gui.g_async(
            lambda: self.journal.all_payees(),
            lambda payees: self.all_payees_loaded(payees),
            self.journal_load_failed,
        )

    def all_payees_loaded(self, payees):
        self.payees = payees
        self.transholder.set_payees_for_completion(self.payees)
        gui.g_async(
            lambda: self.journal.accounts_and_last_commodity_for_account(),
            lambda r: self.accounts_and_last_commodities_loaded(*r),
            self.journal_load_failed,
        )
        if self.status.get_text() == ASYNC_LOAD_MESSAGE:
            self.status.set_text(ASYNC_LOADING_ACCOUNTS_MESSAGE)

    def accounts_and_last_commodities_loaded(self, accounts, last_commos):
        self.accounts = accounts
        self.commodities = last_commos
        self.transholder.set_accounts_for_completion(self.accounts)
        self.transholder.set_default_commodity_getter(
            self.get_commodity_for_account
        )
        self.successfully_loaded_accounts_and_commodities = True
        if self.status.get_text() == ASYNC_LOADING_ACCOUNTS_MESSAGE:
            self.status.set_text("")

    def journal_load_failed(self, e):
        traceback.print_exc()
        gui.FatalError(
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
        ts = journal.transactions_with_payee(
            autofill_text,
            self.internal_parsing,
            case_sensitive=False
        )
        if not ts:
            return
        return self.autofill_transaction_view(transaction_view, ts[-1])

    def autofill_transaction_view(self, transaction_view, transaction):
        transaction_view.replace_postings(transaction.postings)
        transaction_view.set_clearing(transaction.state)

    def update_transaction_view(self, unused_ignored=None):
        self.update_validation()
        k = self.transholder.get_data_for_transaction_record
        title, date, clear, statechar, lines = k()
        self.transaction_view.generate_record(
             title, date, clear, statechar, lines
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
        self.journal.add_text_to_file(text)
        self.reset_after_save()

    def reset_after_save(self):
        self.transholder.clear()
        self.transholder.title_grab_focus()
        self.status.set_text("Transaction saved")
        self.reload_completion_data()

    def save_preferences(self):
        if not self.successfully_loaded_accounts_and_commodities:
            return
        self.preferences["default_to_clearing"] = (
            self.transholder.clearing.get_state() !=
            self.transholder.clearing.STATE_UNCLEARED
        )
        if self.transholder.when.get_date() in (datetime.date.today(), None):
            del self.preferences["last_date"]
        else:
            self.preferences["last_date"] = (
                self.transholder.when.get_date()
            )
        self.preferences.persist()


def get_argparser():
    parser = argparse.ArgumentParser(
        'Add new transactions to your Ledger file',
        parents=[common_programs.get_common_argparser()]
    )
    parser.add_argument('--debug', dest='debug', action='store_true',
                        help='activate debugging')
    return parser


def main():
    args = get_argparser().parse_args()
    common.enable_debugging(args.debug)

    GObject.threads_init()

    journal, s = gui.load_journal_and_settings_for_gui(
        ledger_file=args.file,
        price_file=args.pricedb,
    )
    klass = AddTransApp
    win = klass(journal, s)
    win.connect("delete-event", Gtk.main_quit)
    GObject.idle_add(win.show_all)
    Gtk.main()
