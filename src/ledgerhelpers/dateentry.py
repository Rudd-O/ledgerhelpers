#!/usr/bin/env python

# This code is imported straight from the Kiwi codebase, and ported to work
# with GTK+ 3.x.
#
# The original source code is here:
# http://doc.stoq.com.br/api/kiwi/_modules/kiwi/ui/dateentry.html
#
# The original program was provided under the LGPL 2.1 or later license terms.
# As such, this program reuses it freely, linking it with the program is
# permitted and should be no issue.

import datetime

from gi.repository import GObject
import gi; gi.require_version("Gdk", "3.0")
import gi; gi.require_version("Gtk", "3.0")
from gi.repository import Gdk
from gi.repository import Gtk

from ledgerhelpers import format_date, parse_date


ValueUnset = "WARFQnesartdhaersthaurwstbk345gpfsar8da"


def prev_month(date):
    if date.month == 1:
        return datetime.date(date.year - 1, 12, date.day)
    else:
        day = date.day
        while True:
            try:
                return datetime.date(date.year, date.month - 1, day)
            except ValueError:
                day = day - 1


def next_month(date):
    if date.month == 12:
        return datetime.date(date.year + 1, 1, date.day)
    else:
        day = date.day
        while True:
            try:
                return datetime.date(date.year, date.month + 1, day)
            except ValueError:
                day = day - 1


def beginning_of_month(date):
    return datetime.date(date.year, date.month, 1)


def end_of_month(date):
    if date.month == 12:
        date = datetime.date(date.year + 1, 1, 1)
    else:
        date = datetime.date(date.year, date.month + 1, 1)
    return date - datetime.timedelta(1)


def prev_day(date):
    return date - datetime.timedelta(1)


def next_day(date):
    return date + datetime.timedelta(1)


def according_to_keyval(keyval, date, skip=""):
    if (keyval in (Gdk.KEY_Page_Up, Gdk.KEY_KP_Page_Up)):
        if date:
            return True, prev_month(date)
        else:
            return True, None
    if (keyval in (Gdk.KEY_Page_Down, Gdk.KEY_KP_Page_Down)):
        if date:
            return True, next_month(date)
        else:
            return True, None
    if (
        keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract) and
        "minus" not in skip
    ):
        if date:
            return True, prev_day(date)
        else:
            return True, None
    if (keyval in (Gdk.KEY_plus, Gdk.KEY_KP_Add)):
        if date:
            return True, next_day(date)
        else:
            return True, None
    if (keyval in (Gdk.KEY_Home, Gdk.KEY_KP_Home)):
        if date:
            return True, beginning_of_month(date)
        else:
            return True, None
    if (keyval in (Gdk.KEY_End, Gdk.KEY_KP_End)):
        if date:
            return True, end_of_month(date)
        else:
            return True, None
    return False, None


