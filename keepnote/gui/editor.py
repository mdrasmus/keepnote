"""

    KeepNote
    Editor widget in main window

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


# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# keepnote imports
import keepnote

_ = keepnote.translate


class KeepNoteEditor (gtk.VBox):
    """
    Base class for all KeepNoteEditors
    """

    def __init__(self, app):
        gtk.VBox.__init__(self, False, 0)
        self._app = app
        self._notebook = None
        self._textview = None
        self.show_all()


    def set_notebook(self, notebook):
        """Set notebook for editor"""

    def get_textview(self):
        return self._textview

    def is_focus(self):
        """Return True if text editor has focus"""
        return False

    def grab_focus(self):
        """Pass focus to textview"""

    def clear_view(self):
        """Clear editor view"""
    
    def view_nodes(self, nodes):
        """View a node(s) in the editor"""
    
    def save(self):
        """Save the loaded page"""
        
    def save_needed(self):
        """Returns True if textview is modified"""
        return False

    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""

    def save_preferences(self, app_pref):
        """Save application preferences"""

    def add_ui(self, window):
        pass

    def remove_ui(self, window):
        pass

    def undo(self):
        pass

    def redo(self):
        pass


# add new signals to KeepNoteEditor
gobject.type_register(KeepNoteEditor)
gobject.signal_new("view-node", KeepNoteEditor, gobject.SIGNAL_RUN_LAST,
    gobject.TYPE_NONE, (object,))
gobject.signal_new("visit-node", KeepNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("modified", KeepNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, bool))
gobject.signal_new("font-change", KeepNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("error", KeepNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object))
gobject.signal_new("child-activated", KeepNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, object))
gobject.signal_new("window-request", KeepNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str,))
gobject.signal_new("make-link", KeepNoteEditor, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, ())


