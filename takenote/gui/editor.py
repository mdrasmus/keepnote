"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    Editor widget in main window
"""



# python imports
import sys, os

# pygtk imports
import pygtk
pygtk.require('2.0')
from gtk import gdk
import gtk.glade
import gobject

# takenote imports
import takenote
from takenote.notebook import \
     NoteBookError, \
     NoteBookVersionError
from takenote import notebook as notebooklib
from takenote.gui import richtext
from takenote.gui.richtext import RichTextView, RichTextIO, RichTextError


# TODO: may need to update fonts on page change


class TakeNoteEditor (gtk.VBox):

    def __init__(self):
        gtk.VBox.__init__(self, False, 0)
        self._notebook = None
        
        # state
        self._textview = RichTextView()    # textview
        self._page = None                  # current NoteBookPage
        self._page_scrolls = {}            # remember scroll in each page
        self._queued_scroll = None
        self._textview_io = RichTextIO()

        
        self._sw = gtk.ScrolledWindow()
        self._sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self._sw.set_shadow_type(gtk.SHADOW_IN)       
        self._sw.add(self._textview)
        self.pack_start(self._sw)
        
        self._textview.connect("font-change", self._on_font_callback)
        self._textview.connect("modified", self._on_modified_callback)
        self._textview.connect("child-activated", self._on_child_activated)
        self._textview.connect("loaded", self._on_loaded)
        self._textview.disable()
        self._sw.get_vadjustment().connect("value-changed", self._on_scroll)
        #self._sw.get_vadjustment().connect("changed", self._on_scroll_setup)
        #self._textviews[-1].connect("show", self._on_scroll_init)
        self.show_all()


    def set_notebook(self, notebook):
        """Set notebook for editor"""

        # remove listener for old notebook
        if self._notebook:
            self._notebook.node_changed.remove(self._on_notebook_changed)

        # set new notebook
        self._notebook = notebook

        if self._notebook:
            # add listener and read default font
            self._notebook.node_changed.add(self._on_notebook_changed)
            self._textview.set_default_font(self._notebook.pref.default_font)
        else:
            # no new notebook, clear the view
            self.clear_view()

    def _on_notebook_changed(self, node, recurse):
        self._textview.set_default_font(self._notebook.pref.default_font)
    
    def _on_font_callback(self, textview, font):
        self.emit("font-change", font)
    
    def _on_modified_callback(self, textview, modified):
        self.emit("modified", self._page, modified)

    def _on_child_activated(self, textview, child):
        self.emit("child-activated", textview, child)

    def _on_loaded(self, textview):
        return
        #if self._queued_scroll is not None:
        #    print "set", self._queued_scroll
        #    self._sw.get_vadjustment().set_value(self._queued_scroll)
        #    #self._queued_scroll = None

                            
    
    def get_textview(self):
        return self._textview
    

    def _on_scroll(self, adjust):
        if self._page:
            self._page_scrolls[self._page] = adjust.get_value()


    def _on_scroll_setup(self, adjust):
        print "setup"


    def _on_scroll_init(self, widget):
        print "init"

        
    def is_focus(self):
        return self._textview.is_focus()


    def clear_view(self):
        self._page = None
        self._textview.disable()
    
    def view_pages(self, pages):
        """View a page"""
        
        # TODO: generalize to multiple pages
        assert len(pages) <= 1

        self.save()
        
        if len(pages) == 0:
            
            self.clear_view()
                
        else:
            page = pages[0]
            
            if page.is_page():
                self._page = page
                self._textview.enable()
            
                try:
                    self._queued_scroll = self._page_scrolls.get(
                        self._page, None)
                    #print self._queued_scroll

                    #print "loading"
                    self._textview_io.load(self._textview,
                                           self._textview.get_buffer(),
                                           self._page.get_data_file())
                    #print "done loading"
                    
                except RichTextError, e:
                    self.clear_view()                
                    self.emit("error", e.msg, e)
                except Exception, e:
                    self.clear_view()
                    self.emit("error", "Unknown error", e)
            else:
                self.clear_view()
                
    
    def save(self):
        """Save the loaded page"""
        
        if self._page is not None and \
           self._page.is_valid() and \
           self._textview.is_modified():

            try:
                self._textview_io.save(self._textview.get_buffer(),
                                       self._page.get_data_file(),
                                       self._page.get_title())
            except RichTextError, e:
                self.emit("error", e.msg, e)
                return
            
            self._page.set_attr_timestamp("modified")
            
            try:
                self._page.save()
            except NoteBookError, e:
                self.emit("error", e.msg, e)
    
    def save_needed(self):
        """Returns True if textview is modified"""
        return self._textview.is_modified()


# add new signals to TakeNoteEditor
gobject.type_register(TakeNoteEditor)
gobject.signal_new("modified", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, bool))
gobject.signal_new("font-change", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object,))
gobject.signal_new("error", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (str, object))
gobject.signal_new("child-activated", TakeNoteEditor, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, object))

