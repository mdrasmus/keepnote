#!/usr/bin/env python
# demo for a database design

import time
import random
import sqlite3  as sqlite

attrs = ["title", "icon", "creation", "modification"]
index_file = "test/data/db_demo.sqlite"

#=============================================================================

def clear(con):
    for attr in attrs:
        con.execute(u"DROP TABLE IF EXISTS Attr_%s" % attr)

def init(con):
    for attr in attrs:
        con.execute(u"""CREATE TABLE IF NOT EXISTS Attr_%s
                      (nodeid INTEGER,
                       value TEXT);""" % attr)
        con.execute(u"""CREATE INDEX IF NOT EXISTS IdxAttr_%s_nodid
                           ON Attr_%s (nodeid);""" % (attr, attr))

#=============================================================================

# open database
con = sqlite.connect(index_file, isolation_level="DEFERRED",
                     check_same_thread=False)
cur = con.cursor()
clear(con)
init(con)


# populate database
nodeids = range(20000)
for attr in attrs:
    for nodeid in nodeids:
        con.execute("""INSERT INTO Attr_%s VALUES (?, ?)""" % attr,
                    (nodeid, str(random.random())))


# perform query
start = time.time()
for i in range(100):
    res = con.execute("""SELECT Attr_title.nodeid, 
                                Attr_title.value, 
                                Attr_icon.value,
                                Attr_creation.value FROM 
               Attr_title, Attr_icon, Attr_creation 
               WHERE Attr_title.nodeid == Attr_icon.nodeid AND
                     Attr_title.nodeid == Attr_creation.nodeid AND
                Attr_title.nodeid == %s""" % random.sample(nodeids, 1)[0])

    print "\n".join(map(lambda x: "\t".join(map(str, x)), res))
print time.time() - start

# close database
con.commit()
con.close()
