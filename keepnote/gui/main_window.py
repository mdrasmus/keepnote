"""
    KeepNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for KeepNote Application
"""


# python imports
import gettext
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

_ = gettext.gettext




# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject
import pango

# keepnote imports
import keepnote
from keepnote import KeepNoteError
from keepnote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf, \
     get_accel_file, \
     lookup_icon_filename, \
     Action, \
     ToggleAction, \
     add_actions
from keepnote.notebook import \
     NoteBookError, \
     NoteBookVersionError
from keepnote import notebook as notebooklib
import keepnote.search
from keepnote.gui import richtext
from keepnote.gui.richtext import RichTextView, RichTextImage, RichTextError
from keepnote.gui.treeview import KeepNoteTreeView
from keepnote.gui.listview import KeepNoteListView
from keepnote.gui import \
    dialog_app_options, \
    dialog_find, \
    dialog_drag_drop_test, \
    dialog_image_resize, \
    dialog_wait, \
    dialog_update_notebook, \
    dialog_node_icon
from keepnote.gui.editor import KeepNoteEditor, EditorMenus
from keepnote.gui.icon_menu import IconMenu
from keepnote.gui.three_pane_viewer import ThreePaneViewer

from keepnote import tasklib


CONTEXT_MENU_ACCEL_PATH = "<main>/context_menu"



def set_menu_icon(uimanager, path, filename):
    item = uimanager.get_widget(path)
    img = gtk.Image()
    img.set_from_pixbuf(get_resource_pixbuf(filename))
    item.set_image(img) 


class FileChooserDialog (gtk.FileChooserDialog):
    """File Chooser Dialog with a persistent path"""

    def __init__(self, title=None, parent=None,
                 action=gtk.FILE_CHOOSER_ACTION_OPEN,
                 buttons=None, backend=None,
                 app=None,
                 persistent_path=None):
        gtk.FileChooserDialog.__init__(self, title, parent,
                                       action, buttons, backend)

        self._app = app
        self._persistent_path = persistent_path
        
        if self._app and self._persistent_path:
            path = getattr(self._app.pref, self._persistent_path)
            if os.path.exists(path):
                self.set_current_folder(path)


    def run(self):
        response = gtk.FileChooserDialog.run(self)

        if (response == gtk.RESPONSE_OK and 
            self._app and self._persistent_path):
            setattr(self._app.pref, self._persistent_path,
                     self.get_current_folder())
            
        return response



