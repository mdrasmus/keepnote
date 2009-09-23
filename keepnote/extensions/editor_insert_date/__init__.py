"""

    KeepNote
    Insert date extension

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
_ = gettext.gettext


# keepnote imports
import keepnote

# pygtk imports
try:
    import pygtk
    pygtk.require('2.0')
    import gtk
except ImportError:
    # do not fail on gtk import error,
    # extension should be usable for non-graphical uses
    pass



class Extension (keepnote.Extension):
    
    version = (1, 0)
    name = "Editor Insert Date"
    description = "Inserts a the current date in the text editor"


    def __init__(self, app):
        """Initialize extension"""
        
        keepnote.Extension.__init__(self, app)
        self._widget_focus = {}


    def on_new_window(self, window):
        """Initialize extension for a particular window"""


        window.connect("set-focus", self._on_focus)

        # add menu options
        window.actiongroup.add_actions([
            ("Insert Date", None, "Insert _Date",
             "", None,
             lambda w: self.insert_date(window)),
            ])
        
        window.uimanager.add_ui_from_string(
            """
            <ui>
            <menubar name="main_menu_bar">
               <menu action="Edit">
                  <placeholder name="Editor">
                     <menuitem action="Insert Date"/>
                  </placeholder>
               </menu>
            </menubar>
            </ui>
            """)


    def _on_focus(self, window, widget):
        """Callback for focus change in window"""
        self._widget_focus[window] = widget

    def insert_date(self, window):
        """Insert a date in the editor of a window"""

        widget = self._widget_focus.get(window, None)

        if isinstance(widget, gtk.TextView):
            stamp = time.strftime("%Y/%m/%d", time.localtime())
            widget.get_buffer().insert_at_cursor(stamp)

