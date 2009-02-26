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
from keepnote.gui import guess_open_icon_filename, get_icon_filename
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

    
    def show(self):

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
        

        # run dialog
        response = self.dialog.run()

        icon_file = None
        icon_open_file = None
        
        if response == gtk.RESPONSE_OK:
            # icon filenames
            icon_file = self.icon_entry.get_text()
            icon_open_file = self.icon_open_entry.get_text()
        
        self.dialog.destroy()

        return icon_file, icon_open_file


    def populate_iconview(self):

        self.iconview

    def set_icon(self, entry, preview, filename):
        entry.set_text(filename)

        if not os.path.isabs(filename):
            filename = get_icon_filename(self.main_window.notebook, filename)
            
        preview.set_from_file(filename)


    def on_icon_set_button_clicked(self, widget):
        """Callback for browse icon file"""

        filename = self.icon_entry.get_text()
        filename = browse_file(self.dialog, "Choose Icon", filename)
        
        if filename:
            # set filename and preview
            self.set_icon(self.icon_entry, self.icon_image, filename)

            # try to auto-set open icon filename
            if self.icon_open_entry.get_text().strip() == "":
                open_filename = guess_open_icon_filename(filename)
                if os.path.exists(open_filename):
                    self.set_icon(self.icon_open_entry,
                                  self.icon_open_image,
                                  open_filename)


    def on_icon_open_set_button_clicked(self, widget):
        """Callback for browse open icon file"""
    
        filename = self.icon_open_entry.get_text()
        filename = browse_file(self.dialog, "Choose Open Icon", filename)
        if filename:
            # set filename and preview
            self.set_icon(self.icon_open_entry, self.icon_open_image, filename)
    

