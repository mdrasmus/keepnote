
# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
from takenote.undo import UndoStack

# import textbuffer tools
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
     RichTextBulletTag, \
     color_to_string


# TODO: fix bug with spell check interferring with underline tags

# these tags will not be enumerated by iter_buffer_contents
IGNORE_TAGS = set(["gtkspell-misspelled"])

# default maximum undo levels
MAX_UNDOS = 100


def add_child_to_buffer(textbuffer, it, anchor):
    textbuffer.add_child(it, anchor)


#=============================================================================
# buffer paragraph navigation

# TODO: this might go into textbuffer_tools

def move_to_start_of_line(it):
    """Move a TextIter it to the start of a paragraph"""
    
    if not it.starts_line():
        if it.get_line() > 0:
            it.backward_line()
            it.forward_line()
        else:
            it = it.get_buffer().get_start_iter()
    return it

def move_to_end_of_line(it):
    """Move a TextIter it to the start of a paragraph"""
    it.forward_line()
    return it

def get_paragraph(it):
    """Get iters for the start and end of the paragraph containing 'it'"""
    start = it.copy()
    end = it.copy()

    start = move_to_start_of_line(start)
    end.forward_line()
    return start, end

class paragraph_iter (object):
    """Iterate through the paragraphs of a TextBuffer"""

    def __init__(self, buf, start, end):
        self.buf = buf
        self.pos = start
        self.end = end
    
        # create marks that survive buffer edits
        self.pos_mark = buf.create_mark(None, self.pos, True)
        self.end_mark = buf.create_mark(None, self.end, True)

    def __del__(self):
        if self.pos_mark is not None:
            self.buf.delete_mark(self.pos_mark)
            self.buf.delete_mark(self.end_mark)

    def __iter__(self):
        while self.pos.compare(self.end) == -1:
            self.buf.move_mark(self.pos_mark, self.pos)
            yield self.pos

            self.pos = self.buf.get_iter_at_mark(self.pos_mark)
            self.end = self.buf.get_iter_at_mark(self.end_mark)
            if not self.pos.forward_line():
                break

        # cleanup marks
        self.buf.delete_mark(self.pos_mark)
        self.buf.delete_mark(self.end_mark)

        self.pos_mark = None
        self.end_mark = None

        
