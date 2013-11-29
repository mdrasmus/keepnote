"""

    KeepNote
    Graphical User Interface for KeepNote Application

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
#  Author: Matt Rasmussen <rasmus@alum.mit.edu>
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
import os
import shutil
import sys
import uuid

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
    NoteBookError
from keepnote import notebook as notebooklib
from keepnote import tasklib
from keepnote.gui import \
    get_resource_pixbuf, \
    Action, \
    add_actions, \
    FileChooserDialog, \
    init_key_shortcuts, \
    UIManager

from keepnote.gui import \
    dialog_drag_drop_test, \
    dialog_wait
from keepnote.gui.tabbed_viewer import TabbedViewer


_ = keepnote.translate

#=============================================================================
# constants

DEFAULT_WINDOW_SIZE = (1024, 600)
DEFAULT_WINDOW_POS = (-1, -1)


#=============================================================================


class KeepNoteWindow (gtk.Window):
    """Main windows for KeepNote"""

    def __init__(self, app, winid=None):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)

        self._app = app  # application object
        self._winid = winid if winid else unicode(uuid.uuid4())
        self._viewers = []

        # window state
        self._maximized = False      # True if window is maximized
        self._was_maximized = False  # True if iconified and was maximized
        self._iconified = False      # True if window is minimized
        self._tray_icon = None       # True if tray icon is present
        self._recent_notebooks = []

        self._uimanager = UIManager()
        self._accel_group = self._uimanager.get_accel_group()
        self.add_accel_group(self._accel_group)

        init_key_shortcuts()
        self.init_layout()
        self.setup_systray()

        # load preferences for the first time
        self.load_preferences(True)

    def get_id(self):
        return self._winid

    def init_layout(self):
        # init main window
        self.set_title(keepnote.PROGRAM_NAME)
        self.set_default_size(*DEFAULT_WINDOW_SIZE)
        self.set_icon_list(get_resource_pixbuf("keepnote-16x16.png"),
                           get_resource_pixbuf("keepnote-32x32.png"),
                           get_resource_pixbuf("keepnote-64x64.png"))

        # main window signals
        self.connect("error", lambda w, m, e, t: self.error(m, e, t))
        self.connect("delete-event", lambda w, e: self._on_close())
        self.connect("window-state-event", self._on_window_state)
        self.connect("size-allocate", self._on_window_size)
        #self._app.pref.changed.add(self._on_app_options_changed)

        #====================================
        # Dialogs

        self.drag_test = dialog_drag_drop_test.DragDropTestDialog(self)

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
                self._tray_icon.set_from_pixbuf(
                    get_resource_pixbuf("keepnote-32x32.png"))
                self._tray_icon.set_tooltip(keepnote.PROGRAM_NAME)
                self._statusicon_menu = self.make_statusicon_menu()
                self._tray_icon.connect("activate",
                                        self._on_tray_icon_activate)
                self._tray_icon.connect('popup-menu',
                                        self._on_systray_popup_menu)

            self._tray_icon.set_property(
                "visible", self._app.pref.get("window", "use_systray",
                                              default=True))

        else:
            self._tray_icon = None

    def _on_systray_popup_menu(self, status, button, time):
        self._statusicon_menu.popup(None, None, None, button, time)

    #==============================================
    # viewers

    def new_viewer(self):
        """Creates a new viewer for this window"""

        #viewer = ThreePaneViewer(self._app, self)
        viewer = TabbedViewer(self._app, self)
        viewer.connect("error", lambda w, m, e: self.error(m, e, None))
        viewer.connect("status", lambda w, m, b: self.set_status(m, b))
        viewer.connect("window-request", self._on_window_request)
        viewer.connect("current-node", self._on_current_node)
        viewer.connect("modified", self._on_viewer_modified)

        return viewer

    def add_viewer(self, viewer):
        """Adds a viewer to the window"""
        self._viewers.append(viewer)

    def remove_viewer(self, viewer):
        """Removes a viewer from the window"""
        self._viewers.remove(viewer)

    def get_all_viewers(self):
        """Returns list of all viewers associated with window"""
        return self._viewers

    def get_all_notebooks(self):
        """Returns all notebooks loaded by all viewers"""
        return set(filter(lambda n: n is not None,
                          (v.get_notebook() for v in self._viewers)))

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

    def get_current_node(self):
        """Returns the currently selected node"""
        return self.viewer.get_current_node()

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
            self._app.pref.get("window")["window_size"] = self.get_size()

    #def _on_app_options_changed(self):
    #    self.load_preferences()

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

    def on_new_window(self):
        """Open a new window"""
        win = self._app.new_window()
        notebook = self.get_notebook()
        if notebook:
            self._app.ref_notebook(notebook)
            win.set_notebook(notebook)

    #==============================================
    # Application preferences

    def load_preferences(self, first_open=False):
        """Load preferences"""
        p = self._app.pref

        # notebook
        window_size = p.get("window", "window_size",
                            default=DEFAULT_WINDOW_SIZE)
        window_maximized = p.get("window", "window_maximized", default=True)

        self.setup_systray()
        use_systray = p.get("window", "use_systray", default=True)

        # window config for first open
        if first_open:
            self.resize(*window_size)
            if window_maximized:
                self.maximize()

            minimize = p.get("window", "minimize_on_start", default=False)
            if use_systray and minimize:
                self.iconify()

        # config window
        skip = p.get("window", "skip_taskbar", default=False)
        if use_systray:
            self.set_property("skip-taskbar-hint", skip)

        self.set_keep_above(p.get("window", "keep_above", default=False))

        if p.get("window", "stick", default=False):
            self.stick()
        else:
            self.unstick()

        # other window wide properties
        self._recent_notebooks = p.get("recent_notebooks", default=[])
        self.set_recent_notebooks_menu(self._recent_notebooks)

        self._uimanager.set_force_stock(
            p.get("look_and_feel", "use_stock_icons", default=False))
        self.viewer.load_preferences(self._app.pref, first_open)

    def save_preferences(self):
        """Save preferences"""
        p = self._app.pref

        # save window preferences
        p.set("window", "window_maximized", self._maximized)
        p.set("recent_notebooks", self._recent_notebooks)

        # let viewer save preferences
        self.viewer.save_preferences(self._app.pref)

    def set_recent_notebooks_menu(self, recent_notebooks):
        """Set the recent notebooks in the file menu"""
        menu = self._uimanager.get_widget(
            "/main_menu_bar/File/Open Recent Notebook")

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

        if filename in self._recent_notebooks:
            self._recent_notebooks.remove(filename)

        self._recent_notebooks = [filename] + \
            self._recent_notebooks[:keepnote.gui.MAX_RECENT_NOTEBOOKS]

        self.set_recent_notebooks_menu(self._recent_notebooks)

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

        dialog = gtk.FileChooserDialog(
            _("Open Notebook"), self,
            action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Open"), gtk.RESPONSE_OK))

        def on_folder_changed(filechooser):
            folder = unicode_gtk(filechooser.get_current_folder())
            if os.path.exists(os.path.join(folder, notebooklib.PREF_FILE)):
                filechooser.response(gtk.RESPONSE_OK)

        dialog.connect("current-folder-changed", on_folder_changed)

        path = self._app.get_default_path("new_notebook_path")
        if os.path.exists(path):
            dialog.set_current_folder(path)

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

            path = ensure_unicode(dialog.get_current_folder(), FS_ENCODING)
            if path:
                self._app.pref.set("default_paths", "new_notebook_path",
                                   os.path.dirname(path))

            notebook_file = ensure_unicode(dialog.get_filename(), FS_ENCODING)
            if notebook_file:
                self.open_notebook(notebook_file)

        dialog.destroy()

    def on_open_notebook_url(self):
        """Launches Open NoteBook from URL dialog"""
        dialog = gtk.Dialog("Open Notebook from URL", self,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT)

        p = dialog.get_content_area()

        h = gtk.HBox()
        h.show()
        p.pack_start(h, expand=False, fill=True, padding=0)

        # url label
        l = gtk.Label("URL: ")
        l.show()
        h.pack_start(l, expand=False, fill=True, padding=0)

        # url entry
        entry = gtk.Entry()
        entry.set_width_chars(80)
        entry.connect("activate", lambda w:
                      dialog.response(gtk.RESPONSE_OK))
        entry.show()
        h.pack_start(entry, expand=True, fill=True, padding=0)

        # actions
        dialog.add_button("_Cancel", gtk.RESPONSE_CANCEL)
        dialog.add_button("_Open", gtk.RESPONSE_OK)

        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            url = unicode_gtk(entry.get_text())
            if url:
                self.open_notebook(url)

        dialog.destroy()

    def _on_close(self):
        """Callback for window close"""
        try:
            # TODO: decide if a clipboard action is needed before
            # closing down.
            #clipboard = self.get_clipboard(selection=CLIPBOARD_NAME)
            #clipboard.set_can_store(None)
            #clipboard.store()

            self._app.save()
            self.close_notebook()
            if self._tray_icon:
                # turn off try icon
                self._tray_icon.set_property("visible", False)

        except Exception, e:
            self.error("Error while closing", e, sys.exc_info()[2])

        return False

    def close(self):
        """Close the window"""
        self._on_close()
        self.emit("delete-event", None)
        self.destroy()

    def on_quit(self):
        """Quit the application"""
        self._app.save()
        self._app.quit()

    #===============================================
    # Notebook actions

    def save_notebook(self, silent=False):
        """Saves the current notebook"""
        try:
            # save window information for all notebooks associated with this
            # window
            for notebook in self.get_all_notebooks():
                p = notebook.pref.get("windows", "ids", define=True)
                p[self._winid] = {
                    "viewer_type": self.viewer.get_name(),
                    "viewerid": self.viewer.get_id()}

            # let the viewer save its information
            self.viewer.save()
            self.set_status(_("Notebook saved"))

        except Exception, e:
            if not silent:
                self.error(_("Could not save notebook."), e, sys.exc_info()[2])
                self.set_status(_("Error saving notebook"))
                return

    def reload_notebook(self):
        """Reload the current NoteBook"""

        notebook = self.viewer.get_notebook()
        if notebook is None:
            self.error(_("Reloading only works when a notebook is open."))
            return

        filename = notebook.get_filename()
        self._app.close_all_notebook(notebook, False)
        self.open_notebook(filename)

        self.set_status(_("Notebook reloaded"))

    def new_notebook(self, filename):
        """Creates and opens a new NoteBook"""
        if self.viewer.get_notebook() is not None:
            self.close_notebook()

        try:
            # make sure filename is unicode
            filename = ensure_unicode(filename, FS_ENCODING)
            notebook = notebooklib.NoteBook()
            notebook.create(filename)
            notebook.set_attr("title", os.path.basename(filename))
            notebook.close()
            self.set_status(_("Created '%s'") % notebook.get_title())
        except NoteBookError, e:
            self.error(_("Could not create new notebook."),
                       e, sys.exc_info()[2])
            self.set_status("")
            return None

        return self.open_notebook(filename, new=True)

    def _load_notebook(self, filename):
        """Loads notebook in background with progress bar"""
        notebook = self._app.get_notebook(filename, self)
        if notebook is None:
            return None

        # check for indexing
        # TODO: is this the best place for checking?
        # There is a difference between normal incremental indexing
        # and indexing due version updating.
        # incremental updating (checking a few files that have changed on
        # disk) should be done within notebook.load().
        # Whole notebook re-indexing, triggered by version upgrade
        # should be done separately, and with a different wait dialog
        # clearly indicating that notebook loading is going to take
        # longer than usual.
        if notebook.index_needed():
            self.update_index(notebook)

        return notebook

    def _restore_windows(self, notebook, open_here=True):
        """
        Restore multiple windows for notebook

        open_here -- if True, will open notebook in this window


        Cases:
        1. if notebook has no saved windows, just open notebook in this window
        2. if notebook has 1 saved window
           if open_here:
             open it in this window
           else:
             if this window has no opened notebooks,
                reassign its ids to the notebook and open it here
             else
                reassign notebooks saved ids to this window and viewer
        3. if notebook has >1 saved windows, open them in their own windows
           if this window has no notebook, reassign its id to one of the
           saved ids.

        """
        # init window lookup
        win_lookup = dict((w.get_id(), w) for w in
                          self._app.get_windows())

        def open_in_window(winid, viewerid, notebook):
            win = win_lookup.get(winid, None)
            if win is None:
                # open new window
                win = self._app.new_window()
                win_lookup[winid] = win
                win._winid = winid
                if viewerid:
                    win.get_viewer().set_id(viewerid)

            # set notebook
            self._app.ref_notebook(notebook)
            win.set_notebook(notebook)

        # find out how many windows this notebook had last time
        # init viewer if needed
        windows = notebook.pref.get("windows", "ids", define=True)
        notebook.pref.get("viewers", "ids", define=True)

        if len(windows) == 0:
            # no presistence info found, just open notebook in this window
            self.set_notebook(notebook)

        elif len(windows) == 1:
            # restore a single window
            winid, winpref = windows.items()[0]
            viewerid = winpref.get("viewerid", None)

            if viewerid is not None:
                if len(self.get_all_notebooks()) == 0:
                    # no notebooks are open, so it is ok to reassign
                    # the viewer's id to match the notebook pref
                    self._winid = winid
                    self.viewer.set_id(viewerid)
                    self.set_notebook(notebook)
                elif open_here:
                    # TODO: needs more testing

                    # notebooks are open, so reassign the notebook's pref to
                    # match the existing viewer
                    notebook.pref.set(
                        "windows", "ids",
                        {self._winid:
                         {"viewerid": self.viewer.get_id(),
                          "viewer_type": self.viewer.get_name()}})
                    notebook.pref.set(
                        "viewers", "ids", self.viewer.get_id(),
                        notebook.pref.get("viewers", "ids", viewerid,
                                          define=True))
                    del notebook.pref.get("viewers", "ids")[viewerid]
                    self.set_notebook(notebook)
                else:
                    # open in whatever window the notebook wants
                    open_in_window(winid, viewerid, notebook)
                    self._app.unref_notebook(notebook)

        elif len(windows) > 1:
            # get different kinds of window ids
            restoring_ids = set(windows.keys())
            #new_ids = restoring_ids - set(win_lookup.keys())

            if len(self.get_all_notebooks()) == 0:
                # special case: if no notebooks opened, then make sure
                # to reuse this window

                if self._winid not in restoring_ids:
                    self._winid = iter(restoring_ids).next()

                restoring_ids.remove(self._winid)
                viewerid = windows[self._winid].get("viewerid", None)
                if viewerid:
                    self.viewer.set_id(viewerid)
                self.set_notebook(notebook)

            # restore remaining windows
            while len(restoring_ids) > 0:
                winid = restoring_ids.pop()
                viewerid = windows[winid].get("viewerid", None)
                open_in_window(winid, viewerid, notebook)
            self._app.unref_notebook(notebook)

    def open_notebook(self, filename, new=False, open_here=True):
        """Opens a new notebook"""

        #try:
        #    filename = notebooklib.normalize_notebook_dirname(
        #        filename, longpath=False)
        #except Exception, e:
        #    self.error(_("Could note find notebook '%s'.") % filename, e,
        #               sys.exc_info()[2])
        #    notebook = None
        #else:

        notebook = self._load_notebook(filename)
        if notebook is None:
            return

        # setup notebook
        self._restore_windows(notebook, open_here=open_here)

        if not new:
            self.set_status(_("Loaded '%s'") % notebook.get_title())
        self.update_title()

        # save notebook to recent notebooks
        self.add_recent_notebook(filename)

        return notebook

    def close_notebook(self, notebook=None):
        """Close the NoteBook"""
        if notebook is None:
            notebook = self.get_notebook()

        self.viewer.close_notebook(notebook)
        self.set_status(_("Notebook closed"))

    def _on_close_notebook(self, notebook):
        """Callback when notebook is closing"""
        pass

    def set_notebook(self, notebook):
        """Set the NoteBook for the window"""
        self.viewer.set_notebook(notebook)

    def update_index(self, notebook=None, clear=False):
        """Update notebook index"""

        if notebook is None:
            notebook = self.viewer.get_notebook()
        if notebook is None:
            return

        def update(task):
            # erase database first
            # NOTE: I do this right now so that corrupt databases can be
            # cleared out of the way.
            if clear:
                notebook.clear_index()

            try:
                for node in notebook.index_all():
                    # terminate if search is canceled
                    if task.aborted():
                        break
            except Exception, e:
                self.error(_("Error during index"), e, sys.exc_info()[2])
            task.finish()

        # launch task
        self.wait_dialog(_("Indexing notebook"), _("Indexing..."),
                         tasklib.Task(update))

    def compact_index(self, notebook=None):
        """Update notebook index"""
        if notebook is None:
            notebook = self.viewer.get_notebook()
        if notebook is None:
            return

        def update(task):
            notebook.index("compact")

        # launch task
        self.wait_dialog(_("Compacting notebook index"), _("Compacting..."),
                         tasklib.Task(update))

    #=====================================================
    # viewer callbacks

    def update_title(self, node=None):
        """Set the modification state of the notebook"""
        notebook = self.viewer.get_notebook()

        if notebook is None:
            self.set_title(keepnote.PROGRAM_NAME)
        else:
            title = notebook.get_attr("title", u"")
            if node is None:
                node = self.get_current_node()
            if node is not None:
                title += u": " + node.get_attr("title", "")

            modified = notebook.save_needed()
            if modified:
                self.set_title(u"* %s" % title)
                self.set_status(_("Notebook modified"))
            else:
                self.set_title(title)

    def _on_current_node(self, viewer, node):
        """Callback for when viewer changes the current node"""
        self.update_title(node)

    def _on_viewer_modified(self, viewer, modified):
        """Callback for when viewer has a modified notebook"""
        self.update_title()

    #===========================================================
    # page and folder actions

    def get_selected_nodes(self):
        """
        Returns list of selected nodes
        """
        return self.viewer.get_selected_nodes()

    def confirm_delete_nodes(self, nodes):
        """Confirm whether nodes should be deleted"""

        # TODO: move to app?
        # TODO: add note names to dialog
        # TODO: assume one node is selected
        # could make this a stand alone function/dialog box

        for node in nodes:
            if node.get_attr("content_type") == notebooklib.CONTENT_TYPE_TRASH:
                self.error(_("The Trash folder cannot be deleted."), None)
                return False
            if node.get_parent() is None:
                self.error(_("The top-level folder cannot be deleted."), None)
                return False

        if len(nodes) > 1 or len(nodes[0].get_children()) > 0:
            message = _(
                "Do you want to delete this note and all of its children?")
        else:
            message = _("Do you want to delete this note?")

        return self._app.ask_yes_no(message, _("Delete Note"),
                                    parent=self.get_toplevel())

    def on_empty_trash(self):
        """Empty Trash folder in NoteBook"""

        if self.get_notebook() is None:
            return

        try:
            self.get_notebook().empty_trash()
        except NoteBookError, e:
            self.error(_("Could not empty trash."), e, sys.exc_info()[2])

    #=================================================
    # action callbacks

    def on_view_node_external_app(self, app, node=None, kind=None):
        """View a node with an external app"""

        self._app.save()

        # determine node to view
        if node is None:
            nodes = self.get_selected_nodes()
            if len(nodes) == 0:
                self.emit("error", _("No notes are selected."), None, None)
                return
            node = nodes[0]

        try:
            self._app.run_external_app_node(app, node, kind)
        except KeepNoteError, e:
            self.emit("error", e.msg, e, sys.exc_info()[2])

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

    def on_copy_tree(self):
        """Copy tree callback"""
        widget = self.get_focus()
        if gobject.signal_lookup("copy-tree-clipboard", widget) != 0:
            widget.emit("copy-tree-clipboard")

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

        #about.set_authors(["Matt Rasmussen <rasmus@alum.mit.edu>"])

        about.set_transient_for(self)
        about.set_position(gtk.WIN_POS_CENTER_ON_PARENT)
        about.connect("response", lambda d, r: about.destroy())
        about.show()

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

    def wait_dialog(self, title, text, task, cancel=True):
        """Display a wait dialog"""

        # NOTE: pause autosave while performing long action

        self._app.pause_auto_save(True)

        dialog = dialog_wait.WaitDialog(self)
        dialog.show(title, text, task, cancel=cancel)

        self._app.pause_auto_save(False)

    #================================================
    # Menus

    def get_actions(self):
        actions = map(
            lambda x: Action(*x),
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
                 lambda w: self._app.save()),

                ("Close Notebook", gtk.STOCK_CLOSE, _("_Close Notebook"),
                 "", _("Close the current notebook"),
                 lambda w: self._app.close_all_notebook(self.get_notebook())),

                ("Empty Trash", gtk.STOCK_DELETE, _("Empty _Trash"),
                 "", None,
                 lambda w: self.on_empty_trash()),

                ("Export", None, _("_Export Notebook")),

                ("Import", None, _("_Import Notebook")),

                ("Quit", gtk.STOCK_QUIT, _("_Quit"),
                 "<control>Q", _("Quit KeepNote"),
                 lambda w: self.on_quit()),

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

                ("Copy Tree", gtk.STOCK_COPY, None,
                 "<control><shift>C", None,
                 lambda w: self.on_copy_tree()),

                ("Paste", gtk.STOCK_PASTE, None,
                 "<control>V", None,
                 lambda w: self.on_paste()),

                ("KeepNote Preferences", gtk.STOCK_PREFERENCES,
                 _("_Preferences"),
                 "", None,
                 lambda w: self._app.app_options_dialog.show(self)),

                #========================================
                ("Search", None, _("_Search")),

                ("Search All Notes", gtk.STOCK_FIND, _("_Search All Notes"),
                 "<control>K", None,
                 lambda w: self.search_box.grab_focus()),

                #=======================================
                ("Go", None, _("_Go")),

                #========================================
                ("View", None, _("_View")),

                ("View Note As", gtk.STOCK_OPEN, _("_View Note As")),

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
                 lambda w: self.update_index(clear=True)),

                ("Compact Notebook Index", None, _("_Compact Notebook Index"),
                 "", None,
                 lambda w: self.compact_index()),

                ("Open Notebook URL", None, _("_Open Notebook from URL"),
                 "", None,
                 lambda w: self.on_open_notebook_url()),

                #=========================================
                ("Window", None, _("Window")),

                ("New Window", None, _("New Window"),
                 "", _("Open a new window"),
                 lambda w: self.on_new_window()),

                ("Close Window", None, _("Close Window"),
                 "", _("Close window"),
                 lambda w: self.close()),

                #=========================================
                ("Help", None, _("_Help")),

                ("View Error Log...", gtk.STOCK_DIALOG_ERROR,
                 _("View _Error Log..."),
                 "", None,
                 lambda w: self.view_error_log()),

                ("View Preference Files...", None,
                 _("View Preference Files..."), "", None,
                 lambda w: self.view_config_files()),

                ("Drag and Drop Test...", None, _("Drag and Drop Test..."),
                 "", None,
                 lambda w: self.drag_test.on_drag_and_drop_test()),

                ("About", gtk.STOCK_ABOUT, _("_About"),
                 "", None,
                 lambda w: self.on_about())
                ]) + [

            Action("Main Spacer Tool"),
            Action("Search Box Tool", None, None, "", _("Search All Notes")),
            Action("Search Button Tool", gtk.STOCK_FIND, None, "",
                   _("Search All Notes"),
                   lambda w: self.search_box.on_search_nodes())]

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
     <placeholder name="New"/>
     <separator/>
     <menuitem action="Open Notebook"/>
     <menuitem action="Open Recent Notebook"/>
     <menuitem action="Save Notebook"/>
     <menuitem action="Close Notebook"/>
     <menuitem action="Reload Notebook"/>
     <menuitem action="Empty Trash"/>
     <separator/>
     <menu action="Export" />
     <menu action="Import" />
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
    <menuitem action="Copy Tree"/>
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
    <menuitem action="Compact Notebook Index"/>
    <menuitem action="Open Notebook URL"/>
    <placeholder name="Extensions"/>
  </menu>

  <menu action="Window">
     <menuitem action="New Window"/>
     <menuitem action="Close Window"/>
     <placeholder name="Viewer Window"/>
  </menu>

  <menu action="Help">
    <menuitem action="View Error Log..."/>
    <menuitem action="View Preference Files..."/>
    <menuitem action="Drag and Drop Test..."/>
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

<!-- popup menus -->
<menubar name="popup_menus">
</menubar>

</ui>
"""]

    def get_actions_statusicon(self):
        """Set actions for StatusIcon menu and return."""
        actions = map(
            lambda x: Action(*x),
            [("KeepNote Preferences", gtk.STOCK_PREFERENCES,
              _("_Preferences"),
              "", None,
              lambda w: self._app.app_options_dialog.show(self)),
             ("Quit", gtk.STOCK_QUIT, _("_Quit"),
              "<control>Q", _("Quit KeepNote"),
              lambda w: self.close()),
             ("About", gtk.STOCK_ABOUT, _("_About"),
              "", None,
              lambda w: self.on_about())
             ])

        return actions

    def get_ui_statusicon(self):
        """Create UI xml-definition for StatusIcon menu and return."""
        return ["""
<ui>
  <!-- statusicon_menu -->
  <popup name="statusicon_menu">
    <menuitem action="KeepNote Preferences"/>
    <menuitem action="About"/>
    <separator/>
    <menuitem action="Quit"/>
  </popup>
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
        self.search_box = SearchBox(self)
        self.search_box.show()
        w = self._uimanager.get_widget("/main_tool_bar/Search Box Tool")
        w.remove(w.child)
        w.add(self.search_box)

        return toolbar

    def make_statusicon_menu(self):
        """Initialize the StatusIcon menu."""

        #===============================
        # ui manager

        self._actiongroup_statusicon = gtk.ActionGroup('StatusIcon')
        self._tray_icon.uimanager = gtk.UIManager()
        self._tray_icon.uimanager.insert_action_group(
            self._actiongroup_statusicon, 0)

        # setup menu
        add_actions(self._actiongroup_statusicon,
                    self.get_actions_statusicon())
        for s in self.get_ui_statusicon():
            self._tray_icon.uimanager.add_ui_from_string(s)
        self.setup_menus(self._tray_icon.uimanager)

        # return menu
        statusicon_menu = self._tray_icon.uimanager.get_widget(
            '/statusicon_menu')

        return statusicon_menu


gobject.type_register(KeepNoteWindow)
gobject.signal_new("error", KeepNoteWindow, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (str, object, object))


class SearchBox (gtk.Entry):

    def __init__(self, window):
        gtk.Entry.__init__(self)

        self._window = window

        self.connect("changed", self._on_search_box_text_changed)
        self.connect("activate", lambda w: self.on_search_nodes())

        self.search_box_list = gtk.ListStore(gobject.TYPE_STRING,
                                             gobject.TYPE_STRING)
        self.search_box_completion = gtk.EntryCompletion()
        self.search_box_completion.connect(
            "match-selected", self._on_search_box_completion_match)
        self.search_box_completion.set_match_func(lambda c, k, i: True)
        self.search_box_completion.set_model(self.search_box_list)
        self.search_box_completion.set_text_column(0)
        self.set_completion(self.search_box_completion)

    def on_search_nodes(self):
        """Search nodes"""

        # do nothing if notebook is not defined
        if not self._window.get_notebook():
            return

        # TODO: add parsing grammar
        # get words
        words = [x.lower() for x in
                 unicode_gtk(self.get_text()).strip().split()]

        # clear listview
        self._window.get_viewer().start_search_result()

        # queue for sending results between threads
        from threading import Lock
        from Queue import Queue
        queue = Queue()
        lock = Lock()  # a mutex for the notebook (protect sqlite)

        # update gui with search result
        def search(task):
            alldone = Lock()  # ensure gui and background sync up at end
            alldone.acquire()

            def gui_update():
                lock.acquire()
                more = True

                try:
                    maxstep = 20
                    for i in xrange(maxstep):
                        # check if search is aborted
                        if task.aborted():
                            more = False
                            break

                        # skip if queue is empty
                        if queue.empty():
                            break
                        node = queue.get()

                        # no more nodes left, finish
                        if node is None:
                            more = False
                            break

                        # add result to gui
                        self._window.get_viewer().add_search_result(node)

                except Exception, e:
                    self._window.error(_("Unexpected error"), e)
                    more = False
                finally:
                    lock.release()

                if not more:
                    alldone.release()
                return more
            gobject.idle_add(gui_update)

            # init search
            notebook = self._window.get_notebook()
            try:
                nodes = (notebook.get_node_by_id(nodeid)
                         for nodeid in
                         notebook.search_node_contents(" ".join(words))
                         if nodeid)
            except:
                keepnote.log_error()

            # do search in thread
            try:
                lock.acquire()
                for node in nodes:
                    if task.aborted():
                        break
                    lock.release()
                    if node:
                        queue.put(node)
                    lock.acquire()
                lock.release()
                queue.put(None)
            except Exception, e:
                self.error(_("Unexpected error"), e)

            # wait for gui thread to finish
            # NOTE: if task is aborted, then gui_update stops itself for
            # some reason, thus no need to acquire alldone.
            if not task.aborted():
                alldone.acquire()

        # launch task
        task = tasklib.Task(search)
        self._window.wait_dialog(
            _("Searching notebook"), _("Searching..."), task)
        if task.exc_info()[0]:
            e, t, tr = task.exc_info()
            keepnote.log_error(e, tr)

        self._window.get_viewer().end_search_result()

    def focus_on_search_box(self):
        """Place cursor in search box"""
        self.grab_focus()

    def _on_search_box_text_changed(self, url_text):

        self.search_box_update_completion()

    def search_box_update_completion(self):

        if not self._window.get_notebook():
            return

        text = unicode_gtk(self.get_text())

        self.search_box_list.clear()
        if len(text) > 0:
            results = self._window.get_notebook().search_node_titles(text)[:10]
            for nodeid, title in results:
                self.search_box_list.append([title, nodeid])

    def _on_search_box_completion_match(self, completion, model, iter):

        if not self._window.get_notebook():
            return

        nodeid = model[iter][1]

        node = self._window.get_notebook().get_node_by_id(nodeid)
        if node:
            self._window.get_viewer().goto_node(node, False)
