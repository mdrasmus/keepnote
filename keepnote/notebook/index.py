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

# import sqlite
try:
    import pysqlite2
    #print pysqlite2
    import pysqlite2.dbapi2 as sqlite
except Exception, e:
    #print "fallback", e
    import sqlite3  as sqlite
sqlite.enable_shared_cache(True)
#sqlite.threadsafety = 0


#print sqlite.sqlite_version


# keepnote imports
import keepnote
#import keepnote.search


# index filename
INDEX_FILE = u"index.sqlite"
INDEX_VERSION = 3


NULL = object()


def get_index_file(notebook):
    """Get the index filename for a notebook"""

    index_dir = notebook.pref.get("index_dir", default=u"")

    if not index_dir or not os.path.exists(index_dir):
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

    def is_multivalue(self):
        return self._multivalue

    def init(self, cur):
        """Initialize attribute index for database"""

        # multivalue is not implemented yet
        assert not self._multivalue

        cur.execute(u"""CREATE TABLE IF NOT EXISTS %s
                           (nodeid TEXT,
                            value %s,
                            UNIQUE(nodeid) ON CONFLICT REPLACE);
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

    def add_nodeid(self, cur, nodeid, attr):
        val = attr.get(self._name, NULL)
        if val is not NULL:
            self.set(cur, nodeid, val)


    def remove_node(self, cur, node):
        """Remove node from index"""
        cur.execute(u"DELETE FROM %s WHERE nodeid=?" % self._table_name, 
                    (node.get_attr("nodeid"),))


    def remove_nodeid(self, cur, nodeid):
        """Remove node from index"""
        cur.execute(u"DELETE FROM %s WHERE nodeid=?" % self._table_name, 
                    (nodeid,))


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

        # insert new row
        cur.execute(u"""INSERT INTO %s VALUES (?, ?)""" % self._table_name,
                        (nodeid, value))



class NoteBookIndex (object):
    """Index for a NoteBook"""

    def __init__(self, notebook):
        self._notebook = notebook
        self._uniroot = notebook.get_universal_root_id()
        self._attrs = {}
        self._need_index = False
        self._corrupt = False
        self._has_fulltext = False
        
        self.con = None
        self.cur = None        

        self.open()

        self.add_node(notebook)

    #-----------------------------------------
    # index connection

    def open(self):
        """Open connection to index"""

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
            raise


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
    

    def save(self):
        """Save index"""

        if self.con is not None:
            try:
                self.con.commit()
            except:
                self.open()


    def clear(self):
        """Erases database file and reinitializes"""

        self.close()
        index_file = get_index_file(self._notebook)
        if os.path.exists(index_file):
            os.remove(index_file)
        self.open()


    #-----------------------------------------
    # index initialization and versioning

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
                            mtime FLOAT,
                            symlink BOOLEAN,
                            UNIQUE(nodeid) ON CONFLICT REPLACE);
                        """)

            con.execute(u"""CREATE INDEX IF NOT EXISTS IdxNodeGraphNodeid 
                           ON NodeGraph (nodeid);""")
            con.execute(u"""CREATE INDEX IF NOT EXISTS IdxNodeGraphParentid 
                           ON NodeGraph (parentid);""")
            

            # full text table
            try:
                # test for fts3 availability
                con.execute("CREATE VIRTUAL TABLE fts3test USING fts3(col TEXT);")
                con.execute("DROP TABLE fts3test;")

                if not list(con.execute(u"""SELECT 1 FROM sqlite_master 
                                   WHERE name == 'fulltext';""")):
                    con.execute(u"""CREATE VIRTUAL TABLE 
                                fulltext USING 
                                fts3(nodeid TEXT, content TEXT,
                                     tokenize=porter);""")
                self._has_fulltext = True
            except Exception, e:
                print e
                self._has_fulltext = False

            #print "fulltext", self._has_fulltext

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

    
    def is_corrupt(self):
        """Return True if database appear corrupt"""
        return self._corrupt


    def _on_corrupt(self, error, tracebk=None):

        self._corrupt = True

        # display error
        keepnote.log_error(error, tracebk)

        # TODO: reload database?


    def add_attr(self, attr):
        """Add indexing for a node attribute using AttrIndex"""
        self._attrs[attr.get_name()] = attr
        if self.cur:
            attr.init(self.cur)
        return attr


    def _drop_tables(self):
        """drop NodeGraph tables"""
        self.con.execute(u"DROP TABLE IF EXISTS NodeGraph")
        self.con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphNodeid")
        self.con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphParentid")
        self.con.execute(u"DROP TABLE IF EXISTS fulltext;")
        
    
    def index_needed(self):
        """Returns True if indexing is needed"""
        return self._need_index

    
    def has_fulltext_search(self):
        return self._has_fulltext
    

    #-------------------------------------
    # add/remove nodes from index

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


    def get_node_mtime(self, node):
        
        nodeid = node.get_attr("nodeid")
        self.cur.execute(u"""SELECT mtime FROM NodeGraph
                             WHERE nodeid=?""", (nodeid,))
        row = self.cur.fetchone()
        if row:
            return row[0]
        else:
            return 0.0


    def get_nodeid_mtime(self, nodeid):
        
        self.cur.execute(u"""SELECT mtime FROM NodeGraph
                             WHERE nodeid=?""", (nodeid,))
        row = self.cur.fetchone()
        if row:
            return row[0]
        else:
            return 0.0


            
    def add_node(self, node, mtime=None):
        """Add a node to the index"""               

        # TODO: remove single parent assumption        

        if self.con is None:
            return

        try:
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

            # TODO: refactor mtime
            if mtime is None:
                mtime = os.stat(node.get_path()).st_mtime

            # update nodegraph
            self.cur.execute(
                u"""INSERT INTO NodeGraph VALUES (?, ?, ?, ?, ?)""", 
                (nodeid, parentid, basename, mtime, symlink))

            # update attrs
            for attr in self._attrs.itervalues():
                attr.add_node(self.cur, node)

            # update fulltext
            infile = self._notebook._conn.read_data_as_plain_text(nodeid)
            self.index_nodeid_text(nodeid, node._attr, infile)


        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def add_nodeid(self, nodeid, parentid, basename, attr, mtime):
        """Add a node to the index"""               

        # TODO: remove single parent assumption        

        if self.con is None:
            return

        try:
            # get info
            if parentid is None:
                parentid = self._uniroot
                basename = u""
            symlink = False
            
            # update nodegraph
            self.cur.execute(
                u"""INSERT INTO NodeGraph VALUES (?, ?, ?, ?, ?)""", 
                (nodeid, parentid, basename, mtime, symlink))

            # update attrs
            for attrindex in self._attrs.itervalues():
                attrindex.add_nodeid(self.cur, nodeid, attr)

            # update fulltext
            infile = self._notebook._conn.read_data_as_plain_text(nodeid)
            self.index_nodeid_text(nodeid, attr, infile)


        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def remove_node(self, node):
        """Remove node from index"""
        return self.remove_nodeid(node.get_attr("nodeid"))


    def remove_nodeid(self, nodeid):
        """Remove node from index using nodeid"""

        if self.con is None:
            return
        
        try:
            # delete node
            self.cur.execute(u"DELETE FROM NodeGraph WHERE nodeid=?", (nodeid,))

            # update attrs
            for attr in self._attrs.itervalues():
                attr.remove_nodeid(self.cur, nodeid)

            # delete children
            for (childid,) in self.cur.execute(
                u"SELECT nodeid FROM NodeGraph WHERE parentid=?", (nodeid,)):
                self.remove_nodeid(childid)

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def index_nodeid_text(self, nodeid, attr, infile):

        if (attr.get("content_type", None) == 
            keepnote.notebook.CONTENT_TYPE_PAGE):
            try:
                text = attr.get("title", "") + "\n" + "".join(infile)
            except Exception, e:
                print e
                return
            self.insert_text(nodeid, text)


    def insert_text(self, nodeid, text):

        if not self._has_fulltext:
            return

        if list(self.cur.execute(u"SELECT 1 FROM fulltext WHERE nodeid = ?",
                                 (nodeid,))):
            self.cur.execute(
                u"UPDATE fulltext SET content = ? WHERE nodeid = ?;",
                (text, nodeid))
        else:
            self.cur.execute(u"INSERT INTO fulltext VALUES (?, ?);",
                             (nodeid, text))



    #-------------------------
    # queries
        
    def get_node_path(self, nodeid, visit=None):
        """Get node path for a nodeid"""
        
        if self.con is None:
            return None

        # TODO: handle multiple parents

        if visit is None:
            visit = set()
        visit.add(nodeid)

        try:
            def walk(nodeid):
                self.cur.execute(u"""SELECT nodeid, parentid, basename
                                FROM NodeGraph
                                WHERE nodeid=?""", (nodeid,))
                row = self.cur.fetchone()

                if row:
                    nodeid, parentid, basename = row
                    if parentid in visit:
                        return None

                    if parentid != self._uniroot:
                        path = self.get_node_path(parentid, visit)
                        if path is not None:
                            path.append(nodeid)
                            return path
                        else:
                            return None
                    else:
                        return [nodeid]
            return walk(nodeid)

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def search_titles(self, query):
        """Return nodeids of nodes with matching titles"""

        if "title" not in self._attrs:
            return []

        # order titles by exact matches and then alphabetically
        self.cur.execute(
            u"""SELECT nodeid, value FROM %s WHERE value LIKE ?
                       ORDER BY value != ?, value """ % 
            self._attrs["title"].get_table_name(),
            (u"%" + query + u"%", query))
        
        return list(self.cur.fetchall())


    def get_attr(self, nodeid, key):
        """Query indexed attribute for a node"""
        attr = self._attrs.get(key, None)
        if attr:
            return attr.get(self.cur, nodeid)
        else:
            return []


    def search_contents(self, text):
        
        # fallback
        if not self._has_fulltext:
            words = [x.lower() for x in text.strip().split()]
            return (node.get_attr("nodeid") for node in 
                    keepnote.search.search_manual(self._notebook, words)
                    if node is not None)

        # search db with fts3
        res = self.cur.execute("""SELECT nodeid FROM fulltext 
                  WHERE content MATCH ?;""", (text,))
        return (row[0] for row in res)
