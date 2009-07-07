#
# Keepnote Extension 
# notebook update
#

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
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

import os, re, shutil, time

import keepnote
from keepnote.notebook import NoteBookError, get_valid_unique_filename
from keepnote import notebook as notebooklib

# pygtk imports
try:
    import pygtk
    pygtk.require('2.0')
    from gtk import gdk
    import gtk.glade
    import gobject
except ImportError:
    # do not fail on gtk import error,
    # extension should be usable for non-graphical uses
    pass



class Extension (keepnote.Extension):
    
    version = "1.0"
    name = "Update Notebook 1 to 2"
    description = "Updates a notebook from version 1 to version 2"


    def __init__(self, app):
        """Initialize extension"""
        
        keepnote.Extension.__init__(self, app)
        self.app = app


    def update(self, filename):
        
        notebook = notebooklib.NoteBook()
        
        try:
            notebook.load(filename)
        except Exception, e:
            pass
        
