"""

    KeepNote
    Base class for a viewer

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
import gettext
import os
import subprocess
import traceback
_ = gettext.gettext


# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk
import gobject


# keepnote imports
import keepnote
from keepnote import unicode_gtk
from keepnote import KeepNoteError
from keepnote.gui import \
     dialog_image_resize, \
     get_resource, \
     get_resource_image, \
     get_resource_pixbuf, \
     get_accel_file, \
     Action, \
     FileChooserDialog, \
     CONTEXT_MENU_ACCEL_PATH
from keepnote.history import NodeHistory
from keepnote import notebook as notebooklib
from keepnote.gui import richtext
from keepnote.gui.richtext import RichTextView, RichTextImage, RichTextError
from keepnote.gui.treeview import KeepNoteTreeView
from keepnote.gui.listview import KeepNoteListView
from keepnote.gui.editor import KeepNoteEditor, EditorMenus
from keepnote.gui.icon_menu import IconMenu
from keepnote.gui.link_editor import LinkEditor
from keepnote import notebook as notebooklib
from keepnote.gui.treemodel import iter_children




class Viewer (gtk.VBox):

    def __init__(self, app, parent):
        gtk.VBox.__init__(self, False, 0)
        self._app = app
        self._main_window = parent
        
        self._notebook = None
        self._history = NodeHistory()

        self.image_resize_dialog = \
            dialog_image_resize.ImageResizeDialog(parent, self._app.pref)



    def set_notebook(self, notebook):
        self._notebook = notebook

    def get_notebook(self):
        return self._notebook

    def set_view_mode(self, mode):
        # TODO: is this too specific?
        pass

    def load_preferences(self, app_pref):
        pass

    def save_preferences(self, app_pref):
        pass

    def save(self):
        pass

    def undo(self):
        pass

    def redo(self):
        pass

        
    def visit_history(self, offset):
        """Visit a node in the viewer's history"""
        
        nodeid = self._history.move(offset)
        if nodeid is None:
            return
        node = self._notebook.get_node_by_id(nodeid)
        if node:
            self._history.begin_suspend()
            self.goto_node(node, False)
            self._history.end_suspend()


    def get_current_page(self):
        return None

    def get_selected_nodes(self, widget="focus"):
        pass

    def start_search_result(self):        
        pass

    def add_search_result(self, node):
        pass

    def new_node(self, kind, widget, pos):
        # TODO: choose a more general interface (i.e. deal with widget param)
        pass

    def get_ui(self):
        pass

    def get_actions(self):
        pass

    def setup_menus(self, uimanager):
        pass

    def make_toolbar(self, toolbar, tips, use_stock_icons):
        pass

    def goto_node(self, node, direct=True):
        pass



    #=================================================
    # Image context menu


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
                self.emit("error", _("Could not open Image Viewer"), 
                           e, sys.exc_info()[2])
        else:
            self.emit("error", _("You must specify an Image Viewer in Application Options"))



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
                self.emit("error", _("Could not open Image Editor"), e)
        else:
            self.emit("error", _("You must specify an Image Editor in Application Options"))


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
                    self.emit("error", _("Could not save image '%s'") %
                               filename)

        dialog.destroy()
    

    def make_image_menu(self, menu):
        """image context menu"""

        # TODO: remove dependency on main window
        menu.set_accel_group(self._main_window.get_accel_group())
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



gobject.type_register(Viewer)
gobject.signal_new("error", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object))
gobject.signal_new("status", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, str))
gobject.signal_new("history-changed", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("window-request", Viewer, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str,))

