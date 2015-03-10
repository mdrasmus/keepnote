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

# python imports
import logging
import os
import shutil
import re
import uuid

# keepnote imports
from keepnote import sqlitedict
from keepnote import trans
from keepnote.notebook.connection import NodeExists
from keepnote.notebook.connection import NoteBookConnection
from keepnote.notebook.connection import UnknownNode
from keepnote.notebook.connection.fs import FileFS
from keepnote.notebook.connection.fs import read_attr
from keepnote.notebook.connection.fs import write_attr

_ = trans.translate


logging.getLogger('sqlitedict').setLevel(level=logging.WARNING)


# constants
XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""

NODE_META_FILE = u"node.xml"
NOTEBOOK_META_DIR = u"__NOTEBOOK__"
NODEDIR = u"nodes"
MAX_LEN_NODE_FILENAME = 40
NULL = object()


class NodeFSSimple(object):
    """
    Stores node directories in a directory structure organized by nodeid.

    This provides one of the simplest schemes for assign nodes to directories.
    Consequently, several restrictions apply to what kind of nodeids can be
    stored.

    In this store, nodeid have the following restrictions:
    - nodeids length must be within [3, 255] inclusive.
    - nodeids must contain characters valid for filesystems:
        a-z 0-9 _ - . , <double quote> <single quote> <space>
      Uppercase is not allowed because some filesystems ignore case.
    - nodeids cannot be '??..' or '??.'
    """

    VALID_REGEX = re.compile(r'^[a-z0-9_\-., "\']+$')

    def __init__(self, rootpath):
        self._rootpath = unicode(rootpath)
        self._fansize = 2

    def _is_valid(self, nodeid):
        """Return True if nodeid requires storing in others directory."""
        return not (
            # Contains invalid characters
            not re.match(self.VALID_REGEX, nodeid) or

            # Less than or equal to fansize
            len(nodeid) <= self._fansize or

            # Greater than fansize and ends with dots
            (len(nodeid) == self._fansize + 1 and nodeid.endswith('.')) or

            (len(nodeid) == self._fansize + 2 and nodeid.endswith('..')))

    def get_nodedir(self, nodeid):
        """Return directory of nodeid."""
        if nodeid is None:
            return self._rootpath

        if len(nodeid) <= self._fansize or len(nodeid) > 255:
            raise Exception('Nodeid has invalid length: "%s"' % nodeid)

        if not self._is_valid(nodeid):
            raise Exception('Nodeid is not simple: "%s"' % nodeid)

        return os.path.join(self._rootpath, self._othersdir, nodeid)

    def create_nodedir(self, nodeid, force=False):
        """Create directory of nodeid."""
        nodedir = self.get_nodedir(nodeid)
        if not os.path.exists(nodedir):
            os.makedirs(nodedir)
        else:
            raise NodeExists()
        return nodedir

    def delete_nodedir(self, nodeid, force=False):
        """Delete directory of nodeid."""
        nodedir = self.get_nodedir(nodeid)
        if os.path.exists(nodedir):
            shutil.rmtree(nodedir)
        else:
            raise UnknownNode()

    def has_nodedir(self, nodeid):
        """Returns True if nodeid exists."""
        nodedir = self.get_nodedir(nodeid)
        return os.path.exists(nodedir)

    def close(self):
        """Cease any more interaction with the filesystem."""
        pass

    def iter_nodeids(self):
        """Iterates through all stored nodeids."""
        # List nodeid in general pool.
        for filename in os.listdir(self._rootpath):
            if len(filename) == self._fansize:
                # This is a nodeid prefix.
                path = os.path.join(self._rootpath, filename)
                prefix = filename
                for filename in os.listdir(path):
                    yield prefix + filename


