"""
    KeepNote Extension 
    backup_tar

    Command-line basic commands
"""

#
#  KeepNote
#  Copyright (c) 2008-2009 Matt Rasmussen
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
import os
import sys

# gtk imports
import gobject

# keepnote imports
import keepnote
from keepnote import AppCommand
import keepnote.notebook
import keepnote.notebook.update
import keepnote.extension
import keepnote.gui.extension


class Extension (keepnote.gui.extension.Extension):
    
    def __init__(self, app):
        """Initialize extension"""
        
        keepnote.gui.extension.Extension.__init__(self, app)
        self.app = app
        self.enabled.add(self.on_enabled)

        self.commands = [
            # window commands
            AppCommand("focus", lambda app, args: app.focus_windows(),
                       help="focus all open windows"),
            AppCommand("minimize", self.on_minimize_windows,
                       help="minimize all windows"),
            AppCommand("toggle-windows", self.on_toggle_windows,
                       help="toggle all windows"),

            # extension commands
            AppCommand("install", self.on_install_extension,
                       metavar="FILENAME",
                       help="install a new extension"),
            AppCommand("uninstall", self.on_uninstall_extension,
                       metavar="EXTENSION_NAME",
                       help="uninstall an extension"),
            AppCommand("tmp_ext", self.on_temp_extension,
                       metavar="FILENAME",
                       help="add an extension just for this session"),
            AppCommand("ext_path", self.on_extension_path,
                       metavar="PATH",
                       help="add an extension path for this session"),
            AppCommand("quit", lambda app, args: 
                       gobject.idle_add(app.quit),
                       help="close all KeepNote windows"),

            # notebook commands
            AppCommand("view", self.on_view_note,
                       metavar="NOTE_URL",
                       help="view a note"),
            AppCommand("new", self.on_new_note,
                       metavar="PARENT_URL",
                       help="add a new note"),
            AppCommand("search-titles", self.on_search_titles,
                       metavar="TEXT",
                       help="search notes by title"),
            AppCommand("upgrade", self.on_upgrade_notebook,
                       metavar="[v VERSION] NOTEBOOK...",
                       help="upgrade a notebook"),

            # misc
            AppCommand("screenshot", self.on_screenshot,
                       help="insert a new screenshot"),


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

    def on_minimize_windows(self, app, args):
        
        for window in app.get_windows():
            window.iconify()

    def on_toggle_windows(self, app, args):
        
        for window in app.get_windows():
            if window.is_active():
                self.on_minimize_windows(app, args)
                return
        
        app.focus_windows()



    def on_uninstall_extension(self, app, args):
        
        for extname in args[1:]:
            app.uninstall_extension(extname)


    def on_install_extension(self, app, args):
        
        for filename in args[1:]:
            app.install_extension(filename)

            
    def on_temp_extension(self, app, args):

        for filename in args[1:]:
            entry = app.add_extension(filename, "temp")
            ext = app.get_extension(entry.get_key())
            if ext:
                app.init_extensions_windows(windows=None, exts=[ext])
                ext.enable(True)
            

    def on_extension_path(self, app, args):

        exts = []
        for extensions_dir in args[1:]:
            for filename in keepnote.extension.iter_extensions(extensions_dir):
                entry = app.add_extension_entry(filename, "temp")
                ext = app.get_extension(entry.get_key())
                if ext:
                    exts.append(ext)

        app.init_extensions_windows(windows=None, exts=exts)
        for ext in exts:
            ext.enable(True)


    def on_screenshot(self, app, args):
        window = app.get_current_window()
        if window:
            editor = window.get_viewer().get_editor()
            if hasattr(editor, "get_editor"):
                editor = editor.get_editor()
            if hasattr(editor, "on_screenshot"):
                editor.on_screenshot()
        

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
                        


    def on_new_note(self, app, args):

        if len(args) < 1:
            self.error("Must specify note url")
            return
        
        app.focus_windows()
        
        nodeurl = args[1]
        window, notebook = self.get_window_notebook()
        nodeid = self.get_nodeid(nodeurl)
        if notebook and nodeid:
            node = notebook.get_node_by_id(nodeid)
            if node:
                window.get_viewer().new_node(
                    keepnote.notebook.CONTENT_TYPE_PAGE, "child", node)


    def on_search_titles(self, app, args):

        if len(args) < 1:
            self.error("Must specify text to search")
            return
        
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


    def get_nodeid(self, text):
        
        if keepnote.notebook.is_node_url(text):
            host, nodeid = keepnote.notebook.parse_node_url(text)
            return nodeid            
        else:
            # do text search
            window = self.app.get_current_window()
            if window is None:
                return None
            notebook = window.get_notebook()
            if notebook is None:
                return None
            
            results = list(notebook.search_node_titles(text))

            if len(results) == 1:
                return results[0][0]
            else:
                for nodeid, title in results:
                    if title == text:
                        return nodeid

                return None


    def get_window_notebook(self):
        window = self.app.get_current_window()
        if window is None:
            return None, None
        notebook = window.get_notebook()
        return window, notebook


    def on_upgrade_notebook(self, app, args):

        version = keepnote.notebook.NOTEBOOK_FORMAT_VERSION
        i = 1
        while i < len(args):
            if args[i] == "v":
                try:
                    version = int(args[i+1])
                    i += 2
                except:
                    raise Exception("excepted version number")
            else:
                break

        files = args[i:]

        for filename in files:
            keepnote.log_message("upgrading notebook to version %d: %s\n" % 
                                 (version, filename))
            keepnote.notebook.update.update_notebook(filename, version, 
                                                     verify=True)
