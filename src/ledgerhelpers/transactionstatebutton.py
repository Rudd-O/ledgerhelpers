#!/usr/bin/env python
# coding: utf-8

import gi; gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from ledgerhelpers import parser


class TransactionStateButton(Gtk.Button):

    STATE_CLEARED = parser.STATE_CLEARED
    STATE_UNCLEARED = parser.STATE_UNCLEARED
    STATE_PENDING = parser.STATE_PENDING

    def __init__(self):
        Gtk.Button.__init__(self)
        self.label = Gtk.Label()
        self.add(self.label)
        self.state = "uninitialized"
        self.connect("clicked", lambda _: self._rotate_state())
        self.get_style_context().add_class("circular")
        self._rotate_state()

    def _rotate_state(self):
        if self.state == self.STATE_UNCLEARED:
            self.state = self.STATE_CLEARED
        elif self.state == self.STATE_CLEARED:
            self.state = self.STATE_PENDING
        else:
            self.state = self.STATE_UNCLEARED
        self._reflect_state()

    def _reflect_state(self):
        addtext = "\n\nToggle this to change the transaction state."
        if self.state == self.STATE_UNCLEARED:
            self.label.set_markup("∅")
            self.set_tooltip_text(
                "This transaction is uncleared." + addtext
            )
        elif self.state == self.STATE_CLEARED:
            self.label.set_markup("✻")
            self.set_tooltip_text(
                "This transaction is cleared." + addtext
            )
        else:
            self.label.set_markup("!")
            self.set_tooltip_text(
                "This transaction is pending." + addtext
            )

    def get_state(self):
        return self.state

    def get_state_char(self):
        if self.state == parser.STATE_CLEARED:
            clearing_state = parser.CHAR_CLEARED
        elif self.state == parser.STATE_UNCLEARED:
            clearing_state = ""
        elif self.state == parser.STATE_PENDING:
            clearing_state = parser.CHAR_PENDING
        else:
            assert 0, "not reached"
        return clearing_state

    def set_state(self, state):
        assert state in (self.STATE_CLEARED,
                         self.STATE_PENDING,
                         self.STATE_UNCLEARED)
        self.state = state
        self._reflect_state()
