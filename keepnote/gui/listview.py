"""

    KeepNote
    
    ListView

"""


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk


from keepnote.gui import basetreeview
from keepnote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf
from keepnote.gui import treemodel
from keepnote import notebook
from keepnote.notebook import NoteBookError




class KeepNoteListView (basetreeview.KeepNoteBaseTreeView):
    
    def __init__(self):
        basetreeview.KeepNoteBaseTreeView.__init__(self)
        self._sel_nodes = None

        # configurable callback for setting window status
        self.on_status = None        
        
        # init model
        self.set_model(gtk.TreeModelSort(treemodel.KeepNoteTreeModel()))

        self.model.connect("sort-column-changed", self._sort_column_changed)
        
        # init view
        self.connect("key-release-event", self.on_key_released)
        self.connect("button-press-event", self.on_button_press)
        
        self.set_rules_hint(True)
        self.set_fixed_height_mode(True)
        
        
        # directory order column
        '''
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
        '''

        
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
        self.title_column.set_sort_column_id(
            self.rich_model.get_column_by_name("title_sort").pos)
        # map cells to columns in model
        self.title_column.add_attribute(cell_icon, 'pixbuf',
            self.rich_model.get_column_by_name("icon").pos)
        self.title_column.add_attribute(cell_icon, 'pixbuf-expander-open',
            self.rich_model.get_column_by_name("icon_open").pos)
        self.title_column.add_attribute(self.title_text, 'text',
            self.rich_model.get_column_by_name("title").pos)
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
        column.set_sort_column_id(
            self.rich_model.get_column_by_name("created_time_sort").pos)
        column.connect("clicked", self.on_column_clicked)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text',
            self.rich_model.get_column_by_name("created_time").pos)
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
        column.set_sort_column_id(
            self.rich_model.get_column_by_name("modified_time_sort").pos)
        column.connect("clicked", self.on_column_clicked)
        #column.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
        #column.set_property("min-width", 5)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text',
            self.rich_model.get_column_by_name("modified_time").pos)
        self.append_column(column)
        
        
        # set default sorting
        # remember sort per node
        self.model.set_sort_column_id(
            self.rich_model.get_column_by_name("order").pos,
            gtk.SORT_ASCENDING)
        self.set_reorder(basetreeview.REORDER_ALL)
        
        self.menu = gtk.Menu()
        self.menu.attach_to_widget(self, lambda w,m:None)

        self.set_sensitive(False)


    
    def set_notebook(self, notebook):
        """Set the notebook for listview"""
        basetreeview.KeepNoteBaseTreeView.set_notebook(self, notebook)
        
        if self.rich_model is not None:
            self.rich_model.set_root_nodes([])

        if notebook:
            self.set_sensitive(True)
        else:
            self.set_sensitive(False)


    def set_date_formats(self, formats):
        """Set the date formats used for dates"""
        if self.rich_model:
            self.rich_model.set_date_formats(formats)

    def get_root_nodes(self):
        """Returns the root nodes displayed in listview"""
        if self.rich_model:
            return self.rich_model.get_root_nodes()
        else:
            return []

    #=============================================
    # gui callbacks    


    def is_node_expanded(self, node):
        return node.get_attr("expanded2", False)

    def set_node_expanded(self, node, expand):
        node.set_attr("expanded2", expand)
        

    def on_column_clicked(self, column):
        pass
        #self.set_reorder(basetreeview.REORDER_FOLDER)

    '''
    def on_directory_column_clicked(self, column):
        """sort pages by directory order"""
        self.model.set_sort_column_id(
            self.rich_model.get_column_by_name("order").pos,
            gtk.SORT_ASCENDING)
        self.set_reorder(basetreeview.REORDER_ALL)
    '''

    def _sort_column_changed(self, sortmodel):
        col, sort_dir = self.model.get_sort_column_id()

        if col is None or col < 0:
            self.model.set_sort_column_id(
                self.rich_model.get_column_by_name("order").pos,
                gtk.SORT_ASCENDING)
            self.set_reorder(basetreeview.REORDER_ALL)
        else:
            self.set_reorder(basetreeview.REORDER_FOLDER)
        
    
    def on_key_released(self, widget, event):
        """Callback for key release events"""

        # no special processing while editing nodes
        if self.editing:
            return

        if event.keyval == gdk.keyval_from_name("Delete"):
            # capture node deletes
            self.stop_emission("key-release-event")            
            self.on_delete_node()
            
        elif event.keyval == gdk.keyval_from_name("BackSpace") and \
             event.state & gdk.CONTROL_MASK:
            # capture goto parent node
            self.stop_emission("key-release-event")
            self.emit("goto-parent-node")


        elif event.keyval == gdk.keyval_from_name("Return") and \
             event.state & gdk.CONTROL_MASK:
            # capture goto node
            self.stop_emission("key-release-event")
            self.emit("goto-node", None)
            


    def on_button_press(self, widget, event):
        if event.button == 3:            
            # popup menu
            self.popup_menu(event.x, event.y, event.button, event.time)
            

        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            model, paths = self.get_selection().get_selected_rows()
            # double click --> goto node
            if len(paths) > 0:
                nodes = [self.model.get_value(self.model.get_iter(x),
                                              self.rich_model.get_node_column())
                         for x in paths]

                # NOTE: can only view one node
                self.emit("goto-node", nodes[0])
    

    def is_view_tree(self):

        # TODO: document this more
        return self.get_master_node() is not None
    
    #====================================================
    # actions
    
    def view_nodes(self, nodes, nested=True):
        # TODO: learn how to deactivate expensive sorting
        #self.model.set_default_sort_func(None)
        #self.model.set_sort_column_id(-1, gtk.SORT_ASCENDING)
        
        # save sorting if a single node was selected
        if self._sel_nodes is not None and len(self._sel_nodes) == 1:
            self.save_sorting(self._sel_nodes[0])
            
        
        self._sel_nodes = nodes

        self.rich_model.set_nested(nested)

        if len(nodes) == 1:
            self.set_master_node(nodes[0])
        else:
            self.set_master_node(None)
        
        # populate model
        roots = []
        for node in nodes:
            if nested and len(node.get_children()) > 0:
                # list directory contents
                for child in node.get_children():
                    roots.append(child)
            else:
                # list directory itself
                roots.append(node)

        self.rich_model.set_root_nodes(roots)
        
        # load sorting if single node is selected
        if len(nodes) == 1:
            self.load_sorting(nodes[0], self.model)
        
        # expand rows
        for node in roots:
            if node.get_attr("expanded2", False):
                self.expand_to_path(treemodel.get_path_from_node(
                    self.model, node, self.rich_model.get_node_column()))

        # disable if no roots
        if len(roots) == 0:
            self.set_sensitive(False)
        else:
            self.set_sensitive(True)

        # update status
        npages = len(self.get_root_nodes())
        if npages != 1:
            self.set_status("%d pages" % npages, "stats")
        else:
            self.set_status("1 page", "stats")

        self.emit("select-nodes", [])


    def append_node(self, node):

        # do allow appending of nodes unless we are masterless
        if self.get_master_node() is not None:
            return

        self.rich_model.append(node)
        if node.get_attr("expanded2", False):
            self.expand_to_path(treemodel.get_path_from_node(
                self.model, node, self.rich_model.get_node_column()))

        self.set_sensitive(True)

        # update status
        npages = len(self.get_root_nodes())
        if npages != 1:
            self.set_status("%d pages" % npages, "stats")
        else:
            self.set_status("1 page", "stats")

        
    
    def edit_node(self, page):
        path = treemodel.get_path_from_node(
            self.model, page, self.rich_model.get_node_column())
        if path is None:
            # view page first if not in view
            self.emit("goto-node", page)
            path = treemodel.get_path_from_node(
                self.model, page, self.get_node_column())
            assert path is not None
        self.set_cursor_on_cell(path, self.title_column, self.title_text, True)
        path, col = self.get_cursor()
        self.scroll_to_cell(path)
        

    
    def save_sorting(self, node):
        """Save sorting information into node"""

        info_sort, sort_dir = self.model.get_sort_column_id()

        if sort_dir == gtk.SORT_ASCENDING:
            sort_dir = 1
        else:
            sort_dir = 0

        if info_sort is None or info_sort < 0:
            col = self.rich_model.get_column_by_name("order")
        else:
            col = self.rich_model.get_column(info_sort)

        if col.attr:
            node.set_info_sort(col.attr, sort_dir)


    def load_sorting(self, node, model):
        """Load sorting information from node"""

        info_sort, sort_dir = node.get_info_sort()
            
        if sort_dir:
            sort_dir = gtk.SORT_ASCENDING
        else:
            sort_dir = gtk.SORT_DESCENDING            

        # default sorting
        if info_sort == "":
            info_sort = "order"

        #if info_sort == "order":
        #    reorder_mode = basetreeview.REORDER_ALL
        #else:
        #    reorder_mode = basetreeview.REORDER_FOLDER

        for col in self.rich_model.get_columns():
            if info_sort == col.attr:
                model.set_sort_column_id(col.pos, sort_dir)
                #self.set_reorder(reorder_mode)

    
    def set_status(self, text, bar="status"):
        if self.on_status:
            self.on_status(text, bar=bar)


# register new gtk signals
gobject.type_register(KeepNoteListView)
gobject.signal_new("goto-node", KeepNoteListView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("goto-parent-node", KeepNoteListView,
    gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ())
