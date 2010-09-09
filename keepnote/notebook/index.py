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


class AttrIndex (object):
    """Indexing information for an attribute"""

    def __init__(self, name, type, multivalue=False, index_value=False):
        self._name = name
        self._type = type
        self._table_name = "Attr_" + name
        self._index_name = "IdxAttr_" + name + "_nodeid"
        self._multivalue = multivalue
        self._index_value = index_value
        self._index_value_name = "IdxAttr_" + name + "_value"


    def get_name(self):
        return self._name

    def get_table_name(self):
        return self._table_name

    def get_is_multivalue(self):
        return self._multivalue

    def init(self, cur):
        """Initialize attribute index for database"""
        cur.execute(u"""CREATE TABLE IF NOT EXISTS %s
                           (nodeid TEXT,
                            value %s);
                        """ % (self._table_name, self._type))
        cur.execute(u"""CREATE INDEX IF NOT EXISTS %s
                           ON %s (nodeid);""" % (self._index_name,
                                                 self._table_name))

        if self._index_value:
            cur.execute(u"""CREATE INDEX IF NOT EXISTS %s
                           ON %s (value);""" % (self._index_value_name,
                                                self._table_name))
            

    def add_node(self, cur, node):
        """Add a node's information to the index"""

        nodeid = node.get_attr("nodeid")
        value = node.get_attr(self._name)
        self.set(cur, nodeid, value)


    def remove_node(self, cur, node):
        """Remove node from index"""
        cur.execute(u"DELETE FROM %s WHERE nodeid=?" % self._table_name, 
                    (node.get_attr("nodeid"),))


    def get(self, cur, nodeid):
        """Get information for a node from the index"""
        cur.execute(u"""SELECT value FROM %s WHERE nodeid = ?""" % 
                    self._table_name, (nodeid,))
        values = [row[0] for row in cur.fetchall()]

        # return value
        if self._multivalue:
            return values
        else:
            if len(values) == 0:
                return None
            else:
                return values[0]

    def set(self, cur, nodeid, value):
        """Set the information for a node in the index"""

        rows = list(cur.execute((u"SELECT 1 "
                                 u"FROM %s "
                                 u"WHERE nodeid = ?") % self._table_name, 
                                (nodeid,)))
        if rows:
            row = rows[0]     

            if row[0] != value:
                # record update
                ret = cur.execute((u"UPDATE %s SET "
                                   u"value=? "
                                   u"WHERE nodeid = ?") %
                                  self._table_name,
                                  (value, nodeid))
        else:
            # insert new row
            cur.execute(u"""INSERT INTO %s VALUES 
                            (?, ?)""" % self._table_name,
                        (nodeid, value))
        


class NoteBookIndex (object):
    """Index for a NoteBook"""

    def __init__(self, notebook):
        self._notebook = notebook
        self._uniroot = notebook.get_universal_root_id()
        self._attrs = {}
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
            try:
                self.con.commit()
                self.con.close()
            except:
                # close should always happen without propogating errors
                pass
            self.con = None
            self.cur = None
    
    
    def is_corrupt(self):
        """Return True if database appear corrupt"""
        return self._corrupt


    def _get_version(self):
        """Get version from database"""
        self.con.execute(u"""CREATE TABLE IF NOT EXISTS Version 
                            (version INTEGER, update_date DATE);""")
        version = self.con.execute(u"SELECT MAX(version) FROM Version").fetchone()
        if version is not None:
            version = version[0]
        return version


    def _set_version(self, version=INDEX_VERSION):
        """Set the version of the database"""
        self.con.execute(u"INSERT INTO Version VALUES (?, datetime('now'));", 
                         (version,))


    def init_index(self):
        """Initialize the tables in the index if they do not exist"""

        self._need_index = False

        con = self.con

        try:

            # check database version
            version = self._get_version()
            if version is None or version != INDEX_VERSION:
                # version does not match, drop all tables
                self._drop_tables()
                # update version
                self._set_version()
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
            

            # TODO: make an Attr table
            # this will let me query whether an attribute is currently being
            # indexed and in what table it is in.
            #con.execute(u"""CREATE TABLE IF NOT EXISTS AttrDefs
            #               (attr TEXT,
            #                type );
            #            """)

            # initialize attribute tables
            for attr in self._attrs.itervalues():
                attr.init(self.cur)

            con.commit()
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def add_attr(self, attr):
        self._attrs[attr.get_name()] = attr

        if self.cur:
            attr.init(self.cur)

        return attr


    def _drop_tables(self):
        """clear index"""
        self.con.execute(u"DROP TABLE IF EXISTS NodeGraph")
        self.con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphNodeid")
        self.con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphParentid")
        
    
    def index_needed(self):
        """Returns True if indexing is needed"""
        return self._need_index

    
    def clear(self):
        """Erases database file and reinitializes"""

        self.close()
        index_file = get_index_file(self._notebook)
        if os.path.exists(index_file):
            os.remove(index_file)
        self.open()


    def index_all(self, root=None):
        """
        Reindex all nodes under root

        This function returns an iterator which must be iterated to completion.
        """
        
        if root is None:
            root = self._notebook
        
        visit = set()
        queue = []

        # record nodes that change while indexing
        def changed_callback(nodes, recurse):
            for node in nodes:
                if node not in visit:
                    queue.append(node)
        self._notebook.node_changed.add(changed_callback)

        # perform indexing
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

        # remove callback for notebook changes
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
                                      u"parentid=?, "
                                      u"basename=?, "
                                      u"symlink=? "
                                      u"WHERE nodeid = ?",
                                      (parentid, basename, symlink, nodeid))
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


            # update attrs
            for attr in self._attrs.itervalues():
                attr.add_node(cur, node)

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
            #con.commit()

            # update attrs
            for attr in self._attrs.itervalues():
                attr.remove_node(cur, node)

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])

        
    def get_node_path(self, nodeid, visit=None):
        """Get node path for a nodeid"""
        
        # TODO: handle multiple parents

        con, cur = self.con, self.cur

        if visit is None:
            visit = set()
        visit.add(nodeid)

        try:
            def walk(nodeid):
                cur.execute(u"""SELECT nodeid, parentid, basename
                                FROM NodeGraph
                                WHERE nodeid=?""", (nodeid,))
                row = cur.fetchone()

                if row:
                    nodeid, parentid, basename = row
                    if parentid in visit:
                        return None

                    if parentid != self._uniroot:
                        path = self.get_node_path(parentid, visit)
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


    def search_titles(self, query):
        """Return nodeids of nodes with matching titles"""

        if "title" not in self._attrs:
            return

        # order titles by exact matches and then alphabetically
        self.cur.execute(
            u"""SELECT nodeid, value FROM %s WHERE value LIKE ?
                       ORDER BY value != ?, value """ % 
            self._attrs["title"].get_table_name(),
            (u"%" + query + u"%", query))
        
        return list(self.cur.fetchall())


    def get_attr(self, nodeid, key):
        attr = self._attrs.get(key, None)
        if attr:
            return attr.get(self.cur, nodeid)
        else:
            return []


    def save(self):
        """Save index"""

        if self.con is not None:
            self.con.commit()


    def _on_corrupt(self, error, tracebk=None):

        self._corrupt = True

        # display error
        keepnote.log_error(error, tracebk)

        # TODO: reload database?
        
