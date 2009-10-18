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
import os
import subprocess
import traceback
_ = gettext.gettext


# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk
import gobject


# keepnote imports
import keepnote
from keepnote import unicode_gtk, KeepNoteError
from keepnote.notebook import NoteBookTrash
from keepnote.gui import \
    add_actions, \
    dialog_image_resize, \
    get_resource, \
    get_resource_image, \
    get_resource_pixbuf, \
    get_accel_file, \
    Action, \
    ToggleAction, \
    FileChooserDialog, \
    CONTEXT_MENU_ACCEL_PATH
from keepnote.history import NodeHistory
from keepnote import notebook as notebooklib
from keepnote.gui import richtext
from keepnote.gui.richtext import RichTextView, RichTextImage, RichTextError
from keepnote.gui.treeview import KeepNoteTreeView
from keepnote.gui.listview import KeepNoteListView
from keepnote.gui.editor import KeepNoteEditor, EditorMenus
from keepnote.gui.icon_menu import IconMenu
from keepnote.gui.link_editor import LinkEditor
from keepnote import notebook as notebooklib
from keepnote.gui.treemodel import iter_children
from keepnote.gui.viewer import Viewer
from keepnote.gui.icons import \
     lookup_icon_filename




class ThreePaneViewer (Viewer):
    """A viewer with a treeview, listview, and editor"""

    def __init__(self, app, main_window):
        Viewer.__init__(self, app, main_window)


        # node selections        
        self._current_page = None     # current page in editor
        self._treeview_sel_nodes = [] # current selected nodes in treeview
        self._queue_list_select = []  # nodes to select in listview after treeview change
        self._new_page_occurred = False
        self.back_button = None

        self.connect("history-changed", self._on_history_changed)

        #=========================================
        # widgets
        
        # treeview
        self.treeview = KeepNoteTreeView()
        self.treeview.connect("select-nodes", self._on_tree_select)
        self.treeview.connect("delete-node", self.on_delete_node)
        self.treeview.connect("error", lambda w,t,e: self.emit("error", t, e))
        self.treeview.connect("edit-title", self._on_edit_title)
        self.treeview.connect("goto-node", self.on_list_view_node)
        self.treeview.connect("drop-file", self._on_attach_file)
        
        # listview
        self.listview = KeepNoteListView()
        self.listview.connect("select-nodes", self._on_list_select)
        self.listview.connect("delete-node", self.on_delete_node)
        self.listview.connect("goto-node", self.on_list_view_node)
        self.listview.connect("goto-parent-node",
                              lambda w: self.on_list_view_parent_node())
        self.listview.connect("error", lambda w,t,e: self.emit("error", t, e))
        self.listview.connect("edit-title", self._on_edit_title)
        self.listview.connect("drop-file", self._on_attach_file)
        self.listview.on_status = self.set_status  # TODO: clean up
        
        # editor
        self.editor = KeepNoteEditor(self._app)
        self.editor_menus = EditorMenus(self.editor)
        self.editor.connect("make-link", self._on_make_link)
        self.editor.connect("child-activated", self._on_child_activated)
        self.editor.connect("visit-node", lambda w, n: self.goto_node(n, False))
        self.editor.connect("font-change", self.editor_menus.on_font_change)
        self.editor.connect("error", lambda w,t,e: self.emit("error", t, e))
        self.editor.connect("window-request", lambda w,t: 
                            self.emit("window-request", t))
        self.editor.view_pages([])
        
        self.editor_pane = gtk.VBox(False, 5)
        self.editor_pane.pack_start(self.editor, True, True, 0)

        self.link_editor = LinkEditor()
        self.link_editor.set_textview(self.editor.get_textview())
        self.editor.connect("font-change", self.link_editor.on_font_change)
        self.editor.connect("view-node", self._on_editor_view_node)
        self.editor_pane.pack_start(self.link_editor, False, True, 0)
        self.link_editor.set_search_nodes(self.search_nodes)

        self._main_window.make_image_menu(self.editor.get_textview().get_image_menu())

        #=====================================
        # layout

        # TODO: make sure to add underscore for these variables

        # create a horizontal paned widget
        self.hpaned = gtk.HPaned()
        self.pack_start(self.hpaned, True, True, 0)
        self.hpaned.set_position(keepnote.DEFAULT_HSASH_POS)

                
        # layout major widgets
        self.paned2 = gtk.VPaned()
        self.hpaned.add2(self.paned2)
        self.paned2.set_position(keepnote.DEFAULT_VSASH_POS)
        
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
        
        # layout editor
        self.paned2.add2(self.editor_pane)

        #self.show_all()
        self.treeview.grab_focus()


    def set_notebook(self, notebook):
        
        self._notebook = notebook
        self.editor.set_notebook(notebook)
        self.listview.set_notebook(notebook)
        self.treeview.set_notebook(notebook)

        if self.treeview.get_popup_menu():
            self.treeview.get_popup_menu().iconmenu.set_notebook(notebook)
            self.listview.get_popup_menu().iconmenu.set_notebook(notebook)

        # restore selections
        if self._notebook:
            nodes = [node for node in (
                    self._notebook.get_node_by_id(i)
                    for i in self._notebook.pref.selected_treeview_nodes)
                     if node is not None]
            self.treeview.select_nodes(nodes)
            nodes = [node for node in (
                    self._notebook.get_node_by_id(i)
                    for i in self._notebook.pref.selected_listview_nodes)
                     if node is not None]
            self.listview.select_nodes(nodes)


        self.treeview.grab_focus()


    def get_notebook(self):
        """Return the current notebook for the view"""
        return self._notebook


    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""

        self.set_view_mode(app_pref.view_mode)
        self.paned2.set_position(app_pref.vsash_pos)
        self.hpaned.set_position(app_pref.hsash_pos)

        self.listview.set_date_formats(app_pref.timestamp_formats)
        self.listview.set_rules_hint(app_pref.listview_rules)        
        try:
            # if this version of GTK doesn't have tree-lines, ignore it
            self.treeview.set_property("enable-tree-lines",
                                       app_pref.treeview_lines)
        except:
            pass

        self.editor_menus.enable_spell_check(self._app.pref.spell_check)

        # reload ui
        self.remove_ui(self._main_window)
        self.add_ui(self._main_window)

        
        


    def save_preferences(self, app_pref):
        """Save application preferences"""
        
        app_pref.vsash_pos = self.paned2.get_position()
        app_pref.hsash_pos = self.hpaned.get_position()
        
        # record state in preferences
        app_pref.spell_check = self.editor.get_textview().is_spell_check_enabled()



    def save(self):
        self.editor.save()

        # save selections
        self._notebook.pref.selected_treeview_nodes = [
            node.get_attr("nodeid")
            for node in self.treeview.get_selected_nodes()]
        self._notebook.pref.selected_listview_nodes = [
            node.get_attr("nodeid")
            for node in self.listview.get_selected_nodes()]
        self._notebook.set_preferences_dirty()
        

    def undo(self):
        self.editor.get_textview().undo()

    def redo(self):
        self.editor.get_textview().redo()


    def set_status(self, text, bar="status"):
        self.emit("status", text, bar)

    def set_view_mode(self, mode):
        """
        Sets view mode for ThreePaneViewer

        modes:
            "vertical"
            "horizontal"
        """

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
                    
        self.paned2.set_position(self._app.pref.vsash_pos)
        self.paned2.show()        
        
        self.hpaned.add2(self.paned2)
        self.hpaned.show()
        
        self.paned2.add1(self.listview_sw)
        self.paned2.add2(self.editor_pane)

        # record preference
        if mode != self._app.pref.view_mode:
            self._app.pref.view_mode = mode
            self._app.pref.changed.notify()


    #===============================================
    # node operations


    def get_current_page(self):
        return self._current_page


    def get_selected_nodes(self, widget="focus"):
        """
        Returns (nodes, widget) where 'nodes' are a list of selected nodes
        in widget 'widget'

        Wiget can be
           listview -- nodes selected in listview
           treeview -- nodes selected in treeview
           focus    -- nodes selected in widget with focus
        """
        
        if widget == "focus":
            if self.listview.is_focus():
                widget = "listview"
            elif self.treeview.is_focus():
                widget = "treeview"
            elif self.editor.is_focus():
                widget = "listview"
            else:
                return ([], "")

        if widget == "treeview":
            nodes = self.treeview.get_selected_nodes()
        elif widget == "listview":
            nodes = self.listview.get_selected_nodes()
        else:
            raise Exception("unknown widget '%s'" % widget)

        return (nodes, widget)


    def _on_history_changed(self, viewer, history):
        """Callback for when node browse history changes"""
        
        if self.back_button:
            self.back_button.set_sensitive(history.has_back())
            self.forward_button.set_sensitive(history.has_forward())


    def get_focused_widget(self, default=None):
        
        if self.treeview.is_focus():
            return self.treeview
        if self.listview.is_focus():
            return self.listview
        else:
            return default
    

    def on_delete_node(self, widget="focus", nodes=None):
        
        # get node to delete
        if nodes is None:
            nodes, widget = self.get_selected_nodes()
            
        if len(nodes) == 0:
            return
        node = nodes[0]
        
        if self._main_window.confirm_delete_nodes(nodes):
            # change selection            
            widget = self.get_focused_widget()
            parent = node.get_parent()
            children = parent.get_children()
            i = children.index(node)
            if i < len(children) - 1:
                widget.select_nodes([children[i+1]])
            else:
                widget.select_nodes([parent])

            # perform delete
            try:
                node.trash()
            except NoteBookError, e:
                self.emit("error", e.msg, e)


    def _on_make_link(self, editor):
        """Callback from editor to make a link"""
        self.link_editor.edit()
    
    
    def _on_editor_view_node(self, editor, node):
        """Callback for when editor views a node"""
        self._history.add(node.get_attr("nodeid"))
        self.emit("history-changed", self._history)


    def _on_child_activated(self, editor, textview, child):
        """Callback for when child widget in editor is activated"""
        
        if isinstance(child, richtext.RichTextImage):
            self.view_image(child.get_filename())

        
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

    
    def _on_list_select(self, listview, pages):
        """Callback for listview selection change"""

        # TODO: will need to generalize to multiple pages

        # remember the selected node
        if len(pages) > 0:
            self._current_page = pages[0]
        else:
            self._current_page = None
        
        try:
            self.editor.view_pages(pages)
        except RichTextError, e:
            self.emit("error", 
                      "Could not load page '%s'." % pages[0].get_title(),
                      e, sys.exc_info()[2])

    def on_list_view_node(self, listview, node, direct=False):
        """Focus listview on a node"""
        
        if node and node.has_attr("payload_filename"):
            self._main_window.on_view_node_external_app("file_launcher",
                                           node,
                                           kind="file")
        else:
            self.goto_node(node, direct)
        

    def on_list_view_parent_node(self, node=None):
        """Focus listview on a node's parent"""

        # get node
        if node is None:
            if len(self._treeview_sel_nodes) == 0:
                return
            if len(self._treeview_sel_nodes) > 1 or \
               not self.listview.is_view_tree():
                nodes = self.listview.get_selected_nodes()
                if len(nodes) == 0:
                    return
                node = nodes[0]
            else:
                node = self._treeview_sel_nodes[0]

        # get parent
        parent = node.get_parent()
        if parent is None:
            return

        # queue list select
        nodes = self.listview.get_selected_nodes()
        if len(nodes) > 0:
            self._queue_list_select = nodes
        else:
            self._queue_list_select = [node]

        # select parent
        self.treeview.select_nodes([parent])


    def _on_edit_title(self, widget, node, title):
        """Callback for title edit finishing"""

        # move cursor to editor after new page has been created
        if self._new_page_occurred:
            self._new_page_occurred = False

            if node.get_attr("content_type") != notebooklib.CONTENT_TYPE_DIR:
                self.goto_editor()


    def _on_attach_file(self, widget, parent, index, uri):
        """Attach document"""
        self._main_window.attach_file(uri, parent, index)



    def new_node(self, kind, widget, pos):

        # TODO: think about where this goes

        if self._notebook is None:
            return

        nodes, widget = self.get_selected_nodes(widget)
        #print "nodes", nodes
        
        if len(nodes) == 1:
            parent = nodes[0]
        else:
            parent = self._notebook
        
        if pos == "sibling" and parent.get_parent() is not None:
            index = parent.get_attr("order") + 1
            parent = parent.get_parent()
        else:
            index = None


        if kind == notebooklib.CONTENT_TYPE_DIR:
            node = parent.new_child(notebooklib.CONTENT_TYPE_DIR,
                                    notebooklib.DEFAULT_DIR_NAME,
                                    index)
        else:
            node = parent.new_child(notebooklib.CONTENT_TYPE_PAGE,
                                    notebooklib.DEFAULT_PAGE_NAME,
                                    index)
        
        self.view_new_node(node, widget)


    def view_new_node(self, node, widget):
        
        self._new_page_occurred = True
        
        if widget == "treeview":
            #self.treeview.cancel_editing()
            self.treeview.expand_node(node.get_parent())
            self.treeview.edit_node(node)
        elif widget == "listview":
            self.listview.expand_node(node.get_parent())
            self.listview.edit_node(node)
        elif widget == "":
            pass
        else:
            raise Exception("unknown widget '%s'" % widget)


    def on_edit_node(self):
        nodes, widget = self.get_selected_nodes()

        if len(nodes) == 0:
            return

        if widget == "listview":
            self.listview.edit_node(nodes[0])
        elif widget == "treeview":
            self.treeview.edit_node(nodes[0])


    def goto_node(self, node, direct=True):
        if node is None:
            nodes = self.listview.get_selected_nodes()
            if len(nodes) == 0:
                return
            node = nodes[0]
        
        treenodes = self.treeview.get_selected_nodes()

        if direct:
            self.treeview.select_nodes([node])
        else:
            # get path to root
            path = []
            ptr = node
            while ptr:
                if ptr in treenodes:
                    # if parent path is allready selected then quit
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
            self.listview.select_nodes([node])
                    


    def goto_next_node(self):
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
        
        widget = self.get_focused_widget()
        path, col = widget.get_cursor()

        if path and path[-1] > 0:
            path2 = path[:-1] + (path[-1] - 1,)
            widget.set_cursor(path2)

    def expand_node(self, all=False):
        
        widget = self.get_focused_widget(self.treeview)
        path, col = widget.get_cursor()

        if path:
            widget.expand_row(path, all)

    def collapse_node(self, all=False):
        
        # TODO: move guts into basetreeview

        widget = self.get_focused_widget(self.treeview)
        path, col = widget.get_cursor()

        if path:
            if all:
                # recursively collapse all notes
                model = widget.get_model()
                it = model.get_iter(path)
                def walk(it):
                    for child in iter_children(model, it):
                        walk(child)
                    path2 = model.get_path(it)
                    widget.collapse_row(path2)
                walk(it)
            else:
                widget.collapse_row(path)


    def search_nodes(self, text):
        """Return nodes with titles containing 'text'"""

        # TODO: make proper interface

        # don't show current page in results list
        #if self._current_page:
        #    current_nodeid = self._current_page.get_attr("nodeid")
        #else:
        #    current_nodeid = None
            
        nodes = [(nodeid, title) 
                for nodeid, title in self._notebook._index.search_titles(text)]
        return nodes


    #============================================
    # Search

    def start_search_result(self):        
        self.treeview.select_nodes([])
        self.listview.view_nodes([], nested=False)

    def add_search_result(self, node):
        self.listview.append_node(node)


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
        self.editor.get_textview().grab_focus()

    def goto_link(self):
        """Visit link under cursor"""        
        self.editor.get_textview().click_iter()


    #===========================================
    # ui
    
    def add_ui(self, window):

        assert window == self._main_window

        #print "add"

        self._action_group = gtk.ActionGroup("Viewer")
        self._uis = []
        add_actions(self._action_group, self.get_actions())
        self._main_window.get_uimanager().insert_action_group(
            self._action_group, 0)

        for s in self.get_ui():
            self._uis.append(
                self._main_window.get_uimanager().add_ui_from_string(s))

        uimanager = self._main_window.get_uimanager()
        uimanager.ensure_update()
        
        # setup toolbar
        self.back_button = uimanager.get_widget("/main_tool_bar/Viewer/Back")
        self.forward_button = uimanager.get_widget("/main_tool_bar/Viewer/Forward")


        # setup editor
        self.editor_menus.add_ui(window,
                                 use_minitoolbar=self._app.pref.use_minitoolbar)
        
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
        menu1.iconmenu = self._setup_icon_menu()
        item = uimanager.get_widget(
            "/popup_menus/treeview_popup/Change Note Icon")
        item.set_submenu(menu1.iconmenu)
        item.show()


        # listview context menu
        menu2 = uimanager.get_widget(
            "/popup_menus/listview_popup").get_submenu()
        self.listview.set_popup_menu(menu2)
        menu2.set_accel_group(uimanager.get_accel_group())
        menu2.set_accel_path(CONTEXT_MENU_ACCEL_PATH)
        menu2.iconmenu = self._setup_icon_menu()
        item = uimanager.get_widget(
            "/popup_menus/listview_popup/Change Note Icon")
        item.set_submenu(menu2.iconmenu)
        item.show()
        

    def _setup_icon_menu(self):

        iconmenu = IconMenu()
        iconmenu.connect("set-icon",
            lambda w, i: self._main_window.on_set_icon(
                i, u"", self.get_selected_nodes()[0]))
        iconmenu.new_icon.connect("activate",
            lambda w: self._main_window.on_new_icon(
                self.get_selected_nodes()[0]))

        return iconmenu




    def remove_ui(self, window):

        assert self._main_window == window

        #print "remove"

        self.editor_menus.remove_ui(self._main_window)

        for ui in reversed(self._uis):
            self._main_window.get_uimanager().remove_ui(ui)
        self._uis = []

        self._main_window.get_uimanager().remove_action_group(self._action_group)
        self._action_group = None
        self._main_window.get_uimanager().ensure_update()


    def get_ui(self):        
        
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
              <menuitem action="Go to Link"/>
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
            <separator/>
            <menuitem action="Delete Note"/>
            <menuitem action="Rename Note"/>
            <menuitem action="Change Note Icon"/>
            <separator/>
            <menuitem action="View Note in File Explorer"/>
            <menuitem action="View Note in Text Editor"/>
            <menuitem action="View Note in Web Browser"/>
            <menuitem action="Open File"/>
          </menu>

          <menu action="listview_popup">
            <menuitem action="Go to Note"/>
            <menuitem action="Go to Parent Note"/>
            <separator/>
            <menuitem action="New Page"/>
            <menuitem action="New Child Page"/>
            <menuitem action="New Folder"/>
            <menuitem action="Attach File"/>
            <separator/>
            <menuitem action="Delete Note"/>
            <menuitem action="Rename Note"/>
            <menuitem action="Change Note Icon"/>
            <separator/>
            <menuitem action="View Note in File Explorer"/>
            <menuitem action="View Note in Text Editor"/>
            <menuitem action="View Note in Web Browser"/>
            <menuitem action="Open File"/>
          </menu>
        </menubar>

        </ui>
        """]
        

    def get_actions(self):

        return map(lambda x: Action(*x), [
                
            ("treeview_popup", None, "", "", None, lambda w: None),
            ("listview_popup", None, "", "", None, lambda w: None),


            ("Back", gtk.STOCK_GO_BACK, _("_Back"), "", None,
             lambda w: self.visit_history(-1)),
            
            ("Forward", gtk.STOCK_GO_FORWARD, _("_Forward"), "", None,
             lambda w: self.visit_history(1)),

            ("Go to Note", gtk.STOCK_JUMP_TO, _("Go to _Note"),
             "", None,
             lambda w: self.on_list_view_node(None, None)),
            
            ("Go to Parent Note", gtk.STOCK_GO_BACK, _("Go to _Parent Note"),
             "<shift><alt>Left", None,
             lambda w: self.on_list_view_parent_node()),

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

            ("Expand All Child Notes", gtk.STOCK_ADD, _("Expand _All Child Notes"),
             "<shift><alt>Right", None,
             lambda w: self.expand_node(True)),

            ("Collapse All Child Notes", gtk.STOCK_REMOVE, _("Collapse A_ll Child Notes"),
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
            
            ("Go to Link", None, _("Go to Lin_k"),
             "<control>space", None,
             lambda w: self.goto_link()),
        
            ("Delete Note", gtk.STOCK_DELETE, _("_Delete"),
             "", None, 
             lambda w: self.on_delete_node()),

            ("Rename Note", gtk.STOCK_EDIT, _("_Rename"),
             "", None, 
             lambda w: self.on_edit_node()),

            ("Change Note Icon", None, _("_Change Note Icon"),
             "", None, lambda w: None,
             lookup_icon_filename(None, u"folder-red.png")),

        ]) #+ self.editor_menus.get_actions()


