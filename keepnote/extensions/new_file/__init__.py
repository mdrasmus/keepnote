"""
    KeepNote Extension 
    backup_tar

    Tar file notebook backup
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

import gettext
import os
import re
import shutil
import sys
import time
import xml.etree.cElementTree as etree


#_ = gettext.gettext

import keepnote
from keepnote import unicode_gtk
from keepnote.notebook import NoteBookError, get_valid_unique_filename
from keepnote import notebook as notebooklib
from keepnote import tasklib
from keepnote import tarfile
from keepnote.gui import extension

# pygtk imports
try:
    import pygtk
    pygtk.require('2.0')
    from gtk import gdk
    import gtk.glade
    import gobject
except ImportError:
    # do not fail on gtk import error,
    # extension should be usable for non-graphical uses
    pass



class Extension (extension.Extension):
    
    version = (1, 0)
    name = "New File"
    author = "Matt Rasmussen <rasmus@mit.edu>"
    description = "Attaches a new (empty) file to a notebook"


    def __init__(self, app):
        """Initialize extension"""
        
        extension.Extension.__init__(self, app)
        self.app = app

        self._ui_id = {}
        self._action_groups = {}


        self._file_types = []
        self._default_file_types = [
            FileType("Text File (txt)", "untitled.txt", "plain_text.txt"),
            FileType("Spreadsheet (xls)", "untitled.xls", "spreadsheet.xls"),
            FileType("Word Document (doc)", "untitled.doc", "document.doc")
            ]

        self.enabled.add(self.on_enabled)


    def on_enabled(self, enabled):
        if enabled:
            self.load_config()


    def get_depends(self):
        return [("keepnote", ">=", (0, 6, 3))]


    #===============================
    # config handling

    def get_config_file(self):
        return self.get_data_file("config.xml")

    def load_config(self):
        config = self.get_config_file()
        if not os.path.exists(config):
            self.set_default_file_types()
            self.save_default_example_files()
            self.save_config()
        
        tree = etree.ElementTree(file=config)

        self.set_default_file_types()
        self.save_config()
        

    def save_config(self):
        config = self.get_config_file()

        tree = etree.ElementTree(
            etree.Element("file_types"))
        root = tree.getroot()

        for file_type in self._file_types:
            elm = etree.SubElement(root, "file_type")
            name = etree.SubElement(elm, "name")
            name.text = file_type.name
            example = etree.SubElement(elm, "example_file")
            example.text = file_type.example_file
            filename = etree.SubElement(elm, "filename")
            filename.text = file_type.filename

        tree.write(open(config, "w"), "UTF-8")


    def set_default_file_types(self):

        self._file_types = list(self._default_file_types)

    def save_default_example_files(self):
        
        base = self.get_base_dir()
        data_dir = self.get_data_dir()

        for file_type in self._default_file_types:
            fn = file_type.example_file
            shutil.copy(os.path.join(base, fn), os.path.join(data_dir, fn))



    #==============================
    # UI

    def on_add_ui(self, window):
        """Initialize extension for a particular window"""
        
        # add menu options
        self._action_groups[window] = gtk.ActionGroup("MainWindow")
        self._action_groups[window].add_actions([
            #("treeview_popup", None, None),
            ("New File", None, _("New _File"))
            ])
        window.get_uimanager().insert_action_group(self._action_groups[window], 0)
        
        self._ui_id[window] = window.get_uimanager().add_ui_from_string(
            """
            <ui>
            <menubar name="main_menu_bar">
               <menu action="File">
                  <placeholder name="New">
                     <menuitem action="New File"/>
                  </placeholder>
               </menu>
            </menubar>

            <!--
            <menubar name="popup_menus">
               <menu action="treeview_popup">
                  <placeholder action="New">
                     <menuitem action="New File"/>
                  </placeholder>
               </menu>
            </menubar>
            -->

            </ui>
            """)

        self.set_new_file_menus(window)

    def on_remove_ui(self, window):        

        # remove menu options
        window.get_uimanager().remove_action_group(self._action_groups[window])
        del self._action_groups[window]
        
        window.get_uimanager().remove_ui(self._ui_id[window])
        del self._ui_id[window]

    def on_new_file(self, window, file_type):
        """Callback from gui to add a new file"""

        notebook = window.get_notebook()
        if notebook is None:
            return

        nodes, widget = window.get_selected_nodes()
        if len(nodes) == 0:
            parent = notebook
        else:
            parent = nodes[0]

        try:
            uri = os.path.join(self.get_data_dir(), file_type.example_file)
            node = notebooklib.attach_file(uri, parent)
            node.rename(file_type.filename)
        except Exception, e:
            window.error(_("Error while attaching file '%s'." % uri), e)


    def on_new_file_type(self, window):
        """Callback from gui for adding a new file type"""
        pass


    def set_new_file_menus(self, window):
        """Set the recent notebooks in the file menu"""

        menu = window.get_uimanager().get_widget("/main_menu_bar/File/New/New File")
        if menu:
            self.set_new_file_menu(window, menu)


        menu = window.get_uimanager().get_widget("/popup_menus/treeview_popup/New/New File")
        if menu:
            self.set_new_file_menu(window, menu)


    def set_new_file_menu(self, window, menu):
        """Set the recent notebooks in the file menu"""

        # init menu
        if menu.get_submenu() is None:
            submenu = gtk.Menu()
            submenu.show()
            menu.set_submenu(submenu)
        menu = menu.get_submenu()

        # clear menu
        menu.foreach(lambda x: menu.remove(x))

        def make_func(file_type):
            return lambda w: self.on_new_file(window, file_type)

        # populate menu
        for file_type in self._file_types:
            item = gtk.MenuItem(u"New %s" % file_type.name)
            item.connect("activate", make_func(file_type))
            item.show()
            menu.append(item)

        item = gtk.SeparatorMenuItem()
        item.show()
        menu.append(item)

        item = gtk.MenuItem(u"Add New File Type")
        item.connect("activate", self.on_new_file_type)
        item.show()
        menu.append(item)



class FileType (object):

    def __init__(self, name, filename, example_file):
        self.name = name
        self.filename = filename
        self.example_file = example_file
