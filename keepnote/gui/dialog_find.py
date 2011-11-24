"""

    KeepNote
    Find Dialog

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
from keepnote import get_resource, unicode_gtk



class KeepNoteFindDialog (object):
    """ Find dialog """
    
    def __init__(self, editor):
        self.editor = editor
        self.find_dialog = None
        self.find_text = None
        self.replace_text = None

    
    def on_find(self, replace=False, forward=None):
        if self.find_dialog is not None:
            self.find_dialog.present()
            
            # could add find again behavior here            
            self.find_xml.get_widget("replace_checkbutton").set_active(replace)
            self.find_xml.get_widget("replace_entry").set_sensitive(replace)
            self.find_xml.get_widget("replace_button").set_sensitive(replace)
            self.find_xml.get_widget("replace_all_button").set_sensitive(replace)
            
            if not replace:
                if forward is None:
                    self.on_find_response("find")
                elif forward:
                    self.on_find_response("find_next")
                else:
                    self.on_find_response("find_prev")
            else:
                self.on_find_response("replace")
            
            return
        

        
        self.find_xml = gtk.glade.XML(get_resource("rc", "keepnote.glade"),
                                      domain=keepnote.GETTEXT_DOMAIN)    
        self.find_dialog = self.find_xml.get_widget("find_dialog")
        self.find_dialog.connect("delete-event", lambda w,e: self.on_find_response("close"))
        self.find_last_pos = -1
        
            
        
        self.find_xml.signal_autoconnect({
            "on_find_dialog_key_release_event":
                self.on_find_key_released,
            "on_close_button_clicked": 
                lambda w: self.on_find_response("close"),
            "on_find_button_clicked": 
                lambda w: self.on_find_response("find"),
            "on_replace_button_clicked": 
                lambda w: self.on_find_response("replace"),
            "on_replace_all_button_clicked": 
                lambda w: self.on_find_response("replace_all"),
            "on_replace_checkbutton_toggled":
                lambda w: self.on_find_replace_toggled()
            })
        
        if self.find_text is not None:
            self.find_xml.get_widget("text_entry").set_text(self.find_text)
        
        if self.replace_text is not None:
            self.find_xml.get_widget("replace_entry").set_text(self.replace_text)
        
        self.find_xml.get_widget("replace_checkbutton").set_active(replace)
        self.find_xml.get_widget("replace_entry").set_sensitive(replace)
        self.find_xml.get_widget("replace_button").set_sensitive(replace)
        self.find_xml.get_widget("replace_all_button").set_sensitive(replace)
        
        self.find_dialog.show()
        self.find_dialog.move(*self.editor.get_toplevel().get_position())

    
    def on_find_key_released(self, widget, event):
        
        if event.keyval == gtk.keysyms.G and \
           event.state & gtk.gdk.SHIFT_MASK and \
           event.state & gtk.gdk.CONTROL_MASK:
            self.on_find_response("find_prev")
            widget.stop_emission("key-release-event")
        
        elif event.keyval == gtk.keysyms.g and \
           event.state & gtk.gdk.CONTROL_MASK:
            self.on_find_response("find_next")
            widget.stop_emission("key-release-event")
    
    
    def on_find_response(self, response):
        
        # get find options
        find_text = unicode_gtk(self.find_xml.get_widget("text_entry").get_text())
        replace_text = unicode_gtk(self.find_xml.get_widget("replace_entry").get_text())
        case_sensitive = self.find_xml.get_widget("case_sensitive_button").get_active()
        search_forward = self.find_xml.get_widget("forward_button").get_active()
        
        self.find_text = find_text
        self.replace_text = replace_text
        next = (self.find_last_pos != -1)
        
                
        if response == "close":
            self.find_dialog.destroy()
            self.find_dialog = None
            
        elif response == "find":
            self.find_last_pos = self.editor.get_textview().find(find_text, case_sensitive, search_forward, next)

        elif response == "find_next":
            self.find_xml.get_widget("forward_button").set_active(True)
            self.find_last_pos = self.editor.get_textview().find(find_text, case_sensitive, True)

        elif response == "find_prev":
            self.find_xml.get_widget("backward_button").set_active(True)
            self.find_last_pos = self.editor.get_textview().find(find_text, case_sensitive, False)
        
        elif response == "replace":
            self.find_last_pos = self.editor.get_textview().replace(find_text, replace_text,
                                         case_sensitive, search_forward)
            
        elif response == "replace_all":
            self.editor.get_textview().replace_all(find_text, replace_text,
                                             case_sensitive, search_forward)
    
    
    def on_find_replace_toggled(self):
        
        if self.find_xml.get_widget("replace_checkbutton").get_active():
            self.find_xml.get_widget("replace_entry").set_sensitive(True)
            self.find_xml.get_widget("replace_button").set_sensitive(True)
            self.find_xml.get_widget("replace_all_button").set_sensitive(True)
        else:
            self.find_xml.get_widget("replace_entry").set_sensitive(False)
            self.find_xml.get_widget("replace_button").set_sensitive(False)
            self.find_xml.get_widget("replace_all_button").set_sensitive(False)
