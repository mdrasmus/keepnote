"""

    KeepNote
    Richtext buffer base class

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

import sys

# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk


# import textbuffer tools
from .textbuffer_tools import \
     get_paragraph, \
     get_paragraphs_selected

from .undo_handler import \
     UndoHandler, \
     Action, \
     InsertAction, \
     DeleteAction, \
     InsertChildAction, \
     TagAction


# richtext imports
from .richtextbase_tags import \
     RichTextBaseTagTable, \
     RichTextTagClass, \
     RichTextTag



def add_child_to_buffer(textbuffer, it, anchor):
    textbuffer.add_child(it, anchor)



#=============================================================================

class RichTextAnchor (gtk.TextChildAnchor):
    """Base class of all anchor objects in a RichTextView"""
    
    def __init__(self):
        gtk.TextChildAnchor.__init__(self)
        self._widgets = {} #None: None}
        self._buffer = None

    def add_view(self, view):
        return None
    
    def get_widget(self, view=None):
        return self._widgets[view]

    def get_all_widgets(self):
        return self._widgets

    def show(self):
        for widget in self._widgets.itervalues():
            if widget:
                widget.show()

    def set_buffer(self, buf):
        self._buffer = buf

    def get_buffer(self):
        return self._buffer
    
    def copy(self):
        anchor = RichTextAnchor()
        anchor.set_buffer(self._buffer)
        return anchor
    
    def highlight(self):
        for widget in self._widgets.itervalues():
            if widget:
                widget.highlight()
    
    def unhighlight(self):
        for widget in self._widgets.itervalues():
            if widget:
                widget.unhighlight()

gobject.type_register(RichTextAnchor)
gobject.signal_new("selected", RichTextAnchor, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())
gobject.signal_new("activated", RichTextAnchor, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())
gobject.signal_new("popup-menu", RichTextAnchor, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (int, object))
gobject.signal_new("init", RichTextAnchor, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())




class RichTextBaseBuffer (gtk.TextBuffer):
    """Basic RichTextBuffer with the following features
    
        - maintains undo/redo stacks
    """

    def __init__(self, tag_table=RichTextBaseTagTable()):
        gtk.TextBuffer.__init__(self, tag_table)
        tag_table.add_textbuffer(self)

        # undo handler
        self._undo_handler = UndoHandler(self)
        self._undo_handler.after_changed.add(self.on_after_changed)
        self.undo_stack = self._undo_handler.undo_stack


        # insert mark tracking
        self._insert_mark = self.get_insert()
        self._old_insert_mark = self.create_mark(
            None, self.get_iter_at_mark(self._insert_mark), True)

        
        self._user_action_ending = False
        self._noninteractive = 0

        # setup signals
        self._signals = [

            # local events            
            self.connect("begin_user_action", self._on_begin_user_action),
            self.connect("end_user_action", self._on_end_user_action),
            self.connect("mark-set", self._on_mark_set),
            self.connect("insert-text", self._on_insert_text),
            self.connect("insert-child-anchor", self._on_insert_child_anchor),
            self.connect("apply-tag", self._on_apply_tag),
            self.connect("remove-tag", self._on_remove_tag),
            self.connect("delete-range", self._on_delete_range),

            # undo handler events
            self.connect("insert-text", self._undo_handler.on_insert_text),
            self.connect("delete-range", self._undo_handler.on_delete_range),
            self.connect("insert-pixbuf", self._undo_handler.on_insert_pixbuf),
            self.connect("insert-child-anchor", self._undo_handler.on_insert_child_anchor),
            self.connect("apply-tag", self._undo_handler.on_apply_tag),
            self.connect("remove-tag", self._undo_handler.on_remove_tag),
            self.connect("changed", self._undo_handler.on_changed)
            
            ]



    def block_signals(self):
        """Block all signal handlers"""
        for signal in self._signals:
            self.handler_block(signal)
        self.undo_stack.suppress()

    
    def unblock_signals(self):
        """Unblock all signal handlers"""
        for signal in self._signals:
            self.handler_unblock(signal)
        self.undo_stack.resume()
        self.undo_stack.reset()
   

    def clear(self, clear_undo=False):
        """Clear buffer contents"""
        
        start = self.get_start_iter()
        end = self.get_end_iter()

        if clear_undo:
            self.undo_stack.suppress()

        self.begin_user_action()
        self.remove_all_tags(start, end)
        self.delete(start, end)
        self.end_user_action()

        if clear_undo:
            self.undo_stack.resume()
            self.undo_stack.reset()


    def get_insert_iter(self):
        """Return TextIter for insert point"""
        return self.get_iter_at_mark(self.get_insert())


    #==========================================================
    # restrict cursor and insert

    def is_insert_allowed(self, it, text=""):
        """Check that insert is allowed at TextIter 'it'"""
        return it.can_insert(True)


    def is_cursor_allowed(self, it):
        """Returns True if cursor is allowed at TextIter 'it'"""
        return True
    

    #======================================
    # child widgets

    def add_child(self, it, child):
        """Add TextChildAnchor to buffer"""
        pass

    def update_child(self, action):
        
        if isinstance(action, InsertChildAction):
            # set buffer of child
            action.child.set_buffer(self)
        

    #======================================
    # selection callbacks
    
    def on_selection_changed(self):
        pass


    #=========================================================
    # paragraph change callbacks
    
    def on_paragraph_split(self, start, end):
        pass

    def on_paragraph_merge(self, start, end):
        pass

    def on_paragraph_change(self, start, end):
        pass


    def update_paragraphs(self, action):

        if isinstance(action, InsertAction):

            # detect paragraph spliting
            if "\n" in action.text:
                par_start = self.get_iter_at_offset(action.pos)
                par_end = par_start.copy()
                par_start.backward_line()
                par_end.forward_chars(action.length)
                par_end.forward_line()
                self.on_paragraph_split(par_start, par_end)


        elif isinstance(action, DeleteAction):

            # detect paragraph merging
            if "\n" in action.text:
                par_start, par_end = get_paragraph(
                    self.get_iter_at_offset(action.start_offset))
                self.on_paragraph_merge(par_start, par_end)

    #==================================
    # tag apply/remove

    '''
    def apply_tag(self, tag, start, end):
        if isinstance(tag, RichTextTag):
            tag.on_apply()
        gtk.TextBuffer.apply_tag(self, tag, start, end)
        
        '''

    def remove_tag(self, tag, start, end):
        #assert self.get_tag_table().lookup(tag.get_property("name")) is not None, tag.get_property("name")
        gtk.TextBuffer.remove_tag(self, tag, start, end)



    #===========================================================
    # callbacks
    
    def _on_mark_set(self, textbuffer, it, mark):
        """Callback for mark movement"""

        if mark is self._insert_mark:

            # if cursor is not allowed here, move it back
            old_insert = self.get_iter_at_mark(self._old_insert_mark)
            if not self.get_iter_at_mark(mark).equal(old_insert) and \
               not self.is_cursor_allowed(it):
                self.place_cursor(old_insert)
                return
            
            # when cursor moves, selection changes
            self.on_selection_changed()

            # keep track of cursor position
            self.move_mark(self._old_insert_mark, it)



    def _on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""

        # NOTE: GTK does not give us a proper UTF string, so fix it
        text = unicode(text, "utf_8")
        length = len(text)
        
        # check to see if insert is allowed
        if textbuffer.is_interactive() and \
           not self.is_insert_allowed(it, text):
            textbuffer.stop_emission("insert_text")
            

    def _on_insert_child_anchor(self, textbuffer, it, anchor):
        """Callback for inserting a child anchor"""

        if not self.is_insert_allowed(it, ""):
            self.stop_emission("insert_child_anchor")
        
    def _on_apply_tag(self, textbuffer, tag, start, end):
        """Callback for tag apply"""

        if not isinstance(tag, RichTextTag):
            # do not process tags that are not rich text
            # i.e. gtkspell tags (ignored by undo/redo)
            return

        if tag.is_par_related():
            self.on_paragraph_change(start, end)

    
    def _on_remove_tag(self, textbuffer, tag, start, end):
        """Callback for tag remove"""

        if not isinstance(tag, RichTextTag):
            # do not process tags that are not rich text
            # i.e. gtkspell tags (ignored by undo/redo)
            return
        
        if tag.is_par_related():
            self.on_paragraph_change(start, end)


    def _on_delete_range(self, textbuffer, start, end):
        pass


    def on_after_changed(self, action):
        """
        Callback after content change has occurred

        Fix up textbuffer to restore consistent state (paragraph tags,
        current font application)
        """
        
        
        self.begin_user_action()
        
        self.update_current_tags(action)
        self.update_paragraphs(action)
        self.update_child(action)
        
        self.end_user_action()


    #==================================================================
    # records whether text insert is currently user interactive, or is
    # automated
        

    def begin_noninteractive(self):
        """Begins a noninteractive mode"""
        self._noninteractive += 1

    def end_noninteractive(self):
        """Ends a noninteractive mode"""
        self._noninteractive -= 1

    def is_interactive(self):
        """Returns True when insert is currently interactive"""
        return self._noninteractive == 0


    #=====================================================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        self.begin_noninteractive()
        self.undo_stack.undo()
        self.end_noninteractive()
        
    def redo(self):
        """Redo the last action in the RichTextView"""
        self.begin_noninteractive()        
        self.undo_stack.redo()
        self.end_noninteractive()
    
    def _on_begin_user_action(self, textbuffer):
        """Begin a composite undo/redo action"""
        
        self.undo_stack.begin_action()

    def _on_end_user_action(self, textbuffer):
        """End a composite undo/redo action"""
        
        if not self.undo_stack.is_in_progress() and \
           not self._user_action_ending:
            self._user_action_ending = True
            self.emit("ending-user-action")
            self._user_action_ending = False
        self.undo_stack.end_action()


gobject.type_register(RichTextBaseBuffer)
gobject.signal_new("ending-user-action", RichTextBaseBuffer, 
                   gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())

