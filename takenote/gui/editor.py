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
     NoteBookVersionError, \
     NoteBookDir, \
     NoteBookPage
from takenote import notebook as notebooklib
from takenote.gui import richtext
from takenote.gui.richtext import RichTextView, RichTextError




class TakeNoteEditor (gtk.VBox): #(gtk.Notebook):

    def __init__(self):
        #gtk.Notebook.__init__(self)
        gtk.VBox.__init__(self, False, 0)
        #self.set_scrollable(True)
        self._notebook = None
        
        # TODO: may need to update fonts on page change
        # TODO: add page reorder
        # TODO: add close button on labels
        
        # state
        self._textviews = []
        self._pages = []
        
        self.new_tab()
        self.show()

    def set_notebook(self, notebook):

        if self._notebook:
            self._notebook.node_changed.remove(self.on_notebook_changed)
        
        self._notebook = notebook

        if self._notebook:
            self._notebook.node_changed.add(self.on_notebook_changed)
            for view in self._textviews:                
                view.set_default_font(self._notebook.pref.default_font)
        else:
            self.clear_view()

    def on_notebook_changed(self, node, recurse):
        for view in self._textviews:
            view.set_default_font(self._notebook.pref.default_font)
        
    
    def on_font_callback(self, textview, font):
        self.emit("font-change", font)
    
    def on_modified_callback(self, page_num, modified):
        self.emit("modified", self._pages[page_num], modified)

    def on_child_activated(self, textview, child):
        self.emit("child-activated", textview, child)
    
    #def on_error_callback(self, widget, text, error):
    #    self.emit("error", text, error)
        
    
    def get_textview(self):
        #pos = self.get_current_tab()
        pos = 0
        
        if pos == -1:
            return None
        else:    
            return self._textviews[pos]
    
    
    def new_tab(self):
        self._textviews.append(RichTextView())

        if self._notebook:
            self._textviews[-1].set_default_font(self._notebook.pref.default_font)
        self._pages.append(None)
        
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.set_shadow_type(gtk.SHADOW_IN)       
        sw.add(self._textviews[-1])
        #self.append_page(sw, gtk.Label("(Untitled)"))
        self.pack_start(sw)
        self._textviews[-1].connect("font-change", self.on_font_callback)
        self._textviews[-1].connect("modified", lambda t, m:
            self.on_modified_callback(len(self._pages)-1, m))
        self._textviews[-1].connect("child-activated", self.on_child_activated)
        #self._textviews[-1].connect("error", self.on_error_callback)
        self._textviews[-1].disable()
        self._textviews[-1].show()
        sw.show()
        self.show()
        
    '''
    def close_tab(self, pos=None):
        if self.get_n_pages() <= 1:
            return
    
        if pos is None:
            pos = self.get_current_tab()
        
        self.save_tab(pos)

        del self._pages[pos]
        del self._textviews[pos]
        self.remove_page(pos)
    '''
    
    def get_n_pages(self):
        return 1
    
    def get_current_tab(self):
        return 0

    def is_focus(self):
        pos = self.get_current_tab()
        return self._textviews[pos].is_focus()

    def clear_view(self):
        pos = self.get_current_tab()
        self._pages[pos] = None
        self._textviews[pos].disable()
    
    def view_pages(self, pages):
        # TODO: generalize to multiple pages
        assert len(pages) <= 1

        
        if len(pages) == 0:
            self.save()
            if self.get_n_pages() > 0:
                self.clear_view()
                
        else:
            page = pages[0]
            
            if isinstance(page, NoteBookPage):
            
                self.save()
                if self.get_n_pages() == 0:
                    self.new_tab()
            
                pos = self.get_current_tab()
                self._pages[pos] = page
                self._textviews[pos].enable()
                #self.set_tab_label_text(self.get_children()[pos], 
                #                        self._pages[pos].get_title())
            
                try:
                    self._textviews[pos].load(self._pages[pos].get_data_file())
                except RichTextError, e:
                    self.clear_view()                
                    self.emit("error", e.msg, e)
                except Exception, e:
                    self.clear_view()
                    self.emit("error", "Unknown error", e)
            else:
                self.clear_view()
                
    
    def save(self):
        for pos in xrange(self.get_n_pages()):
            self.save_tab(pos)
            
    
    def save_tab(self, pos):
        if self._pages[pos] is not None and \
            self._pages[pos].is_valid() and \
            self._textviews[pos].is_modified():

            try:
                self._textviews[pos].save(self._pages[pos].get_data_file())
            except RichTextError, e:
                self.emit("error", e.msg, e)
                return
            
            self._pages[pos].set_modified_time()
            
            try:
                self._pages[pos].save()
            except NoteBookError, e:
                self.emit("error", e.msg, e)
    
    def save_needed(self):
        for textview in self._textviews:
            if textview.is_modified():
                return True
        return False

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

