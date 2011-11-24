"""

    KeepNote
    Font handler for RichText buffer.

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
import gtk, gobject, pango
from gtk import gdk


# import textbuffer tools
from .textbuffer_tools import \
     iter_buffer_contents, \
     buffer_contents_iter_to_offset, \
     normalize_tags, \
     insert_buffer_contents, \
     buffer_contents_apply_tags, \
     move_to_start_of_line, \
     move_to_end_of_line, \
     get_paragraph, \
     paragraph_iter, \
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





#=============================================================================
# fonts buffer


class RichTextBaseFont (object):
    """Class for representing a font in a simple way"""
    
    def __init__(self):
        pass


    def set_font(self, attr, tags, current_tags, tag_table):
        pass



class FontHandler (gobject.GObject):
    """Basic RichTextBuffer with the following features
    
        - manages "current font" behavior
    """
    
    def __init__(self, textbuffer):
        gobject.GObject.__init__(self)

        self._buf = textbuffer
        self._current_tags = []
        self._default_attr = gtk.TextAttributes()
        self._font_class = RichTextBaseFont

        self._insert_mark = self._buf.get_insert()
        self._buf.connect("mark-set", self._on_mark_set)

    #==============================================================
    # Tag manipulation    

    def update_current_tags(self, action):
        """Check if current tags need to be applied due to action"""

        self._buf.begin_user_action()

        if isinstance(action, InsertAction):

            # apply current style to inserted text if inserted text is
            # at cursor            
            if action.cursor_insert and len(action.current_tags) > 0:
                it = self._buf.get_iter_at_offset(action.pos)
                it2 = it.copy()
                it2.forward_chars(action.length)

                for tag in action.current_tags:
                    self._buf.apply_tag(tag, it, it2)

        self._buf.end_user_action()


    def _on_mark_set(self, textbuffer, it, mark):

        if mark is self._insert_mark:

            # if cursor at startline pick up opening tags,
            # otherwise closing tags
            opening = it.starts_line()
            self.set_current_tags(
                [x for x in it.get_toggled_tags(opening)
                 if isinstance(x, RichTextTag) and
                 x.can_be_current()])
        

    def set_default_attr(self, attr):
        self._default_attr = attr

    def get_default_attr(self):
        return self._default_attr
 

    def get_current_tags(self):
        """Returns the currently active tags"""
        return self._current_tags

    def set_current_tags(self, tags):
        """Sets the currently active tags"""
        self._current_tags = list(tags)
        self.emit("font-change", self.get_font())
    

    def can_be_current_tag(self, tag):
        return isinstance(tag, RichTextTag) and tag.can_be_current()
        

    def toggle_tag_selected(self, tag, start=None, end=None):
        """Toggle tag in selection or current tags"""

        self._buf.begin_user_action()

        if start is None:
            it = self._buf.get_selection_bounds()
        else:
            it = [start, end]

        # toggle current tags
        if self.can_be_current_tag(tag):
            if tag not in self._current_tags:
                self.clear_current_tag_class(tag)
                self._current_tags.append(tag)
            else:
                self._current_tags.remove(tag)            

        # update region
        if len(it) == 2:
            if not it[0].has_tag(tag):
                self.clear_tag_class(tag, it[0], it[1])
                self._buf.apply_tag(tag, it[0], it[1])
            else:
                self._buf.remove_tag(tag, it[0], it[1])
        
        self._buf.end_user_action()

        self.emit("font-change", self.get_font())



    def apply_tag_selected(self, tag, start=None, end=None):
        """Apply tag to selection or current tags"""
        
        self._buf.begin_user_action()

        if start is None:
            it = self._buf.get_selection_bounds()
        else:
            it = [start, end]
        
        # update current tags
        if self.can_be_current_tag(tag):
            if tag not in self._current_tags:
                self.clear_current_tag_class(tag)
                self._current_tags.append(tag)        

        # update region
        if len(it) == 2:
            self.clear_tag_class(tag, it[0], it[1])
            self._buf.apply_tag(tag, it[0], it[1])
        self._buf.end_user_action()

        self.emit("font-change", self.get_font())


    def remove_tag_selected(self, tag, start=None, end=None):
        """Remove tag from selection or current tags"""

        self._buf.begin_user_action()

        if start is None:
            it = self._buf.get_selection_bounds()
        else:
            it = [start, end]
        
        # no selection, remove tag from current tags
        if tag in self._current_tags:
            self._current_tags.remove(tag)

        # update region
        if len(it) == 2:
            self._buf.remove_tag(tag, it[0], it[1])
        self._buf.end_user_action()

        self.emit("font-change", self.get_font())


    def remove_tag_class_selected(self, tag, start=None, end=None):
        """Remove all tags of a class from selection or current tags"""

        self._buf.begin_user_action()

        if start is None:
            it = self._buf.get_selection_bounds()
        else:
            it = [start, end]
        
        # no selection, remove tag from current tags
        self.clear_current_tag_class(tag)        

        # update region
        if len(it) == 2:
            self.clear_tag_class(tag, it[0], it[1])
        self._buf.end_user_action()

        self.emit("font-change", self.get_font())

    
    def clear_tag_class(self, tag, start, end):
        """Remove all tags of the same class as 'tag' in region (start, end)"""

        cls = self._buf.tag_table.get_class_of_tag(tag)
        if cls is not None and cls.exclusive:
            for tag2 in cls.tags:
                self._buf.remove_tag(tag2, start, end)

        self.emit("font-change", self.get_font())



    def clear_current_tag_class(self, tag):
        """Remove all tags of the same class as 'tag' from current tags"""
        
        cls = self._buf.tag_table.get_class_of_tag(tag)
        if cls is not None and cls.exclusive:
            self._current_tags = [x for x in self._current_tags
                                  if x not in cls.tags]
            

    
    #===========================================================
    # Font management
    
    def get_font_class(self):
        return self._font_class

    def set_font_class(self, font_class):
        self._font_class = font_class


    def get_font(self, font=None):
        """Returns the active font under the cursor"""

        # get iter for retrieving font
        it2 = self._buf.get_selection_bounds()
        
        if len(it2) == 0:
            it = self._buf.get_iter_at_mark(self._buf.get_insert())
        else:
            it = it2[0]
            it.forward_char()
        
        # create a set that is fast for quering the existance of tags
        current_tags = set(self._current_tags)        
        
        # get the text attributes and font at the iter
        attr = gtk.TextAttributes()
        self._default_attr.copy_values(attr)
        it.get_attributes(attr)
        tags = it.get_tags()
        
        # create font object and return
        if font is None:
            font = self.get_font_class()()
        
        font.set_font(attr, tags, current_tags, self._buf.tag_table)
        return font




gobject.type_register(FontHandler)
gobject.signal_new("font-change", FontHandler, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))
