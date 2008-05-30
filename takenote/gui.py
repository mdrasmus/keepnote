"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for TakeNote Application
"""



# python imports
import sys, os, tempfile, re, subprocess, shlex, shutil

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# takenote imports
import takenote
from takenote import get_resource, get_resource_image, get_resource_pixbuf
from takenote.notebook import NoteBookError, NoteBookDir, NoteBookPage
from takenote.richtext import RichTextView, RichTextImage, RichTextError
from takenote.treeview import TakeNoteTreeView
from takenote.noteselector import TakeNoteSelector
from takenote import screenshot_win
import takenote.dialog_app_options
import takenote.dialog_find
import takenote.dialog_drag_drop_test
import takenote.dialog_image_resize

# constants
PROGRAM_NAME = "TakeNote"
PROGRAM_VERSION = "0.4"



def quote_filename(filename):
    if " " in filename:
        filename.replace("\\", "\\\\")
        filename.replace('"', '\"')
        filename = '"%s"' % filename
    return filename


class TakeNoteEditor (gtk.VBox): #(gtk.Notebook):

    def __init__(self):
        #gtk.Notebook.__init__(self)
        gtk.VBox.__init__(self, False, 0)
        #self.set_scrollable(True)
        
        # TODO: may need to update fonts on page change
        # TODO: add page reorder
        # TODO: add close button on labels
        
        # state
        self._textviews = []
        self._pages = []
        
        self.new_tab()
        self.show()

    
    def on_font_callback(self, textview, mods, justify, family, size):
        self.emit("font-change", mods, justify, family, size)
    
    def on_modified_callback(self, page_num, modified):
        self.emit("modified", self._pages[page_num], modified)
    
    #def on_error_callback(self, widget, text, error):
    #    self.emit("error", text, error)
        
    
    def get_textview(self):
        #pos = self.get_current_page()
        pos = 0
        
        if pos == -1:
            return None
        else:    
            return self._textviews[pos]
    
    
    def new_tab(self):
        self._textviews.append(RichTextView())
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
            pos = self.get_current_page()
        
        self.save_tab(pos)

        del self._pages[pos]
        del self._textviews[pos]
        self.remove_page(pos)
    '''
    
    def get_n_pages(self):
        return 1
    
    def get_current_page(self):
        return 0
        
    def view_pages(self, pages):
        # TODO: generalize to multiple pages
        self.save()
        
        if len(pages) == 0:
            if self.get_n_pages() > 0:
                pos = self.get_current_page()
                self._pages[pos] = None
                self._textviews[pos].disable()
        else:
            if self.get_n_pages() == 0:
                self.new_tab()
            
            pos = self.get_current_page()
            self._pages[pos] = pages[0]
            self._textviews[pos].enable()
            #self.set_tab_label_text(self.get_children()[pos], 
            #                        self._pages[pos].get_title())

            
            try:
                self._textviews[pos].load(self._pages[pos].get_data_file())
            except RichTextError, e:
                self._textviews[pos].disable()
                self._pages[pos] = None
                
                self.emit("error", e.msg, e)
                
    
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
    gobject.TYPE_NONE, (object, str, str, int))
gobject.signal_new("error", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object))




class TakeNoteWindow (gtk.Window):
    """Main windows for TakeNote"""

    def __init__(self, app=""):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.app = app
        
        self.set_title("TakeNote")
        self.set_default_size(*takenote.DEFAULT_WINDOW_SIZE)
        self.connect("delete-event", lambda w,e: self.on_quit())
        
        self.notebook = None
        self.sel_nodes = []
        self.current_page = None

        # treeview
        self.treeview = TakeNoteTreeView()
        self.treeview.connect("select-nodes", self.on_select_treenode)
        #self.treeview.connect("node-modified", self.on_treeview_modified)
        self.treeview.connect("error", lambda w,t,e: self.error(t, e))
        
        # selector
        self.selector = TakeNoteSelector()
        self.selector.connect("select-nodes", self.on_select_pages)
        #self.selector.connect("node-modified", self.on_selector_modified)
        self.selector.connect("error", lambda w,t,e: self.error(t, e))
        self.selector.on_status = self.set_status
        
        
        # editor
        self.editor = TakeNoteEditor()
        self.editor.connect("font-change", self.on_font_change)
        self.editor.connect("modified", self.on_page_editor_modified)
        self.editor.connect("error", lambda w,t,e: self.error(t, e))  
        self.editor.view_pages([])


        
        #====================================
        # Dialogs
        
        self.app_options_dialog = takenote.dialog_app_options.ApplicationOptionsDialog(self)
        self.find_dialog = takenote.dialog_find.TakeNoteFindDialog(self)
        self.drag_test = takenote.dialog_drag_drop_test.DragDropTestDialog(self)
        self.image_resize_dialog = takenote.dialog_image_resize.ImageResizeDialog(self)

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
        if self.app.pref.view_mode == "vertical":
            # create a vertical paned widget
            self.paned2 = gtk.VPaned()
        else:
            self.paned2 = gtk.HPaned()
        
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
        
        
        self.show_all()        
        self.treeview.grab_focus()
            
    
    #=============================================================
    # Treeview and listview callbacks
    
    
    def on_select_treenode(self, treeview, nodes):
        self.sel_nodes = nodes
        self.selector.view_nodes(nodes)
        
        # view page
        pages = [node for node in nodes 
                 if isinstance(node, NoteBookPage)]
        
        if len(pages) > 0:
            self.current_page = pages[0]
            try:
                self.editor.view_pages(pages)
            except RichTextError, e:
                self.error("Could not load pages", e)
            
        else:
            self.editor.view_pages([])
            self.current_page = None
        

    
    def on_select_pages(self, selector, pages):

        # TODO: will need to generalize of multiple pages
        
        try:
            if len(pages) > 0:
                self.current_page = pages[0]
            else:
                self.current_page = None
            self.editor.view_pages(pages)
        except RichTextError, e:
            self.error("Could not load page '%s'" % pages[0].get_title(), e)
        
    def on_page_editor_modified(self, editor, page, modified):
        if page and not modified:
            self.treeview.update_node(page)
            self.selector.update_node(page)
        
        if modified:
            self.set_notebook_modified(modified)
    
    
    #==============================================
    # Notebook preferences     
    
    def get_preferences(self):
        if self.notebook is not None:
            self.resize(*self.notebook.pref.window_size)
            self.paned2.set_position(self.notebook.pref.vsash_pos)
            self.hpaned.set_position(self.notebook.pref.hsash_pos)
    

    def set_preferences(self):
        if self.notebook is not None:
            self.notebook.pref.window_size = self.get_size()
            self.notebook.pref.vsash_pos = self.paned2.get_position()
            self.notebook.pref.hsash_pos = self.hpaned.get_position()
           
    #=============================================
    # Notebook open/save/close UI         

    def on_new_notebook(self):
        """Launches New NoteBook dialog"""
        
        dialog = gtk.FileChooserDialog("New Notebook", self, 
            action=gtk.FILE_CHOOSER_ACTION_CREATE_FOLDER,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "New", gtk.RESPONSE_OK))
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()
            os.rmdir(filename)
            self.new_notebook(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
    
    
    def on_open_notebook(self):
        """Launches Open NoteBook dialog"""
        
        dialog = gtk.FileChooserDialog("Open Notebook", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Open", gtk.RESPONSE_OK))
        #self.filew.connect("response", self.on_open_notebook_response)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name("Notebook")
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files")
        dialog.add_filter(file_filter)
        
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()
            self.open_notebook(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()


    def on_save(self):
        """Saves the current NoteBook"""
        if self.notebook is not None:
            needed = self.notebook.save_needed() or \
                     self.editor.save_needed()
            
            self.notebook.save()
            
            try:
                self.editor.save()
            except RichTextError, e:
                self.error("Could not save opened page", e)
            
            if needed:
                self.set_status("Notebook saved")
            
            self.set_notebook_modified(False)
    
    
    def on_quit(self):
        """Close the window and quit"""        
        self.close_notebook()
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
            self.error("Could not load notebook '%s'" % filename)
            return None

        self.notebook = notebook
        self.selector.set_notebook(self.notebook)
        self.treeview.set_notebook(self.notebook)
        self.get_preferences()
        
        self.treeview.grab_focus()
        
        if not new:
            self.set_status("Loaded '%s'" % self.notebook.get_title())
        
        self.set_notebook_modified(False)
        
        return self.notebook
        
        
    def close_notebook(self, save=True):
        """Close the NoteBook"""
        
        if self.notebook is not None:
            if save:
                try:
                    self.editor.save()
                except RichTextError, e:
                    # TODO: should ask question, like try again?
                    self.error("Could not save opened page", e)
                    
                self.set_preferences()
                self.notebook.save()
            self.notebook.node_changed.remove(self.on_notebook_node_changed)
            
            self.notebook = None
            self.selector.set_notebook(self.notebook)
            self.treeview.set_notebook(self.notebook)
            
            self.set_status("Notebook closed")
    
    
    
    #===========================================================
    # page and folder actions
    
    def on_new_dir(self):
        """Add new folder near selected nodes"""
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        if parent.is_page():
            parent = parent.get_parent()
        
        node = parent.new_dir()
        self.treeview.expand_node(parent)
        self.treeview.edit_node(node)
    
            
    
    def on_new_page(self):
        """Add new page near selected nodes"""
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        if parent.is_page():
            parent = parent.get_parent()
        
        node = parent.new_page()
        self.selector.view_nodes([parent])
        self.selector.edit_node(node)

    
    def on_delete_dir(self):
        """Delete node selected in TreeView"""
        
        # TODO: do delete yourself and update views
        # I need treeview.on_notebook_changed
    
        self.treeview.on_delete_node()
    
    
    def on_delete_page(self):
        """Delete node selected in ListView"""
        
        # TODO: do delete yourself and update view
        self.selector.on_delete_page()
    
    
    
    
    #=====================================================
    # Notebook callbacks
    
    def on_notebook_node_changed(self, node, recurse):
        self.set_notebook_modified(True)
        
    
    def set_notebook_modified(self, modified):
        if self.notebook is None:
            self.set_title("TakeNote")
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
        
        self.paned2.remove(self.selector_sw)
        self.paned2.remove(self.editor)
        self.hpaned.remove(self.paned2)
        
        if mode == "vertical":
            # create a vertical paned widget
            self.paned2 = gtk.VPaned()
        else:
            self.paned2 = gtk.HPaned()
        self.paned2.set_position(self.notebook.pref.vsash_pos)
        self.paned2.show()
        
        self.hpaned.add2(self.paned2)
        self.hpaned.show()
        
        self.paned2.add1(self.selector_sw)
        self.paned2.add2(self.editor)
        
        self.app.pref.view_mode = mode
        self.app.pref.write()
    
    #=============================================================
    # Update UI (menubar) from font under cursor
    
    def on_font_change(self, editor, mods, justify, family, size):
        
        # block toolbar handlers
        self.bold_button.handler_block(self.bold_id)
        self.italic_button.handler_block(self.italic_id)
        self.underline_button.handler_block(self.underline_id)
        self.fixed_width_button.handler_block(self.fixed_width_id)
        self.left_button.handler_block(self.left_id)
        self.center_button.handler_block(self.center_id)
        self.right_button.handler_block(self.right_id)
        self.fill_button.handler_block(self.fill_id)
        
        # update font mods
        self.bold_button.set_active(mods["bold"])
        self.italic_button.set_active(mods["italic"])        
        self.underline_button.set_active(mods["underline"])
        self.fixed_width_button.set_active(family == "Monospace")
        
        # update text justification
        self.left_button.set_active(justify == "left")
        self.center_button.set_active(justify == "center")
        self.right_button.set_active(justify == "right")
        self.fill_button.set_active(justify == "fill")
        
        # update font button
        self.font_sel.set_font_name("%s %d" % (family, size))
        #self.font_sel.set_font_size(size)
        
        # unblock toolbar handlers
        self.bold_button.handler_unblock(self.bold_id)
        self.italic_button.handler_block(self.italic_id)
        self.underline_button.handler_unblock(self.underline_id)
        self.fixed_width_button.handler_unblock(self.fixed_width_id)
        self.left_button.handler_unblock(self.left_id)
        self.center_button.handler_unblock(self.center_id)
        self.right_button.handler_unblock(self.right_id) 
        self.fill_button.handler_unblock(self.fill_id)


    #==================================================
    # changing font handlers

    def on_bold(self):
        self.editor.get_textview().on_bold()
        mods, justify, family, size = self.editor.get_textview().get_font()
        
        self.bold_button.handler_block(self.bold_id)
        self.bold_button.set_active(mods["bold"])
        self.bold_button.handler_unblock(self.bold_id)
    
    
    def on_italic(self):
        self.editor.get_textview().on_italic()
        mods, justify, family, size = self.editor.get_textview().get_font()
        
        self.italic_button.handler_block(self.italic_id)
        self.italic_button.set_active(mods["italic"])
        self.italic_button.handler_block(self.italic_id)
    
    
    def on_underline(self):
        self.editor.get_textview().on_underline()
        mods, justify, family, size = self.editor.get_textview().get_font()
        
        self.underline_button.handler_block(self.underline_id)        
        self.underline_button.set_active(mods["underline"])
        self.underline_button.handler_unblock(self.underline_id)
    
    def on_fixed_width(self, toolbar):
        self.editor.get_textview().on_font_family_toggle("Monospace")    
        
        if not toolbar:
            mods, justify, family, size = self.editor.get_textview().get_font()
        
            self.fixed_width_button.handler_block(self.fixed_width_id)        
            self.fixed_width_button.set_active(family == "Monospace")
            self.fixed_width_button.handler_unblock(self.fixed_width_id)

    def on_left_justify(self):
        self.editor.get_textview().on_left_justify()
        mods, justify, family, size = self.editor.get_textview().get_font()
        self.on_font_change(mods, justify, family, size)

    def on_center_justify(self):
        self.editor.get_textview().on_center_justify()
        mods, justify, family, size = self.editor.get_textview().get_font()
        self.on_font_change(mods, justify, family, size)

    def on_right_justify(self):
        self.editor.get_textview().on_right_justify()
        mods, justify, family, size = self.editor.get_textview().get_font()
        self.on_font_change(mods, justify, family, size)

    def on_fill_justify(self):
        self.editor.get_textview().on_fill_justify()
        mods, justify, family, size = self.editor.get_textview().get_font()
        self.on_font_change(mods, justify, family, size)
    
    

    def on_choose_font(self):
        self.font_sel.clicked()
    
    
    def on_font_set(self):
        self.editor.get_textview().on_font_set(self.font_sel)
        self.editor.get_textview().grab_focus()
    
    def on_font_size_inc(self):
        mods, justify, family, size = self.editor.get_textview().get_font()
        size += 2        
        self.editor.get_textview().on_font_size_set(size)
        self.on_font_change(mods, justify, family, size)
    
    
    def on_font_size_dec(self):
        mods, justify, family, size = self.editor.get_textview().get_font()
        if size > 4:
            size -= 2
        self.editor.get_textview().on_font_size_set(size)
        self.on_font_change(mods, justify, family, size)

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
            self.error("TakeNote was unable to remove temp file for screenshot", e)

        self.restore_window()


                    
        
    def on_insert_image(self):
        """Displays the Insert Image Dialog"""
        if self.current_page is None:
            return
                  
        dialog = gtk.FileChooserDialog("Insert Image From File", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Insert", gtk.RESPONSE_OK))

        # run dialog
        response = dialog.run()

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
        response = dialog.run()
        

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
    
    def on_view_folder_file_explorer(self):
        """View folder in file explorer"""
        explorer = self.app.pref.get_external_app("file_explorer")
    
        if len(self.sel_nodes) > 0 and explorer is not None:
            try:
                proc = subprocess.Popen([explorer.prog, self.sel_nodes[0].get_path()])
            except OSError, e:
                self.error("Could not open folder in file explorer", e)


    def on_view_page_file_explorer(self):
        """View current page in file explorer"""
        explorer = self.app.pref.get_external_app("file_explorer")
    
        if self.current_page is not None and explorer is not "":
            try:
                subprocess.Popen([explorer.prog, self.current_page.get_path()])
            except OSError, e:
                self.error("Could not open page in file explorer", e)
            
    
    def on_view_page_web_browser(self):
        """View current page in web browser"""
        browser = self.app.pref.get_external_app("web_browser")
    
        if self.current_page is not None and browser is not None:
            try:
                proc = subprocess.Popen([browser.prog, self.current_page.get_data_file()])
            except OSError, e:
                self.error("Could not open page in web browser", e)
    
    
    def on_view_page_text_editor(self):
        """View current page in text editor"""
        editor = self.app.pref.get_external_app("text_editor")
    
        if self.current_page is not None and editor is not None:
            try:
                proc = subprocess.Popen([editor.prog, self.current_page.get_data_file()])
            except OSError, e:
                self.error("Could not open page in text editor", e)

    
    def on_spell_check_toggle(self, num, widget):
        """Toggle spell checker"""
        
        textview = self.editor.get_textview()
        if textview is not None:
            textview.enable_spell_check(widget.get_active())
        

   
    
    #==================================================
    # Help/about dialog
    
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
            print error
    
    
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
            ("/Edit/Insert _Image",
                None, lambda w,e: self.on_insert_image(), 0, None),
            ("/Edit/Insert _Screenshot",
                "<control>Insert", lambda w,e: self.on_screenshot(), 0, None),
            
            
            ("/_Search", None, None, 0, "<Branch>"),
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
                "<control>R", lambda w,e: self.find_dialog.on_find(True), 0, 
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
            
            ("/Format/sep2", 
                None, None, 0, "<Separator>" ),
            ("/Format/Increase Font _Size", 
                "<control>plus", lambda w, e: self.on_font_size_inc(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("font-inc.png")),
            ("/Format/_Decrease Font Size", 
                "<control>minus", lambda w, e: self.on_font_size_dec(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("font-dec.png")),
            

            ("/Format/sep3", 
                None, None, 0, "<Separator>" ),
            ("/Format/Choose _Font", 
                "<control><shift>F", lambda w, e: self.on_choose_font(), 0, 
                "<ImageItem>", 
                get_resource_pixbuf("font.png")),
            
            ("/_View", None, None, 0, "<Branch>"),
            ("/View/View Folder in File Explorer",
                None, lambda w,e: self.on_view_folder_file_explorer(), 0, 
                "<ImageItem>",
                get_resource_pixbuf("folder-open.png")),
            ("/View/View Page in File Explorer",
                None, lambda w,e: self.on_view_page_file_explorer(), 0, 
                "<ImageItem>",
                get_resource_pixbuf("note.png")),
            ("/View/View Page in Text Editor",
                None, lambda w,e: self.on_view_page_text_editor(), 0, 
                "<ImageItem>",
                get_resource_pixbuf("note.png")),
            ("/View/View Page in Web Browser",
                None, lambda w,e: self.on_view_page_web_browser(), 0, 
                "<ImageItem>",
                get_resource_pixbuf("note.png")),
                
            
            ("/_Go", None, None, 0, "<Branch>"),
            ("/Go/Go To _Tree View",
                "<control><shift>T", lambda w,e: self.on_goto_treeview(), 0, None),
            ("/Go/Go To _List View",
                "<control>Y", lambda w,e: self.on_goto_listview(), 0, None),
            ("/Go/Go To _Editor",
                "<control>D", lambda w,e: self.on_goto_editor(), 0, None),
            
            ("/_Options", None, None, 0, "<Branch>"),
            ("/Options/_Spell check", 
                None, self.on_spell_check_toggle, 0,
                "<ToggleItem>"),
                
            ("/Options/sep1", None, None, 0, "<Separator>"),
            ("/Options/_Horizontal Layout",
                None, lambda w,e: self.set_view_mode("horizontal"), 0, 
                None),
            ("/Options/_Vertical Layout",
                None, lambda w,e: self.set_view_mode("vertical"), 0, 
                None),
                
            ("/Options/sep1", None, None, 0, "<Separator>"),
            ("/Options/_TakeNote Options",
                None, lambda w,e: self.app_options_dialog.on_app_options(), 0, 
                "<StockItem>", gtk.STOCK_PREFERENCES),
            
            ("/_Help",       None, None, 0, "<LastBranch>" ),
            ("/Help/Drap and Drop Test",
                None, lambda w,e: self.drag_test.on_drag_and_drop_test(), 0, None),
            ("/Help/sep1", None, None, 0, "<Separator>"),
            ("/Help/About", None, lambda w,e: self.on_about(), 0, None ),
            )    
    
        accel_group = gtk.AccelGroup()

        # Create item factory
        self.item_factory = gtk.ItemFactory(gtk.MenuBar, "<main>", accel_group)
        self.item_factory.create_items(self.menu_items)
        self.add_accel_group(accel_group)
        return self.item_factory.get_widget("<main>")


    
    def make_toolbar(self):
        
        toolbar = gtk.Toolbar()
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
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
        self.bold_id = self.bold_button.connect("toggled", lambda w: self.editor.get_textview().on_bold())
        toolbar.insert(self.bold_button, -1)


        # italic tool
        self.italic_button = gtk.ToggleToolButton()
        self.italic_button.set_icon_widget(get_resource_image("italic.png"))
        tips.set_tip(self.italic_button, "Italic")
        self.italic_id = self.italic_button.connect("toggled", lambda w: self.editor.get_textview().on_italic())
        toolbar.insert(self.italic_button, -1)

        # underline tool
        self.underline_button = gtk.ToggleToolButton()
        self.underline_button.set_icon_widget(get_resource_image("underline.png"))
        tips.set_tip(self.underline_button, "Underline")
        self.underline_id = self.underline_button.connect("toggled", lambda w: self.editor.get_textview().on_underline())
        toolbar.insert(self.underline_button, -1)
        
        # fixed-width tool
        self.fixed_width_button = gtk.ToggleToolButton()
        self.fixed_width_button.set_icon_widget(get_resource_image("fixed-width.png"))
        tips.set_tip(self.fixed_width_button, "Monospace")
        self.fixed_width_id = self.fixed_width_button.connect("toggled", lambda w: self.on_fixed_width(True))
        toolbar.insert(self.fixed_width_button, -1)               

        # font button
        self.font_sel = gtk.FontButton()
        self.font_sel.set_use_font(True)
        #self.font_sel.set_show_size(False)
        item = gtk.ToolItem()
        item.add(self.font_sel)
        tips.set_tip(item, "Set Font")
        toolbar.insert(item, -1)
        self.font_sel.connect("font-set", lambda w: self.on_font_set())
        
        # font size increase
        button = gtk.ToolButton()
        button.set_icon_widget(get_resource_image("font-inc.png"))
        tips.set_tip(button, "Increase Font Size")
        button.connect("clicked", lambda w: self.on_font_size_inc())
        toolbar.insert(button, -1)        

        # font size decrease
        button = gtk.ToolButton()
        button.set_icon_widget(get_resource_image("font-dec.png"))
        tips.set_tip(button, "Decrease Font Size")
        button.connect("clicked", lambda w: self.on_font_size_dec())
        toolbar.insert(button, -1)        
        
        """
        # font size
        DEFAULT_FONT_SIZE = 12
        self.font_size_button = gtk.SpinButton(
          gtk.Adjustment(value=12, lower=2, upper=100, 
                         step_incr=1, page_incr=2, page_size=2))
        self.font_size_button.set_range(2, 100)
        self.font_size_button.set_value(DEFAULT_FONT_SIZE)
        item = gtk.ToolItem()
        item.add(self.font_size_button)
        tips.set_tip(item, "Set Font Size")
        toolbar.insert(item, -1)
        self.font_size_button.connect("value-changed", lambda w: 
            self.on_font_size_change())
        """
        
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
        item = gtk.MenuItem("New _Folder")
        item.connect("activate", lambda w: self.on_new_dir())
        self.treeview.menu.append(item)
        item.show()
        
        # treeview/new page
        item = gtk.MenuItem("New _Page")
        item.connect("activate", lambda w: self.on_new_page())
        self.treeview.menu.append(item)
        item.show()

        # treeview/delete node
        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        item.connect("activate", lambda w: self.treeview.on_delete_node())
        self.treeview.menu.append(item)
        item.show()

        #=================================
        # note selector context menu
        # selector/new folder
        #item = gtk.MenuItem("New _Folder")
        #item.connect("activate", lambda w: self.on_new_dir())
        #self.selector.menu.append(item)
        #item.show()
        
        # selector/new page
        item = gtk.MenuItem("New _Page")
        item.connect("activate", lambda w: self.on_new_page())
        self.selector.menu.append(item)
        item.show()

        # selector/delete node
        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        item.connect("activate", lambda w: self.selector.on_delete_page())
        self.selector.menu.append(item)
        item.show()
          

#=============================================================================
# Application class

class TakeNote (object):
    """TakeNote application class"""

    
    def __init__(self, basedir=""):
        takenote.set_basedir(basedir)
        
        self.basedir = basedir
        
        # load application preferences
        self.pref = takenote.TakeNotePreferences()
        self.pref.read()
        
        # open main window
        self.window = TakeNoteWindow(self)
        

        
    def open_notebook(self, filename):
        self.window.open_notebook(filename)

    def run_helper(self, app_key, filename, wait=True):
        app = self.pref.get_external_app(app_key)
        
        if app is None:
            raise Exception("Must specify program in Application Options")
        
        args = [app.prog] + app.args
        if "%s" not in args:
            args.append(filename)
        else:
            for i in xrange(len(args)):
                if args[i] == "%s":
                    args[i] = filename

        try:
            proc = subprocess.Popen(args)
        except OSError, e:
            raise Exception("Error running program ")
        
        if wait:
            return proc.wait()






