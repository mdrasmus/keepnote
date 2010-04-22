"""

    KeepNote
    Search features for notebook

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


import sys


from keepnote import notebook as notebooklib
from keepnote.notebook import NoteBook

#import sqlite3
#from sqlite3 import dbapi2 
#print sqlite3.sqlite_version


def make_uuid():
    """Make a random Univerally Unique ID"""
    return str(uuid.uuid4())


def table_exists(cur, table):
    cur.execute("SELECT name FROM sqlite_master WHERE name == '%s';" % table)
    exists = len(cur.fetchall()) > 0
    return exists


'''
        self.cur.execute("""
            CREATE TABLE Genes (
                geneid CHAR(20) PRIMARY KEY,
                common_name CHAR(20),
                species CHAR(20),
                chrom CHAR(20),
                start INTEGER,
                end INTEGER,
                strand INTEGER,        
                description VARCHAR(1000),
                famid CHAR(20)
            );""")

        self.cur.execute("""CREATE UNIQUE INDEX IndexGenes
                            ON Genes (geneid);""")
        self.cur.execute("""CREATE INDEX Index2Genes
                            ON Genes (famid);""")

INSERT INTO Genes VALUES 
("%s", "%s", "%s", "%s", %d, %d, %d, "%s", "%s");

'''




class KeepNoteDb (object):
    def __init__(self):
        self._filename = None
        self._con = None
        self._cur = None


    def connect(self, filename):
        self._filename = filename
        self._con = dbapi2.connect(filename) #, isolation_level=None)
        self._cur = self._con.cursor()

        #self._cur.execute("SELECT load_extension('fts2.dll');")

    def close(self):
        self._con.commit()
        self._con.close()

    def commit(self):
        self._con.commit()

    def init_tables(self, clear=True):

        if clear:
            self.drop_tables()
        
        self._cur.execute("""CREATE TABLE Nodes
            (
            nodeid INTEGER,
            uuid TEXT,
            parentid INTEGER,
            created INTEGER,
            modified INTEGER
            );""")

        self._cur.execute("""
            CREATE VIRTUAL TABLE NodeSearch USING
            fts3(title TEXT,
                 body TEXT,
                 tokenize porter);
            """)


    def drop_tables(self):
        
        if table_exists(self._cur, "Nodes"):
            self._cur.execute("DROP TABLE Nodes;")
        if table_exists(self._cur, "NodeSearch"):
            self._cur.execute("DROP TABLE NodeSearch;")


    def index_notebook(self, notebook):

        def walk(node):
            self.index_node(node)
            for child in node.get_children():
                walk(child)
        walk(notebook)


    def index_node(self, node):
        """Index the text of a NoteBook node"""

        # TODO:
        # need to strip HTML from note
        # need to properly encode and escape special chars
        
        if node.is_page():
            body = "hello" #file(node.get_data_file()).read()
        else:
            body = ""
            
        
        self._cur.execute('INSERT INTO Nodes VALUES (%d,"%s",%d,%d,%d);' %
                  (0, "", 0,
                   node.get_attr("created_time", 0),
                   node.get_attr("modified_time", 0)))


def match_words(node, words):
    """Returns True if all of the words in list 'words' appears in the
       node title or data file"""

    # check title
    title = node.get_title().lower()

    matches = dict.fromkeys(words, False)

    for word in words:
        if word in title:
            matches[word] = True            

    if node.get_attr("content_type") == notebooklib.CONTENT_TYPE_PAGE:
        for line in node.read_data_as_plain_text():
            line = line.lower()
            for word in words:
                if word in line:
                    matches[word] = True

    # return True if all words are found (AND)
    for val in matches.itervalues():
        if not val:
            return False
    
    return True


def search_manual(node, words):
    """Recursively search nodes under node for occurrence of words"""
    
    nodes = []
    words = [x.lower() for x in words]

    stack = [[node, 0]]
    while len(stack) > 0:
        node2, i = stack[-1]
        
        if i == 0 and match_words(node2, words):
            yield node2
        else:
            # return frequently so that search does not block long
            yield None

        if i >= len(node2.get_children()):
            stack.pop()
        else:
            stack[-1][1] += 1
            stack.append([node2.get_children()[i], 0])
        

    
        
if __name__ == "__main__":
    db = KeepNoteDb()
    db.connect("test.db")
    db.init_tables()
    db.index_notebook(notebook)

    db._cur.execute("SELECT * from Nodes;")

    for row in list(db._cur)[:10]:
        print row
    
    db.close()
