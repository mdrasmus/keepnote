"""

    KeepNote
    Tabbed Viewer for KeepNote.

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
import gtk
import gobject

# keepnote imports
import keepnote
from keepnote.gui import \
    add_actions, Action
from keepnote.gui.three_pane_viewer import ThreePaneViewer
from keepnote.gui.viewer import Viewer
from keepnote.gui.icons import get_node_icon


_ = keepnote.translate


class TwoWayDict (object):

    def __init__(self):

        self._lookup1 = {}
        self._lookup2 = {}

    def add(self, item1, item2):
        self._lookup1[item1] = item2
        self._lookup2[item2] = item1

    def get1(self, item1, default=None):
        return self._lookup1.get(item1, default)

    def get2(self, item2, default=None):
        return self._lookup2.get(item2, default)


class TabbedViewer (Viewer):
    """A viewer with a treeview, listview, and editor"""

    def __init__(self, app, main_window, viewerid=None,
                 default_viewer=ThreePaneViewer):
        Viewer.__init__(self, app, main_window, viewerid,
                        viewer_name="tabbed_viewer")
        self._default_viewer = default_viewer
        self._current_viewer = None
        self._callbacks = {}
        self._ui_ready = False
        self._null_viewer = Viewer(app, main_window)
        self._tab_names = {}

        # TODO: move to the app?
        # viewer registry
        self._viewer_lookup = TwoWayDict()
        self._viewer_lookup.add(ThreePaneViewer(app, main_window).get_name(),
                                ThreePaneViewer)

        # layout
        self._tabs = gtk.Notebook()
        self._tabs.show()
        self._tabs.set_property("show-border", False)
        self._tabs.set_property("homogeneous", True)
        self._tabs.set_property("scrollable", True)
        self._tabs.connect("switch-page", self._on_switch_tab)
        self._tabs.connect("page-added", self._on_tab_added)
        self._tabs.connect("page-removed", self._on_tab_removed)
        self._tabs.connect("button-press-event", self._on_button_press)
        self.pack_start(self._tabs, True, True, 0)

        # initialize with a single tab
        self.new_tab()

        # TODO: maybe add close_viewer() function

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

    def new_tab(self, viewer=None, init="current_node"):
        """Open a new tab with a viewer"""

        # TODO: make new tab appear next to existing tab

        # create viewer and add to notebook
        if viewer is None:
            viewer = self._default_viewer(self._app, self._main_window)
        label = TabLabel(self, viewer, None, _("(Untitled)"))
        label.connect("new-name", lambda w, text:
                      self._on_new_tab_name(viewer, text))
        self._tabs.append_page(viewer, label)
        self._tabs.set_tab_reorderable(viewer, True)
        self._tab_names[viewer] = None
        viewer.show_all()

        # setup viewer signals
        self._callbacks[viewer] = [
            viewer.connect("error", lambda w, m, e: self.emit("error", m, e)),
            viewer.connect("status", lambda w, m, b:
                           self.emit("status", m, b)),
            viewer.connect("window-request", lambda w, t:
                           self.emit("window-request", t)),
            viewer.connect("current-node", self.on_tab_current_node),
            viewer.connect("modified", self.on_tab_modified)]

        # load app pref
        viewer.load_preferences(self._app.pref, True)

        # set notebook and node, if requested
        if init == "current_node":
            # replicate current view
            old_viewer = self._current_viewer
            if old_viewer is not None:
                viewer.set_notebook(old_viewer.get_notebook())
                node = old_viewer.get_current_node()
                if node:
                    viewer.goto_node(node)
        elif init == "none":
            pass
        else:
            raise Exception("unknown init")

        # switch to the new tab
        self._tabs.set_current_page(self._tabs.get_n_pages() - 1)

    def close_viewer(self, viewer):
        self.close_tab(self._tabs.page_num(viewer))

    def close_tab(self, pos=None):
        """Close a tab"""
        # do not close last tab
        if self._tabs.get_n_pages() <= 1:
            return

        # determine tab to close
        if pos is None:
            pos = self._tabs.get_current_page()
        viewer = self._tabs.get_nth_page(pos)

        # clean up viewer
        viewer.set_notebook(None)
        for callid in self._callbacks[viewer]:
            viewer.disconnect(callid)
        del self._callbacks[viewer]
        del self._tab_names[viewer]
        self._main_window.remove_viewer(viewer)

        # clean up possible ui
        if pos == self._tabs.get_current_page():
            viewer.remove_ui(self._main_window)
            self._current_viewer = None

        # perform removal from notebook
        self._tabs.remove_page(pos)

    def _on_switch_tab(self, tabs, page, page_num):
        """Callback for switching between tabs"""
        if not self._ui_ready:
            self._current_viewer = self._tabs.get_nth_page(page_num)
            return

        # remove old tab ui
        if self._current_viewer:
            self._current_viewer.remove_ui(self._main_window)

        # add new tab ui
        self._current_viewer = self._tabs.get_nth_page(page_num)
        self._current_viewer.add_ui(self._main_window)

        # notify listeners of new current tab
        def func():
            self.emit("current-node", self._current_viewer.get_current_node())
            notebook = self._current_viewer.get_notebook()
            if notebook:
                self.emit("modified", notebook.save_needed())
            else:
                self.emit("modified", False)
        gobject.idle_add(func)

    def _on_tab_added(self, tabs, child, page_num):
        """Callback when a tab is added"""
        # ensure that tabs are shown if npages > 1, else hidden
        self._tabs.set_show_tabs(self._tabs.get_n_pages() > 1)

    def _on_tab_removed(self, tabs, child, page_num):
        """Callback when a tab is added"""
        # ensure that tabs are shown if npages > 1, else hidden
        self._tabs.set_show_tabs(self._tabs.get_n_pages() > 1)

    def on_tab_current_node(self, viewer, node):
        """Callback for when a viewer wants to set its title"""

        # get node title
        if node is None:
            if viewer.get_notebook():
                title = viewer.get_notebook().get_attr("title", "")
                icon = None
            else:
                title = _("(Untitled)")
                icon = None
        else:
            title = node.get_attr("title", "")
            icon = get_node_icon(node, expand=False)

        # truncate title
        MAX_TITLE = 20
        if len(title) > MAX_TITLE - 3:
            title = title[:MAX_TITLE-3] + "..."

        # set tab label with node title
        tab = self._tabs.get_tab_label(viewer)
        if self._tab_names[viewer] is None:
            # only update tab title if it does not have a name already
            tab.set_text(title)
        tab.set_icon(icon)

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

    def _on_button_press(self, widget, event):
        if (self.get_toplevel().get_focus() == self._tabs and
                event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS):
            # double click, start tab name editing
            label = self._tabs.get_tab_label(self._tabs.get_nth_page(
                self._tabs.get_current_page()))
            label.start_editing()

    def _on_new_tab_name(self, viewer, name):
        """Callback for when a tab gets a new name"""
        if name == "":
            name = None
        self._tab_names[viewer] = name

        if name is None:
            self.on_tab_current_node(viewer, viewer.get_current_node())

    #==============================================

    def set_notebook(self, notebook):
        """Set the notebook for the viewer"""
        if notebook is None:
            # clear the notebook in the viewer
            return self._current_viewer.set_notebook(notebook)

        # restore saved tabs
        tabs = notebook.pref.get("viewers", "ids", self._viewerid,
                                 "tabs", default=[])

        if len(tabs) == 0:
            # no tabs to restore
            if self._current_viewer.get_notebook():
                # create one new tab
                self.new_tab(init="none")
            return self._current_viewer.set_notebook(notebook)

        for tab in tabs:
            # TODO: add check for unknown type
            viewer_type = self._viewer_lookup.get1(tab.get("viewer_type", ""))
            viewer = self._current_viewer

            if viewer.get_notebook() or type(viewer) != viewer_type:
                # create new tab if notebook already loaded or
                # viewer type does not match
                viewer = (
                    viewer_type(self._app, self._main_window,
                                tab.get("viewerid", None))
                    if viewer_type else None)
                self.new_tab(viewer, init="none")
            else:
                # no notebook loaded, so adopt viewerid
                viewer.set_id(tab.get("viewerid", None))

            # set notebook and node
            viewer.set_notebook(notebook)

            # set tab name
            name = tab.get("name", "")
            if name:
                self._tab_names[viewer] = name
                self._tabs.get_tab_label(viewer).set_text(name)

        # set tab focus
        current_id = notebook.pref.get(
            "viewers", "ids",  self._viewerid,
            "current_viewer", default="")
        for i, viewer in enumerate(self.iter_viewers()):
            if viewer.get_id() == current_id:
                self._tabs.set_current_page(i)
                break

    def get_notebook(self):
        return self._current_viewer.get_notebook()

    def close_notebook(self, notebook):

        # progate close notebook
        closed_tabs = []
        for i, viewer in enumerate(self.iter_viewers()):
            notebook2 = viewer.get_notebook()
            viewer.close_notebook(notebook)

            if notebook2 is not None and viewer.get_notebook() is None:
                closed_tabs.append(i)

        # close tabs
        for pos in reversed(closed_tabs):
            self.close_tab(pos)

    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""
        for viewer in self.iter_viewers():
            viewer.load_preferences(app_pref, first_open)

    def save_preferences(self, app_pref):
        """Save application preferences"""
        # TODO: loop through all viewers to save app_pref
        self._current_viewer.save_preferences(app_pref)

    def save(self):
        """Save the current notebook"""
        notebooks = set()

        for viewer in self.iter_viewers():
            viewer.save()

            # add to list of all notebooks
            notebook = viewer.get_notebook()
            if notebook:
                notebooks.add(notebook)

        # clear tab info for all open notebooks
        for notebook in notebooks:
            tabs = notebook.pref.get("viewers", "ids", self._viewerid, "tabs",
                                     default=[])
            tabs[:] = []

        current_viewer = self._current_viewer

        # record tab info
        for viewer in self.iter_viewers():
            notebook = viewer.get_notebook()
            if notebook:
                tabs = notebook.pref.get(
                    "viewers", "ids", self._viewerid, "tabs")
                #node = viewer.get_current_node()
                name = self._tab_names[viewer]
                tabs.append(
                    {"viewer_type": viewer.get_name(),
                     "viewerid": viewer.get_id(),
                     "name": name if name is not None else ""})

                # mark current viewer
                if viewer == current_viewer:
                    notebook.pref.set("viewers", "ids", self._viewerid,
                                      "current_viewer", viewer.get_id())

    def undo(self):
        """Undo the last action in the viewer"""
        return self._current_viewer.undo()

    def redo(self):
        """Redo the last action in the viewer"""
        return self._current_viewer.redo()

    def get_editor(self):
        return self._current_viewer.get_editor()

    #===============================================
    # node operations

    def new_node(self, kind, pos, parent=None):
        return self._current_viewer.new_node(kind, pos, parent)

    def get_current_node(self):
        """Returns the currently focused page"""
        return self._current_viewer.get_current_node()

    def get_selected_nodes(self):
        """
        Returns (nodes, widget) where 'nodes' are a list of selected nodes
        in widget 'widget'
        """
        return self._current_viewer.get_selected_nodes()

    def goto_node(self, node, direct=False):
        """Move view focus to a particular node"""
        return self._current_viewer.goto_node(node, direct)

    def visit_history(self, offset):
        """Visit a node in the viewer's history"""
        self._current_viewer.visit_history(offset)

    #============================================
    # Search

    def start_search_result(self):
        """Start a new search result"""
        return self._current_viewer.start_search_result()

    def add_search_result(self, node):
        """Add a search result"""
        return self._current_viewer.add_search_result(node)

    def end_search_result(self):
        """Start a new search result"""
        return self._current_viewer.end_search_result()

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

        self._current_viewer.add_ui(window)

    def remove_ui(self, window):
        """Remove the view's UI from a window"""
        assert window == self._main_window
        self._ui_ready = False
        self._current_viewer.remove_ui(window)

        for ui in reversed(self._uis):
            self._main_window.get_uimanager().remove_ui(ui)
        self._uis = []

        self._main_window.get_uimanager().remove_action_group(
            self._action_group)

    def _get_ui(self):

        return ["""
<ui>

<!-- main window menu bar -->
<menubar name="main_menu_bar">
  <menu action="Go">
    <placeholder name="Viewer">
      <menuitem action="Next Tab"/>
      <menuitem action="Previous Tab"/>
      <separator/>
    </placeholder>
  </menu>

  <menu action="Window">
    <placeholder name="Viewer Window">
      <menuitem action="New Tab"/>
      <menuitem action="Close Tab"/>
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
             "<control>Page_Up", _("Switch to previous tab"),
             lambda w: self.switch_tab(-1))

            ])
        return actions


class TabLabel (gtk.HBox):

    def __init__(self, tabs, viewer, icon, text):
        gtk.HBox.__init__(self, False, 2)

        #self.name = None

        self.tabs = tabs
        self.viewer = viewer

        # icon
        self.icon = gtk.Image()
        if icon:
            self.icon.set_from_pixbuf(icon)
        self.icon.show()

        # label
        self.label = gtk.Label(text)
        self.label.set_alignment(0, .5)
        self.label.show()

        # entry
        self.entry = gtk.Entry()
        self.entry.set_alignment(0)
        self.entry.connect("focus-out-event", lambda w, e: self.stop_editing())
        self.entry.connect("editing-done", self._done)
        self._editing = False

        # close button
        self.close_button_state = [gtk.STATE_NORMAL]

        def highlight(w, state):
            self.close_button_state[0] = w.get_state()
            w.set_state(state)

        self.eclose_button = gtk.EventBox()
        self.close_button = keepnote.gui.get_resource_image("close_tab.png")
        self.eclose_button.add(self.close_button)
        self.eclose_button.show()

        self.close_button.set_alignment(0, .5)
        self.eclose_button.connect(
            "enter-notify-event",
            lambda w, e: highlight(w, gtk.STATE_PRELIGHT))
        self.eclose_button.connect(
            "leave-notify-event",
            lambda w, e: highlight(w, self.close_button_state[0]))
        self.close_button.show()

        self.eclose_button.connect("button-press-event", lambda w, e:
                                   self.tabs.close_viewer(self.viewer)
                                   if e.button == 1 else None)

        # layout
        self.pack_start(self.icon, False, False, 0)
        self.pack_start(self.label, True, True, 0)
        self.pack_start(self.eclose_button, False, False, 0)

    def _done(self, widget):

        text = self.entry.get_text()
        self.stop_editing()
        self.label.set_label(text)
        self.emit("new-name", text)

    def start_editing(self):

        if not self._editing:
            self._editing = True
            w, h = self.label.get_child_requisition()
            self.remove(self.label)
            self.entry.set_text(self.label.get_label())
            self.pack_start(self.entry, True, True, 0)
            self.reorder_child(self.entry, 1)
            self.entry.set_size_request(w, h)
            self.entry.show()
            self.entry.grab_focus()
            self.entry.start_editing(gtk.gdk.Event(gtk.gdk.NOTHING))

    def stop_editing(self):
        if self._editing:
            self._editing = False
            self.remove(self.entry)
            self.pack_start(self.label, True, True, 0)
            self.reorder_child(self.label, 1)
            self.label.show()

    def set_text(self, text):
        if not self._editing:
            self.label.set_text(text)

    def set_icon(self, pixbuf):
        self.icon.set_from_pixbuf(pixbuf)


gobject.type_register(TabLabel)
gobject.signal_new("new-name", TabLabel, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
