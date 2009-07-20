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
from thread import get_ident

from sqlite3 import dbapi2 as sqlite

# keepnote imports
import keepnote


# index filename
INDEX_FILE = "index.sqlite"



def get_index_file(notebook):
    """Get the index filename for a notebook"""
    return os.path.join(notebook.get_pref_dir(), INDEX_FILE)


class NoteBookIndexDummy (object):
    """Index for a NoteBook"""

    def __init__(self, notebook):
        pass

    def open(self):
        """Open connection to index"""
        pass

    def get_con(self):
        """Get connection for thread"""
        pass

    def close(self):
        """Close connection to index"""
        pass

    def init_index(self):
        """Initialize the tables in the index if they do not exist"""
        pass
            
    def add_node(self, node):
        """Add a node to the index"""
        pass

    def remove_node(self, node):
        """Remove node from index"""
        pass
        
    def get_node_path(self, nodeid):
        """Get node path for a nodeid"""
        return None

    def search_titles(self, query):
        """Return nodeids of nodes with matching titles"""
        return []

    def save(self):
        """Save index"""
        pass



class NoteBookIndex (object):
    """Index for a NoteBook"""

    def __init__(self, notebook):
        self._notebook = notebook
        self._uniroot = notebook.get_universal_root_id()

        self.con = None
        self.open()

        self.add_node(notebook)


    def open(self):
        """Open connection to index"""

        if self.con is None:
            self.con = {}

        index_file = get_index_file(self._notebook)
        con = sqlite.connect(index_file, isolation_level="DEFERRED")
        self.con[get_ident()] = (con, con.cursor())

        self.init_index()


    def get_con(self):
        """Get connection for thread"""

        ident = get_ident()
        if ident not in self.con:
            index_file = get_index_file(self._notebook)
            con = sqlite.connect(index_file, isolation_level="DEFERRED")
            self.con[ident] = (con, con.cursor())
            
        return self.con[ident]


    def close(self):
        """Close connection to index"""
        
        if self.con is not None:

            for con, cur in self.con.itervalues():
                con.close()

            self.con = None


    def init_index(self):
        """Initialize the tables in the index if they do not exist"""

        con, cur = self.get_con()

        # init NodeGraph table
        con.execute("""CREATE TABLE IF NOT EXISTS NodeGraph 
                       (nodeid TEXT,
                        parentid TEXT,
                        basename TEXT,
                        symlink BOOLEAN);
                    """)

        con.execute("""CREATE INDEX IF NOT EXISTS IdxNodeGraphNodeid 
                       ON NodeGraph (nodeid);""")
        con.execute("""CREATE INDEX IF NOT EXISTS IdxNodeGraphParentid 
                       ON NodeGraph (parentid);""")


        # init Nodes table
        con.execute("""CREATE TABLE IF NOT EXISTS Nodes
                       (nodeid TEXT,
                        title TEXT);
                    """)

        con.execute("""CREATE INDEX IF NOT EXISTS IdxNodesTitle 
                       ON Nodes (Title);""")

        con.commit()



            
    def add_node(self, node):
        """Add a node to the index"""
        
        if self.con is None:
            return
        con, cur = self.get_con()

        # get info
        nodeid = str(node.get_attr("nodeid"))
        parent = node.get_parent()
        if parent:
            parentid = str(parent.get_attr("nodeid"))
            basename = node.get_basename()
        else:
            parentid = self._uniroot
            basename = ""
        symlink = False
        
        # NodeGraph
        # update, insert if new
        ret = cur.execute(
            """UPDATE NodeGraph SET 
                   nodeid=?,
                   parentid=?,
                   basename=?,
                   symlink=?
                   WHERE nodeid = ?""",
            (nodeid, parentid, basename, symlink, nodeid))
        if ret.rowcount == 0:
            cur.execute("""
                INSERT INTO NodeGraph VALUES 
                   (?, ?, ?, ?)""",
            (nodeid,
             parentid,
             basename,
             symlink,
             ))

        #Nodes
        # update
        ret = cur.execute(
            """UPDATE Nodes SET 
                   nodeid=?,
                   title=?
                   WHERE nodeid = ?""",
            (nodeid, node.get_title(), nodeid))
        
        # insert if new
        if ret.rowcount == 0:
            cur.execute("""
                INSERT INTO Nodes VALUES 
                   (?, ?)""",
            (nodeid, node.get_title()))

        #con.commit()


    def remove_node(self, node):
        """Remove node from index"""

        if self.con is None:
            return
        con, cur = self.get_con()

        # get info
        nodeid = str(node.get_attr("nodeid"))        

        # delete node
        cur.execute(
            "DELETE FROM NodeGraph WHERE nodeid=?", (nodeid,))
        cur.execute(
            "DELETE FROM Nodes WHERE nodeid=?", (nodeid,))
        #con.commit()
        

        
    def get_node_path(self, nodeid):
        """Get node path for a nodeid"""
        
        # TODO: handle multiple parents

        con, cur = self.get_con()

        def walk(nodeid):
            cur.execute("""SELECT nodeid, parentid, basename
                                FROM NodeGraph
                                WHERE nodeid=?""", (nodeid,))
            row = cur.fetchone()

            if row:
                nodeid, parentid, basename = row
                if parentid != self._uniroot:
                    path = self.get_node_path(parentid)
                    if path is not None:
                        path.append(basename)
                        return path
                    else:
                        return None
                else:
                    return [basename]
        return walk(nodeid)


    def search_titles(self, query):
        """Return nodeids of nodes with matching titles"""

        con, cur = self.get_con()

        # order titles by exact matches and then alphabetically
        cur.execute("""SELECT nodeid, title FROM Nodes WHERE title LIKE ?
                       ORDER BY title != ?, title """,
                    ("%" + query + "%", query))
        
        return list(cur.fetchall())

        


    def save(self):
        """Save index"""

        if self.con is not None:
            con, cur = self.get_con()
            con.commit()




#NoteBookIndex = NoteBookIndexDummy
