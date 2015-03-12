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
import sys
import threading

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# keepnote imports
import keepnote
from keepnote import log_error
import keepnote.gui.richtext.richtext_tags
from keepnote import get_resource, unicode_gtk
from keepnote import tasklib
from keepnote.notebook import NoteBookError
import keepnote.notebook as notebooklib
import keepnote.gui.dialog_app_options
import keepnote.gui.dialog_node_icon
import keepnote.gui.dialog_wait
from keepnote.gui.icons import \
    DEFAULT_QUICK_PICK_ICONS, uncache_node_icon

_ = keepnote.translate

#=============================================================================
# constants

MAX_RECENT_NOTEBOOKS = 20
ACCEL_FILE = u"accel.txt"
IMAGE_DIR = u"images"
CONTEXT_MENU_ACCEL_PATH = "<main>/context_menu"

DEFAULT_AUTOSAVE_TIME = 10 * 1000  # 10 sec (in msec)

# font constants
DEFAULT_FONT_FAMILY = "Sans"
DEFAULT_FONT_SIZE = 10
DEFAULT_FONT = "%s %d" % (DEFAULT_FONT_FAMILY, DEFAULT_FONT_SIZE)

if keepnote.get_platform() == "darwin":
    CLIPBOARD_NAME = gdk.SELECTION_PRIMARY
else:
    CLIPBOARD_NAME = "CLIPBOARD"

DEFAULT_COLORS_FLOAT = [
    # lights
    (1, .6, .6),
    (1, .8, .6),
    (1, 1, .6),
    (.6, 1, .6),
    (.6, 1, 1),
    (.6, .6, 1),
    (1, .6, 1),

    # trues
    (1, 0, 0),
    (1, .64, 0),
    (1, 1, 0),
    (0, 1, 0),
    (0, 1, 1),
    (0, 0, 1),
    (1, 0, 1),

    # darks
    (.5, 0, 0),
    (.5, .32, 0),
    (.5, .5, 0),
    (0, .5, 0),
    (0, .5, .5),
    (0, 0, .5),
    (.5, 0, .5),

    # white, gray, black
    (1, 1, 1),
    (.9, .9, .9),
    (.75, .75, .75),
    (.5, .5, .5),
    (.25, .25, .25),
    (.1, .1, .1),
    (0, 0, 0),
]


def color_float_to_int8(color):
    return (int(255*color[0]), int(255*color[1]), int(255*color[2]))


def color_int8_to_str(color):
    return "#%02x%02x%02x" % (color[0], color[1], color[2])

DEFAULT_COLORS = [color_int8_to_str(color_float_to_int8(color))
                  for color in DEFAULT_COLORS_FLOAT]


#=============================================================================
# resources

class PixbufCache (object):
    """A cache for loading pixbufs from the filesystem"""

    def __init__(self):
        self._pixbufs = {}

    def get_pixbuf(self, filename, size=None, key=None):
        """
        Get pixbuf from a filename
        Cache pixbuf for later use
        """

        if key is None:
            key = (filename, size)

        if key in self._pixbufs:
            return self._pixbufs[key]
        else:
            # may raise GError
            pixbuf = gtk.gdk.pixbuf_new_from_file(filename)

            # resize
            if size:
                if size != (pixbuf.get_width(), pixbuf.get_height()):
                    pixbuf = pixbuf.scale_simple(size[0], size[1],
                                                 gtk.gdk.INTERP_BILINEAR)

            self._pixbufs[key] = pixbuf
            return pixbuf

    def cache_pixbuf(self, pixbuf, key):
        self._pixbufs[key] = pixbuf

    def is_pixbuf_cached(self, key):
        return key in self._pixbufs


# singleton
pixbufs = PixbufCache()


get_pixbuf = pixbufs.get_pixbuf
cache_pixbuf = pixbufs.cache_pixbuf
is_pixbuf_cached = pixbufs.is_pixbuf_cached


def get_resource_image(*path_list):
    """Returns gtk.Image from resource path"""
    filename = get_resource(IMAGE_DIR, *path_list)
    img = gtk.Image()
    img.set_from_file(filename)
    return img


def get_resource_pixbuf(*path_list, **options):
    """Returns cached pixbuf from resource path"""
    # raises GError
    return pixbufs.get_pixbuf(get_resource(IMAGE_DIR, *path_list), **options)


