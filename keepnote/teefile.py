"""

    KeepNote
    Tee File Streams

    Allow one file stream to multiplex for multiple file streams

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

class TeeFileStream (object):
    """Create a file stream that forwards writes to multiple streams"""
    
    def __init__(self, streams, autoflush=False):
        self._streams = list(streams)
        self._autoflush = autoflush


    def add(self, stream):
        """Adds a new stream to teefile"""
        self._streams.append(stream)

        
    def remove(self, stream):
        """Removes a stream from teefile"""
        self._streams.remove(stream)


    def get_streams(self):
        """Returns a list of streams associated with teefile"""
        return list(self._streams)


    def write(self, data):
        """Write data to streams"""
        for stream in self._streams:
            stream.write(data)
            if self._autoflush:
                stream.flush()

    def flush(self):
        """Flush streams"""
        for stream in self._streams:
            stream.flush()

