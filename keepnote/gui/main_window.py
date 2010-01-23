"""

    KeepNote
    Graphical User Interface for KeepNote Application

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
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


# python imports
import mimetypes
import os
import shutil
import subprocess
import sys



# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk
import gobject



# keepnote imports
import keepnote
from keepnote import \
    KeepNoteError, \
    ensure_unicode, \
    unicode_gtk, \
    FS_ENCODING
from keepnote.notebook import \
     NoteBookError, \
     NoteBookVersionError, \
     NoteBookTrash
from keepnote import notebook as notebooklib
from keepnote import tasklib
from keepnote.gui import \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf, \
     Action, \
     ToggleAction, \
     add_actions, \
     CONTEXT_MENU_ACCEL_PATH, \
     FileChooserDialog, \
     init_key_shortcuts, \
     UIManager

from keepnote.gui.icons import \
     lookup_icon_filename
import keepnote.search
from keepnote.gui import richtext
from keepnote.gui import \
    dialog_image_resize, \
    dialog_drag_drop_test, \
    dialog_wait, \
    dialog_update_notebook, \
    dialog_python, \
    update_file_preview
from keepnote.gui.icon_menu import IconMenu
from keepnote.gui.three_pane_viewer import ThreePaneViewer


_ = keepnote.translate



class KeepNoteWindow (gtk.Window):
    """Main windows for KeepNote"""

    def __init__(self, app):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        
        self._app = app # application object

        # window state
        self._maximized = False   # True if window is maximized
        self._was_maximized = False # True if iconified and was maximized
        self._iconified = False   # True if window is minimized
        self._tray_icon = None
        self._auto_saving = False

        self._uimanager = UIManager()
        self._accel_group = self._uimanager.get_accel_group()
        self.add_accel_group(self._accel_group)

        init_key_shortcuts()
        self.init_layout()
        self.setup_systray()

        # load preferences for the first time
        self.load_preferences(True)
        

    def init_layout(self):
        # init main window
        self.set_title(keepnote.PROGRAM_NAME)
        self.set_default_size(*keepnote.DEFAULT_WINDOW_SIZE)
        self.set_icon_list(get_resource_pixbuf("keepnote-16x16.png"),
                           get_resource_pixbuf("keepnote-32x32.png"),
                           get_resource_pixbuf("keepnote-64x64.png"))


        # main window signals
        self.connect("delete-event", lambda w,e: self._on_close())
        self.connect("window-state-event", self._on_window_state)
        self.connect("size-allocate", self._on_window_size)
        self._app.pref.changed.add(self._on_app_options_changed)


        #====================================
        # Dialogs
        
        self.drag_test = dialog_drag_drop_test.DragDropTestDialog(self)
        self.image_resize_dialog = \
            dialog_image_resize.ImageResizeDialog(self, self._app.pref)
        

        self.viewer = self.new_viewer()
        
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
        self.viewer_box = gtk.VBox(False, 0)
        main_vbox2.pack_start(self.viewer_box, True, True, 0)


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


        #====================================================
        # viewer
        
        self.viewer_box.pack_start(self.viewer, True, True, 0)

        # add viewer menus
        self.viewer.add_ui(self)


    def setup_systray(self):
        """Setup systray for window"""

        # system tray icon
        if gtk.gtk_version > (2, 10):
            if not self._tray_icon:
                self._tray_icon = gtk.StatusIcon()
                self._tray_icon.set_from_pixbuf(get_resource_pixbuf("keepnote-32x32.png"))
                self._tray_icon.set_tooltip(keepnote.PROGRAM_NAME)
                self._tray_icon.connect("activate", self._on_tray_icon_activate)

            self._tray_icon.set_property("visible", self._app.pref.use_systray)
            
        else:
            self._tray_icon = None


    def new_viewer(self):
        """Creates a new viewer for this window"""

        viewer = ThreePaneViewer(self._app, self)
        viewer.connect("error", lambda w,m,e: self.error(m, e))
        viewer.connect("status", lambda w,m,b: self.set_status(m, b))
        viewer.connect("window-request", self._on_window_request)

        return viewer


    #===============================================
    # accessors

    def get_app(self):
        """Returns application object"""
        return self._app

    def get_uimanager(self):
        """Returns the UIManager for the window"""
        return self._uimanager

    def get_viewer(self):
        """Returns window's viewer"""
        return self.viewer
            

    def get_accel_group(self):
        """Returns the accel group for the window"""
        return self._accel_group


    def get_notebook(self):
        """Returns the currently loaded notebook"""
        return self.viewer.get_notebook()

    
    def get_current_page(self):
        """Returns the currently selected page"""
        return self.viewer.get_current_page()
        
        

    #=========================================================
    # main window gui callbacks

    def _on_window_state(self, window, event):
        """Callback for window state"""

        iconified = self._iconified        

        # keep track of maximized and minimized state
        self._iconified = bool(event.new_window_state & 
                               gtk.gdk.WINDOW_STATE_ICONIFIED)

        # detect recent iconification
        if not iconified and self._iconified:
            # save maximized state before iconification
            self._was_maximized = self._maximized


        self._maximized = bool(event.new_window_state & 
                               gtk.gdk.WINDOW_STATE_MAXIMIZED)

        # detect recent de-iconification
        if iconified and not self._iconified:
            # explicitly maximize if not maximized
            # NOTE: this is needed to work around a MS windows GTK bug
            if self._was_maximized:
                gobject.idle_add(self.maximize)


    def _on_window_size(self, window, event):
        """Callback for resize events"""

        # record window size if it is not maximized or minimized
        if not self._maximized and not self._iconified:
            self._app.pref.window_size = self.get_size()


    def _on_app_options_changed(self):
        self.load_preferences()


    def _on_tray_icon_activate(self, icon):
        """Try icon has been clicked in system tray"""
        
        if self.is_active():
            self.minimize_window()
        else:
            self.restore_window()


    #=============================================================
    # viewer callbacks


    def _on_window_request(self, viewer, action):
        """Callback for requesting an action from the main window"""
        
        if action == "minimize":
            self.minimize_window()
        elif action == "restore":
            self.restore_window()
        else:
            raise Exception("unknown window request: " + str(action))
    

    #=================================================
    # Window manipulation

    def minimize_window(self):
        """Minimize the window (block until window is minimized"""
        
        if self._iconified:
            return

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

    
    #==============================================
    # Application preferences     
    
    def load_preferences(self, first_open=False):
        """Load preferences"""        

        if first_open:
            self.resize(*self._app.pref.window_size)
            if self._app.pref.window_maximized:
                self.maximize()

        self.setup_systray()

        if self._app.pref.use_systray:
            self.set_property("skip-taskbar-hint", self._app.pref.skip_taskbar)
        
        self.set_recent_notebooks_menu(self._app.pref.recent_notebooks)

        self._uimanager.set_force_stock(self._app.pref.use_stock_icons)

        self.viewer.load_preferences(self._app.pref, first_open)
    

    def save_preferences(self):
        """Save preferences"""

        self._app.pref.window_maximized = self._maximized
        self.viewer.save_preferences(self._app.pref)
        self._app.pref.last_treeview_name_path = []

        if self._app.pref.use_last_notebook and self.viewer.get_notebook():
            self._app.pref.default_notebook = self.viewer.get_notebook().get_path()
        
        self._app.pref.write()
        
        
    def set_recent_notebooks_menu(self, recent_notebooks):
        """Set the recent notebooks in the file menu"""

        menu = self._uimanager.get_widget("/main_menu_bar/File/Open Recent Notebook")

        # init menu
        if menu.get_submenu() is None:
            submenu = gtk.Menu()
            submenu.show()
            menu.set_submenu(submenu)
        menu = menu.get_submenu()

        # clear menu
        menu.foreach(lambda x: menu.remove(x))

        def make_filename(filename, maxsize=30):
            if len(filename) > maxsize:
                base = os.path.basename(filename)
                pre = max(maxsize - len(base), 10)
                return os.path.join(filename[:pre] + u"...", base)
            else:
                return filename

        def make_func(filename):
            return lambda w: self.open_notebook(filename)

        # populate menu
        for i, notebook in enumerate(recent_notebooks):
            item = gtk.MenuItem(u"%d. %s" % (i+1, make_filename(notebook)))
            item.connect("activate", make_func(notebook))
            item.show()
            menu.append(item)


    def add_recent_notebook(self, filename):
        """Add recent notebook"""
        
        if filename in self._app.pref.recent_notebooks:
            self._app.pref.recent_notebooks.remove(filename)
        
        self._app.pref.recent_notebooks = \
            [filename] + self._app.pref.recent_notebooks[:keepnote.gui.MAX_RECENT_NOTEBOOKS]

        self._app.pref.changed.notify()

           
    #=============================================
    # Notebook open/save/close UI

    def on_new_notebook(self):
        """Launches New NoteBook dialog"""
        
        dialog = FileChooserDialog(
            _("New Notebook"), self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("New"), gtk.RESPONSE_OK),
            app=self._app,
            persistent_path="new_notebook_path")
        response = dialog.run()
        
        if response == gtk.RESPONSE_OK:
            # create new notebook
            if dialog.get_filename():
                self.new_notebook(unicode_gtk(dialog.get_filename()))

        dialog.destroy()
    
    
    def on_open_notebook(self):
        """Launches Open NoteBook dialog"""
        
        dialog = FileChooserDialog(
            _("Open Notebook"), self, 
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER, 
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK),
            app=self._app,
            persistent_path="new_notebook_path")

        def on_folder_changed(filechooser):
            folder = unicode_gtk(filechooser.get_current_folder())
            
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
            if dialog.get_current_folder():
                self._app.pref.new_notebook_path = \
                    os.path.dirname(unicode_gtk(dialog.get_current_folder()))

            if dialog.get_filename():
                notebook_file = unicode_gtk(dialog.get_filename())
            self.open_notebook(notebook_file)

        dialog.destroy()

    
    def _on_close(self):
        """Callback for window close"""
        
        self.save_preferences()
        self.close_notebook()
        if self._tray_icon:
            # turn off try icon
            self._tray_icon.set_property("visible", False)
            
        return False
    

    def close(self):
        """Close the window"""

        self.emit("delete-event", None)
        

    
    #===============================================
    # Notebook actions    

    def save_notebook(self, silent=False):
        """Saves the current notebook"""

        if self.viewer.get_notebook() is None:
            return
        
        try:
            # TODO: should this be outside exception?
            self.viewer.save()
            self.viewer.get_notebook().save()
            
            self.set_status(_("Notebook saved"))
            
        except Exception, e:
            if not silent:
                self.error(_("Could not save notebook."), e, sys.exc_info()[2])
                self.set_status(_("Error saving notebook"))
                return

        self.set_notebook_modified(False)

        
            
    
    def reload_notebook(self):
        """Reload the current NoteBook"""
        
        if self.viewer.get_notebook() is None:
            self.error(_("Reloading only works when a notebook is open."))
            return
        
        filename = self.viewer.get_notebook().get_path()
        self.close_notebook(False)
        self.open_notebook(filename)
        
        self.set_status(_("Notebook reloaded"))
        
        
    
    def new_notebook(self, filename):
        """Creates and opens a new NoteBook"""
        
        if self.viewer.get_notebook() is not None:
            self.close_notebook()
        
        try:
            # make sure filename is unicode
            filename = ensure_unicode(filename, FS_ENCODING)
            notebook = notebooklib.NoteBook(filename)
            notebook.create()
            notebook.close()
            self.set_status(_("Created '%s'") % notebook.get_title())
        except NoteBookError, e:
            self.error(_("Could not create new notebook."), e, sys.exc_info()[2])
            self.set_status("")
            return None
        
        return self.open_notebook(filename, new=True)
        
        
    
    def open_notebook(self, filename, new=False):
        """Opens a new notebook"""
        
        if self.viewer.get_notebook() is not None:
            self.close_notebook()
        
        # make sure filename is unicode
        filename = ensure_unicode(filename, FS_ENCODING)
        
        # TODO: should this be moved deeper?
        # convert filenames to their directories
        if os.path.isfile(filename):
            filename = os.path.dirname(filename)

        win = self

        # check version
        try:
            notebook = self._app.get_notebook(filename, self)
            notebook.node_changed.add(self.on_notebook_node_changed)

        except NoteBookVersionError, e:
            self.error(_("This version of %s cannot read this notebook.\n" 
                         "The notebook has version %d.  %s can only read %d.")
                       % (keepnote.PROGRAM_NAME,
                          e.notebook_version,
                          keepnote.PROGRAM_NAME,
                          e.readable_version),
                       e, sys.exc_info()[2])
            return None

        except NoteBookError, e:            
            self.error(_("Could not load notebook '%s'.") % filename,
                       e, sys.exc_info()[2])
            return None

        except Exception, e:
            # give up opening notebook
            self.error(_("Could not load notebook '%s'.") % filename,
                       e, sys.exc_info()[2])
            return None



        # setup notebook
        self.set_notebook(notebook)
        
        if not new:
            self.set_status(_("Loaded '%s'") % self.viewer.get_notebook().get_title())
        
        self.set_notebook_modified(False)

        # setup auto-saving
        self.begin_auto_save()
        
        # save notebook to recent notebooks
        self.add_recent_notebook(filename)


        if self.viewer.get_notebook()._index.index_needed():
            self.update_index()

        return self.viewer.get_notebook()
        
        
    def close_notebook(self, save=True):
        """Close the NoteBook"""

        notebook = self.get_notebook()        

        if notebook is not None:
            if save:
                self.save_notebook()
            
            notebook.node_changed.remove(self.on_notebook_node_changed)
            
            self.set_notebook(None)
            self.set_status(_("Notebook closed"))

            # TODO: will need to check that notebook is not opened by 
            # another window
            #notebook.close()
            self._app.close_notebook(notebook)


    def begin_auto_save(self):
        """Begin autosave callbacks"""

        if self._app.pref.autosave:
            self._auto_saving = True
            gobject.timeout_add(self._app.pref.autosave_time, self.auto_save)
        
    def end_auto_save(self):
        """Stop autosave"""

        self._auto_saving = False


    def auto_save(self):
        """Callback for autosaving"""

        # NOTE: return True to activate next timeout callback
        
        if not self._auto_saving:
            return False

        if self.viewer.get_notebook() is not None:
            self.save_notebook(True)
            return self._app.pref.autosave
        else:
            return False
    

    def set_notebook(self, notebook):
        """Set the NoteBook for the window"""
        
        self.viewer.set_notebook(notebook)


    def update_index(self):
        """Update notebook index"""

        if not self.viewer.get_notebook():
            return

        self.end_auto_save()

        def update(task):
            # do search in another thread

            # erase database first
            # NOTE: I do this right now so that corrupt databases can be
            # cleared out of the way.
            self.viewer.get_notebook()._index.clear()

            for node in self.viewer.get_notebook()._index.index_all():
                # terminate if search is canceled
                if task.aborted():
                    break
            task.finish()

        # launch task
        self.wait_dialog(_("Indexing notebook"), _("Indexing..."),
                         tasklib.Task(update))

        self.begin_auto_save()


    #=====================================================
    # Notebook callbacks
    
    def on_notebook_node_changed(self, nodes, recurse):
        """Callback for when the notebook changes"""
        self.set_notebook_modified(True)
        
    
    def set_notebook_modified(self, modified):
        """Set the modification state of the notebook"""
        
        if self.viewer.get_notebook() is None:
            self.set_title(keepnote.PROGRAM_NAME)
        else:
            if modified:
                self.set_title("* %s" % self.viewer.get_notebook().get_title())
                self.set_status(_("Notebook modified"))
            else:
                self.set_title("%s" % self.viewer.get_notebook().get_title())
    

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
        

    def confirm_delete_nodes(self, nodes):
        """Confirm whether nodes should be deleted"""

        # TODO: move to app?
        # TODO: add note names to dialog
        # TODO: assume one node is selected
        node = nodes[0]

        if isinstance(node, NoteBookTrash):
            self.error(_("The Trash folder cannot be deleted."), None)
            return False
        elif node.get_parent() == None:
            self.error(_("The top-level folder cannot be deleted."), None)
            return False
        elif len(node.get_children()) > 0:
            message = _("Do you want to delete this note and all of its children?")
        else:
            message = _("Do you want to delete this note?")
        
        dialog = gtk.MessageDialog(self.get_toplevel(), 
            flags= gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_QUESTION, 
            buttons=gtk.BUTTONS_YES_NO, 
            message_format=message)

        response = dialog.run()
        dialog.destroy()
        
        return response == gtk.RESPONSE_YES


    def on_empty_trash(self):
        """Empty Trash folder in NoteBook"""
        
        if self.get_notebook() is None:
            return

        try:
            self.get_notebook().empty_trash()
        except NoteBookError, e:
            self.error(_("Could not empty trash."), e, sys.exc_info()[2])

        


    
    #=================================================
    # file attachments

    def on_attach_file(self, widget="focus"):

        if self.viewer.get_notebook() is None:
            return
        
        dialog = FileChooserDialog(
            _("Attach File..."), self, 
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Attach"), gtk.RESPONSE_OK),
            app=self._app,
            persistent_path="attach_file_path")
        dialog.set_default_response(gtk.RESPONSE_OK)

        # setup preview
        preview = gtk.Image()
        dialog.set_preview_widget(preview)
        dialog.connect("update-preview", update_file_preview, preview)

        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            if dialog.get_filename():
                self.attach_file(unicode_gtk(dialog.get_filename()), 
                                 widget=widget)

        dialog.destroy()


    def attach_file(self, filename, node=None, index=None, widget="focus"):
        
        # TODO: where does this belong?
        # could this be a convenience function for the notebook.
        
        if node is None:
            nodes, widget = self.get_selected_nodes(widget)
            node = nodes[0]

        # cannot attach directories (yet)
        if os.path.isdir(filename):
            return
            
        content_type = mimetypes.guess_type(filename)[0]
        if content_type is None:
            content_type = "application/octet-stream"
        
        new_filename = os.path.basename(filename)
        child = None

        try:
            path = notebooklib.get_valid_unique_filename(node.get_path(), 
                                                         new_filename)
            child = self.viewer.get_notebook().new_node(
                    content_type, 
                    path,
                    node,
                    {"payload_filename": new_filename,
                     "title": new_filename})
            child.create()
            node.add_child(child, index)
            child.set_payload(filename, new_filename)            
            child.save(True)
                
        except Exception, e:

            # remove child
            if child:
                child.delete()

            self.error(_("Error while attaching file '%s'." % filename),
                       e, sys.exc_info()[2])



    def on_view_node_external_app(self, app, node=None, kind=None):
        """View a node with an external app"""
        
        # TODO: try to clean up

        self.save_notebook()
        
        # determine node to view
        if node is None:
            nodes, widget = self.get_selected_nodes()
            if len(nodes) == 0:
                self.emit("error", _("No notes are selected."))
                return            
            node = nodes[0]

        try:
            if node.get_attr("content_type") == notebooklib.CONTENT_TYPE_PAGE:

                if kind == "dir":
                    filename = node.get_path()
                else:
                    # get html file
                    filename = node.get_data_file()

            elif node.get_attr("content_type") == notebooklib.CONTENT_TYPE_DIR:
                # get node dir
                filename = node.get_path()
                
            elif node.has_attr("payload_filename"):

                if kind == "dir":
                    filename = node.get_path()
                else:
                    # get payload file
                    filename = os.path.join(node.get_path(),
                                            node.get_attr("payload_filename"))
            else:
                raise KeepNoteError(_("Unable to dertermine note type."))
            

            self._app.run_external_app(app, os.path.realpath(filename))
        
        except KeepNoteError, e:
            self.emit("error", e.msg, e, sys.exc_info()[2])


    #=================================================
    # Image context menu

    # TODO: where does this belong?

    def view_image(self, image_filename):
        current_page = self.get_current_page()
        if current_page is None:
            return

        image_path = os.path.join(current_page.get_path(), image_filename)
        viewer = self._app.pref.get_external_app("image_viewer")
        
        if viewer is not None:
            try:
                proc = subprocess.Popen([viewer.prog, image_path])
            except OSError, e:
                self.emit("error", _("Could not open Image Viewer."), 
                           e, sys.exc_info()[2])
        else:
            self.emit("error", _("You must specify an Image Viewer in Application Options."))



    def _on_view_image(self, menuitem):
        """View image in Image Viewer"""
        
        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()
        self.view_image(image_filename)
        


    def _on_edit_image(self, menuitem):
        """Edit image in Image Editor"""

        current_page = self.get_current_page()
        if current_page is None:
            return
        
        # get image filename
        image_filename = menuitem.get_parent().get_child().get_filename()

        image_path = os.path.join(current_page.get_path(), image_filename)
        editor = self._app.pref.get_external_app("image_editor")
    
        if editor is not None:
            try:
                proc = subprocess.Popen([editor.prog, image_path])
            except OSError, e:
                self.emit("error", _("Could not open Image Editor."), e)
        else:
            self.emit("error", _("You must specify an Image Editor in Application Options."))


    def _on_resize_image(self, menuitem):
        """Resize image"""

        current_page = self.get_current_page()
        if current_page is None:
            return
        
        image = menuitem.get_parent().get_child()
        self.image_resize_dialog.on_resize(image)
        


    def _on_save_image_as(self, menuitem):
        """Save image as a new file"""

        current_page = self.get_current_page()
        if current_page is None:
            return
        
        # get image filename
        image = menuitem.get_parent().get_child()
        image_filename = image.get_filename()
        image_path = os.path.join(current_page.get_path(), image_filename)

        dialog = FileChooserDialog(
            _("Save Image As..."), self, 
            action=gtk.FILE_CHOOSER_ACTION_SAVE,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Save"), gtk.RESPONSE_OK),
            app=self._app,
            persistent_path="save_image_path")
        dialog.set_default_response(gtk.RESPONSE_OK)
        response = dialog.run()        

        if response == gtk.RESPONSE_OK:

            if not dialog.get_filename():
                self.emit("error", _("Must specify a filename for the image."))
            else:
                filename = unicode_gtk(dialog.get_filename())
                try:                
                    image.write(filename)
                except Exception, e:
                    self.error(_("Could not save image '%s'.") % filename)

        dialog.destroy()
    

    def make_image_menu(self, menu):
        """image context menu"""

        # TODO: where does this belong?
        # TODO: convert into UIManager?


        menu.set_accel_group(self.get_accel_group())
        menu.set_accel_path(CONTEXT_MENU_ACCEL_PATH)
        item = gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)
            
        # image/edit
        item = gtk.MenuItem(_("_View Image..."))
        item.connect("activate", self._on_view_image)
        item.child.set_markup_with_mnemonic(_("<b>_View Image...</b>"))
        item.show()
        menu.append(item)
        
        item = gtk.MenuItem(_("_Edit Image..."))
        item.connect("activate", self._on_edit_image)
        item.show()
        menu.append(item)

        item = gtk.MenuItem(_("_Resize Image..."))
        item.connect("activate", self._on_resize_image)
        item.show()
        menu.append(item)

        # image/save
        item = gtk.ImageMenuItem(_("_Save Image As..."))
        item.connect("activate", self._on_save_image_as)
        item.show()
        menu.append(item)

  

    #======================================================
    # Search

    # TODO: make a separate search widget.

    def on_search_nodes(self):
        """Search nodes"""

        # do nothing if notebook is not defined
        if not self.viewer.get_notebook():
            return

        # get words
        words = [x.lower() for x in
                 unicode_gtk(self.search_box.get_text()).strip().split()]
        
        # prepare search iterator
        nodes = keepnote.search.search_manual(self.viewer.get_notebook(), words)

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
        """Place cursor in search box"""
        self.search_box.grab_focus()


    def _on_search_box_text_changed(self, url_text):

        if not self._ignore_text:
            self.search_box_update_completion()

    def search_box_update_completion(self):

        text = unicode_gtk(self.search_box.get_text())
        
        self.search_box_list.clear()
        if len(text) > 0:
            results = self.viewer.get_notebook().search_node_titles(text)[:10]
            for nodeid, title in results:
                self.search_box_list.append([title, nodeid])

    def _on_search_box_completion_match(self, completion, model, iter):
        
        nodeid = model[iter][1]

        node = self.viewer.get_notebook().get_node_by_id(nodeid)
        if node:
            self.viewer.goto_node(node, False)
        

    
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
    

    #===================================================
    # Misc.

    def view_error_log(self):        
        """View error in text editor"""

        # windows locks open files
        # therefore we should copy error log before viewing it
        try:
            filename = os.path.realpath(keepnote.get_user_error_log())
            filename2 = filename + u".bak"
            shutil.copy(filename, filename2)        

            # use text editor to view error log
            self._app.run_external_app("text_editor", filename2)
        except Exception, e:
            self.error(_("Could not open error log") + ":\n" + str(e), 
                       e, sys.exc_info()[2])

    def view_config_files(self):        
        """View config folder in a file explorer"""

        try:
            # use text editor to view error log
            filename = keepnote.get_user_pref_dir()
            self._app.run_external_app("file_explorer", filename)
        except Exception, e:
            self.error(_("Could not open error log") + ":\n" + str(e), 
                       e, sys.exc_info()[2])



    
    #==================================================
    # Help/about dialog
    
    def on_about(self):
        """Display about dialog"""

        def func(dialog, link, data):
            try:
                self._app.open_webpage(link)
            except KeepNoteError, e:
                self.error(e.msg, e, sys.exc_info()[2])
        gtk.about_dialog_set_url_hook(func, None)
        
        
        about = gtk.AboutDialog()
        about.set_name(keepnote.PROGRAM_NAME)
        about.set_version(keepnote.PROGRAM_VERSION_TEXT)
        about.set_copyright(keepnote.COPYRIGHT)
        about.set_logo(get_resource_pixbuf("keepnote-icon.png"))
        about.set_website(keepnote.WEBSITE)
        about.set_license(keepnote.LICENSE_NAME)
        about.set_translator_credits(keepnote.TRANSLATOR_CREDITS)

        license_file = keepnote.get_resource(u"rc", u"COPYING")
        if os.path.exists(license_file):
            about.set_license(open(license_file).read())

        #about.set_authors(["Matt Rasmussen <rasmus@mit.edu>"])
        

        about.set_transient_for(self)
        about.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        about.connect("response", lambda d,r: about.destroy())
        about.show()


    def on_python_prompt(self):

        dialog = dialog_python.PythonDialog(self)
        dialog.show()
        

    #===========================================
    # Messages, warnings, errors UI/dialogs
    
    def set_status(self, text, bar="status"):
        """Sets a status message in the status bar"""
        
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
        self._app.error(text, error, tracebk)


    def wait_dialog(self, title, text, task):
        """Display a wait dialog"""

        dialog = dialog_wait.WaitDialog(self)
        dialog.show(title, text, task)       

        
    
    #================================================
    # Menus

    def get_actions(self):

        actions = map(lambda x: Action(*x),
                      [
            ("File", None, _("_File")),

            ("New Notebook", gtk.STOCK_NEW, _("_New Notebook..."),
             "", _("Start a new notebook"),
             lambda w: self.on_new_notebook()),
            
            ("Open Notebook", gtk.STOCK_OPEN, _("_Open Notebook..."),
             "<control>O", _("Open an existing notebook"),
             lambda w: self.on_open_notebook()),
            
            ("Open Recent Notebook", gtk.STOCK_OPEN, 
             _("Open Re_cent Notebook")),

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
            
            ("Export", None, _("_Export Notebook")),

            ("Import", None, _("_Import Notebook")),

            ("Quit", gtk.STOCK_QUIT, _("_Quit"),
             "<control>Q", _("Quit KeepNote"),
             lambda w: self.close()),

            #=======================================
            ("Edit", None, _("_Edit")),
            
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

            ("Attach File", gtk.STOCK_ADD, _("_Attach File..."),
             "", _("Attach a file to the notebook"),
             lambda w: self.on_attach_file()),

            ("Empty Trash", gtk.STOCK_DELETE, _("Empty _Trash"),
             "", None,
             lambda w: self.on_empty_trash()),
            
            #========================================
            ("Search", None, _("_Search")),
            
            ("Search All Notes", gtk.STOCK_FIND, _("_Search All Notes"),
             "<control>K", None,
             lambda w: self.focus_on_search_box()),

            #=======================================
            ("Go", None, _("_Go")),
            
            #========================================
            ("View", None, _("_View")),

            ("View Note in File Explorer", gtk.STOCK_OPEN,
             _("View Note in File Explorer"),
             "", None,
             lambda w: self.on_view_node_external_app("file_explorer", 
                                                      kind="dir")),
            
            ("View Note in Text Editor", gtk.STOCK_OPEN,
             _("View Note in Text Editor"),
             "", None,
             lambda w: self.on_view_node_external_app("text_editor",
                                                      kind="page")),

            ("View Note in Web Browser", gtk.STOCK_OPEN,
             _("View Note in Web Browser"),
             "", None,
             lambda w: self.on_view_node_external_app("web_browser",
                                                      kind="page")),

            ("Open File", gtk.STOCK_OPEN,
             _("_Open File"),
             "", None,
             lambda w: self.on_view_node_external_app("file_launcher",
                                                      kind="file")),


            #=========================================
            ("Tools", None, _("_Tools")),

            ("Update Notebook Index", None, _("_Update Notebook Index"),
             "", None,
             lambda w: self.update_index()),
            
            ("KeepNote Preferences", gtk.STOCK_PREFERENCES, _("_Preferences"),
             "", None,
             lambda w: self._app.app_options_dialog.show(self)),

            #=========================================
            ("Help", None, _("_Help")),
            
            ("View Error Log...", gtk.STOCK_DIALOG_ERROR, _("View _Error Log..."),
             "", None,
             lambda w: self.view_error_log()),

            ("View Preference Files...", None, _("View Preference Files..."), "", None,
             lambda w: self.view_config_files()),
            
            ("Drag and Drop Test...", None, _("Drag and Drop Test..."),
             "", None,
             lambda w: self.drag_test.on_drag_and_drop_test()),

            ("Python Prompt...", None, _("Python Prompt..."),
             "", None,
             lambda w: self.on_python_prompt()),
            
            ("About", gtk.STOCK_ABOUT, _("_About"),
             "", None,
             lambda w: self.on_about())
            ]) +  [

            Action("Main Spacer Tool"),
            Action("Search Box Tool", None, None, "", _("Search All Notes")),
            Action("Search Button Tool", gtk.STOCK_FIND, None, "", 
                   _("Search All Notes"),
                   lambda w: self.on_search_nodes())]


        # make sure recent notebooks is always visible
        recent = [x for x in actions 
                  if x.get_property("name") == "Open Recent Notebook"][0]
        recent.set_property("is-important", True)

        return actions

    def setup_menus(self, uimanager):
        pass

    def get_ui(self):

        return ["""
<ui>

<!-- main window menu bar -->
<menubar name="main_menu_bar">
  <menu action="File">
     <menuitem action="New Notebook"/>
     <placeholder name="Viewer"/>
     <separator/>
     <menuitem action="Open Notebook"/>
     <menuitem action="Open Recent Notebook"/>
     <menuitem action="Reload Notebook"/>
     <menuitem action="Save Notebook"/>
     <menuitem action="Close Notebook"/>
     <menuitem action="Empty Trash"/>
     <separator/>
     <menu action="Export">
     </menu>
     <menu action="Import">
     </menu>
     <separator/>
     <placeholder name="Extensions"/>
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
    <placeholder name="Viewer"/>
    <separator/>
    <menuitem action="KeepNote Preferences"/>
  </menu>

  <menu action="Search">
    <menuitem action="Search All Notes"/>
    <placeholder name="Viewer"/>
  </menu>

  <placeholder name="Viewer"/>

  <menu action="Go">
    <placeholder name="Viewer"/>
  </menu>

  <menu action="Tools">
    <placeholder name="Viewer"/>
    <menuitem action="Update Notebook Index"/>
  </menu>

  <menu action="Help">
    <menuitem action="View Error Log..."/>
    <menuitem action="View Preference Files..."/>
    <menuitem action="Drag and Drop Test..."/>
    <menuitem action="Python Prompt..."/>
    <separator/>
    <menuitem action="About"/>
  </menu>
</menubar>

<!-- main window tool bar -->
<toolbar name="main_tool_bar">
  <placeholder name="Viewer"/>
  <toolitem action="Main Spacer Tool"/>
  <toolitem action="Search Box Tool"/>
  <toolitem action="Search Button Tool"/>
</toolbar>
</ui>
"""]

    
    def make_menubar(self):
        """Initialize the menu bar"""

        #===============================
        # ui manager

        self._actiongroup = gtk.ActionGroup('MainWindow')
        self._uimanager.insert_action_group(self._actiongroup, 0)

        # setup menus
        add_actions(self._actiongroup, self.get_actions())
        for s in self.get_ui():
            self._uimanager.add_ui_from_string(s)
        self.setup_menus(self._uimanager)

        # return menu bar
        menubar = self._uimanager.get_widget('/main_menu_bar')
        

        return menubar
       
            

    
    def make_toolbar(self):
        
        # configure toolbar
        toolbar = self._uimanager.get_widget('/main_tool_bar')
        toolbar.set_orientation(gtk.ORIENTATION_HORIZONTAL)
        toolbar.set_style(gtk.TOOLBAR_ICONS)
        toolbar.set_border_width(0)

        try:
            # NOTE: if this version of GTK doesn't have this size, then
            # ignore it
            toolbar.set_property("icon-size", gtk.ICON_SIZE_SMALL_TOOLBAR)
        except:
            pass
        
        
        # separator (is there a better way to do this?)
        spacer = self._uimanager.get_widget("/main_tool_bar/Main Spacer Tool")
        spacer.remove(spacer.child)
        spacer.set_expand(True)


        # search box
        self.search_box = gtk.Entry()
        self.search_box.connect("changed", self._on_search_box_text_changed)
        self.search_box.connect("activate",
                                lambda w: self.on_search_nodes())        

        self.search_box_list = gtk.ListStore(gobject.TYPE_STRING, 
                                             gobject.TYPE_STRING)
        self.search_box_completion = gtk.EntryCompletion()
        self.search_box_completion.connect("match-selected", 
                                           self._on_search_box_completion_match)
        self.search_box_completion.set_match_func(lambda c, k, i: True)
        self.search_box_completion.set_model(self.search_box_list)
        self.search_box_completion.set_text_column(0)
        self.search_box.set_completion(self.search_box_completion)
        self.search_box.show()
        self._ignore_text = False
        w = self._uimanager.get_widget("/main_tool_bar/Search Box Tool")
        w.remove(w.child)
        w.add(self.search_box)
                        
        return toolbar


gobject.type_register(KeepNoteWindow)
gobject.signal_new("error", KeepNoteWindow, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object))
