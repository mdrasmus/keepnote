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
    """Returns the last modification time underneath a path in the notebook"""

    # NOTE: mtime is updated for a directory, whenever any of the files 
    # within the directory are modified.
    
    mtime = os.stat(path).st_mtime
    for child_path in iter_child_node_paths(path):
        mtime = max(mtime, last_node_change(child_path))
    return mtime


def find_node_changes(path, last_mtime):
    """Returns the last modification time underneath a path in the notebook"""

    # NOTE: mtime is updated for a directory, whenever any of the files 
    # within the directory are modified.
    
    queue = [path]

    while len(queue) > 0:
        path = queue.pop()

        mtime = os.stat(path).st_mtime
        if mtime > last_mtime:
            yield path, mtime

        for child_path in iter_child_node_paths(path):
            queue.append(child_path)

def get_path_mtime(path):
    return os.stat(path).st_mtime

#=============================================================================

# TODO: make base class for connection



class PathCacheNode (object):
    def __init__(self, nodeid, basename, parent):
        self.nodeid = nodeid
        self.basename = basename
        self.parent = parent
        self.children = set()


class PathCache (object):
    def __init__(self, rootid=None, rootpath=""):
        self._nodes = {None: None}
        
        if rootid:
            self.add(rootid, rootpath, None)


    def clear(self):
        self._nodes.clear()
        self._nodes[None] = None


    def get_path_list(self, nodeid):
        
        path_list = []
        node = self._paths.get(nodeid, None)

        # node is not in cache
        if node is None:
            return None

        # node is in cache, return path list
        while node is not None:
            path_list.append(node.basename)
            node = node.parent
        path_list.reverse()
        
        return path_list


    def get_path(self, nodeid):
        
        path_list = []
        node = self._nodes.get(nodeid, None)

        # node is not in cache
        if node is None:
            return None

        # node is in cache, return path list
        while node is not None:
            path_list.append(node.basename)
            node = node.parent
        path_list.reverse()
        
        return os.path.join(*path_list)

    
    def get_basename(self, nodeid):
        return self._nodes[nodeid].basename
    
    
    def get_parentid(self, nodeid):
        
        node = self._nodes.get(nodeid, None)
        if node.parent:
            return node.parent.nodeid
        else:
            return None


    def get_children(self, nodeid):
        node = self._nodes.get(nodeid, None)
        if node:
            return (child.nodeid for child in node.children)
        else:
            return None

    

    def add(self, nodeid, basename, parentid):
        
        parent = self._nodes.get(parentid, 0)
        if parent is 0:
            print basename, parentid, self._nodes
            raise Exception("unknown parent")
        node = self._nodes.get(nodeid, None)
        if node:
            node.parent = parent
            node.basename = basename
        else:
            node = self._nodes[nodeid] = PathCacheNode(nodeid, basename, parent)
        if parent:
            parent.children.add(node)

        
    def remove(self, nodeid):
        if nodeid in self._nodes:
            node = self._nodes.get(nodeid)
            node.parent.children.remove(node)
            del self._nodes[nodeid]


    def move(self, nodeid, new_basename, parentid):
        
        node = self._nodes.get(nodeid, None)
        parent = self._nodes.get(parentid, 0)
        
        if node is not None:
            if parent is not 0:
                # update cache
                node.parent.children.remove(node)
                node.parent = parent
                node.basename = new_basename
                parent.children.add(node)
            else:
                # since new parent is not cached,
                # remove node from cache
                self.remove(nodeid)

                



