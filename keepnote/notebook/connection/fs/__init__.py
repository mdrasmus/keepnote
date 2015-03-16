"""

    KeepNote

    Low-level Create-Read-Update-Delete (CRUD) interface for notebooks.

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

"""
Strategy for detecting unmanaged notebook modifications, which I also
call tampering.

When a notebook is first opened, there needs to be a mechanism for determining
whether the index (sqlite) is up to date.  There are several ways a
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
UPDATE: A directory with newer mtime needs all of its children re-indexed,
        but their child do not need to reindex as long as their mtimes
        check out.


CHANGE: Moving a new node directory into the notebook.  This would also require
        ensuring that nodeid's are still unique.
DETECT: The new parent directory's mtime will be newer than the last indexed
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


# TODO: orphan behavior

# Unknown parent behavior options
# 1. Perhaps we allow nodes without parentids, but if they have parentids then
#    they need to point to a valid node?
# 2. Or we allow parentids pointing to unknown nodes and store the data
#    in the orphandir until parent arrives.
# Maybe option 2 would work better with UnionConnection


# python imports
import os
import shutil
import re
from os.path import join

# xml imports
import xml.etree.cElementTree as ET


# keepnote imports
import keepnote
from keepnote import safefile, plist, maskdict
from keepnote import trans
import keepnote.notebook
from keepnote.notebook.connection import ConnectionError
from keepnote.notebook.connection import NodeExists
from keepnote.notebook.connection import NoteBookConnection
from keepnote.notebook.connection import UnknownNode
from keepnote.notebook.connection.fs import index as notebook_index
from keepnote.notebook.connection.fs.file import FileFS
from keepnote.notebook.connection.fs.file import get_node_filename
from keepnote.notebook.connection.fs.paths import get_node_meta_file
from keepnote.notebook.connection.fs.paths import NODE_META_FILE
from keepnote.notebook.connection.index import AttrIndex
from keepnote.timestamp import get_timestamp


_ = trans.translate

# constants
XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""

NOTEBOOK_META_DIR = u"__NOTEBOOK__"
LOSTDIR = u"lost_found"
ORPHANDIR = u"orphans"
MAX_LEN_NODE_FILENAME = 40


#=============================================================================
# filenaming scheme

def get_pref_file(nodepath):
    """Returns the filename of the notebook preference file"""
    return os.path.join(nodepath, keepnote.notebook.PREF_FILE)


def get_lostdir(nodepath):
    return os.path.join(nodepath, NOTEBOOK_META_DIR, LOSTDIR)


def get_orphandir(nodepath, nodeid=None):
    if nodeid is not None:
        if len(nodeid) > 2:
            return os.path.join(nodepath, NOTEBOOK_META_DIR, ORPHANDIR,
                                nodeid[:2], nodeid[2:])
        else:
            return os.path.join(nodepath, NOTEBOOK_META_DIR, ORPHANDIR,
                                nodeid[:2])
    else:
        return os.path.join(nodepath, NOTEBOOK_META_DIR, ORPHANDIR)


# TODO: think about how to handle "." and ".." in filenames


#=============================================================================
# functions for ensuring valid filenames in notebooks

REGEX_SLASHES = re.compile(ur"[/\\]")
REGEX_BAD_CHARS = re.compile(ur"[\*\?'&<>|`:;]")
REGEX_LEADING_UNDERSCORE = re.compile(ur"^__+")


def get_valid_filename(filename, default=u"folder",
                       maxlen=MAX_LEN_NODE_FILENAME):
    """
    Converts a filename into a valid one

    Strips bad characters from filename
    """
    filename = filename[:maxlen]
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


def get_valid_unique_filename(path, filename, ext=u"", sep=u" ", number=2,
                              return_number=False, use_number=False):
    """Returns a valid and unique version of a filename for a given path"""
    return keepnote.notebook.get_unique_filename(
        path, get_valid_filename(filename), ext, sep, number,
        return_number=return_number, use_number=use_number)


