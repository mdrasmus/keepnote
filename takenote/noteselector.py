
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
    TakeNoteListStore

from takenote import get_resource, NoteBookError, NoteBookDir, NoteBookPage

    
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
        self.editing = False
        self.on_select_node = None
        self.on_node_changed = None
        self.on_status = None
        self.sel_nodes = None
        
        self.display_columns = []
        
        # init model
        self.model = TakeNoteListStore(7, gdk.Pixbuf, str, str, int, str, int, int, object)
        
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
        self.set_fixed_height_mode(True)
        
        
        # directory order column
        self.column = gtk.TreeViewColumn()
        self.column.set_title("#")
        self.column.set_clickable(True)
        self.column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        self.column.set_min_width(20)
        self.column.set_fixed_width(20)
        self.column.connect("clicked", self.on_directory_column_clicked)
        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)
        self.column.pack_start(cell_text, True)
        self.append_column(self.column)

        
        # title column
        cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()
        self.column = gtk.TreeViewColumn()
        self.column.set_title("Title")
        self.column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        self.column.set_min_width(10)
        self.column.set_fixed_width(250)
        self.column.set_property("resizable", True)
        self.column.pack_start(cell_icon, False)
        self.column.pack_start(self.cell_text, True)
        self.cell_text.set_fixed_height_from_font(1)
        self.cell_text.connect("edited", self.on_edit_title)
        self.cell_text.connect("editing-started", self.on_editing_started)
        self.cell_text.connect("editing-canceled", self.on_editing_canceled)        
        self.cell_text.set_property("editable", True)
        self.column.set_sort_column_id(1)
        # map cells to columns in model
        self.column.add_attribute(cell_icon, 'pixbuf', 0)
        self.column.add_attribute(self.cell_text, 'text', 1)
        self.append_column(self.column)
        
        
        # created column
        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)        
        column = gtk.TreeViewColumn()
        column.set_title("Created")
        column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_property("resizable", True)
        column.set_min_width(10)
        column.set_fixed_width(150)
        column.set_sort_column_id(3)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 2)
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
        column.set_sort_column_id(5)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 4)
        self.append_column(column)        
        
        
        # set default sorting
        # remember sort per node
        self.model.set_sort_column_id(6, gtk.SORT_ASCENDING)
        #self.model.set_sort_column_id(3, gtk.SORT_DESCENDING)
        
        
        self.icon = gdk.pixbuf_new_from_file(get_resource("images", "note.png"))
        

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

    def on_editing_started(self, cellrenderer, editable, path):
        self.editing = True
    
    def on_editing_canceled(self, cellrenderer):
        self.editing = False    

    def on_edit_title(self, cellrenderertext, path, new_text):
        self.editing = False
        
        page = self.model.get_data(path)
        if page.get_title() != new_text:
            # NOTE: can raise NoteBookError
            page.rename(new_text)
            self.model[path][1] = new_text
            
            if self.on_node_changed:
                self.on_node_changed(page, False)
        
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0 and self.on_select_node:
            node = self.model.get_data(paths[0])
            self.on_select_node(node)
        else:
            self.on_select_node(None)
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
        page.delete()
        
        self.model.remove(it)
    
    
    #====================================================
    # actions
    
    def view_nodes(self, nodes):
        # deactivate expensive updates for model
        self.model.block_row_signals()
        #self.model.set_default_sort_func(None)
        #self.model.set_sort_column_id(-1, gtk.SORT_ASCENDING)
        self.set_model(None)
        
        self.sel_nodes = nodes
        self.model.clear()
        
        #from rasmus import util
        #util.tic("view")
        
        npages = 0
        for node in nodes:
            if isinstance(node, NoteBookDir):
                for page in node.get_pages():
                    npages += 1
                    it = self.model.append(row=
                        (self.icon,
                         page.get_title(),
                         page.get_created_time_text(),
                         page.get_created_time(),
                         page.get_modified_time_text(),
                         page.get_modified_time(),
                         npages,
                         page))
            elif isinstance(node, NoteBookPage):
                page = node
                npages += 1
                it = self.model.append(row=
                    (self.icon,
                     page.get_title(),
                     page.get_created_time_text(),
                     page.get_created_time(),
                     page.get_modified_time_text(),
                     page.get_modified_time(),
                     npages,
                     page))
        self.on_select_node(None)
        
        # reactivate model
        self.model.unblock_row_signals()
        self.model.refresh_path_data(None)
        self.set_model(self.model)
        
        #util.toc()
        
        if npages != 1:
            self.set_status("%d pages" % npages, "stats")
        else:
            self.set_status("1 page", "stats")
        
        
    
    
    def update(self):
        self.view_nodes(self.sel_nodes)    
    
    def update_node(self, node):
        path = self.model.get_path_from_data(node)
        
        if path is not None:
            it = self.model.get_iter(path)
            self.model.set(it, 
                           0, self.icon,
                           1, node.get_title(),
                           2, node.get_created_time_text(),
                           3, node.get_created_time(),
                           4, node.get_modified_time_text(),
                           5, node.get_modified_time())
        
    
    def edit_node(self, page):
        path = self.model.get_path_from_data(page)
        self.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        path, col = self.get_cursor()
        self.scroll_to_cell(path)
    
    
    def select_pages(self, pages):
        page = pages[0]
        path = self.model.get_path_from_data(page)
        if path != None:
            self.set_cursor_on_cell(path)

    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
    
    
    def set_status(self, text, bar="status"):
        if self.on_status:
            self.on_status(text, bar=bar)


