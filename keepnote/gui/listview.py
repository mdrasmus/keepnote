"""

    KeepNote    
    ListView

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@mit.edu>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA.
#

import gettext

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

from keepnote.timestamp import get_str_timestamp
from keepnote.gui import basetreeview
from keepnote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf
from keepnote.gui import treemodel
from keepnote import notebook
from keepnote.notebook import NoteBookError
import keepnote

_ = keepnote.translate



class KeepNoteListView (basetreeview.KeepNoteBaseTreeView):
    
    def __init__(self):
        basetreeview.KeepNoteBaseTreeView.__init__(self)
        self._sel_nodes = None

        # configurable callback for setting window status
        self.on_status = None        
        
        # selection config
        self.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        
        # init view
        self.connect("key-release-event", self.on_key_released)
        self.connect("button-press-event", self.on_button_press)
        self.connect("row-expanded", self._on_listview_row_expanded)
        self.connect("row-collapsed", self._on_listview_row_collapsed)
        
        self.set_rules_hint(True)
        self.set_fixed_height_mode(True)
        self.set_sensitive(False)        

        # init model
        self.set_model(gtk.TreeModelSort(treemodel.KeepNoteTreeModel()))
        self.setup_columns()


    def set_model(self, model):
        basetreeview.KeepNoteBaseTreeView.set_model(self, model)
        self.model.connect("sort-column-changed", self._sort_column_changed)



    def clear_columns(self):
        for col in reversed(self.get_columns()):
            self.remove_column(col)

    '''
    def get_attr_column(self, attr, key=lambda x: x):
        assert self._notebook is not None
        
        col = self._columns_lookup.get(attr, None)
        if col is None:
            # TODO: make an API for querying attr_defs
            attr_defs = self._notebook.get_attr("attr_defs")
            for attr_def in attr_defs:
                if attr_def.get("key") == attr:
                    break
            else:
                attr_def = None
            datatype = attr_def.get("datatype", "string") if attr_def else \
                "string"
            
            get = lambda node: key(node.get_attr(attr))
            
            if datatype == "string":
                coltype = str
            elif datatype == "integer":
                coltype = int
            elif datatype == "timestamp":
                coltype = str
            else:
                coltype = str
                
            col = TreeModelColumn(attr, coltype, attr=attr, get=get)
            self.append_column(col)
        return col
    '''

    def setup_columns(self):

        if self._notebook is None:
            self.clear_columns()
            return
        

        self._columns = ["title", "created_time", "modified_time"]

        # TODO: columns actually need to be set when notebook is loaded
        # eventually columns may change when ever master node changes
        
        
        # title column
        title_column = gtk.TreeViewColumn()
        title_column.set_title(_("Title"))
        title_column.set_sort_column_id(
            self.rich_model.get_column_by_name("title_sort").pos)

        title_column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        title_column.set_property("resizable", True)
        title_column.set_min_width(10)
        title_column.set_fixed_width(250)

        # title icon
        cell_icon = gtk.CellRendererPixbuf()
        title_column.pack_start(cell_icon, False)
        title_column.add_attribute(cell_icon, 'pixbuf',
            self.rich_model.get_column_by_name("icon").pos)
        title_column.add_attribute(cell_icon, 'pixbuf-expander-open',
            self.rich_model.get_column_by_name("icon_open").pos)

        # title text
        title_text = gtk.CellRendererText()
        title_column.pack_start(title_text, True)
        title_text.set_fixed_height_from_font(1)
        title_text.connect("edited", lambda r,p,t: self.on_edit_attr(
            r, p, "title", t, validate=lambda t: t != ""))
        title_text.connect("editing-started", self.on_editing_started)
        title_text.connect("editing-canceled", self.on_editing_canceled)        
        title_text.set_property("editable", True)
        title_column.add_attribute(title_text, 'text',
            self.rich_model.get_column_by_name("title").pos)

        self.append_column(title_column)
        self.set_expander_column(title_column)
        
        self.title_text = title_text
        self.title_column = title_column
        
        
        # add columns
        self.add_column("created_time")
        self.add_column("modified_time")

        '''
        column = gtk.TreeViewColumn()
        column.set_title(_("Created"))
        column.set_sort_column_id(
            self.rich_model.get_column_by_name("created_time2_sort").pos)
        make_column(column, "created_time")

        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text',
            self.rich_model.get_column_by_name("created_time2").pos)
        
        self.append_column(column)        
        '''

        '''
        # modified column
        column = gtk.TreeViewColumn()
        column.set_title(_("Modified"))
        column.set_sort_column_id(
            self.rich_model.get_column_by_name("modified_time_sort").pos)
        make_column(column, "modified_time")
        
        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)        
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text',
            self.rich_model.get_column_by_name("modified_time").pos)
        
        self.append_column(column)
        '''
        
        # NOTE: must create a new TreeModelSort whenever we add new columns
        # to the rich_model that could be used in sorting
        # Perhaps something is being cached
        self.set_model(gtk.TreeModelSort(self.rich_model))

        # TODO: load correct sorting right away
        # set default sorting
        # remember sort per node
        self.model.set_sort_column_id(
            self.rich_model.get_column_by_name("order").pos,
            gtk.SORT_ASCENDING)
        self.set_reorder(basetreeview.REORDER_ALL)
        

    def format_timestamp(self, timestamp):
        return (get_str_timestamp(timestamp, 
                                  formats=self.rich_model._date_formats)
                if timestamp is not None else u"")


    def add_column(self, attr):
        
        # get attribute definition from notebook
        attr_def = self._notebook.attr_defs.get(attr)

        # get datatype
        if attr_def is not None:
            datatype = attr_def.datatype
            col_title = attr_def.name
        else:
            datatype = "string"
            col_title = attr

        # create column view
        column = gtk.TreeViewColumn()
        column.set_property("sizing", gtk.TREE_VIEW_COLUMN_FIXED)
        column.set_property("resizable", True)
        column.set_min_width(10)
        column.set_fixed_width(
            self._notebook.get_attr("column_widths", {}).get(attr, 150))
        column.set_title(col_title)


        # get/make model column
        self._add_model_column(attr)

        # cell renderer text
        cell_text = gtk.CellRendererText()
        cell_text.set_fixed_height_from_font(1)
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 
                             self.rich_model.get_column_by_name(attr).pos)

        # define column sorting
        attr_sort = attr + "_sort"
        column.set_sort_column_id(
            self.rich_model.get_column_by_name(attr_sort).pos)


        self.append_column(column)

    
    def _add_model_column(self, attr):
 
        # get attribute definition from notebook
        attr_def = self._notebook.attr_defs.get(attr)

        # get datatype
        if attr_def is not None:
            datatype = attr_def.datatype
            default = attr_def.default
        else:
            datatype = "string"
            default = ""

        # get/make model column
        col = self.rich_model.get_column_by_name(attr)
        if col is None:
            mapfunc = lambda x: x

            # get coltype
            if datatype == "string":
                coltype = str
                coltype_sort = str
            elif datatype == "integer":
                coltype = int
                coltype_sort = int
            elif datatype == "float":
                coltype = float
                coltype_sort = float
            elif datatype == "timestamp":
                mapfunc = self.format_timestamp
                coltype = str
                coltype_sort = int
            else:
                coltype = str
                coltype_sort = str

            get = lambda node: mapfunc(node.get_attr(attr, default))
            
            col = treemodel.TreeModelColumn(attr, coltype, attr=attr, get=get)
            self.rich_model.append_column(col)
        
        # define column sorting
        attr_sort = attr + "_sort"
        col = self.rich_model.get_column_by_name(attr_sort)
        if col is None:
            col = treemodel.TreeModelColumn(
                attr_sort, coltype_sort,
                attr=attr,
                get=lambda node: node.get_attr(attr, default))
            self.rich_model.append_column(col)
        


    
    def set_notebook(self, notebook):
        """Set the notebook for listview"""
        basetreeview.KeepNoteBaseTreeView.set_notebook(self, notebook)
        
        if self.rich_model is not None:
            self.rich_model.set_root_nodes([])

        if notebook:
            self.set_sensitive(True)
        else:
            self.set_sensitive(False)

        self.setup_columns()


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

        # don't save the expand state of the master node
        if len(treemodel.get_path_from_node(
               self.model, node,
               self.rich_model.get_node_column_pos())) > 1:
            node.set_attr("expanded2", expand)
            

    def _sort_column_changed(self, sortmodel):
        self._update_reorder()
        

    def _update_reorder(self):
        col_id, sort_dir = self.model.get_sort_column_id()

        if col_id is None or col_id < 0:
            col = None
        else:
            col = self.rich_model.get_column(col_id)
        
        if col is None: #  or col.attr == "order"
            self.model.set_sort_column_id(
                self.rich_model.get_column_by_name("order").pos,
                gtk.SORT_ASCENDING)
            self.set_reorder(basetreeview.REORDER_ALL)
        else:
            self.set_reorder(basetreeview.REORDER_FOLDER)        

    
    def on_key_released(self, widget, event):
        """Callback for key release events"""

        # no special processing while editing nodes
        if self.editing_path:
            return

        if event.keyval == gtk.keysyms.Delete:
            # capture node deletes
            self.stop_emission("key-release-event")
            self.emit("delete-node", self.get_selected_nodes())
            
        elif event.keyval == gtk.keysyms.BackSpace and \
             event.state & gdk.CONTROL_MASK:
            # capture goto parent node
            self.stop_emission("key-release-event")
            self.emit("goto-parent-node")


        elif event.keyval == gtk.keysyms.Return and \
             event.state & gdk.CONTROL_MASK:
            # capture goto node
            self.stop_emission("key-release-event")
            self.emit("activate-node", None)
            


    def on_button_press(self, widget, event):
        if event.button == 3:            
            # popup menu
            return self.popup_menu(event.x, event.y, event.button, event.time)
            

        if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
            model, paths = self.get_selection().get_selected_rows()
            # double click --> goto node
            if len(paths) > 0:
                nodes = [self.model.get_value(self.model.get_iter(x),
                                              self.rich_model.get_node_column_pos())
                         for x in paths]

                # NOTE: can only view one node
                self.emit("activate-node", nodes[0])
    

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
            
        if len(nodes) > 1:
            nested = False
        
        self._sel_nodes = nodes
        self.rich_model.set_nested(nested)

        # set master node
        self.set_master_node(None)
        
        # populate model
        roots = nodes
        self.rich_model.set_root_nodes(roots)

        # load sorting if single node is selected
        if len(nodes) == 1:
            self.load_sorting(nodes[0], self.model)
        
        # expand rows
        for node in roots:
            self.expand_to_path(treemodel.get_path_from_node(
                self.model, node, self.rich_model.get_node_column_pos()))

        # disable if no roots
        if len(roots) == 0:
            self.set_sensitive(False)
        else:
            self.set_sensitive(True)

        # update status
        self.display_page_count()

        self.emit("select-nodes", [])


    def append_node(self, node):

        # do not allow appending of nodes unless we are masterless
        if self.get_master_node() is not None:
            return

        self.rich_model.append(node)
        
        if node.get_attr("expanded2", False):
            self.expand_to_path(treemodel.get_path_from_node(
                self.model, node, self.rich_model.get_node_column_pos()))

        self.set_sensitive(True)        

        # update status
        #self.display_page_count()


    def display_page_count(self, npages=None):

        if npages is None:
            #npages = len(self.get_root_nodes())
            npages = self.count_pages(self.get_root_nodes())

        if npages != 1:
            self.set_status(_("%d pages") % npages, "stats")
        else:
            self.set_status(_("1 page"), "stats")


    def count_pages(self, roots):

        # TODO: is there a way to make this faster?
        
        def walk(node):
            npages = 1
            if (self.rich_model.get_nested() and 
                (node.get_attr("expanded2", False))):
                for child in node.get_children():
                    npages += walk(child)
            return npages

        return sum(walk(child) for node in roots
                   for child in node.get_children())
        
    
    def edit_node(self, page):
        path = treemodel.get_path_from_node(
            self.model, page, self.rich_model.get_node_column_pos())
        if path is None:
            # view page first if not in view
            self.emit("goto-node", page)
            path = treemodel.get_path_from_node(
                self.model, page, self.rich_model.get_node_column_pos())
            assert path is not None
        self.set_cursor_on_cell(path, self.title_column, self.title_text, True)
        path, col = self.get_cursor()
        self.scroll_to_cell(path)
        

    #def cancel_editing(self):
    #    # TODO: add this
    #    pass
    #    #self.cell_text.stop_editing(True)

    
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
            node.set_attr("info_sort", col.attr)
            node.set_attr("info_sort_dir", sort_dir)


    def load_sorting(self, node, model):
        """Load sorting information from node"""

        info_sort = node.get_attr("info_sort", "order")
        sort_dir = node.get_attr("info_sort_dir", 1)
            
        if sort_dir:
            sort_dir = gtk.SORT_ASCENDING
        else:
            sort_dir = gtk.SORT_DESCENDING            

        # default sorting
        if info_sort == "":
            info_sort = "order"

        for col in self.rich_model.get_columns():
            if info_sort == col.attr and col.name.endswith("_sort"):
                model.set_sort_column_id(col.pos, sort_dir)

        self._update_reorder()

    
    def set_status(self, text, bar="status"):
        if self.on_status:
            self.on_status(text, bar=bar)


    def _on_node_changed_end(self, model, nodes):
        basetreeview.KeepNoteBaseTreeView._on_node_changed_end(self, model, nodes)

        # make sure root is always expanded
        if self.rich_model.get_nested():
            # determine root set
            child = model.iter_children(None)
            while child is not None:
                self.expand_row(model.get_path(child), False)
                child = model.iter_next(child)

    def _on_listview_row_expanded(self, treeview, it, path):
        """Callback for row expand"""
        self.display_page_count()
        
    
    def _on_listview_row_collapsed(self, treeview, it, path):
        self.display_page_count()


