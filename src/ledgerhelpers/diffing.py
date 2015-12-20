#!/usr/bin/env python

import subprocess
import tempfile


def three_way_diff(basefilename, leftcontents, rightcontents):
    """Given a file which is assumed to be utf-8, two utf-8 strings,
    left and right, launch a three-way diff.

    Raises: subprocess.CalledProcessError."""
    if not isinstance(leftcontents, unicode):
        leftcontents = leftcontents.encode("utf-8")
    if not isinstance(rightcontents, unicode):
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
