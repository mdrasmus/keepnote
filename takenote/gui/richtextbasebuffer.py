# python imports
import sys, os, tempfile, re
import urllib2


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenote
from takenote.undo import UndoStack

from takenote.gui.textbuffer_tools import \
     iter_buffer_contents, \
     buffer_contents_iter_to_offset, \
     normalize_tags, \
     insert_buffer_contents, \
     buffer_contents_apply_tags

# import tags
from takenote.gui.richtext_tags import \
     RichTextTagTable, \
     RichTextTag, \
     RichTextModTag, \
     RichTextJustifyTag, \
     RichTextFamilyTag, \
     RichTextSizeTag, \
     RichTextFGColorTag, \
     RichTextBGColorTag, \
     RichTextIndentTag, \
     RichTextBulletTag


# TODO: fix bug with spell check interferring with underline tags

# these tags will not be enumerated by iter_buffer_contents
IGNORE_TAGS = set(["gtkspell-misspelled"])

# default maximum undo levels
MAX_UNDOS = 100


def add_child_to_buffer(textbuffer, it, anchor):
    textbuffer.add_child(it, anchor)

def color_to_string(color):
    redstr = hex(color.red)[2:]
    greenstr = hex(color.green)[2:]
    bluestr = hex(color.blue)[2:]

    while len(redstr) < 4:
        redstr = "0" + redstr
    while len(greenstr) < 4:
        greenstr = "0" + greenstr
    while len(bluestr) < 4:
        bluestr = "0" + bluestr

    return "#%s%s%s" % (redstr, greenstr, bluestr)




#=============================================================================
# RichTextBaseBuffer undoable actions

class Action (object):
    """A base class for undoable actions in RichTextBuffer"""
    
    def __init__(self):
        pass
    
    def do(self):
        pass
    
    def undo(self):
        pass


class InsertAction (Action):
    """Represents the act of inserting text"""
    
    def __init__(self, textbuffer, pos, text, length):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.current_tags = list(textbuffer.get_current_tags())
        self.pos = pos
        self.text = text
        self.length = length
        
    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.pos)
        self.textbuffer.place_cursor(start)

        # set current tags and insert text
        self.textbuffer.set_current_tags(self.current_tags)
        self.textbuffer.insert(start, self.text)
    
    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.pos)
        end = self.textbuffer.get_iter_at_offset(self.pos + self.length)
        self.textbuffer.place_cursor(start)
        self.textbuffer.delete(start, end)



