"""
    KeepNote Extension 
    backup_tar

    Command-line basic commands
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


# python imports
import os
import sys

# keepnote imports
import keepnote
from keepnote import AppCommand
import keepnote.notebook
from keepnote.gui import extension


class Extension (extension.Extension):
    
    version = (1, 0)
    name = "Basic Commands"
    author = "Matt Rasmussen <rasmus@mit.edu>"
    description = "Adds basic command line options to KeepNote"


    def __init__(self, app):
        """Initialize extension"""
        
        extension.Extension.__init__(self, app)
        self.app = app
        self.enabled.add(self.on_enabled)

        self.commands = [
            AppCommand("focus", lambda app, args: app.focus_windows(),
                       help="focus all open windows"),
            AppCommand("screenshot", self.on_screenshot,
                       help="insert a new screenshot"),
            AppCommand("install", self.on_install_extension,
                       metavar="FILENAME",
                       help="install a new extension"),
            AppCommand("uninstall", self.on_uninstall_extension,
                       metavar="EXTENSION_NAME",
                       help="uninstall an extension"),
            AppCommand("tmp_ext", self.on_temp_extension,
                       metavar="FILENAME",
                       help="add an extension just for this session"),
            AppCommand("quit", lambda app, args: app.quit(),
                       help="close all KeepNote windows"),

            AppCommand("view", self.on_view_note,
                       metavar="NOTE_URL",
                       help="view a note"),
            AppCommand("search-titles", self.on_search_titles,
                       metavar="TEXT",
                       help="search notes by title")

            ]


    def get_depends(self):
        return [("keepnote", ">=", (0, 6, 4))]


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

    def on_uninstall_extension(self, app, args):
        
        for extname in args[1:]:
            app.uninstall_extension(extname)


    def on_install_extension(self, app, args):
        
        for filename in args[1:]:
            app.install_extension(filename)

            
    def on_temp_extension(self, app, args):

        for filename in args[1:]:
            entry = app.add_extension_entry(filename, "temp")
            ext = app.get_extension(entry.get_key())
            if ext:
                app.init_extensions_windows(windows=None, exts=[ext])
                ext.enable(True)
            


    def on_screenshot(self, app, args):
        window = app.get_current_window()
        if window:
            window.get_viewer().editor.on_screenshot()
        

    def on_view_note(self, app, args):

        if len(args) < 1:
            self.error("Must specify note url")
            return
        
        app.focus_windows()

        nodeurl = args[1]
        if keepnote.notebook.is_node_url(nodeurl):
            host, nodeid = keepnote.notebook.parse_node_url(nodeurl)
            self.view_nodeid(app, nodeid)
        else:
            # do text search
            window = self.app.get_current_window()
            if window is None:
                return
            notebook = window.get_notebook()
            if notebook is None:
                return
            
            results = list(notebook.search_node_titles(nodeurl))

            if len(results) == 1:
                self.view_nodeid(app, results[0][0])
            else:
                viewer = window.get_viewer()
                viewer.start_search_result()
                for nodeid, title in results:
                    node = notebook.get_node_by_id(nodeid)
                    if node:
                        viewer.add_search_result(node)
                        



    def on_search_titles(self, app, args):

        if len(args) < 1:
            self.error("Must specify text to search")
            return
        
        app.focus_windows()        

        # get window and notebook
        window = self.app.get_current_window()
        if window is None:
            return
        notebook = window.get_notebook()
        if notebook is None:
            return
        
        # do search
        text = args[1]
        nodes = list(notebook.search_node_titles(text))
        for nodeid, title in nodes:
            print "%s\t%s" % (title, keepnote.notebook.get_node_url(nodeid))


    def view_nodeid(self, app, nodeid):
        
        for window in app.get_windows():
            notebook = window.get_notebook()
            if not notebook:
                continue
            node = notebook.get_node_by_id(nodeid)
            if node:
                window.get_viewer().goto_node(node)
                break