def get_paragraphs_selected(buf):
    """Get start and end of selection rounded to nears paragraph boundaries"""
    sel = buf.get_selection_bounds()
    
    if not sel:
        start, end = get_paragraph(buf.get_iter_at_mark(buf.get_insert()))
    else:
        start = move_to_start_of_line(sel[0])
        end = move_to_end_of_line(sel[1])
    return start, end


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
    
    def __init__(self, textbuffer, pos, text, length, cursor_insert=False):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.current_tags = list(textbuffer.get_current_tags())
        self.pos = pos
        self.text = text
        self.length = length
        self.cursor_insert = cursor_insert
        #assert len(self.text) == self.length

        
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

        #assert start.get_slice(end) == self.text, \
        #       (start.get_slice(end), self.text)
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


    def set_font(self, attr, tags, current_tags, tag_table):
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
                     tag_table.lookup("bold") in current_tags or
                     weight == pango.WEIGHT_BOLD,
                     "italic": 
                     tag_table.lookup("italic") in current_tags or
                     style == pango.STYLE_ITALIC,
                     "underline":
                     tag_table.lookup("underline") in current_tags or
                     attr.underline == pango.UNDERLINE_SINGLE,
                     "tt":
                     tag_table.lookup("tt") in current_tags or
                     self.family == "Monospace",
                     "nowrap":
                     tag_table.lookup("nowrap") in current_tags or
                     attr.wrap_mode == gtk.WRAP_NONE}
        
        # set justification
        self.justify = RichTextJustifyTag.justify2name[attr.justification]
        
        # current tags override for family and size
        for tag in current_tags:
            if isinstance(tag, RichTextJustifyTag):
                self.justify = tag.get_justify()
            elif isinstance(tag, RichTextFamilyTag):
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

        self._insert_mark = self.get_insert()
        self._old_insert_mark = self.create_mark(
            None, self.get_iter_at_mark(self._insert_mark), True)

        # action state
        self._insert_text_mark = self.create_mark(None, self.get_start_iter(),
                                                  True)
        self._delete_text_mark = self.create_mark(None, self.get_start_iter(),
                                                  True)
        
        self._next_action = None
        self._current_tags = []
        self._user_action_ending = False
        self._noninteractive = 0

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

        self._default_attr = gtk.TextAttributes()


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

    def set_default_attr(self, attr):
        self._default_attr = attr

    def get_default_attr(self):
        return self._default_attr
    

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
            
            # if cursor startline pick up opening tags,
            # otherwise closing tags
            opening = it.starts_line()
            self._current_tags = [x for x in it.get_toggled_tags(opening)
                                  if isinstance(x, RichTextTag) and
                                  x.can_be_current()]

            # when cursor moves, selection changes
            self.on_selection_changed()

            # keep track of cursor position
            self.move_mark(self._old_insert_mark, it)
            
            # update UI for current fonts
            self.emit("font-change", self.get_font())
    
    
    def _on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""

        # NOTE: GTK does not give us a proper UTF string, so fix it
        text = unicode(text, "utf_8")
        length = len(text)

        # check to see if insert is allowed
        if self.is_interactive() and not self.is_insert_allowed(it, text):
            self.stop_emission("insert_text")
            return

        offset = it.get_offset()
        cursor_insert = (offset == 
                         self.get_iter_at_mark(self.get_insert()).get_offset())
        
        # start next action
        assert self._next_action is None
        self._next_action = InsertAction(self, offset, text, length,
                                         cursor_insert)
        self.move_mark(self._insert_text_mark, it)
        
        
    def _on_delete_range(self, textbuffer, start, end):
        """Callback for delete range"""
        # start next action
        assert self._next_action is None
        self._next_action = DeleteAction(self, start.get_offset(), 
                                         end.get_offset(),
                                         start.get_slice(end),
                                         self.get_iter_at_mark(
                                             self.get_insert()).get_offset())
        self.move_mark(self._delete_text_mark, start)

    
    def _on_insert_pixbuf(self, textbuffer, it, pixbuf):
        """Callback for inserting a pixbuf"""
        pass
    
    
    def _on_insert_child_anchor(self, textbuffer, it, anchor):
        """Callback for inserting a child anchor"""

        if not self.is_insert_allowed(it, ""):
            self.stop_emission("insert_child_anchor")
            return
        
        self._next_action = InsertChildAction(self, it.get_offset(), anchor)

    
    def _on_apply_tag(self, textbuffer, tag, start, end):
        """Callback for tag apply"""

        if not isinstance(tag, RichTextTag):
            # do not process tags that are not rich text
            # i.e. gtkspell tags (ignored by undo/redo)
            return

        if tag.is_par_related():
            self.on_paragraph_change(start, end)

        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), True)
        self.undo_stack.do(action.do, action.undo, False)
        self.set_modified(True)

    
    def _on_remove_tag(self, textbuffer, tag, start, end):
        """Callback for tag remove"""

        if not isinstance(tag, RichTextTag):
            # do not process tags that are not rich text
            # i.e. gtkspell tags (ignored by undo/redo)
            return

        if tag.is_par_related():
            self.on_paragraph_change(start, end)

        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), False)
        self.undo_stack.do(action.do, action.undo, False)
        self.set_modified(True)        
    
    
    def _on_changed(self, textbuffer):
        """Callback for buffer change"""

        # process actions that have changed the buffer
        if not self._next_action:
            return

        paragraph_action = None
        
        if isinstance(self._next_action, InsertAction):
            
            # apply current style to inserted text if inserted text is
            # at cursor
            if self._next_action.cursor_insert and \
               len(self._current_tags) > 0:
                it = self.get_iter_at_mark(self._insert_text_mark)
                it2 = it.copy()
                it2.forward_chars(self._next_action.length)

                # suppress undo stack for applying current tags
                # they are handled by the InsertAction
                # and do not need to be recorded separately as TagAction's
                self.undo_stack.suppress()
                for tag in self._next_action.current_tags:
                    self.apply_tag(tag, it, it2)
                self.undo_stack.resume()

            # detect paragraph spliting
            if "\n" in self._next_action.text:
                paragraph_action = "split"
                par_start = self.get_iter_at_mark(self._insert_text_mark)
                par_end = par_start.copy()
                par_start.backward_line()
                par_end.forward_chars(self._next_action.length)
                par_end.forward_line()

            
                
        elif isinstance(self._next_action, DeleteAction):
            
            # detect paragraph merging
            if "\n" in self._next_action.text:
                paragraph_action = "merge"
                par_start, par_end = get_paragraph(
                    self.get_iter_at_mark(self._delete_text_mark))
        
        self.begin_user_action()
        self.undo_stack.do(self._next_action.do, self._next_action.undo, False)
        
        if paragraph_action == "split":
            self.on_paragraph_split(par_start, par_end)
        elif paragraph_action == "merge":
            self.on_paragraph_merge(par_start, par_end)
        
        self._next_action = None            
        self.end_user_action()


    #==============================================================
    # Tag manipulation    

    
    def get_current_tags(self):
        """Returns the currently active tags"""
        return self._current_tags

    def set_current_tags(self, tags):
        """Sets the currently active tags"""
        self._current_tags = list(tags)            
    

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


    def remove_tag_class_selected(self, tag, start=None, end=None):
        """Remove all tags of a class from selection or current tags"""

        self.begin_user_action()

        if start is None:
            it = self.get_selection_bounds()
        else:
            it = [start, end]
        
        # no selection, remove tag from current tags
        self.clear_current_tag_class(tag)

        # update region
        if len(it) == 2:
            self.clear_tag_class(tag, it[0], it[1])
        self.end_user_action()

    
    def clear_tag_class(self, tag, start, end):
        """Remove all tags of the same class as 'tag' in region (start, end)"""

        # TODO: is there a faster way to do this?
        #   make faster mapping from tag to class

        cls = self.tag_table.get_class_of_tag(tag)
        if cls is not None and cls.exclusive:
            for tag2 in cls.tags:
                self.remove_tag(tag2, start, end)



    def clear_current_tag_class(self, tag):
        """Remove all tags of the same class as 'tag' from current tags"""
        
        cls = self.tag_table.get_class_of_tag(tag)
        if cls is not None and cls.exclusive:
            self._current_tags = [x for x in self._current_tags
                                  if x not in cls.tags]

    
    #===========================================================
    # Font management
    
    def get_font(self, font=None):
        """Returns the active font under the cursor"""
        
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
        self._default_attr.copy_values(attr)
        it.get_attributes(attr)
        tags = it.get_tags()

        # create font object and return
        if font is None:
            font = RichTextFont()
        font.set_font(attr, tags, current_tags, self.tag_table)
        return font


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

        #self._user_action = True
        self.undo_stack.begin_action()

    def _on_end_user_action(self, textbuffer):
        """End a composite undo/redo action"""
        
        if not self._user_action_ending:
            self._user_action_ending = True
            self.on_ending_user_action()
            self._user_action_ending = False
        self.undo_stack.end_action()


    def on_ending_user_action(self):
        """
        Callback for when user action is about to end
        Convenient for implementing extra actions that should be included
        in current user action
        """
        pass



gobject.type_register(RichTextBaseBuffer)
gobject.signal_new("font-change", RichTextBaseBuffer, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))
