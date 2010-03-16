"""

    KeepNote
    Tabbed Viewer for KeepNote.

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
import traceback


# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk
import gobject


# keepnote imports
import keepnote
from keepnote import unicode_gtk, KeepNoteError
from keepnote import notebook as notebooklib
from keepnote.gui.three_pane_viewer import ThreePaneViewer
from keepnote.gui.viewer import Viewer

_ = keepnote.translate


# TODO: be more careful about auto-saving
# should save() save all viewers
# I need to make sure that autosaves in two different windows never occur
# at once on the same notebook.
# maybe, autosaving should be app-wide thing.



class TabbedViewer (Viewer):
    """A viewer with a treeview, listview, and editor"""

    def __init__(self, app, main_window, default_viewer=ThreePaneViewer):
        Viewer.__init__(self, app, main_window)        
        self._default_viewer = default_viewer
        self._current_viewer = None
        self._ui_ready = False
        self._null_viewer = Viewer(app, main_window)
        
        # layout
        self._tabs = gtk.Notebook()
        self._tabs.show()
        self._tabs.connect("switch-page", self._on_switch_tab)
        self.pack_start(self._tabs, True, True, 0)

        self._current_viewer = None

        self.new_tab()
        self.new_tab()


        # TODO: maybe add close_viewer() function


    def new_tab(self, viewer=None):
        """Open a new tab with a viewer"""
        if viewer is None:
            viewer = self._default_viewer(self._app, self._main_window)
        self._tabs.append_page(viewer, gtk.Label("tab"))


    def get_current_viewer(self):
        """Get currently focused viewer"""
        pos = self._tabs.get_current_page()
        if pos == -1:
            return self._null_viewer
        else:
            return self._tabs.get_nth_page(pos)


    def iter_viewers(self):
        """Iterate through all viewers"""
        for i in xrange(self._tabs.get_n_pages()):            
            yield self._tabs.get_nth_page(i)

    
    def _on_switch_tab(self, tabs, page, page_num):
        """Callback for switching between tabs"""

        if not self._ui_ready:
            return

        # remove old tab ui
        if self._current_viewer:
            self._current_viewer.remove_ui(self._main_window)

        # add new tab ui
        self._current_viewer = self._tabs.get_nth_page(page_num)
        self._current_viewer.add_ui(self._main_window)

    #==============================================

    def set_notebook(self, notebook):
        """Set the notebook for the viewer"""
        return self.get_current_viewer().set_notebook(notebook)

    def get_notebook(self):
        return self.get_current_viewer().get_notebook()


    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""

        for viewer in self.iter_viewers():
            viewer.load_preferences(app_pref, first_open)


    def save_preferences(self, app_pref):
        """Save application preferences"""

        for viewer in self.iter_viewers():
            viewer.save_preferences(app_pref)


    def save(self):
        """Save the current notebook"""
        return self.get_current_viewer().save()
        

    def undo(self):
        """Undo the last action in the viewer"""
        return self.get_current_viewer().undo()


    def redo(self):
        """Redo the last action in the viewer"""
        return self.get_current_viewer().redo()


    #===============================================
    # node operations


    def get_current_page(self):
        """Returns the currently focused page"""
        return self.get_current_viewer().get_current_page()


    def get_selected_nodes(self, widget="focus"):
        """
        Returns (nodes, widget) where 'nodes' are a list of selected nodes
        in widget 'widget'

        Wiget can be
           listview -- nodes selected in listview
           treeview -- nodes selected in treeview
           focus    -- nodes selected in widget with focus
        """
        return self.get_current_viewer().get_selected_nodes()


    def goto_node(self, node, direct=True):
        """Move view focus to a particular node"""
        return self.get_current_viewer().goto_node(node, direct)
                    

    #============================================
    # Search

    def start_search_result(self):
        """Start a new search result"""
        return self.get_current_viewer().start_search_result()


    def add_search_result(self, node):
        """Add a search result"""
        return self.get_current_viewer().add_search_result(node)


    #===========================================
    # ui
    
    def add_ui(self, window):
        """Add the view's UI to a window"""
        assert window == self._main_window
        self._ui_ready = True
        self.get_current_viewer().add_ui(window)        


    def remove_ui(self, window):
        """Remove the view's UI from a window"""
        assert window == self._main_window
        self._ui_ready = False
        self.get_current_viewer().remove_ui(window)



