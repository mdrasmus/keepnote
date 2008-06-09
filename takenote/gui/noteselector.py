"""

    TakeNote
    NoteSelector View

"""


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk


from takenote.gui.treemodel import \
    DROP_TREE_MOVE, \
    DROP_PAGE_MOVE, \
    DROP_NO, \
    compute_new_path, \
    copy_row, \
    TakeNoteTreeStore

from takenote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf, \
     get_node_icon
from takenote import notebook
from takenote.notebook import NoteBookError, NoteBookDir, NoteBookPage


COL_ICON          = 0
COL_ICON_EXPAND   = 1
COL_TITLE         = 2
COL_CREATED_TEXT  = 3
COL_CREATED_INT   = 4
COL_MODIFIED_TEXT = 5
COL_MODIFIED_INT  = 6
COL_MANUAL        = 7
COL_NODE          = 8


'''    
class SelectorColumn (object):
    def __init__(self, name, kind, col):
        self.name = name
        self.kind = kind
        self.col = col

TITLE_COLUMN = SelectorColumn("Title", str, 0)
CREATED_COLUMN = SelectorColumn("Created", str, 1)
MODIFIED_COLUMN = SelectorColumn("Modified", str, 2)
'''

class TakeNoteSelector (gtk.TreeView):
    
    def __init__(self):
        gtk.TreeView.__init__(self)
        self.notebook = None
        self.drag_nodes = []
        self.editing = False
        self.on_status = None
        self.sel_nodes = None
        
        self.display_columns = []
        
        # init model
        #self.model = TakeNoteListStore(7, gdk.Pixbuf, str, str, int, str, int, int, object)
        self.model = TakeNoteTreeStore(COL_NODE,
                                       gdk.Pixbuf, gdk.Pixbuf, str, str,
                                       int, str, int, int, object)
        
        # init view
        self.set_model(self.model)
        self.connect("key-release-event", self.on_key_released)
        self.connect("button-press-event", self.on_button_press)
        self.get_selection().connect("changed", self.on_select_changed)
        self.connect("drag-motion", self.on_drag_motion)
        self.connect("drag-data-delete", self.on_drag_data_delete)
        self.set_rules_hint(True)
        self.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK, [DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)
        self.enable_model_drag_dest(
            [DROP_PAGE_MOVE], gtk.gdk.ACTION_MOVE)                
        self.set_fixed_height_mode(True)
        
        
        # directory order column
        column = gtk.TreeViewColumn()
        img = get_resource_image("folder.png")
        img.show()
        column.set_widget(img)
        column.set_clickable(True)
        column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        w, h = img.size_request()
        column.set_min_width(w+10)
        column.set_fixed_width(w+10)
        column.connect("clicked", self.on_directory_column_clicked)
        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)
        column.pack_start(cell_text, True)
        self.append_column(column)

        
        # title column
        cell_icon = gtk.CellRendererPixbuf()
        self.title_text = gtk.CellRendererText()
        self.title_column = gtk.TreeViewColumn()
        self.title_column.set_title("Title")
        self.title_column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        self.title_column.set_min_width(10)
        self.title_column.set_fixed_width(250)
        self.title_column.set_property("resizable", True)
        self.title_column.pack_start(cell_icon, False)
        self.title_column.pack_start(self.title_text, True)
        self.title_text.set_fixed_height_from_font(1)
        self.title_text.connect("edited", self.on_edit_title)
        self.title_text.connect("editing-started", self.on_editing_started)
        self.title_text.connect("editing-canceled", self.on_editing_canceled)        
        self.title_text.set_property("editable", True)
        self.title_column.set_sort_column_id(COL_TITLE)
        # map cells to columns in model
        self.title_column.add_attribute(cell_icon, 'pixbuf', COL_ICON)
        self.title_column.add_attribute(cell_icon, 'pixbuf-expander-open', COL_ICON_EXPAND)
        self.title_column.add_attribute(self.title_text, 'text', COL_TITLE)
        self.append_column(self.title_column)
        self.set_expander_column(self.title_column)
        
        
        # created column
        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)        
        column = gtk.TreeViewColumn()
        column.set_title("Created")
        column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_property("resizable", True)
        column.set_min_width(10)
        column.set_fixed_width(150)
        column.set_sort_column_id(COL_CREATED_INT)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', COL_CREATED_TEXT)
        self.append_column(column)
    
        # modified column
        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)
        column = gtk.TreeViewColumn()
        column.set_title("Modified")
        column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_property("resizable", True)
        column.set_min_width(10)
        column.set_fixed_width(150)
        column.set_sort_column_id(COL_MODIFIED_INT)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', COL_MODIFIED_TEXT)
        self.append_column(column)
        
        
        # set default sorting
        # remember sort per node
        self.model.set_sort_column_id(COL_MANUAL, gtk.SORT_ASCENDING)
        #self.model.set_sort_column_id(3, gtk.SORT_DESCENDING)


        
        self.menu = gtk.Menu()
        self.menu.attach_to_widget(self, lambda w,m:None)
        

    #=============================================
    # drag and drop callbacks
    
    def get_drag_node(self):
        model, source = self.get_selection().get_selected()
        source_path = model.get_path(source)
        node = self.model.get_data(source_path)
        self.drag_nodes = [node]
        return node
    
    
    def on_drag_motion(self, treeview, drag_context, x, y, eventtime):
        """Callback for drag motion.
           Indicate which drops are allowed"""
        
        
        # determine destination row
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
            node = self.drag_nodes[0]
            path = self.model.get_path_from_data(node)
                        
            # remove row
            it = self.model.get_iter(path)
            self.model.remove(it)
            
        
        self.drag_nodes = []
    
    
    #=============================================
    # gui callbacks    
            
    def on_directory_column_clicked(self, column):
        """sort pages by directory order"""
        #self.model.set_default_sort_func
        self.model.set_sort_column_id(6, gtk.SORT_ASCENDING)
        #reset_default_sort_func()
        
    
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete") and \
           not self.editing:
            self.on_delete_page()
            self.stop_emission("key-release-event")

    def on_button_press(self, widget, event):
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


    def on_editing_started(self, cellrenderer, editable, path):
        self.editing = True
    
    def on_editing_canceled(self, cellrenderer):
        self.editing = False    

    def on_edit_title(self, cellrenderertext, path, new_text):
        self.editing = False
        
        page = self.model.get_data(path)
        if page.get_title() != new_text:
            try:
                page.rename(new_text)
                self.model[path][COL_TITLE] = new_text
            
                #self.emit("node-modified", True, page, False)
            except NoteBookError, e:
                self.emit("error", e.msg, e)
        
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0:
            nodes = [self.model.get_data(x) for x in paths]
            self.emit("select-nodes", nodes)
        else:
            self.emit("select-nodes", [])
        return True
    
    
    def on_delete_page(self):
        dialog = gtk.MessageDialog(self.get_toplevel(), 
            flags= gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_QUESTION, 
            buttons=gtk.BUTTONS_YES_NO, 
            message_format="Do you want to delete this page?")
        dialog.connect("response", self.on_delete_page_response)
        dialog.show()
    
    
    def on_delete_page_response(self, dialog, response):
        if response == gtk.RESPONSE_YES:
            dialog.destroy()
            self.delete_page()
            
        elif response == gtk.RESPONSE_NO:
            dialog.destroy()    
    
    def delete_page(self):
        model, it = self.get_selection().get_selected()
        
        if it is None:
            return
        
        path = self.model.get_path(it)
        page = self.model.get_data(model.get_path(it))
        parent = page.get_parent()
        
        try:
            page.trash()
            self.model.remove(it)
            
        except NoteBookError, e:
            self.emit("error", e.msg, e)
        
    
    
    #====================================================
    # actions
    
    def on_node_changed(self, node, recurse):
        self.update_node(node)        
        
    
    def view_nodes(self, nodes):
        # deactivate expensive updates for model
        self.model.block_row_signals()

        # TODO: learn how to deactivate expensive sorting
        #self.model.set_default_sort_func(None)
        #self.model.set_sort_column_id(-1, gtk.SORT_ASCENDING)
        

        # save sorting if a single node was selected
        if self.sel_nodes is not None and len(self.sel_nodes) == 1:
            self.save_sorting(self.sel_nodes[0])
            
        
        #from rasmus import util
        #util.tic("view")

        self.set_model(None)
        
        self.sel_nodes = nodes
        self.model.clear()        

        # populate model
        npages = 0
        for node in nodes:
            if isinstance(node, NoteBookDir):
                for child in node.get_children():
                    npages += 1
                    self.add_node(None, child, npages, True)
            elif isinstance(node, NoteBookPage):
                page = node
                npages += 1
                self.add_node(None, page, npages)
        
        self.emit("select-nodes", [])
        
        # reactivate model
        self.model.unblock_row_signals()
        self.model.refresh_path_data(None)
        self.set_model(self.model)
        
        # load sorting if single node is selected
        if len(nodes) == 1:
            self.load_sorting(nodes[0])
            
        #util.toc()

        # update status
        if npages != 1:
            self.set_status("%d pages" % npages, "stats")
        else:
            self.set_status("1 page", "stats")
        

    def add_node(self, parent, node, order, recursive=False):
        it = self.model.append(parent,
                               (get_node_icon(node, False),
                                get_node_icon(node, True),
                                node.get_title(),
                                node.get_created_time_text(),
                                node.get_created_time(),
                                node.get_modified_time_text(),
                                node.get_modified_time(),
                                order,
                                node))

        if recursive and len(node.get_children()) > 0:
            for order2, child in enumerate(node.get_children()):
                self.add_node(it, child, order2, True)
        
        return it
    
    
    def update(self):
        self.view_nodes(self.sel_nodes)    
    
    def update_node(self, node):
        path = self.model.get_path_from_data(node)
        
        if path is not None:
            it = self.model.get_iter(path)
            self.model.set(it, 
                           COL_ICON, get_node_icon(node, False),
                           COL_ICON_EXPAND, get_node_icon(node, True),
                           COL_TITLE, node.get_title(),
                           COL_CREATED_TEXT, node.get_created_time_text(),
                           COL_CREATED_INT, node.get_created_time(),
                           COL_MODIFIED_TEXT, node.get_modified_time_text(),
                           COL_MODIFIED_INT, node.get_modified_time())
        
    
    def edit_node(self, page):
        path = self.model.get_path_from_data(page)
        assert path is not None
        self.set_cursor_on_cell(path, self.title_column, self.title_text, True)
        path, col = self.get_cursor()
        self.scroll_to_cell(path)
    
    
    def select_pages(self, pages):
        page = pages[0]
        path = self.model.get_path_from_data(page)
        if path is not None:
            self.set_cursor_on_cell(path)

    
    def set_notebook(self, notebook):
        if self.notebook:
            self.notebook.node_changed.remove(self.on_node_changed)
        
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
        else:
            self.notebook.node_changed.add(self.on_node_changed)


    
    def save_sorting(self, node):
        """Save sorting information into node"""
        
        info_sort, sort_dir = self.model.get_sort_column_id()

        if sort_dir == gtk.SORT_ASCENDING:
            sort_dir = 1
        else:
            sort_dir = 0

        if info_sort == COL_MANUAL or info_sort == -1:
            node.set_info_sort(notebook.INFO_SORT_MANUAL, sort_dir)

        elif info_sort == COL_TITLE:
            node.set_info_sort(notebook.INFO_SORT_TITLE, sort_dir)
            
        elif info_sort == COL_CREATED_INT:
            node.set_info_sort(notebook.INFO_SORT_CREATED_TIME, sort_dir)

        elif info_sort == COL_MODIFIED_INT:
            node.set_info_sort(notebook.INFO_SORT_MODIFIED_TIME, sort_dir)


    def load_sorting(self, node):
        """Load sorting information from node"""

        info_sort, sort_dir = node.get_info_sort()
            
        if sort_dir:
            sort_dir = gtk.SORT_ASCENDING
        else:
            sort_dir = gtk.SORT_DESCENDING            
            
        if info_sort == notebook.INFO_SORT_MANUAL or \
           info_sort == notebook.INFO_SORT_NONE:
            self.model.set_sort_column_id(COL_MANUAL, sort_dir)
        elif info_sort == notebook.INFO_SORT_TITLE:
            self.model.set_sort_column_id(COL_TITLE, sort_dir)            
        elif info_sort == notebook.INFO_SORT_CREATED_TIME:
            self.model.set_sort_column_id(COL_CREATED_INT, sort_dir)
        elif info_sort == notebook.INFO_SORT_MODIFIED_TIME:
            self.model.set_sort_column_id(COL_MODIFIED_INT, sort_dir)

    
    def set_status(self, text, bar="status"):
        if self.on_status:
            self.on_status(text, bar=bar)

gobject.type_register(TakeNoteSelector)
gobject.signal_new("select-nodes", TakeNoteSelector, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("error", TakeNoteSelector, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object,))
