"""

    TakeNote
    Copyright Matt Rasmussen 2008

    SafeFile
    Safely write to a tempfile before replacing previous file.

"""


import os, tempfile, codecs


class SafeFile (file):

    def __init__(self, filename, mode="r", tmp=None, codec=None):
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
        self._file = None

        if codec:
            self._encode = codecs.getencoder(codec)
            self._decode = codecs.getdecoder(codec)
        else:
            self._encode = None
            self._decode = None


        # open file
        if self._tmp:
            file.__init__(self, self._tmp, mode)
        else:
            file.__init__(self, filename, mode)


    def read(self, *args, **kargs):
        text = file.read(self, *args, **kargs)
        if self._decode:
            return self._decode(text)[0]
        else:
            return text
        

    def write(self, text):
        if self._encode:
            text, size = self._encode(text)
        return file.write(self, text)
            

    def close(self):
        """Closes file"""
        
        file.close(self)

        if self._tmp:
            os.rename(self._tmp, self._filename)


    def get_tempfile(self):
        """Returns tempfile filename"""
        return self._tmp
