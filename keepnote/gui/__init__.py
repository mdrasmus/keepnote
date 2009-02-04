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
_g_node_icons = {}


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
        
def get_node_icon_filenames(node):
    """Returns NoteBookNode icon filename from resource path"""
    
    if isinstance(node, NoteBookTrash):
        return (get_resource(keepnote.IMAGE_DIR, "trash.png"),
                get_resource(keepnote.IMAGE_DIR, "trash.png"))
    
    elif node.get_attr("content_type") == notebooklib.CONTENT_TYPE_DIR:
        return (get_resource(keepnote.IMAGE_DIR, "folder.png"),
                get_resource(keepnote.IMAGE_DIR, "folder-open.png"))
    
    elif node.get_attr("content_type") == notebooklib.CONTENT_TYPE_PAGE:
        filename = get_resource(keepnote.IMAGE_DIR, "note.png")
        return (filename, filename)

    else:
        filename = get_resource(keepnote.IMAGE_DIR, "note-unkown.png")
        return (filename, filename)



def get_node_icon(node, expand=False):
    """Returns cached pixbuf of NoteBookNode icon from resource path"""
    
    if node in _g_node_icons:
        return _g_node_icons[node][int(expand)]
    else:
        filenames = get_node_icon_filenames(node)
        pixbufs  = (get_pixbuf(filenames[0]),
                    get_pixbuf(filenames[1]))
        _g_node_icons[node] = pixbufs
        return pixbufs[int(expand)]

        
def get_accel_file():
    """Returns gtk accel file"""

    return os.path.join(keepnote.get_user_pref_dir(), ACCEL_FILE)
