"""

    KeepNote
    Classic three-paned viewer for KeepNote.

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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
import gobject
import gtk

# keepnote imports
import keepnote
from keepnote.notebook import NoteBookError
from keepnote.gui import \
    add_actions, \
    Action, \
    CONTEXT_MENU_ACCEL_PATH, \
    DEFAULT_COLORS
from keepnote import notebook as notebooklib
from keepnote.gui import richtext
from keepnote.gui.richtext import RichTextError
from keepnote.gui.treeview import KeepNoteTreeView
from keepnote.gui.listview import KeepNoteListView
from keepnote.gui.editor_richtext import RichTextEditor
from keepnote.gui.editor_text import TextEditor
from keepnote.gui.editor_multi import ContentEditor
from keepnote.gui.icon_menu import IconMenu
from keepnote.gui.viewer import Viewer
from keepnote.gui.icons import lookup_icon_filename
from keepnote.gui.colortool import ColorMenu


_ = keepnote.translate


DEFAULT_VSASH_POS = 200
DEFAULT_HSASH_POS = 200
DEFAULT_VIEW_MODE = "vertical"


class ThreePaneViewer (Viewer):
    """A viewer with a treeview, listview, and editor"""

    def __init__(self, app, main_window, viewerid=None):
        Viewer.__init__(self, app, main_window, viewerid,
                        viewer_name="three_pane_viewer")
        self._ui_ready = False

        # node selections
        self._current_page = None      # current page in editor
        self._treeview_sel_nodes = []  # current selected nodes in treeview
        self._queue_list_select = []   # nodes to select in listview after
                                       # treeview change
        self._new_page_occurred = False
        self.back_button = None
        self._view_mode = DEFAULT_VIEW_MODE

        self.connect("history-changed", self._on_history_changed)

        #=========================================
        # widgets

        # treeview
        self.treeview = KeepNoteTreeView()
        self.treeview.set_get_node(self._app.get_node)
        self.treeview.connect("select-nodes", self._on_tree_select)
        self.treeview.connect("delete-node", self.on_delete_node)
        self.treeview.connect("error", lambda w, t, e:
                              self.emit("error", t, e))
        self.treeview.connect("edit-node", self._on_edit_node)
        self.treeview.connect("goto-node", self.on_goto_node)
        self.treeview.connect("activate-node", self.on_activate_node)
        self.treeview.connect("drop-file", self._on_attach_file)

        # listview
        self.listview = KeepNoteListView()
        self.listview.set_get_node(self._app.get_node)
        self.listview.connect("select-nodes", self._on_list_select)
        self.listview.connect("delete-node", self.on_delete_node)
        self.listview.connect("goto-node", self.on_goto_node)
        self.listview.connect("activate-node", self.on_activate_node)
        self.listview.connect("goto-parent-node",
                              lambda w: self.on_goto_parent_node())
        self.listview.connect("error", lambda w, t, e:
                              self.emit("error", t, e))
        self.listview.connect("edit-node", self._on_edit_node)
        self.listview.connect("drop-file", self._on_attach_file)
        self.listview.on_status = self.set_status  # TODO: clean up

        # editor
        #self.editor = KeepNoteEditor(self._app)
        #self.editor = RichTextEditor(self._app)
        self.editor = ContentEditor(self._app)
        rich_editor = RichTextEditor(self._app)
        self.editor.add_editor("text/xhtml+xml", rich_editor)
        self.editor.add_editor("text", TextEditor(self._app))
        self.editor.set_default_editor(rich_editor)

        self.editor.connect("view-node", self._on_editor_view_node)
        self.editor.connect("child-activated", self._on_child_activated)
        self.editor.connect("visit-node", lambda w, n:
                            self.goto_node(n, False))
        self.editor.connect("error", lambda w, t, e: self.emit("error", t, e))
        self.editor.connect("window-request", lambda w, t:
                            self.emit("window-request", t))
        self.editor.view_nodes([])

        self.editor_pane = gtk.VBox(False, 5)
        self.editor_pane.pack_start(self.editor, True, True, 0)

        #=====================================
        # layout

        # TODO: make sure to add underscore for these variables

        # create a horizontal paned widget
        self.hpaned = gtk.HPaned()
        self.pack_start(self.hpaned, True, True, 0)
        self.hpaned.set_position(DEFAULT_HSASH_POS)

        # layout major widgets
        self.paned2 = gtk.VPaned()
        self.hpaned.add2(self.paned2)
        self.paned2.set_position(DEFAULT_VSASH_POS)

        # treeview and scrollbars
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.treeview)
        self.hpaned.add1(sw)

        # listview with scrollbars
        self.listview_sw = gtk.ScrolledWindow()
        self.listview_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.listview_sw.set_shadow_type(gtk.SHADOW_IN)
        self.listview_sw.add(self.listview)
        self.paned2.add1(self.listview_sw)
        #self.paned2.child_set_property(self.listview_sw, "shrink", True)

        # layout editor
        self.paned2.add2(self.editor_pane)

        self.treeview.grab_focus()

    def set_notebook(self, notebook):
        """Set the notebook for the viewer"""
        # add/remove reference to notebook
        self._app.ref_notebook(notebook)
        if self._notebook is not None:
            self._app.unref_notebook(self._notebook)

        # deregister last notebook, if it exists
        if self._notebook:
            self._notebook.node_changed.remove(
                self.on_notebook_node_changed)

        # setup listeners
        if notebook:
            notebook.node_changed.add(self.on_notebook_node_changed)

        # set notebook
        self._notebook = notebook
        self.editor.set_notebook(notebook)
        self.listview.set_notebook(notebook)
        self.treeview.set_notebook(notebook)

        if self.treeview.get_popup_menu():
            self.treeview.get_popup_menu().iconmenu.set_notebook(notebook)
            self.listview.get_popup_menu().iconmenu.set_notebook(notebook)

            colors = (self._notebook.pref.get("colors", default=DEFAULT_COLORS)
                      if self._notebook else DEFAULT_COLORS)
            self.treeview.get_popup_menu().fgcolor_menu.set_colors(colors)
            self.treeview.get_popup_menu().bgcolor_menu.set_colors(colors)
            self.listview.get_popup_menu().fgcolor_menu.set_colors(colors)
            self.listview.get_popup_menu().bgcolor_menu.set_colors(colors)

        # restore selections
        self._load_selections()

        # put focus on treeview
        self.treeview.grab_focus()

    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""
        p = app_pref.get("viewers", "three_pane_viewer", define=True)
        self.set_view_mode(p.get("view_mode", DEFAULT_VIEW_MODE))
        self.paned2.set_property("position-set", True)
        self.hpaned.set_property("position-set", True)
        self.paned2.set_position(p.get("vsash_pos", DEFAULT_VSASH_POS))
        self.hpaned.set_position(p.get("hsash_pos", DEFAULT_HSASH_POS))

        self.listview.load_preferences(app_pref, first_open)

        try:
            # if this version of GTK doesn't have tree-lines, ignore it
            self.treeview.set_property(
                "enable-tree-lines",
                app_pref.get("look_and_feel", "treeview_lines", default=True))
        except:
            pass

        self.editor.load_preferences(app_pref, first_open)

        # reload ui
        if self._ui_ready:
            self.remove_ui(self._main_window)
            self.add_ui(self._main_window)

    def save_preferences(self, app_pref):
        """Save application preferences"""
        p = app_pref.get("viewers", "three_pane_viewer")
        p["view_mode"] = self._view_mode
        p["vsash_pos"] = self.paned2.get_position()
        p["hsash_pos"] = self.hpaned.get_position()

        self.listview.save_preferences(app_pref)
        self.editor.save_preferences(app_pref)

    def save(self):
        """Save the current notebook"""
        self.listview.save()
        self.editor.save()
        self._save_selections()

    def on_notebook_node_changed(self, nodes):
        """Callback for when notebook node is changed"""
        self.emit("modified", True)

    def undo(self):
        """Undo the last action in the viewer"""
        self.editor.undo()

    def redo(self):
        """Redo the last action in the viewer"""
        self.editor.redo()

    def get_editor(self):
        """Returns node editor"""
        return self.editor.get_editor()

    def set_status(self, text, bar="status"):
        """Set a status message"""
        self.emit("status", text, bar)

    def set_view_mode(self, mode):
        """
        Sets view mode for ThreePaneViewer

        modes:
            "vertical"
            "horizontal"
        """
        vsash = self.paned2.get_position()

        # detach widgets
        self.paned2.remove(self.listview_sw)
        self.paned2.remove(self.editor_pane)
        self.hpaned.remove(self.paned2)

        # remake paned2
        if mode == "vertical":
            # create a vertical paned widget
            self.paned2 = gtk.VPaned()
        else:
            # create a horizontal paned widget
            self.paned2 = gtk.HPaned()

        self.paned2.set_position(vsash)
        self.paned2.show()

        self.hpaned.add2(self.paned2)
        self.hpaned.show()

        self.paned2.add1(self.listview_sw)
        self.paned2.add2(self.editor_pane)

        # record preference
        self._view_mode = mode

    def _load_selections(self):
        """Load previous node selections from notebook preferences"""
        if self._notebook:
            info = self._notebook.pref.get("viewers", "ids",
                                           self._viewerid, define=True)

            # load selections
            nodes = [node for node in (
                self._notebook.get_node_by_id(i)
                for i in info.get("selected_treeview_nodes", []))
                if node is not None]
            self.treeview.select_nodes(nodes)
            nodes = [node for node in (
                self._notebook.get_node_by_id(i)
                for i in info.get("selected_listview_nodes", []))
                if node is not None]

            self.listview.select_nodes(nodes)

    def _save_selections(self):
        """Save node selections into notebook preferences"""
        if self._notebook is not None:
            info = self._notebook.pref.get("viewers", "ids",
                                           self._viewerid, define=True)

            # save selections
            info["selected_treeview_nodes"] = [
                node.get_attr("nodeid")
                for node in self.treeview.get_selected_nodes()]
            info["selected_listview_nodes"] = [
                node.get_attr("nodeid")
                for node in self.listview.get_selected_nodes()]
            self._notebook.set_preferences_dirty()

    #===============================================
    # node operations

    def get_current_node(self):
        """Returns the currently focused page"""
        return self._current_page

    def get_selected_nodes(self):
        """
        Returns  a list of selected nodes.
        """
        if self.treeview.is_focus():
            return self.treeview.get_selected_nodes()
        else:
            nodes = self.listview.get_selected_nodes()
            if len(nodes) == 0:
                return self.treeview.get_selected_nodes()
            else:
                return nodes

    def _on_history_changed(self, viewer, history):
        """Callback for when node browse history changes"""
        if self._ui_ready and self.back_button:
            self.back_button.set_sensitive(history.has_back())
            self.forward_button.set_sensitive(history.has_forward())

    def get_focused_widget(self, default=None):
        """Returns the currently focused widget"""
        if self.treeview.is_focus():
            return self.treeview
        if self.listview.is_focus():
            return self.listview
        else:
            return default

    def on_delete_node(self, widget, nodes=None):
        """Callback for deleting a node"""
        # get node to delete
        if nodes is None:
            nodes = self.get_selected_nodes()

        if len(nodes) == 0:
            return

        if self._main_window.confirm_delete_nodes(nodes):
            # change selection
            if len(nodes) == 1:
                node = nodes[0]
                widget = self.get_focused_widget(self.listview)
                parent = node.get_parent()
                children = parent.get_children()
                i = children.index(node)

                if i < len(children) - 1:
                    widget.select_nodes([children[i+1]])
                else:
                    widget.select_nodes([parent])
            else:
                widget = self.get_focused_widget(self.listview)
                widget.select_nodes([])

            # perform delete
            try:
                for node in nodes:
                    node.trash()
            except NoteBookError, e:
                self.emit("error", e.msg, e)

    def _on_editor_view_node(self, editor, node):
        """Callback for when editor views a node"""
        # record node in history
        self._history.add(node.get_attr("nodeid"))
        self.emit("history-changed", self._history)

    def _on_child_activated(self, editor, textview, child):
        """Callback for when child widget in editor is activated"""
        if self._current_page and isinstance(child, richtext.RichTextImage):
            filename = self._current_page.get_file(child.get_filename())
            self._app.run_external_app("image_viewer", filename)

    def _on_tree_select(self, treeview, nodes):
        """Callback for treeview selection change"""
        # do nothing if selection is unchanged
        if self._treeview_sel_nodes == nodes:
            return

        # remember which nodes are selected in the treeview
        self._treeview_sel_nodes = nodes

        # view the children of these nodes in the listview
        self.listview.view_nodes(nodes)

        # if nodes are queued for selection in listview (via goto parent)
        # then select them here
        if len(self._queue_list_select) > 0:
            self.listview.select_nodes(self._queue_list_select)
            self._queue_list_select = []

        # make sure nodes are also selected in listview
        self.listview.select_nodes(nodes)

    def _on_list_select(self, listview, nodes):
        """Callback for listview selection change"""
        # remember the selected node
        if len(nodes) == 1:
            self._current_page = nodes[0]
        else:
            self._current_page = None

        try:
            self.editor.view_nodes(nodes)
        except RichTextError, e:
            self.emit("error",
                      "Could not load page '%s'." % nodes[0].get_title(), e)

        self.emit("current-node", self._current_page)

    def on_goto_node(self, widget, node):
        """Focus view on a node"""
        self.goto_node(node, direct=False)

    def on_activate_node(self, widget, node):
        """Focus view on a node"""
        if self.viewing_search():
            # if we are in a search, goto node, but not directly
            self.goto_node(node, direct=False)
        else:
            if node and node.has_attr("payload_filename"):
                # open attached file
                self._main_window.on_view_node_external_app("file_launcher",
                                                            node,
                                                            kind="file")
            else:
                # goto node directly
                self.goto_node(node, direct=True)

    def on_goto_parent_node(self, node=None):
        """Focus view on a node's parent"""
        if node is None:
            nodes = self.get_selected_nodes()
            if len(nodes) == 0:
                return
            node = nodes[0]

        # get parent
        parent = node.get_parent()
        if parent is not None:
            self.goto_node(parent, direct=False)

    def _on_edit_node(self, widget, node, attr, value):
        """Callback for title edit finishing"""
        # move cursor to editor after new page has been created
        if self._new_page_occurred:
            self._new_page_occurred = False

            if node.get_attr("content_type") != notebooklib.CONTENT_TYPE_DIR:
                self.goto_editor()

    def _on_attach_file(self, widget, parent, index, uri):
        """Attach document"""
        self._app.attach_file(uri, parent, index)

    def _on_attach_file_menu(self):
        """Callback for attach file action"""

        nodes = self.get_selected_nodes()
        if len(nodes) > 0:
            node = nodes[0]
            self._app.on_attach_file(node, self.get_toplevel())

    def new_node(self, kind, pos, parent=None):
        """Add a new node to the notebook"""

        # TODO: think about where this goes

        if self._notebook is None:
            return

        self.treeview.cancel_editing()
        self.listview.cancel_editing()

        if parent is None:
            nodes = self.get_selected_nodes()
            if len(nodes) == 1:
                parent = nodes[0]
            else:
                parent = self._notebook

        node = Viewer.new_node(self, kind, pos, parent)

        self._view_new_node(node)

    def on_new_dir(self):
        """Add new folder near selected nodes"""
        self.new_node(notebooklib.CONTENT_TYPE_DIR, "sibling")

    def on_new_page(self):
        """Add new page near selected nodes"""
        self.new_node(notebooklib.CONTENT_TYPE_PAGE, "sibling")

    def on_new_child_page(self):
        """Add new page as child of selected nodes"""
        self.new_node(notebooklib.CONTENT_TYPE_PAGE, "child")

    def _view_new_node(self, node):
        """View a node particular widget"""

        self._new_page_occurred = True

        self.goto_node(node)

        if node in self.treeview.get_selected_nodes():
            self.treeview.edit_node(node)
        else:
            self.listview.edit_node(node)

    def _on_rename_node(self):
        """Callback for renaming a node"""
        nodes = self.get_selected_nodes()

        if len(nodes) == 0:
            return

        widget = self.get_focused_widget(self.listview)
        widget.edit_node(nodes[0])

    def goto_node(self, node, direct=False):
        """Move view focus to a particular node"""

        if node is None:
            # default node is the one selected in the listview
            nodes = self.listview.get_selected_nodes()
            if len(nodes) == 0:
                return
            node = nodes[0]

        if direct:
            # direct goto: open up treeview all the way to the node
            self.treeview.select_nodes([node])
        else:
            # indirect goto: do not open up treeview, only listview

            treenodes = self.treeview.get_selected_nodes()

            # get path to root
            path = []
            ptr = node
            while ptr:
                if ptr in treenodes:
                    # if parent path is already selected then quit
                    path = []
                    break
                path.append(ptr)
                ptr = ptr.get_parent()

            # find first node that is collapsed
            node2 = None
            for node2 in reversed(path):
                if not self.treeview.is_node_expanded(node2):
                    break

            # make selections
            if node2:
                self.treeview.select_nodes([node2])

            # This test might be needed for windows crash
            if node2 != node:
                self.listview.select_nodes([node])

    def goto_next_node(self):
        """Move focus to the 'next' node"""

        widget = self.get_focused_widget(self.treeview)
        path, col = widget.get_cursor()

        if path:
            path2 = path[:-1] + (path[-1] + 1,)

            if len(path) > 1:
                it = widget.get_model().get_iter(path[:-1])
                nchildren = widget.get_model().iter_n_children(it)
            else:
                nchildren = widget.get_model().iter_n_children(None)

            if path2[-1] < nchildren:
                widget.set_cursor(path2)

    def goto_prev_node(self):
        """Move focus to the 'previous' node"""
        widget = self.get_focused_widget(self.treeview)
        path, col = widget.get_cursor()

        if path and path[-1] > 0:
            path2 = path[:-1] + (path[-1] - 1,)
            widget.set_cursor(path2)

    def expand_node(self, all=False):
        """Expand the tree beneath the focused node"""
        widget = self.get_focused_widget(self.treeview)
        path, col = widget.get_cursor()

        if path:
            widget.expand_row(path, all)

    def collapse_node(self, all=False):
        """Collapse the tree beneath the focused node"""
        widget = self.get_focused_widget(self.treeview)
        path, col = widget.get_cursor()

        if path:
            if all:
                # recursively collapse all notes
                widget.collapse_all_beneath(path)
            else:
                widget.collapse_row(path)

    def on_copy_tree(self):
        """Callback for copy on whole tree"""
        widget = self._main_window.get_focus()
        if gobject.signal_lookup("copy-tree-clipboard", widget) != 0:
            widget.emit("copy-tree-clipboard")

    #============================================
    # Search

    def start_search_result(self):
        """Start a new search result"""
        self.treeview.select_nodes([])
        self.listview.view_nodes([], nested=False)

    def add_search_result(self, node):
        """Add a search result"""
        self.listview.append_node(node)

    def end_search_result(self):
        """End a search result"""

        # select top result
        try:
            self.listview.get_selection().select_path((0,))
        except:
            # don't worry if there isn't anything to select
            pass

    def viewing_search(self):
        """Returns True if we are currently viewing a search result"""
        return (len(self.treeview.get_selected_nodes()) == 0 and
                len(self.listview.get_selected_nodes()) > 0)

    #=============================================
    # Goto functions

    def goto_treeview(self):
        """Switch focus to TreeView"""
        self.treeview.grab_focus()

    def goto_listview(self):
        """Switch focus to ListView"""
        self.listview.grab_focus()

    def goto_editor(self):
        """Switch focus to Editor"""
        self.editor.grab_focus()

    #===========================================
    # ui

    def add_ui(self, window):
        """Add the view's UI to a window"""

        assert window == self._main_window

        self._ui_ready = True
        self._action_group = gtk.ActionGroup("Viewer")
        self._uis = []
        add_actions(self._action_group, self._get_actions())
        self._main_window.get_uimanager().insert_action_group(
            self._action_group, 0)

        for s in self._get_ui():
            self._uis.append(
                self._main_window.get_uimanager().add_ui_from_string(s))

        uimanager = self._main_window.get_uimanager()
        uimanager.ensure_update()

        # setup toolbar
        self.back_button = uimanager.get_widget("/main_tool_bar/Viewer/Back")
        self.forward_button = uimanager.get_widget(
            "/main_tool_bar/Viewer/Forward")

        # setup editor
        self.editor.add_ui(window)

        # TODO: Try to add accellerator to popup menu
        #menu = viewer.editor.get_textview().get_popup_menu()
        #menu.set_accel_group(self._accel_group)
        #menu.set_accel_path(CONTEXT_MENU_ACCEL_PATH)

        # treeview context menu
        menu1 = uimanager.get_widget(
            "/popup_menus/treeview_popup").get_submenu()
        self.treeview.set_popup_menu(menu1)
        menu1.set_accel_path(CONTEXT_MENU_ACCEL_PATH)
        menu1.set_accel_group(uimanager.get_accel_group())

        # treeview icon menu
        menu1.iconmenu = self._setup_icon_menu()
        item = uimanager.get_widget(
            "/popup_menus/treeview_popup/Change Note Icon")
        item.set_submenu(menu1.iconmenu)
        item.show()

        # treeview fg color menu
        menu1.fgcolor_menu = self._setup_color_menu("fg")
        item = uimanager.get_widget(
            "/popup_menus/treeview_popup/Change Fg Color")
        item.set_submenu(menu1.fgcolor_menu)
        item.show()

        # treeview bg color menu
        menu1.bgcolor_menu = self._setup_color_menu("bg")
        item = uimanager.get_widget(
            "/popup_menus/treeview_popup/Change Bg Color")
        item.set_submenu(menu1.bgcolor_menu)
        item.show()

        # listview context menu
        menu2 = uimanager.get_widget(
            "/popup_menus/listview_popup").get_submenu()
        self.listview.set_popup_menu(menu2)
        menu2.set_accel_group(uimanager.get_accel_group())
        menu2.set_accel_path(CONTEXT_MENU_ACCEL_PATH)

        # listview icon menu
        menu2.iconmenu = self._setup_icon_menu()
        item = uimanager.get_widget(
            "/popup_menus/listview_popup/Change Note Icon")
        item.set_submenu(menu2.iconmenu)
        item.show()

        # listview fg color menu
        menu2.fgcolor_menu = self._setup_color_menu("fg")
        item = uimanager.get_widget(
            "/popup_menus/listview_popup/Change Fg Color")
        item.set_submenu(menu2.fgcolor_menu)
        item.show()

        # listview bg color menu
        menu2.bgcolor_menu = self._setup_color_menu("bg")
        item = uimanager.get_widget(
            "/popup_menus/listview_popup/Change Bg Color")
        item.set_submenu(menu2.bgcolor_menu)
        item.show()

    def _setup_icon_menu(self):
        """Setup the icon menu"""
        iconmenu = IconMenu()
        iconmenu.connect(
            "set-icon",
            lambda w, i: self._app.on_set_icon(
                i, u"", self.get_selected_nodes()))
        iconmenu.new_icon.connect(
            "activate",
            lambda w: self._app.on_new_icon(
                self.get_selected_nodes(), self._notebook,
                self._main_window))
        iconmenu.set_notebook(self._notebook)

        return iconmenu

    def _setup_color_menu(self, kind):
        """Setup the icon menu"""

        def on_set_color(w, color):
            for node in self.get_selected_nodes():
                if kind == "fg":
                    attr = "title_fgcolor"
                else:
                    attr = "title_bgcolor"
                if color:
                    node.set_attr(attr, color)
                else:
                    node.del_attr(attr)

        def on_set_colors(w, colors):
            if self._notebook:
                self._notebook.pref.set("colors", list(colors))
                self._app.get_listeners("colors_changed").notify(
                    self._notebook, colors)

        def on_new_colors(notebook, colors):
            if self._notebook == notebook:
                menu.set_colors(colors)

        colors = self._notebook.pref.get("colors", default=DEFAULT_COLORS) \
            if self._notebook else DEFAULT_COLORS

        menu = ColorMenu(colors)

        menu.connect("set-color", on_set_color)
        menu.connect("set-colors", on_set_colors)
        self._app.get_listeners("colors_changed").add(on_new_colors)

        return menu

    def remove_ui(self, window):
        """Remove the view's UI from a window"""

        assert self._main_window == window

        self._ui_ready = False
        self.editor.remove_ui(self._main_window)

        for ui in reversed(self._uis):
            self._main_window.get_uimanager().remove_ui(ui)
        self._uis = []

        self._main_window.get_uimanager().ensure_update()
        self._main_window.get_uimanager().remove_action_group(
            self._action_group)
        self._action_group = None

    def _get_ui(self):
        """Returns the UI XML"""

        # NOTE: I use a dummy menubar popup_menus so that I can have
        # accelerators on the menus.  It is a hack.

        return ["""
        <ui>
        <menubar name="main_menu_bar">
          <menu action="File">
            <placeholder name="Viewer">
              <menuitem action="New Page"/>
              <menuitem action="New Child Page"/>
              <menuitem action="New Folder"/>
            </placeholder>
          </menu>

          <menu action="Edit">
            <placeholder name="Viewer">
              <menuitem action="Attach File"/>
              <separator/>
              <placeholder name="Editor"/>
            </placeholder>
          </menu>

          <placeholder name="Viewer">
            <placeholder name="Editor"/>
            <menu action="View">
              <menuitem action="View Note in File Explorer"/>
              <menuitem action="View Note in Text Editor"/>
              <menuitem action="View Note in Web Browser"/>
              <menuitem action="Open File"/>
            </menu>
          </placeholder>
          <menu action="Go">
            <placeholder name="Viewer">
              <menuitem action="Back"/>
              <menuitem action="Forward"/>
              <separator/>
              <menuitem action="Go to Note"/>
              <menuitem action="Go to Parent Note"/>
              <menuitem action="Go to Next Note"/>
              <menuitem action="Go to Previous Note"/>
              <menuitem action="Expand Note"/>
              <menuitem action="Collapse Note"/>
              <menuitem action="Expand All Child Notes"/>
              <menuitem action="Collapse All Child Notes"/>
              <separator/>
              <menuitem action="Go to Tree View"/>
              <menuitem action="Go to List View"/>
              <menuitem action="Go to Editor"/>
              <placeholder name="Editor"/>
            </placeholder>
          </menu>
          <menu action="Tools">
          </menu>
        </menubar>

        <toolbar name="main_tool_bar">
          <placeholder name="Viewer">
            <toolitem action="New Folder"/>
            <toolitem action="New Page"/>
            <separator/>
            <toolitem action="Back"/>
            <toolitem action="Forward"/>
            <separator/>
            <placeholder name="Editor"/>
          </placeholder>
        </toolbar>


        <menubar name="popup_menus">
          <menu action="treeview_popup">
            <menuitem action="New Page"/>
            <menuitem action="New Child Page"/>
            <menuitem action="New Folder"/>
            <menuitem action="Attach File"/>
            <placeholder name="New"/>
            <separator/>
            <menuitem action="Cut"/>
            <menuitem action="Copy"/>
            <menuitem action="Copy Tree"/>
            <menuitem action="Paste"/>
            <separator/>
            <menuitem action="Delete Note"/>
            <menuitem action="Rename Note"/>
            <menuitem action="Change Note Icon"/>
            <menuitem action="Change Fg Color"/>
            <menuitem action="Change Bg Color"/>
            <menu action="View Note As">
              <menuitem action="View Note in File Explorer"/>
              <menuitem action="View Note in Text Editor"/>
              <menuitem action="View Note in Web Browser"/>
              <menuitem action="Open File"/>
            </menu>
          </menu>

          <menu action="listview_popup">
            <menuitem action="Go to Note"/>
            <menuitem action="Go to Parent Note"/>
            <separator/>
            <menuitem action="New Page"/>
            <menuitem action="New Child Page"/>
            <menuitem action="New Folder"/>
            <menuitem action="Attach File"/>
            <placeholder name="New"/>
            <separator/>
            <menuitem action="Cut"/>
            <menuitem action="Copy"/>
            <menuitem action="Copy Tree"/>
            <menuitem action="Paste"/>
            <separator/>
            <menuitem action="Delete Note"/>
            <menuitem action="Rename Note"/>
            <menuitem action="Change Note Icon"/>
            <menuitem action="Change Fg Color"/>
            <menuitem action="Change Bg Color"/>
            <menu action="View Note As">
              <menuitem action="View Note in File Explorer"/>
              <menuitem action="View Note in Text Editor"/>
              <menuitem action="View Note in Web Browser"/>
              <menuitem action="Open File"/>
            </menu>
          </menu>
        </menubar>

        </ui>
        """]

    def _get_actions(self):
        """Returns actions for view's UI"""

        return map(lambda x: Action(*x), [

            ("treeview_popup", None, "", "", None, lambda w: None),
            ("listview_popup", None, "", "", None, lambda w: None),

            ("Copy Tree", gtk.STOCK_COPY, _("Copy _Tree"),
             "<control><shift>C", _("Copy entire tree"),
             lambda w: self.on_copy_tree()),

            ("New Page", gtk.STOCK_NEW, _("New _Page"),
             "<control>N", _("Create a new page"),
             lambda w: self.on_new_page(), "note-new.png"),

            ("New Child Page", gtk.STOCK_NEW, _("New _Child Page"),
             "<control><shift>N", _("Create a new child page"),
             lambda w: self.on_new_child_page(),
             "note-new.png"),

            ("New Folder", gtk.STOCK_DIRECTORY, _("New _Folder"),
             "<control><shift>M", _("Create a new folder"),
             lambda w: self.on_new_dir(),
             "folder-new.png"),

            ("Attach File", gtk.STOCK_ADD, _("_Attach File..."),
             "", _("Attach a file to the notebook"),
             lambda w: self._on_attach_file_menu()),


            ("Back", gtk.STOCK_GO_BACK, _("_Back"), "", None,
             lambda w: self.visit_history(-1)),

            ("Forward", gtk.STOCK_GO_FORWARD, _("_Forward"), "", None,
             lambda w: self.visit_history(1)),

            ("Go to Note", gtk.STOCK_JUMP_TO, _("Go to _Note"),
             "", None,
             lambda w: self.on_goto_node(None, None)),

            ("Go to Parent Note", gtk.STOCK_GO_BACK, _("Go to _Parent Note"),
             "<shift><alt>Left", None,
             lambda w: self.on_goto_parent_node()),

            ("Go to Next Note", gtk.STOCK_GO_DOWN, _("Go to Next N_ote"),
             "<alt>Down", None,
             lambda w: self.goto_next_node()),

            ("Go to Previous Note", gtk.STOCK_GO_UP, _("Go to _Previous Note"),
             "<alt>Up", None,
             lambda w: self.goto_prev_node()),

            ("Expand Note", gtk.STOCK_ADD, _("E_xpand Note"),
             "<alt>Right", None,
             lambda w: self.expand_node()),

            ("Collapse Note", gtk.STOCK_REMOVE, _("_Collapse Note"),
             "<alt>Left", None,
             lambda w: self.collapse_node()),

            ("Expand All Child Notes", gtk.STOCK_ADD,
             _("Expand _All Child Notes"),
             "<shift><alt>Right", None,
             lambda w: self.expand_node(True)),

            ("Collapse All Child Notes", gtk.STOCK_REMOVE,
             _("Collapse A_ll Child Notes"),
             "<shift><alt>Left", None,
             lambda w: self.collapse_node(True)),


            ("Go to Tree View", None, _("Go to _Tree View"),
             "<control>T", None,
             lambda w: self.goto_treeview()),

            ("Go to List View", None, _("Go to _List View"),
             "<control>Y", None,
             lambda w: self.goto_listview()),

            ("Go to Editor", None, _("Go to _Editor"),
             "<control>D", None,
             lambda w: self.goto_editor()),

            ("Delete Note", gtk.STOCK_DELETE, _("_Delete"),
             "", None, self.on_delete_node),

            ("Rename Note", gtk.STOCK_EDIT, _("_Rename"),
             "", None,
             lambda w: self._on_rename_node()),

            ("Change Note Icon", None, _("_Change Note Icon"),
             "", None, lambda w: None,
             lookup_icon_filename(None, u"folder-red.png")),

            ("Change Fg Color", None, _("Change _Fg Color")),

            ("Change Bg Color", None, _("Change _Bg Color")),
        ])
