"""

    KeepNote
    MultiEditor widget in main window

    This editor contain multiple editors that can be switched based on
    the content-type of the node.

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

# keepnote imports
import keepnote
from keepnote.gui.editor import KeepNoteEditor


_ = keepnote.translate


class MultiEditor (KeepNoteEditor):
    """
    Manager for switching between multiple editors
    """

    def __init__(self, app):
        KeepNoteEditor.__init__(self, app)
        self.show_all()

        self._notebook = None
        self._nodes = []
        self._editor = None
        self._window = None

        self._signals = ["view-node",
                         "visit-node",
                         "modified",
                         "font-change",
                         "error",
                         "child-activated",
                         "window-request",
                         "make-link"]
        self._signal_ids = []

    def set_editor(self, editor):
        """Set the current child editor"""

        # do nothing if editor is already set
        if editor == self._editor:
            return

        # tear down old editor, if it exists
        if self._editor:
            self._editor.view_nodes([])
            self._editor.save_preferences(self._app.pref)
            self._disconnect_signals(self._editor)
            if self._window:
                self._editor.remove_ui(self._window)
            self._editor.set_notebook(None)
            self.remove(self._editor)

        self._editor = editor

        # start up new editor, if it exists
        if self._editor:
            self.pack_start(self._editor, True, True, 0)
            self._editor.show()
            self._connect_signals(self._editor)
            self._editor.set_notebook(self._notebook)
            if self._window:
                self._editor.add_ui(self._window)
            self._editor.load_preferences(self._app.pref)
            self._editor.view_nodes(self._nodes)

    def get_editor(self):
        """Get the current child editor"""
        return self._editor

    def _connect_signals(self, editor):
        """Connect all signals for child editor"""
        def make_callback(sig):
            return lambda *args: self.emit(sig, *args[1:])

        for sig in self._signals:
            self._signal_ids.append(
                editor.connect(sig, make_callback(sig)))

    def _disconnect_signals(self, editor):
        """Disconnect al signals for child editor"""
        for sigid in self._signal_ids:
            editor.disconnect(sigid)
        self._signal_ids = []

    #========================================
    # Editor Interface

    def set_notebook(self, notebook):
        """Set notebook for editor"""
        self._notebook = notebook
        if self._editor:
            self._editor.set_notebook(notebook)

    def get_textview(self):
        """Return the textview"""
        if self._editor:
            return self._editor.get_textview()
        return None

    def is_focus(self):
        """Return True if text editor has focus"""
        if self._editor:
            return self._editor.is_focus()
        return False

    def grab_focus(self):
        """Pass focus to textview"""
        if self._editor:
            return self._editor.grab_focus()

    def clear_view(self):
        """Clear editor view"""
        if self._editor:
            return self._editor.clear_view()

    def view_nodes(self, nodes):
        """View a page in the editor"""
        self._nodes = nodes[:]
        if self._editor:
            return self._editor.view_nodes(nodes)

    def save(self):
        """Save the loaded node"""
        if self._editor:
            return self._editor.save()

    def save_needed(self):
        """Returns True if textview is modified"""
        if self._editor:
            return self._editor.save_needed()
        return False

    def load_preferences(self, app_pref, first_open=False):
        """Load application preferences"""
        if self._editor:
            return self._editor.load_preferences(app_pref, first_open)

    def save_preferences(self, app_pref):
        """Save application preferences"""
        if self._editor:
            return self._editor.save_preferences(app_pref)

    def add_ui(self, window):
        """Add editor UI to window"""
        self._window = window
        if self._editor:
            return self._editor.add_ui(window)

    def remove_ui(self, window):
        """Remove editor from UI"""
        self._window = None
        if self._editor:
            return self._editor.remove_ui(window)

    def undo(self):
        """Undo last editor action"""
        if self._editor:
            return self._editor.undo()

    def redo(self):
        """Redo last editor action"""
        if self._editor:
            return self._editor.redo()


class ContentEditor (MultiEditor):
    """
    Register multiple editors depending on the content type
    """

    def __init__(self, app):
        MultiEditor.__init__(self, app)

        self._editors = {}
        self._default_editor = None

    def add_editor(self, content_type, editor):
        """Add an editor for a content-type"""
        self._editors[content_type] = editor

    def removed_editor(self, content_type):
        """Remove editor for a content-type"""
        del self._editors[content_type]

    def get_editor_content(self, content_type):
        """Get editor associated with content-type"""
        return self._editors[content_type]

    def set_default_editor(self, editor):
        """Set the default editor"""
        self._default_editor = editor

    #=============================
    # Editor Interface

    def view_nodes(self, nodes):

        if len(nodes) != 1:
            MultiEditor.view_nodes(self, [])
        else:
            content_type = nodes[0].get_attr("content_type").split("/")

            for i in xrange(len(content_type), 0, -1):
                editor = self._editors.get("/".join(content_type[:i]), None)
                if editor:
                    self.set_editor(editor)
                    break
            else:
                self.set_editor(self._default_editor)

            MultiEditor.view_nodes(self, nodes)
