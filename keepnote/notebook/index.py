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
import sys
import traceback
from thread import get_ident
import sqlite3  as sqlite
sqlite.enable_shared_cache(True)
#sqlite.threadsafety = 0

# keepnote imports
import keepnote


# index filename
INDEX_FILE = u"index.sqlite"
INDEX_VERSION = 1


def get_index_file(notebook):
    """Get the index filename for a notebook"""

    if notebook.pref.index_dir and os.path.exists(notebook.pref.index_dir):
        index_dir = notebook.pref.index_dir
    else:
        index_dir = notebook.get_pref_dir()

    return os.path.join(index_dir, INDEX_FILE)


def preorder(node):
    """Iterate through nodes in pre-order traversal"""

    queue = [node]

    while len(queue) > 0:
        node = queue.pop()
        yield node

        for child in node.iter_temp_children():
            queue.append(child)


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

    def search_titles(self, query, cols=[]):
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
        self._need_index = False
        self._corrupt = False
        
        self.con = None
        self.cur = None
        self.open()

        self.add_node(notebook)


    def open(self):
        """
        Open connection to index
        """

        try:
            index_file = get_index_file(self._notebook)
            self._corrupt = False
            self.con = sqlite.connect(index_file, isolation_level="DEFERRED",
                                      check_same_thread=False)
            self.cur = self.con.cursor()
            self.con.execute(u"PRAGMA read_uncommitted = true;")

            self.init_index()
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def close(self):
        """Close connection to index"""
        
        if self.con is not None:
            self.con.commit()
            self.con.close()
            self.con = None
            self.cur = None
    
    
    def is_corrupt(self):
        """Return True if database appear corrupt"""
        return self._corrupt


    def init_index(self):
        """Initialize the tables in the index if they do not exist"""

        self._need_index = False

        con = self.con

        try:

            # check database version
            con.execute(u"""CREATE TABLE IF NOT EXISTS Version 
                            (version INTEGER, update_date DATE);""")
            version = con.execute(u"SELECT MAX(version) FROM Version").fetchone()

            if version is None or version[0] != INDEX_VERSION:
                # version does not exist, drop all tables
                con.execute(u"DROP TABLE IF EXISTS NodeGraph")
                con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphNodeid")
                con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphParentid")
                con.execute(u"DROP TABLE IF EXISTS Nodes")
                con.execute(u"DROP TABLE IF EXISTS IdxNodesTitle")

                # update version
                con.execute(u"INSERT INTO Version VALUES (?, datetime('now'));", (INDEX_VERSION,))

                self._need_index = True


            # init NodeGraph table
            con.execute(u"""CREATE TABLE IF NOT EXISTS NodeGraph 
                           (nodeid TEXT,
                            parentid TEXT,
                            basename TEXT,
                            symlink BOOLEAN);
                        """)

            con.execute(u"""CREATE INDEX IF NOT EXISTS IdxNodeGraphNodeid 
                           ON NodeGraph (nodeid);""")
            con.execute(u"""CREATE INDEX IF NOT EXISTS IdxNodeGraphParentid 
                           ON NodeGraph (parentid);""")


            # init Nodes table
            con.execute(u"""CREATE TABLE IF NOT EXISTS Nodes
                           (nodeid TEXT,
                            title TEXT,
                            icon TEXT);
                        """)

            con.execute(u"""CREATE INDEX IF NOT EXISTS IdxNodesTitle 
                           ON Nodes (Title);""")

            con.commit()
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])

    
    def index_needed(self):
        return self._need_index

    
    def clear(self):
        """Erases database file and reinitializes"""

        self.close()
        index_file = get_index_file(self._notebook)
        if os.path.exists(index_file):
            os.remove(index_file)
        self.open()


    def index_all(self, root=None):
        """Reindex all nodes under root"""
        
        if root is None:
            root = self._notebook
        
        visit = set()
        queue = []

        def changed_callback(nodes, recurse):
            for node in nodes:
                if node not in visit:
                    queue.append(node)

        self._notebook.node_changed.add(changed_callback)

        for node in preorder(root):
            self.add_node(node)
            visit.add(node)
            yield node

        # walk through nodes missed in original pass
        while len(queue) > 0:
            node = queue.pop()
            if node not in visit:
                for node2 in preorder(node):
                    self.add_node(node)
                    visit.add(node)
                    yield node

        self._notebook.node_changed.remove(changed_callback)

        # record index complete
        self._need_index = False

            
    def add_node(self, node):
        """Add a node to the index"""               

        if self.con is None:
            return
        con, cur = self.con, self.cur

        try:

            # TODO: remove single parent assumption

            # get info
            nodeid = node.get_attr("nodeid")
            parent = node.get_parent()
            if parent:
                parentid = parent.get_attr("nodeid")
                basename = node.get_basename()
            else:
                parentid = self._uniroot
                basename = u""
            symlink = False
            title = node.get_title()

            #------------------
            # NodeGraph
            rows = list(cur.execute(u"SELECT parentid, basename "
                                    u"FROM NodeGraph "
                                    u"WHERE nodeid = ?", (nodeid,)))
            if rows:
                row = rows[0]
                if row[0] != parentid or row[1] != basename:
                    # record update
                    ret = cur.execute(u"UPDATE NodeGraph SET "
                                      u"nodeid=?, "
                                      u"parentid=?, "
                                      u"basename=?, "
                                      u"symlink=? "
                                      u"WHERE nodeid = ?",
                                      (nodeid, parentid, basename, 
                                       symlink, nodeid))
            else:
                # insert new row
                cur.execute(u"""
                    INSERT INTO NodeGraph VALUES 
                       (?, ?, ?, ?)""",
                (nodeid,
                 parentid,
                 basename,
                 symlink,
                 ))

            #-----------------
            # Nodes
            rows = list(cur.execute(u"SELECT title "
                                    u"FROM Nodes "
                                    u"WHERE nodeid = ?", (nodeid,)))
            if rows:
                row = rows[0]     

                if row[0] != title:
                    # record update
                    ret = cur.execute(u"UPDATE Nodes SET "
                                      u"nodeid=?, "
                                      u"title=?, "
                                      u"icon=? "
                                      u"WHERE nodeid = ?",
                                      (nodeid, title, u"", nodeid))
            else:
                # insert new row
                cur.execute(u"""
                    INSERT INTO Nodes VALUES 
                       (?, ?, ?)""",
                (nodeid, title, u""))

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def remove_node(self, node):
        """Remove node from index"""

        if self.con is None:
            return
        con, cur = self.con, self.cur

        try:
            # get info
            nodeid = node.get_attr("nodeid")

            # delete node
            cur.execute(
                u"DELETE FROM NodeGraph WHERE nodeid=?", (nodeid,))
            cur.execute(
                u"DELETE FROM Nodes WHERE nodeid=?", (nodeid,))
            #con.commit()

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])

        
    def get_node_path(self, nodeid):
        """Get node path for a nodeid"""
        
        # TODO: handle multiple parents

        con, cur = self.con, self.cur

        try:
            def walk(nodeid):
                cur.execute(u"""SELECT nodeid, parentid, basename
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

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def search_titles(self, query, cols=[]):
        """Return nodeids of nodes with matching titles"""

        con, cur = self.con, self.cur

        if cols:
            sql = u"," + u",".join(cols)
        else:
            sql = u""

        # order titles by exact matches and then alphabetically
        cur.execute(u"""SELECT nodeid, title %s FROM Nodes WHERE title LIKE ?
                       ORDER BY title != ?, title """ % sql,
                    (u"%" + query + u"%", query))
        
        return list(cur.fetchall())

        


    def save(self):
        """Save index"""

        if self.con is not None:
            self.con.commit()


    def _on_corrupt(self, error, tracebk=None):

        self._corrupt = True

        # display error
        keepnote.log_error(error, tracebk)


#NoteBookIndex = NoteBookIndexDummy