class KeepNoteWindow (gtk.Window):
    """Main windows for KeepNote"""

    def __init__(self, app):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self.app = app           # application object
        self.notebook = None     # opened notebook


        # window state
        self._maximized = False   # True if window is maximized
        self._iconified = False   # True if window is minimized
        self.tray_icon = None

        self.uimanager = gtk.UIManager()
        self.accel_group = self.uimanager.get_accel_group()
        self.add_accel_group(self.accel_group)
        
        self._ignore_view_mode = False # prevent recursive view mode changes

        self.init_key_shortcuts()
        self.init_layout()
        self.setup_systray()

        # load preferences
        self.get_app_preferences()
        self.set_view_mode(self.app.pref.view_mode)
        

    def new_viewer(self):

        viewer = ThreePaneViewer(self.app, self)
        viewer.connect("error", lambda w,t,e: self.error(t, e))
        viewer.listview.on_status = self.set_status  # TODO: clean up
        viewer.editor.connect("modified", self.on_page_editor_modified)
        viewer.editor.connect("child-activated", self.on_child_activated)
        viewer.editor.connect("window-request", self.on_window_request)

        # context menus
        self.make_context_menus(viewer)

        return viewer


    def init_layout(self):
        # init main window
        self.set_title(keepnote.PROGRAM_NAME)
        self.set_default_size(*keepnote.DEFAULT_WINDOW_SIZE)
        self.set_icon_list(get_resource_pixbuf("keepnote-16x16.png"),
                           get_resource_pixbuf("keepnote-32x32.png"),
                           get_resource_pixbuf("keepnote-64x64.png"))


        # main window signals
        self.connect("delete-event", lambda w,e: self.on_quit())
        self.connect("window-state-event", self.on_window_state)
        self.connect("size-allocate", self.on_window_size)
        self.app.pref.changed.add(self.on_app_options_changed)
        

        # viewer
        self.viewer = self.new_viewer()


        #====================================
        # Dialogs
        
        self.app_options_dialog = dialog_app_options.ApplicationOptionsDialog(self)
        self.drag_test = dialog_drag_drop_test.DragDropTestDialog(self)
        self.image_resize_dialog = \
            dialog_image_resize.ImageResizeDialog(self, self.app.pref)
        self.node_icon_dialog = dialog_node_icon.NodeIconDialog(self)
        
        
        #====================================
        # Layout
        
        # vertical box
        main_vbox = gtk.VBox(False, 0)
        self.add(main_vbox)
        
        # menu bar
        main_vbox.set_border_width(0)
        self.menubar = self.make_menubar()
        main_vbox.pack_start(self.menubar, False, True, 0)
        
        # toolbar
        main_vbox.pack_start(self.make_toolbar(), False, True, 0)          
        
        main_vbox2 = gtk.VBox(False, 0)
        main_vbox2.set_border_width(1)
        main_vbox.pack_start(main_vbox2, True, True, 0)

        # viewer
        main_vbox2.pack_start(self.viewer, True, True, 0)


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

        # add viewer menus
        add_actions(self.actiongroup, self.viewer.get_actions())
        for s in self.viewer.get_ui():
            ui_id = self.uimanager.add_ui_from_string(s)
        self.viewer.setup_menus(self.uimanager)

        

    def get_accel_group(self):
        return self.accel_group()


    def init_key_shortcuts(self):
        """Setup key shortcuts for the window"""
        
        accel_file = get_accel_file()
        if os.path.exists(accel_file):
            gtk.accel_map_load(accel_file)
        else:
            gtk.accel_map_save(accel_file)


    def setup_systray(self):
    
        # system tray icon
        if gtk.gtk_version > (2, 10):
            if not self.tray_icon:
                self.tray_icon = gtk.StatusIcon()
                self.tray_icon.set_from_pixbuf(get_resource_pixbuf("keepnote-32x32.png"))
                self.tray_icon.set_tooltip(keepnote.PROGRAM_NAME)
                self.tray_icon.connect("activate", self.on_tray_icon_activate)

            self.tray_icon.set_property("visible", self.app.pref.use_systray)
            
        else:
            self.tray_icon = None


    def get_current_page(self):
        return self.viewer.get_current_page()
        

    #=================================================
    # view config
        
    def set_view_mode(self, mode):
        """Sets the view mode of the window
        
        modes:
            "vertical"
            "horizontal"
        """
        
        if self._ignore_view_mode:
            return


        # update menu
        self._ignore_view_mode = True
        self.view_mode_h_toggle.set_active(mode == "horizontal")
        self.view_mode_v_toggle.set_active(mode == "vertical")
        self._ignore_view_mode = False
        
        # set viewer
        self.viewer.set_view_mode(mode)

        # record preference
        self.app.pref.view_mode = mode        
        self.app.pref.write()
        
        
    
                

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


    #=========================================================
    # main window gui callbacks

    def on_window_state(self, window, event):
        """Callback for window state"""

        # keep track of maximized and minimized state
        self._maximized = bool(event.new_window_state & 
                               gtk.gdk.WINDOW_STATE_MAXIMIZED)
        self._iconified = bool(event.new_window_state & 
                               gtk.gdk.WINDOW_STATE_ICONIFIED)



    def on_window_size(self, window, event):
        """Callback for resize events"""

        # record window size if it is not maximized or minimized
        if not self._maximized and not self._iconified:
            self.app.pref.window_size = self.get_size()


    def on_app_options_changed(self):
        self.get_app_preferences()


    def on_tray_icon_activate(self, icon):
        """Try icon has been clicked in system tray"""

        if self._iconified:
            self.restore_window()
        else:
            self.minimize_window()


    def on_window_request(self, widget, action):

        if action == "minimize":
            self.minimize_window()
        elif action == "restore":
            self.restore_window()
        else:
            raise Exception("unknown window request:" + str(action))
    
    
    #==============================================
    # Application preferences     
    
    def get_app_preferences(self):
        """Load preferences"""
        
        self.resize(*self.app.pref.window_size)
        self.viewer.load_preferences(self.app.pref)      
        self.enable_spell_check(self.app.pref.spell_check)
        self.setup_systray()

        if self.app.pref.use_systray:
            self.set_property("skip-taskbar-hint", self.app.pref.skip_taskbar)

        if self.app.pref.window_maximized:
            self.maximize()
    

    def set_app_preferences(self):
        """Save preferences"""

        self.app.pref.window_maximized = self._maximized
        self.viewer.save_preferences(self.app.pref)
        self.app.pref.last_treeview_name_path = []

        if self.app.pref.use_last_notebook and self.notebook:
            self.app.pref.default_notebook = self.notebook.get_path()
        
        self.app.pref.write()
        
        
    

           
    #=============================================
    # Notebook open/save/close UI

    def on_new_notebook(self):
        """Launches New NoteBook dialog"""
        
        dialog = FileChooserDialog(
            _("New Notebook"), self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE, #CREATE_FOLDER,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("New"), gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="new_notebook_path")
        response = dialog.run()
        
        
        if response == gtk.RESPONSE_OK:
            # create new notebook
            self.new_notebook(dialog.get_filename())

        dialog.destroy()
    
    
    def on_open_notebook(self):
        """Launches Open NoteBook dialog"""
        
        dialog = FileChooserDialog(
            _("Open Notebook"), self, 
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, #gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="new_notebook_path")

        def on_folder_changed(filechooser):
            folder = filechooser.get_current_folder()
            
            if os.path.exists(os.path.join(folder, notebooklib.PREF_FILE)):
                filechooser.response(gtk.RESPONSE_OK)
                        
        dialog.connect("current-folder-changed", on_folder_changed)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*.nbk")
        file_filter.set_name(_("Notebook (*.nbk)"))
        dialog.add_filter(file_filter)
        
        file_filter = gtk.FileFilter()
        file_filter.add_pattern("*")
        file_filter.set_name(_("All files (*.*)"))
        dialog.add_filter(file_filter)
        
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            # make sure start in parent directory
            self.app.pref.new_notebook_path = os.path.dirname(dialog.get_current_folder())

            notebook_file = dialog.get_filename()            
            self.open_notebook(notebook_file)

        dialog.destroy()

    
    def on_quit(self):
        """Close the window and quit"""
        self.set_app_preferences()
        self.close_notebook()
        gtk.accel_map_save(get_accel_file())
        gtk.main_quit()
        return False
    

    
    #===============================================
    # Notebook actions    

    def save_notebook(self, silent=False):
        """Saves the current notebook"""

        if self.notebook is None:
            return
        
        try:
            # TODO: should this be outside exception
            self.viewer.save()
            self.notebook.save()

            self.set_status(_("Notebook saved"))
            
            self.set_notebook_modified(False)
            
        except Exception, e:
            if not silent:
                self.error(_("Could not save notebook"), e, sys.exc_info()[2])
                self.set_status(_("Error saving notebook"))
                return

            self.set_notebook_modified(False)

        
            
    
    def reload_notebook(self):
        """Reload the current NoteBook"""
        
        if self.notebook is None:
            self.error(_("Reloading only works when a notebook is open"))
            return
        
        filename = self.notebook.get_path()
        self.close_notebook(False)
        self.open_notebook(filename)
        
        self.set_status(_("Notebook reloaded"))
        
        
    
    def new_notebook(self, filename):
        """Creates and opens a new NoteBook"""
        
        if self.notebook is not None:
            self.close_notebook()
        
        try:
            notebook = notebooklib.NoteBook(filename)
            notebook.create()
            self.set_status(_("Created '%s'") % notebook.get_title())
        except NoteBookError, e:
            self.error(_("Could not create new notebook"), e, sys.exc_info()[2])
            self.set_status("")
            return None
        
        return self.open_notebook(filename, new=True)
        
        
    
    def open_notebook(self, filename, new=False):
        """Opens a new notebook"""
        
        if self.notebook is not None:
            self.close_notebook()

        if os.path.isfile(filename):
            filename = os.path.dirname(filename)

        # check version
        try:
            version = notebooklib.get_notebook_version(filename)
        except Exception, e:
            # give up opening notebook
            self.error(_("Could not load notebook '%s'") % filename,
                       e, sys.exc_info()[2])
        else:
            if version < notebooklib.NOTEBOOK_FORMAT_VERSION:
                if not self.update_notebook(filename, version=version):
                    self.error(_("Cannot open notebook (version too old)"))
                    return None


        
        notebook = notebooklib.NoteBook()
        notebook.node_changed.add(self.on_notebook_node_changed)

        
        try:
            notebook.load(filename)
        except NoteBookVersionError, e:
            self.error(_("This version of %s cannot read this notebook.\n" 
                         "The notebook has version %d.  %s can only read %d")
                       % (keepnote.PROGRAM_NAME,
                          e.notebook_version,
                          keepnote.PROGRAM_NAME,
                          e.readable_version),
                       e, sys.exc_info()[2])
            return None
        except NoteBookError, e:            
            self.error(_("Could not load notebook '%s'") % filename,
                       e, sys.exc_info()[2])
            return None

        # check for icons
        if len(notebook.pref.get_quick_pick_icons()) == 0:
            notebook.pref.set_quick_pick_icons(
                list(keepnote.gui.DEFAULT_QUICK_PICK_ICONS))
            notebook.write_preferences()

        # setup notebook
        self.set_notebook(notebook)
        
        if not new:
            self.set_status(_("Loaded '%s'") % self.notebook.get_title())
        
        self.set_notebook_modified(False)

        # setup auto-saving
        self.begin_auto_save()
        
        return self.notebook
        
        
    def close_notebook(self, save=True):
        """Close the NoteBook"""
        
        if self.notebook is not None:
            if save:
                self.save_notebook()
            
            self.notebook.node_changed.remove(self.on_notebook_node_changed)
            self.set_notebook(None)
            self.set_status(_("Notebook closed"))


    def update_notebook(self, filename, version=None):
        try:
            dialog = dialog_update_notebook.UpdateNoteBookDialog(self)
            return dialog.show(filename, version=version)
        except Exception, e:
            self.error(_("Error occurred"), e, sys.exc_info()[2])
            return False
        


    def begin_auto_save(self):
        """Begin autosave callbacks"""

        if self.app.pref.autosave:
            gobject.timeout_add(self.app.pref.autosave_time, self.auto_save)
        

    def auto_save(self):
        """Callback for autosaving"""

        # NOTE: return True to activate next timeout callback
        
        if self.notebook is not None:
            self.save_notebook(True)
            return self.app.pref.autosave
        else:
            return False
    

    def set_notebook(self, notebook):
        """Set the NoteBook for the window"""
        
        self.notebook = notebook
        self.viewer.set_notebook(notebook)

    #=============================================================
    # Treeview, listview, editor callbacks

    
    def on_page_editor_modified(self, editor, page, modified):
        if modified:
            self.set_notebook_modified(modified)


    def on_child_activated(self, editor, textview, child):
        if isinstance(child, richtext.RichTextImage):
            self.view_image(child.get_filename())
    
    
    #===========================================================
    # page and folder actions

    def get_selected_nodes(self, widget="focus"):
        """
        Returns (nodes, widget) where 'nodes' are a list of selected nodes
        in widget 'widget'

        Wiget can be
           listview -- nodes selected in listview
           treeview -- nodes selected in treeview
           focus    -- nodes selected in widget with focus
        """
        
        return self.viewer.get_selected_nodes(widget)
        

    def on_new_node(self, kind, widget, pos):
        self.viewer.new_node(kind, widget, pos)
        
    
    def on_new_dir(self, widget="focus"):
        """Add new folder near selected nodes"""
        self.on_new_node(notebooklib.CONTENT_TYPE_DIR, widget, "sibling")
    
            
    
    def on_new_page(self, widget="focus"):
        """Add new page near selected nodes"""
        self.on_new_node(notebooklib.CONTENT_TYPE_PAGE, widget, "sibling")
    

    def on_new_child_page(self, widget="focus"):
        self.on_new_node(notebooklib.CONTENT_TYPE_PAGE, widget, "child")


    def on_empty_trash(self):
        """Empty Trash folder in NoteBook"""
        
        if self.notebook is None:
            return

        try:
            self.notebook.empty_trash()
        except NoteBookError, e:
            self.error(_("Could not empty trash."), e, sys.exc_info()[2])



    def on_search_nodes(self):
        """Search nodes"""

        # do nothing if notebook is not defined
        if not self.notebook:
            return

        # get words
        words = [x.lower() for x in
                 self.search_box.get_text().strip().split()]
        
        # prepare search iterator
        nodes = keepnote.search.search_manual(self.notebook, words)

        # clear listview        
        self.viewer.start_search_result()

        def search(task):
            # do search in another thread

            def gui_update(node):
                def func():
                    gtk.gdk.threads_enter()
                    self.viewer.add_search_result(node)
                    gtk.gdk.threads_leave()
                return func

            for node in nodes:
                # terminate if search is canceled
                if task.aborted():
                    break
                gobject.idle_add(gui_update(node))
                
            task.finish()

        # launch task
        self.wait_dialog(_("Searching notebook"), _("Searching..."),
                         tasklib.Task(search))


    def focus_on_search_box(self):
        self.search_box.grab_focus()


    def on_set_icon(self, icon_file, icon_open_file, widget="focus"):
        """
        Change the icon for a node

        icon_file, icon_open_file -- icon basenames
            use "" to delete icon setting (set default)
            use None to leave icon setting unchanged
        """

        if self.notebook is None:
            return

        nodes, widget = self.get_selected_nodes(widget)

        for node in nodes:

            if icon_file is "":
                node.del_attr("icon")
            elif icon_file is not None:
                node.set_attr("icon", icon_file)

            if icon_open_file is "":
                node.del_attr("icon_open")
            elif icon_open_file is not None:
                node.set_attr("icon_open", icon_open_file)

            node.del_attr("icon_load")
            node.del_attr("icon_open_load")



    def on_new_icon(self, widget="focus"):
        """Change the icon for a node"""

        if self.notebook is None:
            return

        nodes, widget = self.get_selected_nodes(widget)

        # TODO: assume only one node is selected
        node = nodes[0]

        icon_file, icon_open_file = self.node_icon_dialog.show(node)

        newly_installed = set()

        # NOTE: files may be filename or basename, use isabs to distinguish
        if icon_file and os.path.isabs(icon_file) and \
           icon_open_file and os.path.isabs(icon_open_file):
            icon_file, icon_open_file = self.notebook.install_icons(
                icon_file, icon_open_file)
            newly_installed.add(os.path.basename(icon_file))
            newly_installed.add(os.path.basename(icon_open_file))
            
        else:
            if icon_file and os.path.isabs(icon_file):
                icon_file = self.notebook.install_icon(icon_file)
                newly_installed.add(os.path.basename(icon_file))

            if icon_open_file and os.path.isabs(icon_open_file):
                icon_open_file = self.notebook.install_icon(icon_open_file)
                newly_installed.add(os.path.basename(icon_open_file))

        # set quick picks if OK was pressed
        if icon_file is not None:
            self.notebook.pref.set_quick_pick_icons(
                self.node_icon_dialog.get_quick_pick_icons())

            # set notebook icons
            notebook_icons = self.notebook.get_icons()
            keep_set = set(self.node_icon_dialog.get_notebook_icons()) | \
                       newly_installed
            for icon in notebook_icons:
                if icon not in keep_set:
                    self.notebook.uninstall_icon(icon)
            
            self.notebook.write_preferences()

        self.on_set_icon(icon_file, icon_open_file)


    
    
    #=====================================================
    # Notebook callbacks
    
    def on_notebook_node_changed(self, nodes, recurse):
        """Callback for when the notebook changes"""
        self.set_notebook_modified(True)
        
    
    def set_notebook_modified(self, modified):
        """Set the modification state of the notebook"""
        
        if self.notebook is None:
            self.set_title(keepnote.PROGRAM_NAME)
        else:
            if modified:
                self.set_title("* %s" % self.notebook.get_title())
                self.set_status(_("Notebook modified"))
            else:
                self.set_title("%s" % self.notebook.get_title())
    
    #=================================================

    def on_attach_file(self):

        if self.notebook is None:
            return
        
        dialog = FileChooserDialog(
            _("Attach File..."), self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Attach"), gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="attach_file_path")
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            filename = dialog.get_filename()
            nodes, widget = self.get_selected_nodes()            
            
            content_type = mimetypes.guess_type(filename)[0]
            if content_type is None:
                content_type = "application/octet-stream"

            new_filename = os.path.basename(filename)

            try:
                child = self.notebook.new_node(
                    content_type, nodes[0].get_path(), nodes[0],
                    {"payload_filename": new_filename,
                     "title": new_filename})
                child.create()
                child.set_payload(filename, new_filename)
                nodes[0].add_child(child)                
                child.save(True)
                
            except Exception, e:
                self.error(_("Error while attaching file '%s'" % filename),
                             e, sys.exc_info()[2])
                             

        dialog.destroy()

        

    #=================================================
    # Image context menu

    # TODO: look at what can be moved out of here

    def on_view_image(self, menuitem):
        """View image in Image Viewer"""

        current_page = self.get_current_page()
        if current_page is None:
            return
        
        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()
        self.view_image(image_filename)
        

    def view_image(self, image_filename):
        current_page = self.get_current_page()
        image_path = os.path.join(current_page.get_path(), image_filename)
        viewer = self.app.pref.get_external_app("image_viewer")
        
        if viewer is not None:
            try:
                proc = subprocess.Popen([viewer.prog, image_path])
            except OSError, e:
                self.error(_("Could not open Image Viewer"), 
                           e, sys.exc_info()[2])
        else:
            self.error(_("You must specify an Image Viewer in Application Options"))


    def on_edit_image(self, menuitem):
        """Edit image in Image Editor"""

        current_page = self.get_current_page()
        if current_page is None:
            return
        
        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()

        image_path = os.path.join(current_page.get_path(), image_filename)
        editor = self.app.pref.get_external_app("image_editor")
    
        if editor is not None:
            try:
                proc = subprocess.Popen([editor.prog, image_path])
            except OSError, e:
                self.error(_("Could not open Image Editor"), 
                           e, sys.exc_info()[2])
        else:
            self.error(_("You must specify an Image Editor in Application Options"))


    def on_resize_image(self, menuitem):
        """Resize image"""

        current_page = self.get_current_page()
        if current_page is None:
            return
        
        image = menuitem.get_parent().get_child()
        self.image_resize_dialog.on_resize(image)
        


    def on_save_image_as(self, menuitem):
        """Save image as a new file"""

        current_page = self.get_current_page()
        if current_page is None:
            return
        
        # get image filename
        image = menuitem.get_parent().get_child()
        image_filename = menuitem.get_parent().get_child().get_filename()
        image_path = os.path.join(current_page.get_path(), image_filename)

        dialog = FileChooserDialog(
            _("Save Image As..."), self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Save"), gtk.RESPONSE_OK),
            app=self.app,
            persistent_path="save_image_path")
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            if dialog.get_filename() == "":
                self.error(_("Must specify a filename for the image."))
            else:
                try:                
                    image.write(dialog.get_filename())
                except Exception, e:
                    self.error(_("Could not save image '%s'") %
                               dialog.get_filename(), e, sys.exc_info()[2])

        dialog.destroy()
    
    
    #=====================================================
    # Cut/copy/paste    
    # forward cut/copy/paste to the correct widget
    
    def on_cut(self):
        """Cut callback"""
        widget = self.get_focus()
        if gobject.signal_lookup("cut-clipboard", widget) != 0:
            widget.emit("cut-clipboard")
    
    def on_copy(self):
        """Copy callback"""
        widget = self.get_focus()
        if gobject.signal_lookup("copy-clipboard", widget) != 0:
            widget.emit("copy-clipboard")

    def on_paste(self):
        """Paste callback"""
        widget = self.get_focus()
        if gobject.signal_lookup("paste-clipboard", widget) != 0:
            widget.emit("paste-clipboard")


    def on_undo(self):
        """Undo callback"""
        self.viewer.undo()

    def on_redo(self):
        """Redo callback"""
        self.viewer.redo()
    
    
    #=====================================================
    # External app viewers

    def on_view_node_external_app(self, app, node=None, widget="focus",
                                  kind=None):
        """View a node with an external app"""

        self.save_notebook()
        
        if node is None:
            nodes, widget = self.get_selected_nodes(widget)
            if len(nodes) == 0:
                self.error(_("No notes are selected."))
                return            
            node = nodes[0]

            if kind == "page" and \
               node.get_attr("content_type") != notebooklib.CONTENT_TYPE_PAGE:
                self.error(_("Only pages can be viewed with %s.") %
                           self.app.pref.get_external_app(app).title)
                return

        try:
            if kind == "page":
                # get html file
                filename = os.path.realpath(node.get_data_file())
                
            elif kind == "file":
                # get payload file
                if not node.has_attr("payload_filename"):
                    self.error(_("Only documents can be viewed with %s.") %
                               self.app.pref.get_external_app(app).title)
                    return
                filename = os.path.realpath(
                    os.path.join(node.get_path(),
                                 node.get_attr("payload_filename")))
                
            else:
                # get node dir
                filename = os.path.realpath(node.get_path())
            
            self.app.run_external_app(app, filename)
        except KeepNoteError, e:
            self.error(e.msg, e, sys.exc_info()[2])


    def view_error_log(self):        
        """View error in text editor"""

        # windows locks open files
        # therefore we should copy error log before viewing it
        try:
            filename = os.path.realpath(keepnote.get_user_error_log())
            filename2 = filename + ".bak"
            shutil.copy(filename, filename2)        

            # use text editor to view error log
            self.app.run_external_app("text_editor", filename2)
        except Exception, e:
            self.error(_("Could not open error log"), e, sys.exc_info()[2])




    #=======================================================
    # spellcheck
    
    def on_spell_check_toggle(self, widget):
        """Toggle spell checker"""
        self.enable_spell_check(widget.get_active())


    def enable_spell_check(self, enabled):
        """Spell check"""

        textview = self.viewer.editor.get_textview()
        if textview is not None:
            textview.enable_spell_check(enabled)
            
            # see if spell check became enabled
            enabled = textview.is_spell_check_enabled()

            # record state in preferences
            self.app.pref.spell_check = enabled

            # update UI to match
            self.spell_check_toggle.set_active(enabled)
    
    #==================================================
    # Help/about dialog
    
    def on_about(self):
        """Display about dialog"""

        def func(dialog, link, data):
            try:
                self.app.open_webpage(link)
            except KeepNoteError, e:
                self.error(e.msg, e, sys.exc_info()[2])
        gtk.about_dialog_set_url_hook(func, None)
        
        
        about = gtk.AboutDialog()
        about.set_name(keepnote.PROGRAM_NAME)
        about.set_version(keepnote.PROGRAM_VERSION_TEXT)
        about.set_copyright("Copyright Matt Rasmussen 2009")
        about.set_logo(get_resource_pixbuf("keepnote-icon.png"))
        about.set_website(keepnote.WEBSITE)
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
            
    
    def error(self, text, error=None, tracebk=None):
        """Display an error message"""
        
        dialog = gtk.MessageDialog(self.get_toplevel(), 
            flags= gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_ERROR, 
            buttons=gtk.BUTTONS_OK, 
            message_format=text)
        dialog.connect("response", lambda d,r: d.destroy())
        dialog.set_title("Error")
        dialog.show()
        
        # add message to error log
        if error is not None:
            sys.stderr.write("\n")
            traceback.print_exception(type(error), error, tracebk)


    def wait_dialog(self, title, text, task):
        """Display a wait dialog"""

        dialog = dialog_wait.WaitDialog(self)
        dialog.show(title, text, task)


    def wait_dialog_test_task(self):
        # create dummy testing task
        
        def func(task):
            complete = 0.0
            while task.is_running():
                print complete
                complete = 1.0 - (1.0 - complete) * .9999
                task.set_percent(complete)
            task.finish()
        return tasklib.Task(func)
        

        
    
    #================================================
    # Menus

    def get_actions(self):

        actions = map(lambda x: Action(*x),
                      [
            ("File", None, "_File"),

            ("New Notebook", gtk.STOCK_NEW, _("_New Notebook"),
             "", _("Start a new notebook"),
             lambda w: self.on_new_notebook()),

            ("New Page", None, _("New _Page"),
             "<control>N", _("Create a new page"),
             lambda w: self.on_new_page()),

            ("New Child Page", None, _("New _Child Page"),
             "<control><shift>N", _("Create a new child page"),
             lambda w: self.on_new_child_page()),

            ("New Folder", None, _("New _Folder"),
             "<control><shift>M", _("Create a new folder"),
             lambda w: self.on_new_dir()),

            ("Open Notebook", gtk.STOCK_OPEN, _("_Open Notebook"),
             "<control>O", _("Open an existing notebook"),
             lambda w: self.on_open_notebook()),
            
            ("Reload Notebook", gtk.STOCK_REVERT_TO_SAVED,
             _("_Reload Notebook"),
             "", _("Reload the current notebook"),
             lambda w: self.reload_notebook()),
            
            ("Save Notebook", gtk.STOCK_SAVE, _("_Save Notebook"),             
             "<control>S", _("Save the current notebook"),
             lambda w: self.save_notebook()),
            
            ("Close Notebook", gtk.STOCK_CLOSE, _("_Close Notebook"),
             "", _("Close the current notebook"),
             lambda w: self.close_notebook()),
            
            ("Quit", gtk.STOCK_QUIT, _("_Quit"),
             "<control>Q", _("Quit KeepNote"),
             lambda w: self.on_quit()),

            #=======================================
            ("Edit", None, "_Edit"),
            
            ("Undo", gtk.STOCK_UNDO, None,
             "<control>Z", None,
             lambda w: self.on_undo()),
            
            ("Redo", gtk.STOCK_REDO, None,
             "<control><shift>Z", None,
             lambda w: self.on_redo()),
            
            ("Cut", gtk.STOCK_CUT, None,
             "<control>X", None,
             lambda w: self.on_cut()),

            ("Copy", gtk.STOCK_COPY, None,
             "<control>C", None,
             lambda w: self.on_copy()),

            ("Paste", gtk.STOCK_PASTE, None,
             "<control>V", None,
             lambda w: self.on_paste()),

            ("Attach File", None, _("_Attach File"),
             "", _("Attach a file to the notebook"),
             lambda w: self.on_attach_file()),

            ("Empty Trash", gtk.STOCK_DELETE, _("Empty _Trash"),
             "", None,
             lambda w: self.on_empty_trash()),
            
            #========================================
            ("Search", None, _("Search")),
            
            ("Search All Notes", gtk.STOCK_FIND, _("_Search All Notes"),
             "<control>K", None,
             lambda w: self.focus_on_search_box()),


            #========================================
            ("View", None, _("_View")),

            
            ("View Note in File Explorer", None,
             _("View Note in File Explorer"),
             "", None,
             lambda w: self.on_view_node_external_app("file_explorer")),
            
            ("View Note in Text Editor", None,
             _("View Note in Text Editor"),
             "", None,
             lambda w: self.on_view_node_external_app("text_editor",
                                                      kind="page")),

            ("View Note in Web Browser", None,
             _("View Note in Web Browser"),
             "", None,
             lambda w: self.on_view_node_external_app("web_browser",
                                                      kind="page")),

            ("Open Document", None,
             _("_Open Document"),
             "", None,
             lambda w: self.on_view_node_external_app("file_launcher",
                                                      kind="file")),

            #=======================================
            ("Go", None, "_Go"),            
            
            #=========================================
            ("Options", None, "_Options"),
            
            ("KeepNote Options", gtk.STOCK_PREFERENCES, _("KeepNote _Options"),
             "", None,
             lambda w: self.app_options_dialog.on_app_options()),

            #=========================================
            ("Help", None, "_Help"),
            
            ("View Error Log...", None, _("View _Error Log..."),
             "", None,
             lambda w: self.view_error_log()),
            
            ("Drag and Drop Test...", None, _("Drag and Drop Test..."),
             "", None,
             lambda w: self.drag_test.on_drag_and_drop_test()),
            
            ("About", gtk.STOCK_ABOUT, _("_About"),
             "", None,
             lambda w: self.on_about())
            ]) + \
            map(lambda x: ToggleAction(*x), [
            ("Spell Check", None, _("_Spell Check"), 
             "", None,
             self.on_spell_check_toggle),

            # TODO: move this to viewer actions
            ("Horizontal Layout", None, _("_Horizontal Layout"),
             "", None,
             lambda w: self.set_view_mode("horizontal")),
            
            ("Vertical Layout", None, _("_Vertical Layout"),
             "", None,
             lambda w: self.set_view_mode("vertical"))])

        return actions

    def setup_menus(self, uimanager):
        u = uimanager
        set_menu_icon(u, "/main_menu_bar/File/New Page", "note-new.png")
        set_menu_icon(u, "/main_menu_bar/File/New Child Page", "note-new.png")
        set_menu_icon(u, "/main_menu_bar/File/New Folder", "folder-new.png")


    def get_ui(self):

        return ["""
<ui>
<menubar name="main_menu_bar">
  <menu action="File">
     <menuitem action="New Notebook"/>
     <menuitem action="New Page"/>
     <menuitem action="New Child Page"/>
     <menuitem action="New Folder"/>
     <separator/>
     <menuitem action="Open Notebook"/>
     <menuitem action="Reload Notebook"/>
     <menuitem action="Save Notebook"/>
     <menuitem action="Close Notebook"/>
     <separator/>
     <placeholder name="File Extensions"/>
     <separator/>
     <menuitem action="Quit"/>
  </menu>
  <menu action="Edit">
    <menuitem action="Undo"/>
    <menuitem action="Redo"/>
    <separator/>
    <menuitem action="Cut"/>
    <menuitem action="Copy"/>
    <menuitem action="Paste"/>
    <separator/>
    <menuitem action="Attach File"/>
    <separator/>
    <placeholder name="Editor"/>
    <separator/>
    <menuitem action="Empty Trash"/>
  </menu>
  <menu action="Search">
    <menuitem action="Search All Notes"/>
    <placeholder name="Editor"/>
  </menu>
  <placeholder name="Editor"/>
  <menu action="View">
    <menuitem action="View Note in File Explorer"/>
    <menuitem action="View Note in Text Editor"/>
    <menuitem action="View Note in Web Browser"/>
    <menuitem action="Open Document"/>
  </menu>
  <menu action="Go">
    <placeholder name="Viewer"/>
  </menu>
  <menu action="Options">
    <menuitem action="Spell Check"/>
    <separator/>
    <menuitem action="Horizontal Layout"/>
    <menuitem action="Vertical Layout"/>
    <separator/>
    <menuitem action="KeepNote Options"/>
  </menu>
  <menu action="Help">
    <menuitem action="View Error Log..."/>
    <menuitem action="Drag and Drop Test..."/>
    <separator/>
    <menuitem action="About"/>
  </menu>
</menubar>
</ui>
"""]

    
    def make_menubar(self):
        """Initialize the menu bar"""

        #===============================
        # ui manager

        self.actiongroup = gtk.ActionGroup('MainWindow')
        self.uimanager.insert_action_group(self.actiongroup, 0)

        # setup menus
        add_actions(self.actiongroup, self.get_actions())
        for s in self.get_ui():
            self.uimanager.add_ui_from_string(s)
        self.setup_menus(self.uimanager)


        # view mode
        self.view_mode_h_toggle = \
            self.uimanager.get_widget("/main_menu_bar/Options/Horizontal Layout")
        self.view_mode_v_toggle = \
            self.uimanager.get_widget("/main_menu_bar/Options/Vertical Layout")

        # get spell check toggle
        self.spell_check_toggle = \
            self.uimanager.get_widget("/main_menu_bar/Options/Spell Check")
        self.spell_check_toggle.set_sensitive(
            self.viewer.editor.get_textview().can_spell_check())


        # return menu bar
        menubar = self.uimanager.get_widget('/main_menu_bar')
        return menubar
       
            

    
    def make_toolbar(self):
        
        toolbar = gtk.Toolbar()
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_ICONS)

        try:
            # NOTE: if this version of GTK doesn't have this size, then
            # ignore it
            toolbar.set_property("icon-size", gtk.ICON_SIZE_SMALL_TOOLBAR)
        except:
            pass
        
        toolbar.set_border_width(0)
        
        tips = gtk.Tooltips()
        tips.enable()
      

        # new folder
        button = gtk.ToolButton()
        if self.app.pref.use_stock_icons:
            button.set_stock_id(gtk.STOCK_DIRECTORY)
        else:
            button.set_icon_widget(get_resource_image("folder-new.png"))
        tips.set_tip(button, "New Folder")
        button.connect("clicked", lambda w: self.on_new_dir())
        toolbar.insert(button, -1)

        # new page
        button = gtk.ToolButton()
        if self.app.pref.use_stock_icons:
            button.set_stock_id(gtk.STOCK_NEW)
        else:
            button.set_icon_widget(get_resource_image("note-new.png"))
        tips.set_tip(button, "New Page")
        button.connect("clicked", lambda w: self.on_new_page())
        toolbar.insert(button, -1)

        # separator
        toolbar.insert(gtk.SeparatorToolItem(), -1)        


        # goto note
        #button = gtk.ToolButton()
        #button.set_stock_id(gtk.STOCK_GO_DOWN)
        #tips.set_tip(button, "Go to Note")
        #button.connect("clicked", lambda w: self.on_list_view_node(None, None))
        #toolbar.insert(button, -1)        
        
        # goto parent node
        #button = gtk.ToolButton()
        #button.set_stock_id(gtk.STOCK_GO_UP)
        #tips.set_tip(button, "Go to Parent Note")
        #button.connect("clicked", lambda w: self.on_list_view_parent_node())
        #toolbar.insert(button, -1)        


        # separator
        #toolbar.insert(gtk.SeparatorToolItem(), -1)        

        # insert editor toolbar
        self.viewer.make_toolbar(toolbar, tips, self.app.pref.use_stock_icons)

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


    def make_image_menu(self, menu):
        """image context menu"""

        menu.set_accel_group(self.accel_group)
        menu.set_accel_path(CONTEXT_MENU_ACCEL_PATH)
        item = gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)
            
        # image/edit
        item = gtk.MenuItem("_View Image...")
        item.connect("activate", self.on_view_image)
        item.child.set_markup_with_mnemonic("<b>_View Image...</b>")
        item.show()
        menu.append(item)
        
        item = gtk.MenuItem("_Edit Image...")
        item.connect("activate", self.on_edit_image)
        item.show()
        menu.append(item)

        item = gtk.MenuItem("_Resize Image...")
        item.connect("activate", self.on_resize_image)
        item.show()
        menu.append(item)

        # image/save
        item = gtk.ImageMenuItem("_Save Image As...")
        item.connect("activate", self.on_save_image_as)
        item.show()
        menu.append(item)


    def make_node_menu(self, widget, menu, control):
        """make list of menu options for nodes"""

        # treeview/new page
        item = gtk.ImageMenuItem()
        item.set_image(get_resource_image("note-new.png"))        
        label = gtk.Label("New _Page")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)        
        item.connect("activate", lambda w: self.on_new_page(control))
        menu.append(item)
        item.show()


        # treeview/new child page 
        item = gtk.ImageMenuItem()
        item.set_image(get_resource_image("note-new.png"))        
        label = gtk.Label("New _Child Page")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)        
        item.connect("activate", lambda w: self.on_new_child_page(control))
        menu.append(item)
        item.show()

        
        # treeview/new folder
        item = gtk.ImageMenuItem()        
        item.set_image(get_resource_image("folder-new.png"))
        label = gtk.Label("New _Folder")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)
        item.connect("activate", lambda w: self.on_new_dir(control))
        menu.append(item)
        item.show()
        

        # treeview/delete node
        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        item.connect("activate", lambda w: widget.on_delete_node())
        menu.append(item)
        item.show()

        # rename node
        item = gtk.MenuItem("_Rename")
        item.connect("activate", lambda w:
                     widget.edit_node(widget.get_selected_nodes()[0]))
        menu.add(item)
        item.show()
        

        # change icon
        item = gtk.ImageMenuItem()
        label = gtk.Label("Change _Icon")
        label.set_use_underline(True)
        label.set_alignment(0.0, 0.5)
        label.show()
        item.add(label)
        img = gtk.Image()
        img.set_from_file(lookup_icon_filename(None, "folder-red.png"))
        item.set_image(img)
        menu.append(item)
        menu.iconmenu = IconMenu()
        menu.iconmenu.connect("set-icon",
                              lambda w, i: self.on_set_icon(i, "", control))
        menu.iconmenu.new_icon.connect("activate",
                                       lambda w: self.on_new_icon(control))
        item.set_submenu(menu.iconmenu)
        item.show()
        

        #=============================================================
        item = gtk.SeparatorMenuItem()
        menu.append(item)
        item.show()


        # treeview/file explorer
        item = gtk.MenuItem("View in File _Explorer")
        item.connect("activate",
                     lambda w: self.on_view_node_external_app("file_explorer",
                                                              None,
                                                              control))
        menu.append(item)
        item.show()        

        # treeview/web browser
        item = gtk.MenuItem("View in _Web Browser")
        item.connect("activate",
                     lambda w: self.on_view_node_external_app("web_browser",
                                                              None,
                                                              control,
                                                              kind="page"))
        menu.append(item)
        item.show()        

        # treeview/text editor
        item = gtk.MenuItem("View in _Text Editor")
        item.connect("activate",
                     lambda w: self.on_view_node_external_app("text_editor",
                                                              None,
                                                              control,
                                                              kind="page"))
        menu.append(item)
        item.show()

        # treeview/Open document
        item = gtk.MenuItem("Open _Document")
        item.connect("activate",
                     lambda w: self.on_view_node_external_app("file_launcher",
                                                              None,
                                                              control,
                                                              kind="file"))
        menu.append(item)
        item.show()
        

    def make_treeview_menu(self, treeview, menu):
        """treeview context menu"""

        menu.set_accel_group(self.accel_group)
        menu.set_accel_path(CONTEXT_MENU_ACCEL_PATH)
        
        self.make_node_menu(treeview, menu, "treeview")

        
    def make_listview_menu(self, listview, menu):
        """listview context menu"""

        menu.set_accel_group(self.accel_group)
        menu.set_accel_path(CONTEXT_MENU_ACCEL_PATH)

        # listview/view note
        item = gtk.ImageMenuItem(gtk.STOCK_GO_DOWN)
        #item.child.set_label("Go to _Note")
        item.child.set_markup_with_mnemonic("<b>Go to _Note</b>")
        item.connect("activate",
                     lambda w: self.viewer.on_list_view_node(None, None))
        menu.append(item)
        item.show()

        # listview/view note
        item = gtk.ImageMenuItem(gtk.STOCK_GO_UP)
        item.child.set_label("Go to _Parent Note")
        item.connect("activate",
                     lambda w: self.viewer.on_list_view_parent_node())
        menu.append(item)
        item.show()

        item = gtk.SeparatorMenuItem()
        menu.append(item)
        item.show()

        self.make_node_menu(listview, menu, "listview")



    def make_context_menus(self, viewer):
        """Initialize context menus"""        

        self.make_image_menu(viewer.editor.get_textview().get_image_menu())       
        self.make_treeview_menu(viewer.treeview, viewer.treeview.menu)
        self.make_listview_menu(viewer.listview, viewer.listview.menu)

