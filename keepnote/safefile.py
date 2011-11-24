"""

    KeepNote
    Safely write to a tempfile before replacing previous file.

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
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


import os, tempfile, codecs, sys

# NOTE: bypass easy_install's monkey patching of file
# easy_install does not correctly emulate 'file'
if type(file) != type:
    # HACK: this works as long as sys.stdout is not patched
    file = type(sys.stdout)


def open(filename, mode="r", tmp=None, codec=None):
    """
    Opens a file that writes to a temp location and replaces existing file
    on close.
    
    filename -- filename to open
    mode     -- write mode (default: 'w')
    tmp      -- specify tempfile
    codec    -- preferred encoding
    """
    stream = SafeFile(filename, mode, tmp)
    
    if "b" not in mode and codec:
        if "r" in mode:
            stream = codecs.getreader(codec)(stream)
        elif "w" in mode:
            stream = codecs.getwriter(codec)(stream)

    return stream


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
        """Closes file and moves temp file to final location"""
        
        try:
            self.flush()
            os.fsync(self.fileno())
        except:
            pass
        file.close(self)

        if self._tmp:
            # NOTE: windows will not allow rename when destination file exists
            if sys.platform.startswith("win"):
                if os.path.exists(self._filename):
                    os.remove(self._filename)
            os.rename(self._tmp, self._filename)
            self._tmp = None



    def discard(self):
        """
        Close and discard written data.

        Temp file does not replace existing file
        """

        file.close(self)

        if self._tmp:
            os.remove(self._tmp)
            self._tmp = None
    

    def get_tempfile(self):
        """Returns tempfile filename"""
        return self._tmp

