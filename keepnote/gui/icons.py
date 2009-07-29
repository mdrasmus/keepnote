"""

    KeepNote
    Graphical User Interface for KeepNote Application

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
import mimetypes
import os

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk

# keepnote imports
import keepnote
import keepnote.gui
from keepnote import get_resource
import keepnote.notebook as notebooklib




_g_default_node_icon_filenames = {
    notebooklib.CONTENT_TYPE_TRASH: ("trash.png", "trash.png"),
    notebooklib.CONTENT_TYPE_DIR: ("folder.png", "folder-open.png"),
    notebooklib.CONTENT_TYPE_PAGE: ("note.png", "note.png")
}
_g_unknown_icons = ("note-unknown.png", "note-unknown.png")


_colors = ["", "-red", "-orange", "-yellow",
           "-green", "-blue", "-violet", "-grey"]
           
builtin_icons = ["folder" + c + ".png" for c in _colors] + \
                ["folder" + c + "-open.png" for c in _colors] + \
                ["note" + c + ".png" for c in _colors] + \
                ["star.png",
                 "heart.png",
                 "check.png",
                 "x.png",

                 "important.png",
                 "question.png",
                 "web.png",
                 "note-unknown.png"]

DEFAULT_QUICK_PICK_ICONS = ["folder" + c + ".png" for c in _colors] + \
                           ["note" + c + ".png" for c in _colors] + \
                           ["star.png",
                            "heart.png",
                            "check.png",
                            "x.png",

                            "important.png",
                            "question.png",
                            "web.png",
                            "note-unknown.png"]



#=============================================================================
# node icons


class MimeIcons:
    
    def __init__(self):
        self._icons = set(gtk.icon_theme_get_default().list_icons())
        self._cache = {}
 
    def get_icon(self, filename, default=None):
        """Try to find icon for mime type"""
 
        # get mime type
        mime_type = mimetypes.guess_type(filename).replace("/", "-")

        return self.get_icon_mimetype(filename, default)


    def get_icon_mimetype(self, mime_type, default=None):
        """Try to find icon for mime type"""
  
        # search in the cache
        if mime_type in self._cache:
            return self._cache[mime_type]
 
        # try gnome mime
        items = mime_type.split('/')
        for i in xrange(len(items), 0, -1):
            icon_name = "gnome-mime-" + '-'.join(items[:i])
            if icon_name in self._icons:
                self._cache[mime_type] = icon_name                
                return icon_name
 
        # try simple mime
        for i in xrange(len(items), 0, -1):
            icon_name = '-'.join(items[:i])
            if icon_name in self._icons:
                self._cache[mime_type] = icon_name
                return icon_name
 
        # file icon
        self._cache[mime_type] = default
        return default


    def get_icon_filename(self, name, default=None):

        if name is None:
            return default
        
        size = 16
        info = gtk.icon_theme_get_default().lookup_icon(name, size, 0)
        if info:
            return info.get_filename()
        else:
            return default
        
        
_g_mime_icons = MimeIcons()


def get_default_icon_basenames(node):
    """Returns basesnames for default icons for a node"""
    content_type = node.get_attr("content_type")

    default = _g_mime_icons.get_icon_mimetype(content_type, "note-unknown.png")
    
    basenames = _g_default_node_icon_filenames.get(content_type,
                                                   (default, default))
    return basenames

    #if basenames is None:
    #    return _g_unknown_icons


def get_default_icon_filenames(node):
    """Returns NoteBookNode icon filename from resource path"""

    filenames = get_default_icon_basenames(node)

    # lookup filenames
    return [lookup_icon_filename(node.get_notebook(), filenames[0]),
            lookup_icon_filename(node.get_notebook(), filenames[1])]


def lookup_icon_filename(notebook, basename):
    """
    Lookup full filename of a icon from a notebook and builtins
    Returns None if not found
    notebook can be None
    """

    # lookup in notebook icon store
    if notebook is not None:
        filename = notebook.get_icon_file(basename)
        if filename:
            return filename

    # lookup in builtins
    filename = get_resource(keepnote.NODE_ICON_DIR, basename)
    if os.path.exists(filename):
        return filename

    # lookup mime types
    return _g_mime_icons.get_icon_filename(basename)



def get_all_icon_basenames(notebook):
    """
    Return a list of all builtin icons and notebook-specific icons
    Icons are referred to by basename
    """

    return builtin_icons + notebook.get_icons()
    

def guess_open_icon_filename(icon_file):
    """
    Guess an 'open' version of an icon from its closed version
    Accepts basenames and full filenames
    """

    path, ext = os.path.splitext(icon_file)
    return path + u"-open" + ext


def get_node_icon_basenames(node):

    # TODO: merge with get_node_icon_filenames?

    notebook = node.get_notebook()

    # get default basenames
    basenames = get_default_icon_basenames(node)

    # load icon    
    if node.has_attr("icon"):
        # use attr
        basename = node.get_attr("icon")
        filename = lookup_icon_filename(notebook, basename)
        if filename:
            basenames[0] = basename


    # load icon with open state
    if node.has_attr("icon_open"):
        # use attr
        basename = node.get_attr("icon_open")
        filename = lookup_icon_filename(notebook, basename)
        if filename:
            basenames[1] = basename
    else:
        if node.has_attr("icon"):

            # use icon to guess open icon
            basename = guess_open_icon_filename(node.get_attr("icon"))
            filename = lookup_icon_filename(notebook, basename)
            if filename:
                basenames[1] = basename
            else:
                # use icon as-is for open icon if it is specified
                basename = node.get_attr("icon")
                filename = lookup_icon_filename(notebook, basename)
                if filename:
                    basenames[1] = basename

    return basenames
    


def get_node_icon_filenames(node):
    """Loads the icons for a node"""

    notebook = node.get_notebook()

    # get default filenames
    filenames = get_default_icon_filenames(node)

    # load icon    
    if node.has_attr("icon"):
        # use attr
        filename = lookup_icon_filename(notebook, node.get_attr("icon"))
        if filename:
            filenames[0] = filename


    # load icon with open state
    if node.has_attr("icon_open"):
        # use attr
        filename = lookup_icon_filename(notebook,
                                      node.get_attr("icon_open"))
        if filename:
            filenames[1] = filename
    else:
        if node.has_attr("icon"):

            # use icon to guess open icon
            filename = lookup_icon_filename(notebook,
                guess_open_icon_filename(node.get_attr("icon")))
            if filename:
                filenames[1] = filename
            else:
                # use icon as-is for open icon if it is specified
                filename = lookup_icon_filename(notebook,
                                              node.get_attr("icon"))
                if filename:
                    filenames[1] = filename    
    
    return filenames


def get_node_icon(node, expand=False):
    """Returns pixbuf of NoteBookNode icon from resource path"""

    if not expand and node.has_attr("icon_load"):
        # return loaded icon
        return keepnote.gui.get_pixbuf(node.get_attr("icon_load"), (15, 15))
    
    elif expand and node.has_attr("icon_open_load"):
        # return loaded icon with open state
        return keepnote.gui.get_pixbuf(node.get_attr("icon_open_load"), (15, 15))
    
    else:
        # load icons and return the one requested
        filenames = get_node_icon_filenames(node)
        node.set_attr("icon_load", filenames[0])
        node.set_attr("icon_open_load", filenames[1])       
        return keepnote.gui.get_pixbuf(filenames[int(expand)], (15, 15))


