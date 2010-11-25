"""

    KeepNote    
    Notebook data structure

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
import mimetypes
import os
import sys
import shutil
import re
import traceback

# xml imports
from xml.sax.saxutils import escape
import xml.etree.cElementTree as ET


# keepnote imports
from keepnote import safefile
from keepnote import trans
from keepnote.notebook import index as notebook_index
import keepnote
import keepnote.notebook

_ = trans.translate


# constants

XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""


#=============================================================================
# filenaming scheme


def get_node_meta_file(nodepath):
    """Returns the metadata file for a node"""
    return os.path.join(nodepath, keepnote.notebook.NODE_META_FILE)

def get_pref_file(nodepath):
    """Returns the filename of the notebook preference file"""
    return os.path.join(nodepath, keepnote.notebook.PREF_FILE)


#=============================================================================
# functions for ensuring valid filenames in notebooks

REGEX_SLASHES = re.compile(ur"[/\\]")
REGEX_BAD_CHARS = re.compile(ur"[\?'&<>|`:;]")
REGEX_LEADING_UNDERSCORE = re.compile(ur"^__+")

def get_valid_filename(filename, default=u"folder"):
    """
    Converts a filename into a valid one
    
    Strips bad characters from filename
    """
    
    filename = re.sub(REGEX_SLASHES, u"-", filename)
    filename = re.sub(REGEX_BAD_CHARS, u"", filename)
    filename = filename.replace(u"\t", " ")
    filename = filename.strip(u" \t.")
    
    # don't allow files to start with two underscores
    filename = re.sub(REGEX_LEADING_UNDERSCORE, u"", filename)
    
    # don't allow pure whitespace filenames
    if filename == u"":
        filename = default
    
    # use only lower case, some filesystems have trouble with mixed case
    filename = filename.lower()
    
    return filename
    


def get_valid_unique_filename(path, filename, ext=u"", sep=u" ", number=2):
    """Returns a valid and unique version of a filename for a given path"""
    return keepnote.notebook.get_unique_filename(
        path, get_valid_filename(filename), ext, sep, number)
    


#=============================================================================
# low-level functions


def iter_child_node_paths(path):
    """Given a path to a node, return the paths of the child nodes"""

    children = os.listdir(path)

    for child in children:
        child_path = os.path.join(path, child)
        if os.path.isfile(os.path.join(child_path, "node.xml")):
            yield child_path


def last_node_change(path):
    mtime = os.stat(path).st_mtime
    for child_path in iter_child_node_paths(path):
        mtime = max(mtime, last_change(child_path))
    return mtime


#=============================================================================

# TODO: make base class for connection

class NoteBookConnection (object):
    def __init__(self, notebook, node_factory):
        self._notebook = notebook
        self._node_factory = node_factory
    

    #================================
    # path API

    def get_node_path(self, node):
        """Returns the path key of the node"""
        
        if node._basename is None:
            return None

        # TODO: think about multiple parents
        path_list = []
        ptr = node
        while ptr is not None:
            path_list.append(ptr._basename)
            ptr = ptr._parent
        path_list.reverse()
        
        return os.path.join(* path_list)


    def get_node_name_path(self, node):
        """Returns list of basenames from root to node"""

        if node._basename is None:
            return None

        # TODO: think about multiple parents
        path_list = []
        ptr = node
        while ptr is not None:
            path_list.append(ptr._basename)
            ptr = ptr._parent
        path_list.pop()
        path_list.reverse()
        return path_list
    
    
    def set_node_basename(self, node, path):
        """Sets the basename directory of the node"""
        
        if node._parent is None:
            # the root node can take a multiple directory path
            node._basename = path
        elif path is None:
            node._basename = None
        else:
            # non-root nodes can only take the last directory as a basename
            node._basename = os.path.basename(path)




    #===============
    # file API

    def path_join(self, *parts):
        return os.path.join(*parts)

    def get_node_file(self, node, filename, path=None):
        if path is None:
            path = self.get_node_path(node)
        return os.path.join(path, filename)


    def open_node_file(self, node, filename, mode="r", codec=None, path=None):
        """Open a file contained within a node"""
        if path is None:
            path = self.get_node_path(node)
        return safefile.open(
            os.path.join(path, filename), mode, codec=codec)

    def remove_node_file(self, node, filename, path=None):
        """Open a file contained within a node"""
        if path is None:
            path = self.get_node_path(node)
        os.remove(os.path.join(path, filename))


    def new_filename(self, node, new_filename, ext=u"", sep=u" ", number=2, 
                     return_number=False, use_number=False, ensure_valid=True,
                     path=None):
        if path is None:
            path = self.get_node_path(node)
        if ext is None:
            new_filename, ext = os.path.splitext(new_filename)

        basename = os.path.basename(new_filename)
        path2 = os.path.join(path, os.path.dirname(new_filename))

        if ensure_valid:
            fullname = keepnote.notebook.get_valid_unique_filename(
                path2, basename, ext, sep=sep, number=number)
        else:
            if return_number:
                fullname, number = keepnote.notebook.get_unique_filename(
                    path2, basename, ext, sep=sep, number=number,
                    return_number=return_number, use_number=use_number)
            else:
                fullname = keepnote.notebook.get_unique_filename(
                    path2, basename, ext, sep=sep, number=number,
                    return_number=return_number, use_number=use_number)

        if return_number:
            return relpath(fullname, path), number
        else:
            return relpath(fullname, path)



    def mkdir(self, node, filename, path=None):
        if path is None:
            path = self.get_node_path(node)
        fullname = os.path.join(path, filename)
        if not os.path.exists(fullname):
            os.mkdir(fullname)

    
    def isfile(self, node, filename, path=None):
        if path is None:
            path = self.get_node_path(node)
        return os.path.isfile(os.path.join(path, filename))


    def path_exists(self, node, filename, path=None):
        if path is None:
            path = self.get_node_path(node)
        return os.path.exists(os.path.join(path, filename))


    def path_basename(self, filename):
        return os.path.basename(filename)

        
    def node_listdir(self, node, filename=None, path=None):
        """
        List data files in node
        """

        if path is None:
            path = self.get_node_path(node)
        if filename is not None:
            path = os.path.join(path, filename)
        
        for filename in os.listdir(path):
            if (filename != NODE_META_FILE and 
                not filename.startswith("__")):
                fullname = os.path.join(path, filename)
                if not os.path.exists(get_node_meta_file(fullname)):
                    # ensure directory is not a node
                    yield filename

    
    def copy_node_files(self, node1, node2):
        """
        Copy all data files from node1 to node2
        """
        
        path1 = self.get_node_path(node1)
        path2 = self.get_node_path(node2)

        for filename in self.node_listdir(node1, path1):
            fullname1 = os.path.join(path1, filename)
            fullname2 = os.path.join(path2, filename)
            
            if os.path.isfile(fullname1):
                shutil.copy(fullname1, fullname2)
            elif os.path.isdir(fullname1):
                shutil.copytree(fullname1, fullname2)

    
    def copy_node_file(self, node1, filename1, node2, filename2,
                       path1=None, path2=None):
        """
        Copy a file between two nodes

        if node is None, filename is assumed to be a local file
        """

        if node1 is None:
            fullname1 = filename1
        else:
            if path1 is None:
                path1 = self.get_node_path(node1)
            fullname1 = os.path.join(path1, filename1)

        if node2 is None:
            fullname2 = filename2
        else:
            if path2 is None:
                path2 = self.get_node_path(node2)
            fullname2 = os.path.join(path2, filename2)
        
        if os.path.isfile(fullname1):
            shutil.copy(fullname1, fullname2)
        elif os.path.isdir(fullname1):
            shutil.copytree(fullname1, fullname2)
        


    #======================
    # Node I/O API

    def read_node(self, parent, path):
        """
        Reads a node from disk

        Returns None if not a node directory
        """
        
        metafile = get_node_meta_file(path)
        attr = self._read_meta_data(metafile, self._notebook.attr_defs)
        return self._node_factory.new_node(
            attr.get("content_type", keepnote.notebook.CONTENT_TYPE_DIR),
            path, parent, self._notebook, attr)



    def read_node_meta_data(self, node):
        """Read a node meta data file"""
        node.set_meta_data(
            self._read_meta_data(node.get_meta_file(), 
                                 self._notebook.attr_defs))

    def write_node_meta_data(self, node):
        """Write a node meta data file"""
        self._write_meta_data(node.get_meta_file(), node, 
                              self._notebook.attr_defs)
    

    def _write_meta_data(self, filename, node, attr_defs):
        """Write a node meta data file"""
        
        try:
            out = safefile.open(filename, "w", codec="utf-8")
            out.write(XML_HEADER)
            out.write("<node>\n"
                      "<version>%s</version>\n" % node.get_version())
            
            for key, val in node.iter_attr():
                attr = attr_defs.get(key, None)
                
                if attr is not None:
                    out.write('<attr key="%s">%s</attr>\n' %
                              (key, escape(attr.write(val))))
                elif key == "version":
                    # skip version attr
                    pass
                elif isinstance(val, keepnote.notebook.UnknownAttr):
                    # write unknown attrs if they are strings
                    out.write('<attr key="%s">%s</attr>\n' %
                              (key, escape(val.value)))
                else:
                    # drop attribute
                    pass
                
            out.write("</node>\n")
            out.close()
        except Exception, e:
            raise keepnote.notebook.NoteBookError(_("Cannot write meta data"), e)



    def _read_meta_data(self, filename, attr_defs):
        """Read a node meta data file"""
        
        attr = {}

        try:
            tree = ET.ElementTree(file=filename)
        except Exception, e:
            raise keepnote.notebook.NoteBookError(_("Error reading meta data file"), e)

        # check root
        root = tree.getroot()
        if root.tag != "node":
            raise keepnote.notebook.NoteBookError(_("Root tag is not 'node'"))
        
        # iterate children
        for child in root:
            if child.tag == "version":
                attr["version"] = int(child.text)
            elif child.tag == "attr":
                key = child.get("key", None)
                if key is not None:
                    attr_parser = attr_defs.get(key, None)
                    if attr_parser is not None:
                        attr[key] = attr_parser.read(child.text)
                    else:
                        # unknown attribute is read as a UnknownAttr
                        attr[key] = keepnote.notebook.UnknownAttr(child.text)

        return attr


    def create_node(self, node, path=None):

        if path is None:
            path = self.get_node_path(node)
        if path is None:
            # use title to set path
            parent_path = node.get_parent().get_path()
            path = keepnote.notebook.get_valid_unique_filename(
                parent_path, node.get_attr("title", _("New Page")))
            self.set_node_basename(node, path)

        try:
            os.mkdir(path)
            self.write_node_meta_data(node)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Cannot create node"), e)

    def delete_node(self, node):
        try:
            shutil.rmtree(node.get_path())
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Do not have permission to delete"), e)
        

    def move_node(self, node, new_parent):
        
        old_path = self.get_node_path(node)
        new_parent_path = self.get_node_path(new_parent)
        new_path = keepnote.notebook.get_valid_unique_filename(
            new_parent_path, node.get_attr("title", _("New Page")))

        try:
            os.rename(old_path, new_path)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Do not have permission for move"), e)

        return new_path

    def rename_node(self, node, title):
        
        # try to pick a path that closely resembles the title
        path = self.get_node_path(node)
        parent_path = os.path.dirname(path)
        path2 = keepnote.notebook.get_valid_unique_filename(parent_path, title)

        try:
            os.rename(path, path2)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Cannot rename '%s' to '%s'" % (path, path2)), e)
        
        return path2


    def node_list_children(self, node, path=None):
        if path is None:
            path = self.get_node_path(node)
            assert path is not None, node
        
        try:
            files = os.listdir(path)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Do not have permission to read folder contents: %s") % path, e)
        
        for filename in files:
            path2 = os.path.join(path, filename)
            if os.path.exists(get_node_meta_file(path2)):
                yield path2

