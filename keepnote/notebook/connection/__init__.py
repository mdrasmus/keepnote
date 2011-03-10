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
    pass

class UnknownNode (ConnectionError):
    def __init__(self, msg="unknown node"):
        ConnectionError.__init__(self, msg)

class NodeExists (ConnectionError):
    def __init__(self, msg="node exists"):
        ConnectionError.__init__(self, msg)

class UnknownFile (ConnectionError):
    def __init__(self, msg="unknown file"):
        ConnectionError.__init__(self, msg)

#=============================================================================


def path_join(*parts):
    """
    Join path parts for node file paths

    Node files always use '/' for path separator.
    """
    # skip initial empty strings
    i = 0
    while parts[i] == "":
        i +=1
    return "/".join(parts[i:])



#=============================================================================

class NoteBookConnection (object):
    def __init__(self):
        pass

    #================================
    # Filesystem-specific API (may not be supported by some connections)
    
    def get_node_path(self, nodeid):
        """Returns the path of the node"""
        pass
    
    def get_node_basename(self, nodeid):
        """Returns the basename of the node"""
        pass

    #======================
    # connection API

    def connect(self, filename):
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

    def create_root(self, nodeid, attr):
        """Create the root node"""
        pass

    def create_node(self, nodeid, attr):
        """Create a node"""
        pass
        
    def read_root(self):
        """Read root node attr"""
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
        return False

    # secondary node API (try to simplify)
    
    def read_data_as_plain_text(self, nodeid):
        """Iterates over the lines of the data file as plain text"""
        pass

    # TODO: try remove concept of parentids and childids from connection API

    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        pass

    def get_parentid(self, nodeid):
        """Returns nodeid of parent of node"""
        pass
    
    def list_children_attr(self, nodeid):
        """List attr of children nodes of nodeid"""
        pass

    def list_children_nodeids(self, nodeid):
        """List nodeids of children of node"""
        pass


    #===============
    # file API

    # XXX: is path_join needed?  or can I always specify paths with '/'?

    def path_join(self, *parts):
        return os.path.join(*parts)

    # TODO: returning a fullpath to a file is not fully portable
    # will eventually need some kind of fetching mechanism
    
    def get_file(self, nodeid, filename, _path=None):
        pass

    def open_file(self, nodeid, filename, mode="r", 
                        codec=None, _path=None):
        """Open a file contained within a node"""        
        pass

    def delete_file(self, nodeid, filename, _path=None):
        """Open a file contained within a node"""
        pass

    def new_filename(self, nodeid, new_filename, ext=u"", sep=u" ", number=2, 
                     return_number=False, use_number=False, ensure_valid=True):
        pass

    def list_files(self, nodeid, filename=None):
        """
        List data files in node
        """
        pass

    def mkdir(self, nodeid, filename):
        pass
    
    def file_exists(self, nodeid, filename):
        pass

    def file_basename(self, filename):
        pass
            
    def copy_files(self, nodeid1, nodeid2):
        """
        Copy all data files from nodeid1 to nodeid2
        """
        pass
    
    def copy_file(self, nodeid1, filename1, nodeid2, filename2):
        """
        Copy a file between two nodes

        if node is None, filename is assumed to be a local file
        """
        pass


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


#=============================================================================
# syncing

class NoteBookSyncer (object):

    def __init__(self):
        self.on_conflict = on_conflict_reject


    def sync_node(self, nodeid, conn1, conn2):
        sync_node(nodeid, conn1, conn2, on_conflict=self.on_conflict)


    '''
    def move_node(self, conn1, nodeid, conn2, parentid):
        """Move a node and its whole subtree"""
        
        if (isinstance(conn1, NoteBookConnectionFS) and 
            isinstance(conn2, NoteBookConnectionFS)):
            # use efficient on-disk move

            attr = conn1.read_node(nodeid)

            path1 = conn1.get_node_path(nodeid)
            ppath2 = conn2.get_node_path(parentid)
            path2 = get_valid_unique_filename(ppath2, attr.get("title", 
                                                               "new note"))
            os.rename(path1, path2)
     '''


