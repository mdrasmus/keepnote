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

import urlparse


#=============================================================================
# errors


class ConnectionError (StandardError):
    def __init__(self, msg="", error=None):
        StandardError.__init__(self, msg)
        self.error = error

    def repr(self):
        if self.error is not None:
            return StandardError.repr(self) + ": " + repr(self.error)
        else:
            return StandardError.repr(self)

class UnknownNode (ConnectionError):
    def __init__(self, msg="unknown node"):
        ConnectionError.__init__(self, msg)

class NodeExists (ConnectionError):
    def __init__(self, msg="node exists"):
        ConnectionError.__init__(self, msg)

class FileError (ConnectionError):
    def __init__(self, msg="file error", error=None):
        ConnectionError.__init__(self, msg, error)

class UnknownFile (FileError):
    def __init__(self, msg="unknown file"):
        FileError.__init__(self, msg)

class CorruptIndex (ConnectionError):
    def __init__(self, msg="index error", error=None):
        ConnectionError.__init__(self, msg, error)

    

#=============================================================================
# file path functions

def path_join(*parts):
    """
    Join path parts for node file paths

    Node files always use '/' for path separator.
    """
    # skip empty strings
    # trim training "slashes"
    return "/".join((part[:-1] if part[-1] == "/" else part) 
                    for part in parts if part != "")


def path_basename(filename):
    """
    Return the last component of a filename

    aaa/bbb   =>  bbb
    aaa/bbb/  =>  bbb
    aaa/      =>  aaa
    aaa       =>  aaa
    ''        =>  ''
    /         =>  ''
    """

    if filename.endswith("/"):
        i = filename.rfind("/", 0, -1) + 1
        return filename[i:-1]
    else:
        i = filename.rfind("/", 0, -1) + 1
        return filename[i:]



#=============================================================================

