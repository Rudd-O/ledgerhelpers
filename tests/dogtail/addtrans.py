#!/usr/bin/python3
# Dogtail test script for addtrans.

import os
import pipes
import tempfile

from dogtail import config
from dogtail import tree
from dogtail.procedural import type
from dogtail.rawinput import keyCombo, pressKey
from dogtail.utils import run


os.environ['LANG'] = "en_US.UTF-8"
os.environ['PYTHONPATH'] = os.path.join(
    os.path.dirname(__file__),
    os.path.pardir,
    os.path.pardir,
    'src'
)
os.environ['PATH'] =  os.path.join(
    os.path.dirname(__file__),
    os.path.pardir,
    os.path.pardir,
    'bin'
) + os.path.pathsep + os.environ['PATH']

config.config.typingDelay = 0.025

t = tempfile.NamedTemporaryFile()
t.write("""
2015-10-05 * beer
    Assets:Cash                       -30 CHF
    Expenses:Drinking                  30 CHF
""")
t.flush()
t.seek(0, 0)

run('addtrans --file %s' % pipes.quote(t.name))
addtrans = tree.root.application('addtrans')
mainwin = addtrans.window('Add transaction')

try:
    type("wine")
    pressKey("Tab")
    type("30")
    pressKey("Tab")
    type("Expenses:Drinking")
    pressKey("Tab")
    pressKey("Tab")
    type("Assets:Cash")
    pressKey("Tab")

    expected = """
2016-11-09 wine
    Expenses:Drinking    30 CHF
    Assets:Cash
"""

    actual = mainwin.child(name='Transaction preview').children[0].text
    assert (
        actual == expected
    ), (
        "Transaction preview did not contain 30 CHF as expected.\n"
        "Expected: %r\n"
        "Actual: %r" % (expected, actual)
    )
finally:
    keyCombo("<Alt>c")

#def recurse(child, level=0):
    #try:
        #print "   " * level, child.getAbsoluteSearchPath()
        #print "   " * level, child.text
    #except UnicodeDecodeError:
        #print "   " * level, "[undecodable path]"
    #for c in child.children:
        #recurse(c, level+1)

#recurse(mainwin)
