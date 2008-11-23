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
    DROP_NO, \
    COL_ICON, \
    COL_ICON_EXPAND, \
    COL_TITLE, \
    COL_CREATED_TEXT, \
    COL_CREATED_INT, \
    COL_MODIFIED_TEXT, \
    COL_MODIFIED_INT, \
    COL_MANUAL, \
    COL_NODE, \
    compute_new_path
from takenote.gui import treemodel

from takenote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf, \
     get_node_icon
from takenote.notebook import NoteBookTrash, \
              NoteBookError




class TakeNoteTreeView (treemodel.TakeNoteBaseTreeView):
    """
    TreeView widget for the TakeNote NoteBook
    """
    
    def __init__(self):
        treemodel.TakeNoteBaseTreeView.__init__(self)

        self.notebook = None

        self.set_model(treemodel.TakeNoteTreeModel())
                
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

        self.set_sensitive(False)


        
    
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
    # selections
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        nodes = [self.model.get_value(self.model.get_iter(path), COL_NODE)
                 for path in paths]
        self.emit("select-nodes", nodes)
        return True


    def get_selected_nodes(self):
        model, it = self.get_selection().get_selected()
        if it is None:
            return []
        node = self.model.get_value(it, COL_NODE)
        return [node]
    
    
    def on_delete_node(self):
        # TODO: add folder name to message box
        
        # get node to delete
        nodes = self.get_selected_nodes()
        if len(nodes) == 0:
            return
        node = nodes[0]
        
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
            self.set_sensitive(False)
        
        else:
            self.set_sensitive(True)
            
            root = self.notebook.get_root_node()
            model = self.model
            self.set_model(None)
            model.set_root_nodes([root])
            self.set_model(model)
            
            if root.get_attr("expanded", True):
                self.expand_to_path((0,))

            
    
    
    def edit_node(self, node):
        path = treemodel.get_path_from_node(self.model, node)
        self.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        self.scroll_to_cell(path)

    
    def expand_node(self, node):
        path = treemodel.get_path_from_node(self.model, node)
        self.expand_to_path(path)



# new signals
gobject.type_register(TakeNoteTreeView)
gobject.signal_new("select-nodes", TakeNoteTreeView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("error", TakeNoteTreeView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object,))
