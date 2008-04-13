"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for TakeNote Application
"""

# TODO: shade undo/redo
# TODO: add pages in treeview
#       will eventually require lazy loading for treeview
# TODO: add framework for customized page selector columns
# TODO: add html links
# TODO: make better font selector
# TODO: add colored text



# python imports
import sys, os, tempfile, re

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenote
from takenote import get_resource
from takenote.undo import UndoStack
from takenote.richtext import RichTextView, RichTextImage
from takenote.treeview import TakeNoteTreeView
from takenote.noteselector import TakeNoteSelector


# constants
PROGRAM_NAME = "TakeNode"
PROGRAM_VERSION = "0.1"




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
        self.on_page_modified = None
        
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
        if self.page is not None and \
           self.page.is_valid() and \
           self.textview.is_modified():
            self.textview.save(self.page.get_data_file())
            self.page.set_modified_time()
            self.page.save()
            if self.on_page_modified:
                self.on_page_modified(self.page)
    
    def save_needed(self):
        return self.textview.is_modified()


class TakeNoteWindow (gtk.Window):
    def __init__(self, basedir=""):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.basedir = basedir
        
        self.set_title("TakeNote")
        self.set_default_size(*takenote.DEFAULT_WINDOW_SIZE)
        self.connect("delete-event", lambda w,e: self.on_close())
        
        self.notebook = None
        self.sel_nodes = []
        self.current_page = None

        # treeview
        self.treeview = TakeNoteTreeView()
        self.treeview.on_select_node = self.on_select_treenode

        
        # selector
        self.selector = TakeNoteSelector()
        self.selector.on_select_node = self.on_select_page
        self.selector.on_status = self.set_status
        self.selector.notebook_tree = self.treeview
        
        
        # editor
        self.editor = TakeNoteEditor()
        self.editor.textview.font_callback = self.on_font_change
        self.editor.on_page_modified = self.on_page_modified
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
        status_hbox = gtk.HBox(False, 0)
        main_vbox.pack_start(status_hbox, False, True, 0)
        
        self.status_bar = gtk.Statusbar()      
        status_hbox.pack_start(self.status_bar, False, True, 0)
        self.status_bar.set_property("has-resize-grip", False)
        self.status_bar.set_size_request(300, -1)
        
        self.stats_bar = gtk.Statusbar()
        status_hbox.pack_start(self.stats_bar, True, True, 0)
        

        # layout major widgets
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.treeview)
        self.hpaned.add1(sw)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.selector)
        self.vpaned.add1(sw)
              
        self.vpaned.add2(self.editor.view)
        
        
        self.show_all()        
        self.treeview.grab_focus()
    

    def set_status(self, text, bar="status"):
        if bar == "status":
            self.status_bar.pop(0)
            self.status_bar.push(0, text)
        elif bar == "stats":
            self.stats_bar.pop(0)
            self.stats_bar.push(0, text)
        else:
            raise Exception("unknown bar '%s'" % bar)


    def error(self, text):
        """Display an error message"""
        self.set_status(text)
        
    
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
            self.set_status("Created '%s'" % self.notebook.get_title())
        except Exception, e:
            self.notebook = None
            self.set_status("Error: Could not create new notebook")
            print e
        
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
        
        node = parent.new_dir()
        self.treeview.update_node(parent)
        self.treeview.expand_node(parent)
        self.treeview.edit_node(node)
    
    
    def on_new_page(self):
        if len(self.sel_nodes) == 1:
            parent = self.sel_nodes[0]
        else:
            parent = self.notebook.get_root_node()
        
        node = parent.new_page()
        self.treeview.update_node(parent)
        self.selector.update()
        self.selector.edit_node(node)
    
    
    def on_save(self):
        if self.notebook is not None:
            needed = self.notebook.save_needed() or \
                     self.editor.save_needed()
            
            self.notebook.save()
            self.editor.save()
            
            if needed:
                self.set_status("Notebook saved")
    
    
    def on_close(self):
        """close the window and quit"""
        self.close_notebook()
        gtk.main_quit()
        return False
    
    
    def on_select_treenode(self, node):
        if node is not None:
            self.sel_nodes = [node]
            self.selector.view_nodes([node])
        else:
            self.sel_nodes = []
            self.selector.view_nodes([])
    
    def on_select_page(self, page):
        self.current_page = page
        self.editor.view_page(page)
        
    def on_page_modified(self, page):
        self.selector.update_node(page)
        
    
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
        if self.current_page is None:
            return
    
        f, imgfile = tempfile.mkstemp(".xpm", "takenote")
        os.close(f)
    
        os.system("import %s" % imgfile)
        if os.path.exists(imgfile):
            try:
                self.insert_image(imgfile, "screenshot.png")
            except Exception, e:
                print e
                self.error("error reading screenshot '%s'" % imgfile)
            
            os.remove(imgfile)
        
    def on_insert_image(self):
        if self.current_page is None:
            return
                  
        dialog = gtk.FileChooserDialog("Insert Image From File", self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=("Cancel", gtk.RESPONSE_CANCEL,
                     "Insert", gtk.RESPONSE_OK))
        dialog.connect("response", self.on_insert_image_response)
        
        """
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name("Notebook")
        self.filew.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name("All files")
        self.filew.add_filter(file_filter)
        """
        
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
                self.error("Could not insert image '%s'" % filename)
            
        elif response == gtk.RESPONSE_CANCEL:
            dialog.destroy()
    
    
    def insert_image(self, filename, savename="image.png"):
        pixbuf = gdk.pixbuf_new_from_file(filename)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.editor.textview.insert_image(img, savename)
        
                

    def on_choose_font(self):
        self.font_sel.clicked()
    
    
    def on_font_set(self):
        self.editor.textview.on_font_set(self.font_sel)
        self.editor.textview.grab_focus()
    
    
    def on_goto_treeview(self):
        self.treeview.grab_focus()
        
    def on_goto_listview(self):
        self.selector.grab_focus()
        
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
    
    def on_cut(self):
        self.editor.textview.emit("cut-clipboard")
    
    def on_copy(self):
        self.editor.textview.emit("copy-clipboard")
    
    def on_paste(self):
        self.editor.textview.emit("paste-clipboard")

    
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
            ("/File/_Save",     
                "<control>S", lambda w,e: self.on_save(), 0, None),
            ("/File/_Close Notebook", 
                "<control>W", lambda w, e: self.close_notebook(), 0, None),
            ("/File/sep1", 
                None, None, 0, "<Separator>" ),
            ("/File/Quit", 
                "<control>Q", lambda w,e: self.on_close(), 0, None),

            ("/_Edit", 
                None, None, 0, "<Branch>"),
            ("/Edit/_Undo", 
                "<control>Z", lambda w,e: self.editor.textview.undo(), 0, None),
            ("/Edit/_Redo", 
                "<control><shift>Z", lambda w,e: self.editor.textview.redo(), 0, None),
            ("/Edit/sep1", 
                None, None, 0, "<Separator>"),
            ("/Edit/Cu_t", 
                "<control>X", lambda w,e: self.on_cut(), 0, None), 
            ("/Edit/_Copy",     
                "<control>C", lambda w,e: self.on_copy(), 0, None), 
            ("/Edit/_Paste",     
                "<control>V", lambda w,e: self.on_paste(), 0, None), 
            ("/Edit/sep2", 
                None, None, 0, "<Separator>"),
            ("/Edit/Insert _Image",
                None, lambda w,e: self.on_insert_image(), 0, None),
            ("/Edit/Insert _Screenshot",
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
        icon.set_from_file(get_resource("images", "bold.xpm"))
        self.bold_button = gtk.ToggleToolButton()
        self.bold_button.set_icon_widget(icon)
        tips.set_tip(self.bold_button, "Bold")
        self.bold_id = self.bold_button.connect("toggled", lambda w: self.editor.textview.on_bold())
        toolbar.insert(self.bold_button, -1)


        # italic tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "italic.xpm"))
        self.italic_button = gtk.ToggleToolButton()
        self.italic_button.set_icon_widget(icon)
        tips.set_tip(self.italic_button, "Italic")
        self.italic_id = self.italic_button.connect("toggled", lambda w: self.editor.textview.on_italic())
        toolbar.insert(self.italic_button, -1)

        # underline tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "underline.xpm"))
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
        icon.set_from_file(get_resource("images", "alignleft.xpm"))
        self.left_button = gtk.ToggleToolButton()
        self.left_button.set_icon_widget(icon)
        tips.set_tip(self.left_button, "Left Justify")
        self.left_id = self.left_button.connect("toggled", lambda w: self.editor.textview.on_left_justify())
        toolbar.insert(self.left_button, -1)
        
        # center tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "aligncenter.xpm"))
        self.center_button = gtk.ToggleToolButton()
        self.center_button.set_icon_widget(icon)
        tips.set_tip(self.center_button, "Center Justify")
        self.center_id = self.center_button.connect("toggled", lambda w: self.editor.textview.on_center_justify())
        toolbar.insert(self.center_button, -1)
        
        # right tool
        icon = gtk.Image() # icon widget
        icon.set_from_file(get_resource("images", "alignright.xpm"))
        self.right_button = gtk.ToggleToolButton()
        self.right_button.set_icon_widget(icon)
        tips.set_tip(self.right_button, "Right Justify")
        self.right_id = self.right_button.connect("toggled", lambda w: self.editor.textview.on_right_justify())
        toolbar.insert(self.right_button, -1)        
        
        return toolbar


class TakeNote (object):
    
    def __init__(self, basedir=""):
        self.basedir = basedir
        
        takenote.BASEDIR = basedir
        
        self.window = TakeNoteWindow(basedir)

        
    def open_notebook(self, filename):
        self.window.open_notebook(filename)

