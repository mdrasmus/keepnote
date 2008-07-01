

import sys

sys.path.append(".")

from takenote import notebook

from sqlite3 import dbapi2 





def table_exists(cur, table):
    cur.execute("SELECT name FROM sqlite_master WHERE name == '%s';" % table)
    exists = len(cur.fetchall()) > 0
    return exists



class TakeNoteDb (object):
    def __init__(self):
        self._filename = None
        self._con = None
        self._cur = None


    def connect(self, filename):
        self._filename = filename
        self._con = dbapi2.connect(filename)
        self._cur = self._con.cursor()

    def close(self):
        self._con.commit()
        self._con.close()

    def commit(self):
        self._con.commit()

    def init_tables(self, clear=True):

        if clear and table_exists(self._cur, "Notes"):
            self.drop_tables()
        
        self._cur.execute("""CREATE TABLE Notes
            (
            nodeid INTEGER,
            path TEXT,            
            title TEXT,
            created TIMESTAMP,
            modified TIMESTAMP,
            body TEXT
            );""")


    def drop_tables(self):
        self._cur.execute("DROP TABLE Notes;")


    def index_notebook(self, notebook):

        def walk(node):
            self.index_node(node)
            for child in node.get_children():
                walk(child)
        walk(notebook)


    def index_node(self, node):
        """Index the text of a NoteBook node"""
        pass
        
if __name__ == "__main__":

    db = TakeNoteDb()
    db.connect("test.db")
    db.init_tables()
    db.close()
