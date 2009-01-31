"""
    KeepNote
    Copyright Matt Rasmussen 2009

    Tee File Streams
"""


class TeeFileStream (object):
    """Create a file stream that forwards writes to multiple streams"""
    
    def __init__(self, streams, autoflush=False):
        self._streams = list(streams)
        self._autoflush = autoflush


    def write(self, data):
        for stream in self._streams:
            stream.write(data)
            if self._autoflush:
                stream.flush()

    def flush(self):
        for stream in self._streams:
            stream.flush()            