class NodeFSStandard(NodeFSSimple):
    """
    Stores node directories in a directory structure organized by nodeid.

    Builds off of NodeFSSimple to provide a greater range of nodeids.

    In this store, nodeid have the following restrictions:
    - nodeids length must be within [1, 255] inclusive.
    - nodeids must contain characters valid for filesystems:
        a-z 0-9 _ - . , <double quote> <single quote> <space>
      Uppercase is not allowed because some filesystems ignore case.
    - nodeids cannot be '.' or '..'
    """

    BANNED_NODEIDS = ['.', '..']

    def __init__(self, rootpath, others='00_extra'):
        super(NodeFSStandard, self).__init__(rootpath)
        self._othersdir = others
        assert(len(self._othersdir) > self._fansize)

    def _is_other(self, nodeid):
        """Return True if nodeid requires storing in others directory."""

        return (
            # Less than or equal to fansize
            len(nodeid) <= self._fansize or

            # Greater than fansize and ends with dots
            (len(nodeid) == self._fansize + 1 and nodeid.endswith('.')) or

            (len(nodeid) == self._fansize + 2 and nodeid.endswith('..')))

    def get_nodedir(self, nodeid):
        """Return directory of nodeid."""
        if nodeid is None:
            return self._rootpath

        if len(nodeid) < 1 or len(nodeid) > 255:
            raise Exception('Nodeid has invalid length: "%s"' % nodeid)

        if nodeid in self.BANNED_NODEIDS:
            raise Exception('Nodeid is banned: "%s"' % nodeid)

        # Contains invalid characters
        if not re.match(self.VALID_REGEX, nodeid):
            raise Exception(
                'Nodeid contains invalid characters: "%s"' % nodeid)

        if not self._is_other(nodeid):
            return os.path.join(self._rootpath,
                                nodeid[:self._fansize],
                                nodeid[self._fansize:])
        else:
            # Shorter nodeids go directly in the otherdir.
            return os.path.join(self._rootpath, self._othersdir, nodeid)

    def iter_nodeids(self):
        """Iterates through all stored nodeids."""
        for nodeid in super(NodeFSStandard, self).iter_nodeids():
            yield nodeid

        # List other nodeids.
        otherspath = os.path.join(self._rootpath, self._othersdir)
        if os.path.exists(otherspath):
            for filename in os.listdir(otherspath):
                yield filename


class NodeFS(NodeFSStandard):
    """
    Stores node directories in a directory structure organized by nodeid.

    Builds off of NodeFSStandard to support any non-empty nodeid.
    """

    BANNED_NODEIDS = ['.', '..']

    def __init__(self, rootpath, others='00_extra',
                 index='00_index.db', tablename='nodes',
                 alt_tablename='alt_nodes'):
        super(NodeFS, self).__init__(rootpath, others=others)
        self._indexfile = os.path.join(self._rootpath, index)
        self._index = sqlitedict.open(self._indexfile, tablename,
                                      flag='c', autocommit=True)
        self._index_alt = sqlitedict.open(self._indexfile, alt_tablename,
                                          flag='c')

    def _is_nonstandard(self, nodeid):
        """Return True if nodeid requires special indexing."""
        return(
            # Long nodeids.
            len(nodeid) > 255 or

            # BANNED nodeids.
            nodeid in self.BANNED_NODEIDS or

            # Contains invalid characters.
            not re.match(self.VALID_REGEX, nodeid))

    def _get_alt_nodeid(self, nodeid):
        # Determine alternate nodeid for this nonstandard nodeid.
        alt_nodeid = self._index.get(nodeid, None)
        if not alt_nodeid:
            alt_nodeid = unicode(uuid.uuid4())
            self._index[nodeid] = alt_nodeid
            self._index_alt[alt_nodeid] = nodeid
            self._index.commit()
            self._index_alt.commit()
        return alt_nodeid

    def get_nodedir(self, nodeid):
        """Return directory of nodeid."""
        if nodeid is None:
            return self._rootpath

        if nodeid == "":
            raise Exception('Nodeid cannot not be zero-length.')

        if self._is_nonstandard(nodeid):
            # Use alt_nodeid to lookup in general node pool.
            alt_nodeid = self._get_alt_nodeid(nodeid)
            return os.path.join(self._rootpath,
                                alt_nodeid[:self._fansize],
                                alt_nodeid[self._fansize:])

        elif self._is_other(nodeid):
            # Shorter nodeids go directly in the otherdir.
            return os.path.join(self._rootpath, self._othersdir, nodeid)
        else:
            # Simple nodeids.
            return os.path.join(self._rootpath,
                                nodeid[:self._fansize],
                                nodeid[self._fansize:])

    def delete_nodedir(self, nodeid):
        """Delete directory of nodeid."""
        super(NodeFS, self).delete_nodedir(nodeid)

        # non-standard ids need to be removed from the index.
        if self._is_nonstandard(nodeid):
            alt_nodeid = self._index[nodeid]
            del self._index[nodeid]
            del self._index_alt[alt_nodeid]
            self._index.commit()
            self._index_alt.commit()

    def close(self):
        """Cease any more interaction with the filesystem."""
        super(NodeFS, self).close()

        # Close indexes, wait on thread cleanup.
        conn1 = self._index.conn
        conn2 = self._index_alt.conn
        self._index.close()
        self._index_alt.close()
        conn1.join()
        conn2.join()

    def iter_nodeids(self):
        """Iterates through all stored nodeids."""
        for nodeid in super(NodeFS, self).iter_nodeids():
            # Do not yield alternate nodeids.
            if nodeid not in self._index_alt:
                yield nodeid

        # Iterate through nonstandard nodeids.
        for nodeid in self._index:
            yield nodeid


