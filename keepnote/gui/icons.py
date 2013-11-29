"""

    KeepNote
    Module for managing node icons in KeepNote

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

# python imports
import mimetypes
import os

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk

# keepnote imports
import keepnote
from keepnote import unicode_gtk
import keepnote.gui
from keepnote import get_resource
import keepnote.notebook as notebooklib


#=============================================================================
# globals/constants

NODE_ICON_DIR = os.path.join(u"images", u"node_icons")

_g_default_node_icon_filenames = {
    notebooklib.CONTENT_TYPE_TRASH: (u"trash.png", u"trash.png"),
    notebooklib.CONTENT_TYPE_DIR: (u"folder.png", u"folder-open.png"),
    notebooklib.CONTENT_TYPE_PAGE: (u"note.png", u"note.png")
}
_g_unknown_icons = ("note-unknown.png", "note-unknown.png")


_colors = [u"", u"-red", u"-orange", u"-yellow",
           u"-green", u"-blue", u"-violet", u"-grey"]

builtin_icons = [u"folder" + c + u".png" for c in _colors] + \
                [u"folder" + c + u"-open.png" for c in _colors] + \
                [u"note" + c + u".png" for c in _colors] + \
                [u"star.png",
                 u"heart.png",
                 u"check.png",
                 u"x.png",

                 u"important.png",
                 u"question.png",
                 u"web.png",
                 u"note-unknown.png"]

DEFAULT_QUICK_PICK_ICONS = [u"folder" + c + u".png" for c in _colors] + \
                           [u"note" + c + u".png" for c in _colors] + \
                           [u"star.png",
                            u"heart.png",
                            u"check.png",
                            u"x.png",

                            u"important.png",
                            u"question.png",
                            u"web.png",
                            u"note-unknown.png"]


#=============================================================================
# node icons


class MimeIcons:

    def __init__(self):
        self.theme = gtk.icon_theme_get_default()
        if self.theme is None:
            icons = []
        else:
            icons = self.theme.list_icons()
        self._icons = set(icons)
        self._cache = {}

    def get_icon(self, filename, default=None):
        """Try to find icon for filename"""

        # get mime type
        mime_type = mimetypes.guess_type(filename)[0].replace("/", "-")
        return self.get_icon_mimetype(mime_type, default)

    def get_icon_mimetype(self, mime_type, default=None):
        """Try to find icon for mime type"""

        # search in the cache
        if mime_type in self._cache:
            return self._cache[mime_type]

        # try gnome mime
        items = mime_type.split('/')
        for i in xrange(len(items), 0, -1):
            icon_name = u"gnome-mime-" + '-'.join(items[:i])
            if icon_name in self._icons:
                self._cache[mime_type] = icon_name
                return unicode(icon_name)

        # try simple mime
        for i in xrange(len(items), 0, -1):
            icon_name = u'-'.join(items[:i])
            if icon_name in self._icons:
                self._cache[mime_type] = icon_name
                return icon_name

        # file icon
        self._cache[mime_type] = default
        return default

    def get_icon_filename(self, name, default=None):
        if name is None or self.theme is None:
            return default

        size = 16
        info = self.theme.lookup_icon(name, size, 0)
        if info:
            return unicode_gtk(info.get_filename())
        else:
            return default


# singleton
_g_mime_icons = MimeIcons()


def get_icon_filename(icon_name, default=None):
    return _g_mime_icons.get_icon_filename(icon_name, default)


# HACK: cache icon filenames
_icon_basename_cache = {}


def lookup_icon_filename(notebook, basename):
    """
    Lookup full filename of a icon from a notebook and builtins
    Returns None if not found
    notebook can be None
    """

    # try cache first
    if (notebook, basename) in _icon_basename_cache:
        return _icon_basename_cache[(notebook, basename)]

    # lookup in notebook icon store
    if notebook is not None:
        filename = notebook.get_icon_file(basename)
        if filename:
            _icon_basename_cache[(notebook, basename)] = filename
            return filename

    # lookup in builtins
    filename = get_resource(NODE_ICON_DIR, basename)
    if os.path.isfile(filename):
        _icon_basename_cache[(notebook, basename)] = filename
        return filename

    # lookup mime types
    filename = _g_mime_icons.get_icon_filename(basename)
    _icon_basename_cache[(notebook, basename)] = filename
    return filename


#=============================================================================

def get_default_icon_basenames(node):
    """Returns basesnames for default icons for a node"""
    content_type = node.get_attr("content_type")
    default = _g_mime_icons.get_icon_mimetype(
        content_type, u"note-unknown.png")
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


def get_node_icon_filenames_basenames(node):

    # TODO: merge with get_node_icon_filenames?

    notebook = node.get_notebook()

    # get default basenames
    basenames = list(get_default_icon_basenames(node))
    filenames = get_default_icon_filenames(node)

    # load icon
    if node.has_attr("icon"):
        # use attr
        basename = node.get_attr("icon")
        filename = lookup_icon_filename(notebook, basename)
        if filename:
            filenames[0] = filename
            basenames[0] = basename

    # load icon with open state
    if node.has_attr("icon_open"):
        # use attr
        basename = node.get_attr("icon_open")
        filename = lookup_icon_filename(notebook, basename)
        if filename:
            filenames[1] = filename
            basenames[1] = basename
    else:
        if node.has_attr("icon"):

            # use icon to guess open icon
            basename = guess_open_icon_filename(node.get_attr("icon"))
            filename = lookup_icon_filename(notebook, basename)
            if filename:
                filenames[1] = filename
                basenames[1] = basename
            else:
                # use icon as-is for open icon if it is specified
                basename = node.get_attr("icon")
                filename = lookup_icon_filename(notebook, basename)
                if filename:
                    filenames[1] = filename
                    basenames[1] = basename

    return basenames, filenames


def get_node_icon_basenames(node):
    return get_node_icon_filenames_basenames(node)[0]


def get_node_icon_filenames(node):
    """Loads the icons for a node"""
    return get_node_icon_filenames_basenames(node)[1]


# TODO: continue to clean up class

class NoteBookIconManager (object):
    def __init__(self):
        self.pixbufs = None
        self._node_icon_cache = {}

    def get_node_icon(self, node, effects=set()):
        if self.pixbufs is None:
            self.pixbufs = keepnote.gui.pixbufs

        expand = "expand" in effects
        fade = "fade" in effects

        icon_size = (15, 15)

        icon_cache, icon_open_cache = self._node_icon_cache.get(
            node, (None, None))

        if not expand and icon_cache:
            # return loaded icon
            if not fade:
                return self.pixbufs.get_pixbuf(icon_cache, icon_size)
            else:
                return self.get_node_icon_fade(icon_cache, icon_size)

        elif expand and icon_open_cache:
            # return loaded icon with open state
            if not fade:
                return self.pixbufs.get_pixbuf(icon_open_cache, icon_size)
            else:
                self.get_node_icon_fade(icon_open_cache, icon_size)

        else:
            # load icons and return the one requested
            filenames = get_node_icon_filenames(node)
            self._node_icon_cache[node] = filenames
            if not fade:
                return self.pixbufs.get_pixbuf(
                    filenames[int(expand)], icon_size)
            else:
                return self.get_node_icon_fade(
                    filenames[int(expand)], icon_size)

    def get_node_icon_fade(self, filename, icon_size, fade_alpha=128):

        key = (filename, icon_size, "fade")
        cached = self.pixbufs.is_pixbuf_cached(key)
        pixbuf = self.pixbufs.get_pixbuf(filename, icon_size, key)
        if cached:
            return pixbuf
        else:
            pixbuf = keepnote.gui.fade_pixbuf(pixbuf, fade_alpha)
            self.pixbufs.cache_pixbuf(pixbuf, key)
            return pixbuf

    def uncache_node_icon(self, node):
        if node in self._node_icon_cache:
            del self._node_icon_cache[node]


# singleton (for now)
notebook_icon_manager = NoteBookIconManager()


def get_node_icon(node, expand=False, fade=False):
    """Returns pixbuf of NoteBookNode icon from resource path"""
    effects = set()
    if expand:
        effects.add("expand")
    if fade:
        effects.add("fade")

    return notebook_icon_manager.get_node_icon(node, effects)


def uncache_node_icon(node):
    notebook_icon_manager.uncache_node_icon(node)
