"""

    KeepNote
    Graphical User Interface for KeepNote Application

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


# python imports
import gettext
import mimetypes
import os
import subprocess
import sys
import tempfile

_ = gettext.gettext

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# keepnote imports
import keepnote
import keepnote.gui.richtext.richtext_tags
from keepnote import get_resource, ensure_unicode, get_platform
from keepnote.notebook import \
     NoteBookError
import keepnote.notebook as notebooklib
from keepnote.gui.icons import \
    DEFAULT_QUICK_PICK_ICONS
    

# setup glade with gettext
gtk.glade.bindtextdomain(keepnote.GETTEXT_DOMAIN, keepnote.get_locale_dir())


# constants
MAX_RECENT_NOTEBOOKS = 10
ACCEL_FILE = "accel.txt"


# globals
_g_pixbufs = {}



#=============================================================================
# resources

def get_pixbuf(filename, size=None):
    """
    Get pixbuf from a filename

    Cache pixbuf for later use
    """

    key = (filename, size)
    
    if key in _g_pixbufs:
        return _g_pixbufs[key]
    else:
        # may raise GError
        pixbuf = gtk.gdk.pixbuf_new_from_file(filename)

        if size:
            if size != (pixbuf.get_width(), pixbuf.get_height()):
                pixbuf = pixbuf.scale_simple(size[0], size[1],
                                             gtk.gdk.INTERP_BILINEAR)
        
        _g_pixbufs[key] = pixbuf
        return pixbuf
    

def get_resource_image(*path_list):
    """Returns gtk.Image from resource path"""
    
    filename = get_resource(keepnote.IMAGE_DIR, *path_list)
    img = gtk.Image()
    img.set_from_file(filename)
    return img

def get_resource_pixbuf(*path_list):
    """Returns cached pixbuf from resource path"""
    # raises GError
    return get_pixbuf(get_resource(keepnote.IMAGE_DIR, *path_list))



#=============================================================================
# misc. gui functions
  
def get_accel_file():
    """Returns gtk accel file"""

    return os.path.join(keepnote.get_user_pref_dir(), ACCEL_FILE)


def update_file_preview(file_chooser, preview):
    """Preview widget for file choosers"""
        
    filename = file_chooser.get_preview_filename()
    try:
        pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename, 128, 128)
        preview.set_from_pixbuf(pixbuf)
        have_preview = True
    except:
        have_preview = False
    file_chooser.set_preview_widget_active(have_preview)


#=============================================================================
# menu actions


class Action (gtk.Action):
    def __init__(self, name, stockid, label=None,
                 accel="", tooltip="", func=None):
        gtk.Action.__init__(self, name, label, tooltip, stockid)
        self.func = func
        self.accel = accel

        if func:
            self.connect("activate", func)

class ToggleAction (gtk.ToggleAction):
    def __init__(self, name, stockid, label=None,
                 accel="", tooltip="", func=None):
        gtk.Action.__init__(self, name, label, tooltip, stockid)
        self.func = func
        self.accel = accel

        if func:
            self.connect("activate", func)

def add_actions(actiongroup, actions):
    for action in actions:
        actiongroup.add_action_with_accel(action, action.accel)



#=============================================================================
# Application for GUI


class KeepNote (keepnote.KeepNote):
    """GUI version of the KeepNote application instance"""

    def __init__(self, basedir=""):
        keepnote.KeepNote.__init__(self, basedir)

        self._tag_table = keepnote.gui.richtext.richtext_tags.RichTextTagTable()

        self._windows = []


    def new_window(self):
        """Create a new main window"""

        from keepnote.gui import main_window

        window = main_window.KeepNoteWindow(self)
        window.connect("delete-event", self._on_window_close)
        self._windows.append(window)
        
        self.init_extensions_window(window)
        window.show_all()

        return window
    

    def get_notebook(self, filename, window=None):
        """Returns a an opened notebook at filename"""

        filename = os.path.realpath(filename)
        if filename not in self._notebooks:
            self._notebooks[filename] = self.open_notebook(filename, window)

        return self._notebooks[filename]


    def open_notebook(self, filename, window=None):
        """Open notebook"""

        # TODO: think about error dialogs without main window
        
        from keepnote.gui import dialog_update_notebook

        version = notebooklib.get_notebook_version(filename)
            
        if version < notebooklib.NOTEBOOK_FORMAT_VERSION:
            dialog = dialog_update_notebook.UpdateNoteBookDialog(self.app, window)
            if not dialog.show(filename, version=version):
                raise NoteBookError(_("Cannot open notebook (version too old)"))

        notebook = notebooklib.NoteBook()
        notebook.load(filename)


        if len(notebook.pref.get_quick_pick_icons()) == 0:
            notebook.pref.set_quick_pick_icons(
                list(DEFAULT_QUICK_PICK_ICONS))
            notebook.write_preferences()

        return notebook


    def focus_windows(self):
        """Focus all open windows on desktop"""

        for window in self._windows:
            window.restore_window()


    def get_richtext_tag_table(self):
        """Returns the application-wide richtext tag table"""
        return self._tag_table

    #===================================
    # callbacks


    def _on_window_close(self, window, event):
        """Callback for window close event"""

        # remove window from window list
        self._windows.remove(window)

        # quit app if last window closes
        if len(self._windows) == 0:
            self.quit()


    def quit(self):
        """Quit the gtk event loop"""
        
        gtk.accel_map_save(get_accel_file())
        gtk.main_quit()



