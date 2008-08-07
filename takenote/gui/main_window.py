"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for TakeNote Application
"""



# python imports
import sys, os, tempfile, re, subprocess, shlex, shutil, time

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# takenote imports
import takenote
from takenote.gui import get_resource, get_resource_image, get_resource_pixbuf
from takenote.notebook import NoteBookError, NoteBookDir, NoteBookPage
from takenote import notebook as notebooklib
import takenote.search
from takenote.gui import richtext
from takenote.gui.richtext import RichTextView, RichTextImage, RichTextError
from takenote.gui.treeview import TakeNoteTreeView
from takenote.gui.noteselector import TakeNoteSelector
from takenote.gui import \
    quote_filename, \
    screenshot_win, \
    dialog_app_options, \
    dialog_find, \
    dialog_drag_drop_test, \
    dialog_image_resize, \
    TakeNoteError





class TakeNoteEditor (gtk.VBox): #(gtk.Notebook):

    def __init__(self):
        #gtk.Notebook.__init__(self)
        gtk.VBox.__init__(self, False, 0)
        #self.set_scrollable(True)
        self._notebook = None
        
        # TODO: may need to update fonts on page change
        # TODO: add page reorder
        # TODO: add close button on labels
        
        # state
        self._textviews = []
        self._pages = []
        
        self.new_tab()
        self.show()

    def set_notebook(self, notebook):
        self._notebook = notebook

        if self._notebook:
            for view in self._textviews:
                view.set_default_font(self._notebook.pref.default_font)
        else:
            self.clear_view()
    
    def on_font_callback(self, textview, font):
        self.emit("font-change", font)
    
    def on_modified_callback(self, page_num, modified):
        self.emit("modified", self._pages[page_num], modified)

    def on_child_activated(self, textview, child):
        self.emit("child-activated", textview, child)
    
    #def on_error_callback(self, widget, text, error):
    #    self.emit("error", text, error)
        
    
    def get_textview(self):
        #pos = self.get_current_tab()
        pos = 0
        
        if pos == -1:
            return None
        else:    
            return self._textviews[pos]
    
    
    def new_tab(self):
        self._textviews.append(RichTextView())

        if self._notebook:
            self._textviews[-1].set_default_font(self._notebook.pref.default_font)
        self._pages.append(None)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)       
        sw.add(self._textviews[-1])
        #self.append_page(sw, gtk.Label("(Untitled)"))
        self.pack_start(sw)
        self._textviews[-1].connect("font-change", self.on_font_callback)
        self._textviews[-1].connect("modified", lambda t, m:
            self.on_modified_callback(len(self._pages)-1, m))
        self._textviews[-1].connect("child-activated", self.on_child_activated)
        #self._textviews[-1].connect("error", self.on_error_callback)
        self._textviews[-1].disable()
        self._textviews[-1].show()
        sw.show()
        self.show()
        
    '''
    def close_tab(self, pos=None):
        if self.get_n_pages() <= 1:
            return
    
        if pos is None:
            pos = self.get_current_tab()
        
        self.save_tab(pos)

        del self._pages[pos]
        del self._textviews[pos]
        self.remove_page(pos)
    '''
    
    def get_n_pages(self):
        return 1
    
    def get_current_tab(self):
        return 0

    def is_focus(self):
        pos = self.get_current_tab()
        return self._textviews[pos].is_focus()

    def clear_view(self):
        pos = self.get_current_tab()
        self._pages[pos] = None
        self._textviews[pos].disable()
    
    def view_pages(self, pages):
        # TODO: generalize to multiple pages
        assert len(pages) <= 1

        
        if len(pages) == 0:
            self.save()
            if self.get_n_pages() > 0:
                self.clear_view()
                
        else:
            page = pages[0]
            
            if isinstance(page, NoteBookPage):
            
                self.save()
                if self.get_n_pages() == 0:
                    self.new_tab()
            
                pos = self.get_current_tab()
                self._pages[pos] = page
                self._textviews[pos].enable()
                #self.set_tab_label_text(self.get_children()[pos], 
                #                        self._pages[pos].get_title())
            
                try:                
                    self._textviews[pos].load(self._pages[pos].get_data_file())
                except RichTextError, e:
                    self.clear_view()                
                    self.emit("error", e.msg, e)
            else:
                self.clear_view()
                
    
    def save(self):
        for pos in xrange(self.get_n_pages()):
            self.save_tab(pos)
            
    
    def save_tab(self, pos):
        if self._pages[pos] is not None and \
            self._pages[pos].is_valid() and \
            self._textviews[pos].is_modified():

            try:
                self._textviews[pos].save(self._pages[pos].get_data_file())
            except RichTextError, e:
                self.emit("error", e.msg, e)
                return
            
            self._pages[pos].set_modified_time()
            
            try:
                self._pages[pos].save()
            except NoteBookError, e:
                self.emit("error", e.msg, e)
    
    def save_needed(self):
        for textview in self._textviews:
            if textview.is_modified():
                return True
        return False

# add new signals to TakeNoteEditor
gobject.type_register(TakeNoteEditor)
gobject.signal_new("modified", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, bool))
gobject.signal_new("font-change", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("error", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object))
gobject.signal_new("child-activated", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, object))


class FontSelector (gtk.ComboBox):

    def __init__(self):
        gtk.ComboBox.__init__(self)

        self._list = gtk.ListStore(str)
        self.set_model(self._list)
        
        self._families = sorted(f.get_name()
                                 for f in self.get_pango_context().list_families())

        for f in self._families:
            self._list.append([f])

        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, 'text', 0)

        
    def set_family(self, family):
        
        index = self._families.index(family)
        self.set_active(index)

    def get_family(self):
        return self._families[self.get_active()]

    



class TakeNoteWindow (gtk.Window):
    """Main windows for TakeNote"""

    def __init__(self, app):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.app = app
        self.notebook = None
        self.sel_nodes = []
        self.current_page = None
        self.maximized = False
        self.iconified = False
        self.queue_list_select = []
        self.ignore_view_mode = False
        
        
        # init main window
        self.set_title(takenote.PROGRAM_NAME)
        self.set_default_size(*takenote.DEFAULT_WINDOW_SIZE)

        # main window signals
        self.connect("delete-event", lambda w,e: self.on_quit())
        self.connect("window-state-event", self.on_window_state)
        self.connect("size-allocate", self.on_window_size)
        self.app.pref.changed.add(self.on_app_options_changed)
        
        # treeview
        self.treeview = TakeNoteTreeView()
        self.treeview.connect("select-nodes", self.on_tree_select)
        self.treeview.connect("error", lambda w,t,e: self.error(t, e))
        
        # selector
        self.selector = TakeNoteSelector()
        self.selector.connect("select-nodes", self.on_list_select)
        self.selector.connect("goto-node", self.on_list_view_node)
        self.selector.connect("goto-parent-node",
                              lambda w: self.on_list_view_parent_node())
        self.selector.connect("error", lambda w,t,e: self.error(t, e))
        self.selector.on_status = self.set_status
        
        
        # editor
        self.editor = TakeNoteEditor()
        self.editor.connect("font-change", self.on_font_change)
        self.editor.connect("modified", self.on_page_editor_modified)
        self.editor.connect("error", lambda w,t,e: self.error(t, e))
        self.editor.connect("child-activated", self.on_child_activated)
        self.editor.view_pages([])


        
        #====================================
        # Dialogs
        
        self.app_options_dialog = dialog_app_options.ApplicationOptionsDialog(self)
        self.find_dialog = dialog_find.TakeNoteFindDialog(self)
        self.drag_test = dialog_drag_drop_test.DragDropTestDialog(self)
        self.image_resize_dialog = dialog_image_resize.ImageResizeDialog(self)

        # context menus
        self.make_context_menus()
        
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
                
        # create a horizontal paned widget
        self.hpaned = gtk.HPaned()
        main_vbox2.pack_start(self.hpaned, True, True, 0)
        self.hpaned.set_position(takenote.DEFAULT_HSASH_POS)
        
        # status bar
        status_hbox = gtk.HBox(False, 0)
        main_vbox.pack_start(status_hbox, False, True, 0)
        
        # message bar
        self.status_bar = gtk.Statusbar()      
        status_hbox.pack_start(self.status_bar, False, True, 0)
        self.status_bar.set_property("has-resize-grip", False)
        self.status_bar.set_size_request(300, -1)
        
        # stats bar
        self.stats_bar = gtk.Statusbar()
        status_hbox.pack_start(self.stats_bar, True, True, 0)
        

        # layout major widgets
        self.paned2 = gtk.VPaned()
        self.hpaned.add2(self.paned2)
        self.paned2.set_position(takenote.DEFAULT_VSASH_POS)
        
        # treeview and scrollbars
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.treeview)
        self.hpaned.add1(sw)
        
        # selector with scrollbars
        self.selector_sw = gtk.ScrolledWindow()
        self.selector_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.selector_sw.set_shadow_type(gtk.SHADOW_IN)
        self.selector_sw.add(self.selector)
        self.paned2.add1(self.selector_sw)
        
        # layout editor
        self.paned2.add2(self.editor)

        # load preferences
        self.get_app_preferences()
        self.set_view_mode(self.app.pref.view_mode)
        
        #self.show_all()
        self.treeview.grab_focus()


    #=========================================================
    # main window gui callbacks

    def on_window_state(self, window, event):
        """Callback for window state"""

        # keep track of maximized and minimized state
        self.maximized = event.new_window_state & \
                         gtk.gdk.WINDOW_STATE_MAXIMIZED
        self.iconified = event.new_window_state & \
                         gtk.gdk.WINDOW_STATE_ICONIFIED


    def on_window_size(self, window, event):
        """Callback for resize events"""

        # record window size if it is not maximized or minimized
        if not self.maximized and not self.iconified:
            self.app.pref.window_size = self.get_size()


    def on_app_options_changed(self):
        self.selector.set_date_formats(self.app.pref.timestamp_formats)
        
    
    #=============================================================
    # Treeview, listview, editor callbacks
    
    
    def on_tree_select(self, treeview, nodes):
        """Callback for treeview selection change"""

        self.sel_nodes = nodes
        self.selector.view_nodes(nodes)

        if len(self.queue_list_select) > 0:
            self.selector.select_nodes(self.queue_list_select)
            self.queue_list_select = []
                
        # view page
        pages = [node for node in nodes 
                 if isinstance(node, NoteBookPage)]
        
        if len(pages) > 0:
            self.selector.select_nodes(pages)
            self.current_page = pages[0]
            try:
                self.editor.view_pages(pages)

            except RichTextError, e:
                self.error("Could not load pages", e)
            
        else:
            self.editor.view_pages([])
            self.current_page = None

    
    def on_list_select(self, selector, pages):
        """Callback for listview selection change"""

        # TODO: will need to generalize to multiple pages
        
        try:
            if len(pages) > 0:
                self.current_page = pages[0]
            else:
                self.current_page = None
            self.editor.view_pages(pages)
        except RichTextError, e:
            self.error("Could not load page '%s'" % pages[0].get_title(), e)

    def on_list_view_node(self, selector, node):
        """Focus listview on a node"""
        if node is None:
            nodes = self.selector.get_selected_nodes()
            if len(nodes) == 0:
                return
            node = nodes[0]
        
        self.treeview.select_nodes([node])


    def on_list_view_parent_node(self, node=None):
        """Focus listview on a node's parent"""

        # get node
        if node is None:
            if len(self.sel_nodes) == 0:
                return
            if len(self.sel_nodes) > 1 or \
               not self.selector.is_view_tree():
                nodes = self.selector.get_selected_nodes()
                if len(nodes) == 0:
                    return
                node = nodes[0]
            else:
                node = self.sel_nodes[0]

        # get parent
        parent = node.get_parent()
        if parent is None:
            return

        # queue list select
        nodes = self.selector.get_selected_nodes()
        if len(nodes) > 0:
            self.queue_list_select = nodes
        else:
            self.queue_list_select = [node]

        # select parent
        self.treeview.select_nodes([parent])

        
    def on_page_editor_modified(self, editor, page, modified):
        if modified:
            self.set_notebook_modified(modified)


    def on_child_activated(self, editor, textview, child):
        if isinstance(child, richtext.RichTextImage):
            self.view_image(child.get_filename())
    
    
    
    #==============================================
    # Application preferences     
    
    def get_app_preferences(self):
        """Load preferences"""
        self.resize(*self.app.pref.window_size)
        self.paned2.set_position(self.app.pref.vsash_pos)
        self.hpaned.set_position(self.app.pref.hsash_pos)

        if self.app.pref.window_maximized:
            self.maximize()
    

    def set_app_preferences(self):
        """Save preferences"""
        
        self.app.pref.vsash_pos = self.paned2.get_position()
        self.app.pref.hsash_pos = self.hpaned.get_position()
        self.app.pref.window_maximized = self.maximized


        self.app.pref.write()
           
    #=============================================
    # Notebook open/save/close UI

    def on_new_notebook(self):
        """Launches New NoteBook dialog"""
        
        dialog = gtk.FileChooserDialog("New Notebook", self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE, #CREATE_FOLDER,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "New", gtk.RESPONSE_OK))
        dialog.set_current_folder(self.app.pref.new_notebook_path)
        
        response = dialog.run()

        self.app.pref.new_notebook_path = dialog.get_current_folder()
        filename = dialog.get_filename()
        dialog.destroy()
        
        if response == gtk.RESPONSE_OK:            
            self.new_notebook(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            pass

        
    
    
    def on_open_notebook(self):
        """Launches Open NoteBook dialog"""
        
        dialog = gtk.FileChooserDialog("Open Notebook", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Open", gtk.RESPONSE_OK))
        dialog.set_current_folder(self.app.pref.new_notebook_path)        

        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name("Notebook (*.nbk)")
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)
        
        response = dialog.run()

        self.app.pref.new_notebook_path = os.path.dirname(dialog.get_current_folder())
        filename = dialog.get_filename()
        dialog.destroy()

        if response == gtk.RESPONSE_OK:
            self.open_notebook(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            pass




    def on_save(self, silent=False):
        """Saves the current NoteBook"""
        if self.notebook is not None:

            try:
                self.editor.save()
                self.notebook.save()
            except Exception, e:
                if not silent:
                    self.error("Could not save notebook", e)
                    self.set_status("Error saving notebook")
                    return
            
            self.set_notebook_modified(False)

        self.set_status("Notebook saved")



    def on_archive_notebook(self):
        """Callback for archiving a notebook"""

        if self.notebook is None:
            return

        dialog = gtk.FileChooserDialog("Backup Notebook", self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Backup", gtk.RESPONSE_OK))


        filename = notebooklib.get_unique_filename(
            self.app.pref.archive_notebook_path,
            time.strftime(os.path.basename(self.notebook.get_path()) +
                          "-%Y-%m-%d"),
            ".tar.gz",
            ".")
        dialog.set_current_name(os.path.basename(filename))
        dialog.set_current_folder(self.app.pref.archive_notebook_path)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archives (*.tar.gz)")
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)
        
        response = dialog.run()

        self.app.pref.archive_notebook_path = dialog.get_current_folder()
        
        
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()

            if "." not in filename:
                filename += ".tar.gz"
            
            self.set_status("Archiving...")
            self.archive_notebook(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()


    def on_restore_notebook(self):
        """Callback for restoring a notebook from an archive"""

        dialog = gtk.FileChooserDialog("Chose Archive To Restore", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Restore", gtk.RESPONSE_OK))
        dialog.set_current_folder(self.app.pref.archive_notebook_path)        

        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archive (*.tar.gz)")
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)
        
        response = dialog.run()

        self.app.pref.archive_notebook_path = dialog.get_current_folder()
        
        if response == gtk.RESPONSE_OK:
            archive_filename = dialog.get_filename()
            dialog.destroy()
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
            return


        # choose new notebook name
        dialog = gtk.FileChooserDialog("Choose New Notebook Name", self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "New", gtk.RESPONSE_OK))
        dialog.set_current_folder(self.app.pref.archive_notebook_path)

        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name("Notebook (*.nbk)")
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.tar.gz")
        file_filter.set_name("Archives (*.tar.gz)")
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files (*.*)")
        dialog.add_filter(file_filter)
        
        response = dialog.run()

        self.app.pref.archive_notebook_path = os.path.dirname(dialog.get_current_folder())


        if response == gtk.RESPONSE_OK:
            notebook_filename = dialog.get_filename()
            dialog.destroy()

            self.set_status("Restoring...")
            self.restore_notebook(archive_filename, notebook_filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()



    def archive_notebook(self, filename):
        """Archive a notebook"""

        if self.notebook is None:
            return


        def progress(percent, filename):
            pass
            #print percent, filename
        
        try:
            self.notebook.archive(filename, progress)
        except NoteBookError, e:
            self.set_status("")
            self.error("Error while archiving notebook:\n%s" % e.msg, e)
            return

        self.set_status("Notebook archived")


    def restore_notebook(self, archive_filename, notebook_filename):

        # make sure current notebook is closed
        self.close_notebook()

        try:
            notebooklib.restore_archived_notebook(archive_filename,
                                                  notebook_filename)
            self.set_status("Notebook restored")
        except NoteBookError, e:
            self.set_status("")
            self.error("Error restoring notebook:\n%s" % e.msg, e)
            return

        # open new notebook
        self.open_notebook(notebook_filename)
            

    
    def on_quit(self):
        """Close the window and quit"""        
        self.close_notebook()
        self.set_app_preferences()
        gtk.main_quit()
        return False
    

    
    #===============================================
    # Notebook actions    
    
    def reload_notebook(self):
        """Reload the current NoteBook"""
        
        if self.notebook is None:
            self.error("Reloading only works when a notebook is open")
            return
        
        filename = self.notebook.get_path()
        self.close_notebook(False)
        self.open_notebook(filename)
        
        self.set_status("Notebook reloaded")
        
        
    
    def new_notebook(self, filename):
        """Creates and opens a new NoteBook"""
        
        if self.notebook is not None:
            self.close_notebook()
        
        try:
            notebook = takenote.NoteBook(filename)
            notebook.create()
            self.set_status("Created '%s'" % notebook.get_title())
        except NoteBookError, e:
            self.error("Could not create new notebook", e)
            self.set_status("")
            return None
        
        notebook = self.open_notebook(filename, new=True)
        self.treeview.expand_node(notebook.get_root_node())
        
        return notebook
        
        
    
    def open_notebook(self, filename, new=False):
        """Opens a new notebook"""
        
        if self.notebook is not None:
            self.close_notebook()
        
        notebook = takenote.NoteBook()
        notebook.node_changed.add(self.on_notebook_node_changed)
        
        try:
            notebook.load(filename)
        except NoteBookError, e:
            self.error("Could not load notebook '%s'" % filename, e)
            return None

        self.set_notebook(notebook)
        
        self.treeview.grab_focus()
        
        if not new:
            self.set_status("Loaded '%s'" % self.notebook.get_title())
        
        self.set_notebook_modified(False)

        # setup auto-saving
        self.begin_auto_save()
        
        return self.notebook
        
        
    def close_notebook(self, save=True):
        """Close the NoteBook"""
        
        if self.notebook is not None:
            if save:
                try:
                    self.editor.save()
                    self.notebook.save()
                except Exception, e:
                    # TODO: should ask question, like try again?
                    self.error("Could not save notebook", e)

            self.notebook.node_changed.remove(self.on_notebook_node_changed)
            
            self.set_notebook(None)
            self.set_status("Notebook closed")



    def begin_auto_save(self):
        """Begin autosave callbacks"""

        if self.app.pref.autosave:
            gobject.timeout_add(self.app.pref.autosave_time, self.auto_save)
        

    def auto_save(self):
        """Callback for autosaving"""

        # NOTE: return True to activate next timeout callback
        
        if self.notebook is not None:
            self.on_save(True)
            return self.app.pref.autosave
        else:
            return False
    

    def set_notebook(self, notebook):
        """Set the NoteBook for the window"""
        
        self.notebook = notebook
        self.editor.set_notebook(notebook)
        self.selector.set_notebook(notebook)
        self.treeview.set_notebook(notebook)


    
    #===========================================================
    # page and folder actions

    def get_selected_nodes(self, widget="focus"):
        """
        Returns (nodes, widget) where 'nodes' are a list of selected nodes
        in widget 'widget'

        Wiget can be
           selector -- nodes selected in listview
           treeview -- nodes selected in treeview
           focus    -- nodes selected in widget with focus
        """
        
        if widget == "focus":
            if self.selector.is_focus():
                widget = "selector"
            elif self.treeview.is_focus():
                widget = "treeview"
            elif self.editor.is_focus():
                widget = "selector"
            else:
                return ([], "")

        if widget == "treeview":
            nodes = self.treeview.get_selected_nodes()
        elif widget == "selector":
            nodes = self.selector.get_selected_nodes()
        else:
            raise Exception("unknown widget '%s'" % widget)

        return (nodes, widget)
        
    
    def on_new_dir(self, widget="focus"):
        """Add new folder near selected nodes"""

        if self.notebook is None:
            return

        nodes, widget = self.get_selected_nodes(widget)
        
        if len(nodes) == 1:
            parent = nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        if parent.is_page():
            parent = parent.get_parent()
        node = parent.new_dir()

        if widget == "treeview":
            self.treeview.expand_node(parent)
            self.treeview.edit_node(node)
        elif widget == "selector":
            #self.selector.view_nodes([parent])
            self.selector.expand_node(parent)
            self.selector.edit_node(node)
        elif widget == "":
            pass
        else:
            raise Exception("unknown widget '%s'" % widget)            
    
            
    
    def on_new_page(self, widget="focus"):
        """Add new page near selected nodes"""

        if self.notebook is None:
            return

        nodes, widget = self.get_selected_nodes(widget)
        
        if len(nodes) == 1:
            parent = nodes[0]
        else:
            parent = self.notebook.get_root_node()

        if parent.is_page():
            parent = parent.get_parent()
        node = parent.new_page()

        if widget == "treeview":
            self.treeview.expand_node(parent)
            self.treeview.edit_node(node)
        elif widget == "selector":
            self.selector.expand_node(parent)
            self.selector.edit_node(node)
        elif widget == "":
            pass
        else:
            raise Exception("unknown widget '%s'" % widget)       
    

    def on_empty_trash(self):
        """Empty Trash folder in NoteBook"""
        
        if self.notebook is None:
            return

        try:
            self.notebook.empty_trash()
        except NoteBookError, e:
            self.error("Could not empty trash.", e)



    def on_search_nodes(self):
        if not self.notebook:
            return

        words = [x.lower() for x in
                 self.search_box.get_text().strip().split()]
        nodes = takenote.search.search_manual(self.notebook, words)
        self.selector.view_nodes(nodes, nested=False)


    def focus_on_search_box(self):
        self.search_box.grab_focus()
    
    #=====================================================
    # Notebook callbacks
    
    def on_notebook_node_changed(self, nodes, recurse):
        self.set_notebook_modified(True)
        
    
    def set_notebook_modified(self, modified):
        if self.notebook is None:
            self.set_title(takenote.PROGRAM_NAME)
        else:
            if modified:
                self.set_title("* %s" % self.notebook.get_title())
                self.set_status("Notebook modified")
            else:
                self.set_title("%s" % self.notebook.get_title())
    
    
    #=================================================
    # view config
        
    def set_view_mode(self, mode):
        """Sets the view mode of the window
        
        modes:
            vertical
            horizontal
        """

        if self.ignore_view_mode:
            return

        self.ignore_view_mode = True
        
        self.paned2.remove(self.selector_sw)
        self.paned2.remove(self.editor)
        self.hpaned.remove(self.paned2)
        
        if mode == "vertical":
            # create a vertical paned widget
            self.paned2 = gtk.VPaned()
            self.view_mode_h_toggle.set_active(False)
            self.view_mode_v_toggle.set_active(True)
        else:
            self.paned2 = gtk.HPaned()
            self.view_mode_h_toggle.set_active(True)
            self.view_mode_v_toggle.set_active(False)            
        self.paned2.set_position(self.app.pref.vsash_pos)
        self.paned2.show()
        
        self.hpaned.add2(self.paned2)
        self.hpaned.show()
        
        self.paned2.add1(self.selector_sw)
        self.paned2.add2(self.editor)
        
        self.app.pref.view_mode = mode
        self.app.pref.write()

        self.ignore_view_mode = False
    
    #=============================================================
    # Update UI (menubar) from font under cursor
    
    def on_font_change(self, editor, font):
        
        # TODO: put these into a datastructure that we can iterate over
        # block toolbar handlers
        self.bold_button.handler_block(self.bold_id)
        self.italic_button.handler_block(self.italic_id)
        self.underline_button.handler_block(self.underline_id)
        self.fixed_width_button.handler_block(self.fixed_width_id)
        self.no_wrap_button.handler_block(self.no_wrap_id)
        self.left_button.handler_block(self.left_id)
        self.center_button.handler_block(self.center_id)
        self.right_button.handler_block(self.right_id)
        self.fill_button.handler_block(self.fill_id)
        self.font_family_combo.handler_block(self.font_family_id)
        self.font_size_button.handler_block(self.font_size_id)
        
        # update font mods
        self.bold_button.set_active(font.mods["bold"])
        self.italic_button.set_active(font.mods["italic"])
        self.underline_button.set_active(font.mods["underline"])
        self.fixed_width_button.set_active(font.family == "Monospace")
        self.no_wrap_button.set_active(font.mods["nowrap"])
        
        # update text justification
        self.left_button.set_active(font.justify == "left")
        self.center_button.set_active(font.justify == "center")
        self.right_button.set_active(font.justify == "right")
        self.fill_button.set_active(font.justify == "fill")
        
        # update font button        
        self.font_family_combo.set_family(font.family)
        self.font_size_button.set_value(font.size)
        
        # unblock toolbar handlers
        self.bold_button.handler_unblock(self.bold_id)
        self.italic_button.handler_unblock(self.italic_id)
        self.underline_button.handler_unblock(self.underline_id)
        self.fixed_width_button.handler_unblock(self.fixed_width_id)
        self.no_wrap_button.handler_unblock(self.no_wrap_id)
        self.left_button.handler_unblock(self.left_id)
        self.center_button.handler_unblock(self.center_id)
        self.right_button.handler_unblock(self.right_id) 
        self.fill_button.handler_unblock(self.fill_id)
        self.font_family_combo.handler_unblock(self.font_family_id)
        self.font_size_button.handler_unblock(self.font_size_id)


    #==================================================
    # changing font handlers

    def on_mod(self, mod, mod_button, mod_id):
        self.editor.get_textview().toggle_font_mod(mod)
        font = self.editor.get_textview().get_font()
        
        mod_button.handler_block(mod_id)
        mod_button.set_active(font.mods[mod])
        mod_button.handler_unblock(mod_id)

    def on_bold(self):
        self.on_mod("bold", self.bold_button, self.bold_id)
    
    def on_italic(self):
        self.on_mod("italic", self.italic_button, self.italic_id)
    
    def on_underline(self):
        self.on_mod("underline", self.underline_button, self.underline_id)
    
    def on_fixed_width(self, toolbar):
        self.editor.get_textview().toggle_font_family("Monospace")    
        
        if not toolbar:
            font = self.editor.get_textview().get_font()
        
            self.fixed_width_button.handler_block(self.fixed_width_id)        
            self.fixed_width_button.set_active(font.family == "Monospace")
            self.fixed_width_button.handler_unblock(self.fixed_width_id)

    def on_no_wrap(self):
        self.on_mod("nowrap", self.no_wrap_button, self.no_wrap_id)        

    def on_justify(self, justify):
        self.editor.get_textview().set_justify(justify)
        font = self.editor.get_textview().get_font()
        self.on_font_change(self.editor, font)

    def on_left_justify(self):
        self.on_justify("left")

    def on_center_justify(self):
        self.on_justify("center")

    def on_right_justify(self):
        self.on_justify("right")

    def on_fill_justify(self):
        self.on_justify("fill")    

    def on_choose_font(self):
        """Callback for opening Choose Font Dialog"""
        
        font = self.editor.get_textview().get_font()

        dialog = gtk.FontSelectionDialog("Choose Font")
        dialog.set_font_name("%s %d" % (font.family, font.size))
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            self.editor.get_textview().set_font(dialog.get_font_name())
            self.editor.get_textview().grab_focus()

        dialog.destroy()
        
    
    def on_family_set(self):
        self.editor.get_textview().set_font_family(self.font_family_combo.get_family())
        self.editor.get_textview().grab_focus()
        

    def on_font_size_change(self, size):
        self.editor.get_textview().set_font_size(size)
        self.editor.get_textview().grab_focus()
    
    def on_font_size_inc(self):
        font = self.editor.get_textview().get_font()
        font.size += 2        
        self.editor.get_textview().set_font_size(font.size)
        self.on_font_change(self.editor, font)
    
    
    def on_font_size_dec(self):
        font = self.editor.get_textview().get_font()
        if font.size > 4:
            font.size -= 2
        self.editor.get_textview().set_font_size(font.size)
        self.on_font_change(self.editor, font)

    #=================================================
    # Window manipulation

    def minimize_window(self):
        """Minimize the window (block until window is minimized"""
        
        # TODO: add timer in case minimize fails
        def on_window_state(window, event):            
            if event.new_window_state & gtk.gdk.WINDOW_STATE_ICONIFIED:
                gtk.main_quit()
        sig = self.connect("window-state-event", on_window_state)
        self.iconify()
        gtk.main()
        self.disconnect(sig)

    def restore_window(self):
        """Restore the window from minimization"""
        self.deiconify()
        self.present()
        
    #==================================================
    # Image/screenshot actions

    def on_screenshot(self):
        """Take and insert a screen shot image"""

        # do nothing if no page is selected
        if self.current_page is None:
            return

        # Minimize window
        self.minimize_window()
        
        # TODO: generalize
        try:
            if takenote.get_platform() == "windows":
                # use win32api to take screenshot
                # create temp file
                f, imgfile = tempfile.mkstemp(".bmp", "takenote")
                os.close(f)
                screenshot_win.take_screenshot(imgfile)
            else:
                # use external app for screen shot
                screenshot = self.app.pref.get_external_app("screen_shot")
                if screenshot is None:
                    self.error("You must specify a Screen Shot program in Application Options")
                    return

                # create temp file
                f, imgfile = tempfile.mkstemp(".png", "takenote")
                os.close(f)

                try:
                    proc = subprocess.Popen([screenshot.prog, imgfile])
                    if proc.wait() != 0:
                        raise OSError("Exited with error")
                except OSError, e:
                    raise e
            
        except Exception, e:        
            # catch exceptions for screenshot program
            self.restore_window()
            self.error("The screenshot program encountered an error", e)
            
        else:
            if not os.path.exists(imgfile):
                # catch error if image is not created
                self.restore_window()
                self.error("The screenshot program did not create the necessary image file '%s'" % imgfile)
            else:
                # insert image
                try:
                    self.insert_image(imgfile, "screenshot.png")
                except Exception, e:
                    # TODO: make exception more specific
                    self.restore_window()
                    self.error("Error importing screenshot '%s'" % imgfile, e)
            
        # remove temp file
        try:
            os.remove(imgfile)
        except OSError, e:
            self.restore_window()
            self.error("%s was unable to remove temp file for screenshot" %
                       takenote.PROGRAM_NAME, e)

        self.restore_window()


    def on_insert_hr(self):

        if self.current_page is None:
            return

        self.editor.get_textview().insert_hr()
        
    def on_insert_image(self):
        """Displays the Insert Image Dialog"""
        if self.current_page is None:
            return
                  
        dialog = gtk.FileChooserDialog("Insert Image From File", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Insert", gtk.RESPONSE_OK))
        dialog.set_current_folder(self.app.pref.insert_image_path)
        

        # run dialog
        response = dialog.run()


        self.app.pref.insert_image_path = dialog.get_current_folder()
        
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
                # TODO: make exception more specific
                self.error("Could not insert image '%s'" % filename, e)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
        
    
    
    def insert_image(self, filename, savename="image.png"):
        """Inserts an image into the text editor"""

        if self.current_page is None:
            return
        
        pixbuf = gdk.pixbuf_new_from_file(filename)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.editor.get_textview().insert_image(img, savename)


    #=================================================
    # Image context menu

    def on_view_image(self, menuitem):
        """View image in Image Viewer"""

        if self.current_page is None:
            return
        
        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()
        self.view_image(image_filename)
        

    def view_image(self, image_filename):
        image_path = os.path.join(self.current_page.get_path(), image_filename)
        viewer = self.app.pref.get_external_app("image_viewer")
        
        if viewer is not None:
            try:
                proc = subprocess.Popen([viewer.prog, image_path])
            except OSError, e:
                self.error("Could not open Image Viewer", e)
        else:
            self.error("You specify an Image Viewer in Application Options""")


    def on_edit_image(self, menuitem):
        """Edit image in Image Editor"""

        if self.current_page is None:
            return
        
        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()

        image_path = os.path.join(self.current_page.get_path(), image_filename)
        editor = self.app.pref.get_external_app("image_editor")
    
        if editor is not None:
            try:
                proc = subprocess.Popen([editor.prog, image_path])
            except OSError, e:
                self.error("Could not open Image Editor", e)
        else:
            self.error("You specify an Image Editor in Application Options""")


    def on_resize_image(self, menuitem):
        """Resize image"""
        
        if self.current_page is None:
            return
        
        image = menuitem.get_parent().get_child()
        self.image_resize_dialog.on_resize(image)
        


    def on_save_image_as(self, menuitem):
        """Save image as a new file"""
        
        if self.current_page is None:
            return
        
        # get image filename
        image = menuitem.get_parent().get_child()
        image_filename = menuitem.get_parent().get_child().get_filename()
        image_path = os.path.join(self.current_page.get_path(), image_filename)

        dialog = gtk.FileChooserDialog("Save Image As...", self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Save", gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_current_folder(self.app.save_image_path)
        
        response = dialog.run()

        self.app.pref.save_image_path = dialog.get_current_folder()

        if response == gtk.RESPONSE_OK:
            if dialog.get_filename() == "":
                self.error("Must specify a filename for the image.")
            else:
                try:                
                    image.write(dialog.get_filename())
                except Exception, e:
                    self.error("Could not save image '%s'" % dialog.get_filename(), e)

        dialog.destroy()
                            
        
        
                
    #=============================================
    # Goto menu options
    
    def on_goto_treeview(self):
        """Switch focus to TreeView"""
        self.treeview.grab_focus()
        
    def on_goto_listview(self):
        """Switch focus to ListView"""
        self.selector.grab_focus()
        
    def on_goto_editor(self):
        """Switch focus to Editor"""
        self.editor.get_textview().grab_focus()
    
    
    
    #=====================================================
    # Cut/copy/paste

    # NOTE: for now all copy/cut/paste is sent to textview
    
    def on_cut(self):
        """Cut callback"""
        self.editor.get_textview().emit("cut-clipboard")
    
    def on_copy(self):
        """Copy callback"""
        self.editor.get_textview().emit("copy-clipboard")
    
    def on_paste(self):
        """Paste callback"""
        self.editor.get_textview().emit("paste-clipboard")
    
    
    #=====================================================
    # External app viewers

    # TODO: combine all viewers into one function
    
    def on_view_node_file_explorer(self, node=None, widget="focus"):
        """View folder in file explorer"""
        
        if node is None:
            nodes, widget = self.get_selected_nodes(widget)
            if len(nodes) == 0:
                self.error("No notes are selected.")
                return
            node = nodes[0]
        
        try:
            filename = os.path.realpath(node.get_path())
            self.app.run_external_app("file_explorer", filename)
        except TakeNoteError, e:
            self.error(e.msg, e)


    
    def on_view_node_web_browser(self, node=None, widget="focus"):
        """View current page in web browser"""

        if node is None:
            nodes, widget = self.get_selected_nodes(widget)
            if len(nodes) == 0:
                self.error("No notes are selected.")                
                return            
            node = nodes[0]

            if not node.is_page():
                self.error("Only pages can be viewed with a web browser.")
                return

        try:
            filename = os.path.realpath(node.get_data_file())
            self.app.run_external_app("web_browser", filename)
        except TakeNoteError, e:
            self.error(e.msg, e)
    
    
    def on_view_node_text_editor(self, node=None, widget="focus"):
        """View current page in text editor"""

        if node is None:
            nodes, widget = self.get_selected_nodes(widget)
            if len(nodes) == 0:
                self.error("No notes are selected.")
                return
            node = nodes[0]

            if not node.is_page():
                self.error("Only pages can be viewed with a text editor.")
                return
           
        try:
            filename = os.path.realpath(node.get_data_file())
            self.app.run_external_app("text_editor", filename)
        except TakeNoteError, e:
            self.error(e.msg, e)


    def view_error_log(self):        
        """View error in text editor"""

        # windows locks open files
        # therefore we should copy error log before viewing it
        filename = os.path.realpath(takenote.get_user_error_log())
        filename2 = filename + ".bak"
        shutil.copy(filename, filename2)        

        # use text editor to view error log
        self.app.run_external_app("text_editor", filename2)
                                       
    
    def on_spell_check_toggle(self, num, widget):
        """Toggle spell checker"""
        
        textview = self.editor.get_textview()
        if textview is not None:
            textview.enable_spell_check(widget.get_active())
            self.spell_check_toggle.set_active(textview.is_spell_check_enabled())

   
    
    #==================================================
    # Help/about dialog
    
    def on_about(self):
        """Display about dialog"""
        
        about = gtk.AboutDialog()
        about.set_name(takenote.PROGRAM_NAME)
        about.set_version("v%s" % (takenote.PROGRAM_VERSION_TEXT) )
        about.set_copyright("Copyright Matt Rasmussen 2008")
        about.set_transient_for(self)
        about.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        about.connect("response", lambda d,r: about.destroy())
        about.show()
    
        

    #===========================================
    # Messages, warnings, errors UI/dialogs
    
    def set_status(self, text, bar="status"):
        if bar == "status":
            self.status_bar.pop(0)
            self.status_bar.push(0, text)
        elif bar == "stats":
            self.stats_bar.pop(0)
            self.stats_bar.push(0, text)
        else:
            raise Exception("unknown bar '%s'" % bar)
    
            
    
    def error(self, text, error=None):
        """Display an error message"""
        #self.set_status(text)
        
        dialog = gtk.MessageDialog(self.get_toplevel(), 
            flags= gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_ERROR, 
            buttons=gtk.BUTTONS_OK, 
            message_format=text)
        dialog.connect("response", lambda d,r: dialog.destroy())
        dialog.set_title("Error")
        dialog.show()

        if error is not None:
            sys.stderr.write(str(error)+"\n")
    
    
    #================================================
    # Menus
    
    def make_menubar(self):
        """Initialize the menu bar"""
        
        self.menu_items = (
            ("/_File",               
                None, None, 0, "<Branch>"),
            ("/File/_New Notebook",
                "", lambda w,e: self.on_new_notebook(), 0, 
                "<StockItem>", gtk.STOCK_NEW),
            ("/File/New _Page",      
                "<control>N", lambda w,e: self.on_new_page(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("note-new.png")),
            ("/File/New _Folder", 
                "<control><shift>N", lambda w,e: self.on_new_dir(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("folder-new.png")),

            #("/File/sep1", 
            #    None, None, 0, "<Separator>" ),                
            #("/File/New _Tab",
            #    "<control>T", lambda w,e: self.editor.new_tab(), 0, None),
            #("/File/C_lose Tab", 
            #    "<control>W", lambda w,e: self.editor.close_tab(), 0, None),
                
            ("/File/sep2", 
                None, None, 0, "<Separator>" ),
            ("/File/_Open Notebook",          
                "<control>O", lambda w,e: self.on_open_notebook(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("open.png")),
            ("/File/_Reload Notebook",          
                None, lambda w,e: self.reload_notebook(), 0, 
                "<StockItem>", gtk.STOCK_REVERT_TO_SAVED),
            ("/File/_Save Notebook",     
                "<control>S", lambda w,e: self.on_save(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("save.png")),
            ("/File/_Close Notebook", 
                None, lambda w, e: self.close_notebook(), 0, 
                "<StockItem>", gtk.STOCK_CLOSE),

            ("/File/sep3", 
                None, None, 0, "<Separator>" ),

            ("/File/_Backup Notebook",
             None, lambda w, e: self.on_archive_notebook(), 0,
                None),
            ("/File/R_estore Notebook",
             None, lambda w, e: self.on_restore_notebook(), 0,
                None),
            
            ("/File/sep4", 
                None, None, 0, "<Separator>" ),
            ("/File/Quit", 
                "<control>Q", lambda w,e: self.on_quit(), 0, None),

            ("/_Edit", 
                None, None, 0, "<Branch>"),
            ("/Edit/_Undo", 
                "<control>Z", lambda w,e: self.editor.get_textview().undo(), 0, 
                "<StockItem>", gtk.STOCK_UNDO),
            ("/Edit/_Redo", 
                "<control><shift>Z", lambda w,e: self.editor.get_textview().redo(), 0, 
                "<StockItem>", gtk.STOCK_REDO),
            ("/Edit/sep1", 
                None, None, 0, "<Separator>"),
            ("/Edit/Cu_t", 
                "<control>X", lambda w,e: self.on_cut(), 0, 
                "<StockItem>", gtk.STOCK_CUT), 
            ("/Edit/_Copy",     
                "<control>C", lambda w,e: self.on_copy(), 0, 
                "<StockItem>", gtk.STOCK_COPY), 
            ("/Edit/_Paste",     
                "<control>V", lambda w,e: self.on_paste(), 0, 
                "<StockItem>", gtk.STOCK_PASTE), 
            
            
            #("/Edit/sep3", 
            #    None, None, 0, "<Separator>"),
            #("/Edit/_Delete Folder",
            #    None, lambda w,e: self.on_delete_dir(), 0, 
            #    "<ImageItem>", folder_delete.get_pixbuf()),
            #("/Edit/Delete _Page",     
            #    None, lambda w,e: self.on_delete_page(), 0,
            #    "<ImageItem>", page_delete.get_pixbuf()),
            ("/Edit/sep4", 
                None, None, 0, "<Separator>"),
            ("/Edit/Insert _Horizontal Rule",
                "<control>H", lambda w,e: self.on_insert_hr(), 0, None),
            ("/Edit/Insert _Image",
                None, lambda w,e: self.on_insert_image(), 0, None),
            ("/Edit/Insert _Screenshot",
                "<control>Insert", lambda w,e: self.on_screenshot(), 0, None),

            ("/Edit/sep5", 
                None, None, 0, "<Separator>"),
            ("/Edit/Empty _Trash",
             None, lambda w,e: self.on_empty_trash(), 0,
             "<StockItem>", gtk.STOCK_DELETE),
            
            
            ("/_Search", None, None, 0, "<Branch>"),
            ("/Search/_Search All Notes",
             "<control>K", lambda w,e: self.focus_on_search_box(), 0,
             "<StockItem>", gtk.STOCK_FIND),
            ("/Search/_Find In Page",     
                "<control>F", lambda w,e: self.find_dialog.on_find(False), 0, 
                "<StockItem>", gtk.STOCK_FIND), 
            ("/Search/Find _Next In Page",     
                "<control>G", lambda w,e: self.find_dialog.on_find(False, forward=True), 0, 
                "<StockItem>", gtk.STOCK_FIND), 
            ("/Search/Find Pre_vious In Page",     
                "<control><shift>G", lambda w,e: self.find_dialog.on_find(False, forward=False), 0, 
                "<StockItem>", gtk.STOCK_FIND),                 
            ("/Search/_Replace In Page",     
                "<control><shift>R", lambda w,e: self.find_dialog.on_find(True), 0, 
                "<StockItem>", gtk.STOCK_FIND), 
                
            
            ("/_Format", 
                None, None, 0, "<Branch>"),
            ("/Format/_Left Align", 
                "<control>L", lambda w,e: self.on_left_justify(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("alignleft.png")),
            ("/Format/C_enter Align", 
                "<control>E", lambda w,e: self.on_center_justify(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("aligncenter.png")),
            ("/Format/_Right Align", 
                "<control>R", lambda w,e: self.on_right_justify(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("alignright.png")),
            ("/Format/_Justify Align", 
                "<control>J", lambda w,e: self.on_fill_justify(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("alignjustify.png")),
            
            ("/Format/sep1", 
                None, None, 0, "<Separator>" ),            
            ("/Format/_Bold", 
                "<control>B", lambda w,e: self.on_bold(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("bold.png")),
            ("/Format/_Italic", 
                "<control>I", lambda w,e: self.on_italic(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("italic.png")),
            ("/Format/_Underline", 
                "<control>U", lambda w,e: self.on_underline(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("underline.png")),
            ("/Format/_Monospace",
                "<control>M", lambda w,e: self.on_fixed_width(False), 0,
                "<ImageItem>",
                get_resource_pixbuf("fixed-width.png")),
            ("/Format/No _Wrapping",
                None, lambda w, e: self.on_no_wrap(), 0,
                "<ImageItem>",
                get_resource_pixbuf("no-wrap.png")),
            
            ("/Format/sep4", 
                None, None, 0, "<Separator>" ),
            ("/Format/Increase Font _Size", 
                "<control>equal", lambda w, e: self.on_font_size_inc(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("font-inc.png")),
            ("/Format/_Decrease Font Size", 
                "<control>minus", lambda w, e: self.on_font_size_dec(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("font-dec.png")),
            
            ("/Format/sep5", 
                None, None, 0, "<Separator>" ),
            ("/Format/Choose _Font", 
                "<control><shift>F", lambda w, e: self.on_choose_font(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("font.png")),

            
            ("/_View", None, None, 0, "<Branch>"),
            ("/View/View Note in File Explorer",
                None, lambda w,e: self.on_view_node_file_explorer(), 0, 
                "<ImageItem>",
                get_resource_pixbuf("note.png")),
            ("/View/View Note in Text Editor",
                None, lambda w,e: self.on_view_node_text_editor(), 0, 
                "<ImageItem>",
                get_resource_pixbuf("note.png")),
            ("/View/View Note in Web Browser",
                None, lambda w,e: self.on_view_node_web_browser(), 0, 
                "<ImageItem>",
                get_resource_pixbuf("note.png")),
                
            
            ("/_Go", None, None, 0, "<Branch>"),
            ("/_Go/Go to _Note",
                None, lambda w,e: self.on_list_view_node(None, None), 0,
                "<StockItem>", gtk.STOCK_GO_DOWN),
            ("/_Go/Go to _Parent Note",
                None, lambda w,e: self.on_list_view_parent_node(), 0,
                "<StockItem>", gtk.STOCK_GO_UP),            

            ("/Go/sep1", None, None, 0, "<Separator>"),

            ("/Go/Go to _Tree View",
                "<control>T", lambda w,e: self.on_goto_treeview(), 0, None),
            ("/Go/Go to _List View",
                "<control>Y", lambda w,e: self.on_goto_listview(), 0, None),
            ("/Go/Go to _Editor",
                "<control>D", lambda w,e: self.on_goto_editor(), 0, None),
            
            ("/_Options", None, None, 0, "<Branch>"),
            ("/Options/_Spell check", 
                None, self.on_spell_check_toggle, 0,
                "<ToggleItem>"),
                
            ("/Options/sep1", None, None, 0, "<Separator>"),
            ("/Options/_Horizontal Layout",
                None, lambda w,e: self.set_view_mode("horizontal"), 0, 
                "<ToggleItem>"),
            ("/Options/_Vertical Layout",
                None, lambda w,e: self.set_view_mode("vertical"), 0, 
                "<ToggleItem>"),
                
            ("/Options/sep1", None, None, 0, "<Separator>"),
            ("/Options/_TakeNote Options",
                None, lambda w,e: self.app_options_dialog.on_app_options(), 0, 
                "<StockItem>", gtk.STOCK_PREFERENCES),
            
            ("/_Help",       None, None, 0, "<LastBranch>" ),
            ("/Help/View Error Log...",
             None, lambda w,e: self.view_error_log(), 0, None),
            ("/Help/Drap and Drop Test...",
                None, lambda w,e: self.drag_test.on_drag_and_drop_test(), 0, None),
            ("/Help/sep1", None, None, 0, "<Separator>"),
            ("/Help/About", None, lambda w,e: self.on_about(), 0, None ),
            )    
    
        accel_group = gtk.AccelGroup()

        # Create item factory
        self.item_factory = gtk.ItemFactory(gtk.MenuBar, "<main>", accel_group)
        self.item_factory.create_items(self.menu_items)
        self.add_accel_group(accel_group)

        # view mode
        self.view_mode_h_toggle = self.item_factory.get_widget("/Options/Horizontal Layout")
        self.view_mode_v_toggle = self.item_factory.get_widget("/Options/Vertical Layout")

        # get spell check toggle
        self.spell_check_toggle = self.item_factory.get_widget("/Options/Spell check")
        self.spell_check_toggle.set_active(self.editor.get_textview()\
                                           .is_spell_check_enabled())
        self.spell_check_toggle.set_sensitive(self.editor.get_textview()\
                                              .can_spell_check())
        
        
        return self.item_factory.get_widget("<main>")


    
    def make_toolbar(self):
        
        toolbar = gtk.Toolbar()
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_property("icon-size", gtk.ICON_SIZE_SMALL_TOOLBAR)
        toolbar.set_border_width(0)
        
        tips = gtk.Tooltips()
        tips.enable()

        # open notebook
        button = gtk.ToolButton()
        button.set_icon_widget(get_resource_image("open.png"))
        tips.set_tip(button, "Open Notebook")
        button.connect("clicked", lambda w: self.on_open_notebook())
        toolbar.insert(button, -1)

        # save notebook
        button = gtk.ToolButton()
        button.set_icon_widget(get_resource_image("save.png"))
        tips.set_tip(button, "Save Notebook")
        button.connect("clicked", lambda w: self.on_save())
        toolbar.insert(button, -1)        

        # separator
        toolbar.insert(gtk.SeparatorToolItem(), -1)        

        # goto note
        button = gtk.ToolButton()
        button.set_stock_id(gtk.STOCK_GO_DOWN)
        tips.set_tip(button, "Go to Note")
        button.connect("clicked", lambda w: self.on_list_view_node(None, None))
        toolbar.insert(button, -1)        
        
        # goto parent node
        button = gtk.ToolButton()
        button.set_stock_id(gtk.STOCK_GO_UP)
        tips.set_tip(button, "Go to Parent Note")
        button.connect("clicked", lambda w: self.on_list_view_parent_node())
        toolbar.insert(button, -1)        


        # separator
        toolbar.insert(gtk.SeparatorToolItem(), -1)        
        
        
        # new folder
        button = gtk.ToolButton()
        button.set_icon_widget(get_resource_image("folder-new.png"))
        tips.set_tip(button, "New Folder")
        button.connect("clicked", lambda w: self.on_new_dir())
        toolbar.insert(button, -1)
        
        # folder delete
        #button = gtk.ToolButton()
        #button.set_icon_widget(get_resource_image("folder-delete.png"))
        #tips.set_tip(button, "Delete Folder")
        #button.connect("clicked", lambda w: self.on_delete_dir())
        #toolbar.insert(button, -1)

        # new note
        button = gtk.ToolButton()
        button.set_icon_widget(get_resource_image("note-new.png"))
        tips.set_tip(button, "New Note")
        button.connect("clicked", lambda w: self.on_new_page())
        toolbar.insert(button, -1)
        
        # note delete
        #button = gtk.ToolButton()
        #button.set_icon_widget(get_resource_image("note-delete.png"))
        #tips.set_tip(button, "Delete Note")
        #button.connect("clicked", lambda w: self.on_delete_page())
        #toolbar.insert(button, -1)


        # separator
        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        
        # bold tool
        self.bold_button = gtk.ToggleToolButton()
        self.bold_button.set_icon_widget(get_resource_image("bold.png"))
        tips.set_tip(self.bold_button, "Bold")
        self.bold_id = self.bold_button.connect("toggled", lambda w: self.editor.get_textview().toggle_font_mod("bold"))
        toolbar.insert(self.bold_button, -1)


        # italic tool
        self.italic_button = gtk.ToggleToolButton()
        self.italic_button.set_icon_widget(get_resource_image("italic.png"))
        tips.set_tip(self.italic_button, "Italic")
        self.italic_id = self.italic_button.connect("toggled", lambda w: self.editor.get_textview().toggle_font_mod("italic"))
        toolbar.insert(self.italic_button, -1)

        # underline tool
        self.underline_button = gtk.ToggleToolButton()
        self.underline_button.set_icon_widget(get_resource_image("underline.png"))
        tips.set_tip(self.underline_button, "Underline")
        self.underline_id = self.underline_button.connect("toggled", lambda w: self.editor.get_textview().toggle_font_mod("underline"))
        toolbar.insert(self.underline_button, -1)
        
        # fixed-width tool
        self.fixed_width_button = gtk.ToggleToolButton()
        self.fixed_width_button.set_icon_widget(get_resource_image("fixed-width.png"))
        tips.set_tip(self.fixed_width_button, "Monospace")
        self.fixed_width_id = self.fixed_width_button.connect("toggled", lambda w: self.on_fixed_width(True))
        toolbar.insert(self.fixed_width_button, -1)

        # no wrap tool
        self.no_wrap_button = gtk.ToggleToolButton()
        self.no_wrap_button.set_icon_widget(get_resource_image("no-wrap.png"))
        tips.set_tip(self.no_wrap_button, "No Wrapping")
        self.no_wrap_id = self.no_wrap_button.connect("toggled", lambda w: self.editor.get_textview().toggle_font_mod("nowrap"))
        toolbar.insert(self.no_wrap_button, -1)


        # font button
        #self.font_sel = gtk.FontButton()
        #self.font_sel.set_use_font(True)
        #self.font_sel.set_show_size(False)
        #item = gtk.ToolItem()
        #item.add(self.font_sel)
        #tips.set_tip(item, "Set Font")
        #toolbar.insert(item, -1)
        #self.font_sel.connect("font-set", lambda w: self.on_font_set())

        # family combo
        DEFAULT_FONT_FAMILY = "Sans"
        self.font_family_combo = FontSelector()
        self.font_family_combo.set_size_request(150, -1)
        item = gtk.ToolItem()
        item.add(self.font_family_combo)
        tips.set_tip(item, "Font Family")
        toolbar.insert(item, -1)
        self.font_family_id = self.font_family_combo.connect("changed", lambda w: self.on_family_set())
        self.font_family_combo.set_family(DEFAULT_FONT_FAMILY)
                
        # font size
        DEFAULT_FONT_SIZE = 10
        self.font_size_button = gtk.SpinButton(
          gtk.Adjustment(value=DEFAULT_FONT_SIZE, lower=2, upper=500, 
                         step_incr=1, page_incr=2, page_size=2))
        #self.font_size_button.set_range(2, 100)
        self.font_size_button.set_value(DEFAULT_FONT_SIZE)
        self.font_size_button.set_editable(False)
        item = gtk.ToolItem()
        item.add(self.font_size_button)
        tips.set_tip(item, "Font Size")
        toolbar.insert(item, -1)
        self.font_size_id = self.font_size_button.connect("value-changed",
            lambda w: 
            self.on_font_size_change(self.font_size_button.get_value()))


        # font size increase
        #button = gtk.ToolButton()
        #button.set_icon_widget(get_resource_image("font-inc.png"))
        #tips.set_tip(button, "Increase Font Size")
        #button.connect("clicked", lambda w: self.on_font_size_inc())
        #toolbar.insert(button, -1)        

        # font size decrease
        #button = gtk.ToolButton()
        #button.set_icon_widget(get_resource_image("font-dec.png"))
        #tips.set_tip(button, "Decrease Font Size")
        #button.connect("clicked", lambda w: self.on_font_size_dec())
        #toolbar.insert(button, -1)        
                
        
        # separator
        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
                
        # left tool
        self.left_button = gtk.ToggleToolButton()
        self.left_button.set_icon_widget(get_resource_image("alignleft.png"))
        tips.set_tip(self.left_button, "Left Align")
        self.left_id = self.left_button.connect("toggled", lambda w: self.on_left_justify())
        toolbar.insert(self.left_button, -1)
        
        # center tool
        self.center_button = gtk.ToggleToolButton()
        self.center_button.set_icon_widget(get_resource_image("aligncenter.png"))
        tips.set_tip(self.center_button, "Center Align")
        self.center_id = self.center_button.connect("toggled", lambda w: self.on_center_justify())
        toolbar.insert(self.center_button, -1)
        
        # right tool
        self.right_button = gtk.ToggleToolButton()
        self.right_button.set_icon_widget(get_resource_image("alignright.png"))
        tips.set_tip(self.right_button, "Right Align")
        self.right_id = self.right_button.connect("toggled", lambda w: self.on_right_justify())
        toolbar.insert(self.right_button, -1)
        
        # justify tool
        self.fill_button = gtk.ToggleToolButton()
        self.fill_button.set_icon_widget(get_resource_image("alignjustify.png"))
        tips.set_tip(self.fill_button, "Justify Align")
        self.fill_id = self.fill_button.connect("toggled", lambda w: self.on_fill_justify())
        toolbar.insert(self.fill_button, -1)


        # separator
        spacer = gtk.SeparatorToolItem()
        spacer.set_draw(False)
        spacer.set_expand(True)
        toolbar.insert(spacer, -1)


        # search box
        item = gtk.ToolItem()
        self.search_box = gtk.Entry()
        #self.search_box.set_max_chars(30)
        self.search_box.connect("activate",
                                lambda w: self.on_search_nodes())
        item.add(self.search_box)
        toolbar.insert(item, -1)

        # search button
        self.search_button = gtk.ToolButton()
        self.search_button.set_stock_id(gtk.STOCK_FIND)
        tips.set_tip(self.search_button, "Search Notes")
        self.search_button.connect("clicked",
                                   lambda w: self.on_search_nodes())
        toolbar.insert(self.search_button, -1)
        
                
        return toolbar



    def make_context_menus(self):
        """Initialize context menus"""

        #==========================
        # image context menu
        item = gtk.SeparatorMenuItem()
        item.show()
        self.editor.get_textview().get_image_menu().append(item)
            
        # image/edit
        item = gtk.MenuItem("View Image...")
        item.connect("activate", self.on_view_image)
        item.show()
        self.editor.get_textview().get_image_menu().append(item)
        
        item = gtk.MenuItem("Edit Image...")
        item.connect("activate", self.on_edit_image)
        item.show()
        self.editor.get_textview().get_image_menu().append(item)

        item = gtk.MenuItem("Resize Image...")
        item.connect("activate", self.on_resize_image)
        item.show()
        self.editor.get_textview().get_image_menu().append(item)

        # image/save
        item = gtk.ImageMenuItem("Save Image As...")
        item.connect("activate", self.on_save_image_as)
        item.show()
        self.editor.get_textview().get_image_menu().append(item)

        #===============================
        # treeview context menu
        # treeview/new folder
        item = gtk.ImageMenuItem()        
        item.set_image(get_resource_image("folder-new.png"))
        label = gtk.Label("New _Folder")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)
        item.connect("activate", lambda w: self.on_new_dir("treeview"))
        self.treeview.menu.append(item)
        item.show()
        
        # treeview/new page
        item = gtk.ImageMenuItem()
        item.set_image(get_resource_image("note-new.png"))        
        label = gtk.Label("New _Page")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)        
        item.connect("activate", lambda w: self.on_new_page("treeview"))
        self.treeview.menu.append(item)
        item.show()

        # treeview/delete node
        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        item.connect("activate", lambda w: self.treeview.on_delete_node())
        self.treeview.menu.append(item)
        item.show()

        item = gtk.SeparatorMenuItem()
        self.treeview.menu.append(item)
        item.show()


        # treeview/file explorer
        item = gtk.MenuItem("View in File Explorer")
        item.connect("activate",
                     lambda w: self.on_view_node_file_explorer(None,
                                                               "treeview"))
        self.treeview.menu.append(item)
        item.show()        

        # treeview/web browser
        item = gtk.MenuItem("View in Web Browser")
        item.connect("activate",
                     lambda w: self.on_view_node_web_browser(None,
                                                             "treeview"))
        self.treeview.menu.append(item)
        item.show()        

        # treeview/text editor
        item = gtk.MenuItem("View in Text Editor")
        item.connect("activate",
                     lambda w: self.on_view_node_text_editor(None,
                                                             "treeview"))
        self.treeview.menu.append(item)
        item.show()

        
        #=================================
        # listview (note selector) context menu

        # selector/view note
        item = gtk.ImageMenuItem(gtk.STOCK_GO_DOWN)
        item.child.set_label("Go to _Note")
        item.connect("activate",
                     lambda w: self.on_list_view_node(None, None))
        self.selector.menu.append(item)
        item.show()

        # selector/view note
        item = gtk.ImageMenuItem(gtk.STOCK_GO_UP)
        item.child.set_label("Go to _Parent Note")
        item.connect("activate",
                     lambda w: self.on_list_view_parent_node())
        self.selector.menu.append(item)
        item.show()

        item = gtk.SeparatorMenuItem()
        self.selector.menu.append(item)
        item.show()

        # selector/new folder
        item = gtk.ImageMenuItem()
        item.set_image(get_resource_image("folder-new.png"))
        label = gtk.Label("New _Folder")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)
        item.connect("activate", lambda w: self.on_new_dir("selector"))
        self.selector.menu.append(item)
        item.show()
        
        # treeview/new page
        item = gtk.ImageMenuItem()
        item.set_image(get_resource_image("note-new.png"))        
        label = gtk.Label("New _Page")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)        
        item.connect("activate", lambda w: self.on_new_page("selector"))
        self.selector.menu.append(item)
        item.show()

        # selector/delete node
        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        item.connect("activate", lambda w: self.selector.on_delete_page())
        self.selector.menu.append(item)
        item.show()

        item = gtk.SeparatorMenuItem()
        item.show()
        self.selector.menu.append(item)
        
        # selector/file explorer
        item = gtk.MenuItem("View in File _Explorer")
        item.connect("activate",
                     lambda w: self.on_view_node_file_explorer(None,
                                                               "selector"))
        self.selector.menu.append(item)
        item.show()

        # treeview/web browser
        item = gtk.MenuItem("View in _Web Browser")
        item.connect("activate",
                     lambda w: self.on_view_node_web_browser(None,
                                                             "selector"))
        self.selector.menu.append(item)
        item.show()        

        # treeview/text editor
        item = gtk.MenuItem("View in _Text Editor")
        item.connect("activate",
                     lambda w: self.on_view_node_text_editor(None,
                                                             "selector"))
        self.selector.menu.append(item)
        item.show()        





