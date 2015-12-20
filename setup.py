#!/usr/bin/env python

from setuptools import setup
import os

dir = os.path.dirname(__file__)
path_to_main_file = os.path.join(dir, "src/ledgerhelpers/__init__.py")
path_to_readme = os.path.join(dir, "README.md")
for line in open(path_to_main_file):
	if line.startswith('__version__'):
		version = line.split()[-1].strip("'").strip('"')
		break
else:
	raise ValueError, '"__version__" not found in "src/ledgerhelpers/__init__.py"'
readme = open(path_to_readme).read(-1)

classifiers = [
'Development Status :: 3 - Alpha',
'Environment :: X11 Applications :: GTK',
'Intended Audience :: End Users/Desktop',
'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
'Operating System :: POSIX :: Linux',
'Programming Language :: Python :: 2 :: Only',
'Programming Language :: Python :: 2.7',
'Topic :: Office/Business :: Financial :: Accounting',
]

programs = ["buy", "withdraw-cli", "cleartrans-cli", "sorttrans-cli", "updateprices"]

setup(
	name='ledgerhelpers',
	version=version,
	description='A collection of helper programs and a helper library for Ledger (ledger-cli)',
	long_description = readme,
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
	data_files = [
		("/usr/share/applications", ["applications/%s.desktop" % p for p in programs]),
	],
	scripts=["bin/%s" % p for p in programs],
	keywords="accounting ledger ledger-cli",
	requires=["ledger", "yahoo_finance"],
	zip_safe=False,
)
