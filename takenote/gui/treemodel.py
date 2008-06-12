


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

from takenote.gui import get_node_icon



# constants
DROP_TREE_MOVE = ("drop_node", gtk.TARGET_SAME_APP, 0)
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
        self._roots = []
        self.set_root_nodes(roots)


    if gtk.gtk_version < (2, 10):
        # NOTE: not available in pygtk 2.8?
        
        def create_tree_iter(self, node):
            return self.get_iter(self.on_get_path(node))

        def get_user_data(self, it):
            return self.on_get_iter(self.get_path(it))        


        
    def set_root_nodes(self, roots=[]):

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



    def on_node_changed(self, node, recurse):
        try:
            path = self.on_get_path(node)
        except:
            # node is not part of model, ignore it
            return
        rowref = self.create_tree_iter(node)
        
        if not recurse:
            self.row_changed(path, rowref)
        else:
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

        return node

    
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
            return children[order+1]

    
    def on_iter_children(self, parent):
        #print "iter_children", parent
        
        if parent is None:
            if len(self._roots) > 0:
                return self._roots[0]
            else:
                return None        
        elif len(parent.get_children()) > 0:
            return parent.get_children()[0]
        else:
            return None
    
    def on_iter_has_child(self, rowref):
        #print "iter_has_child", rowref
        
        return len(rowref.get_children()) > 0
    
    def on_iter_n_children(self, rowref):
        #print "iter_n_children", rowref

        if rowref is None:
            return len(self._roots)

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
                return children[n]
    
    def on_iter_parent(self, child):
        if child in self._root_set:
            return None
        else:
            parent = child.get_parent()
            return parent
        


def get_path_from_node(model, node):
    if node is None:
        return ()

    root_set = {}
    child = model.iter_children(None)
    i = 0
    while child is not None:
        root_set[model.get_value(child, COL_NODE)] = i
        child = model.iter_next(child)
        i += 1
     
    path = []
    while node not in root_set:
        path.append(node.get_order())
        node = node.get_parent()
        if node is None:
            raise Exception("treeiter is not part of model")
    path.append(root_set[node])
    
    return tuple(reversed(path))
    

