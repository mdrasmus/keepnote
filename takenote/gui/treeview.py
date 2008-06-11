"""

    TakeNote
    
    TreeView 

"""


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
from takenote.gui.treemodel import \
    DROP_TREE_MOVE, \
    DROP_PAGE_MOVE, \
    DROP_NO, \
    compute_new_path, \
    copy_row, \
    TakeNoteTreeStore
from takenote.gui import treemodel

from takenote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf, \
     get_node_icon
from takenote.notebook import NoteBookDir, NoteBookPage, NoteBookTrash, \
              NoteBookError



class TakeNoteBaseTreeView (gtk.TreeView):
    """Base class for treeviews of a NoteBook notes"""

    def __init__(self):
        gtk.TreeView.__init__(self)

        # init model        
        self.model = treemodel.TakeNoteTreeModel()
        self.model.connect("row-inserted", self.on_row_inserted)
        self.model.connect("row-has-child-toggled", self.on_row_inserted)
        self.set_model(self.model)

        # row expand/collapse
        self.expanded_id = self.connect("row-expanded", self.on_row_expanded)
        self.collapsed_id = self.connect("row-collapsed", self.on_row_collapsed)

        # drag and drop         
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("drag-drop", self.on_drag_drop)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.connect("drag-data-get", self.on_drag_data_get)
        self.connect("drag-data-received", self.on_drag_data_received)

        self.set_reorderable(True)
        self.enable_model_drag_source(
           gtk.gdk.BUTTON1_MASK, [DROP_TREE_MOVE], gtk.gdk.ACTION_MOVE)
        self.drag_source_set(
            gtk.gdk.BUTTON1_MASK,
            [DROP_TREE_MOVE],
             gtk.gdk.ACTION_MOVE)
        self.enable_model_drag_dest(
           [DROP_TREE_MOVE, DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
        self.drag_dest_set(gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_MOTION,
            [DROP_TREE_MOVE, DROP_PAGE_MOVE],
             gtk.gdk.ACTION_MOVE)



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
    
    def on_row_collapsed(self, treeview, it, path):
        self.model.get_data(path).set_expand(False)


    def on_row_inserted(self, treemodel, path, it):
        node = self.model.get_data_from_iter(it)
        if node.is_expanded():
            self.expand_row(path, False)


    
    #=============================================
    # drag and drop callbacks    
    
    
    def get_drag_node(self):
        model, source = self.get_selection().get_selected()
        source_path = model.get_path(source)
        return self.model.get_data(source_path)
    
        
    def on_drag_motion(self, treeview, drag_context, x, y, eventtime):
        """Callback for drag motion.
           Indicate which drops are allowed"""        

        self.stop_emission("drag-motion")
        
        # determine destination row   
        dest_row = treeview.get_dest_row_at_pos(x, y)
        
        if dest_row is None:
            self.set_drag_dest_row(source_path, gtk.TREE_VIEW_DROP_INTO_OR_AFTER)
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
                self.set_drag_dest_row(target_path, drop_position)
                return

        # reset dest
        self.set_drag_dest_row(source_path, gtk.TREE_VIEW_DROP_INTO_OR_AFTER)
        #self.unset_rows_drag_dest()



    def on_drag_drop(self, widget, drag_context, x, y, timestamp):

        self.stop_emission("drag-drop")
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
                new_parent = self.model.get_data(new_parent_path)
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



class TakeNoteTreeView (TakeNoteBaseTreeView):
    """
    TreeView widget for the TakeNote NoteBook
    """
    
    def __init__(self):
        TakeNoteBaseTreeView.__init__(self)

        self.notebook = None
        self.editing = False
                
        # treeview signals
        self.connect("key-release-event", self.on_key_released)
        self.connect("button-press-event", self.on_button_press)
        
        
        # selection config
        #self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.get_selection().connect("changed", self.on_select_changed)
        
        self.set_headers_visible(False)

        # make treeview searchable
        self.set_search_column(treemodel.COL_TITLE)
        #self.set_fixed_height_mode(True)       

        # tree style
        try:
            # available only on gtk > 2.8
            self.set_property("enable-tree-lines", True)
        except TypeError, e:
            pass


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
        self.column.add_attribute(self.cell_icon, 'pixbuf', treemodel.COL_ICON)
        self.column.add_attribute(self.cell_icon, 'pixbuf-expander-open', treemodel.COL_ICON_EXPAND)
        self.column.add_attribute(self.cell_text, 'text', treemodel.COL_TITLE)

        self.menu = gtk.Menu()
        self.menu.attach_to_widget(self, lambda w,m:None)



        
    
    #=============================================
    # gui callbacks
    
        
    def on_key_released(self, widget, event):
        """Process delete key"""
        
        if event.keyval == gdk.keyval_from_name("Delete") and \
           not self.editing:
            self.on_delete_node()
            self.stop_emission("key-release-event")

    def on_button_press(self, widget, event):
        """Process context popup menu"""
        
        if event.button == 3:            
            # popup menu
            path = self.get_path_at_pos(int(event.x), int(event.y))

            if path is not None:
                path = path[0]
                self.get_selection().select_path(path)
            
                self.menu.popup(None, None, None,
                                event.button, event.time)
                self.menu.show()
                return True

    #=====================================
    # node title editing

    def on_editing_started(self, cellrenderer, editable, path):
        self.editing = True
    
    def on_editing_canceled(self, cellrenderer):
        self.editing = False

    def on_edit_title(self, cellrenderertext, path, new_text):
        self.editing = False
        
        node = self.model.get_data(path)
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
        
    
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0:
            nodes = [self.model.get_data(path) for path in paths]
            self.emit("select-nodes", nodes)
        return True
    
    
    def on_delete_node(self):
        # TODO: add folder name to message box
        
        # get node to delete
        model, it = self.get_selection().get_selected()
        if it is None:
            return    
        node = self.model.get_data(model.get_path(it))
        
        if isinstance(node, NoteBookTrash):
            self.emit("error", "The Trash folder cannot be deleted.", None)
            return
        elif node.get_parent() == None:
            self.emit("error", "The top-level folder cannot be deleted.", None)
            return
        elif node.is_page():
            message = "Do you want to delete this page?"
        else:
            message = "Do you want to delete this folder and all of its pages?"
        
        dialog = gtk.MessageDialog(self.get_toplevel(), 
            flags= gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_QUESTION, 
            buttons=gtk.BUTTONS_YES_NO, 
            message_format=message)

        response = dialog.run()
        
        if response == gtk.RESPONSE_YES:
            dialog.destroy()
            self._delete_node(node)
            
        elif response == gtk.RESPONSE_NO:
            dialog.destroy()
            
    
    def _delete_node(self, node):
        parent = node.get_parent()
        
        if parent is not None:
            try:
                node.trash()
            except NoteBookError, e:
                self.emit("error", e.msg, e)
        else:
            # warn
            self.emit("error", "Cannot delete notebook's toplevel directory", None)
        
        self.emit("select-nodes", [])
        
    
    
    #==============================================
    # actions
    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.set_root_nodes([])
        
        else:
            root = self.notebook.get_root_node()
            self.set_model(None)
            self.model.set_root_nodes([root])
            self.set_model(self.model)
            
            if root.is_expanded():
                self.expand_to_path((0,))

            
    
    
    def edit_node(self, node):
        path = self.model.get_path_from_data(node)
        self.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        self.scroll_to_cell(path)

    
    def expand_node(self, node):
        path = self.model.get_path_from_data(node)
        self.expand_to_path(path)



# new signals
gobject.type_register(TakeNoteTreeView)
gobject.signal_new("select-nodes", TakeNoteTreeView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("error", TakeNoteTreeView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object,))
