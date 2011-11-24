"""
    KeepNote Extension 
    new_file

    Extension allows adding new filetypes to a notebook
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
from keepnote.notebook import NoteBookError
from keepnote import notebook as notebooklib
from keepnote import tasklib
from keepnote import tarfile
from keepnote.gui import extension
from keepnote.gui import dialog_app_options

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
    
    def __init__(self, app):
        """Initialize extension"""
        
        extension.Extension.__init__(self, app)
        self.app = app

        self._file_types = []
        self._default_file_types = [
            FileType("Text File (txt)", "untitled.txt", "plain_text.txt"),
            FileType("Spreadsheet (xls)", "untitled.xls", "spreadsheet.xls"),
            FileType("Word Document (doc)", "untitled.doc", "document.doc")
            ]

        self.enabled.add(self.on_enabled)


    def get_filetypes(self):
        return self._file_types


    def on_enabled(self, enabled):
        if enabled:
            self.load_config()


    def get_depends(self):
        return [("keepnote", ">=", (0, 7, 1))]



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


        try:        
            tree = etree.ElementTree(file=config)

            # check root
            root = tree.getroot()
            if root.tag != "file_types":
                raise NoteBookError("Root tag is not 'file_types'")

            # iterate children
            self._file_types = []
            for child in root:
                if child.tag == "file_type":
                    filetype = FileType("", "", "")

                    for child2 in child:
                        if child2.tag == "name":
                            filetype.name = child2.text
                        elif child2.tag == "filename":
                            filetype.filename = child2.text
                        elif child2.tag == "example_file":
                            filetype.example_file = child2.text

                    self._file_types.append(filetype)

        except:
            self.app.error("Error reading file type configuration")
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


    def update_all_menus(self):
        for window in self.get_windows():
            self.set_new_file_menus(window)

    #==============================
    # UI

    def on_add_ui(self, window):
        """Initialize extension for a particular window"""
        
        # add menu options
        self.add_action(window, "New File", "New _File")
        #("treeview_popup", None, None),
        
        self.add_ui(window,
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


    #=================================
    # Options UI setup

    def on_add_options_ui(self, dialog):
        
        dialog.add_section(NewFileSection("new_file", 
                                          dialog, self._app,
                                          self),
                           "extensions")



    def on_remove_options_ui(self, dialog):
        
        dialog.remove_section("new_file")


    #======================================
    # callbacks

    def on_new_file(self, window, file_type):
        """Callback from gui to add a new file"""

        notebook = window.get_notebook()
        if notebook is None:
            return

        nodes = window.get_selected_nodes()
        if len(nodes) == 0:
            parent = notebook
        else:
            sibling = nodes[0]
            if sibling.get_parent():
                parent = sibling.get_parent()
                index = sibling.get_attr("order") + 1
            else:
                parent = sibling

        try:
            uri = os.path.join(self.get_data_dir(), file_type.example_file)
            node = notebooklib.attach_file(uri, parent)
            node.rename(file_type.filename)
            window.get_viewer().goto_node(node)
        except Exception, e:
            window.error("Error while attaching file '%s'." % uri, e)


    def on_new_file_type(self, window):
        """Callback from gui for adding a new file type"""
        self.app.app_options_dialog.show(window, "new_file")



    #==========================================
    # menu setup

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

        # TODO: perform lookup of filetypes again

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
        item.connect("activate", lambda w: self.on_new_file_type(window))
        item.show()
        menu.append(item)



    #===============================
    # actions

    def install_example_file(self, filename):
        """Installs a new example file into the extension"""

        newpath = self.get_data_dir()
        newfilename = os.path.basename(filename)
        newfilename, ext = os.path.splitext(newfilename)
        newfilename = notebooklib.get_unique_filename(newpath, newfilename, 
                                                      ext=ext, sep=u"", 
                                                      number=2)
        shutil.copy(filename, newfilename)
        return os.path.basename(newfilename)


class FileType (object):
    """Class containing information about a filetype"""

    def __init__(self, name, filename, example_file):
        self.name = name
        self.filename = filename
        self.example_file = example_file

    def copy(self):
        return FileType(self.name, self.filename, self.example_file)




class NewFileSection (dialog_app_options.Section):
    """A Section in the Options Dialog"""

    def __init__(self, key, dialog, app, ext,
                 label=u"New File Types", 
                 icon=None):
        dialog_app_options.Section.__init__(self, key, dialog, app, label, icon)

        self.ext = ext
        self._filetypes = []
        self._current_filetype = None


        # setup UI
        w = self.get_default_widget()
        h = gtk.HBox(False, 5)
        w.add(h)

        # left column (file type list)
        v = gtk.VBox(False, 5)
        h.pack_start(v, False, True, 0)

        self.filetype_store = gtk.ListStore(str, object)
        self.filetype_listview = gtk.TreeView(self.filetype_store)
        self.filetype_listview.set_headers_visible(False)
        self.filetype_listview.get_selection().connect("changed", 
                                                       self.on_listview_select)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)
        sw.add(self.filetype_listview)
        sw.set_size_request(160, 200)
        v.pack_start(sw, False, True, 0)
        

        # create the treeview column
        column = gtk.TreeViewColumn()
        self.filetype_listview.append_column(column)
        cell_text = gtk.CellRendererText()
        column.pack_start(cell_text, True)
        column.add_attribute(cell_text, 'text', 0)

        # add/del buttons
        h2 = gtk.HBox(False, 5)
        v.pack_start(h2, False, True, 0)

        button = gtk.Button("New")
        button.connect("clicked", self.on_new_filetype)
        h2.pack_start(button, True, True, 0)

        button = gtk.Button("Delete")
        button.connect("clicked", self.on_delete_filetype)
        h2.pack_start(button, True, True, 0)




        # right column (file type editor)
        v = gtk.VBox(False, 5)
        h.pack_start(v, False, True, 0)

        table = gtk.Table(3, 2)
        self.filetype_editor = table
        v.pack_start(table, False, True, 0)


        # file type name
        label = gtk.Label("File type name:")
        table.attach(label, 0, 1, 0, 1,
                     xoptions=0, yoptions=0,
                     xpadding=2, ypadding=2)

        self.filetype = gtk.Entry()
        table.attach(self.filetype, 1, 2, 0, 1,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)


        # default filename
        label = gtk.Label("Default filename:")
        table.attach(label, 0, 1, 1, 2,
                     xoptions=0, yoptions=0,
                     xpadding=2, ypadding=2)

        self.filename = gtk.Entry()
        table.attach(self.filename, 1, 2, 1, 2,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)


        # example new file
        label = gtk.Label("Example new file:")
        table.attach(label, 0, 1, 2, 3,
                     xoptions=0, yoptions=0,
                     xpadding=2, ypadding=2)

        self.example_file = gtk.Entry()
        table.attach(self.example_file, 1, 2, 2, 3,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)
        

        # browse button
        button = gtk.Button(_("Browse..."))
        button.set_image(
            gtk.image_new_from_stock(gtk.STOCK_OPEN,
                                     gtk.ICON_SIZE_SMALL_TOOLBAR))
        button.show()
        button.connect("clicked", lambda w: 
                       dialog_app_options.on_browse(
                w.get_toplevel(), "Choose Example New File", "", 
                self.example_file))
        table.attach(button, 1, 2, 3, 4,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)



        w.show_all()


        self.set_filetypes()
        self.set_filetype_editor(None)

        



    def load_options(self, app):
        """Load options from app to UI"""
        
        self._filetypes = [x.copy() for x in self.ext.get_filetypes()]
        self.set_filetypes()
        self.filetype_listview.get_selection().unselect_all()


    def save_options(self, app):
        """Save options to the app"""
        
        self.save_current_filetype()

        # install example files
        bad = []
        for filetype in self._filetypes:
            if os.path.isabs(filetype.example_file):
                # copy new file into extension data dir
                try:
                    filetype.example_file = self.ext.install_example_file(
                        filetype.example_file)
                except Exception, e:
                    app.error("Cannot install example file '%s'" % 
                              filetype.example_file, e)
                    bad.append(filetype)

        # update extension state
        self.ext.get_filetypes()[:] = [x.copy() for x in self._filetypes
                                       if x not in bad]
        self.ext.save_config()
        self.ext.update_all_menus()


    def set_filetypes(self):
        """Initialize the lisview to the loaded filetypes"""
        self.filetype_store.clear()
        for filetype in self._filetypes:
            self.filetype_store.append([filetype.name, filetype])


    def set_filetype_editor(self, filetype):
        """Update editor with current filetype"""

        if filetype is None:
            self._current_filetype = None
            self.filetype.set_text("")
            self.filename.set_text("")
            self.example_file.set_text("")
            self.filetype_editor.set_sensitive(False)
        else:
            self._current_filetype = filetype
            self.filetype.set_text(filetype.name)
            self.filename.set_text(filetype.filename)
            self.example_file.set_text(filetype.example_file)
            self.filetype_editor.set_sensitive(True)
            
            

    def save_current_filetype(self):
        """Save the contents of the editor into the current filetype object"""

        if self._current_filetype:
            self._current_filetype.name = self.filetype.get_text()
            self._current_filetype.filename = self.filename.get_text()
            self._current_filetype.example_file = self.example_file.get_text()

            # update filetype list
            for row in self.filetype_store:
                if row[1] == self._current_filetype:
                    row[0] = self._current_filetype.name


    def on_listview_select(self, selection):
        """Callback for when listview selection changes"""

        model, it = self.filetype_listview.get_selection().get_selected()
        self.save_current_filetype()

        # set editor to current selection
        if it is not None:
            filetype = self.filetype_store[it][1]
            self.set_filetype_editor(filetype)
        else:
            self.set_filetype_editor(None)


    def on_new_filetype(self, button):
        """Callback for adding a new filetype"""

        self._filetypes.append(FileType(u"New File Type", u"untitled", ""))
        self.set_filetypes()
        self.filetype_listview.set_cursor((len(self._filetypes)-1,))


    def on_delete_filetype(self, button):
        
        model, it = self.filetype_listview.get_selection().get_selected()
        if it is not None:
            filetype = self.filetype_store[it][1]
            self._filetypes.remove(filetype)
            self.set_filetypes()
            
    
