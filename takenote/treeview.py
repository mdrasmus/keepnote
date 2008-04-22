




# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk


from takenote.treemodel import \
    DROP_TREE_MOVE, \
    DROP_PAGE_MOVE, \
    DROP_NO, \
    compute_new_path, \
    copy_row, \
    TakeNoteTreeStore

from takenote import get_resource, NoteBookDir, NoteBookPage, NoteBookError


class TakeNoteTreeView (gtk.TreeView):
    
    def __init__(self):
        gtk.TreeView.__init__(self)
    
        self.on_select_node = None
        self.on_node_changed = None
        self.editing = False
        
        # create a TreeStore with one string column to use as the model
        self.model = TakeNoteTreeStore(3, gdk.Pixbuf, gdk.Pixbuf, str, object)
        self.temp_child = None
        
        # init treeview
        self.set_model(self.model)
        
        self.connect("key-release-event", self.on_key_released)
        
        # row expand/collapse
        self.expanded_id = self.connect("row-expanded", self.on_row_expanded)
        self.collapsed_id = self.connect("row-collapsed", self.on_row_collapsed)
        self.connect("test-expand-row", self.on_test_expand_row)
        
        # drag and drop         
        self.connect("drag-begin", self.on_drag_begin)
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("drag-data-received", self.on_drag_data_received)
        
        self.set_reorderable(True)
        self.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK, [DROP_TREE_MOVE], gtk.gdk.ACTION_MOVE)
        self.enable_model_drag_dest(
            [DROP_TREE_MOVE, DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
        
        # selection config
        #self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.get_selection().connect("changed", self.on_select_changed)
        
        self.set_headers_visible(False)
        #self.set_property("enable-tree-lines", True)
        # make treeview searchable
        self.set_search_column(1)
        #self.set_fixed_height_mode(True)       
        

        # create the treeview column
        self.column = gtk.TreeViewColumn()
        self.column.set_clickable(False)
        self.append_column(self.column)

        # create a cell renderers
        self.cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()
        self.cell_text.connect("editing-started", self.on_editing_started)
        self.cell_text.connect("editing-canceled", self.on_editing_canceled)
        self.cell_text.connect("edited", self.on_edit_title)
        self.cell_text.set_property("editable", True)        

        # add the cells to column
        self.column.pack_start(self.cell_icon, False)
        self.column.pack_start(self.cell_text, True)

        # map cells to columns in treestore
        self.column.add_attribute(self.cell_icon, 'pixbuf', 0)
        self.column.add_attribute(self.cell_icon, 'pixbuf-expander-open', 1)
        self.column.add_attribute(self.cell_text, 'text', 2)

        self.icon_folder_closed = gdk.pixbuf_new_from_file(get_resource("images", "folder.png"))
        self.icon_folder_opened = gdk.pixbuf_new_from_file(get_resource("images", "folder-open.png"))
        self.icon_page = gdk.pixbuf_new_from_file(get_resource("images", "note.png"))
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
        
        # get target info
        target_path, drop_position  = dest_row
        target_node = self.model.get_data(target_path)
        target = self.model.get_iter(target_path)
        new_path = compute_new_path(self.model, target, drop_position)
        
        # process node drops
        if "drop_node" in drag_context.targets or \
           "drop_selector" in drag_context.targets:
        
            # get source
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            source_path = self.model.get_path_from_data(source_node)
            
            # determine if drag is allowed
            if self.drop_allowed(source_node, target_node, drop_position):
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
            
            # get target
            target_path, drop_position  = dest_row
            target = self.model.get_iter(target_path)
            target_node = self.model.get_data(target_path)
            new_path = compute_new_path(self.model, target, drop_position)
            
            # get source
            source_widget = drag_context.get_source_widget()
            source_node = source_widget.get_drag_node()
            source_path = self.model.get_path_from_data(source_node)
            
            
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
                
                # if source_widget is not ourself, we need to do our own remove
                # otherwise, drag-delete signal would be called on us to perform
                # the delete
                if source_widget != self:
                    self.model.remove(source)
                
            else:                
                # process node move that is not in treeview
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
        
        # recursively expand nodes that should be expanded
        def walk(it):
            child = self.model.iter_children(it)
            while child:
                node = self.model.get_data_from_iter(child)
                if node.is_expanded():
                    path = self.model.get_path(child)
                    self.expand_row(path, False)
                    walk(child)
                child = self.model.iter_next(child)
        walk(it)
    
    def on_test_expand_row(self, treeview, it, path):
        
        child = self.model.iter_children(it)
        if child and self.model.get_data(path + (0,)) is self.temp_child:
            self.model.remove(child)
            self.add_children(it)
        

    def on_row_collapsed(self, treeview, it, path):
        self.model.get_data(path).set_expand(False)

        
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete") and \
           not self.editing:
            self.on_delete_node()
            self.stop_emission("key-release-event")

    def on_editing_started(self, cellrenderer, editable, path):
        self.editing = True
    
    def on_editing_canceled(self, cellrenderer):
        self.editing = False

    def on_edit_title(self, cellrenderertext, path, new_text):
        self.editing = False
    
        node = self.model.get_data(path)
        
        # can raise NoteBookError
        if new_text != node.get_title():
            node.rename(new_text)            
            self.model[path][2] = new_text
            
            # notify listener
            if self.on_node_changed:
                self.on_node_changed(node, False)
        
    
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0 and self.on_select_node:
            nodes = [self.model.get_data(path) for path in paths]
            self.on_select_node(nodes)
        return True
    
    
    def on_delete_node(self):
        # TODO: add folder name to message box
    
        dialog = gtk.MessageDialog(self.get_toplevel(), 
            flags= gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_QUESTION, 
            buttons=gtk.BUTTONS_YES_NO, 
            message_format="Do you want to delete this folder and all of its pages?")
        dialog.connect("response", self.on_delete_node_response)
        dialog.show()
    
    
    def on_delete_node_response(self, dialog, response):
        if response == gtk.RESPONSE_YES:
            dialog.destroy()
            self.delete_node()
            
        elif response == gtk.RESPONSE_NO:
            dialog.destroy()
            
    
    def delete_node(self):
        model, it = self.get_selection().get_selected()
        
        if it is None:
            return
        
        node = self.model.get_data(model.get_path(it))
        parent = node.get_parent()
        
        if parent is not None:
            node.delete()
            self.update_node(parent)
        else:
            # warn
            print "Cannot delete notebook's toplevel directory"
        
        if self.on_select_node:
            self.on_select_node([])
           
    
    #==============================================
    # actions
    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
        
        else:
            root = self.notebook.get_root_node()
            self.add_node(None, root)
            if root.is_expanded():
                self.expand_to_path(self.model.get_path_from_data(root))

            
    
    
    def edit_node(self, node):
        path = self.model.get_path_from_data(node)
        self.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        self.scroll_to_cell(path)

    
    def expand_node(self, node):
        path = self.model.get_path_from_data(node)
        self.expand_to_path(path)

    #================================================
    # model manipulation        
    
    def get_icons(self, node):
        if isinstance(node, NoteBookDir):
            return self.icon_folder_closed, self.icon_folder_opened
        else:
            return self.icon_page, self.icon_page
            
    
    def add_node(self, parent, node):
        closed, opened = self.get_icons(node)
        it = self.model.append(parent, [closed, 
                                        opened,
                                        node.get_title(), node])
        path = self.model.get_path(it)
        children = list(node.get_children())

        if len(children) > 0:
            if self.row_expanded(path):
                for child in children:
                    self.add_node(it, child)
            else:
                self.model.append(it, [closed, 
                                       opened,
                                       "TEMP", self.temp_child])
        
    def add_children(self, parent):
        node = self.model.get_data(self.model.get_path(parent))
        for child in node.get_children():
            self.add_node(parent, child)
    
    
    def update_node(self, node):
        path = self.model.get_path_from_data(node)
        if path is None:
            return
        
        expanded = self.row_expanded(path)
        it = self.model.get_iter(path)
        
        self.model.set(it, 2, node.get_title())
        
        for child in self.model[path].iterchildren():
            self.model.remove(child.iter)
        
        it = self.model.get_iter(path)
        for child in node.get_children():
            self.add_node(it, child)
        
        if expanded:
            self.expand_to_path(path)
        
