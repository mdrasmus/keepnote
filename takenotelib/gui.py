"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for TakeNote Application
"""

# TODO: shade undo/redo
# TODO: allow open file for *.nbk files
# TODO: add node reordering
# TODO: add pages in treeview
#       will eventually require lazy loading for treeview
# TODO: add basedir to all image loading
#       use get_takenote_file(filename)
# TODO: add framework for customized page selector columns



# python imports
import sys, os, tempfile, re

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenotelib as takenote
from takenotelib.undo import UndoStack
from takenotelib.richtext import RichTextView, RichTextImage

# constants
PROGRAM_NAME = "TakeNode"
PROGRAM_VERSION = "0.1"

DROP_YES = ("drop_yes", gtk.TARGET_SAME_WIDGET, 0)
DROP_NO = ("drop_no", gtk.TARGET_SAME_WIDGET, 0)


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
        
        lpath = list(path)
        for i, child in enumerate(get_child_data(data)):
            lpath.append(i)
            self.add_path_all(tuple(lpath), child, get_child_data)
            lpath.pop()
        
        self.data2path[data] = path
        self.path2data[path] = data

    
    def clear_path(self):
        self.data2path.clear()
        self.path2data.clear()
    
            
        

def str2path(pathtext):
    """Converts str to tuple path"""
    # sometime GTK returns a str instead of a tuple for a path... weird
    return tuple(map(int, pathtext.split(":")))


def dnd_sanity_check(source_path, target_path):
    """The target cannot be a descendant of the source
       i.e. You cannot become your descendent's child
       i.e. The source path cannot be a prefix of the target path"""
    return source_path != target_path[:len(source_path)]
    
    

class TakeNoteTreeStore (gtk.TreeStore):
    
    def __init__(self, *args, **kargs):
        gtk.TreeStore.__init__(self, *args, **kargs)
        
    
    def row_drop_possible(self, dest_path, selection_data):
        print "drop", dest_path
        return len(dest_path) > 1
   

class TakeNoteTreeView (object):
    
    def __init__(self):
        self.on_select_node = None
    
        # create a TreeStore with one string column to use as the model
        self.model = TakeNoteTreeStore(gdk.Pixbuf, str, object)
        self.datamap = DataMap()
                        
        # init treeview
        self.treeview = gtk.TreeView(self.model)
        self.treeview.connect("key-release-event", self.on_key_released)
        self.expanded_id = self.treeview.connect("row-expanded", self.on_row_expanded)
        self.collapsed_id = self.treeview.connect("row-collapsed", self.on_row_collapsed) 
        self.treeview.connect("drag-motion", self.on_drag_motion)
        self.treeview.connect("drag-data-received", self.on_drag_data_received)
        #self.treeview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)
        self.treeview.get_selection().connect("changed", self.on_select_changed)
        self.treeview.set_headers_visible(False)
        #self.treeview.set_property("enable-tree-lines", True)
        # make treeview searchable
        self.treeview.set_search_column(1) 
        self.treeview.set_reorderable(True)        
        self.treeview.enable_model_drag_source(
            gtk.gdk.BUTTON1_MASK, [DROP_YES], gtk.gdk.ACTION_MOVE)
        self.treeview.enable_model_drag_dest(
            [DROP_YES], gtk.gdk.ACTION_MOVE)        
        #self.treeview.set_fixed_height_mode(True)       

        # create the treeview column
        self.column = gtk.TreeViewColumn()
        self.column.set_clickable(False)
        self.treeview.append_column(self.column)

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
        
        self.icon = pixbuf = gdk.pixbuf_new_from_file("bitmaps/open.xpm")
        
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.set_shadow_type(gtk.SHADOW_IN)
        scrolled_window.add(self.treeview)
        self.view = scrolled_window
        
    
    
    #=============================================
    # gui callbacks
    
    def on_drag_motion(self, treeview, drag_context, x, y, eventtime):
        """Callback for drag motion.
           Indicate which drops are allowed"""
        
        # determine destination row   
        dest_row = treeview.get_dest_row_at_pos(x, y)
        if dest_row is None:
            return
        
        # get target and source
        target_path, drop_position  = dest_row    
        model, source = treeview.get_selection().get_selected()
        source_path = model.get_path(source)
        
        # determine if drag is allowed
        if self.drop_allowed(source_path, target_path, drop_position):
            treeview.enable_model_drag_dest([DROP_YES], gtk.gdk.ACTION_MOVE)
        else:
            treeview.enable_model_drag_dest([DROP_NO], gtk.gdk.ACTION_MOVE)
            

    def on_drag_data_received(self, treeview, drag_context, x, y,
                              selection_data, info, eventtime):
                              
        # determine destination row
        dest_row = treeview.get_dest_row_at_pos(x, y)
        if dest_row is None:
            return
        
        # get target and source
        model, source = treeview.get_selection().get_selected()
        target_path, drop_position  = dest_row    
        target = model.get_iter(target_path)
        source_path = model.get_path(source)
        
        
        # determine if drop is allowed
        if self.drop_allowed(source_path, target_path, drop_position):
            node = self.datamap.get_data(source_path)
            
            # record the node's old parent
            old_parent = node.get_parent()
            old_parent_path = source_path[:-1]
            
            # perform move in tree model
            self.treeview.handler_block(self.expanded_id)
            self.treeview.handler_block(self.collapsed_id)
            new_path = self.copy_row(treeview, model, source, target, drop_position)
            self.treeview.handler_unblock(self.expanded_id)
            self.treeview.handler_unblock(self.collapsed_id)
            
            # perform move in notebook model
            new_parent_path = new_path[:-1]
            new_parent = self.datamap.get_data(new_parent_path)
            node.move(new_parent, new_path[-1])
            
            # update notebook model mappings
            self.datamap.remove_path_all(new_parent_path, 
                lambda x: x.get_children())
            if old_parent != new_parent:
                self.datamap.remove_path_all(old_parent_path, 
                    lambda x: x.get_children())
        
            self.datamap.add_path_all(new_parent_path, new_parent,
                lambda x: x.get_children())
            
            if old_parent != new_parent:
                self.datamap.add_path_all(old_parent_path, old_parent,
                    lambda x: x.get_children())
            
            
            # make sure to show new children
            if (drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE or
                drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER):
                treeview.expand_row(target_path, False)
            drag_context.finish(True, True, eventtime)
        else:
            drag_context.finish(False, False, eventtime)
    
    
    def copy_row(self, treeview, model, source, target, drop_position):
        
        # move source row
        source_row = model[source]
        if drop_position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE:
            new = model.prepend(target, source_row)
        elif drop_position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER:
            new = model.append(target, source_row)
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
            self.copy_row(treeview, model, child, new,
                          gtk.TREE_VIEW_DROP_INTO_OR_BEFORE)
        
        # expand view to keep the same expansion pattern
        source_is_expanded = treeview.row_expanded(model.get_path(source))
        new_path = model.get_path(new)
        if source_is_expanded:
            self.expand_to_path(treeview, new_path)
        
        return new_path
    
    
    def expand_to_path(self, treeview, path):
        for i in range(len(path)):
            treeview.expand_row(path[:i+1], open_all=False)
    
    
    def drop_allowed(self, source_path, target_path, drop_position):
        """Determine if drop is allowed"""
        return dnd_sanity_check(source_path, target_path) and \
               not (target_path == (0,) and \
                    (drop_position == gtk.TREE_VIEW_DROP_BEFORE or 
                     drop_position == gtk.TREE_VIEW_DROP_AFTER))
        
    
    def on_row_expanded(self, treeview, it, path):
        self.datamap.get_data(path).set_expand(True)

    def on_row_collapsed(self, treeview, it, path):
        self.datamap.get_data(path).set_expand(False)

        
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete"):
            self.on_delete_node()
            self.treeview.stop_emission("key-release-event")
            

    def on_edit_title(self, cellrenderertext, path, new_text):
        try:
            node = self.datamap.get_data(path)
            node.rename(new_text)
            
            self.model[path][1] = new_text
        except Exception, e:
            print e
            print "takenote: could not rename '%s'" % node.get_title()
    
    
    def on_select_changed(self, treeselect): 
        model, paths = treeselect.get_selected_rows()
        
        if len(paths) > 0 and self.on_select_node:
            self.on_select_node(self.datamap.get_data(paths[0]))
        return True
    
    
    def on_delete_node(self):
        
        model, it = self.treeview.get_selection().get_selected()
        node = self.datamap.get_data(model.get_path(it))
        parent = node.get_parent()
        
        if parent != None:
            node.delete()
            self.update_node(parent)
        else:
            # warn
            print "Cannot delete notebook's toplevel directory"    
    
    #==============================================
    # actions
    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
            self.datamap.clear_path()
        
        else:
            root = self.notebook.get_root_node()
            self.add_node(None, root)
            
    
    
    def edit_node(self, node):
        path = self.datamap.get_path(node)
        self.treeview.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        self.treeview.scroll_to_cell(path)

    
    def expand_node(self, node):
        path = self.datamap.get_path(node)
        self.treeview.expand_to_path(path)
        
    
    def add_node(self, parent, node):
        it = self.model.append(parent, [self.icon, node.get_title(), node])
        path = self.model.get_path(it)
        self.datamap.add_path(path, node)
        
        for child in node.get_children():
            self.add_node(it, child)
        
        if node.is_expanded():
            self.treeview.expand_to_path(self.datamap.get_path(node))
    
    
    def update_node(self, node):
        path = self.datamap.get_path(node)
        expanded = self.treeview.row_expanded(path)
        
        for child in self.model[path].iterchildren():
            self.datamap.remove_path_all(child.path, lambda x: x.get_children())
            self.model.remove(child.iter)
        
        it = self.model.get_iter(path)
        for child in node.get_children():
            self.add_node(it, child)
        
        self.treeview.expand_to_path(path)
    
    
    



class TakeNoteSelector (object):
    
    def __init__(self):
        self.on_select_node = None
        self.sel_nodes = None
        
        # init model
        self.model = gtk.ListStore(gdk.Pixbuf, gobject.TYPE_STRING, object)
        self.datamap = DataMap()        
        
        # init view
        self.treeview = gtk.TreeView(self.model)
        self.treeview.connect("key-release-event", self.on_key_released)        
        self.treeview.get_selection().connect("changed", self.on_select_changed)
        self.treeview.set_rules_hint(True)
        #self.treeview.set_fixed_height_mode(True)
        
        cell_icon = gtk.CellRendererPixbuf()
        self.cell_text = gtk.CellRendererText()
        self.column = gtk.TreeViewColumn()
        self.column.set_title("Pages")
        self.treeview.append_column(self.column)
        
        self.column.pack_start(cell_icon, False)
        self.column.pack_start(self.cell_text, True)
        self.cell_text.connect("edited", self.on_edit_title)
        self.cell_text.set_property("editable", True)

        # map cells to columns in model
        self.column.add_attribute(cell_icon, 'pixbuf', 0)
        self.column.add_attribute(self.cell_text, 'text', 1)
        
        self.icon = pixbuf = gdk.pixbuf_new_from_file("bitmaps/copy.xpm")


        # Create a new scrolled window, with scrollbars only if needed
        scrolled_window = gtk.ScrolledWindow()
        scrolled_window.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        scrolled_window.set_shadow_type(gtk.SHADOW_IN)        
        scrolled_window.add(self.treeview)
        self.view = scrolled_window

    #=============================================
    # gui callbacks
    
    def on_key_released(self, widget, event):
        if event.keyval == gdk.keyval_from_name("Delete"):
            self.on_delete_page()
            self.treeview.stop_emission("key-release-event")
    

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
        model, it = self.treeview.get_selection().get_selected()
        path = self.model.get_path(it)
        page = self.datamap.get_data(model.get_path(it))
        self.datamap.remove_path(path)
        page.delete()
        self.update()
    
    
    #====================================================
    # actions
    
    def view_nodes(self, nodes):
        self.sel_nodes = nodes
        self.model.clear()
        self.datamap.clear_path()
        
        for node in nodes:
            for page in node.get_pages():
                it = self.model.append()
                self.model.set(it, 0, self.icon)                
                self.model.set(it, 1, page.get_title())
                self.model.set(it, 2, page)
                path = self.model.get_path(it)
                self.datamap.add_path(path, page)
        self.on_select_node(None)        
    
    
    def update(self):
        self.view_nodes(self.sel_nodes)    
    
    def edit_node(self, page):
        path = self.datamap.get_path(page)
        self.treeview.set_cursor_on_cell(path, self.column, self.cell_text, 
                                         True)
        path, col = self.treeview.get_cursor()
        self.treeview.scroll_to_cell(path)
    
    
    def select_pages(self, pages):
        page = pages[0]
        path = self.datamap.get_path(page)
        if path != None:
            self.treeview.set_cursor_on_cell(path)

    
    def set_notebook(self, notebook):
        self.notebook = notebook
        
        if self.notebook is None:
            self.model.clear()
            self.datamap.clear_path()





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
        if self.page is not None and self.page.is_valid():
            self.textview.save(self.page.get_data_file())


class TakeNoteWindow (gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self.set_title("TakeNote")
        self.set_default_size(*takenote.DEFAULT_WINDOW_SIZE)
        self.connect("delete-event", lambda w,e: self.on_close())
        
        self.notebook = None
        self.sel_nodes = []
        self.current_page = None
        
        # selector
        self.selector = TakeNoteSelector()
        self.selector.on_select_node = self.on_select_page
        
        # treeview
        self.treeview = TakeNoteTreeView()
        self.treeview.on_select_node = self.on_select_treenode
        
        # editor
        self.editor = TakeNoteEditor()
        self.editor.textview.font_callback = self.on_font_change
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
        self.status_bar = gtk.Statusbar()      
        main_vbox.pack_start(self.status_bar, False, True, 0)  


        # layout major widgets
        self.hpaned.add1(self.treeview.view)
        self.vpaned.add1(self.selector.view)        
        self.vpaned.add2(self.editor.view)
        
        
        self.show_all()        
        self.treeview.treeview.grab_focus()
    

    
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
        except Exception, e:
            self.notebook = None
            print e
            print "could not create new notebook"
        
        self.open_notebook(filename)
        
        
    
    def open_notebook(self, filename):
        if self.notebook is not None:
            self.close_notebook()
        
        self.notebook = takenote.NoteBook()
        self.notebook.load(filename)
        self.selector.set_notebook(self.notebook)
        self.treeview.set_notebook(self.notebook)
        self.get_preferences()
        
        self.treeview.treeview.grab_focus()
        
        
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
    
    
    
    def on_close(self):
        """close the window and quit"""
        self.close_notebook()
        gtk.main_quit()
        return False
    
    
    def on_select_treenode(self, node):
        self.sel_nodes = [node]
        self.selector.view_nodes([node])
    
    def on_select_page(self, page):
        self.current_page = page
        self.editor.view_page(page)
        
    
    
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
        if self.current_page == None:
            return
    
        f, imgfile = tempfile.mkstemp(".xpm", "takenote")
        os.close(f)
    
        os.system("import %s" % imgfile)
        if os.path.exists(imgfile):
            try:
                pixbuf = gdk.pixbuf_new_from_file(imgfile)
                img = RichTextImage()
                img.set_from_pixbuf(pixbuf)
                self.editor.textview.insert_image(img, "screenshot.jpg")
            except Exception, e:
                print e
                print "error reading screenshot '%s'" % imgfile
            
            os.remove(imgfile)        

    def on_choose_font(self):
        self.font_sel.clicked()
    
    
    def on_font_set(self):
        self.editor.textview.on_font_set(self.font_sel)
        self.editor.textview.grab_focus()
    
    
    def on_goto_treeview(self):
        self.treeview.treeview.grab_focus()
        
    def on_goto_listview(self):
        self.selector.treeview.grab_focus()
        
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
            ("/File/_Save Page",     
                "<control>S", lambda w,e: self.editor.save(), 0, None),
            ("/File/_Close Notebook", 
                "<control>W", lambda w, e: self.close_notebook(), 0, None),
            ("/File/sep1", 
                None, None, 0, "<Separator>" ),
            ("/File/Quit", 
                "<control>Q", lambda w,e: self.on_close(), 0, None),

            ("/_Edit", 
                None, None, 0, "<Branch>"),
            ("/Edit/Un_do",     
                "<control>Z", lambda w,e: self.editor.textview.undo(), 0, None),
            ("/Edit/_Redo", 
                "<control><shift>Z", lambda w,e: self.editor.textview.redo(), 0, None),
            ("/Edit/sep1", 
                None, None, 0, "<Separator>"),
            ("/Edit/Insert Screenshot",
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
        icon.set_from_file("bitmaps/bold.xpm")
        self.bold_button = gtk.ToggleToolButton()
        self.bold_button.set_icon_widget(icon)
        tips.set_tip(self.bold_button, "Bold")
        self.bold_id = self.bold_button.connect("toggled", lambda w: self.editor.textview.on_bold())
        toolbar.insert(self.bold_button, -1)


        # italic tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/italic.xpm")
        self.italic_button = gtk.ToggleToolButton()
        self.italic_button.set_icon_widget(icon)
        tips.set_tip(self.italic_button, "Italic")
        self.italic_id = self.italic_button.connect("toggled", lambda w: self.editor.textview.on_italic())
        toolbar.insert(self.italic_button, -1)

        # underline tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/underline.xpm")
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
        icon.set_from_file("bitmaps/alignleft.xpm")
        self.left_button = gtk.ToggleToolButton()
        self.left_button.set_icon_widget(icon)
        tips.set_tip(self.left_button, "Left Justify")
        self.left_id = self.left_button.connect("toggled", lambda w: self.editor.textview.on_left_justify())
        toolbar.insert(self.left_button, -1)
        
        # center tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/aligncenter.xpm")
        self.center_button = gtk.ToggleToolButton()
        self.center_button.set_icon_widget(icon)
        tips.set_tip(self.center_button, "Center Justify")
        self.center_id = self.center_button.connect("toggled", lambda w: self.editor.textview.on_center_justify())
        toolbar.insert(self.center_button, -1)
        
        # right tool
        icon = gtk.Image() # icon widget
        icon.set_from_file("bitmaps/alignright.xpm")
        self.right_button = gtk.ToggleToolButton()
        self.right_button.set_icon_widget(icon)
        tips.set_tip(self.right_button, "Right Justify")
        self.right_id = self.right_button.connect("toggled", lambda w: self.editor.textview.on_right_justify())
        toolbar.insert(self.right_button, -1)        
        
        return toolbar


class TakeNote (object):
    
    def __init__(self, basedir=""):
        self.window = TakeNoteWindow()
        self.basedir = basedir
        
    def open_notebook(self, filename):
        self.window.open_notebook(filename)