def on_conflict_reject(nodeid, conn1, conn2, attr1=None, attr2=None):
    """
    Existing node (conn2) always wins conflict
    """
    pass


def on_conflict_newer(nodeid, conn1, conn2, attr1=None, attr2=None):
    """
    Node with newer modified_time wins conflict

    conn2 wins ties
    """
    
    if attr1 is None:
        attr1 = conn1.read_node(nodeid)
    if attr2 is None:
        attr2 = conn2.read_node(nodeid)

    if attr1.get("modified_time", 0) > attr2.get("modified_time", 0):
        conn2.update_node(nodeid, attr1)
        sync_files(conn1, nodeid, conn2, nodeid)
    else:
        # leave node in conn2 unchanged
        pass


def sync_node(nodeid, conn1, conn2, attr=None, 
              on_conflict=on_conflict_newer):
    """
    Sync a node 'nodeid' from connection 'conn1' to 'conn2'

    Conflicts are resolved based on on_conflict (newer node by default)
    """

    if attr is None:
        attr = conn1.read_node(nodeid)
    
    try:
        conn2.create_node(nodeid, attr)
        sync_files(conn1, nodeid, conn2, nodeid)
    except NodeExists:
        # conflict
        on_conflict(nodeid, conn1, conn2, attr)



def sync_files(conn1, nodeid1, conn2, nodeid2, path1="", path2=""):
    """Sync files from conn1.nodeid1 to conn2.nodeid2"""

    files = list(conn1.list_files(nodeid1, path1))

    # ensure target path exists
    if not conn2.file_exists(nodeid2, path2):
        conn2.mkdir(nodeid2, path2)

    # remove files in node2 that don't exist in node1
    for f in list(conn2.list_files(nodeid2, path2)):
        f2 = path_join(path2, f)
        if not conn1.file_exists(nodeid1, f2):
            conn2.delete_file(nodeid2, f2)

    # copy files from node1 to node2
    for f in files:
        file1 = path_join(path1, f)
        file2 = path_join(path2, f)

        if f.endswith("/"):
            # recurse into directories
            sync_files(conn1, nodeid1, conn2, nodeid2, file1, file2)
            continue
        
        copy_files(conn1, nodeid1, file1, conn2, nodeid2, file2)


def copy_files(conn1, nodeid1, file1, conn2, nodeid2, file2):
    """Copy a file from conn1.nodeid1.file1 to conn2.nodeid2.file2"""
    
    stream1 = conn1.open_file(nodeid1, file1, "rb")
    stream2 = conn2.open_file(nodeid2, file2, "wb")
    
    while True:
        data = stream1.read(1024*4)
        if len(data) == 0:
            break
        stream2.write(data)
    
    stream1.close()
    stream2.close()



# TODO: need to keep namespace of files and node directories spearate.
# Need to carefully define what valid filenames look like.
#  - is it case-sensitive?
#  - which characters are allowed?
#  - would do a translation between what the user thinks the path is and
#    what is actually used on disk.


"""
File path translation strategy.

on disk            user-visible
filename      =>     filename
__filename    =>     filename
____filename  =>     __filename

user-visble       on disk 
filename      =>  filename (if simple file exists)
              =>  __filename (if simple file does not-exist)
__filename    =>  ____filename


Within an attached directory naming scheme is 1-to-1



Reading filename from disk:
  filename = read_from_disk()
  if filename.startswith("__"):
    # unquote filename
    return filename[2:]

Looking for filename on disk:
  if filename.startswith("__"):
    # escape '__'
    filename = "__" + filename
  if simple_file_exists(filename):  # i.e. not a node dir
    return filename
  else:
    # try quoted name
    return "__" + filename


node directories aren't allowed to start with '__'.

"""
