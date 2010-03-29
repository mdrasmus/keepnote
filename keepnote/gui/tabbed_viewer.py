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
from keepnote.gui import \
    add_actions, Action
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
        self._callbacks = {}
        self._ui_ready = False
        self._null_viewer = Viewer(app, main_window)
        
        # layout
        self._tabs = gtk.Notebook()
        self._tabs.show()
        self._tabs.set_property("show-border", False)
        self._tabs.set_property("homogeneous", True)
        self._tabs.set_property("scrollable", True)
        self._tabs.connect("switch-page", self._on_switch_tab)
        self._tabs.connect("page-added", self._on_tab_added)
        self._tabs.connect("page-removed", self._on_tab_removed)
        self.pack_start(self._tabs, True, True, 0)

        self.new_tab()

        # TODO: maybe add close_viewer() function


    def new_tab(self, viewer=None):
        """Open a new tab with a viewer"""
        
        if viewer is None:
            viewer = self._default_viewer(self._app, self._main_window)
        self._tabs.append_page(viewer, gtk.Label(_("(Untitled)")))
        self._tabs.set_tab_reorderable(viewer, True)
        viewer.show_all()

        # setup viewer
        self._callbacks[viewer] = [
            viewer.connect("current-node", self.on_tab_current_node),
            viewer.connect("modified", self.on_tab_modified)]
        viewer.load_preferences(self._app.pref, True)        

        # replicate current view
        old_viewer = self.get_current_viewer()
        if old_viewer is not None:
            viewer.set_notebook(old_viewer.get_notebook())
            node = old_viewer.get_current_page()
            if node:
                viewer.goto_node(node)

        # switch to the new tab
        self._tabs.set_current_page(self._tabs.get_n_pages() - 1)


    def close_tab(self, pos=None):
        """Close a tab"""

        if self._tabs.get_n_pages() <= 1:
            return

        if pos is None:
            pos = self._tabs.get_current_page()

        viewer = self._tabs.get_nth_page(pos)
        viewer.set_notebook(None)
        for callid in self._callbacks[viewer]:
            viewer.disconnect(callid)
        del self._callbacks[viewer]

        if pos == self._tabs.get_current_page():
            viewer.remove_ui(self._main_window)
            self._current_viewer = None

        self._tabs.remove_page(pos)


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

        # notify listeners of new current tab
        def func():
            self.emit("current-node", self._current_viewer.get_current_page())
            notebook = self._current_viewer.get_notebook()
            if notebook:
                self.emit("modified", notebook.save_needed())
            else:
                self.emit("modified", False)
        gobject.idle_add(func)


    def _on_tab_added(self, tabs, child, page_num):
        self._tabs.set_show_tabs(self._tabs.get_n_pages() > 1)

    def _on_tab_removed(self, tabs, child, page_num):
        self._tabs.set_show_tabs(self._tabs.get_n_pages() > 1)


    def on_tab_current_node(self, viewer, node):
        """Callback for when a viewer wants to set its title"""

        # get node title
        if node is None:
            if viewer.get_notebook():
                title = viewer.get_notebook().get_attr("title")
            else:
                title = _("(Untitled)")
        else:
            title = node.get_attr("title")

        # truncate title
        MAX_TITLE = 20
        if len(title) > MAX_TITLE - 3:
            title = title[:MAX_TITLE-3] + "..."

        # set tab label with node title
        self._tabs.set_tab_label_text(viewer, title)
                
        # propogate current-node signal
        self.emit("current-node", node)


    def on_tab_modified(self, viewer, modified):
        """Callback for when viewer contains modified data"""
        # propogate modified signal
        self.emit("modified", modified)


    def switch_tab(self, step):
        """Switches to the next or previous tab"""

        pos = self._tabs.get_current_page()
        pos = (pos + step) % self._tabs.get_n_pages()
        self._tabs.set_current_page(pos)
        

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
        self.get_current_viewer().save_preferences(app_pref)


    def save(self):
        """Save the current notebook"""
        for viewer in self.iter_viewers():
            viewer.save()
        

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


    def goto_node(self, node, direct=False):
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
        self._action_group = gtk.ActionGroup("Tabbed Viewer")
        self._uis = []
        add_actions(self._action_group, self._get_actions())
        self._main_window.get_uimanager().insert_action_group(
            self._action_group, 0)

        for s in self._get_ui():
            self._uis.append(
                self._main_window.get_uimanager().add_ui_from_string(s))

        uimanager = self._main_window.get_uimanager()
        uimanager.ensure_update()


        self.get_current_viewer().add_ui(window)     


    def remove_ui(self, window):
        """Remove the view's UI from a window"""
        assert window == self._main_window
        self._ui_ready = False
        self.get_current_viewer().remove_ui(window)

        for ui in reversed(self._uis):
            self._main_window.get_uimanager().remove_ui(ui)
        self._uis = []

        self._main_window.get_uimanager().remove_action_group(self._action_group)
        self._action_group = None
        self._main_window.get_uimanager().ensure_update()



    def _get_ui(self):

        return ["""
<ui>

<!-- main window menu bar -->
<menubar name="main_menu_bar">
  <menu action="File">
    <placeholder name="Viewer Window">
      <menuitem action="New Tab"/>
      <menuitem action="Close Tab"/>
    </placeholder>
  </menu>
  <menu action="Go">
    <placeholder name="Viewer">
      <menuitem action="Next Tab"/>
      <menuitem action="Previous Tab"/>
      <separator/>
    </placeholder>
  </menu>
</menubar>
</ui>
"""]


    def _get_actions(self):

        actions = map(lambda x: Action(*x), [
            ("New Tab", None, _("New _Tab"),
             "<shift><control>T", _("Open a new tab"),
             lambda w: self.new_tab()),
            ("Close Tab", None, _("Close _Tab"),
             "<shift><control>W", _("Close a tab"),
             lambda w: self.close_tab()),
            ("Next Tab", None, _("_Next Tab"),
             "<control>Page_Down", _("Switch to next tab"),
             lambda w: self.switch_tab(1)),
            ("Previous Tab", None, _("_Previous Tab"),
             "<control>Page_Up", _("Swtch to previous tab"),
             lambda w: self.switch_tab(-1))

            ])
        return actions

