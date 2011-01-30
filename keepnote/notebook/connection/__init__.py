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
        
    def read_root(self):
        """Read root node attr"""
        pass
    
    def read_node(self, nodeid):
        """Read a node attr"""
        pass

    def update_node(self, nodeid, attr):
        """Write node attr"""
        pass

    def create_root(self, filename, nodeid, attr):
        """Create the root node"""
        pass

    def create_node(self, nodeid, parentid, attr, _path=None):
        """Create a node"""
        pass
    
    def delete_node(self, nodeid):
        """Delete node"""
        pass

    # secondary node API (try to simplify)

    def move_node(self, nodeid, new_parentid, attr):
        """Move a node to a new parent"""
        pass

    def read_data_as_plain_text(self, nodeid):
        """Iterates over the lines of the data file as plain text"""
        pass

    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        pass

    def get_parentid(self, nodeid):
        """Returns nodeid of parent of node"""
        pass
    
    def list_children_attr(self, nodeid, _path=None):
        """List attr of children nodes of nodeid"""
        pass

    def list_children_nodeids(self, nodeid, _path=None):
        """List nodeids of children of node"""
        pass


    #===============
    # file API

    # XXX: is path_join needed?  or can I always specify paths with '/'?

    def path_join(self, *parts):
        return os.path.join(*parts)

    # TODO: returning a fullpath to a file is not fully portable
    # will eventually need some kind of fetching mechanism
    
    def get_node_file(self, nodeid, filename, _path=None):
        pass

    def open_node_file(self, nodeid, filename, mode="r", 
                        codec=None, _path=None):
        """Open a file contained within a node"""        
        pass

    def delete_node_file(self, nodeid, filename, _path=None):
        """Open a file contained within a node"""
        pass

    def new_filename(self, nodeid, new_filename, ext=u"", sep=u" ", number=2, 
                     return_number=False, use_number=False, ensure_valid=True):
        pass

    def mkdir(self, nodeid, filename, _path=None):
        pass
    
    def isfile(self, nodeid, filename, _path=None):
        pass

    def path_exists(self, nodeid, filename, _path=None):
        pass

    def path_basename(self, filename):
        pass
        
    def listdir(self, nodeid, filename=None, _path=None):
        """
        List data files in node
        """
        pass
    
    def copy_node_files(self, nodeid1, nodeid2):
        """
        Copy all data files from nodeid1 to nodeid2
        """
        pass
    
    def copy_node_file(self, nodeid1, filename1, nodeid2, filename2):
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

