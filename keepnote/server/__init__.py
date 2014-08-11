"""

    KeepNote

    Serving KeepNote notebooks over HTTP

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
import BaseHTTPServer
from collections import defaultdict
from cStringIO import StringIO
import httplib
import json
import mimetypes
import os
import urllib
import urlparse

# bottle imports
from . import bottle
from .bottle import Bottle
from .bottle import abort
from .bottle import get
from .bottle import request
from .bottle import response
from .bottle import static_file
from .bottle import template

# keepnote imports
import keepnote
import keepnote.notebook.connection as connlib
from keepnote.notebook.connection import NoteBookConnection
from keepnote import plist


XML_HEADER = u"""\
<?xml version="1.0" encoding="UTF-8"?>
"""

# Server directories.
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')


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


def parse_node_path(path, prefixes=("/",)):

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


class NoteBookHttpServer ():

    def __init__(self, conn, host="", port=8000):
        self.conn = conn
        self.host = host
        self.port = port
        self.notebook_prefixes = ['notebook/']

        # Setup web app.
        self.app = Bottle()
        self.app.route('/', 'GET',callback=self.home_view)
        self.app.route('/static/<filename:re:.*>',
                       callback=self.static_file_view)
        self.app.route('/notebook/<path:re:.*>', 'GET',
                       callback=self.notebook_view)

    def serve_forever(self):
        """Run server."""
        self.app.run(host=self.host, port=self.port, debug=True, reloader=True)

    def shutdown(self):
        """Shutdown server."""
        pass

    def parse_path(self, path):
        """
        Parse a url path into (urlparts, nodeid, filename)
        """
        parts = urlparse.urlsplit(path)
        nodeid, filename = parse_node_path(parts.path, self.notebook_prefixes)
        return parts, nodeid, filename

    def plist_response(self, data):
        response.content_type = 'text/xml'
        return XML_HEADER + plist.dumps(data).encode('utf8')

    def json_response(self, data):
        response.content_type = 'application/json'
        return json.dumps(data).encode('utf8')

    def home_view(self):
        """Homepage of notebook webapp."""
        context = {}
        return template(TEMPLATES_DIR + '/home.html', context)

    def notebook_view(self, path):
        """Notebook data view."""
        parts, nodeid, filename = self.parse_path(path)

        try:

            if nodeid == '':
                if 'all' in request.GET:
                    response.content_type = 'text/html'

                    body = StringIO()
                    body.write("<html><body>")
                    write_tree(body, self.conn)
                    body.write("</body></html>")
                    return body.getvalue()

                # get rootid
                rootid = self.conn.get_rootid()
                return self.json_response(rootid)

            elif filename is None:
                # return node attr
                attr = self.conn.read_node(nodeid)

                response.content_type = 'text/xml'

                if attr.get("parentids") == [None]:
                    del attr["parentids"]

                return self.json_response(attr)

            elif filename.endswith("/"):
                # list directory
                files = list(self.conn.list_dir(nodeid, filename))
                return self.json_response({
                    'files': files,
                })

            else:
                # return node file
                with self.conn.open_file(nodeid, filename) as stream:
                    mime, encoding = mimetypes.guess_type(
                        filename, strict=False)
                    response.content_type = (mime if mime else 'text')
#                                             'application/octet-stream')
                    return stream.read()

        except Exception, e:
            keepnote.log_error()
            abort(404, 'node not found ' + str(e))

    # get static files
    def static_file_view(self, filename):
        return static_file(filename, root=STATIC_DIR)