def get_valid_unique_filename_list(filenames, filename,
                                   ext=u"", sep=u" ", number=2,
                                   return_number=False, use_number=False):
    """Returns a valid and unique version of a filename for a given path"""
    return keepnote.notebook.get_unique_filename_list(
        filenames, get_valid_filename(filename), ext, sep, number,
        return_number=return_number, use_number=use_number)


def new_filename(conn, nodeid, new_filename, ext=u"", sep=u" ", number=2,
                 return_number=False, use_number=False, ensure_valid=True,
                 _path=None):

    filenames = list(conn.list_dir(nodeid,
                                   os.path.dirname(new_filename) + '/'))
    return new_filename_list(filenames, new_filename, ext=ext, sep=sep,
                             number=number,  return_number=return_number,
                             use_number=use_number, ensure_valid=ensure_valid,
                             _path=_path)


def new_filename_list(filenames, new_filename, ext=u"", sep=u" ", number=2,
                      return_number=False, use_number=False, ensure_valid=True,
                      _path=None):

    # TODO: use proper local and node path's (get_node_filename)

    # TODO: add assert for valid new_filename

    if ext is None:
        new_filename, ext = os.path.splitext(new_filename)

    if ensure_valid:
        fullname, number = get_valid_unique_filename_list(
            filenames, new_filename, ext, sep=sep, number=number,
            return_number=True, use_number=use_number)
    else:
        fullname, number = keepnote.notebook.get_unique_filename_list(
            filenames, new_filename, ext, sep=sep, number=number,
            return_number=True, use_number=use_number)

    if return_number:
        return fullname, number
    else:
        return fullname


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


def get_path_mtime2(path):
    mtime = _mtime_cache.get(path, None)
    if mtime is None:
        mtime = _mtime_cache[path] = os.stat(path).st_mtime
    return mtime


def get_path_mtime(path):
    return os.stat(path).st_mtime


def mark_path_outdated(path):
    os.utime(path, None)
    mtime = _mtime_cache.get(path, None)
    if mtime is not None:
        del _mtime_cache[path]


def read_attr(filename, set_extra=True):
    """
    Read a node meta data file. Returns an attr dict

    filename -- a filename or stream
    """
    try:
        tree = ET.ElementTree(file=filename)
    except Exception, e:
        raise ConnectionError(
            _(u"Error reading meta data file '%s'" % filename), e)

    # check root
    root = tree.getroot()
    if root.tag != "node":
        raise ConnectionError(_("Root tag is not 'node'"))

    # iterate children
    attr = {}
    extra = {}
    for child in root:
        if child.tag == "dict":
            attr = plist.load_etree(child)
        elif child.tag == "version":
            extra['version'] = int(child.text)
        elif child.tag == "id":
            extra['nodeid'] = child.text

    # For backward-compatibility, use attr nodeid to set extra if needed.
    if 'nodeid' not in extra:
        extra['nodeid'] = attr['nodeid']

    if set_extra:
        for key, value in extra.items():
            attr[key] = value

    return attr, extra


