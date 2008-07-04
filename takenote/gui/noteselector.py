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

from takenote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf, \
     get_node_icon
from takenote.gui import treemodel
from takenote import notebook
from takenote.notebook import NoteBookError, NoteBookDir, NoteBookPage



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

class TakeNoteSelector (treemodel.TakeNoteBaseTreeView):
    
    def __init__(self):
        treemodel.TakeNoteBaseTreeView.__init__(self)
        self.drag_nodes = []
        self.on_status = None
        self.sel_nodes = None
        
        self.display_columns = []
        
        # init model
        self.set_model(gtk.TreeModelSort(treemodel.TakeNoteTreeModel()))
        
        # init view
        self.connect("key-release-event", self.on_key_released)
        self.connect("button-press-event", self.on_button_press)
        self.get_selection().connect("changed", self.on_select_changed)
        self.set_rules_hint(True)
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
        self.title_column.connect("clicked", self.on_column_clicked)
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
        column.connect("clicked", self.on_column_clicked)
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
        column.connect("clicked", self.on_column_clicked)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', COL_MODIFIED_TEXT)
        self.append_column(column)
        
        
        # set default sorting
        # remember sort per node
        self.model.set_sort_column_id(COL_MANUAL, gtk.SORT_ASCENDING)
        self.set_reorder(treemodel.REORDER_ALL)
        
        self.menu = gtk.Menu()
        self.menu.attach_to_widget(self, lambda w,m:None)


    def set_date_formats(self, formats):
        self.model.get_model().set_date_formats(formats)
    
    
    #=============================================
    # gui callbacks    


    def is_node_expanded(self, node):
        return node.is_expanded2()

    def set_node_expanded(self, node, expand):
        node.set_expand2(expand)
        

    def on_column_clicked(self, column):
        self.set_reorder(treemodel.REORDER_FOLDER)
            
    def on_directory_column_clicked(self, column):
        """sort pages by directory order"""
        self.model.set_sort_column_id(COL_MANUAL, gtk.SORT_ASCENDING)
        self.set_reorder(treemodel.REORDER_ALL)
        
    
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

        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            model, paths = self.get_selection().get_selected_rows()

            if len(paths) > 0:
                nodes = [self.model.get_value(self.model.get_iter(x), COL_NODE)
                         for x in paths]

            # NOTE: can only view one node
            self.emit("view-node", nodes[0])


    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0:
            nodes = [self.model.get_value(self.model.get_iter(x), COL_NODE)
                     for x in paths]
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

        response = dialog.run()
        
        if response == gtk.RESPONSE_YES:
            dialog.destroy()
            self.delete_page()
            
        elif response == gtk.RESPONSE_NO:
            dialog.destroy()    


    def get_selected_nodes(self):
        model, it = self.get_selection().get_selected()        
        if it is None:
            return []
        return [self.model.get_value(it, COL_NODE)]
        
    
    def delete_page(self):
        model, it = self.get_selection().get_selected()
        
        if it is None:
            return
        
        path = self.model.get_path(it)
        page = self.model.get_value(it, COL_NODE)
        parent = page.get_parent()
        
        try:
            page.trash()
        except NoteBookError, e:
            self.emit("error", e.msg, e)
        
    
    
    #====================================================
    # actions
    
    def view_nodes(self, nodes, nested=True):
        # TODO: learn how to deactivate expensive sorting
        #self.model.set_default_sort_func(None)
        #self.model.set_sort_column_id(-1, gtk.SORT_ASCENDING)
        
        # save sorting if a single node was selected
        if self.sel_nodes is not None and len(self.sel_nodes) == 1:
            self.save_sorting(self.sel_nodes[0])
            
        
        #from rasmus import util
        #util.tic("view")

        model = self.model
        self.set_model(None)        
        self.sel_nodes = nodes

        model.get_model().set_nested(nested)

        if len(nodes) == 1:
            model.get_model().set_master_node(nodes[0])
            self.set_master_node(nodes[0])
        else:
            model.get_model().set_master_node(None)
            self.set_master_node(None)
        
        # populate model
        roots = []
        for node in nodes:
            if isinstance(node, NoteBookDir):
                for child in node.get_children():
                    roots.append(child)
            elif isinstance(node, NoteBookPage):
                roots.append(node)

        model.get_model().set_root_nodes(roots)
        
        # load sorting if single node is selected
        if len(nodes) == 1:
            self.load_sorting(nodes[0], model)
        
        # reactivate model
        self.set_model(model)
        
        #util.toc()

        # expand rows
        for node in roots:
            if node.is_expanded2():
                self.expand_to_path(treemodel.get_path_from_node(self.model, node))

        # disable if no roots
        if len(roots) == 0:
            self.set_sensitive(False)
        else:
            self.set_sensitive(True)

        # update status
        npages = len(roots)
        if npages != 1:
            self.set_status("%d pages" % npages, "stats")
        else:
            self.set_status("1 page", "stats")

        self.emit("select-nodes", [])

                
    def expand_node(self, node):
        try:
            path = treemodel.get_path_from_node(self.model, node)        
            self.expand_to_path(path)
        except Exception:
            pass
        
    
    def edit_node(self, page):
        path = treemodel.get_path_from_node(self.model, page)
        assert path is not None
        self.set_cursor_on_cell(path, self.title_column, self.title_text, True)
        path, col = self.get_cursor()
        self.scroll_to_cell(path)
    
    
    def select_pages(self, pages):
        page = pages[0]
        path = treemodel.get_path_from_node(self.model, page)
        if path is not None:
            self.set_cursor_on_cell(path)

    
    def set_notebook(self, notebook):
        if self.model is not None:
            self.set_sensitive(True)
            self.model.get_model().set_root_nodes([])
        else:
            self.set_sensitive(False)


    
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


    def load_sorting(self, node, model):
        """Load sorting information from node"""

        info_sort, sort_dir = node.get_info_sort()
            
        if sort_dir:
            sort_dir = gtk.SORT_ASCENDING
        else:
            sort_dir = gtk.SORT_DESCENDING            

            
        if info_sort == notebook.INFO_SORT_MANUAL or \
           info_sort == notebook.INFO_SORT_NONE:
            model.set_sort_column_id(COL_MANUAL, sort_dir)
            self.set_reorder(treemodel.REORDER_ALL)
        elif info_sort == notebook.INFO_SORT_TITLE:
            model.set_sort_column_id(COL_TITLE, sort_dir)
            self.set_reorder(treemodel.REORDER_FOLDER)
        elif info_sort == notebook.INFO_SORT_CREATED_TIME:
            model.set_sort_column_id(COL_CREATED_INT, sort_dir)
            self.set_reorder(treemodel.REORDER_FOLDER)
        elif info_sort == notebook.INFO_SORT_MODIFIED_TIME:
            model.set_sort_column_id(COL_MODIFIED_INT, sort_dir)
            self.set_reorder(treemodel.REORDER_FOLDER)

    
    def set_status(self, text, bar="status"):
        if self.on_status:
            self.on_status(text, bar=bar)

gobject.type_register(TakeNoteSelector)
gobject.signal_new("select-nodes", TakeNoteSelector, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("view-node", TakeNoteSelector, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("error", TakeNoteSelector, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object,))
