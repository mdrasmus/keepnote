"""

    KeepNote
    Notebook indexing

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
import keepnote.notebook
from keepnote.notebook.connection.index import AttrIndex, NodeIndex


# index filename
INDEX_FILE = u"index.sqlite"
INDEX_VERSION = 3

#=============================================================================


# TODO: remove uniroot

class NoteBookIndex (NodeIndex):
    """Index for a NoteBook"""

    def __init__(self, conn, index_file):
        NodeIndex.__init__(self, conn)
        self._index_file = index_file
        self._uniroot = keepnote.notebook.UNIVERSAL_ROOT
        self.con = None     # sqlite connection
        self.cur = None     # sqlite cursor


        # index state/capabilities
        self._need_index = False
        self._corrupt = False
        
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
                                      isolation_level="DEFERRED",
                                      #isolation_level="IMMEDIATE",
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
            
            # init attribute indexes
            self.init_attrs(self.cur)

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
        """
        Called when database appears corrupt
        Logs error and schedules re-indexing
        """
        self._corrupt = True
        self._need_index = True

        # display error
        keepnote.log_error(error, tracebk)

        # TODO: reload database?


    def _drop_tables(self):
        """drop NodeGraph tables"""
        self.con.execute(u"DROP TABLE IF EXISTS NodeGraph")
        self.con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphNodeid")
        self.con.execute(u"DROP INDEX IF EXISTS IdxNodeGraphParentid")
        self.drop_attrs(self.cur)
        

    
    def index_needed(self):
        """Returns True if indexing is needed"""
        return self._need_index


    def set_index_needed(self, val=True):
        """Returns True if re-indexing is needed"""
        self._need_index = val
    


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
        # simply by walking through the tree, all nodes will index themselves
        for nodeid in preorder(conn, rootid):
            yield nodeid

        # record index complete
        self._need_index = False


    def compact(self):
        """
        Try to compact the index by reclaiming space
        """
        keepnote.log_message("compacting index '%s'\n" % self._index_file)
        self.con.execute("VACUUM;")
        self.con.comment()


    def get_node_mtime(self, nodeid):
        """Get the last indexed mtime for a node"""
        
        self.cur.execute(u"""SELECT mtime FROM NodeGraph
                             WHERE nodeid=?""", (nodeid,))
        row = self.cur.fetchone()
        if row:
            return row[0]
        else:
            return 0.0

    def set_node_mtime(self, nodeid, mtime=None, commit=True):
        """Set the last indexed mtime for a node"""

        if mtime is None:
            mtime = time.time()

        self.cur.execute("""UPDATE NodeGraph SET mtime = ? WHERE nodeid = ?;""",
                         (mtime, nodeid))
        if commit:
            self.con.commit()


    def get_mtime(self):
        """Get last modification time of the index"""
        return os.stat(self._index_file).st_mtime

    
    def add_node(self, nodeid, parentid, basename, attr, mtime, commit=True):
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

            self.add_node_attr(self.cur, nodeid, attr)
            
            if commit:
                self.con.commit()

        except Exception, e:
            keepnote.log_error("error index node %s '%s'" % 
                               (nodeid, attr.get("title", "")))
            self._on_corrupt(e, sys.exc_info()[2])


    def remove_node(self, nodeid, commit=True):
        """Remove node from index using nodeid"""

        if self.con is None:
            return
        
        try:
            # delete node
            self.cur.execute(u"DELETE FROM NodeGraph WHERE nodeid=?", (nodeid,))

            self.remove_node_attr(self.cur, nodeid)

            if commit:
                self.con.commit()

        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])



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


    def get_attr(self, nodeid, attr):
        """Return a nodes's attribute value"""
        return self.get_node_attr(self.cur, nodeid, attr)

        
    def has_node(self, nodeid):
        """Returns True if index has node"""
        self.cur.execute(u"""SELECT nodeid, parentid, basename, mtime
                             FROM NodeGraph
                             WHERE nodeid=?""", (nodeid,))
        return self.cur.fetchone() is not None


    def list_children(self, nodeid):
        """List children indexed for node"""

        try:
            self.cur.execute(u"""SELECT nodeid, basename
                                FROM NodeGraph
                                WHERE parentid=?""", (nodeid,))
            return list(self.cur.fetchall())
            
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def has_children(self, nodeid):
        """Returns True if node has children"""
        
        try:
            self.cur.execute(u"""SELECT nodeid
                                FROM NodeGraph
                                WHERE parentid=?""", (nodeid,))
            return self.cur.fetchone() != None
            
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def search_titles(self, title):
        """Search node titles"""

        try:
            return self.search_node_titles(self.cur, title)
        except sqlite.DatabaseError, e:
            self._on_corrupt(e, sys.exc_info()[2])
            raise


    def search_contents(self, text):
        """Search node contents"""

        cur = self.con.cursor()
        try:
            for res in self.search_node_contents(cur, text):
                yield res            
        except:
            keepnote.log_error("SQLITE error while performing search")
        finally:
            cur.close()



