"""
    KeepNote
    Extension system with GUI relevant functions
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
import sys

# gtk imports
import gtk

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

        # UI interface
        self.__ui_ids = {}         # toolbar/menu ids (per window)
        self.__action_groups = {}  # ui actions (per window)

        self.enabled.add(self._on_enable_ui)

    #================================
    # window interactions

    def _on_enable_ui(self, enabled):
        """Initialize UI during enable/disable"""
        if enabled:
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
        # remove actions for window
        self.remove_all_actions(window)

        # remove ui elements for window
        self.remove_all_ui(window)

    def on_add_options_ui(self, dialog):
        pass

    def on_remove_options_ui(self, dialog):
        pass

    #===============================
    # helper functions

    def add_action(self, window, action_name, menu_text,
                   callback=lambda w: None,
                   stock_id=None, accel="", tooltip=None):
        # init action group
        if window not in self.__action_groups:
            group = gtk.ActionGroup("MainWindow")
            self.__action_groups[window] = group
            window.get_uimanager().insert_action_group(group, 0)

        # add action
        self.__action_groups[window].add_actions([
            (action_name, stock_id, menu_text, accel, tooltip, callback)])

    def remove_action(self, window, action_name):
        group = self.__action_groups.get(window, None)
        if group is not None:
            action = group.get_action(action_name)
            if action:
                group.remove_action(action)

    def remove_all_actions(self, window):
        group = self.__action_groups.get(window, None)
        if group is not None:
            window.get_uimanager().remove_action_group(group)
            del self.__action_groups[window]

    def add_ui(self, window, uixml):
        # init list of ui ids
        uids = self.__ui_ids.get(window, None)
        if uids is None:
            uids = self.__ui_ids[window] = []

        # add ui, record id
        uid = window.get_uimanager().add_ui_from_string(uixml)
        uids.append(uid)

        # return id
        return uid

    def remove_ui(self, window, uid):
        uids = self.__ui_ids.get(window, None)
        if uids is not None and uid in uids:
            window.get_uimanager().remove_ui(uid)
            uids.remove(uid)

            # remove uid list if last uid removed
            if len(uids) == 0:
                del self.__ui_ids[window]

    def remove_all_ui(self, window):
        uids = self.__ui_ids.get(window, None)
        if uids is not None:
            for uid in uids:
                window.get_uimanager().remove_ui(uid)
            del self.__ui_ids[window]