def fade_pixbuf(pixbuf, alpha=128):
    """Returns a new faded a pixbuf"""
    width, height = pixbuf.get_width(), pixbuf.get_height()
    pixbuf2 = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, width, height)
    pixbuf2.fill(0xffffff00)  # fill with transparent
    pixbuf.composite(pixbuf2, 0, 0, width, height,
                     0, 0, 1.0, 1.0, gtk.gdk.INTERP_NEAREST, alpha)
    #pixbuf.composite_color(pixbuf2, 0, 0, width, height,
    #                       0, 0, 1.0, 1.0, gtk.gdk.INTERP_NEAREST, alpha,
    #                       0, 0, 1, 0xcccccc, 0x00000000)
    return pixbuf2


#=============================================================================
# misc. gui functions

def get_accel_file():
    """Returns gtk accel file"""

    return os.path.join(keepnote.get_user_pref_dir(), ACCEL_FILE)


def init_key_shortcuts():
    """Setup key shortcuts for the window"""
    accel_file = get_accel_file()
    if os.path.exists(accel_file):
        gtk.accel_map_load(accel_file)
    else:
        gtk.accel_map_save(accel_file)


def set_gtk_style(font_size=10, vsep=0):
    """
    Set basic GTK style settings
    """
    gtk.rc_parse_string("""
      style "keepnote-treeview" {
        font_name = "%(font_size)d"
        GtkTreeView::vertical-separator = %(vsep)d
        GtkTreeView::expander-size = 10
      }

      class "GtkTreeView" style "keepnote-treeview"
      class "GtkEntry" style "keepnote-treeview"

      """ % {"font_size": font_size,
             "vsep": vsep})


def update_file_preview(file_chooser, preview):
    """Preview widget for file choosers"""

    filename = file_chooser.get_preview_filename()
    try:
        pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename, 128, 128)
        preview.set_from_pixbuf(pixbuf)
        have_preview = True
    except:
        have_preview = False
    file_chooser.set_preview_widget_active(have_preview)


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
            path = self._app.get_default_path(self._persistent_path)
            if path and os.path.exists(path):
                self.set_current_folder(path)

    def run(self):
        response = gtk.FileChooserDialog.run(self)

        if (response == gtk.RESPONSE_OK and
                self._app and self._persistent_path):
            self._app.set_default_path(
                self._persistent_path, unicode_gtk(self.get_current_folder()))

        return response


#=============================================================================
# menu actions

class UIManager (gtk.UIManager):
    """Specialization of UIManager for use in KeepNote"""

    def __init__(self, force_stock=False):
        gtk.UIManager.__init__(self)
        self.connect("connect-proxy", self._on_connect_proxy)
        self.connect("disconnect-proxy", self._on_disconnect_proxy)

        self.force_stock = force_stock

        self.c = gtk.VBox()

    def _on_connect_proxy(self, uimanager, action, widget):
        """Callback for a widget entering management"""
        if isinstance(action, (Action, ToggleAction)) and action.icon:
            self.set_icon(widget, action)

    def _on_disconnect_proxy(self, uimanager, action, widget):
        """Callback for a widget leaving management"""
        pass

    def set_force_stock(self, force):
        """Sets the 'force stock icon' option"""
        self.force_stock = force

        for ag in self.get_action_groups():
            for action in ag.list_actions():
                for widget in action.get_proxies():
                    self.set_icon(widget, action)

    def set_icon(self, widget, action):
        """Sets the icon for a managed widget"""

        # do not handle actions that are not of our custom classes
        if not isinstance(action, (Action, ToggleAction)):
            return

        if isinstance(widget, gtk.ImageMenuItem):
            if self.force_stock and action.get_property("stock-id"):
                img = gtk.Image()
                img.set_from_stock(action.get_property("stock-id"),
                                   gtk.ICON_SIZE_MENU)
                img.show()
                widget.set_image(img)

            elif action.icon:
                img = gtk.Image()
                img.set_from_pixbuf(get_resource_pixbuf(action.icon))
                img.show()
                widget.set_image(img)

        elif isinstance(widget, gtk.ToolButton):
            if self.force_stock and action.get_property("stock-id"):
                w = widget.get_icon_widget()
                if w:
                    w.set_from_stock(action.get_property("stock-id"),
                                     gtk.ICON_SIZE_MENU)

            elif action.icon:
                w = widget.get_icon_widget()
                if w:
                    w.set_from_pixbuf(get_resource_pixbuf(action.icon))
                else:
                    img = gtk.Image()
                    img.set_from_pixbuf(get_resource_pixbuf(action.icon))
                    img.show()
                    widget.set_icon_widget(img)


