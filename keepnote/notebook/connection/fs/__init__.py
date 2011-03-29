"""

    KeepNote    
    
    Low-level Create-Read-Update-Delete (CRUD) interface for notebooks.

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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

"""
Strategy for detecting unmanaged notebook modifications.

When a notebook is first opened, there needs to be a mechanism for determining
whether the index (sqlite) is update to date.  There are several ways a
notebook can change on disk in unmanaged ways, that I would like to be 
able to recover from.  Below is a list of changes, methods for detecting
them, and solutions to updating the index.

CHANGE: Edits to "node.xml" files
DETECT: The mtime of the "node.xml" file should be newer than the last indexed
        mtime.
UPDATE: Read the "node.xml" file and index the attr.


CHANGE: Moving/renaming a node directory to a new location within the notebook.
DETECT: The new parent directory's mtime with be newer than the last indexed
        mtime.  The child directory being moved will often have no change in
        mtime.
UPDATE: A directory with newer mtime needs all of its children re-indexed.


CHANGE: Moving a new node directory into the notebook.  This would also require
        ensuring that nodeid's are still unique.
DETECT: The new parent directory's mtime with be newer than the last indexed
        mtime.  The child directory being moved will often have no change in
        mtime.
UPDATE: A directory with newer mtime needs all of its children re-indexed.
        In addition, if any of the children have never been seen before
        (nodeid not in index), then their entire subtree should re-indexed.


CHANGE: A payload file may change in contents (e.g. page.html) and would need
        to be re-indexed for fulltext search.
DETECT: The mtime for the payload file should be newer than the last indexed
        mtime.
UPDATE: Perhaps at this time unmanaged changes to payload files are not
        re-indexed.

