import codecs
import os


def datapath(filename):
    return os.path.join(os.path.dirname(__file__), "testdata", filename)


def data(filename):
    return codecs.open(datapath(filename), "rb", "utf-8").read()
