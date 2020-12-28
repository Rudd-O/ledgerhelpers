#!/usr/bin/python3

import subprocess
import tempfile


def three_way_diff(basefilename, leftcontents, rightcontents):
    """Given a file which is assumed to be utf-8, two utf-8 strings,
    left and right, launch a three-way diff.

    Raises: subprocess.CalledProcessError."""
    if isinstance(leftcontents, str):
        leftcontents = leftcontents.encode("utf-8")
    if isinstance(rightcontents, str):
        rightcontents = rightcontents.encode("utf-8")

    prevfile = tempfile.NamedTemporaryFile(prefix=basefilename + ".previous.")
    prevfile.write(leftcontents)
    prevfile.flush()
    newfile = tempfile.NamedTemporaryFile(prefix=basefilename + ".new.")
    newfile.write(rightcontents)
    newfile.flush()
    try:
        subprocess.check_call(
            ('meld', prevfile.name, basefilename, newfile.name)
        )
    finally:
        prevfile.close()
        newfile.close()


def two_way_diff(leftcontents, rightcontents):
    """Given two strings which are assumed to be utf-8, open a
    two-way diff view with them.

    Raises: subprocess.CalledProcessError."""
    if isinstance(leftcontents, str):
        leftcontents = leftcontents.encode("utf-8")
    if isinstance(rightcontents, str):
        rightcontents = rightcontents.encode("utf-8")

    prevfile = tempfile.NamedTemporaryFile(prefix=".base.")
    prevfile.write(leftcontents)
    prevfile.flush()
    newfile = tempfile.NamedTemporaryFile(prefix=".new.")
    newfile.write(rightcontents)
    newfile.flush()
    try:
        subprocess.check_call(
            ('meld', prevfile.name, newfile.name)
        )
    finally:
        prevfile.close()
        newfile.close()
