#!/usr/bin/python3

import glob
from setuptools import setup
import os
import platform
import sys

assert sys.version_info.major == 3, "This program can no longer be built for Python 2"

dir = os.path.dirname(__file__)
path_to_main_file = os.path.join(dir, "src/ledgerhelpers/__init__.py")
path_to_readme = os.path.join(dir, "README.md")
for line in open(path_to_main_file):
	if line.startswith('__version__'):
		version = line.split()[-1].strip("'").strip('"')
		break
else:
	raise ValueError('"__version__" not found in "src/ledgerhelpers/__init__.py"')
readme = open(path_to_readme).read(-1)

classifiers = [
'Development Status :: 3 - Alpha',
'Environment :: X11 Applications :: GTK',
'Intended Audience :: End Users/Desktop',
'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
'Operating System :: POSIX :: Linux',
'Programming Language :: Python :: 3 :: Only',
'Programming Language :: Python :: 3.6',
'Topic :: Office/Business :: Financial :: Accounting',
]

programs = [
    "withdraw-cli",
    "cleartrans-cli",
    "sorttrans-cli",
    "updateprices",
    "sellstock-cli",
    "addtrans",
]

# https://github.com/Rudd-O/ledgerhelpers/issues/3
# Don't write to /usr/share/applications on OS X to work around the
# 'System Integrity Protection'.
data_files = [
	("/usr/share/applications", ["applications/%s.desktop" % p for p in programs]),
	("/usr/share/doc/ledgerhelpers/doc", glob.glob(os.path.join(os.path.dirname(__file__), "doc", "*"))),
	("/usr/share/man/man1", glob.glob(os.path.join(os.path.dirname(__file__), "man", "*.1"))),
] if platform.system() != 'Darwin' else []

setup(
	name='ledgerhelpers',
	version=version,
	description='A collection of helper programs and a helper library for Ledger (ledger-cli)',
	long_description = readme,
	long_description_content_type = "text/markdown",
	author='Manuel Amador (Rudd-O)',
	author_email='rudd-o@rudd-o.com',
	license="GPLv2+",
	url='http://github.com/Rudd-O/ledgerhelpers',
	package_dir=dict([
                    ("ledgerhelpers", "src/ledgerhelpers"),
					]),
	classifiers = classifiers,
	packages=["ledgerhelpers",
              "ledgerhelpers.programs"],
	data_files = data_files,
	scripts=["bin/%s" % p for p in programs],
	keywords="accounting ledger ledger-cli",
	requires=["ledger", "yahoo_finance"],
	zip_safe=False,
)
