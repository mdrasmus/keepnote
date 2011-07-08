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


#=============================================================================
# errors


class ConnectionError (StandardError):
    def __init__(self, msg, error=None):
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

class UnknownFile (ConnectionError):
    def __init__(self, msg="unknown file"):
        ConnectionError.__init__(self, msg)

class CorruptIndex (ConnectionError):
    def __init__(self, msg="index error", error=None):
        ConnectionError.__init__(self, msg, error)


class Unimplemented (ConnectionError):
    def __init__(self, msg="unimplemented"):
        ConnectionError.__init__(self, msg)
    

#=============================================================================


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
        pass
            
    def read_node(self, nodeid):
        """Read a node attr"""
        pass

    def update_node(self, nodeid, attr):
        """Write node attr"""
        pass

    def delete_node(self, nodeid):
        """Delete node"""
        pass

    def has_node(self, nodeid):
        """Returns True if node exists"""
        return False

    # TODO: can this be simplified with a search query?
    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        pass
    

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
        pass


    def delete_file(self, nodeid, filename):
        """Delete a file contained within a node"""
        pass

    def create_dir(self, nodeid, filename):
        """Create directory within node"""
        pass

    def list_files(self, nodeid, filename="/"):
        """
        List data files in node
        """
        pass
    
    def file_exists(self, nodeid, filename):
        pass

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

        if fullname1.endswith("/"):
            # copy directory tree
            self.create_dir(nodeid2, filename2)

            for filename in self.list_files(nodeid1):
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


    # Is this needed inside the connection?  Can it be support outside?
    #def new_filename(self, nodeid, new_filename, ext=u"", sep=u" ", number=2, 
    #                 return_number=False, use_number=False, ensure_valid=True):
    #    pass


    #---------------------------------
    # index management

    def init_index(self):
        """Initialize the index"""
        pass
    
    def index_needed(self):
        pass

    def clear_index(self):
        pass

    def index_all(self):
        pass


    #---------------------------------
    # indexing/querying

    def index_attr(self, key, index_value=False):
        """Add indexing for an attribute"""
        pass

    def search_node_titles(self, text):
        """Search nodes by title"""
        pass

    def search_node_contents(self, text):
        """Search nodes by content"""
        pass

    def has_fulltext_search(self):
        pass

    def update_index_node(self, nodeid, attr):
        """Update a node in the index"""
        pass
    
    def get_node_path_by_id(self, nodeid):
        """Lookup node path by nodeid"""
        pass

    def get_attr_by_id(self, nodeid, key):
        pass




    #================================
    # Filesystem-specific API (may not be supported by some connections)
    
    def get_node_path(self, nodeid):
        """Returns the path of the node"""
        pass
    
    def get_node_basename(self, nodeid):
        """Returns the basename of the node"""
        pass

    # TODO: returning a fullpath to a file is not fully portable
    # will eventually need some kind of fetching mechanism    
    def get_file(self, nodeid, filename, _path=None):
        pass


