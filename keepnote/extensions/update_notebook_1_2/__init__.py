#
# Keepnote Extension 
# backup_tar
#
# Tar file notebook backup
#

import os, re, shutil, time
import tarfile

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
        
