"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for TakeNote Application
"""

# TODO: shade undo/redo
# TODO: add pages in treeview
#       will eventually require lazy loading for treeview
# TODO: add framework for customized page selector columns
# TODO: add html links
# TODO: make better font selector
# TODO: add colored text



# python imports
import sys, os, tempfile, re

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenote
from takenote.undo import UndoStack
from takenote.richtext import RichTextView, RichTextImage

# constants
PROGRAM_NAME = "TakeNode"
PROGRAM_VERSION = "0.1"

DROP_TREE_MOVE = ("drop_node", gtk.TARGET_SAME_WIDGET, 0)
DROP_PAGE_MOVE = ("drop_selector", gtk.TARGET_SAME_APP, 1)
DROP_NO = ("drop_no", gtk.TARGET_SAME_WIDGET, 0)



BASEDIR = ""
def get_resource(*path_list):
    return os.path.join(BASEDIR, *path_list)


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
    


class DataMap (object):
    def __init__(self):
        self.data2path = {}
        self.path2data = {}
    
    def get_path(self, data):
        return self.data2path.get(data, None)
    
    def get_data(self, path):
        if isinstance(path, str):
            path = str2path(path)
        data = self.path2data.get(path, None)
        assert data is not None, path
        return data
    
    def remove_path(self, path):
        if path in self.path2data:
            data = self.path2data[path]
            del self.path2data[path]
            del self.data2path[data]
    
    def remove_path_all(self, path, get_child_data):
        """Recursively remove path and all its descendants"""
        if path in self.path2data:
            data = self.path2data[path]
            
            for child in get_child_data(data):
                child_path = self.get_path(child)
                if child_path is not None:
                    self.remove_path_all(child_path, get_child_data)
            
            del self.path2data[path]
            del self.data2path[data]
    
    def add_path(self, path, data):
        self.data2path[data] = path
        self.path2data[path] = data
    
    def add_path_all(self, path, data, get_child_data):
        """Recursively add paths for data and all its descendants"""
        
        for i, child in enumerate(get_child_data(data)):
            self.add_path_all(path + (i,), child, get_child_data)
        
        self.data2path[data] = path
        self.path2data[path] = data

    
    def clear_path(self):
        self.data2path.clear()
        self.path2data.clear()
    
    
    def assert_path(self, path, get_child_data):
        data = self.get_data(path)
        
        for i, child in enumerate(get_child_data(data)):            
            path2 = path + (i,)
            child2 = self.get_data(path2)
            
            assert child2 == child
            self.assert_path(path2, get_child_data)
            
        
    
            
        

def str2path(pathtext):
    """Converts str to tuple path"""
    # sometime GTK returns a str instead of a tuple for a path... weird
    return tuple(map(int, pathtext.split(":")))


def dnd_sanity_check(source_path, target_path):
    """The target cannot be a descendant of the source
       i.e. You cannot become your descendent's child
       i.e. The source path cannot be a prefix of the target path"""
    return source_path != target_path[:len(source_path)]
    
    
class TakeNoteTreeModel (gtk.TreeStore):
    def __init__(self, data_col, *kinds):
        gtk.TreeStore.__init__(self, *kinds)
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
            self.data2path[parent_path + (i,)] = \
                self[parent_path + (i,)][self.data_col]
        
    def on_rows_reordered(self, model, path, it, new_order):
        pass #print "reordered", path
        
    def on_row_changed(self, model, path, it):
        self.data2path[self[it][self.data_col]] = path
    
    
    def get_data(self, path):
        data = self[path][self.data_col]
        self.data2path[data] = path
        return data
    
    
    def get_path_from_data(self, data):
        return self.data2path.get(data, None)
        

class TakeNoteTreeView (gtk.TreeView):
    
    def __init__(self):
        gtk.TreeView.__init__(self)
    
        self.on_select_node = None
        
        
        # create a TreeStore with one string column to use as the model
        self.model = TakeNoteTreeModel(2, gdk.Pixbuf, str, object)
                        
        # init treeview
        self.set_model(self.model)
        
        self.connect("key-release-event", self.on_key_released)
        self.expanded_id = self.connect("row-expanded", self.on_row_expanded)
        self.collapsed_id = self.connect("row-collapsed", self.on_row_collapsed)
                 
        self.connect("drag-begin", self.on_drag_begin)
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("drag-data-received", self.on_drag_data_received)
        #self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.get_selection().connect("changed", self.on_select_changed)
        self.set_headers_visible(False)
        #self.set_property("enable-tree-lines", True)
        # make treeview searchable
        self.set_search_column(1) 
        self.set_reorderable(True)        
        self.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK, [DROP_TREE_MOVE], gtk.gdk.ACTION_MOVE)
        self.enable_model_drag_dest(
            [DROP_TREE_MOVE, DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
        #self.set_fixed_height_mode(True)       

        # create the treeview column
        self.column = gtk.TreeViewColumn()
        self.column.set_clickable(False)
        self.append_column(self.column)

        # create a cell renderers
        self.cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()
        self.cell_text.connect("edited", self.on_edit_title)
        self.cell_text.set_property("editable", True)        

        # add the cells to column
        self.column.pack_start(self.cell_icon, False)
        self.column.pack_start(self.cell_text, True)

        # map cells to columns in treestore
        self.column.add_attribute(self.cell_icon, 'pixbuf', 0)
        self.column.add_attribute(self.cell_text, 'text', 1)
        
        self.icon = gdk.pixbuf_new_from_file(get_resource("images", "open.xpm"))
        #self.drag_source_set_icon_pixbuf(self.icon)
        

        
    
    #=============================================
    # drag and drop callbacks    
    
    
    def get_drag_node(self):
        model, source = self.get_selection().get_selected()
        source_path = model.get_path(source)
        return self.model.get_data(source_path)
    
    
    def on_drag_begin(self, widget, drag_context):
        pass
        #drag_context.drag_set_selection("tree")
        #drag_context.set_icon_pixbuf(self.icon, 0, 0)
        #self.stop_emission("drag-begin")
     
    
    def on_drag_motion(self, treeview, drag_context, x, y, eventtime):
        """Callback for drag motion.
           Indicate which drops are allowed"""
        
        # determine destination row   
        dest_row = treeview.get_dest_row_at_pos(x, y)
        
        if dest_row is None:
            return
        
        # process node drops
        if "drop_node" in drag_context.targets:
        
            # get target and source
            target_path, drop_position  = dest_row
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            target_node = self.model.get_data(target_path)
            
            # determine if drag is allowed
            if self.drop_allowed(source_node, target_node, drop_position):
                treeview.enable_model_drag_dest([DROP_TREE_MOVE, DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
            else:
                treeview.enable_model_drag_dest([DROP_NO], gtk.gdk.ACTION_MOVE)
        
        elif "drop_selector" in drag_context.targets:
            # NOTE: this is until pages are in treeview
            
            # get target and source
            target_path, drop_position  = dest_row
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            target_node = self.model.get_data(target_path)
            
            # determine if drag is allowed
            if self.drop_allowed(source_node, target_node, drop_position) and \
               drop_position not in (gtk.TREE_VIEW_DROP_BEFORE,
                                     gtk.TREE_VIEW_DROP_AFTER):
                treeview.enable_model_drag_dest([DROP_TREE_MOVE, DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
            else:
                treeview.enable_model_drag_dest([DROP_NO], gtk.gdk.ACTION_MOVE)

        
    
    def on_drag_data_received(self, treeview, drag_context, x, y,
                              selection_data, info, eventtime):
            
         
        # determine destination row
        dest_row = treeview.get_dest_row_at_pos(x, y)
        if dest_row is None:
            drag_context.finish(False, False, eventtime)
            return
        
        # process node drops
        if "drop_node" in drag_context.targets or \
           "drop_selector" in drag_context.targets:
            
            # get target and source info
            target_path, drop_position  = dest_row
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            target_node = self.model.get_data(target_path)
            source_path = self.model.get_path_from_data(source_node)
            
            
            # determine if drop is allowed
            if not self.drop_allowed(source_node, target_node, drop_position):
                drag_context.finish(False, False, eventtime)
                return
            
            # do tree move if source path is in our tree
            if source_path is not None:
                # get target and source iters
                target = self.model.get_iter(target_path)
                source = self.model.get_iter(source_path)
                
                
                # record old and new parent paths
                old_parent = source_node.get_parent()
                old_parent_path = source_path[:-1]
                new_path = compute_new_path(self.model, target, drop_position)
                new_parent_path = new_path[:-1]
                new_parent = self.model.get_data(new_parent_path)

                # perform move in notebook model
                source_node.move(new_parent, new_path[-1])

                # perform move in tree model
                self.handler_block(self.expanded_id)
                self.handler_block(self.collapsed_id)

                copy_row(treeview, self.model, source, target, drop_position)

                self.handler_unblock(self.expanded_id)
                self.handler_unblock(self.collapsed_id)
                
                # make sure to show new children
                if (drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or
                    drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                    treeview.expand_row(target_path, False)
                
                drag_context.finish(True, True, eventtime)
            else:
                assert source_node.is_page()
                
                # NOTE: this is here until pages are in treeview
                if drop_position in (gtk.TREE_VIEW_DROP_BEFORE,
                                     gtk.TREE_VIEW_DROP_AFTER):
                    drag_context.finish(False, False, eventtime)
                else:
                    # process node move that is not in treeview
                    target = self.model.get_iter(target_path)
                    new_path = compute_new_path(self.model, target, drop_position)
                    new_parent_path = new_path[:-1]
                    new_parent = self.model.get_data(new_parent_path)
                    source_node.move(new_parent, new_path[-1])
                    drag_context.finish(True, True, eventtime)
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
        
        
        return not (target_node.get_parent() is None and \
                    (drop_position == gtk.TREE_VIEW_DROP_BEFORE or 
                     drop_position == gtk.TREE_VIEW_DROP_AFTER))
    
    #=============================================
    # gui callbacks    
    
    def on_row_expanded(self, treeview, it, path):
        self.model.get_data(path).set_expand(True)

    def on_row_collapsed(self, treeview, it, path):
        self.model.get_data(path).set_expand(False)

        
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete"):
            self.on_delete_node()
            self.stop_emission("key-release-event")
            

    def on_edit_title(self, cellrenderertext, path, new_text):
        try:
            node = self.model.get_data(path)
            node.rename(new_text)
            
            self.model[path][1] = new_text
        except Exception, e:
            print e
            print "takenote: could not rename '%s'" % node.get_title()
    
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0 and self.on_select_node:
            self.on_select_node(self.model.get_data(paths[0]))
        return True
    
    
    def on_delete_node(self):
        
        model, it = self.get_selection().get_selected()
        node = self.model.get_data(model.get_path(it))
        parent = node.get_parent()
        
        if parent is not None:
            node.delete()
            self.update_node(parent)
        else:
            # warn
            print "Cannot delete notebook's toplevel directory"
        
        if self.on_select_node:
            self.on_select_node(None)
           
    
    #==============================================
    # actions
    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
            #self.datamap.clear_path()
        
        else:
            root = self.notebook.get_root_node()
            self.add_node(None, root)
            
    
    
    def edit_node(self, node):
        path = self.model.get_path_from_data(node)
        self.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        self.scroll_to_cell(path)

    
    def expand_node(self, node):
        path = self.model.get_path_from_data(node)
        self.expand_to_path(path)
        
    
    def add_node(self, parent, node):
        it = self.model.append(parent, [self.icon, node.get_title(), node])
        path = self.model.get_path(it)
        
        for child in node.get_children():
            self.add_node(it, child)
        
        if node.is_expanded():
            self.expand_to_path(self.model.get_path_from_data(node))
    
    
    def update_node(self, node):
        path = self.model.get_path_from_data(node)
        expanded = self.row_expanded(path)
        
        for child in self.model[path].iterchildren():
            self.model.remove(child.iter)
        
        it = self.model.get_iter(path)
        for child in node.get_children():
            self.add_node(it, child)
        
        self.expand_to_path(path)
        
    
    
class SelectorColumn (object):
    def __init__(self, name, kind, col):
        self.name = name
        self.kind = kind
        self.col = col

TITLE_COLUMN = SelectorColumn("Title", str, 0)
CREATED_COLUMN = SelectorColumn("Created", str, 1)
MODIFIED_COLUMN = SelectorColumn("Modified", str, 2)


class TakeNoteSelector (gtk.TreeView):
    
    def __init__(self):
        gtk.TreeView.__init__(self)
        self.drag_nodes = []
    
        self.on_select_node = None
        self.on_status = None
        self.sel_nodes = None
        self.notebook_tree = None
        
        self.display_columns = []
        
        # init model
        self.model = gtk.ListStore(gdk.Pixbuf, str, str, int, str, int, object)
        self.model.connect("rows-reordered", self.on_rows_reordered)
        self.datamap = DataMap()        
        
        # init view
        self.set_model(self.model)
        self.connect("key-release-event", self.on_key_released)        
        self.get_selection().connect("changed", self.on_select_changed)
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.set_rules_hint(True)
        self.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK, [DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
        self.enable_model_drag_dest(
            [DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)                
        #self.set_fixed_height_mode(True)
        
        cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()
        self.column = gtk.TreeViewColumn()
        self.column.set_title("Title")
        self.column.set_property("resizable", True)
        self.append_column(self.column)
        
        
        self.column.pack_start(cell_icon, False)
        self.column.pack_start(self.cell_text, True)
        self.cell_text.connect("edited", self.on_edit_title)
        self.cell_text.set_property("editable", True)
        self.column.set_sort_column_id(1)
        # map cells to columns in model
        self.column.add_attribute(cell_icon, 'pixbuf', 0)
        self.column.add_attribute(self.cell_text, 'text', 1)
        
        
        cell_text = gtk.CellRendererText()
        column = gtk.TreeViewColumn()
        column.set_title("Created")
        column.set_property("resizable", True)
        column.set_sort_column_id(3)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 2)
        self.append_column(column)

        cell_text = gtk.CellRendererText()
        column = gtk.TreeViewColumn()
        column.set_property("resizable", True)
        column.set_sort_column_id(5)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.set_title("Modified")
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 4)
        self.append_column(column)        
        
        # set default sorting
        self.model.set_sort_column_id(3, gtk.SORT_DESCENDING)
        
        self.icon = gdk.pixbuf_new_from_file(get_resource("images", "copy.xpm"))
        

    #=============================================
    # drag and drop callbacks
    
    def get_drag_node(self):
        model, source = self.get_selection().get_selected()
        source_path = model.get_path(source)
        node = self.datamap.get_data(source_path)
        self.drag_nodes = [node]
        return node
    
    
    def on_drag_motion(self, treeview, drag_context, x, y, eventtime):
        """Callback for drag motion.
           Indicate which drops are allowed"""
        
        
        # determine destination row   
        if self.notebook_tree is None:
            return
        
        dest_row = treeview.get_dest_row_at_pos(x, y)
        if dest_row is None:
            return
        
        # TODO: allow reorder in selector
        """
        # get target and source
        target_path, drop_position  = dest_row    
        model, source = treeview.get_selection().get_selected()
        source_path = model.get_path(source)
        
        # determine if drag is allowed
        if self.drop_allowed(source_path, target_path, drop_position):
            treeview.enable_model_drag_dest([DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
        else:
            treeview.enable_model_drag_dest([DROP_NO], gtk.gdk.ACTION_MOVE)    
        """
    
    
    def on_drag_data_delete(self, widget, drag_context):
        if drag_context.drag_drop_succeeded():
            self.set_model(None)
        
            node = self.drag_nodes[0]
            path = self.datamap.get_path(node)
            nodes = []
            
            # remove old datamaps
            nrows = self.model.iter_n_children(None)
            self.datamap.remove_path(path)
            for i in xrange(path[0]+1, nrows):
                nodes.append(self.datamap.get_data((i,)))
                self.datamap.remove_path((i,))
            
            # remove row
            it = self.model.get_iter(path)
            self.model.remove(it)
            
            # add new datamaps
            nrows = self.model.iter_n_children(None)
            for j, i in enumerate(xrange(path[0], nrows)):
                self.datamap.add_path((i,), nodes[j])
            
            self.set_model(self.model)
            
        
        self.drag_nodes = []
    
    
    #=============================================
    # gui callbacks    
    
    def on_rows_reordered(self, treemodel, path, it, new_order):
        self.datamap.clear_path()
        
        nrows = self.model.iter_n_children(None)
        for i in xrange(nrows):
            self.datamap.add_path((i,), self.model[(i,)][6])
        
    
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete"):
            self.on_delete_page()
            self.stop_emission("key-release-event")
    

    def on_edit_title(self, cellrenderertext, path, new_text):
        try:
            page = self.datamap.get_data(path)
            if page.get_title() != new_text:
                page.rename(new_text)
                self.model[path][1] = new_text
        except Exception, e:
            print e
            print "takenote: could not rename page '%s'" % page.get_title()
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0 and self.on_select_node:
            node = self.datamap.get_data(paths[0])
            self.on_select_node(node)
        else:
            self.on_select_node(None)
        return True
    
    
    def on_delete_page(self):
        model, it = self.get_selection().get_selected()
        path = self.model.get_path(it)
        page = self.datamap.get_data(model.get_path(it))
        self.datamap.remove_path(path)
        page.delete()
        self.update()
    
    
    #====================================================
    # actions
    
    def view_nodes(self, nodes):
        self.set_model(None)
    
        self.sel_nodes = nodes
        self.model.clear()
        self.datamap.clear_path()
        
        npages = 0
        for node in nodes:
            for page in node.get_pages():
                npages += 1
                it = self.model.append()
                self._set_page(it, page)
                path = self.model.get_path(it)
                self.datamap.add_path(path, page)
        self.on_select_node(None)        
        
        if npages != 1:
            self.set_status("%d pages" % npages, "stats")
        else:
            self.set_status("1 page", "stats")
        
        self.set_model(self.model)
    
    
    def update(self):
        self.view_nodes(self.sel_nodes)    
    
    def update_node(self, node):
        path = self.datamap.get_path(node)
        
        if path is not None:
            it = self.model.get_iter(path)
            self._set_page(it, node)
    
    
    def _set_page(self, it, page):
        self.model.set(it, 0, self.icon)                
        self.model.set(it, 1, page.get_title())
        self.model.set(it, 2, page.get_created_time_text())
        self.model.set(it, 3, page.get_created_time())
        self.model.set(it, 4, page.get_modified_time_text())
        self.model.set(it, 5, page.get_modified_time())
        self.model.set(it, 6, page)
    
    def edit_node(self, page):
        path = self.datamap.get_path(page)
        self.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        path, col = self.get_cursor()
        self.scroll_to_cell(path)
    
    
    def select_pages(self, pages):
        page = pages[0]
        path = self.datamap.get_path(page)
        if path != None:
            self.set_cursor_on_cell(path)

    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
            self.datamap.clear_path()
    
    
    def set_status(self, text, bar="status"):
        if self.on_status:
            self.on_status(text, bar=bar)






class TakeNoteEditor (object):

    def __init__(self):
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        self.textview = RichTextView()
        sw.add(self.textview)
        sw.show()
        self.textview.show()
        self.view = sw
        self.on_page_modified = None
        
        self.page = None
        
    def view_page(self, page):
        self.save()
        self.page = page
        
        if page is None:
            self.textview.disable()
        else:
            self.textview.enable()
            self.textview.load(page.get_data_file())
    
    def save(self):
        if self.page is not None and \
           self.page.is_valid() and \
           self.textview.is_modified():
            self.textview.save(self.page.get_data_file())
            self.page.set_modified_time()
            self.page.save()
            if self.on_page_modified:
                self.on_page_modified(self.page)
    
    def save_needed(self):
        return self.textview.is_modified()


class TakeNoteWindow (gtk.Window):
    def __init__(self, basedir=""):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.basedir = basedir
        
        self.set_title("TakeNote")
        self.set_default_size(*takenote.DEFAULT_WINDOW_SIZE)
        self.connect("delete-event", lambda w,e: self.on_close())
        
        self.notebook = None
        self.sel_nodes = []
        self.current_page = None

        # treeview
        self.treeview = TakeNoteTreeView()
        self.treeview.on_select_node = self.on_select_treenode

        
        # selector
        self.selector = TakeNoteSelector()
        self.selector.on_select_node = self.on_select_page
        self.selector.on_status = self.set_status
        self.selector.notebook_tree = self.treeview
        
        
        # editor
        self.editor = TakeNoteEditor()
        self.editor.textview.font_callback = self.on_font_change
        self.editor.on_page_modified = self.on_page_modified
        self.editor.view_page(None)
        
        #====================================
        # Layout
        
        # vertical box
        main_vbox = gtk.VBox(False, 0)
        self.add(main_vbox)
        
        # menu bar
        main_vbox.set_border_width(0)
        menubar = self.make_menubar()
        main_vbox.pack_start(menubar, False, True, 0)
        
        # toolbar
        main_vbox.pack_start(self.make_toolbar(), False, True, 0)          
        
        main_vbox2 = gtk.VBox(False, 0)
        main_vbox2.set_border_width(1)
        main_vbox.pack_start(main_vbox2, True, True, 0)
        
        #==========================================
        # create a horizontal paned widget
        self.hpaned = gtk.HPaned()
        main_vbox2.pack_start(self.hpaned, True, True, 0)
        self.hpaned.set_position(takenote.DEFAULT_HSASH_POS)

        # create a vertical paned widget
        self.vpaned = gtk.VPaned()
        self.hpaned.add2(self.vpaned)
        self.vpaned.set_position(takenote.DEFAULT_VSASH_POS)
        
        
        # status bar
        status_hbox = gtk.HBox(False, 0)
        main_vbox.pack_start(status_hbox, False, True, 0)
        
        self.status_bar = gtk.Statusbar()      
        status_hbox.pack_start(self.status_bar, False, True, 0)
        self.status_bar.set_property("has-resize-grip", False)
        self.status_bar.set_size_request(300, -1)
        
        self.stats_bar = gtk.Statusbar()
        status_hbox.pack_start(self.stats_bar, True, True, 0)
        

        # layout major widgets
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.treeview)
        self.hpaned.add1(sw)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.selector)
        self.vpaned.add1(sw)
              
        self.vpaned.add2(self.editor.view)
        
        
        self.show_all()        
        self.treeview.grab_focus()
    

    def set_status(self, text, bar="status"):
        if bar == "status":
            self.status_bar.pop(0)
            self.status_bar.push(0, text)
        elif bar == "stats":
            self.stats_bar.pop(0)
            self.stats_bar.push(0, text)
        else:
            raise Exception("unknown bar '%s'" % bar)


    def error(self, text):
        """Display an error message"""
        self.set_status(text)
        
    
    def get_preferences(self):
        if self.notebook is not None:
            self.resize(*self.notebook.pref.window_size)
            if self.notebook.pref.window_pos != [-1, -1]:
                self.move(*self.notebook.pref.window_pos)
            self.vpaned.set_position(self.notebook.pref.vsash_pos)
            self.hpaned.set_position(self.notebook.pref.hsash_pos)
    

    def set_preferences(self):
        if self.notebook is not None:
            self.notebook.pref.window_size = self.get_size()
            self.notebook.pref.window_pos = self.get_position()
            self.notebook.pref.vsash_pos = self.vpaned.get_position()
            self.notebook.pref.hsash_pos = self.hpaned.get_position()
                    

    def on_new_notebook(self):
        self.filew = gtk.FileChooserDialog("New Notebook", self, 
            action=gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "New", gtk.RESPONSE_OK))
        self.filew.connect("response", self.on_new_notebook_response)
    
        self.filew.show()
    
    
    def on_new_notebook_response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            filename = self.filew.get_filename()
            dialog.destroy()
            os.rmdir(filename)
            self.new_notebook(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
    
    
    def on_open_notebook(self):
        self.filew = gtk.FileChooserDialog("Open Notebook", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Open", gtk.RESPONSE_OK))
        self.filew.connect("response", self.on_open_notebook_response)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name("Notebook")
        self.filew.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files")
        self.filew.add_filter(file_filter)
        
        self.filew.show()
    
    def on_open_notebook_response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            filename = self.filew.get_filename()
            dialog.destroy()
            self.open_notebook(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        
    
    def new_notebook(self, filename):
        if self.notebook is not None:
            self.close_notebook()
        
        try:
            self.notebook = takenote.NoteBook(filename)
            self.notebook.create()
            self.set_status("Created '%s'" % self.notebook.get_title())
        except Exception, e:
            self.notebook = None
            self.set_status("Error: Could not create new notebook")
            print e
        
        self.open_notebook(filename, new=True)
        
        
    
    def open_notebook(self, filename, new=False):
        if self.notebook is not None:
            self.close_notebook()
        
        self.notebook = takenote.NoteBook()
        self.notebook.load(filename)
        self.selector.set_notebook(self.notebook)
        self.treeview.set_notebook(self.notebook)
        self.get_preferences()
        
        self.treeview.grab_focus()
        
        if not new:
            self.set_status("Loaded '%s'" % self.notebook.get_title())
        
        
    def close_notebook(self):
        if self.notebook is not None:
            self.editor.save()
            self.set_preferences()
            self.notebook.save()
            self.notebook = None
            self.selector.set_notebook(self.notebook)
            self.treeview.set_notebook(self.notebook)
    
    
    def on_new_dir(self):
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        node = parent.new_dir("New Node")
        self.treeview.update_node(parent)
        self.treeview.expand_node(parent)
        self.treeview.edit_node(node)
    
    
    def on_new_page(self):
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        node = parent.new_page("New Page")
        self.treeview.update_node(parent)
        self.selector.update()
        self.selector.edit_node(node)
    
    
    def on_save(self):
        if self.notebook is not None:
            needed = self.notebook.save_needed() or \
                     self.editor.save_needed()
            
            self.notebook.save()
            self.editor.save()
            
            if needed:
                self.set_status("Notebook saved")
    
    
    def on_close(self):
        """close the window and quit"""
        self.close_notebook()
        gtk.main_quit()
        return False
    
    
    def on_select_treenode(self, node):
        if node is not None:
            self.sel_nodes = [node]
            self.selector.view_nodes([node])
        else:
            self.sel_nodes = []
            self.selector.view_nodes([])
    
    def on_select_page(self, page):
        self.current_page = page
        self.editor.view_page(page)
        
    def on_page_modified(self, page):
        self.selector.update_node(page)
        
    
    #=============================================================
    # Font UI Update
    
    def on_font_change(self, mods, justify):
    
        # block toolbar handlers
        self.bold_button.handler_block(self.bold_id)
        self.italic_button.handler_block(self.italic_id)
        self.underline_button.handler_block(self.underline_id) 
        self.left_button.handler_block(self.left_id)
        self.center_button.handler_block(self.center_id)
        self.right_button.handler_block(self.right_id) 
        
        # update font mods
        self.bold_button.set_active(mods["bold"])
        self.italic_button.set_active(mods["italic"])        
        self.underline_button.set_active(mods["underline"])
        
        # update text justification
        self.left_button.set_active(justify == "left")
        self.center_button.set_active(justify == "center")
        self.right_button.set_active(justify == "right")                
        
        # unblock toolbar handlers
        self.bold_button.handler_unblock(self.bold_id)
        self.italic_button.handler_block(self.italic_id)
        self.underline_button.handler_unblock(self.underline_id)
        self.left_button.handler_unblock(self.left_id)
        self.center_button.handler_unblock(self.center_id)
        self.right_button.handler_unblock(self.right_id) 
        
        
    
    def on_bold(self):
        self.editor.textview.on_bold()
        mods, justify = self.editor.textview.get_font()
        
        self.bold_button.handler_block(self.bold_id)
        self.bold_button.set_active(mods["bold"])
        self.bold_button.handler_unblock(self.bold_id)
    
    
    def on_italic(self):
        self.editor.textview.on_italic()
        mods, justify = self.editor.textview.get_font()
        
        self.italic_button.handler_block(self.italic_id)
        self.italic_button.set_active(mods["italic"])
        self.italic_button.handler_block(self.italic_id)
    
    
    def on_underline(self):
        self.editor.textview.on_underline()
        mods, justify = self.editor.textview.get_font()
        
        self.underline_button.handler_block(self.underline_id)        
        self.underline_button.set_active(mods["underline"])
        self.underline_button.handler_unblock(self.underline_id)
    

    def on_left_justify(self):
        self.editor.textview.on_left_justify()
        mods, justify = self.editor.textview.get_font()
        self.on_font_change(mods, justify)

    def on_center_justify(self):
        self.editor.textview.on_center_justify()
        mods, justify = self.editor.textview.get_font()
        self.on_font_change(mods, justify)

    def on_right_justify(self):
        self.editor.textview.on_right_justify()
        mods, justify = self.editor.textview.get_font()
        self.on_font_change(mods, justify)


    def on_screenshot(self):
        if self.current_page is None:
            return
    
        f, imgfile = tempfile.mkstemp(".xpm", "takenote")
        os.close(f)
    
        os.system("import %s" % imgfile)
        if os.path.exists(imgfile):
            try:
                self.insert_image(imgfile, "screenshot.png")
            except Exception, e:
                print e
                self.error("error reading screenshot '%s'" % imgfile)
            
            os.remove(imgfile)
        
    def on_insert_image(self):
        if self.current_page is None:
            return
                  
        dialog = gtk.FileChooserDialog("Insert Image From File", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Insert", gtk.RESPONSE_OK))
        dialog.connect("response", self.on_insert_image_response)
        
        """
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name("Notebook")
        self.filew.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files")
        self.filew.add_filter(file_filter)
        """
        
        dialog.show()
    
    def on_insert_image_response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()
            
            imgname, ext = os.path.splitext(os.path.basename(filename))
            if ext == ".jpg":
                imgname = imgname + ".jpg"
            else:
                imgname = imgname + ".png"
            
            try:
                self.insert_image(filename, imgname)
            except Exception, e:
                self.error("Could not insert image '%s'" % filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
    
    
    def insert_image(self, filename, savename="image.png"):
        pixbuf = gdk.pixbuf_new_from_file(filename)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.editor.textview.insert_image(img, savename)
        
                

    def on_choose_font(self):
        self.font_sel.clicked()
    
    
    def on_font_set(self):
        self.editor.textview.on_font_set(self.font_sel)
        self.editor.textview.grab_focus()
    
    
    def on_goto_treeview(self):
        self.treeview.grab_focus()
        
    def on_goto_listview(self):
        self.selector.grab_focus()
        
    def on_goto_editor(self):
        self.editor.textview.grab_focus()
    
    def on_about(self):
        """Display about dialog"""
        
        about = gtk.AboutDialog()
        about.set_name(PROGRAM_NAME)
        about.set_version("v%s" % (PROGRAM_VERSION) )
        about.set_copyright("Copyright Matt Rasmussen 2008")
        about.set_transient_for(self)
        about.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        about.connect("response", lambda d,r: about.destroy())
        about.show()
    
    def on_cut(self):
        self.editor.textview.emit("cut-clipboard")
    
    def on_copy(self):
        self.editor.textview.emit("copy-clipboard")
    
    def on_paste(self):
        self.editor.textview.emit("paste-clipboard")

    
    #================================================
    # Menubar
    
    def make_menubar(self):
        # menu bar
        self.menu_items = (
            ("/_File",               
                None, None, 0, "<Branch>"),
            ("/File/_New Notebook",
                None, lambda w,e: self.on_new_notebook(), 0, None),
            ("/File/New _Page",      
                "<control>N", lambda w,e: self.on_new_page(), 0, None),
            ("/File/New _Directory", 
                "<control><shift>N", lambda w,e: self.on_new_dir(), 0, None),
            ("/File/_Open Notebook",          
                "<control>O", lambda w,e: self.on_open_notebook(), 0, None),
            ("/File/_Save",     
                "<control>S", lambda w,e: self.on_save(), 0, None),
            ("/File/_Close Notebook", 
                "<control>W", lambda w, e: self.close_notebook(), 0, None),
            ("/File/sep1", 
                None, None, 0, "<Separator>" ),
            ("/File/Quit", 
                "<control>Q", lambda w,e: self.on_close(), 0, None),

            ("/_Edit", 
                None, None, 0, "<Branch>"),
            ("/Edit/_Undo", 
                "<control>Z", lambda w,e: self.editor.textview.undo(), 0, None),
            ("/Edit/_Redo", 
                "<control><shift>Z", lambda w,e: self.editor.textview.redo(), 0, None),
            ("/Edit/sep1", 
                None, None, 0, "<Separator>"),
            ("/Edit/Cu_t", 
                "<control>X", lambda w,e: self.on_cut(), 0, None), 
            ("/Edit/_Copy",     
                "<control>C", lambda w,e: self.on_copy(), 0, None), 
            ("/Edit/_Paste",     
                "<control>V", lambda w,e: self.on_paste(), 0, None), 
            ("/Edit/sep2", 
                None, None, 0, "<Separator>"),
            ("/Edit/Insert _Image",
                None, lambda w,e: self.on_insert_image(), 0, None),
            ("/Edit/Insert _Screenshot",
                "<control>Insert", lambda w,e: self.on_screenshot(), 0, None),
                
            
            ("/_Format", 
                None, None, 0, "<Branch>"),
            ("/Format/_Left Align", 
                "<control>L", lambda w,e: self.on_left_justify(), 0, None ),
            ("/Format/C_enter Align", 
                "<control>E", lambda w,e: self.on_center_justify(), 0, None ),
            ("/Format/_Right Align", 
                "<control>R", lambda w,e: self.on_right_justify(), 0, None ),
            ("/Format/sep1", 
                None, None, 0, "<Separator>" ),            
            ("/Format/_Bold", 
                "<control>B", lambda w,e: self.on_bold(), 0, None ),
            ("/Format/_Italic", 
                "<control>I", lambda w,e: self.on_italic(), 0, None ),
            ("/Format/_Underline", 
                "<control>U", lambda w,e: self.on_underline(), 0, None ),
            ("/Format/sep2", 
                None, None, 0, "<Separator>" ),
            ("/Format/Choose _Font", 
                "<control><shift>F", lambda w, e: self.on_choose_font(), 0, None),
            
            ("/_Go", 
                None, None, 0, "<Branch>"),
            ("/Go/Go To _Tree View",
                "<control>T", lambda w,e: self.on_goto_treeview(), 0, None),
            ("/Go/Go To _List View",
                "<control>Y", lambda w,e: self.on_goto_listview(), 0, None),
            ("/Go/Go To _Editor",
                "<control>D", lambda w,e: self.on_goto_editor(), 0, None),
                
            
            ("/_Help",       None, None, 0, "<LastBranch>" ),
            ("/_Help/About", None, lambda w,e: self.on_about(), 0, None ),
            )    
    
        accel_group = gtk.AccelGroup()

        # This function initializes the item factory.
        # Param 1: The type of menu - can be MenuBar, Menu,
        #          or OptionMenu.
        # Param 2: The path of the menu.
        # Param 3: A reference to an AccelGroup. The item factory sets up
        #          the accelerator table while generating menus.
        item_factory = gtk.ItemFactory(gtk.MenuBar, "<main>", accel_group)

        # This method generates the menu items. Pass to the item factory
        #  the list of menu items
        item_factory.create_items(self.menu_items)

        # Attach the new accelerator group to the window.
        self.add_accel_group(accel_group)

        # need to keep a reference to item_factory to prevent its destruction
        self.item_factory = item_factory
        # Finally, return the actual menu bar created by the item factory.
        return item_factory.get_widget("<main>")


    
    def make_toolbar(self):
        
        toolbar = gtk.Toolbar()
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_border_width(0)
        
        tips = gtk.Tooltips()
        
        # bold tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "bold.xpm"))
        self.bold_button = gtk.ToggleToolButton()
        self.bold_button.set_icon_widget(icon)
        tips.set_tip(self.bold_button, "Bold")
        self.bold_id = self.bold_button.connect("toggled", lambda w: self.editor.textview.on_bold())
        toolbar.insert(self.bold_button, -1)


        # italic tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "italic.xpm"))
        self.italic_button = gtk.ToggleToolButton()
        self.italic_button.set_icon_widget(icon)
        tips.set_tip(self.italic_button, "Italic")
        self.italic_id = self.italic_button.connect("toggled", lambda w: self.editor.textview.on_italic())
        toolbar.insert(self.italic_button, -1)

        # underline tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "underline.xpm"))
        self.underline_button = gtk.ToggleToolButton()
        self.underline_button.set_icon_widget(icon)
        tips.set_tip(self.underline_button, "Underline")
        self.underline_id = self.underline_button.connect("toggled", lambda w: self.editor.textview.on_underline())
        toolbar.insert(self.underline_button, -1)
                

        # font button
        self.font_sel = gtk.FontButton()
        item = gtk.ToolItem()
        item.add(self.font_sel)
        tips.set_tip(item, "Set Font")
        toolbar.insert(item, -1)
        self.font_sel.connect("font-set", lambda w: self.on_font_set())
        
        # left tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "alignleft.xpm"))
        self.left_button = gtk.ToggleToolButton()
        self.left_button.set_icon_widget(icon)
        tips.set_tip(self.left_button, "Left Justify")
        self.left_id = self.left_button.connect("toggled", lambda w: self.editor.textview.on_left_justify())
        toolbar.insert(self.left_button, -1)
        
        # center tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "aligncenter.xpm"))
        self.center_button = gtk.ToggleToolButton()
        self.center_button.set_icon_widget(icon)
        tips.set_tip(self.center_button, "Center Justify")
        self.center_id = self.center_button.connect("toggled", lambda w: self.editor.textview.on_center_justify())
        toolbar.insert(self.center_button, -1)
        
        # right tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "alignright.xpm"))
        self.right_button = gtk.ToggleToolButton()
        self.right_button.set_icon_widget(icon)
        tips.set_tip(self.right_button, "Right Justify")
        self.right_id = self.right_button.connect("toggled", lambda w: self.editor.textview.on_right_justify())
        toolbar.insert(self.right_button, -1)        
        
        return toolbar


class TakeNote (object):
    
    def __init__(self, basedir=""):
        self.basedir = basedir

        global BASEDIR
        BASEDIR = basedir
        
        self.window = TakeNoteWindow(basedir)

        
    def open_notebook(self, filename):
        self.window.open_notebook(filename)

