"""
    KeepNote Extension 
    backup_tar

    Tar file notebook backup
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
from keepnote.gui import extension


class Extension (extension.Extension):
    
    version = (1, 0)
    name = "Basic Commands"
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
            AppCommand("quit", lambda app, args: app.quit(),
                       help="close all KeepNote windows"),
            ]


    def get_depends(self):
        return [("keepnote", ">=", (0, 6, 2))]


    def on_enabled(self, enabled):
        
        if enabled:
            for command in self.commands:
                try:
                    self.app.add_command(command)
                except Exception, e:
                    self.app.erorr("Could not add command '%s'" % command.name,
                                   e, sys.exc_info()[2])

        else:
            for command in self.commands:
                self.app.remove_command(command.name)


    #====================================================
    # commands

    def on_uninstall_extension(self, app, args):
        
        for extname in args[1:]:
            ext = app.get_extension(extname)
            if ext is None:
                app.error("unknown extension '%s'" % extname)
            else:
                app.uninstall_extension(ext)


    def on_install_extension(self, app, args):
        
        for filename in args[1:]:
            app.install_extension(filename)


    def on_screenshot(self, app, args):
        window = app.get_current_window()
        if window:
            window.get_viewer().editor.on_screenshot()
        