def write_attr(filename, nodeid, attr):
    """
    Write a node meta file

    filename -- a filename or stream
    attr     -- attribute dict
    """
    if isinstance(filename, basestring):
        out = safefile.open(filename, "w", codec="utf-8")

    # Ensure nodeid is consistent if given.
    nodeid2 = attr.get('nodeid')
    if nodeid2:
        assert nodeid == nodeid2, (nodeid, nodeid2)

    version = attr.get('version',
                       keepnote.notebook.NOTEBOOK_FORMAT_VERSION)
    out.write(u'<?xml version="1.0" encoding="UTF-8"?>\n'
              u'<node>\n'
              u'<version>%d</version>\n'
              u'<id>%s</id>\n' % (version, nodeid))
    plist.dump(attr, out, indent=2, depth=0)
    out.write(u'</node>\n')

    if isinstance(filename, basestring):
        out.close()


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
    def __init__(self, rootid=None, rootpath=u""):
        self._root_parent = object()
        self._nodes = {None: self._root_parent}

        if rootid:
            self.add(rootid, rootpath, self._root_parent)

    def clear(self):
        """Clears cache"""
        self._nodes.clear()
        self._nodes[None] = self._root_parent

    def has_node(self, nodeid):
        """Returns True if node in cache"""
        if nodeid is None:
            return False
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
        while node is not self._root_parent:
            if node is None:
                # path is not fully cached
                return None
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
        while node is not self._root_parent:
            if node is None:
                # path is not fully cached
                return None
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
        if node and node.parent and node.parent is not self._root_parent:
            return node.parent.nodeid
        else:
            return None

    def get_children(self, nodeid):
        """
        Returns iterator of the child ids of a nodeid
        Returns None if nodeid is not cached or children have not been read
        """
        node = self._nodes.get(nodeid)
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

        parent = self._nodes.get(parentid, None)
        #if parent is 0:
            # TODO: should I allow unknown parent?
            #raise UnknownNode("unknown parent %s" %
            #                  repr((basename, parentid, self._nodes)))
        node = self._nodes.get(nodeid, None)
        if node:
            node.parent = parent
            node.basename = basename
        else:
            node = self._nodes[nodeid] = PathCacheNode(
                nodeid, basename, parent)
        if parent and parent is not self._root_parent:
            parent.children.add(node)

    def remove(self, nodeid):
        """Remove a nodeid from the cache"""
        if nodeid in self._nodes:
            node = self._nodes.get(nodeid)
            if node.parent and node.parent is not self._root_parent:
                node.parent.children.remove(node)
            del self._nodes[nodeid]

    def move(self, nodeid, new_basename, parentid):
        """move nodeid to a new parent"""
        node = self._nodes.get(nodeid, None)
        parent = self._nodes.get(parentid, None)

        if node is not None:
            if node.parent and node.parent is not self._root_parent:
                node.parent.children.remove(node)

            node.parent = parent
            node.basename = new_basename

            if parent and parent is not self._root_parent:
                # update cache
                parent.children.add(node)


#=============================================================================
# Main NoteBook Connection

