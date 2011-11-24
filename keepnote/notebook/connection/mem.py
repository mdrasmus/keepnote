"""

    KeepNote    
    
    Low-level Create-Read-Update-Delete (CRUD) interface for notebooks.

    This module provides a pure-memory implementation of the notebook

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

import urlparse
from StringIO import StringIO

# keepnote imports
import keepnote
from keepnote import notebook
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import NoteBookConnection


#=============================================================================

class Node (object):
    def __init__(self, attr={}):
        self.attr = dict(attr)
        self.files = {}

class File (StringIO):
    def close(self):
        self.closed = True

    def reopen(self):
        self.closed = False
        self.seek(0)


class NoteBookConnectionMem (NoteBookConnection):
    def __init__(self):
        self._nodes = {}
        self._rootid = None

    #======================
    # connection API

    def connect(self, url):
        """Make a new connection"""
        pass
        
    def close(self):
        """Close connection"""
        pass

    def save(self):
        """Save any unsynced state"""
        pass

    #======================
    # Node I/O API
    
    def create_node(self, nodeid, attr):
        """Create a node"""
        if nodeid in self._nodes:
            raise connlib.NodeExists()
        if self._rootid is None:
            self._rootid = nodeid
        self._nodes[nodeid] = Node(attr)
        
            
    def read_node(self, nodeid):
        """Read a node attr"""
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        return node.attr

    def update_node(self, nodeid, attr):
        """Write node attr"""
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        node.attr = dict(attr)

    def delete_node(self, nodeid):
        """Delete node"""
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        del self._nodes[nodeid]

    def has_node(self, nodeid):
        """Returns True if node exists"""
        return nodeid in self._nodes


    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        return self._rootid
    

    #===============
    # file API

    def open_file(self, nodeid, filename, mode="r", codec=None):
        """
        Open a file contained within a node

        nodeid   -- node to open a file from
        filename -- filename of file to open
        mode     -- can be "r" (read), "w" (write), "a" (append)
        codec    -- read or write with an encoding (default: None)
        """
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        if filename.endswith("/"):
            raise connlib.FileError()
        stream = node.files.get(filename)
        if stream is None:
            stream = node.files[filename] = File()
        else:
            stream.reopen()
        return stream


    def delete_file(self, nodeid, filename):
        """Delete a file contained within a node"""
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        try:
            del node.files[filename]
        except:
            raise connlib.UnknownFile()

    def create_dir(self, nodeid, filename):
        """Create directory within node"""
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        if not filename.endswith("/"):
            raise connlib.FileError()
        node.files[filename] = None        

    def list_dir(self, nodeid, filename="/"):
        """
        List data files in node
        """
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        if not filename.endswith("/"):
            raise connlib.FileError()
        files = [f for f in node.files.iterkeys()
                 if f.startswith(filename) and f != filename]
                
    def has_file(self, nodeid, filename):
        node = self._nodes.get(nodeid)
        if node is None:
            raise connlib.UnknownNode()
        return filename in node.files


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
            return [(nodeid, node.attr["title"])
                    for nodeid, node in self._nodes.iteritems()
                        if query[2] in node.attr.get("title", "")]

        elif query[0] == "search_fulltext":
            # TODO: could implement brute-force backup
            return []

        elif query[0] == "has_fulltext":
            return False

        elif query[0] == "node_path":
            nodeid = query[1]
            path = []
            node = self._nodes.get(nodeid)
            while node:
                path.append(node.attr["nodeid"])
                parentids = node.attr.get("parentids")
                if parentids:
                    node = self._nodes.get(parentids[0])
                else:
                    break
            path.reverse()
            return path

        elif query[0] == "get_attr":
            return self._nodes[query[1]][query[2]]

        # FS-specific
        elif query[0] == "init":
            return 

        elif query[0] == "index_needed":
            return False

        elif query[0] == "clear":
            return

        elif query[0] == "index_all":
            return