class NoteBookConnectionFSRaw (NoteBookConnection):
    """
    Provides a NoteBookConnection using NodeFS as a backing.
    """

    def __init__(self):
        self._rootid = None

        self._rootpath = None
        self._nodefs = None
        self._filefs = FileFS(self._get_node_path)

    def _create_rootdir(self, url):
        os.makedirs(url)

    def _get_node_path(self, nodeid):
        return self._nodefs.get_nodedir(nodeid)

    def _get_node_attr_file(self, nodepath):
        return os.path.join(nodepath, NODE_META_FILE)

    #======================
    # connection API

    def connect(self, url):
        """Make a new connection."""
        self._rootpath = url
        if not os.path.exists(url):
            self._create_rootdir(url)
        self._nodefs = NodeFS(self._rootpath)

    def close(self):
        """Close connection."""
        self._nodefs.close()

    def save(self):
        """Save any unsynced state."""
        pass

    #======================
    # Node I/O API

    def create_node(self, nodeid, attr):
        """Create a node."""
        # First node is root.
        if self._rootid is None:
            self._rootid = nodeid
        nodepath = self._nodefs.create_nodedir(nodeid)
        attr_file = self._get_node_attr_file(nodepath)
        write_attr(attr_file, nodeid, attr)

    def read_node(self, nodeid):
        """Read a node attr."""
        nodepath = self._nodefs.get_nodedir(nodeid)
        if not os.path.exists(nodepath):
            raise UnknownNode()
        attr_file = self._get_node_attr_file(nodepath)
        attrs, extra = read_attr(attr_file, set_extra=False)
        return attrs

    def update_node(self, nodeid, attr):
        """Write node attr."""
        nodepath = self._nodefs.get_nodedir(nodeid)
        if not os.path.exists(nodepath):
            raise UnknownNode()
        attr_file = self._get_node_attr_file(nodepath)
        write_attr(attr_file, nodeid, attr)

    def delete_node(self, nodeid):
        """Delete node."""
        self._nodefs.delete_nodedir(nodeid)

    def has_node(self, nodeid):
        """Returns True if node exists."""
        return self._nodefs.has_nodedir(nodeid)

    def get_rootid(self):
        """Returns nodeid of notebook root node."""
        return self._rootid

    #===============
    # file API

    def open_file(self, nodeid, filename, mode="r", codec=None, _path=None):
        """Open a node file."""
        return self._filefs.open_file(
            nodeid, filename, mode=mode, codec=codec, _path=_path)

    def delete_file(self, nodeid, filename, _path=None):
        """Delete a node file."""
        return self._filefs.delete_file(nodeid, filename, _path)

    def create_dir(self, nodeid, filename, _path=None):
        """Create directory within node."""
        return self._filefs.create_dir(nodeid, filename, _path)

    def list_dir(self, nodeid, filename="/", _path=None):
        """List data files in node."""
        return self._filefs.list_dir(nodeid, filename, _path)

    def has_file(self, nodeid, filename, _path=None):
        """Return True if file exists."""
        return self._filefs.has_file(nodeid, filename, _path)

    #---------------------------------
    # indexing

    def index(self, query):

        # TODO: make this plugable
        # also plug-ability will ensure safer fall back to unhandeled queries

        # built-in queries
        # ["index_attr", key, (index_value)]
        # ["search", "title", text]
        # ["search_fulltext", text]
        # ["has_fulltext"]
        # ["node_path", nodeid]
        # ["get_attr", nodeid, key]

        if query[0] == "index_attr":
            return

        elif query[0] == "search":
            assert query[1] == "title"

            return [
                (nodeid, node["title"])
                for nodeid, node in (
                    (nodeid, self.read_node(nodeid))
                    for nodeid in self._nodefs.iter_nodeids())
                if query[2] in node.get("title", "")]

        elif query[0] == "search_fulltext":
            # TODO: could implement brute-force backup
            return []

        elif query[0] == "has_fulltext":
            return False

        elif query[0] == "node_path":
            nodeid = query[1]
            path = []
            node = self.read_node(nodeid)
            while node:
                path.append(node["nodeid"])
                parentids = node.get("parentids")
                if parentids:
                    node = self.read_node(parentids[0])
                else:
                    break
            path.reverse()
            return path

        elif query[0] == "get_attr":
            return self.read_node(query[1])[query[2]]

        # FS-specific
        elif query[0] == "init":
            return

        elif query[0] == "index_needed":
            return False

        elif query[0] == "clear":
            return

        elif query[0] == "index_all":
            return
