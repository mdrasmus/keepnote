
import sys
import os
import httplib
import urllib
import urlparse
import thread
import select
import BaseHTTPServer
from StringIO import StringIO

from keepnote import notebook
from keepnote.notebook.connection import NoteBookConnection
from keepnote.notebook.connection.fs import NoteBookConnectionFS
from keepnote.notebook.connection.http import \
    NoteBookConnectionHttp, NoteBookHttpServer
from keepnote import plist


#=============================================================================


# connect to notebook on disk
conn = NoteBookConnectionFS()
conn.connect(u"test/data/notes")

# start server in another thread
host = "localhost"
port = 8000
url = "http://%s:%d/" % (host, port)
server = NoteBookHttpServer(conn, port=port)
thread.start_new_thread(server.serve_forever, ())

#=============================================================================

conn2 = NoteBookConnectionHttp()
conn2.connect(url)

# read node
rootid = conn.get_rootid()
print "READ:", conn2.read_node(rootid)
print "READ:", conn2.read_node("aaa%2Fbbb%20ccc/ddd")


# create a new node
nodeid = notebook.new_nodeid()
attr = {"nodeid": nodeid, "parentid": rootid, "title": "A new node"}
conn2.create_node(nodeid, attr)
attr = conn2.read_node(nodeid)
print "NEW NODE:", attr

# update node
attr["new_attr"] = 7
print "SEND", attr
conn2.update_node(nodeid, attr)
print "UPDATE NODE:", conn2.read_node(nodeid)["new_attr"]

# put file
stream = conn2.open_file(nodeid, "myfile", "w")
stream.write("hello")
stream.close()

stream = conn2.open_file(nodeid, "myfile")
print stream.read()
stream.close()

stream = conn2.open_file(nodeid, "myfile", "a")
stream.write("_hello")
stream.close()

print "LIST", conn2.list_files(nodeid, "/")

stream = conn2.open_file(nodeid, "myfile")
print stream.read()
stream.close()

conn2.delete_file(nodeid, "myfile")

conn2.index(["index_attr", "title", "TEXT"])
print "QUERY", conn2.index(["search_fulltext", "a"])[:10]
print "QUERY", conn2.search_node_titles("new")[:3]
print "QUERY", conn2.get_node_path_by_id(nodeid)

# delete node
conn2.delete_node(nodeid)

# save
conn2.save()



if 0:
    def walk(conn, nodeid):
        attr = conn.read_node(nodeid)
        if not attr:
            return
        print attr.get("title", "NONE")
        for childid in attr.get("childrenids", ()):
            walk(conn, childid)
    walk(conn2, rootid)


# close notebook
conn.close()
conn2.close()