"""

# python imports
import gettext
import mimetypes
import os
import sys
import shutil
import re
import traceback
from os.path import join, isdir, isfile
from os import listdir

# xml imports
from xml.sax.saxutils import escape
import xml.etree.cElementTree as ET


# keepnote imports
from keepnote import safefile
from keepnote import trans
from keepnote.notebook.connection.fs import index as notebook_index
from keepnote.notebook.connection import \
    NoteBookConnection, UnknownNode, UnknownFile, NodeExists, \
    CorruptIndex, ConnectionError, path_basename
import keepnote
import keepnote.notebook

_ = trans.translate


# constants

XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""

NODE_META_FILE = u"node.xml"
NOTEBOOK_META_DIR = u"__NOTEBOOK__"
LOSTDIR = u"lost_found"



#=============================================================================
# filenaming scheme

def get_node_meta_file(nodepath):
    """Returns the metadata file for a node"""
    return os.path.join(nodepath, NODE_META_FILE)

def get_pref_file(nodepath):
    """Returns the filename of the notebook preference file"""
    return os.path.join(nodepath, keepnote.notebook.PREF_FILE)

def get_lostdir(nodepath):
    return os.path.join(nodepath, NOTEBOOK_META_DIR, LOSTDIR)


def path_local2node(filename):
    """
    Converts a local path to a node path

    On unix:

      aaa/bbb/ccc  =>  aaa/bbb/ccc

    On windows:

      aaa\bbb\ccc  =>  aaa/bbb/ccc
    """

    if os.path.sep == "/":
        return filename
    return filename.replace(os.path.sep, "/")


def path_node2local(filename):
    """
    Converts a node path to a local path

    On unix:

      aaa/bbb/ccc  =>  aaa/bbb/ccc

    On windows:

      aaa/bbb/ccc  =>  aaa\bbb\ccc
    """
    
    if os.path.sep == "/":
        return filename
    return filename.replace("/", os.path.sep)
    

def get_node_filename(node_path, filename):
    """
    Returns a full local path to a node file

    node_path  -- local path to a node
    filename   -- node path to attached file
    """
    return os.path.join(node_path, path_node2local(filename))


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
        if os.path.isfile(os.path.join(child_path, u"node.xml")):
            yield child_path


def last_node_change2(path):
    """Returns the last modification time underneath a path in the notebook"""

    # NOTE: mtime is updated for a directory, whenever any of the files 
    # within the directory are modified.
    
    mtime = os.stat(path).st_mtime
    for child_path in iter_child_node_paths(path):
        mtime = max(mtime, last_node_change2(child_path))
    return mtime


def last_node_change(path):
    """Returns the last modification time underneath a path in the notebook"""

    # NOTE: mtime is updated for a directory, whenever any of the files 
    # within the directory are modified.

    stat = os.stat

    mtime = stat(path).st_mtime

    for dirpath, dirnames, filenames in os.walk(path):
        mtime = max(mtime, stat(dirpath).st_mtime)
        if u"node.xml" in filenames:
            mtime = max(mtime, stat(join(dirpath, u"node.xml")).st_mtime)
    
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

        queue.extend(iter_child_node_paths(path))

_mtime_cache = {}
def get_path_mtime(path):
    mtime = _mtime_cache.get(path, None)
    if mtime is None:
        mtime = _mtime_cache[path] = os.stat(path).st_mtime
    return mtime

def mark_path_outdated(path):
    os.utime(path, None)
    mtime = _mtime_cache.get(path, None)
    if mtime is not None:
        del _mtime_cache[path]


#=============================================================================
# path cache

class PathCacheNode (object):
    """Cache information for a node"""

    def __init__(self, nodeid, basename, parent):
        self.nodeid = nodeid
        self.basename = basename
        self.parent = parent
        self.children = set()
        self.children_complete = False
        


class PathCache (object):
    """
    An in-memory cache of filesystem paths for nodeids
    """

    def __init__(self, rootid=None, rootpath=""):
        self._nodes = {None: None}
        
        if rootid:
            self.add(rootid, rootpath, None)


    def clear(self):
        """Clears cache"""
        self._nodes.clear()
        self._nodes[None] = None


    def has_node(self, nodeid):
        """Returns True if node in cache"""
        return nodeid in self._nodes


    def get_path_list(self, nodeid):
        """
        Returns list representing a path for a nodeid
        Returns None if nodeid is not cached
        """
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
        
        return path_list


    def get_path(self, nodeid):
        """
        Returns path for a nodeid
        Returns None if nodeid is not cached
        """

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
        """
        Returns basename of path for a nodeid
        Returns None if nodeid is not cached
        """
        node = self._nodes.get(nodeid, None)
        if node:
            return node.basename
        else:
            return None
    
    
    def get_parentid(self, nodeid):
        """
        Returns parentid of a nodeid
        Returns None if nodeid is not cached
        """
        node = self._nodes.get(nodeid, None)
        if node and node.parent:
            return node.parent.nodeid
        else:
            return None


    def get_children(self, nodeid):
        """
        Returns iterator of the child ids of a nodeid
        Returns None if nodeid is not cached or children have not been read
        """
        node = self._nodes.get(nodeid, None)
        if node and node.children_complete:
            return (child.nodeid for child in node.children)
        else:
            return None

    def set_children_complete(self, nodeid, complete):
        node = self._nodes.get(nodeid, None)
        if node:
            node.children_complete = complete
    

    def add(self, nodeid, basename, parentid):
        """Add a new nodeid, basename, and parentid to the cache"""
        
        parent = self._nodes.get(parentid, 0)
        if parent is 0:
            raise UnknownNode("unknown parent %s" % 
                              repr((basename, parentid, self._nodes)))
        node = self._nodes.get(nodeid, None)
        if node:
            node.parent = parent
            node.basename = basename
        else:
            node = self._nodes[nodeid] = PathCacheNode(nodeid, basename, parent)
        if parent:
            parent.children.add(node)

        
    def remove(self, nodeid):
        """Remove a nodeid from the cache"""
        if nodeid in self._nodes:
            node = self._nodes.get(nodeid)
            node.parent.children.remove(node)
            del self._nodes[nodeid]


    def move(self, nodeid, new_basename, parentid):
        """move nodeid to a new parent"""
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

                

# TODO: figure out how to do attribute defs.  Is it really needed?  
# Maybe storage should always know datatype of attr, so attr defs are not
# needed.
# would I want to enable validation though?  and managed attr using attrids?
# or does this not belong at the connection level.


class NoteBookConnectionFS (NoteBookConnection):
    def __init__(self, notebook):
        NoteBookConnection.__init__(self)
        
        self._filename = None
        self._notebook = notebook
        self._index = None
        self._path_cache = PathCache()
        self._rootid = None

        # attributes to not write to disk, they can be derived
        self._attr_suppress = set(["parentids", "childids"])

        # NOTES:
        # - I only use the notebook object for assesing attrdefs and
        # for setuping up the index.
        # try to remove.
    

    #================================
    # Filesystem-specific API (may not be supported by some connections)
    
    def get_node_path(self, nodeid):
        """Returns the path of the node"""
        return self._get_node_path(nodeid)
    
    
    def get_node_basename(self, nodeid):
        """Returns the basename of the node"""
        basename = self._path_cache.get_basename(nodeid)
        if basename is None and self._index:
            # fallback to index
            node = self._index.get_node(nodeid)
            if node:
                basename = node["basename"]
        if basename is None:
            raise UnknownNode(nodeid)
        return basename


    # TODO: returning a fullpath to a file is not fully portable
    # will eventually need some kind of fetching mechanism

    # TODO: don't allow .. .
    
    def get_file(self, nodeid, filename, _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
        return get_node_filename(path, filename)


    #===========================
    # Private path API

    def _get_node_path(self, nodeid):
        """Returns the path of the nodeid"""
        
        path = self._path_cache.get_path(nodeid)
        if path is None and self._index:
            # fallback to index
            path_list = self._index.get_node_path(nodeid)
            if path_list is not None:
                path = os.path.join(* path_list)
        if path is None:
            raise UnknownNode(nodeid)
        return path


    def _get_node_name_path(self, nodeid):
        """Returns the path of the nodeid"""
        
        path = self._path_cache.get_path_list(nodeid)
        if path is None and self._index:
            # fallback to index
            path = self._index.get_node_path(nodeid)
        if path is None:
            raise UnknownNode(nodeid)
        return path


    def _get_node_mtime(self, nodeid):
        """mtime (modification time) for nodeid"""
        return os.stat(self._get_node_path(nodeid)).st_mtime


    def _get_lostdir(self):
        return get_lostdir(self._filename)

    def _move_to_lostdir(self, filename):
        """Moves a file/dir to the lost_found directory"""
        
        lostdir = self._get_lostdir()
        new_filename = keepnote.notebook.get_unique_filename(
            lostdir, os.path.basename(filename),  sep=u"-")
        
        keepnote.log_message("moving data to lostdir '%s' => '%s'\n" % 
                             (filename, new_filename))
        try:
            os.rename(filename, new_filename)
        except OSError, e:
            raise ConnectionError("unable to store lost file '%s'" 
                                  % filename, e)
        
            

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
        

    def create_root(self, nodeid, attr):
        """Create the root node"""
        if self._filename is None:
            raise ConnectionError("connect() has not been called")

        self.create_node(nodeid, attr, self._filename, True)

        # make lost and found        
        lostdir = self._get_lostdir()
        if not os.path.exists(lostdir):
            os.makedirs(lostdir)
    

    def create_node(self, nodeid, attr, _path=None, _root=False):
        """Create a node"""
        
        # check for existing nodeid
        if self.has_node(nodeid):
            raise NodeExists(nodeid)

        # generate a new nodeid if one is not given
        if nodeid is None:
            nodeid = keepnote.notebook.new_nodeid()

        # determine parentid
        if _root:
            # we are creating the root node, therefore there is no parent
            parentid = None
        else:
            # get parent from attr
            parentids = attr.get("parentids", None)
            # if parentids is None or [], use rootid as default
            parentid = parentids[0] if parentids else self._rootid

        # if no path, use title to set path
        if _path is None:
            title = attr.get("title", _("New Page"))

            # TODO: handle case where parent does not currently exist
            # TODO: also handle case where parent finally shows up and
            # reunites with its children in the orphans dir
            parent_path = self._get_node_path(parentid)
            path = keepnote.notebook.get_valid_unique_filename(
                parent_path, title)
        else:
            path = _path
            
        # initialize with no children
        attr["childrenids"] = []

        # determine basename
        basename = os.path.basename(path) if parentid else path

        # make directory and write attr
        try:
            os.mkdir(path)
            self._write_attr(self._get_node_attr_file(nodeid, path), 
                             attr, self._notebook.attr_defs)
            self._path_cache.add(nodeid, basename, parentid)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Cannot create node"), e)
        
        # update index
        if self._index:
            self._index.add_node(nodeid, parentid, basename, attr, 
                                 mtime=get_path_mtime(path))

        return nodeid
    
        
    def _read_root(self):
        """Read root node attr"""
        if self._filename is None:
            raise ConnectionError("connect() has not been called")
        
        attr = self._read_node(None, self._filename)
        self._rootid = attr["nodeid"]
        return attr
    
    
    def read_node(self, nodeid):
        """Read a node attr"""
        
        path = self._get_node_path(nodeid)
        parentid = self._get_parentid(nodeid)
        return self._read_node(parentid, path)
    

    def has_node(self, nodeid):
        """Returns True if node exists"""
        return (self._path_cache.has_node(nodeid) or 
                (self._index and self._index.has_node(nodeid)))


    def update_node(self, nodeid, attr):
        """Write node attr"""
        
        #print self._index.get_attr(nodeid, "title")

        # TODO: support mutltiple parents 

        # determine if parentid has changed
        parentid = self._get_parentid(nodeid) # old parent
        parentids2 = attr.get("parentids", None) # new parent
        parentid2 = parentids2[0] if parentids2 else self._rootid
        
        # determine if title has changed
        title_index = self._index.get_attr(nodeid, "title") # old title

        # write attrs
        path = self._get_node_path(nodeid)
        self._write_attr(get_node_meta_file(path), attr, 
                         self._notebook.attr_defs)
        
        if parentid != parentid2:
            # move to a new parent
            self._move_node(nodeid, attr, parentid2)
        elif (parentid and title_index and 
              title_index != attr.get("title", "")):
            # rename node directory, but
            # do not rename root node dir (parentid is None)
            self._rename_node_dir(nodeid, attr, path, parentid2)
        else:
            # update index
            basename = os.path.basename(path)
            self._index.add_node(nodeid, parentid2, basename, attr, 
                                 mtime=get_path_mtime(path))
        

    def _rename_node_dir(self, nodeid, attr, path, new_parentid):
        """Renames a node directory to resemble attr['title']"""
        
        # try to pick a path that closely resembles the title
        title = attr.get("title", "")
        parent_path = os.path.dirname(path)
        path2 = keepnote.notebook.get_valid_unique_filename(parent_path, title)

        try:
            os.rename(path, path2)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(_("Cannot rename '%s' to '%s'" % (path, path2)), e)

        # update index
        basename = os.path.basename(path2)
        self._path_cache.move(nodeid, basename, new_parentid)
        self._index.add_node(nodeid, new_parentid, basename, attr, 
                             mtime=get_path_mtime(path2))


    def _move_node(self, nodeid, attr, new_parentid):
        """Move a node to a new parent"""

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
            
    
    def delete_node(self, nodeid):
        """Delete node"""
        try:
            shutil.rmtree(self._get_node_path(nodeid))
        except OSError, e:
            raise keepnote.notebook.NoteBookError(
                _("Do not have permission to delete"), e)

        self._path_cache.remove(nodeid)
        self._index.remove_node(nodeid)

        # TODO: do I also need to unindex all unreachable children?
                

    def read_data_as_plain_text(self, nodeid):
        """Iterates over the lines of the data file as plain text"""
        try:
            infile = self.open_file(
                nodeid, keepnote.notebook.PAGE_DATA_FILE, "r", codec="utf-8")
            for line in keepnote.notebook.read_data_as_plain_text(infile):
                yield line
            infile.close()
        except:
            pass


    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        if self._rootid:
            return self._rootid
        else:
            return self._read_root()["nodeid"]
        

    def _get_parentid(self, nodeid):
        """Returns nodeid of parent of node"""
        # TODO: I could fallback to index for this too
        return self._path_cache.get_parentid(nodeid)


    def has_children(self, nodeid, _path=None, _index=True):
        """Returns True if node has children"""
        path = self._path_cache.get_path(nodeid) if _path is None else _path
        assert path is not None
        
        # if node is unchanged on disk (same mtime), 
        # use index to detect children
        #if _index and self._index:
        #    mtime = get_path_mtime(path)
        #    index_mtime = self._index.get_node_mtime(nodeid)
        #    if mtime <= index_mtime:
        #        return self._index.has_children(nodeid)
        
        try:
            files = os.listdir(path)
        except OSError, e:
            raise keepnote.notebook.NoteBookError(
                _("Do not have permission to read folder contents: %s") 
                % path, e)
        
        for filename in files:
            path2 = os.path.join(path, filename)
            if os.path.exists(get_node_meta_file(path2)):
                return True

        return False

    
    def _list_children_attr(self, nodeid, _path=None, _index=True):
        """List attr of children nodes of nodeid"""
        path = self._path_cache.get_path(nodeid) if _path is None else _path
        assert path is not None
        

        files = None
        mtime = index_mtime = None
        if _index and self._index:
            try:
                # if node is unchanged on disk (same mtime), 
                # use index to detect children
                mtime = get_path_mtime(path)
                index_mtime = self._index.get_node_mtime(nodeid)
                if mtime <= index_mtime:
                    files = list(row[1] for row in 
                                 self._index.list_children(nodeid))
            except Exception, e:
                pass

        if files is None:
            try:    
                files = os.listdir(path)
            except:
                raise keepnote.notebook.NoteBookError(
                    _("Do not have permission to read folder contents: %s") 
                    % path, e)           
        
        
        for filename in files:
            path2 = os.path.join(path, filename)
            if os.path.exists(get_node_meta_file(path2)):
                try:
                    yield self._read_node(nodeid, path2)
                except keepnote.notebook.NoteBookError, e:
                    keepnote.log_error("error reading %s" % path2)
                    continue
                    # TODO: raise warning, not all children read

        self._path_cache.set_children_complete(nodeid, True)


    def _list_children_nodeids(self, nodeid, _path=None, _index=True):
        """List nodeids of children of node"""
        # try to use cache first
        children = self._path_cache.get_children(nodeid)
        if children is not None:
            return children

        path = self._path_cache.get_path(nodeid) if _path is None else _path
        assert path is not None
        
       
        # if node is unchanged on disk (same mtime), 
        # use index to detect children
        if _index and self._index:
            mtime = get_path_mtime(path)
            index_mtime = self._index.get_node_mtime(nodeid)
            if mtime <= index_mtime:
                return (row[0] for row in self._index.list_children(nodeid))

        return (attr["nodeid"]
                for attr in self._list_children_attr(nodeid, _path))



    def _read_node(self, parentid, path):
        """Reads a node from disk"""
        
        metafile = get_node_meta_file(path)
        attr = self._read_attr(metafile, self._notebook.attr_defs)
        attr["parentids"] = [parentid]
        if not self._validate_attr(attr):
            self._write_attr(metafile, attr, self._notebook.attr_defs)

        # update path cache
        nodeid = attr["nodeid"]
        basename = os.path.basename(path) if parentid else path  
        self._path_cache.add(nodeid, basename, parentid)
        
        
        # if node has changed on disk (newer mtime), then re-index it
        # if reading root node, index might not be initialized yet
        if self._index:
            try:
                mtime = get_path_mtime(path)
                index_mtime = self._index.get_node_mtime(nodeid)
                if mtime > index_mtime:
                    # mark children out of date
                    for path2 in iter_child_node_paths(path):
                        mark_path_outdated(path2)
                    
                    self._index.add_node(
                        nodeid, parentid, basename, attr, mtime)
                    
                    # TODO: make re-indexing smarter (use mtimes for partial
                    # reindexing) 
                    # record that more indexing is needed
                    self._index.set_index_needed(True)
            except:
                keepnote.log_error()
                pass    

        # supplement childids
        attr["childrenids"] = list(self._list_children_nodeids(nodeid, path))

        return attr
    
    
    def _get_node_attr_file(self, nodeid, path=None):
        """Returns the meta file for the node"""
        return self.get_file(nodeid, NODE_META_FILE, path)


    def _write_attr(self, filename, attr, attr_defs):
        """Write a node meta data file"""
        
        try:
            out = safefile.open(filename, "w", codec="utf-8")
            out.write(XML_HEADER)
            out.write("<node>\n"
                      "<version>%s</version>\n" % 
                      keepnote.notebook.NOTEBOOK_FORMAT_VERSION)
            
            for key, val in attr.iteritems():
                if key in self._attr_suppress:
                    continue

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


    def _read_attr(self, filename, attr_defs, recover=True):
        """Read a node meta data file"""
        
        attr = {}

        try:
            tree = ET.ElementTree(file=filename)
        except Exception, e:
            if recover:
                self._recover_attr(filename)
                return self._read_attr(filename, attr_defs, recover=False)
            
            raise keepnote.notebook.NoteBookError(
                _("Error reading meta data file"), e)

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


    def _recover_attr(self, filename):
        
        self._move_to_lostdir(filename)
        out = open(filename, "w")
        out.write("<node></node>")
        out.close()


    def _validate_attr(self, attr):
        
        nodeid = attr.get("nodeid", None)
        if nodeid is None:
            nodeid = attr["nodeid"] = keepnote.notebook.new_nodeid()
            return False

        # TODO: ensure no duplicated nodeid's

        return True



    #===============
    # file API
    
    def open_file(self, nodeid, filename, mode="r", 
                        codec=None, _path=None):
        """Open a node file"""        
        path = self._get_node_path(nodeid) if _path is None else _path
        fullname = get_node_filename(path, filename)
        dirpath = os.path.dirname(fullname)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)

        return safefile.open(fullname, mode, codec=codec)

    def delete_file(self, nodeid, filename, _path=None):
        """Delete a node file"""
        path = self._get_node_path(nodeid) if _path is None else _path
        filepath = get_node_filename(path, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
        else:
            shutil.rmtree(filepath)

    
    def rename_file(self, nodeid, filename, new_filename):
        """Rename a node file"""

        path = self._get_node_path(nodeid) if _path is None else _path
        filepath = get_node_filename(path, filename)
        new_filepath = get_node_filename(path, new_filename)

        # remove files in the way
        if os.path.isfile(new_filepath):
            os.remove(new_filepath)
        if os.path.isdir(new_filename):
            shutil.rmtree(new_filepath)

        # rename file
        os.rename(filepath, new_filepath)
        

    def list_files(self, nodeid, filename="", _path=None):
        """
        List data files in node

        directories have a '/' at the end of their name
        """

        path = self._get_node_path(nodeid) if _path is None else _path
        path = get_node_filename(path, filename)

        try:
            filenames = os.listdir(path)
        except:
            raise UnknownFile()

        for filename in filenames:
            if (filename != NODE_META_FILE and 
                not filename.startswith("__")):
                fullname = os.path.join(path, filename)
                if not os.path.exists(get_node_meta_file(fullname)):
                    # ensure directory is not a node
                    
                    if os.path.isdir(fullname):
                        yield filename + "/"
                    else:
                        yield filename


    def mkdir(self, nodeid, filename, _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
        fullname = get_node_filename(path, filename)
        if not os.path.exists(fullname):
            os.mkdir(fullname)
    

    def file_exists(self, nodeid, filename, _path=None):
        path = self._get_node_path(nodeid) if _path is None else _path
        return os.path.exists(get_node_filename(path, filename))

    
    def copy_node_files(self, nodeid1, nodeid2):
        """
        Copy all data files from nodeid1 to nodeid2
        """
        
        path1 = self._get_node_path(nodeid1)
        path2 = self._get_node_path(nodeid2)

        for filename in self.list_files(nodeid1, path1):
            fullname1 = get_node_filename(path1, filename)
            fullname2 = get_node_filename(path2, filename)
            
            if os.path.isfile(fullname1):
                shutil.copy(fullname1, fullname2)
            elif os.path.isdir(fullname1):
                shutil.copytree(fullname1, fullname2)

    
    def copy_node_file(self, nodeid1, filename1, nodeid2, filename2,
                       _path1=None, _path2=None):
        """
        Copy a file between two nodes

        if node is None, filename is assumed to be a local file
        """

        if nodeid1 is None:
            fullname1 = filename1
        else:
            path1 = self._get_node_path(nodeid1) if not _path1 else _path1
            fullname1 = get_node_filename(path1, filename1)

        if nodeid2 is None:
            fullname2 = filename2
        else:
            path2 = self._get_node_path(nodeid2) if not _path2 else _path2
            fullname2 = get_node_filename(path2, filename2)
        
        if os.path.isfile(fullname1):
            shutil.copy(fullname1, fullname2)
        elif os.path.isdir(fullname1):
            shutil.copytree(fullname1, fullname2)


    def new_filename(self, nodeid, new_filename, ext=u"", sep=u" ", number=2, 
                     return_number=False, use_number=False, ensure_valid=True,
                     _path=None):

        # TODO: use proper local and node path's (get_node_filename)

        # TODO: move this out of the connection

        # TODO: add assert for valid new_filename

        path = self._get_node_path(nodeid) if _path is None else _path
        if ext is None:
            new_filename, ext = os.path.splitext(new_filename)

        basename = path_basename(new_filename)
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


    #---------------------------------
    # index management

    def init_index(self):
        """Initialize the index"""
        self._index = notebook_index.NoteBookIndex(
            self, self._get_index_file())
        
    def index_needed(self):
        return self._index.index_needed()

    def clear_index(self):
        return self._index.clear()

    def index_all(self):
        for node in self._index.index_all():
            yield node

    def _get_index_file(self):

        notebook = self._notebook
        index_dir = notebook.pref.get("index_dir", default=u"")
        if not index_dir or not os.path.exists(index_dir):
            index_dir = notebook.get_pref_dir()
        
        return os.path.join(index_dir, notebook_index.INDEX_FILE)
        

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
        
        path = self._get_node_path(nodeid)
        basename = os.path.basename(path)
        parentid = attr["parentids"][0]
        self._index.add_node(nodeid, parentid, basename, attr, 
                             mtime=get_path_mtime(path))

    
    def get_node_path_by_id(self, nodeid):
        """Lookup node by nodeid"""
        return self._index.get_node_path(nodeid)
        

    def get_attr_by_id(self, nodeid, key):
        return self._index.get_attr(nodeid, key)

    

