"""
    KeepNote Extension 
    notebook_html

    Command-line basic commands
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


# python imports
import sys
import os
import httplib
import urllib
import urlparse
import thread
import select
import BaseHTTPServer
from StringIO import StringIO

# gtk imports
import gobject

# keepnote imports
import keepnote
from keepnote import AppCommand
import keepnote.notebook
import keepnote.notebook.update
import keepnote.extension
import keepnote.gui.extension
from keepnote.notebook.connection import NoteBookConnection
from keepnote.notebook.connection.fs import NoteBookConnectionFS
from keepnote.notebook.connection.http import \
    NoteBookConnectionHttp, NoteBookHttpServer
from keepnote import plist



class Extension (keepnote.gui.extension.Extension):
    
    def __init__(self, app):
        """Initialize extension"""
        
        keepnote.gui.extension.Extension.__init__(self, app)
        self.app = app
        self.enabled.add(self.on_enabled)

        self._ports = {}

        self.commands = [
            # window commands
            AppCommand("start-http-server", 
                       self.start_http_server,
                       metavar="PORT NOTEBOOK",
                       help="start HTTP server on PORT with NOTEBOOK"),
            AppCommand("stop-http-server", 
                       self.stop_http_server,
                       metavar="PORT",
                       help="stop HTTP server on port PORT")
            ]


    def get_depends(self):
        return [("keepnote", ">=", (0, 7, 6))]


    def on_enabled(self, enabled):
        
        if enabled:
            for command in self.commands:
                if self.app.get_command(command.name):
                    continue
                try:
                    self.app.add_command(command)
                except Exception, e:
                    self.app.error("Could not add command '%s'" % command.name,
                                   e, sys.exc_info()[2])

        else:
            for command in self.commands:
                self.app.remove_command(command.name)


    #====================================================
    # commands

    def start_http_server(self, app, args):
        
        port = int(args[1])
        notebook_path = unicode(args[2])

        # connect to notebook on disk
        conn = NoteBookConnectionFS()
        conn.connect(notebook_path)

        # start server in another thread
        host = "localhost"
        url = "http://%s:%d/" % (host, port)
        server = NoteBookHttpServer(conn, port=port)

        if port in self._ports:
            raise Exception("Server already on port %d" % port)

        self._ports[port] = server

        keepnote.log_message("starting server:\n%s\n" % url)
        thread.start_new_thread(server.serve_forever, ())

        if host == "localhost":
            keepnote.log_message("NOTE: server is local only.  Use ssh port forwarding for security.\n")


    def stop_http_server(self, app, args):
        
        port = int(args[1])

        if port not in self._ports:
            raise Exception("No server is on port %d" % port)

        server = self._ports[port]

        keepnote.log_message("stopping server on port %d...\n" % port)
        server.shutdown()

        del self._ports[port]
       


