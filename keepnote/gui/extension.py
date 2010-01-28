"""
    KeepNote
    Extension system with GUI relevant functions
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
from keepnote import extension

#=============================================================================
# extension functions



class Extension (extension.Extension):
    """KeepNote Extension"""

    def __init__(self, app):
        extension.Extension.__init__(self, app)
        
        self.__windows = set()
        self.__uis = set()


    def enable(self, enable):
        """Enable/disable extension"""

        # check dependencies
        self.check_depends()

        # mark extension enable state
        self._enabled = enable

        # TODO: I should use the listener system and registry each of these
        # callbacks that way.

        # call callback for app
        self._app.on_extension_enabled(self, enable)

        # callback for GUI extension
        self._on_enable_ui()

        # call callback for extension implementation
        self.on_enabled(enable)

        # return whether the extension is enabled
        return self._enabled

    
    #================================
    # window interactions

    def _on_enable_ui(self):
        """Initialize UI during enable/disable"""
        if self._enabled:
            # TODO: should each extension have to remember what windows it has?
            for window in self.__windows:
                if window not in self.__uis:
                    self.on_add_ui(window)
                    self.__uis.add(window)
        else:
            for window in self.__uis:
                self.on_remove_ui(window)
            self.__uis.clear()



    def on_new_window(self, window):
        """Initialize extension for a particular window"""

        if self._enabled:
            try:
                self.on_add_ui(window)
                self.__uis.add(window)
            except Exception, e:
                keepnote.log_error(e, sys.exc_info()[2])
        self.__windows.add(window)


    def on_close_window(self, window):
        """Callback for when window is closed"""
     
        if window in self.__windows:
            if window in self.__uis:
                try:
                    self.on_remove_ui(window)
                except Exception, e:
                    keepnote.log_error(e, sys.exc_info()[2])
                self.__uis.remove(window)
            self.__windows.remove(window)

    def get_windows(self):
        """Returns windows associated with extension"""
        return self.__windows
            

    #===============================
    # UI interaction

    def on_add_ui(self, window):
        pass

    def on_remove_ui(self, window):
        pass

    def on_add_options_ui(self, dialog):
        pass

    def on_remove_options_ui(self, dialog):
        pass

