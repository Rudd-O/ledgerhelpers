import ledger
import ledgerhelpers
import os
import sys
import threading

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import GObject
from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import Pango


EVENT_TAB = 65289
EVENT_SHIFTTAB = 65056
EVENT_ESCAPE = 65307


_css_adjusted = {}


def g_async(func, success_func, failure_func):
    def f():
        try:
            GObject.idle_add(success_func, func())
        except BaseException as e:
            GObject.idle_add(failure_func, e)
    t = threading.Thread(target=f)
    t.setDaemon(True)
    t.start()
    return t


def add_css(css):
    # Must only ever be called at runtime, not at import time.
    global _css_adjusted
    if css not in _css_adjusted:
        style_provider = Gtk.CssProvider()
        style_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            style_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    _css_adjusted[css] = True


def FatalError(message, secondary=None, outside_mainloop=False, parent=None):
    d = Gtk.MessageDialog(
        parent,
        Gtk.DialogFlags.DESTROY_WITH_PARENT,
        Gtk.MessageType.ERROR,
        Gtk.ButtonsType.CLOSE,
        message,
    )
    if secondary:
        d.format_secondary_text(secondary)
    d.run()


def cannot_start_dialog(msg):
    return FatalError("Cannot start program", msg, outside_mainloop=True)


class EagerCompletion(Gtk.EntryCompletion):
    """Completion class that substring matches within a builtin ListStore."""

    def __init__(self, *args):
        Gtk.EntryCompletion.__init__(self, *args)
        self.set_model(Gtk.ListStore(GObject.TYPE_STRING))
        self.set_match_func(self.iter_points_to_matching_entry)
        self.set_text_column(0)
        self.set_inline_completion(True)

    def iter_points_to_matching_entry(self, c, k, i, u=None):
        model = self.get_model()
        acc = model.get(i, 0)[0].lower()
        if k.lower() in acc:
            return True
        return False


def load_journal_and_settings_for_gui(price_file_mandatory=False):
    try:
        ledger_file = ledgerhelpers.find_ledger_file()
    except Exception, e:
        cannot_start_dialog(str(e))
        sys.exit(4)
    try:
        price_file = ledgerhelpers.find_ledger_price_file()
    except ledgerhelpers.LedgerConfigurationError, e:
        if price_file_mandatory:
            cannot_start_dialog(str(e))
            sys.exit(4)
        else:
            price_file = None
    except Exception, e:
        cannot_start_dialog(str(e))
        sys.exit(4)
    try:
        from ledgerhelpers.journal import Journal
        journal = Journal.from_file(ledger_file, price_file)
    except Exception, e:
        cannot_start_dialog("Cannot open ledger file: %s" % e)
        sys.exit(5)
    s = ledgerhelpers.Settings.load_or_defaults(
        os.path.expanduser("~/.ledgerhelpers.ini")
    )
    return journal, s


def find_ledger_file_for_gui():
    try:
        ledger_file = ledgerhelpers.find_ledger_file()
        return ledger_file
    except Exception, e:
        cannot_start_dialog(str(e))
        sys.exit(4)


class EagerCompletingEntry(Gtk.Entry):
    """Entry that substring-matches eagerly using a builtin ListStore-based
    Completion, and also accepts defaults.
    """

    prevent_completion = False

    def __init__(self, *args):
        Gtk.Entry.__init__(self, *args)
        self.default_text = ''
        self.old_default_text = ''
        self.set_completion(EagerCompletion())

    def set_default_text(self, default_text):
        self.old_default_text = self.default_text
        self.default_text = default_text
        if not self.get_text() or self.get_text() == self.old_default_text:
            self.set_text(self.default_text)


