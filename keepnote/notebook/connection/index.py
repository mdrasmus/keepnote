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



NULL = object()

#=============================================================================


def match_words(infile, words):
    """Returns True if all of the words in list 'words' appears in the file"""

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


def read_data_as_plain_text(conn, nodeid):
    """Iterates over the lines of the data file as plain text"""
    try:
        infile = conn.open_file(
            nodeid, keepnote.notebook.PAGE_DATA_FILE, "r", codec="utf-8")
        for line in keepnote.notebook.read_data_as_plain_text(infile):
            yield line
        infile.close()
    except:
        pass


def test_fts3(cur, tmpname="fts3test"):
    """
    Returns True if fts3 extension is available
    """

    # full text table
    try:
        # test for fts3 availability
        cur.execute(u"DROP TABLE IF EXISTS %s;" % tmpname)
        cur.execute(
            "CREATE VIRTUAL TABLE %s USING fts3(col TEXT);" % tmpname)
        cur.execute("DROP TABLE %s;" % tmpname)
        return True
    except Exception, e:
        return False


#=============================================================================

class AttrIndex (object):
    """Indexing information for an attribute"""

    def __init__(self, name, type, index_value=False):
        self._name = name
        self._type = type
        self._table_name = "Attr_" + name
        self._index_name = "IdxAttr_" + name + "_nodeid"
        self._index_value = index_value
        self._index_value_name = "IdxAttr_" + name + "_value"


    def get_name(self):
        return self._name

    def get_table_name(self):
        return self._table_name

    def init(self, cur):
        """Initialize attribute index for database"""

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
        if len(values) == 0:
            return None
        else:
            return values[0]

    def set(self, cur, nodeid, value):
        """Set the information for a node in the index"""

        # insert new row
        cur.execute(u"""INSERT INTO %s VALUES (?, ?)""" % self._table_name,
                        (nodeid, value))


class NodeIndex (object):
    """
    General index for nodes and their attributes
    """

    def __init__(self, conn):
        self._nconn = conn  # notebook connection
        self._attrs = {}    # attr indexes
        self._has_fulltext = False
        self._use_fulltext = True
        self._open_node_fulltext = \
            lambda nodeid: read_data_as_plain_text(self._nconn, nodeid)


    def set_conn(self, nconn):
        """Set NoteBookConnection"""
        self._nconn = nconn


    def has_fulltext_search(self):
        return self._has_fulltext
    

    def enable_fulltext_search(self, enabled):
        self._use_fulltext = enabled


    def set_open_fulltext_func(self, func):
        self._open_node_fulltext = func
    

    #===============================
    # add/remove/get attr indexing


    def add_attr(self, attr):
        """Add indexing for a node attribute using AttrIndex"""
        self._attrs[attr.get_name()] = attr
        if self.cur:
            attr.init(self.cur)
        return attr

    
    def remove_attr(self, name):
        """Remove an AttrIndex by name"""
        del self._attrs[name]


    def get_attr_index(self, name):
        """Return AttrIndex by name"""
        return self._attrs.get(name)


    def has_attr(self, name):
        return name in self._attrs


    #=============================
    # setup/drop attr tables


    def init_attrs(self, cur):

        # full text table
        if test_fts3(cur):
            # create fulltext table if it does not already exist
            if not list(cur.execute(u"""SELECT 1 FROM sqlite_master 
                               WHERE name == 'fulltext';""")):
                cur.execute(u"""CREATE VIRTUAL TABLE 
                            fulltext USING 
                            fts3(nodeid TEXT, content TEXT,
                                 tokenize=porter);""")
            self._has_fulltext = True
        else:
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
            attr.init(cur)


    def drop_attrs(self, cur):

        cur.execute(u"DROP TABLE IF EXISTS fulltext;")
        
        # drop attribute tables
        table_names = [x for (x,) in cur.execute(
            u"""SELECT name FROM sqlite_master WHERE name LIKE 'Attr_%'""")]

        for table_name in table_names:
            cur.execute(u"""DROP TABLE %s;""" % table_name)


    #===============================
    # add/remove/get nodes from index

    def add_node_attr(self, cur, nodeid, attr, fulltext=True):

        # update attrs
        for attrindex in self._attrs.itervalues():
            attrindex.add_node(cur, nodeid, attr)

        # update fulltext
        if fulltext:
            infile = self._open_node_fulltext(nodeid)
            self._index_node_text(cur, nodeid, attr, infile)

    def remove_node_attr(self, cur, nodeid):
        
        # update attrs
        for attr in self._attrs.itervalues():
            attr.remove_node(cur, nodeid)
            
        self._remove_text(cur, nodeid)


    def get_node_attr(self, cur, nodeid, key):
        """Query indexed attribute for a node"""
        attr = self._attrs.get(key, None)
        if attr:
            return attr.get(cur, nodeid)
        else:
            return None


    #================================
    # search


    def search_node_contents(self, cur, text):

        # TODO: implement fully general fix
        # crude cleaning
        text = text.replace('"', "")

        # fallback if fts3 is not available
        if not self._has_fulltext or not self._use_fulltext:
            words = [x.lower() for x in text.strip().split()]
            return self.search_node_contents_manual(cur, words)
        
        # search db with fts3
        res = cur.execute("""SELECT nodeid FROM fulltext 
                             WHERE content MATCH ?;""", (text,))
        return (row[0] for row in res)


    def search_node_contents_manual(self, cur, words):
        """Recursively search nodes under node for occurrence of words"""

        keepnote.log_message("manual search\n")

        nodeid = self._nconn.get_rootid()
        
        stack = [nodeid]
        while len(stack) > 0:
            nodeid = stack.pop()
            
            title = self._nconn.read_node(nodeid).get("title", "").lower()
            infile = chain([title], 
                           read_data_as_plain_text(self._nconn, nodeid))

            if match_words(infile, words):
                yield nodeid
            else:
                # return frequently so that search does not block long
                yield None

            children = self._nconn._list_children_nodeids(nodeid)
            stack.extend(children)


    def search_node_titles(self, cur, query):
        """Return nodeids of nodes with matching titles"""

        # TODO: can this be generalized?
        # similar to get_node_attr(nodeid, attr)

        if not self.has_attr("title"):
            return []

        # order titles by exact matches and then alphabetically
        cur.execute(
            u"""SELECT nodeid, value FROM %s WHERE value LIKE ?
                           ORDER BY value != ?, value """ % 
            self.get_attr_index("title").get_table_name(),
            (u"%" + query + u"%", query))

        return list(cur.fetchall())


    #=================================
    # helper functions


    def _index_node_text(self, cur, nodeid, attr, infile):

        text = attr.get("title", "") + "\n" + "".join(infile)
        self._insert_text(cur, nodeid, text)


    def _insert_text(self, cur, nodeid, text):
        
        if not self._has_fulltext:
            return

        if list(cur.execute(u"SELECT 1 FROM fulltext WHERE nodeid = ?",
                            (nodeid,))):
            cur.execute(u"UPDATE fulltext SET content = ? WHERE nodeid = ?;",
                        (text, nodeid))
        else:
            cur.execute(u"INSERT INTO fulltext VALUES (?, ?);",
                        (nodeid, text))


    def _remove_text(self, cur, nodeid):
        
        if not self._has_fulltext:
            return

        cur.execute(u"DELETE FROM fulltext WHERE nodeid = ?", (nodeid,))


