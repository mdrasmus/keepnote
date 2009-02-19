"""
    KeepNote
    Copyright Matt Rasmussen 2008
    
    Graphical User Interface for KeepNote Application
"""



# python imports
import sys, os, tempfile, re, subprocess, shlex, shutil

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# keepnote imports
import keepnote
from keepnote import get_resource
from keepnote.notebook import \
     NoteBookError, \
     NoteBookTrash
import keepnote.notebook as notebooklib


ACCEL_FILE = "accel.txt"


# globals
_g_pixbufs = {}
_g_default_node_icon_filenames = {
    notebooklib.CONTENT_TYPE_TRASH: ("trash.png", "trash.png"),
    notebooklib.CONTENT_TYPE_DIR: ("folder.png", "folder-open.png"),
    notebooklib.CONTENT_TYPE_PAGE: ("note.png", "note.png")
}
_g_unknown_icons = ("note-unknown.png", "note-unknown.png")
      


def get_pixbuf(filename):
    """
    Get pixbuf from a filename

    Cache pixbuf for later use
    """
    
    if filename in _g_pixbufs:
        return _g_pixbufs[filename]
    else:
        # may raise GError
        pixbuf = gtk.gdk.pixbuf_new_from_file(filename)
        _g_pixbufs[filename] = pixbuf
        return pixbuf
    

def get_resource_image(*path_list):
    """Returns gtk.Image from resource path"""
    
    filename = get_resource(keepnote.IMAGE_DIR, *path_list)
    img = gtk.Image()
    img.set_from_file(filename)
    return img

def get_resource_pixbuf(*path_list):
    """Returns cached pixbuf from resource path"""
    # raises GError
    return get_pixbuf(get_resource(keepnote.IMAGE_DIR, *path_list))


#==============================
# node icons

def get_default_icon_filenames(node):  
    content_type = node.get_attr("content_type")
    return _g_default_node_icon_filenames.get(content_type, _g_unknown_icons)
    

def get_icon_filename(node, filename):

    filename2 = node.get_notebook().get_icon_file(filename)
    if filename2:
        return filename2
    else:
        filename = get_resource(keepnote.IMAGE_DIR, filename)
        if filename:
            return filename
        else:
            # TODO: handle this better
            return None


def get_node_icon_filenames(node):
    """Returns NoteBookNode icon filename from resource path"""

    filenames = get_default_icon_filenames(node)

    # TODO: add lookup in notebook icon dir
    # lookup filenames
    return (get_icon_filename(node, filenames[0]),
            get_icon_filename(node, filenames[1]))



def get_node_icon(node, expand=False):
    """Returns cached pixbuf of NoteBookNode icon from resource path"""
    
    if not expand and node.has_attr("icon_load"):
        # return loaded icon
        return get_pixbuf(node.get_attr("icon_load"))
    
    elif expand and node.has_attr("icon_open_load"):
        # return loaded icon with open state
        return get_pixbuf(node.get_attr("icon_open_load"))
    
    else:
        # load icons
        
        # get default filenames
        filenames = get_node_icon_filenames(node)

        # load icon
        if node.has_attr("icon"):
            # use attr
            node.set_attr("icon_load",
                          get_icon_filename(node, node.get_attr("icon")))
        else:
            # use default
            node.set_attr("icon_load", filenames[0])

        # load icon with open state
        if node.has_attr("icon_open"):
            # use attr
            node.set_attr("icon_open_load",
                          get_icon_filename(node, node.get_attr("icon_open")))
        else:

            if node.has_attr("icon"):
                # use icon as open icon if it is specified
                node.set_attr("icon_open_load",
                          get_icon_filename(node, node.get_attr("icon")))
            else:
                # use default
                node.set_attr("icon_open_load", filenames[1])
        
        return get_pixbuf(filenames[int(expand)])

        
def get_accel_file():
    """Returns gtk accel file"""

    return os.path.join(keepnote.get_user_pref_dir(), ACCEL_FILE)