class NoteBookConnection (object):
    def __init__(self, notebook, node_factory):
        self._filename = None
        self._notebook = notebook
        self._node_factory = node_factory
        self._index = None
        self._path_cache = PathCache()
        self._rootid = None

        # NOTES:
        # - I only use the notebook object for assesing attrdefs and
        # for setuping up the index.
    

    #================================
    # Filesystem-specific API (may not be supported by some connections)
    
    def get_node_path(self, node):
        """Returns the path of the node"""
        return self._get_node_path(node.get_attr("nodeid"))
    
    
    def get_node_basename(self, nodeid):
        return self._path_cache.get_basename(nodeid)
    

    #===========================
    # Private path API

    def _get_node_path(self, nodeid):
        """Returns the path of the nodeid"""
        
        path = self._path_cache.get_path(nodeid)
        if path is None and self._index:
            # fallback to index
            path = os.path.join(* self._index.get_node_path(nodeid))
        if path is None:
            raise Exception("unknown path")
        return path


    def _get_node_name_path(self, nodeid):
        """Returns the path of the nodeid"""
        
        path = self._path_cache.get_path_list(nodeid)
        if path is None and self._index:
            # fallback to index
            path = self._index.get_node_path(nodeid)
        if path is None:
            raise Exception("unknown path")
        return path


    def _get_node_mtime(self, nodeid):
        """mtime (modification time) for nodeid"""
        return os.stat(self._get_node_path(nodeid)).st_mtime


    #======================
    # Node I/O API

    def connect(self, filename):
        """Make a new connection"""
        self._filename = filename

        
    def close(self):
        """Close connection"""
        self._filename = None
        self._index.close()
        

    def save(self):
        """Save any unsynced state"""
        self._index.save()

        
    def read_root(self):
        """Read root node attr"""
        assert self._filename is not None
        
        metafile = get_node_meta_file(self._filename)
        attr = self._read_attr(metafile, self._notebook.attr_defs)
        if not self._validate_attr(attr):
            self._write_attr(metafile, attr, self._notebook.attr_defs)
            print attr
        self._rootid = attr["nodeid"]

        # update path cache
        nodeid = attr["nodeid"]
        self._path_cache.add(nodeid, self._filename, None)
        
        # NOTE: do not index yet.  It might not be setup yet

        return attr
    
    
    def read_node(self, nodeid):
        """Read a node attr"""

        path = self._get_node_path(nodeid)
        metafile = get_node_meta_file(path)
        attr = self._read_attr(metafile, self._notebook.attr_defs)
        if not self._validate_attr(attr):
            self._write_attr(metafile, attr, self._notebook.attr_defs)
            print attr
        
        # if node has changed on disk (newer mtime), then re-index it
        mtime = get_path_mtime(path)
        index_mtime = self._index.get_node_mtime(nodeid)
        if mtime > index_mtime:
            parentid = self.get_parentid(nodeid)
            basename = os.path.basename(path)
            self._index.add_node(nodeid, parentid, basename, attr, mtime)
            
        return attr
    

    def update_node(self, nodeid, attr):
        """Write node attr"""

        path = self._path_cache.get_path(nodeid)
        self._write_attr(self._get_node_attr_file(nodeid, path), 
                         attr, self._notebook.attr_defs)

        # update index
        basename = os.path.basename(path)
        parentid = self._path_cache.get_parentid(nodeid)
        self._index.add_node(nodeid, parentid, basename, attr, 
                             mtime=get_path_mtime(path))


    def create_root(self, filename, nodeid, attr):
        self.create_node(nodeid, None, attr, filename)
    

    def create_node(self, nodeid, parentid, attr, _path=None):

        if nodeid is None:
            nodeid = keepnote.notebook.new_nodeid()

        # if no path, use title to set path
        if _path is None:
            title = attr.get("title", _("New Page"))
            parent_path = self._get_node_path(parentid)
            path = keepnote.notebook.get_valid_unique_filename(
                parent_path, title)
        else:
            path = _path
        if parentid is not None:
            basename = os.path.basename(path)
        else:
            basename = path

        try:
            os.mkdir(path)
            self._write_attr(self._get_node_attr_file(nodeid, path), 
                             attr, self._notebook.attr_defs)
            self._path_cache.add(nodeid, basename, parentid)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Cannot create node"), e)

        return nodeid
        
    
    def delete_node(self, nodeid):
        try:
            shutil.rmtree(self._get_node_path(nodeid))
        except OSError, e:
            raise keepnote.notebook.NoteBookError(
                _("Do not have permission to delete"), e)

        self._path_cache.remove(nodeid)
        self._index.remove_node(nodeid)
        

    def move_node(self, nodeid, new_parentid, attr):
        
        old_path = self._get_node_path(nodeid)
        new_parent_path = self._get_node_path(new_parentid)
        new_path = keepnote.notebook.get_valid_unique_filename(
            new_parent_path, attr.get("title", _("New Page")))

        try:
            os.rename(old_path, new_path)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Do not have permission for move"), e)

        # update index
        basename = os.path.basename(new_path)
        self._path_cache.move(nodeid, basename, new_parentid)
        self._index.add_node(nodeid, new_parentid, basename, attr, 
                             mtime=get_path_mtime(new_path))


    def rename_node(self, nodeid, attr, title):
        
        # try to pick a path that closely resembles the title
        path = self._get_node_path(nodeid)
        parent_path = os.path.dirname(path)
        path2 = keepnote.notebook.get_valid_unique_filename(parent_path, title)

        try:
            os.rename(path, path2)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Cannot rename '%s' to '%s'" % (path, path2)), e)

        # update index
        basename = os.path.basename(path2)
        parentid = self._path_cache.get_parentid(nodeid)
        self._path_cache.move(nodeid, basename, parentid)
        self.update_index_node(nodeid, attr)
        
        return path2


    def read_data_as_plain_text(self, nodeid):
        """Iterates over the lines of the data file as plain text"""
        try:
            infile = self.open_node_file(
                nodeid, keepnote.notebook.PAGE_DATA_FILE, "r", codec="utf-8")
            for line in keepnote.notebook.read_data_as_plain_text(infile):
                yield line
            infile.close()
        except:
            pass


    def get_rootid(self):
        if self._rootid:
            return self._rootid
        else:
            return self._read_root()["nodeid"]
        

    def get_parentid(self, nodeid):
        
        # TODO: I could fallback to index for this too
        return self._path_cache.get_parentid(nodeid)

    
    def list_children_attr(self, nodeid, _path=None):
        
        path = self._path_cache.get_path(nodeid) if _path is None else _path
        assert path is not None

        try:
            files = os.listdir(path)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(
                _("Do not have permission to read folder contents: %s") 
                % path, e)
        
        for filename in files:
            path2 = os.path.join(path, filename)
            if os.path.exists(get_node_meta_file(path2)):
                try:
                    yield self._read_node(nodeid, path2)
                except keepnote.notebook.NoteBookError, e:
                    print >>sys.stderr, "error reading", path2
                    traceback.print_exception(*sys.exc_info())
                    continue
                    # TODO: raise warning, not all children read


    def list_children_nodeids(self, nodeid, _path=None):

        # try to use cache first
        children = self._path_cache.get_children(nodeid)
        if children is not None:
            return children
        else:
            return (attr["nodeid"]
                    for attr in self.list_children_attr(nodeid, _path))



    def _read_node(self, parentid, path):
        """Reads a node from disk"""

        metafile = get_node_meta_file(path)
        attr = self._read_attr(metafile, self._notebook.attr_defs)
        if not self._validate_attr(attr):
            self._write_attr(metafile, attr, self._notebook.attr_defs)
            print attr

        # update path cache
        nodeid = attr["nodeid"]
        basename = os.path.basename(path)
        self._path_cache.add(nodeid, basename, parentid)
        
        # if node has changed on disk (newer mtime), then re-index it
        mtime = get_path_mtime(path)
        index_mtime = self._index.get_node_mtime(nodeid)
        if mtime > index_mtime:
            self._index.add_node(nodeid, parentid, basename, attr, mtime)

        return attr
    
    
    def _get_node_attr_file(self, nodeid, path=None):
        """Returns the meta file for the node"""
        return self.get_node_file(nodeid, keepnote.notebook.NODE_META_FILE,
                                  path)


    def _write_attr(self, filename, attr, attr_defs):
        """Write a node meta data file"""
        
        try:
            out = safefile.open(filename, "w", codec="utf-8")
            out.write(XML_HEADER)
            out.write("<node>\n"
                      "<version>%s</version>\n" % 
                      keepnote.notebook.NOTEBOOK_FORMAT_VERSION)
            
            for key, val in attr.iteritems():
                attr_def = attr_defs.get(key, None)
                
                if attr_def is not None:
                    out.write('<attr key="%s">%s</attr>\n' %
                              (key, escape(attr_def.write(val))))
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
            raise keepnote.notebook.NoteBookError(
                _("Cannot write meta data"), e)


    def _read_attr(self, filename, attr_defs):
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


    def _validate_attr(self, attr):
        
        nodeid = attr.get("nodeid", None)
        if nodeid is None:
            nodeid = attr["nodeid"] = keepnote.notebook.new_nodeid()
            return False

        # TODO: ensure no duplicated nodeid's

        return True



    #===============
    # file API

    # XXX: is path_join needed?  or can I always specify paths with '/'?

    def path_join(self, *parts):
        return os.path.join(*parts)

    # TODO: returning a fullpath to a file is not fully portable
    # will eventually need some kind of fetching mechanism
    
    def get_node_file(self, nodeid, filename, _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
        return os.path.join(path, filename)

    
    def open_node_file(self, nodeid, filename, mode="r", 
                        codec=None, _path=None):
        """Open a file contained within a node"""        
        path = self._get_node_path(nodeid) if _path is None else _path
        return safefile.open(
            os.path.join(path, filename), mode, codec=codec)

    def delete_node_file(self, nodeid, filename, _path=None):
        """Open a file contained within a node"""
        path = self._get_node_path(nodeid) if _path is None else _path
        os.remove(os.path.join(path, filename))


    def new_filename(self, nodeid, new_filename, ext=u"", sep=u" ", number=2, 
                     return_number=False, use_number=False, ensure_valid=True,
                     _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
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
            return keepnote.notebook.relpath(fullname, path), number
        else:
            return keepnote.notebook.relpath(fullname, path)



    def mkdir(self, nodeid, filename, _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
        fullname = os.path.join(path, filename)
        if not os.path.exists(fullname):
            os.mkdir(fullname)

    
    def isfile(self, nodeid, filename, _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
        return os.path.isfile(os.path.join(path, filename))


    def path_exists(self, nodeid, filename, _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
        return os.path.exists(os.path.join(path, filename))


    def path_basename(self, filename):
        return os.path.basename(filename)

        
    def listdir(self, nodeid, filename=None, _path=None):
        """
        List data files in node
        """

        path = self._get_node_path(nodeid) if _path is None else _path
        if filename is not None:
            path = os.path.join(path, filename)
        
        for filename in os.listdir(path):
            if (filename != keepnote.notebook.NODE_META_FILE and 
                not filename.startswith("__")):
                fullname = os.path.join(path, filename)
                if not os.path.exists(get_node_meta_file(fullname)):
                    # ensure directory is not a node
                    yield filename

    
    def copy_node_files(self, nodeid1, nodeid2):
        """
        Copy all data files from nodeid1 to nodeid2
        """
        
        path1 = self._get_node_path(nodeid1)
        path2 = self._get_node_path(nodeid2)

        for filename in self.node_listdir(nodeid1, path1):
            fullname1 = os.path.join(path1, filename)
            fullname2 = os.path.join(path2, filename)
            
            if os.path.isfile(fullname1):
                shutil.copy(fullname1, fullname2)
            elif os.path.isdir(fullname1):
                shutil.copytree(fullname1, fullname2)

    
    def copy_node_file(self, nodeid1, filename1, nodeid2, filename2,
                       path1=None, path2=None):
        """
        Copy a file between two nodes

        if node is None, filename is assumed to be a local file
        """

        if nodeid1 is None:
            fullname1 = filename1
        else:
            if path1 is None:
                path1 = self._get_node_path(nodeid1)
            fullname1 = os.path.join(path1, filename1)

        if nodeid2 is None:
            fullname2 = filename2
        else:
            if path2 is None:
                path2 = self._get_node_path(nodeid2)
            fullname2 = os.path.join(path2, filename2)
        
        if os.path.isfile(fullname1):
            shutil.copy(fullname1, fullname2)
        elif os.path.isdir(fullname1):
            shutil.copytree(fullname1, fullname2)


    #---------------------------------
    # index management

    def init_index(self):
        """Initialize the index"""
        self._index = notebook_index.NoteBookIndex(self, self._notebook)
    
    def index_needed(self):
        return self._index.index_needed()

    def clear_index(self):
        return self._index.clear()

    def index_all(self):
        for node in self._index.index_all():
            yield node


    #---------------------------------
    # indexing/querying

    def index_attr(self, key, index_value=False):
        
        datatype = self._notebook.attr_defs[key].datatype

        if issubclass(datatype, basestring):
            index_type = "TEXT"
        elif issubclass(datatype, int):
            index_type = "INTEGER"
        elif issubclass(datatype, float):
            index_type = "FLOAT"
        else:
            raise Exception("unknown attr datatype '%s'" % repr(datatype))

        self._index.add_attr(notebook_index.AttrIndex(key, index_type, 
                                                      index_value=index_value))


    def search_node_titles(self, text):
        """Search nodes by title"""
        return self._index.search_titles(text)

    def search_node_contents(self, text):
        """Search nodes by content"""
        return self._index.search_contents(text)


    def has_fulltext_search(self):
        return self._index.has_fulltext_search()
    

    def update_index_node(self, nodeid, attr):
        """Update a node in the index"""
        
        path = self._path_cache.get_path(nodeid)
        basename = os.path.basename(path)
        parentid = self._path_cache.get_parentid(nodeid)
        self._index.add_node(nodeid, parentid, basename, attr, 
                             mtime=get_path_mtime(path))

    
    def get_node_path_by_id(self, nodeid):
        """Lookup node by nodeid"""
        return self._index.get_node_path(nodeid)
        

    def get_attr_by_id(self, nodeid, key):
        return self._index.get_attr(nodeid, key)

    