class DeleteAction (Action):
    """Represents the act of deleting a region in a RichTextBuffer"""
    
    def __init__(self, textbuffer, start_offset, end_offset, text,
                 cursor_offset):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.text = text
        self.cursor_offset = cursor_offset
        self.contents = []        
        self._record_range()
    

    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.textbuffer.place_cursor(start)
        self._record_range()
        self.textbuffer.delete(start, end)


    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        
        self.textbuffer.begin_user_action()
        insert_buffer_contents(self.textbuffer, start, self.contents,
                               add_child=add_child_to_buffer)
        cursor = self.textbuffer.get_iter_at_offset(self.cursor_offset)
        self.textbuffer.place_cursor(cursor)
        self.textbuffer.end_user_action()

    
    def _record_range(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.contents = list(buffer_contents_iter_to_offset(
            iter_buffer_contents(self.textbuffer, start, end)))



class InsertChildAction (Action):
    """Represents the act of inserting a child object into a RichTextBuffer"""
    
    def __init__(self, textbuffer, pos, child):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.pos = pos
        self.child = child
        
    
    def do(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)

        # NOTE: this is RichTextBuffer specific
        self.child = self.child.copy()
        self.textbuffer.add_child(it, self.child)
        

    
    def undo(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.child = it.get_child_anchor()
        it2 = it.copy()
        it2.forward_char()
        self.textbuffer.delete(it, it2)
        


class TagAction (Action):
    """Represents the act of applying a tag to a region in a RichTextBuffer"""
    
    def __init__(self, textbuffer, tag, start_offset, end_offset, applied):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.tag = tag
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.applied = applied
        self.contents = []
        self._record_range()
        
    
    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self._record_range()
        if self.applied:
            self.textbuffer.apply_tag(self.tag, start, end)
        else:
            self.textbuffer.remove_tag(self.tag, start, end)

    
    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        if self.applied:
            self.textbuffer.remove_tag(self.tag, start, end)
        # undo for remove tag is simply to restore old tags
        buffer_contents_apply_tags(self.textbuffer, self.contents)
        
    
    def _record_range(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)

        # TODO: I can probably discard iter's.  Maybe make argument to
        # iter_buffer_contents
        self.contents = filter(lambda (kind, it, param): 
            kind in ("begin", "end") and param == self.tag,
            buffer_contents_iter_to_offset(
                iter_buffer_contents(self.textbuffer, start, end)))



#=============================================================================
# RichText Base

class RichTextFont (object):
    """Class for representing a font in a simple way"""
    
    def __init__(self):
        # TODO: remove hard-coding
        self.mods = {}
        self.justify = "left"
        self.family = "Sans"
        self.size = 10
        self.fg_color = ""
        self.bg_color = ""


    def set_font(self, attr, current_tags, tag_table):
        font = attr.font
                
        if font:
            # get font family
            self.family = font.get_family()

            # get size in points (get_size() returns pango units)
            PIXELS_PER_PANGO_UNIT = 1024
            self.size = font.get_size() // PIXELS_PER_PANGO_UNIT

            weight = font.get_weight()
            style = font.get_style()
        else:
            # TODO: replace this hard-coding
            self.family = "Sans"
            self.size = 10
            weight = pango.WEIGHT_NORMAL
            style = pango.STYLE_NORMAL
        
        
        # get colors
        self.fg_color = color_to_string(attr.fg_color)
        self.bg_color = color_to_string(attr.bg_color)
        
        # set modifications (current tags override)
        self.mods = {"bold":
                tag_table.bold_tag in current_tags or
                weight == pango.WEIGHT_BOLD,
                "italic": 
                tag_table.italic_tag in current_tags or
                style == pango.STYLE_ITALIC,
                "underline":
                tag_table.underline_tag in current_tags or
                attr.underline == pango.UNDERLINE_SINGLE,
                "nowrap":
                tag_table.no_wrap_tag in current_tags or
                attr.wrap_mode == gtk.WRAP_NONE}
        
        # set justification
        self.justify = tag_table.justify2name[attr.justification]
        
        # current tags override
        if tag_table.center_tag in current_tags:
            self.justify = "center"
        elif tag_table.right_tag in current_tags:
            self.justify = "right"
        elif tag_table.fill_tag in current_tags:
            self.justify = "fill"
        
        
        # current tags override for family and size
        for tag in current_tags:            
            if isinstance(tag, RichTextFamilyTag):
                self.family = tag.get_family()            
            elif isinstance(tag, RichTextSizeTag):
                self.size = tag.get_size()
            elif isinstance(tag, RichTextFGColorTag):
                self.fg_color = tag.get_color()
            elif isinstance(tag, RichTextBGColorTag):
                self.bg_color = tag.get_color()




class RichTextBaseBuffer (gtk.TextBuffer):
    """Basic RichTextBuffer with the following features
    
        - maintains undo/redo stacks
        - manages "current font" behavior
    """

    def __init__(self):
        gtk.TextBuffer.__init__(self, RichTextTagTable())
        self.undo_stack = UndoStack(MAX_UNDOS)

        # action state
        self._insert_mark = None
        self._next_action = None
        self._current_tags = []
        self._user_action = False

        # setup signals
        self._signals = [
            self.connect("begin_user_action", self._on_begin_user_action),
            self.connect("end_user_action", self._on_end_user_action),
            self.connect("mark-set", self._on_mark_set),
            self.connect("insert-text", self._on_insert_text),
            self.connect("delete-range", self._on_delete_range),
            self.connect("insert-pixbuf", self._on_insert_pixbuf),
            self.connect("insert-child-anchor", self._on_insert_child_anchor),
            self.connect("apply-tag", self._on_apply_tag),
            self.connect("remove-tag", self._on_remove_tag),
            self.connect("changed", self._on_changed)
            ]

        self.default_attr = gtk.TextAttributes()

    
    def get_current_tags(self):
        """Returns the currently active tags"""
        return self._current_tags

    def set_current_tags(self, tags):
        """Sets the currently active tags"""
        self._current_tags = list(tags)            
    
    def block_signals(self):
        """Block all signal handlers"""
        for signal in self._signals:
            self.handler_block(signal)
    
    
    def unblock_signals(self):
        """Unblock all signal handlers"""
        for signal in self._signals:
            self.handler_unblock(signal)

    def clear(self):
        """Clear buffer contents"""
        
        start = self.get_start_iter()
        end = self.get_end_iter()

        self.begin_user_action()
        self.remove_all_tags(start, end)
        self.delete(start, end)
        self.end_user_action()

    #======================================
    # stubs to overwrite in subclass

    def add_child(self, it, child):
        """Add TextChildAnchor to buffer"""
        pass
    
    def on_selection_changed(self):
        pass

    def on_ending_user_action(self):
        """
        Callback for when user action is about to end
        Convenient for implementing extra actions that should be included
        in current user action
        """
        pass
    


    #===========================================================
    # callbacks
    
    def _on_mark_set(self, textbuffer, it, mark):
        """Callback for mark movement"""

        if mark.get_name() == "insert":

            # pick up the last tags
            self._current_tags = [x for x in it.get_toggled_tags(False)
                                  if x.can_be_current()]

            self.on_selection_changed()
            
            # update UI for current fonts
            font = self.get_font()
            self.emit("font-change", font)
    
    
    def _on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""

        # check to make sure insert is not in front of bullet
        if it.starts_line() and self._indent.par_has_bullet(it):
            print "here"
            self.stop_emission("insert_text")
            return
        
        # start new action
        self._next_action = InsertAction(self, it.get_offset(), text, length)
        self._insert_mark = self.create_mark(None, it, True)
        
        
    def _on_delete_range(self, textbuffer, start, end):
        """Callback for delete range"""        

        # start next action
        self._next_action = DeleteAction(self, start.get_offset(), 
                                        end.get_offset(),
                                        start.get_slice(end),
                                        self.get_iter_at_mark(
                                            self.get_insert()).get_offset())
        
    
    def _on_insert_pixbuf(self, textbuffer, it, pixbuf):
        """Callback for inserting a pixbuf"""
        pass
    
    
    def _on_insert_child_anchor(self, textbuffer, it, anchor):
        """Callback for inserting a child anchor"""

        # TODO: is there a reason I use self._next_action?
        self._next_action = InsertChildAction(self, it.get_offset(), anchor)
    
    def _on_apply_tag(self, textbuffer, tag, start, end):
        """Callback for tag apply"""

        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), True)
        self.undo_stack.do(action.do, action.undo, False)
        self.set_modified(True)

    
    def _on_remove_tag(self, textbuffer, tag, start, end):
        """Callback for tag remove"""

        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), False)
        self.undo_stack.do(action.do, action.undo, False)
        self.set_modified(True)        
    
    
    def _on_changed(self, textbuffer):
        """Callback for buffer change"""

        paragraph_action = None

        if not self._next_action:
            return
        
        if isinstance(self._next_action, InsertAction):
            # apply current style to inserted text
            
            if len(self._current_tags) > 0:
                it = self.get_iter_at_mark(self._insert_mark)
                it2 = it.copy()
                it2.forward_chars(self._next_action.length)

                # TODO: could I suppress undo for these tags
                for tag in self._current_tags:
                    self.apply_tag(tag, it, it2)

                self.delete_mark(self._insert_mark)
                self._insert_mark = None

            if "\n" in self._next_action.text:
                paragraph_action = "split"

                par_start = self.get_iter_at_mark(self.get_insert())
                par_end = par_start.copy()
                
                par_start.backward_line()
                par_end.forward_chars(self._next_action.length)
                par_end.forward_line()
                par_end.backward_char()
            
                
        elif isinstance(self._next_action, DeleteAction):
            # deregister any deleted anchors
            
            for kind, offset, param in self._next_action.contents:
                if kind == "anchor":
                    self._anchors.remove(param[0])

            if "\n" in self._next_action.text:
                paragraph_action = "merge"
                par_start, par_end = self._indent.get_paragraph()
        
        
        self.begin_user_action()
        self.undo_stack.do(self._next_action.do, self._next_action.undo, False)
        
        if paragraph_action == "split":
            self._indent.on_paragraph_split(par_start, par_end)
        elif paragraph_action == "merge":
            self._indent.on_paragraph_merge(par_start, par_end)
        
        self._next_action = None            
        self.end_user_action()

    #==============================================================
    # Tag manipulation    

    def can_be_current_tag(self, tag):
        return isinstance(tag, RichTextTag) and tag.can_be_current()
        

    def toggle_tag_selected(self, tag, start=None, end=None):
        """Toggle tag in selection or current tags"""

        self.begin_user_action()

        if start is None:
            it = self.get_selection_bounds()
        else:
            it = [start, end]
        
        # no selection, toggle current tags
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
                self.apply_tag(tag, it[0], it[1])
            else:
                self.remove_tag(tag, it[0], it[1])
        
        self.end_user_action()


    def apply_tag_selected(self, tag, start=None, end=None):
        """Apply tag to selection or current tags"""
        
        self.begin_user_action()

        if start is None:
            it = self.get_selection_bounds()
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
            self.apply_tag(tag, it[0], it[1])
        self.end_user_action()


    def remove_tag_selected(self, tag, start=None, end=None):
        """Remove tag from selection or current tags"""

        self.begin_user_action()

        if start is None:
            it = self.get_selection_bounds()
        else:
            it = [start, end]
        
        # no selection, remove tag from current tags
        if tag in self._current_tags:
            self._current_tags.remove(tag)

        # update region
        if len(it) == 2:
            self.remove_tag(tag, it[0], it[1])
        self.end_user_action()

    
    def clear_tag_class(self, tag, start, end):
        """Remove all tags of the same class as 'tag' in region (start, end)"""

        # TODO: is there a faster way to do this?
        #   make faster mapping from tag to class
        
        for cls in self.tag_table.exclusive_classes:
            if tag in cls:
                for tag2 in cls:
                    self.remove_tag(tag2, start, end)



    def clear_current_tag_class(self, tag):
        """Remove all tags of the same class as 'tag' from current tags"""

        # TODO: is there a faster way to do this?
        #   make faster mapping from tag to class
        #   loop through tags in current tags instead of tag class

        for cls in self.tag_table.exclusive_classes:
            if tag in cls:
                for tag2 in cls:
                    if tag2 in self._current_tags:
                        self._current_tags.remove(tag2)

    
    #===========================================================
    # Font management
    
    def get_font(self, font=None):

        # TODO: add indent
        
        # get iter for retrieving font
        it2 = self.get_selection_bounds()
        
        if len(it2) == 0:
            it = self.get_iter_at_mark(self.get_insert())
        else:
            it = it2[0]
            it.forward_char()
        
        # create a set that is fast for quering the existance of tags
        current_tags = set(self._current_tags)        
        
        # get the text attributes and font at the iter
        attr = gtk.TextAttributes()
        self.default_attr.copy_values(attr)
        it.get_attributes(attr)

        # create font object and return
        if font is None:
            font = RichTextFont()
        font.set_font(attr, current_tags, self.tag_table)
        return font




    #=========================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        self.undo_stack.undo()
        
    def redo(self):
        """Redo the last action in the RichTextView"""    
        self.undo_stack.redo()
    
    def _on_begin_user_action(self, textbuffer):
        """Begin a composite undo/redo action"""

        self._user_action = True
        self.undo_stack.begin_action()

    def _on_end_user_action(self, textbuffer):
        """End a composite undo/redo action"""

        self.on_ending_user_action()        
        self._user_action = False
        self.undo_stack.end_action()