class TakeNoteBaseTreeView (gtk.TreeView):
    """Base class for treeviews of a NoteBook notes"""

    def __init__(self):
        gtk.TreeView.__init__(self)

        self.model = None
        self._reorderable = True

        # row expand/collapse
        self.expanded_id = self.connect("row-expanded",
                                        self.on_row_expanded)
        self.collapsed_id = self.connect("row-collapsed",
                                         self.on_row_collapsed)

        
        # drag and drop         
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("drag-drop", self.on_drag_drop)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)

        self.enable_model_drag_source(
           gtk.gdk.BUTTON1_MASK, [DROP_TREE_MOVE], gtk.gdk.ACTION_MOVE)
        self.drag_source_set(
            gtk.gdk.BUTTON1_MASK,
            [DROP_TREE_MOVE],
             gtk.gdk.ACTION_MOVE)
        self.enable_model_drag_dest(
           [DROP_TREE_MOVE], gtk.gdk.ACTION_MOVE)
        self.drag_dest_set(gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_MOTION,
            [DROP_TREE_MOVE],
             gtk.gdk.ACTION_MOVE)

    def set_reorderable(self, order):
        self._reorderable = order

    def get_reorderable(self):
        return self._reorderable

    def set_model(self, model):
        if self.model is not None:
            self.model.disconnect(self.insert_id)
            self.model.disconnect(self.has_child_id)

        self.model = model
        gtk.TreeView.set_model(self, self.model)

        if model is not None:
            # init model        
            self.insert_id = self.model.connect("row-inserted",
                                                self.on_row_inserted)
            self.has_child_id = self.model.connect("row-has-child-toggled",
                                                   self.on_row_inserted)



    def on_row_expanded(self, treeview, it, path):
        self.model.get_value(it, COL_NODE).set_expand(True)

        # recursively expand nodes that should be expanded
        def walk(it):
            child = self.model.iter_children(it)
            while child:
                node = self.model.get_value(child, COL_NODE)
                if node.is_expanded():
                    path = self.model.get_path(child)
                    self.expand_row(path, False)
                    walk(child)
                child = self.model.iter_next(child)
        walk(it)
    
    def on_row_collapsed(self, treeview, it, path):
        self.model.get_value(it, COL_NODE).set_expand(False)


    def on_row_inserted(self, treemodel, path, it):
        node = self.model.get_value(it, COL_NODE)
        if node.is_expanded():
            self.expand_row(path, False)


    
    #=============================================
    # drag and drop callbacks    
    
    
    def get_drag_node(self):
        model, source = self.get_selection().get_selected()
        source_path = model.get_path(source)
        return self.model.get_value(source, COL_NODE)

        
    def on_drag_motion(self, treeview, drag_context, x, y, eventtime):
        """Callback for drag motion.
           Indicate which drops are allowed"""        

        self.stop_emission("drag-motion")

        if not self._reorderable:
            return False
        
        # determine destination row   
        dest_row = treeview.get_dest_row_at_pos(x, y)
        
        if dest_row is None:
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            source_path = get_path_from_node(self.model, source_node)
            self.set_drag_dest_row(source_path, gtk.TREE_VIEW_DROP_INTO_OR_AFTER)
            return 
        
        # get target info
        target_path, drop_position  = dest_row
        target = self.model.get_iter(target_path)
        target_node = self.model.get_value(target, COL_NODE)
        new_path = compute_new_path(self.model, target, drop_position)
        
        # process node drops
        if "drop_node" in drag_context.targets:

            # get source
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            source_path = get_path_from_node(self.model, source_node)
            
            # determine if drag is allowed
            if self.drop_allowed(source_node, target_node, drop_position):
                self.set_drag_dest_row(target_path, drop_position)
                return

        # reset dest
        self.set_drag_dest_row(source_path, gtk.TREE_VIEW_DROP_INTO_OR_AFTER)
        #self.unset_rows_drag_dest()



    def on_drag_drop(self, widget, drag_context, x, y, timestamp):

        self.stop_emission("drag-drop")

        if not self._reorderable:
            return False
        
        self.drag_get_data(drag_context, "drop_node")
        return True


    def on_drag_data_delete(self, widget, drag_context):
        self.stop_emission("drag-data-delete")


    def on_drag_data_get(self, widget, drag_context, selection_data,
                         info, timestamp):
        self.stop_emission("drag-data-get")

        model, source = self.get_selection().get_selected()
        source_path = model.get_path(source)
        selection_data.tree_set_row_drag_data(model, source_path)
        
    
    
    def on_drag_data_received(self, treeview, drag_context, x, y,
                              selection_data, info, eventtime):

        self.stop_emission("drag-data-received")
         
        # determine destination row
        dest_row = treeview.get_dest_row_at_pos(x, y)
        if dest_row is None:
            drag_context.finish(False, False, eventtime)
            return
        
        # process node drops
        if "drop_node" in drag_context.targets:
            
            # get target
            target_path, drop_position  = dest_row
            target = self.model.get_iter(target_path)
            target_node = self.model.get_value(target, COL_NODE)
            new_path = compute_new_path(self.model, target, drop_position)
            
            # get source
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            source_path = get_path_from_node(self.model, source_node)
            
            
            # determine if drop is allowed
            if not self.drop_allowed(source_node, target_node, drop_position):
                drag_context.finish(False, False, eventtime)
                return
            
            # do tree move if source path is in our tree
            if source_path is not None:
                # get target and source iters
                source = self.model.get_iter(source_path)

                # record old and new parent paths
                old_parent = source_node.get_parent()
                old_parent_path = source_path[:-1]                
                new_parent_path = new_path[:-1]
                new_parent_it = self.model.get_iter(new_parent_path)
                new_parent = self.model.get_value(new_parent_it, COL_NODE)

                # perform move in notebook model
                try:
                    source_node.move(new_parent, new_path[-1])
                except NoteBookError, e:
                    drag_context.finish(False, False, eventtime)
                    self.emit("error", e.msg, e)
                    return

                if old_parent.is_expanded():
                    self.expand_to_path(old_parent_path)
                
                if new_parent.is_expanded():
                    self.expand_to_path(new_parent_path)
                
                # make sure to show new children
                if (drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or
                    drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                    treeview.expand_row(target_path, False)
                
                drag_context.finish(True, True, eventtime)
                
            else:                
                # process node move that is not in treeview
                new_parent_path = new_path[:-1]
                new_parent_it = self.model.get_iter(new_parent_path)
                new_parent = self.model.get_value(new_parent_it, COL_NODE)
                source_node.move(new_parent, new_path[-1])
                drag_context.finish(True, True, eventtime)

                if new_parent.is_expanded():
                    self.expand_to_path(new_parent_path)
                                
        else:
            drag_context.finish(False, False, eventtime)
            
    
        
    def drop_allowed(self, source_node, target_node, drop_position):
        """Determine if drop is allowed"""
        
        # source cannot be an ancestor of target
        ptr = target_node
        while ptr is not None:
            if ptr == source_node:
                return False
            ptr = ptr.get_parent()
        

        # (1) do not let nodes move out of notebook root
        # (2) do not let nodes move into pages
        return not (target_node.get_parent() is None and \
                    (drop_position == gtk.TREE_VIEW_DROP_BEFORE or 
                     drop_position == gtk.TREE_VIEW_DROP_AFTER)) and \
               not (target_node.is_page() and \
                    (drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or 
                     drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER))



