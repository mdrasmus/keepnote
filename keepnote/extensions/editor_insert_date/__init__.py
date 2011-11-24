"""

    KeepNote
    Insert date extension

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



class Extension (extension.Extension):

    def __init__(self, app):
        """Initialize extension"""
        
        extension.Extension.__init__(self, app)

        self._widget_focus = {}
        self._set_focus_id = {}
        
        self.format = "%Y/%m/%d"

        self.enabled.add(self.on_enabled)


    def on_enabled(self, enabled):
        if enabled:
            self.load_config()


    def get_depends(self):
        return [("keepnote", ">=", (0, 7, 1))]

    #===============================
    # config handling

    def get_config_file(self):
        return self.get_data_file("config")

    def load_config(self):
        config = self.get_config_file()
        if not os.path.exists(config):
            self.save_config()
        else:
            self.format = open(config).readline()
        

    def save_config(self):
        config = self.get_config_file()
        out = open(config, "w")
        out.write(self.format)
        out.close()

        
    #================================
    # UI setup

    def on_add_ui(self, window):

        # list to focus events from the window
        self._set_focus_id[window] = window.connect("set-focus", self._on_focus)

        # add menu options
        self.add_action(window, "Insert Date", "Insert _Date", 
                        lambda w: self.insert_date(window))

        self.add_ui(window,
                """
                <ui>
                <menubar name="main_menu_bar">
                   <menu action="Edit">
                      <placeholder name="Viewer">
                         <placeholder name="Editor">
                           <placeholder name="Extension">
                             <menuitem action="Insert Date"/>
                           </placeholder>
                         </placeholder>
                      </placeholder>
                   </menu>
                </menubar>
                </ui>
                """)

    def on_remove_ui(self, window):
        
        extension.Extension.on_remove_ui(self, window)
        
        # disconnect window callbacks
        window.disconnect(self._set_focus_id[window])
        del self._set_focus_id[window]


    #=================================
    # Options UI setup

    def on_add_options_ui(self, dialog):
        
        dialog.add_section(EditorInsertDateSection("editor_insert_date", 
                                                   dialog, self._app,
                                                   self),
                           "extensions")



    def on_remove_options_ui(self, dialog):
        
        dialog.remove_section("editor_insert_date")


    #================================
    # actions


    def _on_focus(self, window, widget):
        """Callback for focus change in window"""
        self._widget_focus[window] = widget

    
    def insert_date(self, window):
        """Insert a date in the editor of a window"""

        widget = self._widget_focus.get(window, None)

        if isinstance(widget, gtk.TextView):
            stamp = time.strftime(self.format, time.localtime())
            widget.get_buffer().insert_at_cursor(stamp)



class EditorInsertDateSection (dialog_app_options.Section):
    """A Section in the Options Dialog"""

    def __init__(self, key, dialog, app, ext,
                 label=u"Editor Insert Date", 
                 icon=None):
        dialog_app_options.Section.__init__(self, key, dialog, app, label, icon)

        self.ext = ext

        w = self.get_default_widget()
        v = gtk.VBox(False, 5)
        w.add(v)

        table = gtk.Table(1, 2)
        v.pack_start(table, False, True, 0)

        label = gtk.Label("Date format:")
        table.attach(label, 0, 1, 0, 1,
                     xoptions=0, yoptions=0,
                     xpadding=2, ypadding=2)

        self.format = gtk.Entry()
        table.attach(self.format, 1, 2, 0, 1,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)

        xml = gtk.glade.XML(dialog_app_options.get_resource("rc", "keepnote.glade"),
                            "date_and_time_key", keepnote.GETTEXT_DOMAIN)
        key = xml.get_widget("date_and_time_key")
        key.set_size_request(400, 200)
        v.pack_start(key, True, True, 0)

        w.show_all()


    def load_options(self, app):
        """Load options from app to UI"""
        
        self.format.set_text(self.ext.format)

    def save_options(self, app):
        """Save options to the app"""
        
        self.ext.format = self.format.get_text()
        self.ext.save_config()
