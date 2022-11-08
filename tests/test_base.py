import codecs
import os

import ledgerhelpers as m


if os.getenv('LEDGERHELPERS_TEST_DEBUG'):
    m.enable_debugging(True)


def datapath(filename):
    return os.path.join(os.path.dirname(__file__), "testdata", filename)


def data(filename):
    with codecs.open(datapath(filename), "rb", "utf-8") as f:
        return f.read()