class _DateEntryPopup(Gtk.Window):

    __gsignals__ = {
        'date-selected': (
            GObject.SIGNAL_RUN_LAST,
            None,
            (object,)
        )
    }

    def __init__(self, dateentry):
        Gtk.Window.__init__(self, Gtk.WindowType.POPUP)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect('key-press-event', self._on__key_press_event)
        self.connect('button-press-event', self._on__button_press_event)
        self._dateentry = dateentry

        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self.add(frame)
        frame.show()

        vbox = Gtk.VBox()
        vbox.set_border_width(12)
        frame.add(vbox)
        vbox.show()
        self._vbox = vbox

        self.calendar = Gtk.Calendar()
        self.calendar.connect('day-selected-double-click',
                              self._on_calendar__day_selected_double_click)
        self.calendar.connect('day-selected',
                              self._on_calendar__day_selected_double_click)
        vbox.pack_start(self.calendar, False, False, 0)
        self.calendar.show()

        buttonbox = Gtk.HButtonBox()
        buttonbox.set_border_width(12)
        buttonbox.set_layout(Gtk.ButtonBoxStyle.SPREAD)
        vbox.pack_start(buttonbox, False, False, 0)
        buttonbox.show()

        for label, callback in [('_Today', self._on_today__clicked),
                                ('_Close', self._on_close__clicked)]:
            button = Gtk.Button(label, use_underline=True)
            button.connect('clicked', callback)
            buttonbox.pack_start(button, False, False, 0)
            button.show()

        self.set_resizable(False)
        self.set_screen(dateentry.get_screen())

        self.realize()
        self.height = self._vbox.size_request().height

    def _on_calendar__day_selected_double_click(self, calendar):
        self.emit('date-selected', self.get_date())

    def _on__button_press_event(self, window, event):
        # If we're clicking outside of the window close the popup
        hide = False

        # Also if the intersection of self and the event is empty, hide
        # the calendar
        if (tuple(self.get_allocation().intersect(
            Gdk.Rectangle(x=int(event.x), y=int(event.y),
                          width=1, height=1))) == (0, 0, 0, 0)):
            hide = True

        # Toplevel is the window that received the event, and parent is the
        # calendar window. If they are not the same, means the popup should
        # be hidden. This is necessary for when the event happens on another
        # widget
        toplevel = event.get_window().get_toplevel()
        parent = self.calendar.get_parent_window()
        if toplevel != parent:
            hide = True

        if hide:
            self.popdown()

    def _on__key_press_event(self, window, event):
        """
        Mimics Combobox behavior

        Escape, Enter or Alt+Up: Close
        Space: Select
        """
        keyval = event.keyval
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        if (keyval == Gdk.KEY_Escape or
            keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) or
            ((keyval == Gdk.KEY_Up or keyval == Gdk.KEY_KP_Up) and
             state == Gdk.ModifierType.MOD1_MASK)):
            self.popdown()
            return True
        processed, new_date = according_to_keyval(keyval, self.get_date())
        if processed and new_date:
            self.set_date(new_date)
        return processed

    def _on_select__clicked(self, button):
        self.emit('date-selected', self.get_date())

    def _on_close__clicked(self, button):
        self.popdown()

    def _on_today__clicked(self, button):
        self.set_date(datetime.date.today())

    def _popup_grab_window(self):
        activate_time = 0L
        win = self.get_window()
        result = Gdk.pointer_grab(win, True, (
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK),
            None, None, activate_time
        )
        if result == 0:
            if Gdk.keyboard_grab(self.get_window(), True, activate_time) == 0:
                return True
            else:
                self.get_window().get_display().pointer_ungrab(activate_time)
                print "ungrabbing"
                return False
        print "fuck"
        return False

    def _get_position(self):
        self.realize()
        calendar = self

        sample = self._dateentry

        # We need to fetch the coordinates of the entry window
        # since comboentry itself does not have a window
        origin = sample.entry.get_window().get_origin()
        x, y = origin.x, origin.y
        width = calendar.size_request().width
        height = self.height

        screen = sample.get_screen()
        monitor_num = screen.get_monitor_at_window(sample.get_window())
        monitor = screen.get_monitor_geometry(monitor_num)

        if x < monitor.x:
            x = monitor.x
        elif x + width > monitor.x + monitor.width:
            x = monitor.x + monitor.width - width

        alloc = sample.get_allocation()

        if y + alloc.height + height <= monitor.y + monitor.height:
            y += alloc.height
        elif y - height >= monitor.y:
            y -= height
        elif (monitor.y + monitor.height - (y + alloc.height) >
              y - monitor.y):
            y += alloc.height
            height = monitor.y + monitor.height - y
        else:
            height = y - monitor.y
            y = monitor.y

        return x, y, width, height

    def popup(self, date):
        """
        Shows the list of options. And optionally selects an item
        :param date: date to select
        """
        combo = self._dateentry
        if not (combo.get_realized()):
            return

        treeview = self.calendar
        if treeview.get_mapped():
            return
        toplevel = combo.get_toplevel()
        if isinstance(toplevel, Gtk.Window) and toplevel.get_group():
            toplevel.get_group().add_window(self)

        x, y, width, height = self._get_position()
        self.set_size_request(width, height)
        self.move(x, y)

        if (date is not None and date is not ValueUnset):
            self.set_date(date)
        self.grab_focus()

        if not (self.calendar.has_focus()):
            self.calendar.grab_focus()

        self.show_all()
        if not self._popup_grab_window():
            self.hide()
            return

        self.grab_add()

    def popdown(self):
        """Hides the list of options"""
        combo = self._dateentry
        if not (combo.get_realized()):
            return

        self.grab_remove()
        self.hide()

    # month in gtk.Calendar is zero-based (i.e the allowed values are 0-11)
    # datetime one-based (i.e. the allowed values are 1-12)
    # So convert between them

    def get_date(self):
        """Gets the date of the date entry
        :returns: date of the entry
        :rtype date: datetime.date
        """
        y, m, d = self.calendar.get_date()
        return datetime.date(y, m + 1, d)

    def set_date(self, date):
        """Sets the date of the date entry
        :param date: date to set
        :type date: datetime.date
        """
        self.calendar.select_month(date.month - 1, date.year)
        self.calendar.select_day(date.day)
        # FIXME: Only mark the day in the current month?
        self.calendar.clear_marks()
        self.calendar.mark_day(date.day)


