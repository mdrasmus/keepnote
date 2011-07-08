"""

    KeepNote    
    
    Serving/accessing KeepNote notebooks over HTTP 

"""

#
#  KeepNote
#  Copyright (c) 2008-2011 Matt Rasmussen
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
import os
import httplib
import urllib
import urlparse
import thread
import select
import BaseHTTPServer

from keepnote import notebook
from keepnote.notebook.connection import NoteBookConnection
from keepnote.notebook.connection.fs import NoteBookConnectionFS
from keepnote import plist


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
        filename = path[i+1:]
    else:
        nodeid = path
        filename = None

    return nodeid, filename


def format_node_path(prefix, nodeid="", filename=None):
    """
    prefix must end with "/"
    """
    nodeid = nodeid.replace("/", "%2F")
    if filename is not None:
        return "%s%s/%s" % (prefix, nodeid, filename)
    else:
        return prefix + nodeid


def format_node_url(host, prefix, nodeid, filename=None, port=80):
    portstr = ":" + str(port) if port != 80 else ""
    return "http://%s%s/%s" % (host, portstr, 
                               format_node_path(prefix, nodeid, filename))





#=============================================================================
# Notebook HTTP Server

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
            if filename is None:
                # return node attr
                attr = self.server.conn.read_node(nodeid)

                self.send_response(200)
                self.send_header("content_type", "text/plain")
                self.end_headers()

                if attr.get("parentids") == [None]:
                    del attr["parentids"]
                self.wfile.write(plist.dumps(attr))

            elif filename.endswith("/"):
                # list directory
                files = list(self.server.conn.list_files(nodeid, filename))
                
                self.send_response(200)
                self.send_header("content_type", "text/plain")
                self.end_headers()
                self.wfile.write(plist.dumps(files))
                
            else:
                # return node file
                stream = self.server.conn.open_file(nodeid, filename)
                self.send_response(200)
                self.send_header("content_type", "text/plain")
                self.end_headers()
                self.wfile.write(stream.read())
                stream.close()

        except Exception, e:
            self.send_error(404, "node not found " + str(e))


    def do_PUT(self):
        """
        PUT action handler
        """

        parts, nodeid, filename = self.parse_path()
        
        # read attr
        content_len = int(self.headers.get("Content-length"))
        
        try:
            if filename is None:
                # create node
                data = self.rfile.read(content_len)
                attr = plist.loads(data)
                attr["nodeid"] = nodeid
                self.server.conn.create_node(nodeid, attr)
                
            elif filename.endwith("/"):
                # create dir
                self.serve.conn.create_dir(nodeid, filename)

            else:
                # create file
                data = self.rfile.read(content_len)
                stream = self.server.conn.open_file(nodeid, filename, "w")
                stream.write(data)
                stream.close()

            self.send_response(200) # ok
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
        except Exception, e:
            # FIX response
            self.send_error(404, "cannot create node: " + str(e))


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
                    self.send_response(200) # ok
                    self.send_header("content_type", "text/plain")
                    self.end_headers()
                    self.wfile.write(plist.dumps(res))
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

            self.send_response(200) # ok
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
            
        except Exception, e:
            # FIX response
            self.send_error(404, "cannot create node: " + str(e))


    def do_DELETE(self):

        parts, nodeid, filename = self.parse_path()
        
        try:
            if not filename:
                # delete node
                self.server.conn.delete_node(nodeid)
            else:
                # delete file/dir
                self.server.conn.delete_file(nodeid, filename)

            self.send_response(202)
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
        except Exception, e:
            # TDOD: fix response
            self.send_error(404, "cannot delete node: " + str(e))


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
                self.send_response(200)
            else:
                self.send_response(404)
            self.send_header("content_type", "text/plain")
            self.end_headers()
            
        except Exception, e:
            # TDOD: fix response
            self.send_error(404, "cannot delete node: " + str(e))


    def log_message(self, format, *args):
        # suppress logging
        pass



class NoteBookHttpServer (BaseHTTPServer.HTTPServer):

    def __init__(self, conn, prefix="/", port=8000):
        self.conn = conn
        self.prefixes = [prefix]
        self.server_address = ('', port)
        BaseHTTPServer.HTTPServer.__init__(self, self.server_address, 
                                           HttpHandler)



