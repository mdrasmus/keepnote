

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

    
    
class TakeNoteTreeModel (gtk.TreeModel):
    """Provides a mapping from data back to a path in the TreeStore"""

    def __init__(self, data_col): #, *types):
        #gtk.TreeStore.__init__(self, *types)
        self.data_col = data_col
        self.data2path = {}
        
        self.connect("row-inserted", self.on_row_inserted)
        self.connect("row-deleted", self.on_row_deleted)
        self.connect("rows-reordered", self.on_rows_reordered)
        self.connect("row-changed", self.on_row_changed)


    def on_row_inserted(self, model, path, it):
        parent_path = path[:-1]
        
        nrows = model.iter_n_children(it)
        for i in xrange(path[-1]+1, nrows):
            self.data2path[parent_path + (i,)] = \
                self[parent_path + (i,)][self.data_col]
        
        
    def on_row_deleted(self, model, path):
        parent_path = path[:-1]
        
        if len(parent_path) > 0:
            it = model.get_iter(parent_path)
        else:
            it = model.get_iter_root()
        nrows = model.iter_n_children(it)
        for i in xrange(path[-1], nrows):
            path2 = parent_path + (i,)
            self.data2path[self[path2][self.data_col]] = path2
                
        
    def on_rows_reordered(self, model, path, it, new_order):
        nrows = model.iter_n_children(it)
        for i in xrange(nrows):
            path2 = path + (i,)
            self.data2path[self[path2][self.data_col]] = path2
        
    def on_row_changed(self, model, path, it):
        self.data2path[self[it][self.data_col]] = path
    
    
    def get_data(self, path):
        if isinstance(path, str):
            path = str2path(path)
        data = self[path][self.data_col]
        self.data2path[data] = path
        return data

    def get_data_from_iter(self, it):
        return self[it][self.data_col]
    
    
    def get_path_from_data(self, data):
        return self.data2path.get(data, None)




class TakeNoteTreeStore (TakeNoteTreeModel, gtk.TreeStore):
    def __init__(self, data_col, *types):
        gtk.TreeStore.__init__(self, *types)
        TakeNoteTreeModel.__init__(self, data_col)


class TakeNoteListStore (TakeNoteTreeModel, gtk.ListStore):
    def __init__(self, data_col, *types):
        gtk.ListStore.__init__(self, *types)
        TakeNoteTreeModel.__init__(self, data_col)

