"""

    KeepNote
    Font selector widget

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
from gtk import gdk
import gtk.glade
import gobject



class FontSelector (gtk.ComboBox):
    """ComboBox for selection Font family"""
    
    def __init__(self):
        gtk.ComboBox.__init__(self)

        self._list = gtk.ListStore(str)
        self.set_model(self._list)
        
        self._families = sorted(f.get_name()
            for f in self.get_pango_context().list_families())
        self._lookup = [x.lower() for x in self._families]

        for f in self._families:
            self._list.append([f])

        cell = gtk.CellRendererText()
        self.pack_start(cell, True)
        self.add_attribute(cell, 'text', 0)
        
        fam = self.get_pango_context().get_font_description().get_family()
        self.set_family(fam)

        
    def set_family(self, family):
        try:
            index = self._lookup.index(family.lower())
            self.set_active(index)
        except:
            pass
        

    def get_family(self):
        return self._families[self.get_active()]
