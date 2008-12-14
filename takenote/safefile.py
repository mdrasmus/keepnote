"""

    TakeNote
    Copyright Matt Rasmussen 2008

    SafeFile
    Safely write to a tempfile before replacing previous file.

"""


import os, tempfile


class SafeFile (file):

    def __init__(self, filename, mode="r", tmp=None):
        """
        filename -- filename to open
        mode     -- write mode (default: 'w')
        tmp      -- specify tempfile
        """
        
        # set tempfile
        if "w" in mode and tmp is None:
            f, tmp = tempfile.mkstemp(".tmp", filename+"_", dir=".")
            os.close(f)

        self._tmp = tmp
        self._filename = filename

        # open file
        if self._tmp:
            file.__init__(self, self._tmp, mode)
        else:
            file.__init__(self, filename, mode)


    def close(self):
        """Closes file"""
        
        file.close(self)

        if self._tmp:
            os.rename(self._tmp, self._filename)


    def get_tempfile(self):
        """Returns tempfile filename"""
        return self._tmp
