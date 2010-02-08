"""
    KeepNote Extension 
    backup_tar

    Tar file notebook backup
"""

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

import gettext
import os
import re
import shutil
import sys
import time

#_ = gettext.gettext

import keepnote
from keepnote import unicode_gtk, AppCommand
from keepnote.notebook import NoteBookError, get_valid_unique_filename
from keepnote import notebook as notebooklib
from keepnote import tasklib
from keepnote import tarfile
from keepnote.gui import extension

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



class Extension (extension.Extension):
    
    version = (1, 0)
    name = "Basic Commands"
    description = "Adds basic command line options to KeepNote"


    def __init__(self, app):
        """Initialize extension"""
        
        extension.Extension.__init__(self, app)
        self.app = app
        self.enabled.add(self.on_enabled)


    def get_depends(self):
        return [("keepnote", ">=", (0, 6, 2))]


    def on_enabled(self, enabled):
        
        if enabled:
            self.app.add_command(AppCommand("focus", 
                                            lambda app, args: app.focus_windows()))

            def screenshot_func(app, args):
                window = app.get_current_window()
                if window:
                    window.get_viewer().editor.on_screenshot()
            self.app.add_command(AppCommand("screenshot", screenshot_func))

        else:
            self.app.remove_command("focus")
            self.app.remove_command("screenshot")
