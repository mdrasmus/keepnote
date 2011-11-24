"""

    KeepNote
    Notebook indexing

"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
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


# python imports
from itertools import chain
import os
import sys
import time
import traceback

# import sqlite
try:
    import pysqlite2
    import pysqlite2.dbapi2 as sqlite
except Exception, e:
    import sqlite3  as sqlite
#sqlite.enable_shared_cache(True)
#sqlite.threadsafety = 0


# keepnote imports
import keepnote



# index filename
INDEX_FILE = u"index.sqlite"
INDEX_VERSION = 3


NULL = object()



def match_words(infile, words):
    """Returns True if all of the words in list 'words' appears in the
       node title or data file"""

    matches = dict.fromkeys(words, False)

    for line in infile:
        line = line.lower()
        for word in words:
            if word in line:
                matches[word] = True

    # return True if all words are found (AND)
    for val in matches.itervalues():
        if not val:
            return False
    
    return True



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

    def drop(self, cur):
        cur.execute(u"DROP TABLE IF EXISTS %s" % self._table_name)
            

    def add_node(self, cur, nodeid, attr):
        val = attr.get(self._name, NULL)
        if val is not NULL:
            self.set(cur, nodeid, val)


    def remove_node(self, cur, nodeid):
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


# TODO: remove uniroot

class NoteBookIndex (object):
    """Index for a NoteBook"""

    def __init__(self, conn, index_file):
        self._nconn = conn
        self._index_file = index_file
        self._uniroot = keepnote.notebook.UNIVERSAL_ROOT
        self._attrs = {}

        # index state/capabilities
        self._need_index = False
        self._corrupt = False
        self._has_fulltext = False
        
        self.con = None # sqlite connection
        self.cur = None # sqlite cursor

        # start index
        self.open()


    #-----------------------------------------
    # index connection

    def open(self, auto_clear=True):
        """Open connection to index"""
        
        try:
            self._corrupt = False
            self._need_index = False
            self.con = sqlite.connect(self._index_file, 
                                      #isolation_level="DEFERRED",
                                      isolation_level="IMMEDIATE",
                                      check_same_thread=False)
            self.cur = self.con.cursor()
            #self.con.execute(u"PRAGMA read_uncommitted = true;")

            self.init_index(auto_clear=auto_clear)
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

        try:
            mtime = time.time()
            self.con.execute("""UPDATE NodeGraph SET mtime = ? WHERE nodeid = ?;""",
                             (mtime, self._nconn.get_rootid()))

            if self.con is not None:
                try:
                    self.con.commit()
                except:
                    self.open()
        except Exception, e:
            self._on_corrupt(e, sys.exc_info()[2])

        


    def clear(self):
        """Erases database file and reinitializes"""

        self.close()
        if self._index_file:
            if os.path.exists(self._index_file):
                os.remove(self._index_file)
            self.open(auto_clear=False)


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


    def init_index(self, auto_clear=True):
        """Initialize the tables in the index if they do not exist"""

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
                con.execute(u"DROP TABLE IF EXISTS fts3test;")
                con.execute(
                    "CREATE VIRTUAL TABLE fts3test USING fts3(col TEXT);")
                con.execute("DROP TABLE fts3test;")

                # create fulltext table if it does not already exist
                if not list(con.execute(u"""SELECT 1 FROM sqlite_master 
                                   WHERE name == 'fulltext';""")):
                    con.execute(u"""CREATE VIRTUAL TABLE 
                                fulltext USING 
                                fts3(nodeid TEXT, content TEXT,
                                     tokenize=porter);""")
                self._has_fulltext = True
            except Exception, e:
                keepnote.log_error(e)
                self._has_fulltext = False

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

            # check whether index is uptodate
            #if not self._need_index:
            #    self._need_index = self.check_index()

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])

            keepnote.log_message("reinitializing index '%s'\n" %
                                 self._index_file)
            self.clear()

    
    def is_corrupt(self):
        """Return True if database appear corrupt"""
        return self._corrupt


    def check_index(self):
        """Check filesystem to see if index is up to date"""

        keepnote.log_message("checking index... ")
        start = time.time()
        mtime_index = self.get_mtime()
        mtime = keepnote.notebook.connection.fs.last_node_change(
            self._nconn._get_node_path(self._nconn.get_rootid()))
        keepnote.log_message("%f seconds\n" % (time.time() - start))
        return (mtime > mtime_index)
                    

    def _on_corrupt(self, error, tracebk=None):

        self._corrupt = True
        self._need_index = True

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
        
        # drop attribute tables
        table_names = [x for (x,) in self.con.execute(
            u"""SELECT name FROM sqlite_master WHERE name LIKE 'Attr_%'""")]

        for table_name in table_names:
            self.con.execute(u"""DROP TABLE %s;""" % table_name)
        

    
    def index_needed(self):
        """Returns True if indexing is needed"""
        return self._need_index


    def set_index_needed(self, val=True):
        self._need_index = val
    
    def has_fulltext_search(self):
        return self._has_fulltext
    

    #-------------------------------------
    # add/remove nodes from index

    # TODO: prevent "unmanaged change detected" warning when doing index_all()
    # Also I think double indexing is occuring

    def index_all(self, rootid=None):
        """
        Reindex all nodes under 'rootid'

        This function returns an iterator which must be iterated to completion.
        """
        
        visit = set()
        conn = self._nconn        
        if rootid is None:
            rootid = conn.get_rootid()
        

        def preorder(conn, nodeid):
            """Iterate through nodes in pre-order traversal"""
            queue = [nodeid]
            while len(queue) > 0:
                nodeid = queue.pop()
                yield nodeid
                queue.extend(
                    conn._list_children_nodeids(nodeid, _index=False))


        # perform indexing
        for nodeid in preorder(conn, rootid):
            yield nodeid

        # record index complete
        self._need_index = False


    def get_node_mtime(self, nodeid):
        
        self.cur.execute(u"""SELECT mtime FROM NodeGraph
                             WHERE nodeid=?""", (nodeid,))
        row = self.cur.fetchone()
        if row:
            return row[0]
        else:
            return 0.0

    def set_node_mtime(self, nodeid, mtime=None):

        if mtime is None:
            mtime = time.time()

        self.con.execute("""UPDATE NodeGraph SET mtime = ? WHERE nodeid = ?;""",
                         (mtime, nodeid))


    def get_mtime(self):
        """Get last modification time of the index"""
        return os.stat(self._index_file).st_mtime

    
    def add_node(self, nodeid, parentid, basename, attr, mtime):
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
                attrindex.add_node(self.cur, nodeid, attr)

            # update fulltext
            infile = self._nconn.read_data_as_plain_text(nodeid)
            self.index_node_text(nodeid, attr, infile)
            
        except Exception, e:
            keepnote.log_error("error index node %s '%s'" % 
                               (nodeid, attr.get("title", "")))
            self._on_corrupt(e, sys.exc_info()[2])


    def remove_node(self, nodeid):
        """Remove node from index using nodeid"""

        if self.con is None:
            return
        
        try:
            # delete node
            self.cur.execute(u"DELETE FROM NodeGraph WHERE nodeid=?", (nodeid,))

            # update attrs
            for attr in self._attrs.itervalues():
                attr.remove_node(self.cur, nodeid)

            # delete children
            #for (childid,) in self.cur.execute(
            #    u"SELECT nodeid FROM NodeGraph WHERE parentid=?", (nodeid,)):
            #    self.remove_node(childid)

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])


    def index_node_text(self, nodeid, attr, infile):

        try:
            text = attr.get("title", "") + "\n" + "".join(infile)
            self.insert_text(nodeid, text)
        except Exception, e:
            keepnote.log_error()


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
        
    def get_node_path(self, nodeid):
        """Get node path for a nodeid"""
        
        # TODO: handle multiple parents

        visit = set([nodeid])
        path = []
        parentid = None

        try:
            while parentid != self._uniroot:
                # continue to walk up parent
                path.append(nodeid)

                self.cur.execute(u"""SELECT nodeid, parentid, basename
                                FROM NodeGraph
                                WHERE nodeid=?""", (nodeid,))
                row = self.cur.fetchone()

                # nodeid is not index
                if row is None:
                    return None

                nodeid, parentid, basename = row
                
                # parent has unexpected loop
                if parentid in visit:
                    self._on_corrupt(Exception("unexpect parent path loop"))
                    return None
                
                # walk up
                nodeid = parentid

            path.reverse()
            return path

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def get_node_filepath(self, nodeid):
        """Get node path for a nodeid"""
        
        # TODO: handle multiple parents

        visit = set([nodeid])
        path = []
        parentid = None

        try:
            while parentid != self._uniroot:
                # continue to walk up parent

                self.cur.execute(u"""SELECT nodeid, parentid, basename
                                FROM NodeGraph
                                WHERE nodeid=?""", (nodeid,))
                row = self.cur.fetchone()

                # nodeid is not index
                if row is None:
                    return None

                nodeid, parentid, basename = row
                if basename != "":
                    path.append(basename)

                # parent has unexpected loop
                if parentid in visit:
                    self._on_corrupt(Exception("unexpect parent path loop"))
                    return None
                
                # walk up
                nodeid = parentid

            path.reverse()
            return path

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def get_node(self, nodeid):
        """Get node data for a nodeid"""
        
        # TODO: handle multiple parents

        try:
            self.cur.execute(u"""SELECT nodeid, parentid, basename, mtime
                                FROM NodeGraph
                                WHERE nodeid=?""", (nodeid,))
            row = self.cur.fetchone()

            # nodeid is not index
            if row is None:
                return None
            
            return {"nodeid": row[0],
                    "parentid": row[1],
                    "basename": row[2],
                    "mtime": row[3]}
            
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise

        
    def has_node(self, nodeid):
        """Returns True if index has node"""
        self.cur.execute(u"""SELECT nodeid, parentid, basename, mtime
                             FROM NodeGraph
                             WHERE nodeid=?""", (nodeid,))
        return self.cur.fetchone() is not None


    def list_children(self, nodeid):
                
        try:
            self.cur.execute(u"""SELECT nodeid, basename
                                FROM NodeGraph
                                WHERE parentid=?""", (nodeid,))
            return list(self.cur.fetchall())
            
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def has_children(self, nodeid):
        
        try:
            self.cur.execute(u"""SELECT nodeid
                                FROM NodeGraph
                                WHERE parentid=?""", (nodeid,))
            return self.cur.fetchone() != None
            
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def search_titles(self, query):
        """Return nodeids of nodes with matching titles"""

        if "title" not in self._attrs:
            return []

        try:
            # order titles by exact matches and then alphabetically
            self.cur.execute(
                u"""SELECT nodeid, value FROM %s WHERE value LIKE ?
                           ORDER BY value != ?, value """ % 
                self._attrs["title"].get_table_name(),
                (u"%" + query + u"%", query))

            return list(self.cur.fetchall())

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def get_attr(self, nodeid, key):
        """Query indexed attribute for a node"""
        attr = self._attrs.get(key, None)
        if attr:
            return attr.get(self.cur, nodeid)
        else:
            return None


    def search_contents(self, text):

        # TODO: implement fully general fix
        # crude cleaning
        text = text.replace('"', "")

        # fallback if fts3 is not available
        if not self._has_fulltext:
            words = [x.lower() for x in text.strip().split()]
            return self._search_manual(words)
        
        cur = self.con.cursor()

        # search db with fts3
        try:
            res = cur.execute("""SELECT nodeid FROM fulltext 
                             WHERE content MATCH ?;""", (text,))
            return (row[0] for row in res)
        except:
            keepnote.log_error("SQLITE error while performing search")
            return []


    def _search_manual(self, words):
        """Recursively search nodes under node for occurrence of words"""

        keepnote.log_message("manual search")

        nodeid = self._nconn.get_rootid()
        
        stack = [nodeid]
        while len(stack) > 0:
            nodeid = stack.pop()
            
            title = self._nconn.read_node(nodeid).get("title", "").lower()
            infile = chain([title], 
                           self._nconn.read_data_as_plain_text(nodeid))

            if match_words(infile, words):
                yield nodeid
            else:
                # return frequently so that search does not block long
                yield None

            children = self._nconn._list_children_nodeids(nodeid)
            stack.extend(children)




