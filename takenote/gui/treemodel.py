


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
from takenote.gui import get_node_icon
from takenote.notebook import NoteBookError


# treeview drag and drop config
DROP_TREE_MOVE = ("drop_node", gtk.TARGET_SAME_APP, 0)
DROP_NO = ("drop_no", gtk.TARGET_SAME_WIDGET, 0)


# treeview reorder rules
REORDER_NONE = 0
REORDER_FOLDER = 1
REORDER_ALL = 2


# treeview column numbers
COL_ICON          = 0
COL_ICON_EXPAND   = 1
COL_TITLE         = 2
COL_CREATED_TEXT  = 3
COL_CREATED_INT   = 4
COL_MODIFIED_TEXT = 5
COL_MODIFIED_INT  = 6
COL_MANUAL        = 7
COL_NODE          = 8



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



def get_path_from_node(model, node):
    """Determine the path of a node in a treemodel"""

    # NOTE: I must make no assumptions about the type of the model
    # I could change that if I make a wrapper around TreeSortModel
    
    if node is None:
        return ()

    # determine root set
    root_set = {}
    child = model.iter_children(None)
    i = 0
    while child is not None:
        root_set[model.get_value(child, COL_NODE)] = i
        child = model.iter_next(child)
        i += 1

    # walk up parent path until root set
    node_path = []
    while node not in root_set:
        node_path.append(node)
        node = node.get_parent()
        if node is None:
            raise Exception("treeiter is not part of model")

    # walk back down are record path
    path = [root_set[node]]
    it = model.get_iter(tuple(path))
    for node in reversed(node_path):
        child = model.iter_children(it)
        i = 0

        while child is not None:
            if model.get_value(child, COL_NODE) == node:
                path.append(i)
                it = child
                break
            child = model.iter_next(child)
            i += 1
        else:
            raise Exception("bad model")

    return tuple(path)
        



class TakeNoteTreeModel (gtk.GenericTreeModel):

    _col_types = [gdk.Pixbuf, gdk.Pixbuf, str, str,
                  int, str, int, int, object]

    def __init__(self, roots=[]):
        gtk.GenericTreeModel.__init__(self)
        self.set_property("leak-references", False)
        
        
        self._notebook = None
        self._roots = []
        self._master_node = None
        self._date_formats = None
        self.set_root_nodes(roots)
        self._nested = True


    if gtk.gtk_version < (2, 10):
        # NOTE: not available in pygtk 2.8?
        
        def create_tree_iter(self, node):
            return self.get_iter(self.on_get_path(node))

        def get_user_data(self, it):
            return self.on_get_iter(self.get_path(it))        


    def set_master_node(self, node):
        self._master_node = node

    def get_master_node(self):
        return self._master_node

    def set_date_formats(self, formats):
        self._date_formats = formats

    def set_nested(self, nested):
        self._nested = nested
        self.set_root_nodes(self._roots)

    
    def set_root_nodes(self, roots=[]):

        for i in xrange(len(self._roots)-1, -1, -1):
            self.row_deleted((i,))
        
        self._roots = []
        self._root_set = {}
        for i, node in enumerate(roots):
            self._roots.append(node)
            self._root_set[node] = i
            rowref = self.create_tree_iter(node)
            self.row_inserted((i,), rowref)
            self.row_has_child_toggled((i,), rowref)
            self.row_has_child_toggled((i,), rowref)

        if self._notebook is not None:
            self._notebook.node_changed.remove(self.on_node_changed)
            self._notebook = None

        if len(roots) > 0:
            self._notebook = roots[0].get_notebook()
            self._notebook.node_changed.add(self.on_node_changed)



    def on_node_changed(self, node, recurse):

        self.emit("node-changed-start", node)
        
        if node == self._master_node:
            # reset roots
            self.set_root_nodes(self._master_node.get_children())
        else:                        
            try:
                path = self.on_get_path(node)
            except:
                # node is not part of model, ignore it
                return
            rowref = self.create_tree_iter(node)
        
            if False: #not recurse:
                # seems like I shouldn't use this
                # it won't update the list view properly
                # when a single item changes it name
                self.row_changed(path, rowref)
            else:
                for i, child in enumerate(node.get_children()):
                    path2 = path + (i,)
                    self.row_deleted(path2)                    
            
                self.row_deleted(path)
                self.row_inserted(path, rowref)
                self.row_has_child_toggled(path, rowref)
                self.row_has_child_toggled(path, rowref)

        self.emit("node-changed-end", node)

    
    def on_get_flags(self):
        return gtk.TREE_MODEL_ITERS_PERSIST
    
    def on_get_n_columns(self):
        return len(self._col_types)

    def on_get_column_type(self, index):
        return self._col_types[index]
    
    def on_get_iter(self, path):
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
        elif column == COL_ICON_EXPAND:
            return get_node_icon(node, True)
        elif column == COL_TITLE:
            return node.get_title()
        elif column == COL_CREATED_TEXT:
             return node.get_created_time_text(self._date_formats)
        elif column == COL_CREATED_INT:
            return node.get_created_time()
        elif column == COL_MODIFIED_TEXT:
            return node.get_modified_time_text(self._date_formats)
        elif column == COL_MODIFIED_INT:
            return node.get_modified_time()
        elif column == COL_MANUAL:
            return node.get_order()
        elif column == COL_NODE:
            return node
    
    def on_iter_next(self, rowref):
        parent = rowref.get_parent()

        #if parent is None:
        if parent is None or rowref in self._root_set:
            n = self._root_set[rowref]
            if n >= len(self._roots) - 1:
                return None
            else:
                return self._roots[n+1]
        
        children = parent.get_children()
        order = rowref.get_order()
        assert 0 <= order < len(children)
        
        if order == len(children) - 1:
            return None
        else:
            return children[order+1]

    
    def on_iter_children(self, parent):
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
        return self._nested and len(rowref.get_children()) > 0
    
    def on_iter_n_children(self, rowref):
        if rowref is None:
            return len(self._roots)
        if not self._nested:
            return 0

        return len(rowref.get_children())
    
    def on_iter_nth_child(self, parent, n):
        
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

