"""

    KeepNote
    Change Node Icon Submenu

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

# pygtk imports
import pygtk
pygtk.require('2.0')
import gobject
import gtk

import keepnote.gui.icons
from keepnote.gui.icons import \
    lookup_icon_filename

default_menu_icons = [x for x in keepnote.gui.icons.builtin_icons
                      if "-open." not in x][:20]



class IconMenu (gtk.Menu):
    """Icon picker menu"""

    def __init__(self):
        gtk.Menu.__init__(self)

        self._notebook = None
        
        # default icon
        self.default_icon = gtk.MenuItem("_Default Icon")
        self.default_icon.connect("activate",
                                  lambda w: self.emit("set-icon", ""))
        self.default_icon.show()

        # new icon
        self.new_icon = gtk.MenuItem("_More Icons...")
        self.new_icon.show()


        self.width = 4
        self.posi = 0
        self.posj = 0
        
        self.setup_menu()


    def clear(self):
        """clear menu"""
        
        self.foreach(lambda item: self.remove(item))        
        self.posi = 0
        self.posj = 0


    def set_notebook(self, notebook):        
        """Set notebook for menu"""
        
        if self._notebook is not None:
            # disconnect from old notebook
            self._notebook.pref.quick_pick_icons_changed.remove(self.setup_menu)
        
        self._notebook = notebook
        
        if self._notebook is not None:
            # listener to new notebook
            self._notebook.pref.quick_pick_icons_changed.add(self.setup_menu)
        
        self.setup_menu()
    

    def setup_menu(self):
        """Update menu to reflect notebook"""

        self.clear()       

        if self._notebook is None:
            for iconfile in default_menu_icons:
                self.add_icon(iconfile)
        else:
            for iconfile in self._notebook.pref.get_quick_pick_icons():
                self.add_icon(iconfile)

        # separator
        item = gtk.SeparatorMenuItem()
        item.show()
        self.append(item)

        # default icon               
        self.append(self.default_icon)

        # new icon        
        self.append(self.new_icon)

        # make changes visible
        self.unrealize()
        self.realize()
        

    def append_grid(self, item):
        self.attach(item, self.posj, self.posj+1, self.posi, self.posi+1)
        
        self.posj += 1
        if self.posj >= self.width:
            self.posj = 0
            self.posi += 1

    def append(self, item):
        
        # reset posi, posj
        if self.posj > 0:
            self.posi += 1
            self.posj = 0

        gtk.Menu.append(self, item)

    def add_icon(self, iconfile):

        child = gtk.MenuItem("")
        child.remove(child.child)
        img = gtk.Image()
        iconfile2 = lookup_icon_filename(self._notebook, iconfile)
        img.set_from_file(iconfile2)
        child.add(img)
        child.child.show()
        child.show()
        child.connect("activate",
                      lambda w: self.emit("set-icon", iconfile))
        self.append_grid(child)


gobject.type_register(IconMenu)
gobject.signal_new("set-icon", IconMenu, gobject.SIGNAL_RUN_LAST, 
           gobject.TYPE_NONE, (object,))

