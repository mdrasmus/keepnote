

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk



# constants
DROP_TREE_MOVE = ("drop_node", gtk.TARGET_SAME_WIDGET, 0)
DROP_PAGE_MOVE = ("drop_selector", gtk.TARGET_SAME_APP, 1)
DROP_NO = ("drop_no", gtk.TARGET_SAME_WIDGET, 0)




def compute_new_path(model, target, drop_position):
    path = model.get_path(target)
    
    if drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or \
       drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
        return path + (0,) #model.get_n_children(target),)
    elif drop_position == gtk.TREE_VIEW_DROP_BEFORE:
        return path
    elif drop_position == gtk.TREE_VIEW_DROP_AFTER:
        return path[:-1] + (path[-1] + 1,)
    else:
        raise Exception("unknown drop position %s" %
            str(drop_position))


def copy_row(treeview, model, source, target, drop_position):

    # move source row
    source_row = model[source]
    if drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or \
       drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
        new = model.prepend(target, source_row)
    elif drop_position == gtk.TREE_VIEW_DROP_BEFORE:
        new = model.insert_before(None, target, source_row)
    elif drop_position == gtk.TREE_VIEW_DROP_AFTER:
        new = model.insert_after(None, target, source_row)
    else:
        raise Exception("unknown drop position %s" %
            str(drop_position))

    # recursively move children
    for n in range(model.iter_n_children(source)):
        child = model.iter_nth_child(source, n)
        copy_row(treeview, model, child, new,
                 gtk.TREE_VIEW_DROP_INTO_OR_BEFORE)

    # expand view to keep the same expansion pattern
    source_is_expanded = treeview.row_expanded(model.get_path(source))
    new_path = model.get_path(new)
    if source_is_expanded:
        treeview.expand_to_path(new_path)

    return new_path

    

def str2path(pathtext):
    """Converts str to tuple path"""
    # sometime GTK returns a str instead of a tuple for a path... weird
    return tuple(map(int, pathtext.split(":")))

    
    
class DataTreeModel (gtk.TreeModel):
    """Provides a mapping from data back to a path in the TreeModel"""

    def __init__(self, data_col, *types):
        self.data_col = data_col
        self.types = types
        self.data2path = {}
        
        self.__signals = []
        
        self.__signals.append(self.connect("row-inserted", self._on_row_inserted))
        self.__signals.append(self.connect("row-deleted", self._on_row_deleted))
        self.__signals.append(self.connect("rows-reordered", self._on_rows_reordered))
        self.__signals.append(self.connect("row-changed", self._on_row_changed))

    #===================================
    # signals

    def block_row_signals(self):
        for signal in self.__signals:
            self.handler_block(signal)
        
    def unblock_row_signals(self):
        for signal in self.__signals:
            self.handler_unblock(signal)
        
    def _on_row_inserted(self, model, path, it):
        parent_path = path[:-1]
        
        nrows = model.iter_n_children(it)
        for i in xrange(path[-1]+1, nrows):
            self.data2path[parent_path + (i,)] = \
                self[parent_path + (i,)][self.data_col]
        
        
    def _on_row_deleted(self, model, path):
        # TODO: do I need path2data so I can delete mapping for deleted rows
        parent_path = path[:-1]
        
        if len(parent_path) > 0:
            it = model.get_iter(parent_path)
        else:
            it = model.get_iter_root()
        nrows = model.iter_n_children(it)
        for i in xrange(path[-1], nrows):
            path2 = parent_path + (i,)
            if path2 in self:
                self.data2path[self[path2][self.data_col]] = path2

                
        
    def _on_rows_reordered(self, model, path, it, new_order):
        nrows = model.iter_n_children(it)
        for i in xrange(nrows):
            path2 = path + (i,)
            self.data2path[self[path2][self.data_col]] = path2
        
    def _on_row_changed(self, model, path, it):
        self.data2path[self[it][self.data_col]] = path


    #=========================
    # data interface
    
    def get_data(self, path):
        if isinstance(path, str):
            path = str2path(path)
        data = self[path][self.data_col]
        self.data2path[data] = path
        return data

    def set_data(self, path, data):
        self.data2path[data] = path

    def get_data_from_iter(self, it):
        return self[it][self.data_col]
    
    
    def get_path_from_data(self, data):
        return self.data2path.get(data, None)


    def refresh_path_data(self, it):
        
        if it is None:
            parent_path = ()
        else:
            parent_path = self.get_path(it)
        
        nrows = self.iter_n_children(it)
        child = self.iter_children(it)
        for i in xrange(nrows):
            path2 = parent_path + (i,)
            self.data2path[self[path2][self.data_col]] = path2
            self.refresh_path_data(child)
            child = self.iter_next(child)


