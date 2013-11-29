"""

    KeepNote
    Treemodel for treeview and listview

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
import gobject
import gtk


def get_path_from_node(model, node, node_col):
    """
    Determine the path of a NoteBookNode 'node' in a gtk.TreeModel 'model'
    """

    # NOTE: I must make no assumptions about the type of the model
    # I could change that if I make a wrapper around TreeSortModel

    if node is None:
        return ()

    # determine root set
    root_set = {}
    child = model.iter_children(None)
    i = 0
    while child is not None:
        root_set[model.get_value(child, node_col)] = i
        child = model.iter_next(child)
        i += 1

    # walk up parent path until root set
    node_path = []
    while node not in root_set:
        node_path.append(node)
        node = node.get_parent()
        if node is None:
            # node is not in the model (e.g. listview subset)
            return None

    # walk back down and record path
    path = [root_set[node]]
    it = model.get_iter(tuple(path))
    for node in reversed(node_path):
        child = model.iter_children(it)
        i = 0

        while child is not None:
            if model.get_value(child, node_col) == node:
                path.append(i)
                it = child
                break
            child = model.iter_next(child)
            i += 1
        else:
            raise Exception("bad model")

    return tuple(path)


class TreeModelColumn (object):

    def __init__(self, name, datatype, attr=None, get=lambda node: ""):
        self.pos = None
        self.name = name
        self.type = datatype
        self.attr = attr
        self.get_value = get


def iter_children(model, it):
    """Iterate through the children of a row (it)"""

    node = model.iter_children(it)
    while node:
        yield node
        node = model.iter_next(node)


class BaseTreeModel (gtk.GenericTreeModel):
    """
    TreeModel that wraps a subset of a NoteBook

    The subset is defined by the self._roots list.
    """

    def __init__(self, roots=[]):
        gtk.GenericTreeModel.__init__(self)
        self.set_property("leak-references", False)

        self._notebook = None
        self._roots = []
        self._master_node = None
        self._nested = True

        self._columns = []
        self._columns_lookup = {}
        self._node_column = None

        self.set_root_nodes(roots)

        # add default node column
        self.append_column(TreeModelColumn("node", object,
                                           get=lambda node: node))
        self.set_node_column(self.get_column_by_name("node"))

    def set_notebook(self, notebook):
        """
        Set the notebook for this model
        A notebook must be set before any nodes can be added to the model
        """

        # unhook listeners for old notebook. if it exists
        if self._notebook is not None:
            self._notebook.node_changed.remove(self._on_node_changed)

        self._notebook = notebook

        # attach new listeners for new notebook, if it exists
        if self._notebook:
            self._notebook.node_changed.add(self._on_node_changed)

    #==========================
    # column manipulation

    def append_column(self, column):
        """Append a new column to the treemodel"""
        assert column.name not in self._columns_lookup

        column.pos = len(self._columns)
        self._columns.append(column)
        self._columns_lookup[column.name] = column

    def get_column(self, pos):
        """Returns a column from a particular position"""
        return self._columns[pos]

    def get_columns(self):
        """Returns list of columns in treemodel"""
        return self._columns

    def get_column_by_name(self, colname):
        """Returns a columns with the given name"""
        return self._columns_lookup.get(colname, None)

    def add_column(self, name, coltype, get):
        """Append column only if it does not already exist"""
        col = self.get_column_by_name(name)
        if col is None:
            col = TreeModelColumn(name, coltype, get=get)
            self.append_column(col)
        return col

    def get_node_column_pos(self):
        """Returns the column position containing node objects"""
        assert self._node_column is not None
        return self._node_column.pos

    def get_node_column(self):
        """Returns the columns that conatins nodes"""
        return self._node_column

    def set_node_column(self, col):
        """Set the column that contains nodes"""
        self._node_column = col

    if gtk.gtk_version < (2, 10):
        # NOTE: not available in pygtk 2.8?

        def create_tree_iter(self, node):
            return self.get_iter(self.on_get_path(node))

        def get_user_data(self, it):
            return self.on_get_iter(self.get_path(it))

    #================================
    # master nodes and root nodes

    def set_master_node(self, node):
        self._master_node = node

    def get_master_node(self):
        return self._master_node

    def set_nested(self, nested):
        """Sets the 'nested mode' of the treemodel"""
        self._nested = nested
        self.set_root_nodes(self._roots)

    def get_nested(self):
        """Returns True if treemodel is in 'nested mode'
        'nested mode' means rows can have children.
        """
        return self._nested

    def clear(self):
        """Clear all rows from model"""
        for i in xrange(len(self._roots)-1, -1, -1):
            self.row_deleted((i,))

        self._roots = []
        self._root_set = {}

    def set_root_nodes(self, roots=[]):
        """Set the root nodes of the model"""
        # clear the model
        self.clear()

        for node in roots:
            self.append(node)

        # we must have a notebook, so that we can react to NoteBook changes
        if len(roots) > 0:
            assert self._notebook is not None

    def get_root_nodes(self):
        """Returns the root nodes of the treemodel"""
        return self._roots

    def append(self, node):
        """Appends a node at the root level of the treemodel"""
        index = len(self._roots)
        self._root_set[node] = index
        self._roots.append(node)
        rowref = self.create_tree_iter(node)
        self.row_inserted((index,), rowref)
        self.row_has_child_toggled((index,), rowref)
        self.row_has_child_toggled((index,), rowref)

    #==============================
    # notebook callbacks

    def _on_node_changed(self, actions):
        """Callback for when a node changes"""

        # notify listeners that changes in the model will start to occur
        nodes = [a[1] for a in actions if a[0] == "changed" or
                 a[0] == "changed-recurse"]
        self.emit("node-changed-start", nodes)

        for action in actions:
            act = action[0]

            if (act == "changed" or act == "changed-recurse" or
                    act == "added"):
                node = action[1]
            else:
                node = None

            if node and node == self._master_node:
                # reset roots
                self.set_root_nodes(self._master_node.get_children())

            elif act == "changed-recurse":
                try:
                    path = self.on_get_path(node)
                except:
                    continue  # node is not part of model, ignore it
                rowref = self.create_tree_iter(node)
                # TODO: is it ok to create rowref before row_deleted?

                self.row_deleted(path)
                self.row_inserted(path, rowref)
                self.row_has_child_toggled(path, rowref)

            elif act == "added":
                try:
                    path = self.on_get_path(node)
                except:
                    continue  # node is not part of model, ignore it
                rowref = self.create_tree_iter(node)

                self.row_inserted(path, rowref)
                parent = node.get_parent()
                if len(parent.get_children()) == 1:
                    rowref2 = self.create_tree_iter(parent)
                    self.row_has_child_toggled(path[:-1], rowref2)
                self.row_has_child_toggled(path, rowref)

            elif act == "removed":
                parent = action[1]
                index = action[2]

                try:
                    parent_path = self.on_get_path(parent)
                except:
                    continue  # node is not part of model, ignore it
                path = parent_path + (index,)

                self.row_deleted(path)
                rowref = self.create_tree_iter(parent)
                if len(parent.get_children()) == 0:
                    self.row_has_child_toggled(parent_path, rowref)

        # notify listeners that changes in the model have ended
        self.emit("node-changed-end", nodes)

    #=====================================
    # gtk.GenericTreeModel implementation

    def on_get_flags(self):
        """Returns the flags of this treemodel"""
        return gtk.TREE_MODEL_ITERS_PERSIST

    def on_get_n_columns(self):
        """Returns the number of columns in a treemodel"""
        return len(self._columns)

    def on_get_column_type(self, index):
        """Returns the type of a column in the treemodel"""
        return self._columns[index].type

    def on_get_iter(self, path):
        """Returns the node of a path"""
        if path[0] >= len(self._roots):
            return None

        node = self._roots[path[0]]

        for i in path[1:]:
            if i >= len(node.get_children()):
                print path
                raise ValueError()
            node = node.get_children()[i]

        return node

    def on_get_path(self, rowref):
        """Returns the path of a rowref"""
        if rowref is None:
            return ()

        path = []
        node = rowref
        while node not in self._root_set:
            path.append(node.get_attr("order"))
            node = node.get_parent()
            if node is None:
                raise Exception("treeiter is not part of model")
        path.append(self._root_set[node])

        return tuple(reversed(path))

    def on_get_value(self, rowref, column):
        """Returns a value from a row in the treemodel"""
        return self.get_column(column).get_value(rowref)

    def on_iter_next(self, rowref):
        """Returns the next sibling of a rowref"""
        parent = rowref.get_parent()

        if parent is None or rowref in self._root_set:
            n = self._root_set[rowref]
            if n >= len(self._roots) - 1:
                return None
            else:
                return self._roots[n+1]

        children = parent.get_children()
        order = rowref.get_attr("order")
        assert 0 <= order < len(children)

        if order == len(children) - 1:
            return None
        else:
            return children[order+1]

    def on_iter_children(self, parent):
        """Returns the first child of a treeiter"""
        if parent is None:
            if len(self._roots) > 0:
                return self._roots[0]
            else:
                return None
        elif self._nested and len(parent.get_children()) > 0:
            return parent.get_children()[0]
        else:
            return None

    def on_iter_has_child(self, rowref):
        """Returns True of treeiter has children"""
        return self._nested and rowref.has_children()

    def on_iter_n_children(self, rowref):
        """Returns the number of children of a treeiter"""
        if rowref is None:
            return len(self._roots)
        if not self._nested:
            return 0

        return len(rowref.get_children())

    def on_iter_nth_child(self, parent, n):
        """Returns the n'th child of a treeiter"""
        if parent is None:
            if n >= len(self._roots):
                return None
            else:
                return self._roots[n]
        elif not self._nested:
            return None
        else:
            children = parent.get_children()
            if n >= len(children):
                print "out of bounds", parent.get_title(), n
                return None
            else:
                return children[n]

    def on_iter_parent(self, child):
        """Returns the parent of a treeiter"""
        if child in self._root_set:
            return None
        else:
            parent = child.get_parent()
            return parent


