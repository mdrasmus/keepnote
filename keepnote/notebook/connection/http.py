"""

    KeepNote    
    
    Serving/accessing KeepNote notebooks over HTTP 

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
import sys
import os
import httplib
import urllib
import urlparse
import thread
import select
import BaseHTTPServer
from collections import defaultdict

# keepnote imports
import keepnote
from keepnote import notebook
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import NoteBookConnection
from keepnote.notebook.connection.fs import NoteBookConnectionFS
from keepnote import plist


XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""

#=============================================================================
# Node URL scheme

def determine_path_prefix(path, prefixes=()):
    """
    Prefixes must end with a slash
    """

    for prefix in prefixes:
        if path.startswith(prefix):
            return prefix

    return ""

def parse_node_path(path, prefixes=("/")):

    # skip over prefix
    prefix = determine_path_prefix(path, prefixes)
    path = path[len(prefix):]
    
    # find end of nodeid (ends with an optional slash)
    i = path.find("/")
    if i != -1:
        nodeid = path[:i]
        filename = urllib.unquote(path[i+1:])
        if filename == "":
            filename = "/"
    else:
        nodeid = path
        filename = None

    return urllib.unquote(nodeid), filename


def format_node_path(prefix, nodeid="", filename=None):
    """
    prefix must end with "/"
    """
    nodeid = nodeid.replace("/", "%2F")
    if filename is not None:
        return urllib.quote("%s%s/%s" % (prefix, nodeid, filename))
    else:
        return urllib.quote(prefix + nodeid)


def format_node_url(host, prefix, nodeid, filename=None, port=80):
    portstr = ":" + str(port) if port != 80 else ""
    return "http://%s%s/%s" % (host, portstr, 
                               format_node_path(prefix, nodeid, filename))





#=============================================================================
# Notebook HTTP Server


def write_tree(out, conn):
    
    def walk(conn, nodeid):
        attr = conn.read_node(nodeid)

        # TODO: needs escape
        if attr.get("content_type", "") == "text/xhtml+xml":
            url = format_node_path("", nodeid, "page.html")
        elif "payload_filename" in attr:
            url = format_node_path("", nodeid, 
                                   attr["payload_filename"])
        else:
            url = format_node_path("", nodeid, "")
        out.write(
            "<a href='%s'>%s</a>" % (
                url, attr.get("title", "page").encode("utf8")))
        out.write("<ul>")

        for childid in attr.get("childrenids", ()):
            out.write("<li>")
            walk(conn, childid)
            out.write("</li>")

        out.write("</ul>")
    walk(conn, conn.get_rootid())



class HttpHandler (BaseHTTPServer.BaseHTTPRequestHandler):
    """
    HTTP handler for NoteBook Server
    """

    def parse_path(self, path=None):
        """
        Parse a url path into (urlparts, nodeid, filename)
        """

        if path is None:
            path = self.path
        parts = urlparse.urlsplit(path)
        nodeid, filename = parse_node_path(parts.path, self.server.prefixes)
        return parts, nodeid, filename


    def do_GET(self):
        """
        GET action handler
        """
        parts, nodeid, filename = self.parse_path()
        
        try:
            if nodeid == "":
                if parts.query == "all":
                    self.send_response(httplib.OK)
                    self.send_header("content_type", "text/html")
                    self.end_headers()

                    self.wfile.write("<html><body>")
                    write_tree(self.wfile, self.server.conn)
                    self.wfile.write("</body></html>")
                    return


                # get rootid
                rootid = self.server.conn.get_rootid()

                self.send_response(httplib.OK)
                self.send_header("content_type", "text/xml")
                self.end_headers()
                self.wfile.write(XML_HEADER)
                self.wfile.write(plist.dumps(rootid))

            elif filename is None:
                # return node attr
                attr = self.server.conn.read_node(nodeid)

                self.send_response(httplib.OK)
                self.send_header("content_type", "text/xml")
                self.end_headers()

                if attr.get("parentids") == [None]:
                    del attr["parentids"]
                self.wfile.write(XML_HEADER)
                self.wfile.write(plist.dumps(attr).encode("utf8"))

            elif filename.endswith("/"):
                # list directory
                files = list(self.server.conn.list_dir(nodeid, filename))
                
                self.send_response(httplib.OK)
                self.send_header("content_type", "application/octet-stream")
                self.end_headers()
                self.wfile.write(XML_HEADER)
                self.wfile.write(plist.dumps(files).encode("utf8"))
                
            else:
                # return node file
                stream = self.server.conn.open_file(nodeid, filename)
                self.send_response(httplib.OK)
                self.send_header("content_type", "application/octet-stream")
                self.end_headers()
                self.wfile.write(stream.read())
                stream.close()

        except Exception, e:
            keepnote.log_error()
            self.send_error(404, "node not found " + str(e))


    def do_PUT(self):
        """
        PUT action handler
        """

        parts, nodeid, filename = self.parse_path()
        
        # read attr
        content_len = int(self.headers.get("Content-length", 0))
        
        try:
            if filename is None:
                # create node
                data = self.rfile.read(content_len)
                attr = plist.loads(data)
                attr["nodeid"] = nodeid
                self.server.conn.create_node(nodeid, attr)
                
            elif filename.endswith("/"):
                # create dir
                self.server.conn.create_dir(nodeid, filename)

            else:
                # create file
                data = self.rfile.read(content_len)
                stream = self.server.conn.open_file(nodeid, filename, "w")
                stream.write(data)
                stream.close()

            self.send_response(httplib.OK)
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
        except Exception, e:
            # FIX response
            keepnote.log_error()
            self.send_error(httplib.NOT_FOUND, "cannot create node: " + str(e))


    def do_POST(self):

        parts, nodeid, filename = self.parse_path()

        content_len = int(self.headers.get("Content-length", 0))
        data = self.rfile.read(content_len)

        try:
            if nodeid == "":
                # pure command                
                if parts.query == "save":
                    self.server.conn.save()
                    
                elif parts.query == "index":
                    query = plist.loads(data)
                    res = self.server.conn.index(query)
                    if hasattr(res, "next"):
                        res = list(res)
                    self.send_response(httplib.OK)
                    self.send_header("content_type", "text/xml")
                    self.end_headers()
                    self.wfile.write(XML_HEADER)
                    self.wfile.write(plist.dumps(res).encode("utf8"))
                    return 

            elif not filename:
                # update node
                attr = plist.loads(data)
                attr["nodeid"] = nodeid
                self.server.conn.update_node(nodeid, attr)

            else:
                # write file
                params = urlparse.parse_qs(parts.query)
                if params.get("mode", "r") == ["a"]:
                    stream = self.server.conn.open_file(nodeid, filename, "a")
                else:
                    stream = self.server.conn.open_file(nodeid, filename, "w")
                stream.write(data)
                stream.close()

            self.send_response(httplib.OK)
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
            
        except Exception, e:
            # FIX response
            keepnote.log_error()
            self.send_error(httplib.NOT_FOUND, "cannot create node: " + str(e))


    def do_DELETE(self):

        parts, nodeid, filename = self.parse_path()
        
        try:
            if not filename:
                # delete node
                self.server.conn.delete_node(nodeid)
            else:
                # delete file/dir
                self.server.conn.delete_file(nodeid, filename)

            self.send_response(httplib.OK)
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
        except Exception, e:
            # TDOD: fix response
            keepnote.log_error()
            self.send_error(httplib.NOT_FOUND, "cannot delete node: " + str(e))


    def do_HEAD(self):
        
        parts, nodeid, filename = self.parse_path()
        
        try:
            if not filename:
                # exists node
                exists = self.server.conn.has_node(nodeid)
            else:
                # exists file/dir
                exists = self.server.conn.has_file(nodeid, filename)

            if exists:
                self.send_response(httplib.OK)
            else:
                self.send_response(httplib.NOT_FOUND)
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
        except Exception, e:
            # TODO: fix response
            keepnote.log_error()
            self.send_error(httplib.NOT_FOUND, "cannot find node: " + str(e))


    #def log_message(self, format, *args):
        # suppress logging
    #    pass



class NoteBookHttpServer (BaseHTTPServer.HTTPServer):

    def __init__(self, conn, prefix="/", host="", port=8000):
        self.conn = conn
        self.prefixes = [prefix]
        self.server_address = (host, port)
        BaseHTTPServer.HTTPServer.__init__(self, self.server_address, 
                                           HttpHandler)



class NoteBookConnectionHttp (NoteBookConnection):

    def __init__(self):
        self._netloc = ""
        self._prefix = "/"
        self._conn = None
        self._title_cache = NodeTitleCache()
        
        
    def connect(self, url):
        
        parts = urlparse.urlsplit(url)

        self._netloc = parts.netloc
        self._prefix = parts.path
        self._conn =  httplib.HTTPConnection(self._netloc)
        self._title_cache.clear()
        #self._conn.set_debuglevel(1)

    def close(self):
        self._conn.close()

    def save(self):

        # POST http://host/prefix/?save
        
        self._request('POST', format_node_path(self._prefix) + "?save")
        result = self._conn.getresponse()
        
        pass


    def _request(self, action, url, body=None, headers={}):
        try:
            return self._conn.request(action, url, body, headers)
        except httplib.ImproperConnectionState:
            # restart connection
            self._conn =  httplib.HTTPConnection(self._netloc)
            return self._request(action, url, body, headers)


    #===========================================
    
    
    def create_node(self, nodeid, attr):
        
        body_content = plist.dumps(attr).encode("utf8")
        self._request('PUT', format_node_path(self._prefix, nodeid), 
                      body_content)
        result = self._conn.getresponse()
        if result.status != httplib.OK:
            raise connlib.ConnectionError(
                "unexpected error '%s'" % str(e), e)

        self._title_cache.update_attr(attr)


    def read_node(self, nodeid):

        self._request('GET', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        if result.status == httplib.OK:
            try:
                attr = plist.load(result)
                self._title_cache.update_attr(attr)
                return attr
            except Exception, e:
                raise connlib.ConnectionError(
                    "unexpected error '%s'" % str(e), e)
        else:
            raise connlib.UnknownNode(nodeid)


    def update_node(self, nodeid, attr):
        
        body_content = plist.dumps(attr).encode("utf8")
        self._request('POST', format_node_path(self._prefix, nodeid), 
                      body_content)
        result = self._conn.getresponse()
        if result.status != httplib.OK:
            raise connlib.ConnectionError()
        self._title_cache.update_attr(attr)

        
    def delete_node(self, nodeid):
        
        self._request('DELETE', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        if result.status != httplib.OK:
            raise connlib.ConnectionError()
        self._title_cache.remove(nodeid)


    def has_node(self, nodeid):
        """Returns True if node exists"""

        # HEAD nodeid/filename
        self._request('HEAD', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        return result.status == httplib.OK


    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        # GET /
        self._request('GET', format_node_path(self._prefix))
        result = self._conn.getresponse()
        if result.status == httplib.OK:
            return plist.load(result)
        else:
            raise connlib.UnknownNode()
        


    #===============
    # file API

    def open_file(self, nodeid, filename, mode="r", codec=None):
        """Open a file contained within a node"""

        # read: GET nodeid/file
        # write: POST nodeid/file
        # append: POST nodeid/file?mode=a

        class HttpFile (object):
            def __init__(self, codec=None):
                self.data = []
                self.codec = codec

            def write(self, data):
                if codec:
                    data = data.encode(codec)
                self.data.append(data)


        if mode == "r":
            self._request(
                'GET', format_node_path(self._prefix, nodeid, filename))
            result = self._conn.getresponse()
            if result.status == httplib.OK:
                return result
            else:
                raise connlib.FileError()

        elif mode == "w":
            stream = HttpFile(codec)
            def on_close():
                body_content = "".join(stream.data)
                self._request(
                    'POST', format_node_path(self._prefix, nodeid, filename),
                    body_content)
                result = self._conn.getresponse()
            stream.close = on_close
            return stream
          
        elif mode == "a":
            stream = HttpFile(codec)
            def on_close():
                body_content = "".join(stream.data)
                self._request(
                    'POST', format_node_path(self._prefix, nodeid, filename)
                    + "?mode=a", 
                body_content)
                result = self._conn.getresponse()
            stream.close = on_close
            return stream
        
        else:
            raise connlib.FileError("unknown mode '%s'" % mode)
        

    def delete_file(self, nodeid, filename):
        """Open a file contained within a node"""

        # DELETE nodeid/file
        self._request(
            'DELETE', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        if result.status != httplib.OK:
            raise connlib.FileError()

    def create_dir(self, nodeid, filename):

        # PUT nodeid/dir/
        if not filename.endswith("/"):
            filename += "/"
        self._request(
            'PUT', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        if result.status != httplib.OK:
            raise connlib.FileError()

    def list_dir(self, nodeid, filename="/"):
        """
        List data files in node
        """

        # GET nodeid/dir/
        if not filename.endswith("/"):
            filename += "/"
        self._request(
            'GET', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        if result.status == httplib.OK:
            try:
                return plist.load(result)
            except Exception, e:
                raise connlib.ConnectionError(
                    "unexpected response '%s'" % str(e), e)
        else:
            raise connlib.FileError("cannot list node")
        
    
    def has_file(self, nodeid, filename):

        # HEAD nodeid/filename
        self._request(
            'HEAD', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        return result.status == httplib.OK


    #---------------------------------
    # indexing/querying

    def index_raw(self, query):

        # POST /?index
        # query plist encoded
        body_content = plist.dumps(query).encode("utf8")
        self._request(
            'POST', format_node_path(self._prefix) + "?index", body_content)
        result = self._conn.getresponse()
        if result.status == httplib.OK:
            try:
                return plist.load(result)
            except Exception, e:
                raise connlib.ConnectionError(
                    "unexpected response '%s'" % str(e), e)


    def index(self, query):
        
        if len(query) > 2 and query[:2] == ["search", "title"]:
            if not self._title_cache.is_complete():
                #print "full index"
                result = self.index_raw(["search", "title", "%"])
                for nodeid, title in result:
                    self._title_cache.add(nodeid, title)
                self._title_cache.set_complete()

            #print len(self._title_cache._titles), query
            return list(self._title_cache.get(query[2]))

        elif len(query) == 3 and query[0] == "get_attr" and query[2] == "icon":
            # HACK: fetching icons is too slow right now
            return None
        
        else:
            return self.index_raw(query)


    def get_node_path(self, nodeid):
        
        #if nodeid == self.get_rootid():
        #    nodeid == ""
        #return format_node_path(self._prefix, nodeid)

        return format_node_url(self._netloc, self._prefix, nodeid)


    def get_file(self, nodeid, filename):

        return format_node_url(self._netloc, self._prefix, nodeid, filename)



class NodeTitleCache (object):
    def __init__(self):
        self._titles = defaultdict(lambda:set())
        self._nodeids = {}
        self._complete = False

    def is_complete(self):
        return self._complete
    

    def set_complete(self, val=True):
        self._complete = val
                     

    def update_attr(self, attr):
        nodeid = attr.get("nodeid", None)
        title = attr.get("title", None)

        # do nothing if nodeid is not present
        if nodeid is None:
            return

        # if nodeid is in cache, remove it
        self.remove(nodeid)

        # if title is not present, do not cache anything
        if title is None:
            return

        self.add(nodeid, title)


    def remove_attr(self, attr):

        nodeid = attr.get("nodeid", None)
        
        # do nothing if nodeid is not present
        if nodeid is None:
            return
        
        self.remove(nodeid)


    def add(self, nodeid, title):
        self._titles[title.lower()].add(nodeid)
        self._nodeids[nodeid] = title


    def remove(self, nodeid):
        
        # if nodeid is in cache, remove it
        if nodeid in self._nodeids:
            try:
                old_title = self._nodeids[nodeid]
                self._titles[old_title.lower()].remove(nodeid)
                del self._nodeids[nodeid]
            except:
                pass

        
    def get(self, query):
        query = query.lower()
        for title in self._titles.iterkeys():
            if query in title:
                for nodeid in self._titles[title]:
                    yield (nodeid, self._nodeids[nodeid])


    def clear(self):
        self._titles.clear()
        self._nodeids.clear()
        self._complete = False
