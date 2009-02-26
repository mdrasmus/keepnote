"""

    KeepNote
    Update notebook dialog

"""

# python imports
import os, sys, threading, time, traceback, shutil


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk.glade
import gobject


# keepnote imports
import keepnote
from keepnote.gui import \
     guess_open_icon_filename, \
     lookup_icon_filename, \
     get_pixbuf, \
     builtin_icons, \
     get_all_icon_basenames
from keepnote import tasklib
from keepnote import notebook_update
from keepnote import notebook as notebooklib
from keepnote.gui import get_resource


def browse_file(parent, title, filename=None):
    """Callback for selecting file browser"""

    dialog = gtk.FileChooserDialog(title, parent, 
        action=gtk.FILE_CHOOSER_ACTION_OPEN,
        buttons=("Cancel", gtk.RESPONSE_CANCEL,
                 "Open", gtk.RESPONSE_OK))
    dialog.set_transient_for(parent)
    dialog.set_modal(True)

    # set the filename if it is fully specified
    if filename and os.path.isabs(filename):
        dialog.set_filename(filename)

    response = dialog.run()

    if response == gtk.RESPONSE_OK:
        filename = dialog.get_filename()
    else:
        filename = None
        
    dialog.destroy()
    
    return filename
            


class NodeIconDialog (object):
    """Updates a notebook"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.app = main_window.app
        self.node = None
        
    
    def show(self, node=None):

        self.node = node

        self.xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                 "node_icon_dialog")
        self.dialog = self.xml.get_widget("node_icon_dialog")
        self.xml.signal_autoconnect(self)
        self.dialog.connect("close", lambda w:
                            self.dialog.response(gtk.RESPONSE_CANCEL))
        self.dialog.set_transient_for(self.main_window)

        self.icon_entry = self.xml.get_widget("icon_entry")
        self.icon_open_entry = self.xml.get_widget("icon_open_entry")
        self.icon_image = self.xml.get_widget("icon_image")
        self.icon_open_image = self.xml.get_widget("icon_open_image")
        self.iconview = self.xml.get_widget("iconview")

        if node:            
            self.set_icon("icon", node.get_attr("icon", ""))
            self.set_icon("icon_open", node.get_attr("icon_open", ""))


        self.populate_iconview()

        # run dialog
        response = self.dialog.run()
        
        icon_file = None
        icon_open_file = None
        
        if response == gtk.RESPONSE_OK:
            # icon filenames
            icon_file = self.icon_entry.get_text()
            icon_open_file = self.icon_open_entry.get_text()

            if icon_file.strip() == "":
                icon_file = None
            if icon_open_file.strip() == "":
                icon_open_file = None
        
        self.dialog.destroy()

        return icon_file, icon_open_file


    def populate_iconview(self):
        """Show icons in iconview"""

        self.iconlist = gtk.ListStore(gtk.gdk.Pixbuf, str)

        for iconfile in get_all_icon_basenames(self.main_window.notebook):
            filename = lookup_icon_filename(self.main_window.notebook, iconfile)

            if filename:
                try:
                    pixbuf = get_pixbuf(filename)
                except GError:
                    continue
                self.iconlist.append((pixbuf, iconfile))

        self.iconview.set_model(self.iconlist)
        self.iconview.set_pixbuf_column(0)
        #self.iconview.set_text_column(1)
        

    def set_icon(self, kind, filename):

        if kind == "icon":        
            self.icon_entry.set_text(filename)
        else:
            self.icon_open_entry.set_text(filename)

        if filename == "":
            filenames = keepnote.gui.get_node_icon_filenames(self.node)
            filename = filenames[{"icon": 0, "icon_open": 1}[kind]]

        self.set_preview(kind, filename)

        # try to auto-set open icon filename
        if kind == "icon":
            if self.icon_open_entry.get_text().strip() == "":
                open_filename = guess_open_icon_filename(filename)

                if lookup_icon_filename(self.main_window.notebook,
                                        open_filename):
                    self.set_preview("icon_open", open_filename)
                else:
                    self.set_preview("icon_open", filename)


    def set_preview(self, kind, filename):
        
        if os.path.isabs(filename):
            filename2 = filename
        else:
            filename2 = lookup_icon_filename(self.main_window.notebook,
                                             filename)
            
        if kind == "icon":
            self.icon_image.set_from_file(filename2)
        else:
            self.icon_open_image.set_from_file(filename2)


    def on_icon_set_button_clicked(self, widget):
        """Callback for browse icon file"""

        filename = self.icon_entry.get_text()
        filename = browse_file(self.dialog, "Choose Icon", filename)
        
        if filename:
            # set filename and preview
            self.set_icon("icon", filename)


    def on_icon_open_set_button_clicked(self, widget):
        """Callback for browse open icon file"""
    
        filename = self.icon_open_entry.get_text()
        filename = browse_file(self.dialog, "Choose Open Icon", filename)
        if filename:
            # set filename and preview
            self.set_icon("icon_open", filename)
    

    def on_set_icon_button_clicked(self, widget):

        for path in self.iconview.get_selected_items():
            it = self.iconlist.get_iter(path)
            self.set_icon("icon", self.iconlist.get_value(it, 1))


    def on_set_icon_open_button_clicked(self, widget):

        for path in self.iconview.get_selected_items():
            it = self.iconlist.get_iter(path)
            self.set_icon("icon_open", self.iconlist.get_value(it, 1))
            

    
