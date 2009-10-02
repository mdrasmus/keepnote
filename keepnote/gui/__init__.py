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
from keepnote import log_error
import keepnote.gui.richtext.richtext_tags
from keepnote import get_resource, ensure_unicode, get_platform
from keepnote.notebook import \
     NoteBookError
import keepnote.notebook as notebooklib
import keepnote.gui.dialog_app_options
import keepnote.gui
from keepnote.gui.icons import \
    DEFAULT_QUICK_PICK_ICONS
    

# setup glade with gettext
gtk.glade.bindtextdomain(keepnote.GETTEXT_DOMAIN, keepnote.get_locale_dir())


# constants
MAX_RECENT_NOTEBOOKS = 20
ACCEL_FILE = "accel.txt"
CONTEXT_MENU_ACCEL_PATH = "<main>/context_menu"


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


def init_key_shortcuts():
    """Setup key shortcuts for the window"""

    accel_file = get_accel_file()
    if os.path.exists(accel_file):
        gtk.accel_map_load(accel_file)
    else:
        gtk.accel_map_save(accel_file)



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



class FileChooserDialog (gtk.FileChooserDialog):
    """File Chooser Dialog with a persistent path"""

    def __init__(self, title=None, parent=None,
                 action=gtk.FILE_CHOOSER_ACTION_OPEN,
                 buttons=None, backend=None,
                 app=None,
                 persistent_path=None):
        gtk.FileChooserDialog.__init__(self, title, parent,
                                       action, buttons, backend)

        self._app = app
        self._persistent_path = persistent_path
        
        if self._app and self._persistent_path:
            path = getattr(self._app.pref, self._persistent_path)
            if os.path.exists(path):
                self.set_current_folder(path)


    def run(self):
        response = gtk.FileChooserDialog.run(self)

        if (response == gtk.RESPONSE_OK and 
            self._app and self._persistent_path):
            setattr(self._app.pref, self._persistent_path,
                    unicode_gtk(self.get_current_folder()))
            
        return response



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
    """Add a list of Action's to an gtk.ActionGroup"""

    for action in actions:
        actiongroup.add_action_with_accel(action, action.accel)


def remove_actions(actiongroup, names):
    """Remove actions specified by name from an gtk.ActionGroup"""

    for action in actiongroup.list_actions():
        if action.get_name() in names:
            actiongroup.remove_action(action)


#=============================================================================
# Application for GUI


class KeepNote (keepnote.KeepNote):
    """GUI version of the KeepNote application instance"""

    def __init__(self, basedir=""):
        keepnote.KeepNote.__init__(self, basedir)

        self._tag_table = keepnote.gui.richtext.richtext_tags.RichTextTagTable()
        
        self._current_window = None
        self._windows = []

        self.app_options_dialog = keepnote.gui.dialog_app_options.ApplicationOptionsDialog(self)


    def new_window(self):
        """Create a new main window"""

        window = keepnote.gui.main_window.KeepNoteWindow(self)
        window.connect("delete-event", self._on_window_close)
        window.connect("focus-in-event", self._on_focus)
        self._windows.append(window)
        
        self.init_extensions_window(window)
        window.show_all()

        return window

    def get_current_window(self):
        """Returns the currenly active window"""
        return self._current_window
    


    def open_notebook(self, filename, window=None):
        """Open notebook"""

        # TODO: think about error dialogs without main window
        
        from keepnote.gui import dialog_update_notebook

        version = notebooklib.get_notebook_version(filename)
            
        if version < notebooklib.NOTEBOOK_FORMAT_VERSION:
            dialog = dialog_update_notebook.UpdateNoteBookDialog(self, window)
            if not dialog.show(filename, version=version):
                raise NoteBookError(_("Cannot open notebook (version too old)"))

        notebook = notebooklib.NoteBook()
        notebook.load(filename)

        # install default quick pick icons
        if len(notebook.pref.get_quick_pick_icons()) == 0:
            notebook.pref.set_quick_pick_icons(
                list(DEFAULT_QUICK_PICK_ICONS))

            # TODO: use listeners to invoke saving
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

        if window in self._windows:
            for ext in self.iter_extensions():
                try:
                    ext.on_close_window(window)
                except Exception, e:
                    log_error(e, sys.exc_info()[2])

            # remove window from window list
            self._windows.remove(window)

            if window == self._current_window:
                self._current_window = None

        # quit app if last window closes
        if len(self._windows) == 0:
            self.quit()


    def _on_focus(self, window, event):
        """Callback for when a window gains focus"""
        self._current_window = window


    def quit(self):
        """Quit the gtk event loop"""
        
        gtk.accel_map_save(get_accel_file())
        gtk.main_quit()


    #====================================
    # extension methods


    def init_extensions_window(self, window):
        """Initialize all extensions for a window"""
        
        for ext in self.iter_extensions():
            try:
                ext.on_new_window(window)
            except Exception, e:
                log_error(e, sys.exc_info()[2])

