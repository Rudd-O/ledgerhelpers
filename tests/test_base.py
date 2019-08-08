import codecs
import os


def datapath(filename):
    return os.path.join(os.path.dirname(__file__), "testdata", filename)


def data(filename):
    with codecs.open(datapath(filename), "rb", "utf-8") as f:
        return f.read()
