


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

from takenote.gui import get_node_icon



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

    _col_types = [gdk.Pixbuf, gdk.Pixbuf, str, str,
                  int, str, int, int, object]

    def __init__(self, roots=[]):
        gtk.GenericTreeModel.__init__(self)
        self.set_property("leak-references", False)
        
        
        self._notebook = None
        self._refs = set()
        self._roots = []
        self.set_root_nodes(roots)


    if gtk.ver < (2, 10):
        # NOTE: not available in pygtk 2.8?
        
        def create_tree_iter(self, node):
            return self.get_iter(self.on_get_path(node))

        def get_user_data(self, it):
            return self.on_get_iter(self.get_path(it))        


        
    def set_root_nodes(self, roots=[]):

        # since roots have changed, invalidate all iters
        #paths = [self.on_get_path(x) for x in self._refs]
        #paths.sort(reverse=True)
        #for path in paths:
        #    self.row_deleted(path)
        #self._refs.clear()

        for i in xrange(len(self._roots)-1, -1, -1):
            self.row_deleted((i,))
        
        
        self._roots = list(roots)
        self._root_set = {}
        for i, node in enumerate(self._roots):
            self._root_set[node] = i

        if self._notebook is not None:
            self._notebook.node_changed.remove(self.on_node_changed)
            self._notebook = None

        if len(roots) > 0:
            self._notebook = roots[0].get_notebook()
            self._notebook.node_changed.add(self.on_node_changed)

        for node in self._roots:
            self._ensure_ref(node)


    def _ensure_ref(self, node):
        if node is None:
            return None
        self._refs.add(node)
        return node
    

    def on_node_changed(self, node, recurse):
        
        if not recurse:
            path = self.on_get_path(node)
            rowref = self.create_tree_iter(node)
            self.row_changed(path, rowref)
        else:
            path = self.on_get_path(node)
            rowref = self.create_tree_iter(node)

            '''
            def walk(node, path, clean):
                for i, child in enumerate(node.get_children()):
                    path2 = path + (i,)
                    if clean or child in self._refs:
                        self._refs.remove(child)
                        self.row_deleted(path2)
                    walk(child, path2, False)
            walk(node, path, True)
            '''

            #self._refs.add(node)

            #print "changed", node.get_title(), path

            for i, child in enumerate(node.get_children()):
                path2 = path + (i,)
                self.row_deleted(path2)
                    
            
            self.row_deleted(path)
            self.row_inserted(path, rowref)
            self.row_has_child_toggled(path, rowref)
            self.row_has_child_toggled(path, rowref)


    
    def on_get_flags(self):
        return gtk.TREE_MODEL_ITERS_PERSIST
    
    def on_get_n_columns(self):
        return len(self._col_types)

    def on_get_column_type(self, index):
        return self._col_types[index]
    
    def on_get_iter(self, path):
        #print "get_iter", path, self._roots
        
        if path[0] >= len(self._roots):
            return None
        
        node = self._roots[path[0]]
                
        for i in path[1:]:
            if i >= len(node.get_children()):
                raise ValueError()
            node = node.get_children()[i]
            self._refs.add(node)

        return self._ensure_ref(node)

    
    def on_get_path(self, rowref):
        if rowref is None:
            return ()
        
        path = []
        node = rowref
        while node not in self._root_set:
            path.append(node.get_order())
            node = node.get_parent()
            if node is None:
                raise Exception("treeiter is not part of model")
        path.append(self._root_set[node])
        
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
        #print "iter_next", rowref
        
        parent = rowref.get_parent()

        if parent is None:
            n = self._root_set[rowref]
            if n >= len(self._roots) - 1:
                #print "root", n
                return None
            else:
                return self._roots[n+1]
        
        children = parent.get_children()
        order = rowref.get_order()
        assert 0 <= order < len(children)
        
        if order == len(children) - 1:
            #print "last child", rowref.get_title(), order
            return None
        else:
            return self._ensure_ref(children[order+1])

    
    def on_iter_children(self, parent):
        #print "iter_children", parent
        
        if parent is None:
            if len(self._roots) > 0:
                return self._roots[0]
            else:
                return None        
        elif len(parent.get_children()) > 0:
            return self._ensure_ref(parent.get_children()[0])
        else:
            return None
    
    def on_iter_has_child(self, rowref):
        #print "iter_has_child", rowref
        
        return len(rowref.get_children()) > 0
    
    def on_iter_n_children(self, rowref):
        #print "iter_n_children", rowref

        if rowref is None:
            print "root"
            return len(self._roots)

        print "nchildren", rowref.get_title(), len(rowref.get_children())
        return len(rowref.get_children())
    
    def on_iter_nth_child(self, parent, n):
        
        if parent is None:
            if n >= len(self._roots):
                return None
            else:
                return self._roots[n]
        else:
            #print "nth child", parent.get_title(), n
            
            children = parent.get_children()
            if n >= len(children):
                print "out of bounds"
                return None
            else:
                return self._ensure_ref(children[n])
    
    def on_iter_parent(self, child):
        if child in self._root_set:
            return None
        else:
            parent = child.get_parent()
            return self._ensure_ref(parent)
    

    def get_data(self, path):
        return self.on_get_iter(path)
    

    def get_data_from_iter(self, it):
        return self.get_user_data(it)
    
    
    def get_path_from_data(self, data):
        return self.on_get_path(data)



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

