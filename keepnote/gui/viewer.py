"""

    KeepNote
    Base class for a viewer

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
import os
import subprocess
import traceback


# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk
import gobject


# keepnote imports
import keepnote
from keepnote import KeepNoteError
from keepnote.history import NodeHistory
from keepnote import notebook as notebooklib
from keepnote.gui.treemodel import iter_children

_ = keepnote.translate



class Viewer (gtk.VBox):

    def __init__(self, app, parent):
        gtk.VBox.__init__(self, False, 0)
        self._app = app
        self._main_window = parent
        
        self._notebook = None
        self._history = NodeHistory()



    def set_notebook(self, notebook):
        """Sets the current notebook for the viewer"""
        self._notebook = notebook

    def get_notebook(self):
        """Returns the current notebook for the viewer"""
        return self._notebook
    
    def load_preferences(self, app_pref, first_open):
        pass

    def save_preferences(self, app_pref):
        pass

    def save(self):
        pass

    def undo(self):
        pass

    def redo(self):
        pass

    def get_current_page(self):
        return None

    def get_selected_nodes(self, widget="focus"):
        pass

    def new_node(self, kind, widget, pos):
        # TODO: choose a more general interface (i.e. deal with widget param)
        pass

    def goto_node(self, node, direct=True):
        pass

    def visit_history(self, offset):
        """Visit a node in the viewer's history"""
        
        nodeid = self._history.move(offset)
        if nodeid is None:
            return
        node = self._notebook.get_node_by_id(nodeid)
        if node:
            self._history.begin_suspend()
            self.goto_node(node, False)
            self._history.end_suspend()


    #===============================================
    # search

    def start_search_result(self):        
        pass

    def add_search_result(self, node):
        pass

    #================================================
    # UI management

    def add_ui(self, window):
        pass

    def remove_ui(self, window):
        pass





gobject.type_register(Viewer)
gobject.signal_new("error", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object))
gobject.signal_new("status", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, str))
gobject.signal_new("history-changed", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("window-request", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str,))

