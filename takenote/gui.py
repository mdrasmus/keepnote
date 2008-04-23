"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for TakeNote Application
"""

# TODO: shade undo/redo
# TODO: add framework for customized page selector columns
# TODO: add html links
# TODO: add colored text



# python imports
import sys, os, tempfile, re

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk
import gtk.glade

# takenote imports
import takenote
from takenote import get_resource, NoteBookError, NoteBookDir, NoteBookPage
from takenote.undo import UndoStack
from takenote.richtext import RichTextView, RichTextImage, RichTextError
from takenote.treeview import TakeNoteTreeView
from takenote.noteselector import TakeNoteSelector


# constants
PROGRAM_NAME = "TakeNode"
PROGRAM_VERSION = "0.1"

g_images = {}

def get_image(filename):
    if filename in g_images:
        return g_images[filename]
    else:
        img = gtk.Image()
        img.set_from_file(filename)
        g_images[filename] = img
        return img



class TakeNoteEditor (gtk.ScrolledWindow):

    def __init__(self):
        gtk.ScrolledWindow.__init__(self)
        
        # state
        self._textview = RichTextView()
        self._page = None
        
        # callbacks
        self.on_page_modified = None
        
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_IN)
        
        self.add(self._textview)
        self.show()
        self._textview.show()

        
        
        
    def get_textview(self):
        return self._textview
    
        
    def view_pages(self, pages):
        # TODO: generalize to multiple pages
        self.save()
            
        if len(pages) == 0:
            self._page = None
            self._textview.disable()
        else:
            self._page = pages[0]
            self._textview.enable()
            
            try:
                self._textview.load(self._page.get_data_file())
            except RichTextError, e:
                self._textview.disable()
                self._page = None
                raise
                
    
    def save(self):
        if self._page is not None and \
           self._page.is_valid() and \
           self._textview.is_modified():
           
            try:
                self._textview.save(self._page.get_data_file())
            except RichTextError, e:
                raise
            else:
                self._page.set_modified_time()
                self._page.save()
                if self.on_page_modified:
                    self.on_page_modified(self._page)
    
    def save_needed(self):
        return self._textview.is_modified()


class TakeNoteWindow (gtk.Window):
    def __init__(self, app=""):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.app = app
        
        self.set_title("TakeNote")
        self.set_default_size(*takenote.DEFAULT_WINDOW_SIZE)
        self.connect("delete-event", lambda w,e: self.on_close())
        
        self.notebook = None
        self.sel_nodes = []
        self.current_page = None

        # treeview
        self.treeview = TakeNoteTreeView()
        self.treeview.on_select_node = self.on_select_treenode
        self.treeview.on_node_changed = self.on_treeview_node_changed
        
        # selector
        self.selector = TakeNoteSelector()
        self.selector.on_select_node = self.on_select_page
        self.selector.on_node_changed = self.on_selector_node_changed
        self.selector.on_status = self.set_status
        
        
        # editor
        self.editor = TakeNoteEditor()
        self.editor.get_textview().font_callback = self.on_font_change
        self.editor.on_page_modified = self.on_page_modified
        self.editor.view_pages([])
        
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

        
        
        
        # status bar
        status_hbox = gtk.HBox(False, 0)
        main_vbox.pack_start(status_hbox, False, True, 0)
        
        self.status_bar = gtk.Statusbar()      
        status_hbox.pack_start(self.status_bar, False, True, 0)
        self.status_bar.set_property("has-resize-grip", False)
        self.status_bar.set_size_request(300, -1)
        
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

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.treeview)
        self.hpaned.add1(sw)

        self.selector_sw = gtk.ScrolledWindow()
        self.selector_sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.selector_sw.set_shadow_type(gtk.SHADOW_IN)
        self.selector_sw.add(self.selector)
        self.paned2.add1(self.selector_sw)

        self.paned2.add2(self.editor)
        
        
        self.show_all()        
        self.treeview.grab_focus()
        
    
    def set_view_mode(self, mode):
        
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
    
    
    def set_status(self, text, bar="status"):
        if bar == "status":
            self.status_bar.pop(0)
            self.status_bar.push(0, text)
        elif bar == "stats":
            self.stats_bar.pop(0)
            self.stats_bar.push(0, text)
        else:
            raise Exception("unknown bar '%s'" % bar)
    
    
    def error(self, text, error):
        """Display an error message"""
        #self.set_status(text)
        
        dialog = gtk.MessageDialog(self.get_toplevel(), 
            flags= gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_ERROR, 
            buttons=gtk.BUTTONS_OK, 
            message_format=text)
        dialog.connect("response", lambda d,r: dialog.destroy())
        dialog.show()
        
        print error
        
    
    def get_preferences(self):
        if self.notebook is not None:
            self.resize(*self.notebook.pref.window_size)
            #if self.notebook.pref.window_pos != (-1, -1):
            #    self.move(*self.notebook.pref.window_pos)
            self.paned2.set_position(self.notebook.pref.vsash_pos)
            self.hpaned.set_position(self.notebook.pref.hsash_pos)
    

    def set_preferences(self):
        if self.notebook is not None:
            self.notebook.pref.window_size = self.get_size()
            #self.notebook.pref.window_pos = self.get_position()
            self.notebook.pref.vsash_pos = self.paned2.get_position()
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

    
    def on_reload_notebook(self):
        if self.notebook is None:
            self.error("Reloading only works when a notebook is open")
            return
        
        filename = self.notebook.get_path()
        self.close_notebook(False)
        self.open_notebook(filename)
        
        
    
    def new_notebook(self, filename):
        if self.notebook is not None:
            self.close_notebook()
        
        try:
            self.notebook = takenote.NoteBook(filename)
            self.notebook.create()
            self.set_status("Created '%s'" % self.notebook.get_title())
        except NoteBookError, e:
            self.notebook = None
            self.error("Could not create new notebook", e)
        
        self.open_notebook(filename, new=True)
        
        
    
    def open_notebook(self, filename, new=False):
        if self.notebook is not None:
            self.close_notebook()
        
        self.notebook = takenote.NoteBook()
        self.notebook.load(filename)
        self.selector.set_notebook(self.notebook)
        self.treeview.set_notebook(self.notebook)
        self.get_preferences()
        
        self.treeview.grab_focus()
        
        if not new:
            self.set_status("Loaded '%s'" % self.notebook.get_title())
        
        
    def close_notebook(self, save=True):
        if self.notebook is not None:
            if save:
                try:
                    self.editor.save()
                except RichTextError, e:
                    self.error("Could not save opened page", e)
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
        
        if parent.is_page():
            parent = parent.get_parent()
        
        node = parent.new_dir()
        self.treeview.update_node(parent)
        self.treeview.expand_node(parent)
        self.treeview.edit_node(node)
    
    def on_delete_dir(self):                
        
        # TODO: do delete yourself and update views
        # I need treeview.on_notebook_changed
    
        self.treeview.on_delete_node()
            
    
    def on_new_page(self):
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        if parent.is_page():
            parent = parent.get_parent()
        
        node = parent.new_page()
        self.treeview.update_node(parent)
        self.selector.view_nodes([parent])
        self.selector.edit_node(node)
    
    
    def on_delete_page(self):
        
        # TODO: do delete yourself and update view
        self.selector.on_delete_page()
    
    
    def on_save(self):
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
    
    
    def on_close(self):
        """close the window and quit"""
        self.close_notebook()
        gtk.main_quit()
        return False
    
    
    def on_select_treenode(self, nodes):
        self.sel_nodes = nodes
        self.selector.view_nodes(nodes)
        
        # view page
        pages = [node for node in nodes 
                 if isinstance(node, NoteBookPage)]
        
        if len(pages) > 0:
            self.current_page = pages[0]
        else:
            self.current_page = None
        
        try:
            self.editor.view_pages(pages)
        except RichTextError, e:
            self.error("Could not load pages", e)

    
    def on_select_page(self, page):
        self.current_page = page
        try:
            if page is None:
                self.editor.view_pages([])
            else:
                self.editor.view_pages([page])
        except RichTextError, e:
            self.error("Could not load page '%s'" % page.get_title(), e)
        
    def on_page_modified(self, page):
        self.treeview.update_node(page)
        self.selector.update_node(page)

    
    def on_treeview_node_changed(self, node, recurse):
        self.selector.update_node(node)

    def on_selector_node_changed(self, node, recurse):
        self.treeview.update_node(node)
        
    
    #=============================================================
    # Font UI Update
    
    def on_font_change(self, mods, justify, family, size):
        
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
    
    
    #==================================================
    # font callbacks

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
    
        
    #==================================================
    # callbacks

    def on_screenshot(self):
        if self.current_page is None:
            return
    
        f, imgfile = tempfile.mkstemp(".png", "takenote")
        os.close(f)
        
        # TODO: generalize
        os.system("import %s" % imgfile)
        if os.path.exists(imgfile):
            try:
                self.insert_image(imgfile, "screenshot.png")
            except Exception, e:
                # TODO: make exception more specific
                self.error("Error importing screenshot '%s'" % imgfile, e)
            
            try:
                os.remove(imgfile)
            except OSError, e:
                self.error("Was unable to remove temp file for screenshot", e)
                
        
    def on_insert_image(self):
        if self.current_page is None:
            return
                  
        dialog = gtk.FileChooserDialog("Insert Image From File", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Insert", gtk.RESPONSE_OK))
        dialog.connect("response", self.on_insert_image_response)
        dialog.show()
        
    
    def on_insert_image_response(self, dialog, response):
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
                self.error("Could not insert image '%s'" % filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
    
    
    def insert_image(self, filename, savename="image.png"):
        pixbuf = gdk.pixbuf_new_from_file(filename)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.editor.get_textview().insert_image(img, savename)
        
                

    
    def on_goto_treeview(self):
        self.treeview.grab_focus()
        
    def on_goto_listview(self):
        self.selector.grab_focus()
        
    def on_goto_editor(self):
        self.editor.get_textview().grab_focus()
    
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
    
    def on_cut(self):
        self.editor.get_textview().emit("cut-clipboard")
    
    def on_copy(self):
        self.editor.get_textview().emit("copy-clipboard")
    
    def on_paste(self):
        self.editor.get_textview().emit("paste-clipboard")

    def on_view_folder_file_explorer(self):
        explorer = self.app.pref.external_apps.get("file_explorer", "")
    
        if len(self.sel_nodes) > 0 and explorer != "":
            ret = os.system("%s '%s'" % (explorer, self.sel_nodes[0].get_path()))
            
            if ret != 0:
                self.error("Could not open node in file explorer")


    def on_view_page_file_explorer(self):
        explorer = self.app.pref.external_apps.get("file_explorer", "")
    
        if self.current_page is not None and explorer != "":
            ret = os.system("%s '%s'" % (explorer, self.current_page.get_path()))
            
            if ret != 0:
                self.error("Could not open node in file explorer")
            
    
    def on_view_page_web_browser(self):
        browser = self.app.pref.external_apps.get("web_browser", "")
    
        if self.current_page is not None and browser != "":
            ret = os.system("%s '%s'" % (browser, self.current_page.get_data_file()))
            
            if ret != 0:
                self.error("Could not open page in web browser")
    
    
    def on_view_page_text_editor(self):
        # TODO: edit in background
    
        editor = self.app.pref.external_apps.get("text_editor", "")
    
        if self.current_page is not None and editor != "":
            ret = os.system("%s '%s'" % (editor, self.current_page.get_data_file()))
            
            if ret != 0:
                self.error("Could not open page in text editor")
    
    #==================================================================
    # Find dialog
    
    def on_find(self, replace=False, forward=None):
        if hasattr(self, "find_dialog") and self.find_dialog:
            self.find_dialog.present()
            
            # could add find again behavior here            
            self.find_xml.get_widget("replace_checkbutton").set_active(replace)
            self.find_xml.get_widget("replace_entry").set_sensitive(replace)
            self.find_xml.get_widget("replace_button").set_sensitive(replace)
            self.find_xml.get_widget("replace_all_button").set_sensitive(replace)
            
            if not replace:
                if forward is None:
                    self.on_find_response("find")
                elif forward:
                    self.on_find_response("find_next")
                else:
                    self.on_find_response("find_prev")
            else:
                self.on_find_response("replace")
            
            return
        

        
        self.find_xml = gtk.glade.XML(get_resource("rc", "app_config.glade"))    
        self.find_dialog = self.find_xml.get_widget("find_dialog")
        self.find_dialog.connect("delete-event", lambda w,e: self.on_find_response("close"))
        self.find_last_pos = -1
        
            
        
        self.find_xml.signal_autoconnect({
            "on_find_dialog_key_release_event":
                self.on_find_key_released,
            "on_close_button_clicked": 
                lambda w: self.on_find_response("close"),
            "on_find_button_clicked": 
                lambda w: self.on_find_response("find"),
            "on_replace_button_clicked": 
                lambda w: self.on_find_response("replace"),
            "on_replace_all_button_clicked": 
                lambda w: self.on_find_response("replace_all"),
            "on_replace_checkbutton_toggled":
                lambda w: self.on_find_replace_toggled()
            })
        
        if hasattr(self, "find_text"):
            self.find_xml.get_widget("text_entry").set_text(self.find_text)
        
        if hasattr(self, "replace_text"):
            self.find_xml.get_widget("replace_entry").set_text(self.replace_text)
        
        self.find_xml.get_widget("replace_checkbutton").set_active(replace)
        self.find_xml.get_widget("replace_entry").set_sensitive(replace)
        self.find_xml.get_widget("replace_button").set_sensitive(replace)
        self.find_xml.get_widget("replace_all_button").set_sensitive(replace)
        
        self.find_dialog.show()
    
    def on_find_key_released(self, widget, event):
        
        if event.keyval == gdk.keyval_from_name("G") and \
           event.state & gtk.gdk.SHIFT_MASK and \
           event.state & gtk.gdk.CONTROL_MASK:
            self.on_find_response("find_prev")
            widget.stop_emission("key-release-event")
        
        elif event.keyval == gdk.keyval_from_name("g") and \
           event.state & gtk.gdk.CONTROL_MASK:
            self.on_find_response("find_next")
            widget.stop_emission("key-release-event")

    
    
    def on_find_response(self, response):
        
        # get find options
        find_text = self.find_xml.get_widget("text_entry").get_text()
        replace_text = self.find_xml.get_widget("replace_entry").get_text()
        case_sensitive = self.find_xml.get_widget("case_sensitive_button").get_active()
        search_forward = self.find_xml.get_widget("forward_button").get_active()
        
        self.find_text = find_text
        self.replace_text = replace_text
        next = (self.find_last_pos != -1)
        
                
        if response == "close":
            self.find_dialog.destroy()
            self.find_dialog = None
            
        elif response == "find":
            self.find_last_pos = self.editor.get_textview().find(find_text, case_sensitive, search_forward,
                                      next)

        elif response == "find_next":
            self.find_xml.get_widget("forward_button").set_active(True)
            self.find_last_pos = self.editor.get_textview().find(find_text, case_sensitive, True)

        elif response == "find_prev":
            self.find_xml.get_widget("backward_button").set_active(True)
            self.find_last_pos = self.editor.get_textview().find(find_text, case_sensitive, False)
        
        elif response == "replace":
            self.find_last_pos = self.editor.get_textview().replace(find_text, replace_text,
                                         case_sensitive, search_forward)
            
        elif response == "replace_all":
            self.editor.get_textview().replace_all(find_text, replace_text,
                                             case_sensitive, search_forward)
    
    
    def on_find_replace_toggled(self):
        
        if self.find_xml.get_widget("replace_checkbutton").get_active():
            self.find_xml.get_widget("replace_entry").set_sensitive(True)
            self.find_xml.get_widget("replace_button").set_sensitive(True)
            self.find_xml.get_widget("replace_all_button").set_sensitive(True)
        else:
            self.find_xml.get_widget("replace_entry").set_sensitive(False)
            self.find_xml.get_widget("replace_button").set_sensitive(False)
            self.find_xml.get_widget("replace_all_button").set_sensitive(False)
            
    
    #===================================================================
    # Application options
    
    def on_app_options(self):
        self.app_config_xml = gtk.glade.XML(get_resource("rc", "app_config.glade"))    
        self.app_config_dialog = self.app_config_xml.get_widget("app_config_dialog")
        self.app_config_dialog.set_transient_for(self)

        
        self.app_config_xml.signal_autoconnect({
            "on_ok_button_clicked": 
                lambda w: self.on_app_options_ok(),
            "on_cancel_button_clicked": 
                lambda w: self.app_config_dialog.destroy(),
                
            "on_default_notebook_button_clicked": 
                lambda w: self.on_app_options_browse(
                    "default_notebook", 
                    "Choose Default Notebook",
                    self.app.pref.default_notebook),
            "on_file_explorer_button_clicked": 
                lambda w: self.on_app_options_browse(
                    "file_explorer",
                    "Choose File Manager Application",
                    self.app.pref.external_apps.get("file_explorer", "")),
            "on_web_browser_button_clicked": 
                lambda w: self.on_app_options_browse(
                    "web_browser",
                    "Choose Web Browser Application",
                    self.app.pref.external_apps.get("web_browser", "")),
            "on_text_editor_button_clicked": 
                lambda w: self.on_app_options_browse(
                    "text_editor",
                    "Choose Text Editor Application",
                    self.app.pref.external_apps.get("text_editor", "")),
            "on_image_editor_button_clicked": 
                lambda w: self.on_app_options_browse(
                    "image_editor",
                    "Choose Image Editor Application",
                    self.app.pref.external_apps.get("image_editor", "")),
            })
        
        # populate dialog
        self.app_config_xml.get_widget("default_notebook_entry").\
            set_text(self.app.pref.default_notebook)
        
        self.app_config_xml.get_widget("file_explorer_entry").\
            set_text(self.app.pref.external_apps.get("file_explorer", ""))
        self.app_config_xml.get_widget("web_browser_entry").\
            set_text(self.app.pref.external_apps.get("web_browser", ""))
        self.app_config_xml.get_widget("text_editor_entry").\
            set_text(self.app.pref.external_apps.get("text_editor", ""))
        self.app_config_xml.get_widget("image_editor_entry").\
            set_text(self.app.pref.external_apps.get("image_editor", ""))
        
        
        self.app_config_dialog.show()
        
    
    
    def on_app_options_browse(self, name, title, filename):
        dialog = gtk.FileChooserDialog(title, self.app_config_dialog, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Open", gtk.RESPONSE_OK))
        dialog.connect("response", self.on_app_options_browse_response)
        dialog.set_transient_for(self.app_config_dialog)
        dialog.set_modal(True)
                
        
        if filename != "" and os.path.isabs(filename):
            dialog.set_filename(filename)
        
        
        # NOTE: monkey patch
        dialog.entry_name = name
        
        dialog.show()
        dialog.move(*self.get_position())
    
    
    def on_app_options_browse_response(self, dialog, response):
        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            dialog.destroy()
            
            self.app_config_xml.get_widget(dialog.entry_name + "_entry").\
                set_text(filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
    
    
    def on_app_options_ok(self):
        self.app.pref.default_notebook = \
            self.app_config_xml.get_widget("default_notebook_entry").get_text()
        
        self.app.pref.external_apps["file_explorer"] = \
            self.app_config_xml.get_widget("file_explorer_entry").get_text()
        self.app.pref.external_apps["web_browser"] = \
            self.app_config_xml.get_widget("web_browser_entry").get_text()
        self.app.pref.external_apps["text_editor"] = \
            self.app_config_xml.get_widget("text_editor_entry").get_text()
        self.app.pref.external_apps["image_editor"] = \
            self.app_config_xml.get_widget("image_editor_entry").get_text()
        
        self.app.pref.write()
        
        self.app_config_dialog.destroy()
        self.app_config_dialog = None
    
    #================================================
    # Drag and drop texting dialog
    
    def on_drag_and_drop_test(self):
        self.drag_win = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.drag_win.connect("delete-event", lambda d,r: self.drag_win.destroy())
        self.drag_win.drag_dest_set(0, [], gtk.gdk.ACTION_DEFAULT)
        
        self.drag_win.set_default_size(400, 400)
        vbox = gtk.VBox(False, 0)
        self.drag_win.add(vbox)
        
        self.drag_win.mime = gtk.TextView()
        vbox.pack_start(self.drag_win.mime, False, True, 0)
        
        self.drag_win.editor = gtk.TextView()
        self.drag_win.editor.connect("drag-motion", self.on_drag_and_drop_test_motion)        
        self.drag_win.editor.connect("drag-data-received", self.on_drag_and_drop_test_data)
        self.drag_win.editor.connect("paste-clipboard", self.on_drag_and_drop_test_paste)
        self.drag_win.editor.set_wrap_mode(gtk.WRAP_WORD)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.drag_win.editor)
        vbox.pack_start(sw)
        
        self.drag_win.show_all()
    
    def on_drag_and_drop_test_motion(self, textview, drag_context, x, y, timestamp):
        buf = self.drag_win.mime.get_buffer()
        target = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        if target != "":
            textview.drag_dest_set_target_list([(target, 0, 0)])
    
    def on_drag_and_drop_test_data(self, textview, drag_context, x, y,
                                   selection_data, info, eventtime):
        textview.get_buffer().insert_at_cursor("drag_context = " + 
            str(drag_context.targets) + "\n")
        textview.stop_emission("drag-data-received")
        
        buf = textview.get_buffer()
        buf.insert_at_cursor("type(sel.data) = " + 
            str(type(selection_data.data)) + "\n")
        buf.insert_at_cursor("sel.data = " +
            str(selection_data.data)[:1000] + "\n")
        drag_context.finish(False, False, eventtime)            

        
    
    def on_drag_and_drop_test_paste(self, textview):
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        targets = clipboard.wait_for_targets()
        textview.get_buffer().insert_at_cursor("clipboard.targets = " + 
            str(targets)+"\n")
        textview.stop_emission('paste-clipboard')
        
        buf = self.drag_win.mime.get_buffer()
        target = buf.get_text(buf.get_start_iter(), buf.get_end_iter())
        if target != "":
            clipboard.request_contents(target, self.on_drag_and_drop_test_contents)
    
    def on_drag_and_drop_test_contents(self, clipboard, selection_data, data):
        buf = self.drag_win.editor.get_buffer()
        data = selection_data.data
        buf.insert_at_cursor("sel.targets = " + repr(selection_data.get_targets()) + "\n")
        buf.insert_at_cursor("type(sel.data) = " + str(type(data))+"\n")        
        print "sel.data = " + str(data)[:1000]+"\n"
        buf.insert_at_cursor("sel.data = " + str(data)[:1000]+"\n")
    

    
    #================================================
    # Menubar
    
    def make_menubar(self):
        # menu bar
        folder_delete = gtk.Image()
        folder_delete.set_from_file(get_resource("images", "folder-delete.png"))
        
        page_delete = gtk.Image()
        page_delete.set_from_file(get_resource("images", "note-delete.png"))
        
        self.menu_items = (
            ("/_File",               
                None, None, 0, "<Branch>"),
            ("/File/_New Notebook",
                "", lambda w,e: self.on_new_notebook(), 0, 
                "<StockItem>", gtk.STOCK_NEW),
            ("/File/New _Page",      
                "<control>N", lambda w,e: self.on_new_page(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "note-new.png")).get_pixbuf()),
            ("/File/New _Folder", 
                "<control><shift>N", lambda w,e: self.on_new_dir(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "folder-new.png")).get_pixbuf()),
            ("/File/_Open Notebook",          
                "<control>O", lambda w,e: self.on_open_notebook(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "open.png")).get_pixbuf()),
            ("/File/_Reload Notebook",          
                None, lambda w,e: self.on_reload_notebook(), 0, 
                "<StockItem>", gtk.STOCK_REVERT_TO_SAVED),
            ("/File/_Save Notebook",     
                "<control>S", lambda w,e: self.on_save(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "save.png")).get_pixbuf()),
            ("/File/_Close Notebook", 
                "<control>W", lambda w, e: self.close_notebook(), 0, 
                "<StockItem>", gtk.STOCK_CLOSE),
            ("/File/sep1", 
                None, None, 0, "<Separator>" ),
            ("/File/Quit", 
                "<control>Q", lambda w,e: self.on_close(), 0, None),

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
            
            
            ("/Edit/sep3", 
                None, None, 0, "<Separator>"),
            ("/Edit/_Delete Folder",
                None, lambda w,e: self.on_delete_dir(), 0, 
                "<ImageItem>", folder_delete.get_pixbuf()),
            ("/Edit/Delete _Page",     
                None, lambda w,e: self.on_delete_page(), 0,
                "<ImageItem>", page_delete.get_pixbuf()),
            ("/Edit/sep4", 
                None, None, 0, "<Separator>"),
            ("/Edit/Insert _Image",
                None, lambda w,e: self.on_insert_image(), 0, None),
            ("/Edit/Insert _Screenshot",
                "<control>Insert", lambda w,e: self.on_screenshot(), 0, None),
            
            
            ("/_Search", None, None, 0, "<Branch>"),
            ("/Search/_Find In Page",     
                "<control>F", lambda w,e: self.on_find(False), 0, 
                "<StockItem>", gtk.STOCK_FIND), 
            ("/Search/Find _Next In Page",     
                "<control>G", lambda w,e: self.on_find(False, forward=True), 0, 
                "<StockItem>", gtk.STOCK_FIND), 
            ("/Search/Find Pre_vious In Page",     
                "<control><shift>G", lambda w,e: self.on_find(False, forward=False), 0, 
                "<StockItem>", gtk.STOCK_FIND),                 
            ("/Search/_Replace In Page",     
                "<control>R", lambda w,e: self.on_find(True), 0, 
                "<StockItem>", gtk.STOCK_FIND), 
                
            
            ("/_Format", 
                None, None, 0, "<Branch>"),
            ("/Format/_Left Align", 
                "<control>L", lambda w,e: self.on_left_justify(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "alignleft.png")).get_pixbuf()),
            ("/Format/C_enter Align", 
                "<control>E", lambda w,e: self.on_center_justify(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "aligncenter.png")).get_pixbuf()),
            ("/Format/_Right Align", 
                "<control>R", lambda w,e: self.on_right_justify(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "alignright.png")).get_pixbuf()),
            ("/Format/_Justify Align", 
                "<control>J", lambda w,e: self.on_fill_justify(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "alignjustify.png")).get_pixbuf()),
            
            ("/Format/sep1", 
                None, None, 0, "<Separator>" ),            
            ("/Format/_Bold", 
                "<control>B", lambda w,e: self.on_bold(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "bold.png")).get_pixbuf()),
            ("/Format/_Italic", 
                "<control>I", lambda w,e: self.on_italic(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "italic.png")).get_pixbuf()),
            ("/Format/_Underline", 
                "<control>U", lambda w,e: self.on_underline(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "underline.png")).get_pixbuf()),
            ("/Format/_Monospace",
                "<control>M", lambda w,e: self.on_fixed_width(False), 0,
                "<ImageItem>",
                get_image(get_resource("images", "fixed-width.png")).get_pixbuf()),
            
            ("/Format/sep2", 
                None, None, 0, "<Separator>" ),
            ("/Format/Increase Font _Size", 
                "<control>plus", lambda w, e: self.on_font_size_inc(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "font-inc.png")).get_pixbuf()),
            ("/Format/_Decrease Font Size", 
                "<control>minus", lambda w, e: self.on_font_size_dec(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "font-dec.png")).get_pixbuf()),
            

            ("/Format/sep3", 
                None, None, 0, "<Separator>" ),
            ("/Format/Choose _Font", 
                "<control><shift>F", lambda w, e: self.on_choose_font(), 0, 
                "<ImageItem>", 
                get_image(get_resource("images", "font.png")).get_pixbuf()),
            
            ("/_View", None, None, 0, "<Branch>"),
            ("/View/View Folder in File Explorer",
                None, lambda w,e: self.on_view_folder_file_explorer(), 0, 
                "<ImageItem>",
                get_image(get_resource("images", "folder-open.png")).get_pixbuf()),
            ("/View/View Page in File Explorer",
                None, lambda w,e: self.on_view_page_file_explorer(), 0, 
                "<ImageItem>",
                get_image(get_resource("images", "note.png")).get_pixbuf()),
            ("/View/View Page in Text Editor",
                None, lambda w,e: self.on_view_page_text_editor(), 0, 
                "<ImageItem>",
                get_image(get_resource("images", "note.png")).get_pixbuf()),                
            ("/View/View Page in Web Browser",
                None, lambda w,e: self.on_view_page_web_browser(), 0, 
                "<ImageItem>",
                get_image(get_resource("images", "note.png")).get_pixbuf()),
                
            
            ("/_Go", None, None, 0, "<Branch>"),
            ("/Go/Go To _Tree View",
                "<control>T", lambda w,e: self.on_goto_treeview(), 0, None),
            ("/Go/Go To _List View",
                "<control>Y", lambda w,e: self.on_goto_listview(), 0, None),
            ("/Go/Go To _Editor",
                "<control>D", lambda w,e: self.on_goto_editor(), 0, None),
            
            ("/_Options", None, None, 0, "<Branch>"),
            ("/Options/_Horizontal Layout",
                None, lambda w,e: self.set_view_mode("horizontal"), 0, 
                None),
            ("/Options/_Vertical Layout",
                None, lambda w,e: self.set_view_mode("vertical"), 0, 
                None),
                
            ("/Options/sep1", None, None, 0, "<Separator>"),
            ("/Options/_TakeNote Options",
                None, lambda w,e: self.on_app_options(), 0, 
                "<StockItem>", gtk.STOCK_PREFERENCES),
            
            ("/_Help",       None, None, 0, "<LastBranch>" ),
            ("/Help/Drap and Drop Test",
                None, lambda w,e: self.on_drag_and_drop_test(), 0, None),
            ("/Help/sep1", None, None, 0, "<Separator>"),
            ("/Help/About", None, lambda w,e: self.on_about(), 0, None ),
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
        tips.enable()

        # open notebook
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "open.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
        tips.set_tip(button, "Open Notebook")
        button.connect("clicked", lambda w: self.on_open_notebook())
        toolbar.insert(button, -1)

        # save notebook
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "save.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
        tips.set_tip(button, "Save Notebook")
        button.connect("clicked", lambda w: self.on_save())
        toolbar.insert(button, -1)        

        # separator
        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
    
        # new folder
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "folder-new.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
        tips.set_tip(button, "New Folder")
        button.connect("clicked", lambda w: self.on_new_dir())
        toolbar.insert(button, -1)
        
        # folder delete
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "folder-delete.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
        tips.set_tip(button, "Delete Folder")
        button.connect("clicked", lambda w: self.on_delete_dir())
        toolbar.insert(button, -1)

        # new note
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "note-new.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
        tips.set_tip(button, "New Note")
        button.connect("clicked", lambda w: self.on_new_page())
        toolbar.insert(button, -1)
        
        # note delete
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "note-delete.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
        tips.set_tip(button, "Delete Note")
        button.connect("clicked", lambda w: self.on_delete_page())
        toolbar.insert(button, -1)


        # separator
        toolbar.insert(gtk.SeparatorToolItem(), -1)
        
        
        # bold tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "bold.png"))
        self.bold_button = gtk.ToggleToolButton()
        self.bold_button.set_icon_widget(icon)
        tips.set_tip(self.bold_button, "Bold")
        self.bold_id = self.bold_button.connect("toggled", lambda w: self.editor.get_textview().on_bold())
        toolbar.insert(self.bold_button, -1)


        # italic tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "italic.png"))
        self.italic_button = gtk.ToggleToolButton()
        self.italic_button.set_icon_widget(icon)
        tips.set_tip(self.italic_button, "Italic")
        self.italic_id = self.italic_button.connect("toggled", lambda w: self.editor.get_textview().on_italic())
        toolbar.insert(self.italic_button, -1)

        # underline tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "underline.png"))
        self.underline_button = gtk.ToggleToolButton()
        self.underline_button.set_icon_widget(icon)
        tips.set_tip(self.underline_button, "Underline")
        self.underline_id = self.underline_button.connect("toggled", lambda w: self.editor.get_textview().on_underline())
        toolbar.insert(self.underline_button, -1)
        
        # fixed-width tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "fixed-width.png"))
        self.fixed_width_button = gtk.ToggleToolButton()
        self.fixed_width_button.set_icon_widget(icon)
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
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "font-inc.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
        tips.set_tip(button, "Increase Font Size")
        button.connect("clicked", lambda w: self.on_font_size_inc())
        toolbar.insert(button, -1)        

        # font size decrease
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "font-dec.png"))
        button = gtk.ToolButton()
        button.set_icon_widget(icon)
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
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "alignleft.png"))
        self.left_button = gtk.ToggleToolButton()
        self.left_button.set_icon_widget(icon)
        tips.set_tip(self.left_button, "Left Align")
        self.left_id = self.left_button.connect("toggled", lambda w: self.on_left_justify())
        toolbar.insert(self.left_button, -1)
        
        # center tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "aligncenter.png"))
        self.center_button = gtk.ToggleToolButton()
        self.center_button.set_icon_widget(icon)
        tips.set_tip(self.center_button, "Center Align")
        self.center_id = self.center_button.connect("toggled", lambda w: self.on_center_justify())
        toolbar.insert(self.center_button, -1)
        
        # right tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "alignright.png"))
        self.right_button = gtk.ToggleToolButton()
        self.right_button.set_icon_widget(icon)
        tips.set_tip(self.right_button, "Right Align")
        self.right_id = self.right_button.connect("toggled", lambda w: self.on_right_justify())
        toolbar.insert(self.right_button, -1)
        
        # justify tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "alignjustify.png"))
        self.fill_button = gtk.ToggleToolButton()
        self.fill_button.set_icon_widget(icon)
        tips.set_tip(self.fill_button, "Justify Align")
        self.fill_id = self.fill_button.connect("toggled", lambda w: self.on_fill_justify())
        toolbar.insert(self.fill_button, -1)
        return toolbar


class TakeNote (object):
    
    def __init__(self, basedir=""):
        self.basedir = basedir
        self.pref = takenote.TakeNotePreferences()
        
        
        takenote.BASEDIR = basedir
        self.pref.read()
        self.window = TakeNoteWindow(self)
        

        
    def open_notebook(self, filename):
        self.window.open_notebook(filename)

