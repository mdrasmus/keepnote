"""

    KeepNote
    Editor widget in main window

"""


#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
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

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk.glade
import gobject

try:
    raise ImportError()

    from gtksourceview2 import View as SourceView
    from gtksourceview2 import Buffer as SourceBuffer
    from gtksourceview2 import LanguageManager as SourceLanguageManager
except ImportError:
    SourceView = None

# keepnote imports
import keepnote
from keepnote import \
    KeepNoteError, unicode_gtk
from keepnote.notebook import \
    NoteBookError, \
    parse_node_url, \
    is_node_url
from keepnote.gui.richtext import \
    RichTextView, RichTextBuffer, \
    RichTextIO, RichTextError
from keepnote.gui import \
    CONTEXT_MENU_ACCEL_PATH, \
    Action, \
    ToggleAction, \
    add_actions
from keepnote.gui.editor import KeepNoteEditor

_ = keepnote.translate


class TextEditor (KeepNoteEditor):

    def __init__(self, app):
        KeepNoteEditor.__init__(self, app)
        self._app = app
        self._notebook = None

        self._link_picker = None
        self._maxlinks = 10  # maximum number of links to show in link picker

        # state
        self._page = None                  # current NoteBookPage
        self._page_scrolls = {}            # remember scroll in each page
        self._page_cursors = {}
        self._textview_io = RichTextIO()

        # textview and its callbacks
        if SourceView:
            self._textview = SourceView(SourceBuffer())
            self._textview.get_buffer().set_highlight_syntax(True)
            #self._textview.set_show_margin(True)
            #self._textview.disable()
        else:
            self._textview = RichTextView(RichTextBuffer(
                self._app.get_richtext_tag_table()))  # textview
            self._textview.disable()
            self._textview.connect("modified", self._on_modified_callback)
            self._textview.connect("visit-url", self._on_visit_url)

        # scrollbars
        self._sw = gtk.ScrolledWindow()
        self._sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self._sw.set_shadow_type(gtk.SHADOW_IN)
        self._sw.add(self._textview)
        self.pack_start(self._sw)

        #self._socket = gtk.Socket()
        #self.pack_start(self._socket)

        # menus
        #self.editor_menus = EditorMenus(self._app, self)

        # find dialog
        #self.find_dialog = dialog_find.KeepNoteFindDialog(self)

        self.show_all()

    def set_notebook(self, notebook):
        """Set notebook for editor"""
        # set new notebook
        self._notebook = notebook

        if self._notebook:
            # read default font
            pass
        else:
            # no new notebook, clear the view
            self.clear_view()

    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""

        #self.editor_menus.enable_spell_check(
        #    self._app.pref.get("editors", "general", "spell_check",
        #                       default=True))

        if not SourceView:
            self._textview.set_default_font("Monospace 10")

    def save_preferences(self, app_pref):
        """Save application preferences"""
        # record state in preferences
        #app_pref.set("editors", "general", "spell_check",
        #             self._textview.is_spell_check_enabled())

    def get_textview(self):
        """Return the textview"""
        return self._textview

    def is_focus(self):
        """Return True if text editor has focus"""
        return self._textview.is_focus()

    def grab_focus(self):
        """Pass focus to textview"""
        self._textview.grab_focus()

    def clear_view(self):
        """Clear editor view"""
        self._page = None
        if not SourceView:
            self._textview.disable()

    def undo(self):
        """Undo the last action in the viewer"""
        self._textview.undo()

    def redo(self):
        """Redo the last action in the viewer"""
        self._textview.redo()

    def view_nodes(self, nodes):
        """View a page in the editor"""
        # editor cannot view multiple nodes at once
        # if asked to, it will view none
        if len(nodes) > 1:
            nodes = []

        # save current page before changing nodes
        self.save()
        self._save_cursor()

        if len(nodes) == 0:
            self.clear_view()

        else:
            page = nodes[0]
            self._page = page
            if not SourceView:
                self._textview.enable()

            try:
                if page.has_attr("payload_filename"):
                    #text = safefile.open(
                    #    os.path.join(page.get_path(),
                    #                 page.get_attr("payload_filename")),
                    #    codec="utf-8").read()
                    infile = page.open_file(
                        page.get_attr("payload_filename"), "r", "utf-8")
                    text = infile.read()
                    infile.close()
                    self._textview.get_buffer().set_text(text)
                    self._load_cursor()

                    if SourceView:
                        manager = SourceLanguageManager()
                        #print manager.get_language_ids()
                        #lang = manager.get_language_from_mime_type(
                        #    page.get_attr("content_type"))
                        lang = manager.get_language("python")
                        self._textview.get_buffer().set_language(lang)

                else:
                    self.clear_view()

            except RichTextError, e:
                self.clear_view()
                self.emit("error", e.msg, e)
            except Exception, e:
                self.clear_view()
                self.emit("error", "Unknown error", e)

        if len(nodes) > 0:
            self.emit("view-node", nodes[0])

    def _save_cursor(self):
        if self._page is not None:
            it = self._textview.get_buffer().get_iter_at_mark(
                self._textview.get_buffer().get_insert())
            self._page_cursors[self._page] = it.get_offset()

            x, y = self._textview.window_to_buffer_coords(
                gtk.TEXT_WINDOW_TEXT, 0, 0)
            it = self._textview.get_iter_at_location(x, y)
            self._page_scrolls[self._page] = it.get_offset()

    def _load_cursor(self):

        # place cursor in last location
        if self._page in self._page_cursors:
            offset = self._page_cursors[self._page]
            it = self._textview.get_buffer().get_iter_at_offset(offset)
            self._textview.get_buffer().place_cursor(it)

        # place scroll in last position
        if self._page in self._page_scrolls:
            offset = self._page_scrolls[self._page]
            buf = self._textview.get_buffer()
            it = buf.get_iter_at_offset(offset)
            mark = buf.create_mark(None, it, True)
            self._textview.scroll_to_mark(
                mark, 0.49, use_align=True, xalign=0.0)
            buf.delete_mark(mark)

    def save(self):
        """Save the loaded page"""
        if (self._page is not None and
            self._page.is_valid() and
            (SourceView or
                self._textview.is_modified())):

            try:
                # save text data
                buf = self._textview.get_buffer()
                text = unicode_gtk(buf.get_text(buf.get_start_iter(),
                                                buf.get_end_iter()))
                #out = safefile.open(
                #  os.path.join(self._page.get_path(),
                #               self._page.get_attr("payload_filename")), "w",
                #  codec="utf-8")
                out = self._page.open_file(
                    self._page.get_attr("payload_filename"), "w", "utf-8")
                out.write(text)
                out.close()

                # save meta data
                self._page.set_attr_timestamp("modified_time")
                self._page.save()

            except RichTextError, e:
                self.emit("error", e.msg, e)

            except NoteBookError, e:
                self.emit("error", e.msg, e)

            except Exception, e:
                self.emit("error", str(e), e)

    def save_needed(self):
        """Returns True if textview is modified"""
        if not SourceView:
            return self._textview.is_modified()
        return False

    def add_ui(self, window):
        if not SourceView:
            self._textview.set_accel_group(window.get_accel_group())
            self._textview.set_accel_path(CONTEXT_MENU_ACCEL_PATH)

        #if hasattr(self, "_socket"):
        #    print "id", self._socket.get_id()
        #    self._socket.add_id(0x480001f)

        #self.editor_menus.add_ui(window,
        #                         use_minitoolbar=
        #                         self._app.pref.get("look_and_feel",
        #                                            "use_minitoolbar",
        #                                            default=False))

    def remove_ui(self, window):
        pass
        #self.editor_menus.remove_ui(window)

    #===========================================
    # callbacks for textview

    def _on_modified_callback(self, textview, modified):
        """Callback for textview modification"""
        self.emit("modified", self._page, modified)

        # make notebook node modified
        if modified:
            self._page.mark_modified()
            self._page.notify_change(False)

    def _on_visit_url(self, textview, url):
        """Callback for textview visiting a URL"""

        if is_node_url(url):
            host, nodeid = parse_node_url(url)
            node = self._notebook.get_node_by_id(nodeid)
            if node:
                self.emit("visit-node", node)

        else:
            try:
                self._app.open_webpage(url)
            except KeepNoteError, e:
                self.emit("error", e.msg, e)