@GObject.type_register
class DateEntry(Gtk.HBox):
    """I am an entry which you can input a date on.
    I make entering a date blazing fast.

    The date you input in me must be of the form YYYY-MM-DD or YYYY/MM/DD.
    These are the date formats expected by Ledger.

    In addition to the text box where you can type, I also contain a button
    with an arrow you can click, to get a popup window with a date picker
    where you can select the date.  When the text box has focus, Alt+Down
    will display the date picker popup.

    There are a number of cool combos you can use, whether in the text box
    or in the date picker popup:

    * Plus: next day
    * Minus: previous day
    * Page Up: previous month
    * Page Down : next month
    * End: end of the month
    * Home: beginning of the month

    In the date picker popup, hitting Enter, or Escape, or Alt+Up after
    selecting a date (making it blue with a click or with the Space bar)
    makes the date picker popup go away.  Clicking outside the date picker
    popup also closes it.
    """

    __gsignals__ = {
        'changed': (
            GObject.SIGNAL_RUN_LAST,
            None,
            ()
        ),
        'activate': (
            GObject.SIGNAL_RUN_LAST,
            None,
            ()
        ),
    }

    def __init__(self):
        Gtk.HBox.__init__(self)

        self._popping_down = False
        self._old_date = None

        self.entry = Gtk.Entry()
        self.entry.set_max_length(10)
        self.entry.set_width_chars(10)
        self.entry.set_overwrite_mode(True)
        self.entry.set_tooltip_text(
            self.__doc__.replace("\n    ", "\n").strip()
        )
        self.entry.connect('changed', self._on_entry__changed)
        self.entry.connect('activate', self._on_entry__activate)
        self.entry.connect('key-press-event', self._on_entry__key_press_event)
        self.entry.set_placeholder_text("Date")
        self.pack_start(self.entry, False, False, 0)
        self.entry.show()

        self._button = Gtk.ToggleButton()
        self._button.connect('scroll-event', self._on_entry__scroll_event)
        self._button.connect('toggled', self._on_button__toggled)
        self._button.set_focus_on_click(False)
        self.pack_start(self._button, False, False, 0)
        self._button.show()

        arrow = Gtk.Arrow(Gtk.ArrowType.DOWN, Gtk.ShadowType.NONE)
        self._button.add(arrow)
        arrow.show()

        self._popup = _DateEntryPopup(self)
        self._popup.connect('date-selected', self._on_popup__date_selected)
        self._popup.connect('hide', self._on_popup__hide)
        self._popup.set_size_request(-1, 24)

    def _on_entry__key_press_event(self, unused_window, event):
        keyval = event.keyval
        state = event.state & Gtk.accelerator_get_default_mod_mask()
        if (
            (keyval == Gdk.KEY_Down or keyval == Gdk.KEY_KP_Down) and
            state == Gdk.ModifierType.MOD1_MASK
        ):
            self._button.activate()
            return True

        skip_minus = ""
        if not self.get_date():
            skip_minus = "minus"
        if self.entry.get_property("cursor-position") in (4, 7):
            skip_minus = "minus"
        processed, new_date = according_to_keyval(event.keyval,
                                                  self.get_date(),
                                                  skip=skip_minus)
        if processed and new_date:
            self.set_date(new_date)
        return processed

    # Virtual methods

    def do_grab_focus(self):
        self.entry.grab_focus()

    # Callbacks

    def _on_entry__changed(self, entry):
        try:
            date = self.get_date()
        except ValueError:
            date = None
        self._changed(date)

    def _on_entry__activate(self, entry):
        self.emit('activate')

    def _on_entry__scroll_event(self, entry, event):
        if event.direction == Gdk.SCROLL_UP:
            days = 1
        elif event.direction == Gdk.SCROLL_DOWN:
            days = -1
        else:
            return

        try:
            date = self.get_date()
        except ValueError:
            date = None

        if not date:
            newdate = datetime.date.today()
        else:
            newdate = date + datetime.timedelta(days=days)
        self.set_date(newdate)

    def _on_button__toggled(self, button):
        if self._popping_down:
            return

        try:
            date = self.get_date()
        except ValueError:
            date = None

        self._popup.popup(date)

    def _on_popup__hide(self, popup):
        self._popping_down = True
        self._button.set_active(False)
        self._popping_down = False

    def _on_popup__date_selected(self, popup, date):
        self.set_date(date)
        self.entry.grab_focus()
        self.entry.set_position(len(self.entry.get_text()))
        self._changed(date)

    def _changed(self, date):
        if self._old_date != date:
            self.emit('changed')
            self._old_date = date

    # Public API

    def set_date(self, date):
        """Sets the date.
        :param date: date to set
        :type date: a datetime.date instance or None
        """
        if not isinstance(date, datetime.date) and date is not None:
            raise TypeError(
                "date must be a datetime.date instance or None, not %r" % (
                    date,
                )
            )

        if date is None:
            value = ''
        else:
            try:
                value = format_date(date, self.entry.get_text())
            except ValueError:
                value = format_date(date, "2016-12-01")
        self.entry.set_text(value)

    def get_date(self):
        """Get the selected date
        :returns: the date.
        :rtype: datetime.date or None
        """
        try:
            date = self.entry.get_text()
            date = parse_date(date)
        except ValueError:
            date = None
        if date == ValueUnset:
            date = None
        return date

    def follow(self, other_calendar):
        self.followed = other_calendar
        self.followed_last_value = other_calendar.get_date()

        def copy_when(other_calendar, *args):
            if (
                self.get_date() == self.followed_last_value or
                other_calendar.get_date() > self.get_date()
            ):
                self.set_date(other_calendar.get_date())
            self.followed_last_value = other_calendar.get_date()
        other_calendar.connect("changed", copy_when)


class TestWindow(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="Whatever")
        self.set_border_width(12)

        combobox = DateEntry()
        self.add(combobox)


def main():
    klass = TestWindow
    win = klass()
    win.connect("delete-event", Gtk.main_quit)
    GObject.idle_add(win.show_all)
    Gtk.main()


if __name__ == "__main__":
    main()
