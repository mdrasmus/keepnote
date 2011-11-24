"""

    KeepNote
    Link Editor Widget

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
import gtk, gobject

# keepnote imports
from keepnote import is_url, unicode_gtk
from keepnote.notebook import get_node_url



# TODO: make more checks for start, end not None

class LinkEditor (gtk.Frame):
    """Widget for editing KeepNote links"""

    def __init__(self):
        gtk.Frame.__init__(self, "Link editor")

        self.use_text = False
        self.current_url = None
        self.active = False
        self.textview = None
        self.search_nodes = None

        self.layout()

    def set_textview(self, textview):
        self.textview = textview
        

    def layout(self):
        # layout        
        self.set_no_show_all(True)
        
        self.align = gtk.Alignment()
        self.add(self.align)
        self.align.set_padding(5, 5, 5, 5)
        self.align.set(0, 0, 1, 1)

        self.show()        
        self.align.show_all()

        vbox = gtk.VBox(False, 5)
        self.align.add(vbox)

        hbox = gtk.HBox(False, 5)
        #self.align.add(hbox)
        vbox.pack_start(hbox, True, True, 0)

        label = gtk.Label("url:")
        hbox.pack_start(label, False, False, 0)
        label.set_alignment(0, .5)
        self.url_text = gtk.Entry()
        hbox.pack_start(self.url_text, True, True, 0)
        self.url_text.set_width_chars(-1)
        self.url_text.connect("key-press-event", self._on_key_press_event)
        self.url_text.connect("focus-in-event", self._on_url_text_start)
        self.url_text.connect("focus-out-event", self._on_url_text_done)
        self.url_text.connect("changed", self._on_url_text_changed)
        self.url_text.connect("activate", self._on_activate)

        self._liststore = gtk.ListStore(gobject.TYPE_STRING, 
                                        gobject.TYPE_STRING)
        self.completion = gtk.EntryCompletion()
        self.completion.connect("match-selected", self._on_completion_match)
        self.completion.set_match_func(self._match_func)
        self.completion.set_model(self._liststore)
        self.completion.set_text_column(0)
        self.url_text.set_completion(self.completion)
        self._ignore_text = False

        #self.use_text_check = gtk.CheckButton("_use text as url")
        #vbox.pack_start(self.use_text_check, False, False, 0)
        #self.use_text_check.connect("toggled", self._on_use_text_toggled)
        #self.use_text = self.use_text_check.get_active()

        if not self.active:
            self.hide()
            

    def set_search_nodes(self, search):
        self.search_nodes = search


    def _match_func(self, completion, key_string, iter):
        return True

    def _on_url_text_changed(self, url_text):

        if not self._ignore_text:
            self.update_completion()


    def update_completion(self):

        text = unicode_gtk(self.url_text.get_text())

        self._liststore.clear()
        if self.search_nodes and len(text) > 0:
            results = self.search_nodes(text)[:10]
            for nodeid, title in results:
                self._liststore.append([title, nodeid])
        
        

    def _on_completion_match(self, completion, model, iter):
        
        url = get_node_url(model[iter][1])
        
        self._ignore_text = True
        self.url_text.set_text(url)
        self._ignore_text = False
        self.dismiss(True)


    def _on_use_text_toggled(self, check):
        self.use_text = check.get_active()

        if self.use_text and self.current_url is not None:
            self.url_text.set_text(self.current_url)
            self.url_text.set_sensitive(False)
            self.set_url()
        else:
            self.url_text.set_sensitive(True)
    
    def _on_url_text_done(self, widget, event):
        self.set_url()

    def _on_url_text_start(self, widget, event):

        if self.textview:
            tag, start, end = self.textview.get_link()
            if tag:
                self.textview.get_buffer().select_range(start, end)
                self.update_completion()
            else:
                self.dismiss(False)
                

    def set_url(self):

        if self.textview is None:
            return
        
        url = unicode_gtk(self.url_text.get_text())
        tag, start, end = self.textview.get_link()
        
        if start is not None:
            if url == "":
                self.textview.set_link(None, start, end)
            elif tag.get_href() != url:
                self.textview.set_link(url, start, end)
                              

    def on_font_change(self, editor, font):
        """Callback for when font changes under richtext cursor"""
        
        if font.link:
            self.active = True
            self.url_text.set_width_chars(-1)
            self.show()
            self.align.show_all()
            self.current_url = font.link.get_href()
            self._ignore_text = True
            self.url_text.set_text(self.current_url)
            self._ignore_text = False

            if self.textview:
                gobject.idle_add(lambda :
                self.textview.scroll_mark_onscreen(
                    self.textview.get_buffer().get_insert()))
            
        elif self.active:
            self.set_url()            
            self.active = False
            self.hide()
            self.current_url = None
            self.url_text.set_text("")
        

    def edit(self):

        if self.active:
            self.url_text.select_region(0, -1)
            self.url_text.grab_focus()

            if self.textview:
                tag, start, end = self.textview.get_link()
                if start:
                    self.textview.get_buffer().select_range(start, end)

    def _on_activate(self, entry):
        self.dismiss(True)


    def _on_key_press_event(self, widget, event):

        if event.keyval == gtk.keysyms.Escape:
            self.dismiss(False)
            

    def dismiss(self, set_url):
        
        if self.textview is None:
            return
        
        tag, start, end = self.textview.get_link()
        if end:
            if set_url:
                self.set_url()
            #self.textview.get_buffer().place_cursor(end)
        else:
            # DEBUG
            #print "NO LINK"
            pass

        self.textview.grab_focus()