COL_ICON          = 0
COL_ICON_EXPAND   = 1
COL_TITLE         = 2
COL_CREATED_TEXT  = 3
COL_CREATED_INT   = 4
COL_MODIFIED_TEXT = 5
COL_MODIFIED_INT  = 6
COL_MANUAL        = 7
COL_NODE          = 8


class TakeNoteTreeModel (gtk.GenericTreeModel):

    def __init__(self, root):
        self._data_col = data_col
        self._col_types = [gdk.Pixbuf, gdk.Pixbuf, str, str,
                           int, str, int, int, object]
        self._root = root
        
    def set_root_node(self, root):
        self._root = root

    
    def on_get_flags(self):
        return 0
    
    def on_get_n_columns(self):
        return len(self._col_types)

    def on_get_column_type(self, index):
        return self._col_types[index]    
    
    def on_get_iter(self, path):
        if len(path) == 0:
            return self._root
        else:
            node = self._root
            for i in path:
                if i >= len(node.get_children()):
                    raise ValueError()
                node = node.get_children()[i]
    
    def on_get_path(self, rowref):
        path = []
        node = rowref
        while node is not None:
            path.append(node.get_order())
            node = node.get_parent()
        return tuple(reversed(path))
    
    def on_get_value(self, rowref, column):
        node = rowref

        if column == COL_ICON:
            return get_node_icon(node, False)
        elif column == COL_ICON:
            return get_node_icon(node, True)
        elif column == COL_TITLE:
            return node.get_title()
        elif column == COL_CREATED_TEXT:
             return node.get_created_time_text()
        elif column == COL_CREATED_INT:
            return node.get_created_time()
        elif column == COL_MODIFIED_TEXT:
            return node.get_modified_time_text()
        elif column == COL_MODIFIED_INT:
            return node.get_modified_time()
        elif column == COL_MANUAL:
            return node.get_order()
        elif column == COL_NODE:
            return node
    
    def on_iter_next(self, rowref):
        parent = rowref.get_parent()
        children = parent.get_children()
        order = rowref.get_order()

        if order >= len(children) - 1:
            return None
        else:
            return children[order]
    
    def on_iter_children(self, parent):
        if len(parent.get_children()) > 0:
            return parent.get_children()[0]
        else:
            return None
    
    def on_iter_has_child(self, rowref):
        return len(rowref.get_children()) > 0
    
    def on_iter_n_children(self, rowref):
        return len(rowref.get_children())
    
    def on_iter_nth_child(self, parent, n):
        return parent.get_children()[n]
    
    def on_iter_parent(self, child):
        return child.get_parent()
    


class TakeNoteTreeStore (DataTreeModel, gtk.TreeStore):
    def __init__(self, data_col, *types):
        gtk.TreeStore.__init__(self, *types)
        DataTreeModel.__init__(self, data_col, *types)
    
    def clear(self):
        self.data2path.clear()
        gtk.TreeStore.clear(self)

    def append_temp(self, parent):        
        self.append(parent, [None] * len(self.types))



class TakeNoteListStore (DataTreeModel, gtk.ListStore):
    def __init__(self, data_col, *types):
        gtk.ListStore.__init__(self, *types)
        DataTreeModel.__init__(self, data_col, *types)
    
    def clear(self):
        self.data2path.clear()
        gtk.ListStore.clear(self)

