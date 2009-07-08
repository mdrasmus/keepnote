"""

    KeepNote
    Notebook indexing

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
import os
from sqlite3 import dbapi2 as sqlite

# keepnote imports
import keepnote


# index filename
INDEX_FILE = "index.sqlite"



def get_index_file(notebook):
    """Get the index filename for a notebook"""
    return os.path.join(notebook.get_pref_dir(), INDEX_FILE)



class NoteBookIndex (object):
    """Index for a NoteBook"""

    def __init__(self, notebook):
        self._notebook = notebook
        self._unirootid = notebook.get_universal_root_id()

        self.con = None
        self.cur = None
        self.open()


    def open(self):
        """Open connection to index"""
        index_file = get_index_file(self._notebook)
        self.con = sqlite.connect(index_file, isolation_level="DEFERRED")
        self.cur = self.con.cursor()

        self.init_index()


    def close(self):
        """Close connection to index"""
        
        self.con.close()
        self.con = None
        self.cur = None


    def init_index(self):
        """Initialize the tables in the index if they do not exist"""

        # init NodeGraph table
        query = """CREATE TABLE IF NOT EXISTS NodeGraph 
                       (nodeid TEXT,
                        parentid TEXT,
                        basename TEXT,
                        symlink BOOLEAN);
                    """
        self.cur.execute(query)
        self.con.commit()

            
    def add_node(self, node):
        """Add a node to the index"""
        
        if self.con is None:
            return

        # get info
        nodeid = str(node.get_attr("nodeid"))
        parent = node.get_parent()
        if parent:
            parentid = str(parent.get_attr("nodeid"))
            basename = node.get_basename()
        else:
            parentid = self._unirootid
            basename = ""
        symlink = False
        

        # update
        ret = self.cur.execute(
            """UPDATE NodeGraph SET 
                   nodeid=?,
                   parentid=?,
                   basename=?,
                   symlink=?
                   WHERE nodeid = ?""",
            (nodeid, parentid, basename, symlink, nodeid))

        # insert if new
        if ret.rowcount == 0:
            self.cur.execute("""
                INSERT INTO NodeGraph VALUES 
                   (?, ?, ?, ?)""",
            (nodeid,
             parentid,
             basename,
             symlink,
             ))


    def remove_node(self, node):
        
        if self.con is None:
            return

        # get info
        nodeid = str(node.get_attr("nodeid"))        
        
        # delete node
        ret = self.cur.execute(
            "DELETE FROM NodeGraph WHERE nodeid=?", (nodeid,))


    def save(self):
        """Save index"""
        
        if self.con:
            self.con.commit()