class LedgerAmountEntry(Gtk.Grid):

    __gsignals__ = {
        'changed': (GObject.SIGNAL_RUN_LAST, None, ())
    }

    def show(self):
        Gtk.Grid.show(self)
        self.entry.show()
        if self.display:
            self.display.show()

    def do_changed(self):
        pass

    def set_placeholder_text(self, text):
        self.entry.set_placeholder_text(text)

    def __init__(self, display=True):
        Gtk.Grid.__init__(self)
        self.amount = None
        self.entry = Gtk.Entry()
        self.entry.set_width_chars(8)
        if display:
            self.display = Gtk.Label()
        else:
            self.display = None
        self.entry.set_alignment(1.0)
        self.attach(self.entry, 0, 0, 1, 1)
        if self.display:
            self.attach(self.display, 1, 0, 1, 1)
            self.display.set_halign(Gtk.Align.END)
            self.display.set_justify(Gtk.Justification.RIGHT)
        self.set_column_spacing(4)
        self.donotreact = False
        self.entry.connect("changed", self.entry_changed)
        self.set_default_commodity(ledger.Amount("$ 1").commodity)
        self.set_activates_default = self.entry.set_activates_default

    def get_default_commodity(self):
        return self.default_commodity

    def set_default_commodity(self, commodity):
        if isinstance(commodity, ledger.Amount):
            commodity = commodity.commodity
        self.default_commodity = commodity
        self.emit("changed")

    def is_focus(self):
        return self.entry.is_focus()

    def grab_focus(self):
        self.entry.grab_focus()

    def get_amount(self):
        return self.amount

    def set_amount(self, amount, skip_entry_update=False):
        self.amount = amount
        if self.display:
            self.display.set_text(str(amount) if amount is not None else "")
        self.donotreact = True
        if not skip_entry_update:
            self.entry.set_text(str(amount) if amount is not None else "")
        self.donotreact = False
        self.emit("changed")

    def set_text(self, text):
        self.entry.set_text(text)

    def _adjust_entry_size(self, w):
        text = w.get_text()
        w.set_width_chars(max([8, len(text)]))

    def entry_changed(self, w, *args):
        self._adjust_entry_size(w)

        if self.donotreact:
            return

        text = self.entry.get_text()

        try:
            p = ledger.Amount(text)
        except ArithmeticError:
            self.set_amount(None, True)
            self.emit("changed")
            return

        if not str(p.commodity):
            p.commodity = self.default_commodity
        if str(p):
            self.set_amount(p, True)
        else:
            self.set_amount(None, True)

        self.emit("changed")


class LedgerAmountWithPriceEntry(LedgerAmountEntry):

    def __init__(self, display=True):
        self.price = None
        LedgerAmountEntry.__init__(self, display=display)

    def get_amount_and_price(self):
        return self.amount, self.price

    def get_amount_and_price_formatted(self):
        if self.amount and self.price:
            return str(self.amount) + " " + self.price.strip()
        elif self.amount:
            return str(self.amount)
        elif self.price:
            return self.price
        else:
            return ""

    def set_amount_and_price(self, amount, price, skip_entry_update=False):
        self.amount = amount
        self.price = price
        p = [
            str(amount if amount is not None else "").strip(),
            str(price if price is not None else "").strip(),
        ]
        p = [x for x in p if x]
        concat = " ".join(p)
        if self.display:
            self.display.set_text(concat)
        self.donotreact = True
        if not skip_entry_update:
            self.entry.set_text(concat)
        self.donotreact = False

    def entry_changed(self, w, *args):
        self._adjust_entry_size(w)

        if self.donotreact:
            return

        text = self.entry.get_text()
        i = text.find("@")
        if i != -1:
            price = text[i:] if text[i:] else None
            text = text[:i]
        else:
            price = None

        try:
            p = ledger.Amount(text)
        except ArithmeticError:
            self.set_amount_and_price(None, price, True)
            self.emit("changed")
            return

        if not str(p.commodity):
            p.commodity = self.default_commodity
        if str(p):
            self.set_amount_and_price(p, price, True)
        else:
            self.set_amount_and_price(None, price, True)

        self.emit("changed")


class EditableTabFocusFriendlyTextView(Gtk.TextView):

    def __init__(self, *args):
        Gtk.TextView.__init__(self, *args)
        self.connect("key-press-event", self.handle_tab)

    def handle_tab(self, widget, event):
        if event.keyval == EVENT_TAB:
            widget.get_toplevel().child_focus(Gtk.DirectionType.TAB_FORWARD)
            return True
        elif event.keyval == EVENT_SHIFTTAB:
            widget.get_toplevel().child_focus(Gtk.DirectionType.TAB_BACKWARD)
            return True
        return False


class LedgerTransactionView(Gtk.Box):

    css = """
ledgertransactionview {
  border: 1px @borders inset;
}
"""

    def __init__(self, *args):
        add_css(self.css)
        Gtk.Box.__init__(self)
        self.textview = EditableTabFocusFriendlyTextView(*args)
        self.textview.override_font(
            Pango.font_description_from_string('monospace')
        )
        self.textview.set_border_width(12)
        self.textview.set_hexpand(True)
        self.textview.set_vexpand(True)
        self.add(self.textview)
        self.textview.get_buffer().set_text(
            "# A live preview will appear here as you input data."
        )

    def get_buffer(self):
        return self.textview.get_buffer()

    def generate_record(self, *args):
        lines = ledgerhelpers.generate_record(*args)
        self.textview.get_buffer().set_text("\n".join(lines))


LedgerTransactionView.set_css_name("ledgertransactionview")


class EscapeHandlingMixin(object):

    escape_handling_suspended = False

    def activate_escape_handling(self):
        self.connect("key-press-event", self.handle_escape)

    def suspend_escape_handling(self):
        self.escape_handling_suspended = True

    def resume_escape_handling(self):
        self.escape_handling_suspended = False

    def handle_escape(self, window, event, user_data=None):
        if (
            not self.escape_handling_suspended and
            event.keyval == EVENT_ESCAPE
        ):
            self.emit('delete-event', None)
            return True
        return False