class NoteBookConnection (object):
    def __init__(self):
        pass

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
        # TODO: document root creation
        # proposal 1: if rootid is not set yet, then this node is root
        # proposal 2: if parentids is [], then this node is root
        # proposal 3: try to remove root concept from connection
        raise NotImplementedError("create_node")
            
    def read_node(self, nodeid):
        """Read a node attr"""
        raise NotImplementedError("read_node")

    def update_node(self, nodeid, attr):
        """Write node attr"""
        raise NotImplementedError("update_node")

    def delete_node(self, nodeid):
        """Delete node"""
        raise NotImplementedError("delete_node")

    def has_node(self, nodeid):
        """Returns True if node exists"""
        raise NotImplementedError("has_node")

    # TODO: can this be simplified with a search query?
    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        raise NotImplementedError("get_rootid")
    

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
        raise NotImplementedError("open_file")


    def delete_file(self, nodeid, filename):
        """Delete a file contained within a node"""
        raise NotImplementedError("delete_file")

    def create_dir(self, nodeid, filename):
        """Create directory within node"""
        raise NotImplementedError("create_dir")

    def list_dir(self, nodeid, filename="/"):
        """
        List data files in node
        """
        raise NotImplementedError("list_dir")
    
    def has_file(self, nodeid, filename):
        raise NotImplementedError("has_file")

    def move_file(self, nodeid, filename1, nodeid2, filename2):
        """
        Move or rename a node file
        
        'nodeid1' and 'nodeid2' cannot be None.
        """

        if nodeid is None or nodeid2 is None:
            raise UnknownFile("nodeid cannot be None")
        
        self.copy_file(nodeid, filename, nodeid, new_filename)
        self.delete_file(nodeid, filename)


    def copy_file(self, nodeid1, filename1, nodeid2, filename2):
        """
        Copy a file between two nodes

        'nodeid1' and 'nodeid2' can be the same nodeid.

        If 'nodeidX' is None, 'filenameX' is assumed to be a local file.

        If 'filename1' is a dir (ends with a "/") filename2 must be a dir
        and the copy is recursive for the contents of 'filename1'.

        """

        if filename1.endswith("/"):
            # copy directory tree
            self.create_dir(nodeid2, filename2)

            for filename in self.list_dir(nodeid1):
                self.copy_file(nodeid1, path_join(filename1, filename),
                               nodeid2, path_join(filename2, filename))

        else:
            # copy file
            
            if nodeid1 is not None:
                stream1 = self.open_file(nodeid1, filename1)
            else:
                # filename1 is local
                stream1 = open(filename1, "rb")

            if nodeid2 is not None:
                stream2 = self.open_file(nodeid2, filename2, "w")
            else:
                # filename 2 is local
                stream2 = open(filename2, "w")

            while True:
                data = stream1.read(1024*4)
                if len(data) == 0:
                    break
                stream2.write(data)

            stream1.close()
            stream2.close()


    #---------------------------------
    # indexing
    
    def index(self, query):

        # TODO: make this plugable

        # built-in queries
        # ["index_attr", key, (index_value)]
        # ["search", "title", text]
        # ["search_fulltext", text]
        # ["has_fulltext"]
        # ["node_path", nodeid]
        # ["get_attr", nodeid, key]

        if query[0] == "index_attr":
            index_value = query[3] if len(query) == 4 else False
            return self.index_attr(query[1], query[2], index_value)
            
        elif query[0] == "search":
            assert query[1] == "title"
            return self.search_node_titles(query[2])

        elif query[0] == "search_fulltext":
            return self.search_node_contents(query[1])

        elif query[0] == "has_fulltext":
            return False

        elif query[0] == "node_path":
            return self.get_node_path_by_id(query[1])

        elif query[0] == "get_attr":
            return self.get_attr_by_id(query[1], query[2])


        # FS-specific
        elif query[0] == "init":
            return self.init_index()

        elif query[0] == "index_needed":
            return self.index_needed()

        elif query[0] == "clear":
            return self.clear_index()

        elif query[0] == "index_all":
            return self.index_all()

    #---------------------------------
    # indexing/querying
    # TODO: perhaps deprecate this for generic index() calls

    def index_attr(self, key, datatype, index_value=False):
        """Add indexing for an attribute"""
        return self.index(["index_attr", key, datatype, index_value])

    def search_node_titles(self, text):
        """Search nodes by title"""
        return self.index(["search", "title", text])

    def search_node_contents(self, text):
        """Search nodes by content"""
        return self.index(["search_fulltext", text])
    
    def get_node_path_by_id(self, nodeid):
        """Lookup node path by nodeid"""
        return self.index(["node_path", nodeid])

    def get_attr_by_id(self, nodeid, key):
        return self.index(["get_attr", nodeid, key])



    #---------------------------------------
    # FS-specific index management
    # TODO: try to deprecate

    def init_index(self):
        """Initialize the index"""
        return self.index(["init"])
    
    def index_needed(self):
        return self.index(["index_needed"])

    def clear_index(self):
        return self.index(["clear_index"])

    def index_all(self):
        return self.index(["index_all"])



    #================================
    # Filesystem-specific API (may not be supported by some connections)
    
    def get_node_path(self, nodeid):
        """Returns the path of the node"""
        raise NotImplementedError("get_node_path")
    
    def get_node_basename(self, nodeid):
        """Returns the basename of the node"""
        raise NotImplementedError("get_node_basename")

    # TODO: returning a fullpath to a file is not fully portable
    # will eventually need some kind of fetching mechanism    
    def get_file(self, nodeid, filename, _path=None):
        raise NotImplementedError("get_file")



#=============================================================================
# Connection registration

class NoteBookConnections (object):

    def __init__(self):
        self._protos = {}

    def add(self, proto, connection_class):
        self._protos[proto] = connection_class

    def get(self, url):
        proto = self.get_proto(url)
        conn_class = self._protos.get(proto, None)
        if conn_class:
            return conn_class()
        else:
            # fallback to 'file' protocol
            return self._protos.get("file", None)

    def get_proto(self, url):
        if "://" not in url:
            proto = "file"
        else:
            parts = urlparse.urlsplit(url)
            proto = parts.scheme if parts.scheme else "file"
        return proto

    def lookup(self, proto):
        return self._protos.get(proto, None)