gobject.type_register(BaseTreeModel)
gobject.signal_new("node-changed-start", BaseTreeModel,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("node-changed-end", BaseTreeModel,
                   gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))


class KeepNoteTreeModel (BaseTreeModel):
    """
    TreeModel that wraps a subset of a NoteBook

    The subset is defined by the self._roots list.
    """
    def __init__(self, roots=[]):
        BaseTreeModel.__init__(self, roots)

        self.fades = set()

        # add default node column
        #self.append_column(TreeModelColumn("node", object,
        #                                   get=lambda node: node))
        #self.set_node_column(self.get_column_by_name("node"))

        # TODO: move to treeviewer
        # init default columns
        #self.append_column(
        #    TreeModelColumn(
        #        "icon", gdk.Pixbuf,
        #        get=lambda node: get_node_icon(node, False,
        #                                       node in self.fades)))
        #self.append_column(
        #    TreeModelColumn(
        #        "icon_open", gdk.Pixbuf,
        #        get=lambda node: get_node_icon(node, True,
        #                                       node in self.fades)))
        #self.append_column(
        #    TreeModelColumn("title", str,
        #                    attr="title",
        #                    get=lambda node: node.get_attr("title")))
        #self.append_column(
        #    TreeModelColumn("title_sort", str,
        #                    attr="title",
        #                    get=lambda node: node.get_title().lower()))
        #self.append_column(
        #    TreeModelColumn("created_time2", str,
        #                    attr="created_time",
        #                    get=lambda node: self.get_time_text(node,
        #                                                    "created_time")))
        #self.append_column(
        #    TreeModelColumn("created_time2_sort", int,
        #                    attr="created_time",
        #                    get=lambda node: node.get_attr(
        #                        "created_time", 0)))
        #self.append_column(
        #    TreeModelColumn("modified_time", str,
        #                    attr="modified_time",
        #                    get=lambda node: self.get_time_text(node,
        #                                                 "modified_time")))
        #self.append_column(
        #    TreeModelColumn(
        #        "modified_time_sort", int,
        #        attr="modified_time",
        #        get=lambda node: node.get_attr("modified_time", 0)))
        #self.append_column(
        #    TreeModelColumn("order", int,
        #                    attr="order",
        #                    get=lambda node: node.get_attr("order")))