gobject.type_register(TakeNoteTreeModel)
gobject.signal_new("node-changed-start", TakeNoteTreeModel, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("node-changed-end", TakeNoteTreeModel, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))



class TakeNoteBaseTreeView (gtk.TreeView):
    """Base class for treeviews of a NoteBook notes"""

    def __init__(self):
        gtk.TreeView.__init__(self)

        self.model = None
        self._reorder = REORDER_ALL
        self._dest_row = None
        self._master_node = None
        self.editing = False
        self.__sel_nodes = []
        self.__sel_nodes2 = []

        # selection
        self.get_selection().connect("changed", self.__on_select_changed)

        # row expand/collapse
        self.expanded_id = self.connect("row-expanded",
                                        self.on_row_expanded)
        self.collapsed_id = self.connect("row-collapsed",
                                         self.on_row_collapsed)

        
        # drag and drop
        self.connect("drag-begin", self.on_drag_begin)
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
    
    def set_master_node(self, node):
        self._master_node = node

    def set_reorder(self, order):
        self._reorder = order

    def get_reorderable(self):
        return self._reorder


    def set_model(self, model):
        """Set the model for the view"""


        # if model already attached, disconnect all of its signals
        if self.model is not None:
            if hasattr(self.model, "get_model"):
                self.model.get_model().disconnect(self.changed_start_id)
                self.model.get_model().disconnect(self.changed_end_id)
            else:
                self.model.disconnect(self.changed_start_id)
                self.model.disconnect(self.changed_end_id)
            self.model.disconnect(self.insert_id)
            self.model.disconnect(self.delete_id)
            self.model.disconnect(self.has_child_id)

        # set new model
        self.model = model
        gtk.TreeView.set_model(self, self.model)

        # set new model
        if model is not None:
            # init signals for model
            if hasattr(self.model, "get_model"):
                self.changed_start_id = self.model.get_model().\
                    connect("node-changed-start", self.on_node_changed_start)
                self.changed_end_id = self.model.get_model().\
                    connect("node-changed-end", self.on_node_changed_end)
            else:
                self.changed_start_id = self.model.connect("node-changed-start",
                                                           self.on_node_changed_start)
                self.changed_end_id = self.model.connect("node-changed-end",
                                                         self.on_node_changed_end)                
            self.insert_id = self.model.connect("row-inserted",
                                                self.on_row_inserted)
            self.delete_id = self.model.connect("row-deleted",
                                                self.on_row_deleted)
            self.has_child_id = self.model.connect("row-has-child-toggled",
                                                   self.on_row_has_child_toggled)



    #=========================================
    # model change callbacks

    def on_node_changed_start(self, model, node):
        # remember which nodes are selected
        self.__sel_nodes2[:] = self.__sel_nodes


    def on_node_changed_end(self, model, node):
        # if nodes still exist, try to reselect them
        if len(self.__sel_nodes2) > 0:
            try:
                path2 = get_path_from_node(self.model, self.__sel_nodes2[0])
                self.set_cursor(path2)
                self.scroll_to_cell(path2)
            except:
                pass


    def __on_select_changed(self, treeselect):
        """Keep track of which nodes are selected"""
        model, paths = treeselect.get_selected_rows()

        self.__sel_nodes = [self.model.get_value(self.model.get_iter(path),
                                                 COL_NODE)
                            for path in paths]
    

    def is_node_expanded(self, node):
        # query expansion from nodes
        return node.is_expanded()

    def set_node_expanded(self, node, expand):
        # save expansion in node
        node.set_expand(expand)
        

    def on_row_expanded(self, treeview, it, path):
        """Callback for row expand

           Performs smart expansion (remembers children expansion)"""

        # save expansion in node
        self.set_node_expanded(self.model.get_value(it, COL_NODE), True)

        # recursively expand nodes that should be expanded
        def walk(it):
            child = self.model.iter_children(it)
            while child:
                node = self.model.get_value(child, COL_NODE)
                if self.is_node_expanded(node):
                    path = self.model.get_path(child)
                    self.expand_row(path, False)
                    walk(child)
                child = self.model.iter_next(child)
        walk(it)
    
    def on_row_collapsed(self, treeview, it, path):
        # save expansion in node
        self.set_node_expanded(self.model.get_value(it, COL_NODE), False)


    def on_row_inserted(self, model, path, it):

        # maintain proper expansion
        node = self.model.get_value(it, COL_NODE)
        if self.is_node_expanded(node):
            self.expand_row(path, False)


    def on_row_deleted(self, model, path):
        pass

    def on_row_has_child_toggled(self, model, path, it):

        # maintain proper expansion
        node = self.model.get_value(it, COL_NODE)
        if self.is_node_expanded(node):
            self.expand_row(path, False)        


    #===========================================
    # actions

    def select_nodes(self, nodes):

        # NOTE: for now only select one node
        if len(nodes) > 0:
            node = nodes[0]
            try:
                path = get_path_from_node(self.model, node)
                self.expand_to_path(path)
                self.set_cursor(path)
                self.scroll_to_cell(path)
            except:
                pass
        else:

            # NOTE: this may be invalid
            self.set_cursor(None)


    #============================================
    # editing titles
    
    def on_editing_started(self, cellrenderer, editable, path):
        """Callback for start of title editing"""
        # remember editing state
        self.editing = True
    
    def on_editing_canceled(self, cellrenderer):
        """Callback for canceled of title editing"""
        # remember editing state
        self.editing = False

    def on_edit_title(self, cellrenderertext, path, new_text):
        """Callback for completion of title editing"""

        # remember editing state
        self.editing = False

        # get node being edited
        node = self.model.get_value(self.model.get_iter(path), COL_NODE)
        if node is None:
            return
        
        # do not allow empty names
        if new_text.strip() == "":
            return

        # set new title and catch errors
        if new_text != node.get_title():
            try:
                node.rename(new_text)            
            except NoteBookError, e:
                self.emit("error", e.msg, e)

        # reselect node
        self.set_cursor((0,))
        self.set_cursor(path)
        self.scroll_to_cell(path)
        
    

    
    #=============================================
    # drag and drop callbacks    
    
    
    def get_drag_node(self):
        model, source = self.get_selection().get_selected()
        source_path = model.get_path(source)
        return self.model.get_value(source, COL_NODE)


    def on_drag_begin(self, treeview, drag_context):
        self.stop_emission("drag-begin")
        
        model, source = self.get_selection().get_selected()
        pixbuf = self.model.get_value(source, COL_ICON)
        pixbuf = pixbuf.scale_simple(40, 40, gtk.gdk.INTERP_BILINEAR)
        self.drag_source_set_icon_pixbuf(pixbuf)
        source_path = model.get_path(source)
        self._dest_row = None

        
    def on_drag_motion(self, treeview, drag_context, x, y, eventtime):
        """Callback for drag motion.
           Indicate which drops are allowed"""        

        self.stop_emission("drag-motion")

        if self._reorder == REORDER_NONE:
            return False
        
        # determine destination row   
        dest_row = treeview.get_dest_row_at_pos(x, y)
        
        if dest_row is not None:
            # get target info
            target_path, drop_position = dest_row
            target = self.model.get_iter(target_path)
            target_node = self.model.get_value(target, COL_NODE)
        
            # process node drops
            if "drop_node" in drag_context.targets:
                # get source
                source_widget = drag_context.get_source_widget()
                source_node = source_widget.get_drag_node()
                source_path = get_path_from_node(self.model, source_node)
            
                # determine if drag is allowed
                if self.drop_allowed(source_node, target_node, drop_position):
                    self.set_drag_dest_row(target_path, drop_position)
                    self._dest_row = target_path, drop_position


    def on_drag_drop(self, widget, drag_context, x, y, timestamp):

        self.stop_emission("drag-drop")

        if self._reorder == REORDER_NONE:
            drag_context.finish(False, False, timestamp)
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
         
        # if no destination, give up
        if self._dest_row is None:
            drag_context.finish(False, False, eventtime)
            return
        
        # process node drops
        if "drop_node" in drag_context.targets:
            
            # get target
            target_path, drop_position  = self._dest_row
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
                if len(new_parent_path) == 0:
                    new_parent = self._master_node
                    assert self._master_node is not None
                else:
                    new_parent_it = self.model.get_iter(new_parent_path)
                    new_parent = self.model.get_value(new_parent_it, COL_NODE)

                # perform move in notebook model
                try:
                    source_node.move(new_parent, new_path[-1])
                except NoteBookError, e:
                    drag_context.finish(False, False, eventtime)
                    self.emit("error", e.msg, e)
                    return

                if len(old_parent_path) > 0 and old_parent.is_expanded():
                    self.expand_to_path(old_parent_path)
                
                if len(new_parent_path) > 0 and new_parent.is_expanded():
                    self.expand_to_path(new_parent_path)
                
                # make sure to show new children
                if (drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or
                    drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                    treeview.expand_row(target_path, False)
                
                drag_context.finish(True, True, eventtime)
                
            else:                
                # process node move that is not in treeview
                new_parent_path = new_path[:-1]
                if len(new_parent_path) == 0:
                    new_parent = self._master_node
                    assert self._master_node is not None
                else:
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
        # (3) only allow INTO drops if reorder == FOLDER
        return not (target_node.get_parent() is None and \
                    (drop_position == gtk.TREE_VIEW_DROP_BEFORE or 
                     drop_position == gtk.TREE_VIEW_DROP_AFTER)) and \
               not (target_node.is_page() and \
                    (drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or 
                     drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER)) and \
               not (self._reorder == REORDER_FOLDER and \
                    (drop_position not in (gtk.TREE_VIEW_DROP_INTO_OR_BEFORE,
                                           gtk.TREE_VIEW_DROP_INTO_OR_AFTER)))