class EditorMenus (gobject.GObject):

    def __init__(self, app, editor):
        gobject.GObject.__init__(self)

        self._app = app
        self._editor = editor
        self._action_group = None
        self._uis = []
        self.spell_check_toggle = None

        self._removed_widgets = []

    #=======================================================
    # spellcheck

    def enable_spell_check(self, enabled):
        """Spell check"""
        self._editor.get_textview().enable_spell_check(enabled)

        # see if spell check became enabled
        enabled = self._editor.get_textview().is_spell_check_enabled()

        # update UI to match
        if self.spell_check_toggle:
            self.spell_check_toggle.set_active(enabled)

        return enabled

    def on_spell_check_toggle(self, widget):
        """Toggle spell checker"""
        self.enable_spell_check(widget.get_active())

    #=====================================================
    # toolbar and menus

    def add_ui(self, window):
        self._action_group = gtk.ActionGroup("Editor")
        self._uis = []
        add_actions(self._action_group, self.get_actions())
        window.get_uimanager().insert_action_group(
            self._action_group, 0)

        for s in self.get_ui():
            self._uis.append(window.get_uimanager().add_ui_from_string(s))
        window.get_uimanager().ensure_update()

        self.setup_menu(window, window.get_uimanager())

    def remove_ui(self, window):
        # remove ui
        for ui in reversed(self._uis):
            window.get_uimanager().remove_ui(ui)
        self._uis = []
        window.get_uimanager().ensure_update()

        # remove action group
        window.get_uimanager().remove_action_group(self._action_group)
        self._action_group = None

    def get_actions(self):

        def BothAction(name1, *args):
            return [Action(name1, *args), ToggleAction(name1 + " Tool", *args)]

        return (map(lambda x: Action(*x), [
            # finding
            ("Find In Page", gtk.STOCK_FIND, _("_Find In Page..."),
             "<control>F", None,
             lambda w: self._editor.find_dialog.on_find(False)),

            ("Find Next In Page", gtk.STOCK_FIND, _("Find _Next In Page..."),
             "<control>G", None,
             lambda w: self._editor.find_dialog.on_find(False, forward=True)),

            ("Find Previous In Page", gtk.STOCK_FIND,
             _("Find Pre_vious In Page..."),
             "<control><shift>G", None,
             lambda w: self._editor.find_dialog.on_find(False, forward=False)),

            ("Replace In Page", gtk.STOCK_FIND_AND_REPLACE,
             _("_Replace In Page..."),
             "<control>R", None,
             lambda w: self._editor.find_dialog.on_find(True)),

            ]) +

            [ToggleAction("Spell Check", None, _("_Spell Check"),
                          "", None,
                          self.on_spell_check_toggle)]
        )

    def get_ui(self):

        ui = ["""
        <ui>
        <menubar name="main_menu_bar">
          <menu action="Edit">
            <placeholder name="Viewer">
              <placeholder name="Editor">
                <placeholder name="Extension"/>
              </placeholder>
            </placeholder>
          </menu>
          <menu action="Search">
            <placeholder name="Viewer">
              <placeholder name="Editor">
                <menuitem action="Find In Page"/>
                <menuitem action="Find Next In Page"/>
                <menuitem action="Find Previous In Page"/>
                <menuitem action="Replace In Page"/>
              </placeholder>
            </placeholder>
          </menu>
          <placeholder name="Viewer">
            <placeholder name="Editor">
            </placeholder>
          </placeholder>

          <menu action="Go">
            <placeholder name="Viewer">
              <placeholder name="Editor">
              </placeholder>
            </placeholder>
          </menu>

          <menu action="Tools">
            <placeholder name="Viewer">
              <menuitem action="Spell Check"/>
            </placeholder>
          </menu>
        </menubar>
     </ui>
        """]

        ui.append("""
        <ui>
        <toolbar name="main_tool_bar">
          <placeholder name="Viewer">
            <placeholder name="Editor">
            </placeholder>
          </placeholder>
        </toolbar>

        </ui>
        """)

        return ui

    def setup_menu(self, window, uimanager):
        # get spell check toggle
        self.spell_check_toggle = (
            uimanager.get_widget("/main_menu_bar/Tools/Viewer/Spell Check"))
        self.spell_check_toggle.set_sensitive(
            self._editor.get_textview().can_spell_check())
        self.spell_check_toggle.set_active(window.get_app().pref.get(
            "editors", "general", "spell_check", default=True))