class BaseNoteBookConnectionFS (NoteBookConnection):
    """
    NoteBook connection that stores data on the filesystem.

    This base class enforces no attr schema.
    """
    def __init__(self):
        NoteBookConnection.__init__(self)

        self._filename = None
        self._index = None
        self._path_cache = PathCache()
        self._rootid = None
        self._filefs = FileFS(self._get_node_path)

        self._index_file = None

        # attributes to not write to disk, they can be derived
        self._attr_suppress = set(["parentids", "childrenids"])
        self._attr_mask = maskdict.MaskDict({}, self._attr_suppress)

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
            path_list = self._index.get_node_filepath(nodeid)
            if path_list is not None:
                path = os.path.join(self._filename, * path_list)
        if path is None:
            raise UnknownNode(nodeid)

        return path

    def _get_node_mtime(self, nodeid):
        """mtime (modification time) for nodeid"""
        return os.stat(self._get_node_path(nodeid)).st_mtime

    def _get_lostdir(self):
        return get_lostdir(self._filename)

    def _get_orphandir(self, nodeid=None):
        return get_orphandir(self._filename, nodeid)

    def _move_to_lostdir(self, filename):
        """Moves a file/dir to the lost_found directory"""
        lostdir = self._get_lostdir()
        if not os.path.exists(lostdir):
            os.makedirs(lostdir)

        new_filename = keepnote.notebook.get_unique_filename(
            lostdir, os.path.basename(filename),  sep=u"-")

        keepnote.log_message(u"moving data to lostdir '%s' => '%s'\n" %
                             (filename, new_filename))
        try:
            os.rename(filename, new_filename)
        except OSError, e:
            raise ConnectionError(u"unable to store lost file '%s'"
                                  % filename, e)

    #======================
    # Connection API

    def connect(self, url):
        """Make a new connection"""
        self._filename = url
        self.init_index()

    def close(self):
        """Close connection"""
        self._index.close()
        self._filename = None

    def save(self):
        """Save any unsynced state"""
        self._index.save()

    #======================
    # Node I/O API

    def create_node(self, nodeid, attr, _path=None):
        """Create a node"""
        if self._filename is None:
            raise ConnectionError("connect() has not been called")

        # check for creating root
        if self._rootid is None:
            parentids = attr.get("parentids", [])
            if parentids != []:
                raise ConnectionError("root node must have parentids = []")
            _path = self._filename
            is_root = True
        else:
            is_root = False

        # check for existing nodeid
        if self.has_node(nodeid):
            raise NodeExists(nodeid)

        # generate a new nodeid if one is not given
        if nodeid is None:
            nodeid = keepnote.notebook.new_nodeid()

        # TODO: handle case where parent does not currently exist
        # TODO: handle case where parent finally shows up and
        # reunites with its children in the orphans dir

        # Determine parentid.
        # TODO: support multiple parents.
        parentids = attr.get("parentids")
        parentid = parentids[0] if parentids else None

        # Determine path.
        if _path:
            path = _path
        elif parentid:
            # Make path using parent and title.
            parent_path = self._get_node_path(parentid)
            title = attr.get("title", _("New Page"))
            path = get_valid_unique_filename(parent_path, title)
        else:
            # Use an orphandir since no parent exists.
            path = self._get_orphandir(nodeid)

        # Clean attributes.
        self._clean_attr(nodeid, attr)

        # Make directory and write attr
        try:
            attr_file = self._get_node_attr_file(nodeid, path)
            os.makedirs(path)
            self._write_attr(attr_file, nodeid, attr)

        except OSError, e:
            raise ConnectionError(_("Cannot create node"), e)

        # Finish initializing root.
        if is_root:
            self._rootid = nodeid
            self._init_root()

        # Update cache and index.
        basename = os.path.basename(path) if parentid else path
        self._path_cache.add(nodeid, basename, parentid)
        self._index.add_node(nodeid, parentid, basename, attr,
                             mtime=get_path_mtime(path))

        return nodeid

    def _clean_attr(self, nodeid, attr):
        """
        Ensure attributes follow the notebook schema.
        """
        return True

    def _init_root(self):
        """Initialize root node"""

        # make index
        fn = os.path.dirname(self._get_index_file())
        if not os.path.exists(fn):
            os.makedirs(fn)
        if self._index is None:
            self.init_index()

        # make lost and found
        lostdir = self._get_lostdir()
        if not os.path.exists(lostdir):
            os.makedirs(lostdir)

        # make orhpan dir
        orphandir = self._get_orphandir()
        if not os.path.exists(orphandir):
            os.makedirs(orphandir)

    def _read_root(self):
        """Read root node attr"""
        if self._filename is None:
            raise ConnectionError("connect() has not been called")

        attr = self._read_node(None, self._filename)
        self._rootid = attr["nodeid"]
        self._init_root()
        return attr

    def read_node(self, nodeid, _force_index=False):
        """Read a node attr"""
        path = self._get_node_path(nodeid)
        parentid = self._get_parentid(nodeid)
        return self._read_node(parentid, path, _force_index=_force_index)

    def has_node(self, nodeid):
        """Returns True if node exists"""
        return (self._path_cache.has_node(nodeid) or
                (self._index and self._index.has_node(nodeid)))

    def update_node(self, nodeid, attr):
        """Write node attr"""

        # TODO: support mutltiple parents

        # Clean attributes.
        self._clean_attr(nodeid, attr)

        # write attrs
        path = self._get_node_path(nodeid)
        self._write_attr(get_node_meta_file(path), nodeid, attr)

        # Determine possible path changes due to node moves or title renaming.

        # Get old parentid.
        parentid = self._get_parentid(nodeid)

        # Get new parentid
        if nodeid == self.get_rootid():
            parentid2 = None
        else:
            parentids2 = attr.get("parentids")
            parentid2 = parentids2[0] if parentids2 else None

        # Get old title.
        title_index = self._index.get_attr(nodeid, "title")

        if parentid != parentid2:
            # Move to a new parent.
            self._rename_node_dir(nodeid, attr, parentid, parentid2, path)
        elif (parentid and title_index and
              title_index != attr.get("title", u"")):
            # Rename node directory, but
            # do not rename root node dir (parentid is None).
            self._rename_node_dir(nodeid, attr, parentid, parentid2, path)
        else:
            # Update index.
            basename = os.path.basename(path)
            self._index.add_node(nodeid, parentid2, basename, attr,
                                 mtime=get_path_mtime(path))

    def _rename_node_dir(self, nodeid, attr, parentid, new_parentid, path):
        """Renames a node directory to resemble attr['title']"""

        if new_parentid is not None:
            # try to pick a path that closely resembles the title
            title = attr.get("title", _("New Page"))
            new_parent_path = self._get_node_path(new_parentid)
            new_path = get_valid_unique_filename(new_parent_path, title)
            basename = os.path.basename(new_path)
        else:
            # make orphan
            new_path = self._get_orphandir(nodeid)
            basename = new_path

        try:
            os.rename(path, new_path)
        except Exception, e:
            raise ConnectionError(
                _(u"Cannot rename '%s' to '%s'" % (path, new_path)), e)

        # update index
        self._path_cache.move(nodeid, basename, new_parentid)
        self._index.add_node(nodeid, new_parentid, basename, attr,
                             mtime=get_path_mtime(new_path))

        # update parent too
        if parentid:
            self._index.set_node_mtime(
                parentid, get_path_mtime(os.path.dirname(path)))
        if new_parentid and new_parentid != parentid:
            self._index.set_node_mtime(
                new_parentid, get_path_mtime(new_parent_path))

    def delete_node(self, nodeid):
        """Delete node"""

        # TODO: will need code that orphans any children of nodeid
        path = self._get_node_path(nodeid)
        if not os.path.exists(path):
            raise UnknownNode()

        try:
            shutil.rmtree(path)
        except Exception, e:
            raise ConnectionError(
                _(u"Do not have permission to delete"), e)

        # TODO: remove from index entire subtree

        self._path_cache.remove(nodeid)
        self._index.remove_node(nodeid)

    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        if self._rootid:
            return self._rootid
        else:
            return self._read_root()["nodeid"]

    def _get_parentid(self, nodeid):
        """Returns nodeid of parent of node"""
        parentid = self._path_cache.get_parentid(nodeid)
        if parentid is None:
            node = self._index.get_node(nodeid)
            if node and node["parentid"] != keepnote.notebook.UNIVERSAL_ROOT:
                return node["parentid"]
        return parentid

    def _list_children_attr(self, nodeid, _path=None, _full=True):
        """List attr of children nodes of nodeid"""
        path = self._path_cache.get_path(nodeid) if _path is None else _path
        assert path is not None

        try:
            files = os.listdir(path)
        except Exception, e:
            raise ConnectionError(
                _(u"Do not have permission to read folder contents: %s")
                % path, e)

        for filename in files:
            path2 = os.path.join(path, filename)
            if os.path.exists(get_node_meta_file(path2)):
                try:
                    yield self._read_node(nodeid, path2, _full=_full)
                except ConnectionError, e:
                    keepnote.log_error(u"error reading %s" % path2)
                    continue
                    # TODO: raise warning, not all children read

        self._path_cache.set_children_complete(nodeid, True)

    def _list_children_nodeids(self, nodeid, _path=None, _index=True):
        """List nodeids of children of node"""

        # try to use cache first
        children = self._path_cache.get_children(nodeid)
        if children is not None:
            return children

        #path = self._get_node_path(nodeid)
        #
        # Disabled for now.  Don't rely on index for listing children
        # if node is unchanged on disk (same mtime),
        # use index to detect children
        # however we also require a fully updated index (not index_needed)
        #if _index and self._index and not self._index.index_needed():
        #    mtime = get_path_mtime(path)
        #    index_mtime = self._index.get_node_mtime(nodeid)
        #    if mtime <= index_mtime:
        #        children = []
        #        for row in self._index.list_children(nodeid):
        #            self._path_cache.add(row[0], row[1], nodeid)
        #            children.append(row[0])
        #        return children

        # fallback to reading attrs of children
        return (attr["nodeid"]
                for attr in self._list_children_attr(
                    nodeid, _path, _full=False))

    def _read_attr(self, metafile):
        return read_attr(metafile, set_extra=False)

    def _read_node(self, parentid, path, _full=True, _force_index=False):
        """
        Reads a node from disk.

        _full -- If True, populate all children ids from filesystem.
        _force_index -- Index node regardless of mtime.
        """
        metafile = get_node_meta_file(path)
        attr, extra = self._read_attr(metafile)
        nodeid = extra['nodeid']

        # Clean attr and rewrite them if needed.
        if not self._clean_attr(nodeid, attr):
            self._write_attr(metafile, nodeid, attr)

        # update path cache
        basename = os.path.basename(path) if parentid else path
        self._path_cache.add(nodeid, basename, parentid)

        # check indexing
        if _force_index:
            # reindex this node
            self._index.add_node(
                nodeid, parentid, basename, attr, get_path_mtime(path))
        else:
            # if node has changed on disk (newer mtime), then re-index it
            current, mtime = self._node_index_current(nodeid, path)
            if not current:
                self._reindex_node(nodeid, parentid, path, attr, mtime)

        # Supplement parent and child ids
        # TODO: when cloning is implemented, use filesystem to only supplement
        # not replace ids
        if parentid and 'parentids' in attr:
            attr['parentids'] = [parentid]
        if _full and 'childrenids' in attr:
            attr["childrenids"] = list(
                self._list_children_nodeids(nodeid, path))

        return attr

    def _node_index_current(self, nodeid, path, mtime=None):
        if mtime is None:
            mtime = get_path_mtime(path)
        index_mtime = self._index.get_node_mtime(nodeid)
        return mtime <= index_mtime, mtime

    def _reindex_node(self, nodeid, parentid, path, attr, mtime, warn=True):
        """Reindex a node that has been tampered"""
        if warn:
            keepnote.log_message(
                u"Unmanaged change detected. Reindexing '%s'\n" % path)

        # TODO: to prevent a full recurse I could index children but
        # use 0 for mtime, so that they will still trigger an index for them
        # selves
        # reindex all children in case their parentid's changed
        #for path2 in iter_child_node_paths(path):
        #    attr2 = self._read_node(nodeid, path2, _full=False,
        #                            _force_index=True)
            #self._index.add_node(
            #    attr2["nodeid"], nodeid,
            #    os.path.basename(path2), attr2,
            #    get_path_mtime(path2))

        # reindex this node
        self._index.add_node(
            nodeid, parentid, os.path.basename(path), attr, mtime)

    def _get_node_attr_file(self, nodeid, path=None):
        """Returns the meta file for the node"""
        return self.get_file(nodeid, NODE_META_FILE, path)

    def _write_attr(self, filename, nodeid, attr):
        """Write a node meta data file"""
        self._attr_mask.set_dict(attr)

        try:
            write_attr(filename, nodeid, self._attr_mask)
        except Exception, e:
            raise
            raise ConnectionError(
                _("Cannot write meta data" + " " + filename + ":" + str(e)), e)

    #===============
    # file API

    def open_file(self, nodeid, filename, mode="r", codec=None, _path=None):
        """Open a node file."""
        path = self._filefs.get_node_path(nodeid)
        stream = self._filefs.open_file(
            nodeid, filename, mode=mode, codec=codec, _path=_path)

        # TODO: this should check and update the mtime
        # but only update if it was previously consistent (before the open)
        # update mtime since file creation causes directory mtime to change
        if self._index:
            self._index.set_node_mtime(nodeid, os.stat(path).st_mtime)

        return stream

    def delete_file(self, nodeid, filename, _path=None):
        """Delete a node file."""
        self._filefs.delete_file(
            nodeid, filename, _path=_path)

    def list_dir(self, nodeid, filename="/", _path=None):
        """
        List data files in node.

        Directories have a '/' at the end of their name.
        """
        return self._filefs.list_dir(nodeid, filename, _path=_path)

    def create_dir(self, nodeid, filename, _path=None):
        """Create directory within node."""
        return self._filefs.create_dir(nodeid, filename, _path=_path)

    def has_file(self, nodeid, filename, _path=None):
        """Return True is file exists."""
        return self._filefs.has_file(nodeid, filename, _path=_path)

    def move_file(self, nodeid1, filename1, nodeid2, filename2,
                  _path1=None, _path2=None):
        """Rename a node file."""
        return self._filefs.move_file(nodeid1, filename1, nodeid2, filename2,
                                      _path1=_path1, _path2=_path2)

    def copy_file(self, nodeid1, filename1, nodeid2, filename2,
                  _path1=None, _path2=None):
        """
        Copy a file between two nodes.

        If nodeid is None, filename is assumed to be a local file.
        """
        self._filefs.copy_file(nodeid1, filename1, nodeid2, filename2,
                               _path1=_path1, _path2=_path2)

    #---------------------------------
    # index management

    def init_index(self):
        """Initialize the index"""

        fn = self._get_index_file()
        if os.path.exists(os.path.dirname(fn)):
            self._index = notebook_index.NoteBookIndex(self, fn)

    def index_needed(self):
        return self._index.index_needed()

    def clear_index(self):
        return self._index.clear()

    def index_all(self):

        # clear memory cache too
        self._path_cache.clear()
        self._path_cache.add(self.get_rootid(), self._filename, None)

        # TODO: index orphans
        # may need private method to iterate orphans

        for node in self._index.index_all():
            yield node

    def _get_index_file(self):

        if self._index_file is not None:
            return self._index_file
        else:
            return os.path.join(
                self._filename, NOTEBOOK_META_DIR, notebook_index.INDEX_FILE)

    # TODO: temp solution. remove soon
    def _set_index_file(self, index_file):
        self._index_file = index_file

    #---------------------------------
    # indexing/querying

    def index(self, query):

        if query[0] == "has_fulltext":
            return self._index.has_fulltext_search()

        elif query[0] == "enable_fulltext":
            return self._index.enable_fulltext_search(query[1])

        elif query[0] == "compact":
            return self._index.compact()

        else:
            return NoteBookConnection.index(self, query)

    def index_attr(self, key, datatype, index_value=False):

        if isinstance(datatype, basestring):
            index_type = datatype
        elif issubclass(datatype, basestring):
            index_type = "TEXT"
        elif issubclass(datatype, int):
            index_type = "INTEGER"
        elif issubclass(datatype, float):
            index_type = "FLOAT"
        else:
            raise Exception("unknown attr datatype '%s'" % repr(datatype))

        self._index.add_attr(AttrIndex(key, index_type,
                                       index_value=index_value))

    def search_node_titles(self, text):
        """Search nodes by title"""
        return self._index.search_titles(text)

    def search_node_contents(self, text):
        """Search nodes by content"""
        return self._index.search_contents(text)

    def has_fulltext_search(self):
        return self._index.has_fulltext_search()

    def enable_fulltext_search(self, enabled):
        return self._index.enable_fulltext_search(enabled)

    def get_node_path_by_id(self, nodeid):
        """Lookup node by nodeid"""
        return self._index.get_node_path(nodeid)

    def get_attr_by_id(self, nodeid, key):
        return self._index.get_attr(nodeid, key)


class NoteBookConnectionFS (BaseNoteBookConnectionFS):
    """
    NoteBook connection that stores data on the filesystem.

    This connection enforces a schema where the following attr fields
    are always present:
      - nodeid
      - version
      - parentids
      - childrenids
    """
    def _read_attr(self, metafile):
        return read_attr(metafile, set_extra=True)

    def _clean_attr(self, nodeid, attr):
        """
        Ensure attributes follow the notebook schema.
        """
        was_clean = True
        masked = set(['childrenids', 'parentids'])
        current_time = get_timestamp()

        # Set default attrs if needed.
        defaults = {
            'nodeid': nodeid,
            'version': keepnote.notebook.NOTEBOOK_FORMAT_VERSION,
            'parentids': [],
            'childrenids': [],
            'created_time': current_time,
            'modified_time': current_time,
        }
        for key, value in defaults.items():
            if key not in attr:
                attr[key] = value
                if key not in masked:
                    was_clean = False

        # Issue new nodeid if one is not present.
        if not attr['nodeid']:
            attr['nodeid'] = keepnote.notebook.new_nodeid()
            was_clean = False

        return was_clean
