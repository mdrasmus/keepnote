"""

    KeepNote
    base class for treeview

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

# python imports
import urllib

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk
import gobject
from gtk import gdk

# keepnote imports
import keepnote
from keepnote import unicode_gtk
from keepnote.notebook import NoteBookError
from keepnote.gui.icons import get_node_icon
from keepnote.gui.treemodel import \
    get_path_from_node, iter_children
from keepnote.gui import treemodel, CLIPBOARD_NAME
from keepnote.timestamp import get_str_timestamp

_ = keepnote.translate


MIME_NODE_COPY = "application/x-keepnote-node-copy"
MIME_TREE_COPY = "application/x-keepnote-tree-copy"
MIME_NODE_CUT = "application/x-keepnote-node-cut"

# treeview drag and drop config
DROP_URI = ("text/uri-list", 0, 1)
DROP_TREE_MOVE = ("drop_node", gtk.TARGET_SAME_APP, 0)
#DROP_NO = ("drop_no", gtk.TARGET_SAME_WIDGET, 0)


# treeview reorder rules
REORDER_NONE = 0
REORDER_FOLDER = 1
REORDER_ALL = 2


def parse_utf(text):

    # TODO: lookup the standard way to do this

    if (text[:2] in ('\xff\xfe', '\xfe\xff') or
            (len(text) > 1 and text[1] == '\x00') or
            (len(text) > 3 and text[3] == '\x00')):
        return text.decode("utf16")
    else:
        text = text.replace("\x00", "")
        return unicode(text, "utf8")


def compute_new_path(model, target, drop_position):
    """Compute the new path of a tagret rowiter in a treemodel"""
    path = model.get_path(target)

    if drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or \
       drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
        return path + (0,)
    elif drop_position == gtk.TREE_VIEW_DROP_BEFORE:
        return path
    elif drop_position == gtk.TREE_VIEW_DROP_AFTER:
        return path[:-1] + (path[-1] + 1,)
    else:
        raise Exception("unknown drop position %s" %
                        str(drop_position))


class TextRendererValidator (object):
    def __init__(self, format=lambda x: x, parse=lambda x: x,
                 validate=lambda x: True):

        def parse2(x):
            if not validate(x):
                raise Exception("Invalid")
            return parse(x)

        self.format = format
        self.parse = parse2


class KeepNoteBaseTreeView (gtk.TreeView):
    """Base class for treeviews of a NoteBook notes"""

    def __init__(self):
        gtk.TreeView.__init__(self)

        self.model = None
        self.rich_model = None
        self._notebook = None
        self._master_node = None
        self.editing_path = False
        self.__sel_nodes = []
        self.__sel_nodes2 = []
        self.__scroll = (0, 0)
        self.__suppress_sel = False
        self._node_col = None
        self._get_icon = None
        self._get_node = self._get_node_default
        self._date_formats = {}

        self._menu = None

        # special attr's
        self._attr_title = "title"
        self._attr_icon = "icon"
        self._attr_icon_open = "icon_open"

        # selection
        self.get_selection().connect("changed", self.__on_select_changed)
        self.get_selection().connect("changed", self.on_select_changed)

        # row expand/collapse
        self.connect("row-expanded", self._on_row_expanded)
        self.connect("row-collapsed", self._on_row_collapsed)

        # drag and drop state
        self._is_dragging = False   # whether drag is in progress
        self._drag_count = 0
        self._dest_row = None        # current drag destition
        self._reorder = REORDER_ALL  # enum determining the kind of reordering
                                     # that is possible via drag and drop
        # region, defined by number of vertical pixels from top and bottom of
        # the treeview widget, where drag scrolling will occur
        self._drag_scroll_region = 30

        # clipboard
        self.connect("copy-clipboard", self._on_copy_node)
        self.connect("copy-tree-clipboard", self._on_copy_tree)
        self.connect("cut-clipboard", self._on_cut_node)
        self.connect("paste-clipboard", self._on_paste_node)

        # drop and drop events
        self.connect("drag-begin", self._on_drag_begin)
        self.connect("drag-end", self._on_drag_end)
        self.connect("drag-motion", self._on_drag_motion)
        self.connect("drag-drop", self._on_drag_drop)
        self.connect("drag-data-delete", self._on_drag_data_delete)
        self.connect("drag-data-get", self._on_drag_data_get)
        self.connect("drag-data-received", self._on_drag_data_received)

        # configure drag and drop events
        self.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK, [DROP_TREE_MOVE], gtk.gdk.ACTION_MOVE)
        self.drag_source_set(
            gtk.gdk.BUTTON1_MASK,
            [DROP_TREE_MOVE],
            gtk.gdk.ACTION_MOVE)
        self.enable_model_drag_dest([DROP_TREE_MOVE, DROP_URI],
                                    gtk.gdk.ACTION_MOVE |
                                    gtk.gdk.ACTION_COPY |
                                    gtk.gdk.ACTION_LINK)

        self.drag_dest_set(
            gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_MOTION,
            [DROP_TREE_MOVE, DROP_URI],
            gtk.gdk.ACTION_DEFAULT |
            gtk.gdk.ACTION_MOVE |
            gtk.gdk.ACTION_COPY |
            gtk.gdk.ACTION_LINK |
            gtk.gdk.ACTION_PRIVATE |
            gtk.gdk.ACTION_ASK)

    def set_master_node(self, node):
        self._master_node = node

        if self.rich_model:
            self.rich_model.set_master_node(node)

    def get_master_node(self):
        return self._master_node

    def set_notebook(self, notebook):
        self._notebook = notebook

        # NOTE: not used yet
        if self.model:
            if hasattr(self.model, "get_model"):
                self.model.get_model().set_notebook(notebook)
            else:
                self.model.set_notebook(notebook)

    def set_get_node(self, get_node_func=None):

        if get_node_func is None:
            self._get_node = self._get_node_default
        else:
            self._get_node = get_node_func

    def _get_node_default(self, nodeid):
        if self._notebook is None:
            return None
        return self._notebook.get_node_by_id(nodeid)

    def set_model(self, model):
        """Set the model for the view"""

        # TODO: could group signal IDs into lists, for each detach
        # if model already attached, disconnect all of its signals
        if self.model is not None:
            self.rich_model.disconnect(self.changed_start_id)
            self.rich_model.disconnect(self.changed_end_id)
            self.model.disconnect(self.insert_id)
            self.model.disconnect(self.delete_id)
            self.model.disconnect(self.has_child_id)

            self._node_col = None
            self._get_icon = None

        # set new model
        self.model = model
        self.rich_model = None
        gtk.TreeView.set_model(self, self.model)

        # set new model
        if self.model is not None:
            # look to see if model has an inner model (happens when we have
            # sorting models)
            if hasattr(self.model, "get_model"):
                self.rich_model = self.model.get_model()
            else:
                self.rich_model = model

            # init signals for model
            self.rich_model.set_notebook(self._notebook)
            self.changed_start_id = self.rich_model.connect(
                "node-changed-start", self._on_node_changed_start)
            self.changed_end_id = self.rich_model.connect(
                "node-changed-end", self._on_node_changed_end)
            self._node_col = self.rich_model.get_node_column_pos()
            self._get_icon = lambda row: \
                self.model.get_value(
                    row, self.rich_model.get_column_by_name("icon").pos)

            self.insert_id = self.model.connect("row-inserted",
                                                self.on_row_inserted)
            self.delete_id = self.model.connect("row-deleted",
                                                self.on_row_deleted)
            self.has_child_id = self.model.connect(
                "row-has-child-toggled", self.on_row_has_child_toggled)

    def set_popup_menu(self, menu):
        self._menu = menu

    def get_popup_menu(self):
        return self._menu

    def popup_menu(self, x, y, button, time):
        """Display popup menu"""
        if self._menu is None:
            return

        path = self.get_path_at_pos(int(x), int(y))
        if path is None:
            return False

        path = path[0]

        if not self.get_selection().path_is_selected(path):
            self.get_selection().unselect_all()
            self.get_selection().select_path(path)

        self._menu.popup(None, None, None, button, time)
        self._menu.show()
        return True

    #========================================
    # columns

    def clear_columns(self):
        for col in reversed(self.get_columns()):
            self.remove_column(col)

    def get_column_by_attr(self, attr):
        for col in self.get_columns():
            if col.attr == attr:
                return col
        return None

    def _add_title_render(self, column, attr):

        # make sure icon attributes are in model
        self._add_model_column(self._attr_icon)
        self._add_model_column(self._attr_icon_open)

        # add renders
        cell_icon = self._add_pixbuf_render(
            column, self._attr_icon, self._attr_icon_open)
        title_text = self._add_text_render(
            column, attr, editable=True,
            validator=TextRendererValidator(validate=lambda x: x != ""))

        # record reference to title_text renderer
        self.title_text = title_text

        return cell_icon, title_text

    def _add_text_render(self, column, attr, editable=False,
                         validator=TextRendererValidator()):
        # cell renderer text
        cell = gtk.CellRendererText()
        cell.set_fixed_height_from_font(1)
        column.pack_start(cell, True)
        column.add_attribute(cell, 'text',
                             self.rich_model.get_column_by_name(attr).pos)

        column.add_attribute(
            cell, 'cell-background',
            self.rich_model.add_column(
                "title_bgcolor", str,
                lambda node: node.get_attr("title_bgcolor", None)).pos)
        column.add_attribute(
            cell, 'foreground',
            self.rich_model.add_column(
                "title_fgcolor", str,
                lambda node: node.get_attr("title_fgcolor", None)).pos)

        # set edit callbacks
        if editable:
            cell.connect("edited", lambda r, p, t: self.on_edit_attr(
                r, p, attr, t, validator=validator))
            cell.connect("editing-started", lambda r, e, p:
                         self.on_editing_started(r, e, p, attr, validator))
            cell.connect("editing-canceled", self.on_editing_canceled)
            cell.set_property("editable", True)

        return cell

    def _add_pixbuf_render(self, column, attr, attr_open=None):

        cell = gtk.CellRendererPixbuf()
        column.pack_start(cell, False)
        column.add_attribute(cell, 'pixbuf',
                             self.rich_model.get_column_by_name(attr).pos)
        #column.add_attribute(
        #    cell, 'cell-background',
        #    self.rich_model.add_column(
        #        "title_bgcolor", str,
        #        lambda node: node.get_attr("title_bgcolor", None)).pos)

        if attr_open:
            column.add_attribute(
                cell, 'pixbuf-expander-open',
                self.rich_model.get_column_by_name(attr_open).pos)

        return cell

    def _get_model_column(self, attr, mapfunc=lambda x: x):
        col = self.rich_model.get_column_by_name(attr)
        if col is None:
            self._add_model_column(attr, add_sort=False, mapfunc=mapfunc)
            col = self.rich_model.get_column_by_name(attr)
        return col

    def get_col_type(self, datatype):

        if datatype == "string":
            return str
        elif datatype == "integer":
            return int
        elif datatype == "float":
            return float
        elif datatype == "timestamp":
            return str
        else:
            return str

    def get_col_mapfunc(self, datatype):
        if datatype == "timestamp":
            return self.format_timestamp
        else:
            return lambda x: x

    def _add_model_column(self, attr, add_sort=True, mapfunc=lambda x: x):

        # get attribute definition from notebook
        attr_def = self._notebook.attr_defs.get(attr)

        # get datatype
        if attr_def is not None:
            datatype = attr_def.datatype
            default = attr_def.default
        else:
            datatype = "string"
            default = ""

        # value fetching
        get = lambda node: mapfunc(node.get_attr(attr, default))

        # get coltype
        mapfunc_sort = lambda x: x
        if datatype == "string":
            coltype = str
            coltype_sort = str
            mapfunc_sort = lambda x: x.lower()
        elif datatype == "integer":
            coltype = int
            coltype_sort = int
        elif datatype == "float":
            coltype = float
            coltype_sort = float
        elif datatype == "timestamp":
            mapfunc = self.format_timestamp
            coltype = str
            coltype_sort = int
        else:
            coltype = str
            coltype_sort = str

        # builtin column types
        if attr == self._attr_icon:
            coltype = gdk.Pixbuf
            coltype_sort = None
            get = lambda node: get_node_icon(node, False,
                                             node in self.rich_model.fades)
        elif attr == self._attr_icon_open:
            coltype = gdk.Pixbuf
            coltype_sort = None
            get = lambda node: get_node_icon(node, True,
                                             node in self.rich_model.fades)

        # get/make model column
        col = self.rich_model.get_column_by_name(attr)
        if col is None:
            col = treemodel.TreeModelColumn(attr, coltype, attr=attr, get=get)
            self.rich_model.append_column(col)

        # define column sorting
        if add_sort and coltype_sort is not None:
            attr_sort = attr + "_sort"
            col = self.rich_model.get_column_by_name(attr_sort)
            if col is None:
                get_sort = lambda node: mapfunc_sort(
                    node.get_attr(attr, default))
                col = treemodel.TreeModelColumn(
                    attr_sort, coltype_sort, attr=attr, get=get_sort)
                self.rich_model.append_column(col)

    def set_date_formats(self, formats):
        """Sets the date formats of the treemodel"""
        self._date_formats = formats

    def format_timestamp(self, timestamp):
        return (get_str_timestamp(timestamp, formats=self._date_formats)
                if timestamp is not None else u"")

    #=========================================
    # model change callbacks

    def _on_node_changed_start(self, model, nodes):
        # remember which nodes are selected
        self.__sel_nodes2 = list(self.__sel_nodes)

        # suppress selection changes while nodes are changing
        self.__suppress_sel = True

        # cancel editing
        self.cancel_editing()

        # save scrolling
        self.__scroll = self.widget_to_tree_coords(0, 0)

    def _on_node_changed_end(self, model, nodes):

        # maintain proper expansion
        for node in nodes:

            if node == self._master_node:
                for child in node.get_children():
                    if self.is_node_expanded(child):
                        path = get_path_from_node(
                            self.model, child,
                            self.rich_model.get_node_column_pos())
                        self.expand_row(path, False)
            else:
                try:
                    path = get_path_from_node(
                        self.model, node,
                        self.rich_model.get_node_column_pos())
                except:
                    path = None
                if path is not None:
                    parent = node.get_parent()

                    # NOTE: parent may lose expand state if it has one child
                    # therefore, we should expand parent if it exists and is
                    # visible (i.e. len(path)>1) in treeview
                    if (parent and self.is_node_expanded(parent) and
                            len(path) > 1):
                        self.expand_row(path[:-1], False)

                    if self.is_node_expanded(node):
                        self.expand_row(path, False)

        # if nodes still exist, and expanded, try to reselect them
        sel_count = 0
        selection = self.get_selection()
        for node in self.__sel_nodes2:
            sel_count += 1
            if node.is_valid():
                path2 = get_path_from_node(
                    self.model, node, self.rich_model.get_node_column_pos())
                if (path2 is not None and
                        (len(path2) <= 1 or self.row_expanded(path2[:-1]))):
                    # reselect and scroll to node
                    selection.select_path(path2)

        # restore scroll
        gobject.idle_add(lambda: self.scroll_to_point(*self.__scroll))

        # resume emitting selection changes
        self.__suppress_sel = False

        # emit de-selection
        if sel_count == 0:
            self.select_nodes([])

    def __on_select_changed(self, treeselect):
        """Keep track of which nodes are selected"""

        self.__sel_nodes = self.get_selected_nodes()
        if self.__suppress_sel:
            self.get_selection().stop_emission("changed")

    def is_node_expanded(self, node):
        # query expansion from nodes
        return node.get_attr("expanded", False)

    def set_node_expanded(self, node, expand):
        # save expansion in node
        node.set_attr("expanded", expand)

        # TODO: do I notify listeners of expand change
        # Will this interfere with on_node_changed callbacks

    def _on_row_expanded(self, treeview, it, path):
        """Callback for row expand

           Performs smart expansion (remembers children expansion)"""

        # save expansion in node
        self.set_node_expanded(self.model.get_value(it, self._node_col), True)

        # recursively expand nodes that should be expanded
        def walk(it):
            child = self.model.iter_children(it)
            while child:
                node = self.model.get_value(child, self._node_col)
                if self.is_node_expanded(node):
                    path = self.model.get_path(child)
                    self.expand_row(path, False)
                    walk(child)
                child = self.model.iter_next(child)
        walk(it)

    def _on_row_collapsed(self, treeview, it, path):
        # save expansion in node
        self.set_node_expanded(self.model.get_value(it, self._node_col), False)

    def on_row_inserted(self, model, path, it):
        pass

    def on_row_deleted(self, model, path):
        pass

    def on_row_has_child_toggled(self, model, path, it):
        pass

    def cancel_editing(self):
        if self.editing_path:
            self.set_cursor_on_cell(self.editing_path, None, None, False)

    #===========================================
    # actions

    def expand_node(self, node):
        """Expand a node in TreeView"""
        path = get_path_from_node(self.model, node,
                                  self.rich_model.get_node_column_pos())
        if path is not None:
            self.expand_to_path(path)

    def collapse_all_beneath(self, path):
        """Collapse all children beneath a path"""
        it = self.model.get_iter(path)

        def walk(it):
            for child in iter_children(self.model, it):
                walk(child)
            path2 = self.model.get_path(it)
            self.collapse_row(path2)
        walk(it)

    #===========================================
    # selection

    def select_nodes(self, nodes):
        """Select nodes in treeview"""

        # NOTE: for now only select one node
        if len(nodes) > 0:
            node = nodes[0]
            path = get_path_from_node(self.model, node,
                                      self.rich_model.get_node_column_pos())
            if path is not None:
                if len(path) > 1:
                    self.expand_to_path(path[:-1])
                self.set_cursor(path)
                gobject.idle_add(lambda: self.scroll_to_cell(path))
        else:
            # unselect all nodes
            self.get_selection().unselect_all()

    def on_select_changed(self, treeselect):
        """Callback for when selection changes"""
        nodes = self.get_selected_nodes()
        self.emit("select-nodes", nodes)
        return True

    def get_selected_nodes(self):
        """Returns a list of currently selected nodes"""
        iters = self.get_selected_iters()
        if len(iters) == 0:
            if self.editing_path:
                node = self._get_node_from_path(self.editing_path)
                if node:
                    return [node]
            return []
        else:
            return [self.model.get_value(it, self._node_col)
                    for it in iters]

    def get_selected_iters(self):
        """Return a list of currently selected TreeIter's"""
        iters = []
        self.get_selection().selected_foreach(lambda model, path, it:
                                              iters.append(it))
        return iters

    # TODO: add a reselect if node is deleted
    # select next sibling or parent

    #============================================
    # editing attr

    def on_editing_started(self, cellrenderer, editable, path, attr,
                           validator=TextRendererValidator()):
        """Callback for start of title editing"""
        # remember editing state
        self.editing_path = path

        # get node being edited and init gtk.Entry widget
        node = self.model.get_value(self.model.get_iter(path), self._node_col)
        if node is not None:
            val = node.get_attr(attr)
            try:
                editable.set_text(validator.format(val))
            except:
                pass

        gobject.idle_add(lambda: self.scroll_to_cell(path))

    def on_editing_canceled(self, cellrenderer):
        """Callback for canceled of title editing"""
        # remember editing state
        self.editing_path = None

    def on_edit_attr(self, cellrenderertext, path, attr, new_text,
                     validator=TextRendererValidator()):
        """Callback for completion of title editing"""

        # remember editing state
        self.editing_path = None

        new_text = unicode_gtk(new_text)

        # get node being edited
        node = self.model.get_value(self.model.get_iter(path), self._node_col)
        if node is None:
            return

        # determine value from new_text, if invalid, ignore it
        try:
            new_val = validator.parse(new_text)
        except:
            return

        # set new attr and catch errors
        try:
            node.set_attr(attr, new_val)
        except NoteBookError, e:
            self.emit("error", e.msg, e)

        # reselect node
        # need to get path again because sorting may have changed
        path = get_path_from_node(self.model, node,
                                  self.rich_model.get_node_column_pos())
        if path is not None:
            self.set_cursor(path)
            gobject.idle_add(lambda: self.scroll_to_cell(path))

        self.emit("edit-node", node, attr, new_val)

    #=============================================
    # copy and paste

    def _on_copy_node(self, widget):
        """Copy a node onto the clipboard"""

        nodes = self.get_selected_nodes()
        if len(nodes) > 0:
            clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)

            targets = [(MIME_NODE_COPY, gtk.TARGET_SAME_APP, -1),
                       ("text/html", 0, -1),
                       ("text/plain", 0, -1)]

            clipboard.set_with_data(targets, self._get_selection_data,
                                    self._clear_selection_data,
                                    nodes)

    def _on_copy_tree(self, widget):

        nodes = self.get_selected_nodes()
        if len(nodes) > 0:
            clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)

            targets = [(MIME_TREE_COPY, gtk.TARGET_SAME_APP, -1),
                       (MIME_NODE_COPY, gtk.TARGET_SAME_APP, -1),
                       ("text/html", 0, -1),
                       ("text/plain", 0, -1)]

            clipboard.set_with_data(targets, self._get_selection_data,
                                    self._clear_selection_data,
                                    nodes)

    def _on_cut_node(self, widget):
        """Copy a node onto the clipboard"""

        nodes = widget.get_selected_nodes()
        if len(nodes) > 0:
            clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)

            targets = [(MIME_NODE_CUT, gtk.TARGET_SAME_APP, -1),
                       ("text/html", 0, -1),
                       ("text/plain", 0, -1)]

            clipboard.set_with_data(targets, self._get_selection_data,
                                    self._clear_selection_data,
                                    nodes)

            self._fade_nodes(nodes)

    def _on_paste_node(self, widget):
        """Paste into the treeview"""

        clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)

        targets = clipboard.wait_for_targets()
        if targets is None:
            # nothing on clipboard
            return
        targets = set(targets)

        if MIME_NODE_CUT in targets:
            # request KEEPNOTE node objects
            clipboard.request_contents(MIME_NODE_CUT, self._do_paste_nodes)

        elif MIME_TREE_COPY in targets:
            # request KEEPNOTE node objects
            clipboard.request_contents(MIME_TREE_COPY, self._do_paste_nodes)

        elif MIME_NODE_COPY in targets:
            # request KEEPNOTE node objects
            clipboard.request_contents(MIME_NODE_COPY, self._do_paste_nodes)

    def _get_selection_data(self, clipboard, selection_data, info, nodes):
        """Callback for when Clipboard needs selection data"""

        if MIME_NODE_CUT in selection_data.target:
            # set nodes
            selection_data.set(MIME_NODE_CUT, 8,
                               ";".join([node.get_attr("nodeid")
                                         for node in nodes]))

        elif MIME_TREE_COPY in selection_data.target:
            # set nodes
            selection_data.set(MIME_TREE_COPY, 8,
                               ";".join([node.get_attr("nodeid")
                                         for node in nodes]))

        elif MIME_NODE_COPY in selection_data.target:
            # set nodes
            selection_data.set(MIME_NODE_COPY, 8,
                               ";".join([node.get_attr("nodeid")
                                         for node in nodes]))

        elif "text/html" in selection_data.target:
            # set html
            selection_data.set("text/html", 8,
                               " ".join(["<a href='%s'>%s</a>" %
                                         (node.get_url(),
                                          node.get_title())
                                         for node in nodes]))

        else:
            # set plain text
            selection_data.set_text(" ".join([node.get_url()
                                              for node in nodes]))

    def _do_paste_nodes(self, clipboard, selection_data, data):
        """Paste nodes into treeview"""
        if self._notebook is None:
            return

        # find paste location
        selected = self.get_selected_nodes()
        if len(selected) > 0:
            parent = selected[0]
        else:
            parent = self._notebook

        # find nodes to paste
        nodeids = selection_data.data.split(";")
        nodes = [self._get_node(nodeid) for nodeid in nodeids]

        #nodes = [self._notebook.get_node_by_id(nodeid)
        #         for nodeid in nodeids]

        if selection_data.target == MIME_NODE_CUT:
            for node in nodes:
                try:
                    if node is not None:
                        node.move(parent)
                except:
                    keepnote.log_error()

        elif selection_data.target == MIME_TREE_COPY:
            for node in nodes:
                try:
                    if node is not None:
                        node.duplicate(parent, recurse=True)
                except Exception:
                    keepnote.log_error()

        elif selection_data.target == MIME_NODE_COPY:
            for node in nodes:
                try:
                    if node is not None:
                        node.duplicate(parent)
                except Exception:
                    keepnote.log_error()

    def _clear_selection_data(self, clipboard, data):
        """Callback for when Clipboard contents are reset"""
        self._clear_fading()

    #============================================
    # node fading

    def _clear_fading(self):
        """Clear faded nodes"""
        nodes = list(self.rich_model.fades)
        self.rich_model.fades.clear()
        if self._notebook:
            self._notebook.notify_changes(nodes, False)

    def _fade_nodes(self, nodes):
        self.rich_model.fades.clear()
        for node in nodes:
            self.rich_model.fades.add(node)
            node.notify_change(False)

    #=============================================
    # drag and drop

    def set_reorder(self, order):
        self._reorder = order

    def get_reorderable(self):
        return self._reorder

    def get_drag_node(self):
        iters = self.get_selected_iters()
        if len(iters) == 0:
            return None
        return self.model.get_value(iters[0], self._node_col)

    def get_drag_nodes(self):
        return [self.model.get_value(it, self._node_col)
                for it in self.get_selected_iters()]

    #  drag and drop callbacks

    def _on_drag_timer(self):

        # process scrolling
        self._process_drag_scroll()
        return self._is_dragging

    def _process_drag_scroll(self):

        # get header height
        header_height = [0]

        if self.get_headers_visible():
            self.forall(lambda w, d: header_height.__setitem__(
                0, w.allocation.height), None)

        # get mouse poistion in tree coordinates
        x, y = self.get_pointer()
        x, y = self.widget_to_tree_coords(x, y - header_height[0])

        # get visible rect in tree coordinates
        rect = self.get_visible_rect()

        def dist_to_scroll(dist):
            """Convert a distance outside the widget into a scroll step"""

            # TODO: put these scroll constants somewhere else
            small_scroll_dist = 30
            small_scroll = 30
            fast_scroll_coeff = small_scroll

            if dist < small_scroll_dist:
                # slow scrolling
                self._drag_count = 0
                return small_scroll
            else:
                # fast scrolling
                self._drag_count += 1
                return small_scroll + fast_scroll_coeff * self._drag_count**2

        # test for scroll boundary
        dist = rect.y - y
        if dist > 0:
            self.scroll_to_point(-1, rect.y - dist_to_scroll(dist))

        else:
            dist = y - rect.y - rect.height
            if dist > 0:
                self.scroll_to_point(-1, rect.y + dist_to_scroll(dist))

    def _on_drag_begin(self, treeview, drag_context):
        """Callback for beginning of drag and drop"""
        self.stop_emission("drag-begin")

        iters = self.get_selected_iters()
        if len(iters) == 0:
            return

        # use first selected item for icon
        source = iters[0]

        # setup the drag icon
        if self._get_icon:
            pixbuf = self._get_icon(source)
            pixbuf = pixbuf.scale_simple(40, 40, gtk.gdk.INTERP_BILINEAR)
            self.drag_source_set_icon_pixbuf(pixbuf)

        # clear the destination row
        self._dest_row = None

        self.cancel_editing()

        self._is_dragging = True
        self._drag_count = 0
        gobject.timeout_add(200, self._on_drag_timer)

    def _on_drag_motion(self, treeview, drag_context, x, y, eventtime,
                        stop_emit=True):
        """
        Callback for drag motion.
        Indicate which drops are allowed (cannot drop into descendant).
        Also record the destination for later use.
        """

        # override gtk's default drag motion code
        if stop_emit:
            self.stop_emission("drag-motion")

        # if reordering is disabled then terminate the drag
        if self._reorder == REORDER_NONE:
            return False

        # determine destination row
        dest_row = treeview.get_dest_row_at_pos(x, y)

        if dest_row is not None:
            # get target info
            target_path, drop_position = dest_row
            target = self.model.get_iter(target_path)
            target_node = self.model.get_value(target, self._node_col)

            # process node drops
            if "drop_node" in drag_context.targets:
                # get source
                source_widget = drag_context.get_source_widget()
                source_nodes = source_widget.get_drag_nodes()

                # determine if drag is allowed
                allow = True
                for source_node in source_nodes:
                    if not self._drop_allowed(source_node, target_node,
                                              drop_position):
                        allow = False

                if allow:
                    self.set_drag_dest_row(target_path, drop_position)
                    self._dest_row = target_path, drop_position
                    drag_context.drag_status(gdk.ACTION_MOVE, eventtime)

            elif "text/uri-list" in drag_context.targets:
                if self._drop_allowed(None, target_node, drop_position):
                    self.set_drag_dest_row(target_path, drop_position)
                    self._dest_row = target_path, drop_position
                    drag_context.drag_status(gdk.ACTION_COPY, eventtime)

    def _on_drag_drop(self, widget, drag_context, x, y, timestamp):
        """
        Callback for drop event
        """
        # override gtk's default drag drop code
        self.stop_emission("drag-drop")

        # if reordering is disabled, reject drop
        if self._reorder == REORDER_NONE:
            drag_context.finish(False, False, timestamp)
            return False

        # cause get data event to occur
        if "drop_node" in drag_context.targets:
            self.drag_get_data(drag_context, "drop_node")

        elif "text/uri-list" in drag_context.targets:
            self.drag_get_data(drag_context, "text/uri-list")

        # accept drop
        return True

    def _on_drag_end(self, widget, drag_context):
        """Callback for end of dragging"""
        self._is_dragging = False

    def _on_drag_data_delete(self, widget, drag_context):
        """
        Callback for deleting data due to a 'move' event
        """

        # override gtk's delete event
        self.stop_emission("drag-data-delete")

        # do nothing else, deleting old copy is handled else where

    def _on_drag_data_get(self, widget, drag_context, selection_data,
                          info, timestamp):
        """
        Callback for when data is requested by drag_get_data
        """

        # override gtk's data get code
        self.stop_emission("drag-data-get")

        # TODO: think more about what data to actually set for
        # tree_set_row_drag_data()
        iters = self.get_selected_iters()
        if len(iters) > 0:
            source = iters[0]
            source_path = self.model.get_path(source)
            selection_data.tree_set_row_drag_data(self.model, source_path)

    def _on_drag_data_received(self, treeview, drag_context, x, y,
                               selection_data, info, eventtime):

        """
        Callback for when data is received from source widget
        """
        # override gtk's data received code
        self.stop_emission("drag-data-received")

        # NOTE: force one more call to motion, since Windows ignores
        # cross app drag calls
        self._on_drag_motion(treeview, drag_context, x, y, eventtime,
                             stop_emit=False)

        # if no destination, give up.  Occurs when drop is not allowed
        if self._dest_row is None:
            drag_context.finish(False, False, eventtime)
            return

        if "drop_node" in drag_context.targets:
            # process node drops
            self._on_drag_node_received(treeview, drag_context, x, y,
                                        selection_data, info, eventtime)

        elif "text/uri-list" in drag_context.targets:
            target_path, drop_position = self._dest_row
            target = self.model.get_iter(target_path)
            target_node = self.model.get_value(target, self._node_col)

            if self._drop_allowed(None, target_node, drop_position):
                new_path = compute_new_path(self.model, target, drop_position)
                parent = self._get_node_from_path(new_path[:-1])

                uris = parse_utf(selection_data.data)
                uris = [xx for xx in (urllib.unquote(uri.strip())
                                      for uri in uris.split("\n"))
                        if len(xx) > 0 and xx[0] != "#"]

                for uri in reversed(uris):
                    if uri.startswith("file://"):
                        uri = uri[7:]
                        if keepnote.get_platform() == "windows":
                            # remove one more '/' for windows
                            uri = uri[1:]
                    self.emit("drop-file", parent, new_path[-1], uri)
            drag_context.finish(True, False, eventtime)

        else:
            # unknown drop type, reject
            drag_context.finish(False, False, eventtime)

    def _get_node_from_path(self, path):

        if len(path) == 0:
            # TODO: donot use master node (lookup parent instead)
            assert self._master_node is not None
            return self._master_node
        else:
            it = self.model.get_iter(path)
            return self.model.get_value(it, self._node_col)

    def _on_drag_node_received(self, treeview, drag_context, x, y,
                               selection_data, info, eventtime):
        """
        Callback for node received from another widget
        """
        # get target
        target_path, drop_position = self._dest_row
        target = self.model.get_iter(target_path)
        target_node = self.model.get_value(target, self._node_col)
        new_path = compute_new_path(self.model, target, drop_position)

        # get source
        source_widget = drag_context.get_source_widget()
        source_nodes = source_widget.get_drag_nodes()
        if len(source_nodes) == 0:
            drag_context.finish(False, False, eventtime)
            return

        # determine new parent and index
        new_parent_path = new_path[:-1]
        new_parent = self._get_node_from_path(new_parent_path)
        index = new_path[-1]

        # move each source node
        for source_node in source_nodes:
            # determine if drop is allowed
            if not self._drop_allowed(source_node, target_node, drop_position):
                drag_context.finish(False, False, eventtime)
                continue

            # perform move in notebook model
            try:
                source_node.move(new_parent, index)
                index = new_parent.get_children().index(source_node)
                # NOTE: we update index in case moving source_node changes
                # the drop path
            except NoteBookError, e:
                # TODO: think about whether finish should always be false
                drag_context.finish(False, False, eventtime)
                self.emit("error", e.msg, e)
                return

        # re-establish selection on source node
        self.emit("goto-node", source_nodes[0])

        # notify that drag was successful
        drag_context.finish(True, True, eventtime)

    def _drop_allowed(self, source_node, target_node, drop_position):
        """Determine if drop is allowed"""

        # source cannot be an ancestor of target
        ptr = target_node
        while ptr is not None:
            if ptr == source_node:
                return False
            ptr = ptr.get_parent()

        drop_into = (drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or
                     drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER)

        return (
            # (1) do not let nodes move out of notebook root
            not (target_node.get_parent() is None and not drop_into) and

            # (2) do not let nodes move into nodes that don't allow children
            not (not target_node.allows_children() and drop_into) and

            # (3) if reorder == FOLDER, ensure drop is either INTO a node
            #     or new_parent == old_parent
            not (source_node and
                 self._reorder == REORDER_FOLDER and not drop_into and
                 target_node.get_parent() == source_node.get_parent()))


gobject.type_register(KeepNoteBaseTreeView)
gobject.signal_new("goto-node", KeepNoteBaseTreeView, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new(
    "activate-node", KeepNoteBaseTreeView, gobject.SIGNAL_RUN_LAST,
    gobject.TYPE_NONE, (object,))
gobject.signal_new(
    "delete-node", KeepNoteBaseTreeView, gobject.SIGNAL_RUN_LAST,
    gobject.TYPE_NONE, (object,))
gobject.signal_new("goto-parent-node", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
gobject.signal_new("copy-clipboard", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, ())
gobject.signal_new("copy-tree-clipboard", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, ())
gobject.signal_new("cut-clipboard", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, ())
gobject.signal_new("paste-clipboard", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, ())
gobject.signal_new("select-nodes", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("edit-node", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object, str, str))
gobject.signal_new("drop-file", KeepNoteBaseTreeView,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object, int, str))
gobject.signal_new("error", KeepNoteBaseTreeView, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (str, object,))