class NoteBookConnectionHttp (NoteBookConnection):

    def __init__(self):
        self._netloc = ""
        self._prefix = "/"
        self._conn = None
        
    def connect(self, url):
        
        parts = urlparse.urlsplit(url)

        self._netloc = parts.netloc
        self._prefix = parts.path
        self._conn =  httplib.HTTPConnection(self._netloc)
        #self._conn.set_debuglevel(1)

    def close(self):
        self._conn.close()

    def save(self):

        # POST http://host/prefix/?save
        
        self._conn.request('POST', format_node_path(self._prefix) + "?save")
        result = self._conn.getresponse()
        
        pass


    #===========================================
    
    
    def create_node(self, nodeid, attr):
        
        body_content = plist.dumps(attr) + "\n"
        self._conn.request('PUT', format_node_path(self._prefix, nodeid), 
                           body_content)
        result = self._conn.getresponse()


    def read_node(self, nodeid):

        self._conn.request('GET', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        if result.status == 200:
            try:
                return plist.load(result)
            except:
                attr = None

        return None


    def update_node(self, nodeid, attr):
        
        body_content = plist.dumps(attr) + "\n"
        self._conn.request('POST', format_node_path(self._prefix, nodeid), 
                           body_content)
        result = self._conn.getresponse()

        
    def delete_node(self, nodeid):
        
        self._conn.request('DELETE', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()


    def has_node(self, nodeid):
        """Returns True if node exists"""

        # HEAD nodeid/filename
        self._conn.request(
            'HEAD', format_node_path(self._prefix, nodeid))
        result = self._conn.getresponse()
        return result.status == 200

    # TODO: can this be simplified with a search query?
    def get_rootid(self):
        """Returns nodeid of notebook root node"""
        pass


    #===============
    # file API

    def open_file(self, nodeid, filename, mode="r", codec=None):
        """Open a file contained within a node"""

        # read: GET nodeid/file
        # write: POST nodeid/file
        # append: POST nodeid/file?mode=a

        class HttpFile (object):
            def __init__(self):
                self.data = []

            def write(self, data):
                self.data.append(data)


        if mode == "r":
            self._conn.request(
                'GET', format_node_path(self._prefix, nodeid, filename))
            result = self._conn.getresponse()
            return result

        elif mode == "w":
            stream = HttpFile()
            def on_close():
                body_content = "".join(stream.data)
                self._conn.request(
                    'POST', format_node_path(self._prefix, nodeid, filename),
                    body_content)
                result = self._conn.getresponse()
            stream.close = on_close
            return stream
          
        elif mode == "a":
            stream = HttpFile()
            def on_close():
                body_content = "".join(stream.data)
                self._conn.request(
                    'POST', format_node_path(self._prefix, nodeid, filename)
                    + "?mode=a", 
                body_content)
                result = self._conn.getresponse()
            stream.close = on_close
            return stream
        
        else:
            raise Exception("unknown mode '%s'" % mode)
        

    def delete_file(self, nodeid, filename):
        """Open a file contained within a node"""

        # DELETE nodeid/file
        self._conn.request(
            'DELETE', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()

    def create_dir(self, nodeid, filename):

        # PUT nodeid/dir/
        if not filename.endswith("/"):
            filename += "/"
        self._conn.request(
            'PUT', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()

    def list_files(self, nodeid, filename="/"):
        """
        List data files in node
        """

        # GET nodeid/dir/
        if not filename.endswith("/"):
            filename += "/"
        self._conn.request(
            'GET', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        if result.status == 200:
            try:
                return plist.load(result)
            except:
                attr = None
        else:
            raise FileError("cannot list node")
        
    
    def has_file(self, nodeid, filename):

        # HEAD nodeid/filename
        self._conn.request(
            'HEAD', format_node_path(self._prefix, nodeid, filename))
        result = self._conn.getresponse()
        return result.status == 200


    #---------------------------------
    # indexing/querying

    def index(self, query):

        # POST /?index
        # query plist encoded
        body_content = plist.dumps(query)
        self._conn.request(
            'POST', format_node_path(self._prefix) + "?index", body_content)
        result = self._conn.getresponse()
        if result.status == 200:
            try:
                return plist.load(result)
            except:
                return None


