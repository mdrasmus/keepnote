"""

    KeepNote
    Python prompt extension

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
import gettext
import time
import os
import sys
_ = gettext.gettext


# keepnote imports
import keepnote
from keepnote.gui import extension


# pygtk imports
try:
    import pygtk
    pygtk.require('2.0')
    import gtk

    from keepnote.gui import dialog_app_options

except ImportError:
    # do not fail on gtk import error,
    # extension should be usable for non-graphical uses
    pass


sys.path.append(os.path.dirname(__file__))
import dialog_python


class Extension (extension.Extension):

    def __init__(self, app):
        """Initialize extension"""
        
        extension.Extension.__init__(self, app)

        self._ui_id = {}
        self._action_groups = {}


    def get_depends(self):
        return [("keepnote", ">=", (0, 6, 2))]

        
    #================================
    # UI setup

    def on_add_ui(self, window):

        # add menu options
        self._action_groups[window] = gtk.ActionGroup("MainWindow")
        self._action_groups[window].add_actions([
                ("Python Prompt...", None, "Python Prompt...",
                 "", None,
                 lambda w: self.on_python_prompt(window)),
                ])
        window.get_uimanager().insert_action_group(self._action_groups[window], 0)


        self._ui_id[window] = window.get_uimanager().add_ui_from_string(
                """
                <ui>
                <menubar name="main_menu_bar">
                   <menu action="Tools">
                      <placeholder name="Extensions">
                        <menuitem action="Python Prompt..."/>
                      </placeholder>
                   </menu>
                </menubar>
                </ui>
                """)

    def on_remove_ui(self, window):        
        
        # remove menu options
        window.get_uimanager().remove_ui(self._ui_id[window])
        window.get_uimanager().remove_action_group(self._action_groups[window])
        del self._action_groups[window]
        del self._ui_id[window]


    #================================
    # actions


    def on_python_prompt(self, window):

        dialog = dialog_python.PythonDialog(window)
        dialog.show()
