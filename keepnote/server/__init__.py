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
from cStringIO import StringIO
from httplib import BAD_REQUEST
from httplib import FORBIDDEN
from httplib import NOT_FOUND
import json
import mimetypes
import os
import urllib

# bottle imports
from . import bottle
from .bottle import Bottle
from .bottle import abort
from .bottle import request
from .bottle import response
from .bottle import static_file
from .bottle import template

# keepnote imports
import keepnote
from keepnote.notebook import new_nodeid
import keepnote.notebook.connection as connlib

# Server directories.
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')


#=============================================================================
# Node URL scheme


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


def write_node_tree(out, conn, nodeid=None):
    if not nodeid:
        nodeid = conn.get_rootid()

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
        write_node_tree(out, conn, childid)
        out.write("</li>")

    out.write("</ul>")


class BaseNoteBookHttpServer(object):

    def __init__(self, conn, host="", port=8000):
        self.conn = conn
        self.host = host
        self.port = port
        self.notebook_prefixes = ['notebook/']

        self.app = Bottle()
        self.server = None

        # Setup web app routes.
        self.app.get('/', callback=self.home_view)
        self.app.get('/static/<filename:re:.*>',
                     callback=self.static_file_view)

        # Notebook node routes.
        self.app.post('/notebook/',
                      callback=self.command_view)
        self.app.get('/notebook/nodes/',
                     callback=self.read_root_view)
        self.app.get('/notebook/nodes/<nodeid:re:[^/]+>',
                     callback=self.read_node_view)
        self.app.post('/notebook/nodes/',
                      callback=self.create_node_view)
        self.app.post('/notebook/nodes/<nodeid:re:[^/]+>',
                      callback=self.create_node_view)
        self.app.put('/notebook/nodes/<nodeid:re:[^/]+>',
                     callback=self.update_node_view)
        self.app.delete('/notebook/nodes/<nodeid:re:[^/]+>',
                        callback=self.delete_node_view)
        self.app.route('/notebook/nodes/<nodeid:re:[^/]+>', 'HEAD',
                       callback=self.has_node_view)

        # Notebook file routes.
        self.app.get('/notebook/nodes/<nodeid:re:[^/]*>/<filename:re:.*>',
                     callback=self.read_file_view)
        self.app.post('/notebook/nodes/<nodeid:re:[^/]*>/<filename:re:.*>',
                      callback=self.write_file_view)
        self.app.put('/notebook/nodes/<nodeid:re:[^/]*>/<filename:re:.*>',
                     callback=self.write_file_view)
        self.app.delete('/notebook/nodes/<nodeid:re:[^/]*>/<filename:re:.*>',
                        callback=self.delete_file_view)
        self.app.route('/notebook/nodes/<nodeid:re:[^/]*>/<filename:re:.*>',
                       'HEAD', callback=self.has_file_view)

    def serve_forever(self, debug=False):
        """
        Run server.
        """
        if os.environ.get("KEEPNOTE_DEBUG"):
            debug = True

        self.server = bottle.WSGIRefServer(
            host=self.host, port=self.port, debug=debug)
        self.app.run(
            host=self.host, port=self.port, server=self.server,
            debug=debug, reloader=debug)

    def shutdown(self):
        """
        Shutdown server.
        """
        if self.server:
            self.server.srv.shutdown()

    def json_response(self, data):
        """
        Return a JSON response.
        """
        response.content_type = 'application/json'
        return json.dumps(data).encode('utf8')

    def home_view(self):
        """
        Homepage of notebook webapp.
        """
        context = {}
        return template(TEMPLATES_DIR + '/home.html', context)

    def command_view(self):
        """
        Notebook commands.
        """
        if 'save' in request.query:
            # Force notebook save.
            self.conn.save()

        elif 'index' in request.query:
            # Query notebook index.
            data = request.body.read()
            query = json.loads(data)
            result = self.conn.index(query)

            # Build list if needed.
            if hasattr(result, "next"):
                result = list(result)

            return self.json_response(result)

    def read_root_view(self):
        """
        Return notebook root nodeid.
        """
        # get rootid
        result = {
            'rootids': [self.conn.get_rootid()],
        }
        return self.json_response(result)

    def render_node_tree(self, nodeid):
        body = StringIO()
        body.write("<html><body>")
        write_node_tree(body, self.conn, nodeid)
        body.write("</body></html>")
        return body.getvalue()

    def read_node_view(self, nodeid):
        """
        Read notebook node attr.
        """
        nodeid = urllib.unquote(nodeid)

        if 'all' in request.query:
            # Render a simple tree
            response.content_type = 'text/html'
            return self.render_node_tree(nodeid)

        try:
            # return node attr
            attr = self.conn.read_node(nodeid)
            if attr.get("parentids") == [None]:
                del attr["parentids"]

            return self.json_response(attr)

        except connlib.UnknownNode, e:
            keepnote.log_error()
            abort(NOT_FOUND, 'node not found ' + str(e))

    def create_node_view(self, nodeid=None):
        """
        Create new notebook node.
        """
        if nodeid is not None:
            nodeid = urllib.unquote(nodeid)
        else:
            nodeid = new_nodeid()

        data = request.body.read()
        attr = json.loads(data)

        try:
            self.conn.create_node(nodeid, attr)
        except connlib.NodeExists, e:
            keepnote.log_error()
            abort(FORBIDDEN, 'node already exists.' + str(e))

        return self.json_response(attr)

    def update_node_view(self, nodeid):
        """Update notebook node attr."""
        nodeid = urllib.unquote(nodeid)

        # update node
        data = request.body.read()
        attr = json.loads(data)

        try:
            self.conn.update_node(nodeid, attr)
        except connlib.UnknownNode, e:
            keepnote.log_error()
            abort(NOT_FOUND, 'node not found ' + str(e))

        return self.json_response(attr)

    def delete_node_view(self, nodeid):
        """Delete notebook node."""
        nodeid = urllib.unquote(nodeid)
        try:
            self.conn.delete_node(nodeid)
        except connlib.UnknownNode, e:
            keepnote.log_error()
            abort(NOT_FOUND, 'node not found ' + str(e))

    def has_node_view(self, nodeid):
        """
        Check for node existence.
        """
        nodeid = urllib.unquote(nodeid)
        if not self.conn.has_node(nodeid):
            abort(NOT_FOUND, 'node not found')

    def read_file_view(self, nodeid, filename):
        """Access notebook file."""
        nodeid = urllib.unquote(nodeid)
        filename = urllib.unquote(filename)
        if not filename:
            filename = '/'

        #default_mime = 'application/octet-stream'
        default_mime = 'text'

        try:
            if filename.endswith("/"):
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
                    response.content_type = (mime if mime else default_mime)

                    # TODO: return stream.
                    return stream.read()

        except connlib.UnknownNode, e:
            keepnote.log_error()
            abort(NOT_FOUND, 'cannot find node ' + str(e))
        except connlib.FileError, e:
            keepnote.log_error()
            abort(FORBIDDEN, 'Could not read file ' + str(e))

    def write_file_view(self, nodeid, filename):
        """
        Write node file.
        """
        nodeid = urllib.unquote(nodeid)
        filename = urllib.unquote(filename)
        if not filename:
            filename = '/'

        if filename.endswith("/"):
            # Create dir.
            if request.method == 'PUT':
                self.conn.create_dir(nodeid, filename)
            else:
                abort(BAD_REQUEST, 'Invalid method on directory')

        else:
            # Write file.
            try:
                if request.query.get("mode", "w") == ["a"]:
                    if request.method == 'PUT':
                        abort(BAD_REQUEST, 'Invalid method for file append')
                    stream = self.conn.open_file(nodeid, filename, "a")
                else:
                    stream = self.conn.open_file(nodeid, filename, "w")
                stream.write(request.body.read())
                stream.close()

            except connlib.UnknownNode, e:
                keepnote.log_error()
                abort(NOT_FOUND, 'cannot find node ' + str(e))
            except connlib.FileError, e:
                keepnote.log_error()
                abort(FORBIDDEN, 'Could not write file ' + str(e))

    def delete_file_view(self, nodeid, filename):
        """
        Delete node file.
        """
        nodeid = urllib.unquote(nodeid)
        filename = urllib.unquote(filename)
        if not filename:
            filename = '/'

        try:
            # delete file/dir
            self.conn.delete_file(nodeid, filename)
        except connlib.UnknownNode, e:
            keepnote.log_error()
            abort(NOT_FOUND, 'cannot find node ' + str(e))
        except connlib.FileError, e:
            keepnote.log_error()
            abort(FORBIDDEN, 'cannot delete file ' + str(e))

    def has_file_view(self, nodeid, filename):
        """
        Check node file existence.
        """
        nodeid = urllib.unquote(nodeid)
        filename = urllib.unquote(filename)
        if not filename:
            filename = '/'

        if not self.conn.has_file(nodeid, filename):
            abort(NOT_FOUND, 'file not found')

    # get static files
    def static_file_view(self, filename):
        return static_file(filename, root=STATIC_DIR)


class NoteBookHttpServer(BaseNoteBookHttpServer):

    def create_node_view(self, nodeid=None):
        """
        Create new notebook node.
        """
        if nodeid is not None:
            nodeid = urllib.unquote(nodeid)
        else:
            nodeid = new_nodeid()

        data = request.body.read()
        attr = json.loads(data)

        # Enforce notebook scheme, nodeid is required.
        attr['nodeid'] = nodeid

        try:
            self.conn.create_node(nodeid, attr)
        except connlib.NodeExists, e:
            keepnote.log_error()
            abort(FORBIDDEN, 'node already exists.' + str(e))

        return self.json_response(attr)
