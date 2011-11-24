"""

    KeepNote
    Image Resize Dialog

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

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade

# keepnote imports
import keepnote
from keepnote import get_resource




class NewImageDialog (object):
    """New Image dialog"""
    
    def __init__(self, main_window, app):
        self.main_window = main_window
        self.app = app


    def show(self):
        
        dialog = gtk.Dialog(_("New Image"),
                            self.main_window,
                            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
                            (gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT,
                             gtk.STOCK_OK, gtk.RESPONSE_ACCEPT))

        table = gtk.Table(3, 2)
        dialog.vbox.pack_start(table, False, True, 0)

        label = gtk.Label(_("format:"))
        table.attach(label, 0, 1, 0, 1,
                     xoptions=0, yoptions=0,
                     xpadding=2, ypadding=2)

        # make this a drop down
        self.width = gtk.Entry()
        table.attach(self.width, 1, 2, 0, 1,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)


        label = gtk.Label(_("width:"))
        table.attach(label, 0, 1, 0, 1,
                     xoptions=0, yoptions=0,
                     xpadding=2, ypadding=2)

        self.width = gtk.Entry()
        table.attach(self.width, 1, 2, 0, 1,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)



        label = gtk.Label(_("height:"))
        table.attach(label, 0, 1, 0, 1,
                     xoptions=0, yoptions=0,
                     xpadding=2, ypadding=2)

        self.width = gtk.Entry()
        table.attach(self.width, 1, 2, 0, 1,
                     xoptions=gtk.FILL, yoptions=0,
                     xpadding=2, ypadding=2)


        table.show_all()
        response = dialog.run()


        dialog.destroy()