class Action (gtk.Action):
    def __init__(self, name, stockid=None, label=None,
                 accel="", tooltip="", func=None,
                 icon=None):
        gtk.Action.__init__(self, name, label, tooltip, stockid)
        self.func = func
        self.accel = accel
        self.icon = icon
        self.signal = None

        if func:
            self.signal = self.connect("activate", func)


class ToggleAction (gtk.ToggleAction):
    def __init__(self, name, stockid, label=None,
                 accel="", tooltip="", func=None, icon=None):
        gtk.ToggleAction.__init__(self, name, label, tooltip, stockid)
        self.func = func
        self.accel = accel
        self.icon = icon
        self.signal = None

        if func:
            self.signal = self.connect("toggled", func)


def add_actions(actiongroup, actions):
    """Add a list of Action's to an gtk.ActionGroup"""

    for action in actions:
        actiongroup.add_action_with_accel(action, action.accel)


#=============================================================================
# Application for GUI


# TODO: implement 'close all' for notebook
# requires listening for close.


class KeepNote (keepnote.KeepNote):
    """GUI version of the KeepNote application instance"""

    def __init__(self, basedir=None):
        keepnote.KeepNote.__init__(self, basedir)

        # window management
        self._current_window = None
        self._windows = []

        # shared gui resources
        self._tag_table = (
            keepnote.gui.richtext.richtext_tags.RichTextTagTable())
        self.init_dialogs()

        # auto save
        self._auto_saving = False           # True if autosave is on
        self._auto_save_registered = False  # True if autosave is registered
        self._auto_save_pause = 0           # >0 if autosave is paused

    def init(self):
        """Initialize application from disk"""
        keepnote.KeepNote.init(self)

    def init_dialogs(self):
        self.app_options_dialog = (
            keepnote.gui.dialog_app_options.ApplicationOptionsDialog(self))
        self.node_icon_dialog = (
            keepnote.gui.dialog_node_icon.NodeIconDialog(self))

    def set_lang(self):
        """Set language for application"""
        keepnote.KeepNote.set_lang(self)

        # setup glade with gettext
        import gtk.glade
        gtk.glade.bindtextdomain(keepnote.GETTEXT_DOMAIN,
                                 keepnote.get_locale_dir())
        gtk.glade.textdomain(keepnote.GETTEXT_DOMAIN)

        # re-initialize dialogs
        self.init_dialogs()

    def load_preferences(self):
        """Load information from preferences"""
        keepnote.KeepNote.load_preferences(self)

        # set defaults for auto save
        p = self.pref
        p.get("autosave_time", default=DEFAULT_AUTOSAVE_TIME)

        # set style
        set_gtk_style(font_size=p.get("look_and_feel", "app_font_size",
                                      default=10))

        # let windows load their preferences
        for window in self._windows:
            window.load_preferences()

        for notebook in self._notebooks.itervalues():
            notebook.enable_fulltext_search(p.get("use_fulltext_search",
                                                  default=True))

        # start autosave loop, if requested
        self.begin_auto_save()

    def save_preferences(self):
        """Save information into preferences"""

        # let windows save their preferences
        for window in self._windows:
            window.save_preferences()

        keepnote.KeepNote.save_preferences(self)

    #=================================
    # GUI

    def get_richtext_tag_table(self):
        """Returns the application-wide richtext tag table"""
        return self._tag_table

    def new_window(self):
        """Create a new main window"""
        import keepnote.gui.main_window

        window = keepnote.gui.main_window.KeepNoteWindow(self)
        window.connect("delete-event", self._on_window_close)
        window.connect("focus-in-event", self._on_window_focus)
        self._windows.append(window)

        self.init_extensions_windows([window])
        window.show_all()

        if self._current_window is None:
            self._current_window = window

        return window

    def get_current_window(self):
        """Returns the currenly active window"""
        return self._current_window

    def get_windows(self):
        """Returns a list of open windows"""
        return self._windows

    def open_notebook(self, filename, window=None, task=None):
        """Open notebook"""
        from keepnote.gui import dialog_update_notebook

        # HACK
        if isinstance(self._conns.get(filename),
                      keepnote.notebook.connection.fs.NoteBookConnectionFS):

            try:
                version = notebooklib.get_notebook_version(filename)
            except Exception, e:
                self.error(_("Could not load notebook '%s'.") % filename,
                           e, sys.exc_info()[2])
                return None

            if version < notebooklib.NOTEBOOK_FORMAT_VERSION:
                dialog = dialog_update_notebook.UpdateNoteBookDialog(
                    self, window)
                if not dialog.show(filename, version=version, task=task):
                    self.error(_("Cannot open notebook (version too old)"))
                    gtk.gdk.threads_leave()
                    return None

        # load notebook in background
        def update(task):
            sem = threading.Semaphore()
            sem.acquire()

            # perform notebook load in gui thread.
            # Ideally, this should be in the background, but it is very
            # slow.  If updating the wait dialog wasn't so expensive, I would
            # simply do loading in the background thread.
            def func():
                try:
                    conn = self._conns.get(filename)
                    notebook = notebooklib.NoteBook()
                    notebook.load(filename, conn)
                    task.set_result(notebook)
                except Exception:
                    task.set_exc_info()
                    task.stop()
                sem.release()  # notify that notebook is loaded
                return False

            gobject.idle_add(func)

            # wait for notebook to load
            sem.acquire()

        def update_old(task):
            notebook = notebooklib.NoteBook()
            notebook.load(filename)
            task.set_result(notebook)

        task = tasklib.Task(update)
        dialog = keepnote.gui.dialog_wait.WaitDialog(window)
        dialog.show(_("Opening notebook"), _("Loading..."), task, cancel=False)

        # detect errors
        try:
            if task.aborted():
                raise task.exc_info()[1]
            else:
                notebook = task.get_result()
                if notebook is None:
                    return None

        except notebooklib.NoteBookVersionError, e:
            self.error(_("This version of %s cannot read this notebook.\n"
                         "The notebook has version %d.  %s can only read %d.")
                       % (keepnote.PROGRAM_NAME,
                          e.notebook_version,
                          keepnote.PROGRAM_NAME,
                          e.readable_version),
                       e, task.exc_info()[2])
            return None

        except NoteBookError, e:
            self.error(_("Could not load notebook '%s'.") % filename,
                       e, task.exc_info()[2])
            return None

        except Exception, e:
            # give up opening notebook
            self.error(_("Could not load notebook '%s'.") % filename,
                       e, task.exc_info()[2])
            return None

        self._init_notebook(notebook)

        return notebook

    def _init_notebook(self, notebook):

        write_needed = False

        # install default quick pick icons
        if len(notebook.pref.get_quick_pick_icons()) == 0:
            notebook.pref.set_quick_pick_icons(
                list(DEFAULT_QUICK_PICK_ICONS))
            notebook.set_preferences_dirty()
            write_needed = True

        # install default quick pick icons
        if len(notebook.pref.get("colors", default=())) == 0:
            notebook.pref.set("colors", DEFAULT_COLORS)
            notebook.set_preferences_dirty()
            write_needed = True

        notebook.enable_fulltext_search(self.pref.get("use_fulltext_search",
                                                      default=True))

        # TODO: use listeners to invoke saving
        if write_needed:
            notebook.write_preferences()

    def save_notebooks(self, silent=False):
        """Save all opened notebooks"""

        # clear all window and viewer info in notebooks
        for notebook in self._notebooks.itervalues():
            notebook.pref.clear("windows", "ids")
            notebook.pref.clear("viewers", "ids")

        # save all the windows
        for window in self._windows:
            window.save_notebook(silent=silent)

        # save all the notebooks
        for notebook in self._notebooks.itervalues():
            notebook.save()

        # let windows know about completed save
        for window in self._windows:
            window.update_title()

    def _on_closing_notebook(self, notebook, save):
        """
        Callback for when notebook is about to close
        """
        keepnote.KeepNote._on_closing_notebook(self, notebook, save)

        try:
            if save:
                self.save()
        except:
            keepnote.log_error("Error while closing notebook")

        for window in self._windows:
            window.close_notebook(notebook)

    def goto_nodeid(self, nodeid):
        """
        Open a node by nodeid
        """
        for window in self.get_windows():
            notebook = window.get_notebook()
            if not notebook:
                continue
            node = notebook.get_node_by_id(nodeid)
            if node:
                window.get_viewer().goto_node(node)
                break

    #=====================================
    # auto-save

    def begin_auto_save(self):
        """Begin autosave callbacks"""

        if self.pref.get("autosave"):
            self._auto_saving = True

            if not self._auto_save_registered:
                self._auto_save_registered = True
                gobject.timeout_add(self.pref.get("autosave_time"),
                                    self.auto_save)
        else:
            self._auto_saving = False

    def end_auto_save(self):
        """Stop autosave"""
        self._auto_saving = False

    def auto_save(self):
        """Callback for autosaving"""

        self._auto_saving = self.pref.get("autosave")

        # NOTE: return True to activate next timeout callback
        if not self._auto_saving:
            self._auto_save_registered = False
            return False

        # don't do autosave if it is paused
        if self._auto_save_pause > 0:
            return True

        self.save(True)

        return True

    def pause_auto_save(self, pause):
        """Pauses autosaving"""
        self._auto_save_pause += 1 if pause else -1

    #===========================================
    # node icons

    def on_set_icon(self, icon_file, icon_open_file, nodes):
        """
        Change the icon for a node

        icon_file, icon_open_file -- icon basenames
            use "" to delete icon setting (set default)
            use None to leave icon setting unchanged
        """

        # TODO: maybe this belongs inside the node_icon_dialog?

        for node in nodes:
            if icon_file == u"":
                node.del_attr("icon")
            elif icon_file is not None:
                node.set_attr("icon", icon_file)

            if icon_open_file == u"":
                node.del_attr("icon_open")
            elif icon_open_file is not None:
                node.set_attr("icon_open", icon_open_file)

            # uncache pixbufs
            uncache_node_icon(node)

    def on_new_icon(self, nodes, notebook, window=None):
        """Change the icon for a node"""

        # TODO: maybe this belongs inside the node_icon_dialog?

        if notebook is None:
            return

        # TODO: assume only one node is selected
        node = nodes[0]

        icon_file, icon_open_file = self.node_icon_dialog.show(node,
                                                               window=window)

        newly_installed = set()

        # NOTE: files may be filename or basename, use isabs to distinguish
        if icon_file and os.path.isabs(icon_file) and \
           icon_open_file and os.path.isabs(icon_open_file):
            icon_file, icon_open_file = notebook.install_icons(
                icon_file, icon_open_file)
            newly_installed.add(os.path.basename(icon_file))
            newly_installed.add(os.path.basename(icon_open_file))

        else:
            if icon_file and os.path.isabs(icon_file):
                icon_file = notebook.install_icon(icon_file)
                newly_installed.add(os.path.basename(icon_file))

            if icon_open_file and os.path.isabs(icon_open_file):
                icon_open_file = notebook.install_icon(icon_open_file)
                newly_installed.add(os.path.basename(icon_open_file))

        # set quick picks if OK was pressed
        if icon_file is not None:
            notebook.pref.set_quick_pick_icons(
                self.node_icon_dialog.get_quick_pick_icons())

            # TODO: figure out whether I need to track newly installed or not.
            # set notebook icons
            notebook_icons = notebook.get_icons()
            keep_set = (set(self.node_icon_dialog.get_notebook_icons()) |
                        newly_installed)
            for icon in notebook_icons:
                if icon not in keep_set:
                    notebook.uninstall_icon(icon)

            notebook.set_preferences_dirty()

            # TODO: should this be done with a notify?
            notebook.write_preferences()

        self.on_set_icon(icon_file, icon_open_file, nodes)

    #==================================
    # file attachment

    def on_attach_file(self, node=None, parent_window=None):

        dialog = FileChooserDialog(
            _("Attach File..."), parent_window,
            action=gtk.FILE_CHOOSER_ACTION_OPEN,
            buttons=(_("Cancel"), gtk.RESPONSE_CANCEL,
                     _("Attach"), gtk.RESPONSE_OK),
            app=self,
            persistent_path="attach_file_path")
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_select_multiple(True)

        # setup preview
        preview = gtk.Image()
        dialog.set_preview_widget(preview)
        dialog.connect("update-preview", update_file_preview, preview)

        response = dialog.run()

        if response == gtk.RESPONSE_OK:
            if len(dialog.get_filenames()) > 0:
                filenames = map(unicode_gtk, dialog.get_filenames())
                self.attach_files(filenames, node,
                                  parent_window=parent_window)

        dialog.destroy()

    def attach_file(self, filename, parent, index=None,
                    parent_window=None):
        self.attach_files([filename], parent, index, parent_window)

    def attach_files(self, filenames, parent, index=None,
                     parent_window=None):

        if parent_window is None:
            parent_window = self.get_current_window()

        #def func(task):
        #    for filename in filenames:
        #        task.set_message(("detail", _("attaching %s") %
        #                          os.path.basename(filename)))
        #        notebooklib.attach_file(filename, parent, index)
        #        if not task.is_running():
        #            task.abort()
        #task = tasklib.Task(func)

        try:
            for filename in filenames:
                notebooklib.attach_file(filename, parent, index)

            #dialog = keepnote.gui.dialog_wait.WaitDialog(parent_window)
            #dialog.show(_("Attach File"), _("Attaching files to notebook."),
            #            task, cancel=False)

            #if task.aborted():
            #    raise task.exc_info()[1]

        except Exception, e:
            if len(filenames) > 1:
                self.error(_("Error while attaching files %s." %
                             ", ".join(["'%s'" % f for f in filenames])),
                           e, sys.exc_info()[2])
            else:
                self.error(
                    _("Error while attaching file '%s'." % filenames[0]),
                    e, sys.exc_info()[2])

    #==================================
    # misc GUI

    def focus_windows(self):
        """Focus all open windows on desktop"""
        for window in self._windows:
            window.restore_window()

    def error(self, text, error=None, tracebk=None, parent=None):
        """Display an error message"""

        if parent is None:
            parent = self.get_current_window()

        dialog = gtk.MessageDialog(
            parent,
            flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_ERROR,
            buttons=gtk.BUTTONS_OK,
            message_format=text)
        dialog.connect("response", lambda d, r: d.destroy())
        dialog.set_title(_("Error"))
        dialog.show()

        # add message to error log
        if error is not None:
            keepnote.log_error(error, tracebk)

    def message(self, text, title="KeepNote", parent=None):
        """Display a message window"""

        if parent is None:
            parent = self.get_current_window()

        dialog = gtk.MessageDialog(
            parent,
            flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_INFO,
            buttons=gtk.BUTTONS_OK,
            message_format=text)
        dialog.set_title(title)
        dialog.run()
        dialog.destroy()

    def ask_yes_no(self, text, title="KeepNote", parent=None):
        """Display a yes/no window"""

        if parent is None:
            parent = self.get_current_window()

        dialog = gtk.MessageDialog(
            parent,
            flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            type=gtk.MESSAGE_QUESTION,
            buttons=gtk.BUTTONS_YES_NO,
            message_format=text)

        dialog.set_title(title)
        response = dialog.run()
        dialog.destroy()

        return response == gtk.RESPONSE_YES

    def quit(self):
        """Quit the gtk event loop"""
        keepnote.KeepNote.quit(self)

        gtk.accel_map_save(get_accel_file())
        gtk.main_quit()

    #===================================
    # callbacks

    def _on_window_close(self, window, event):
        """Callback for window close event"""

        if window in self._windows:
            for ext in self.get_enabled_extensions():
                try:
                    if isinstance(ext, keepnote.gui.extension.Extension):
                        ext.on_close_window(window)
                except Exception, e:
                    log_error(e, sys.exc_info()[2])

            # remove window from window list
            self._windows.remove(window)

            if window == self._current_window:
                self._current_window = None

        # quit app if last window closes
        if len(self._windows) == 0:
            self.quit()

    def _on_window_focus(self, window, event):
        """Callback for when a window gains focus"""
        self._current_window = window

    #====================================
    # extension methods

    def init_extensions_windows(self, windows=None, exts=None):
        """Initialize all extensions for a window"""

        if exts is None:
            exts = self.get_enabled_extensions()

        if windows is None:
            windows = self.get_windows()

        for window in windows:
            for ext in exts:
                try:
                    if isinstance(ext, keepnote.gui.extension.Extension):
                        ext.on_new_window(window)
                except Exception, e:
                    log_error(e, sys.exc_info()[2])

    def install_extension(self, filename):
        """Install a new extension"""
        if self.ask_yes_no(_("Do you want to install the extension \"%s\"?") %
                           filename, "Extension Install"):
            # install extension
            new_exts = keepnote.KeepNote.install_extension(self, filename)

            # initialize extensions with windows
            self.init_extensions_windows(exts=new_exts)

            if len(new_exts) > 0:
                self.message(_("Extension \"%s\" is now installed.") %
                             filename, _("Install Successful"))
                return True

        return False

    def uninstall_extension(self, ext_key):
        """Install a new extension"""
        if self.ask_yes_no(
                _("Do you want to uninstall the extension \"%s\"?") %
                ext_key, _("Extension Uninstall")):
            if keepnote.KeepNote.uninstall_extension(self, ext_key):
                self.message(_("Extension \"%s\" is now uninstalled.") %
                             ext_key,
                             _("Uninstall Successful"))
                return True

        return False
