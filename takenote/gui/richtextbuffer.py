


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
     iter_buffer_contents as iter_buffer_contents2, \
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

# string for bullet points
BULLET_STR = u"\u2022 "


#=============================================================================
# helper functions

def parse_utf(text):

    # TODO: lookup the standard way to do this
    
    if text[:2] in ('\xff\xfe', '\xfe\xff') or (
        len(text) > 1 and text[1] == '\x00') or (
        len(text) > 3 and text[3] == '\x00'):
        return text.decode("utf16")
    else:
        return unicode(text, "utf8")



def add_child_to_buffer(textbuffer, it, anchor):
    textbuffer.add_child(it, anchor)

def iter_buffer_contents(textbuffer, start=None, end=None,
                         ignore_tags=IGNORE_TAGS):
    return iter_buffer_contents2(textbuffer, start, end, ignore_tags)


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





class RichTextError (StandardError):
    """Class for errors with RichText"""

    # NOTE: this is only used for saving and loading in textview
    # should this stay here?
    
    def __init__(self, msg, error):
        StandardError.__init__(self, msg)
        self.msg = msg
        self.error = error
    
    def __str__(self):
        if self.error:
            return str(self.error) + "\n" + self.msg
        else:
            return self.msg


#=============================================================================
# RichText undoable actions

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
# RichText child objects


class RichTextAnchor (gtk.TextChildAnchor):
    """Base class of all anchor objects in a RichTextView"""
    
    def __init__(self):
        gtk.TextChildAnchor.__init__(self)
        self._widget = None
        self._buffer = None
    
    def get_widget(self):
        return self._widget

    def set_buffer(self, buf):
        self._buffer = buf
    
    def copy(slef):
        anchor = RichTextAnchor()
        anchor.set_buffer(self._buffer)
        return anchor
    
    def highlight(self):
        if self._widget:
            self._widget.highlight()
    
    def unhighlight(self):
        if self._widget:
            self._widget.unhighlight()

gobject.type_register(RichTextAnchor)
gobject.signal_new("selected", RichTextAnchor, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())
gobject.signal_new("activated", RichTextAnchor, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, ())
gobject.signal_new("popup-menu", RichTextAnchor, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (int, object))


class BaseWidget (object):
    """Widgets in RichTextBuffer must support this interface"""
    
    def __init__(self):
        pass
        
    def highlight(self):
        pass
    
    def unhighlight(self):
        pass


class RichTextSep (gtk.HSeparator, BaseWidget):
    """Separator widget for a Horizontal Rule"""
    def __init__(self):
        gtk.HSeparator.__init__(self)
        BaseWidget.__init__(self)
        self.modify_bg(gtk.STATE_NORMAL, gdk.Color(0, 0, 0))
        self.modify_fg(gtk.STATE_NORMAL, gdk.Color(0, 0, 0))
        self.connect("size-request", self.on_resize)

    def on_resize(self, sep, req):
        req.height = 10
        req.width = self.get_parent().get_allocation().width - 20
        
    

class RichTextHorizontalRule (RichTextAnchor):
    def __init__(self):
        gtk.TextChildAnchor.__init__(self)
        self._widget = RichTextSep()
        #width = 400
        #height = 1
        #color = 0 # black
        #padding = 5

        #pixbuf = gdk.Pixbuf(gdk.COLORSPACE_RGB, False, 8, width, height)
        #pixbuf.fill(color)
        #self._widget.set_from_pixbuf(pixbuf)
        #self._widget.img.set_padding(0, padding)
        self._widget.show()
    
    def get_widget(self):
        return self._widget
    
    def copy(slef):
        return RichTextHorizontalRule()
       

class BaseImage (gtk.EventBox, BaseWidget):
    """Subclasses gtk.Image to make an Image Widget that can be used within
       RichTextViewS"""

    def __init__(self, *args, **kargs):
        gtk.EventBox.__init__(self)
        BaseWidget.__init__(self)
        self._img = gtk.Image(*args, **kargs)
        self.add(self._img)

        # TODO: will this be configurable?
        # set to white background
        self.modify_bg(gtk.STATE_NORMAL, gdk.Color(65535, 65535, 65535))

        # gtk.STATE_ACTIVE
        # gtk.STATE_PRELIGHT
        # gtk.STATE_SELECTED
        # gtk.STATE_INSENSITIVE

    
    def highlight(self):
        self.drag_highlight()
    
    def unhighlight(self):
        self.drag_unhighlight()
    
    def set_from_pixbuf(self, pixbuf):
        self._img.set_from_pixbuf(pixbuf)
    
    def set_from_stock(self, stock, size):
        self._img.set_from_stock(stock, size)
    
    def show(self):
        gtk.EventBox.show(self)
        self._img.show()


# TODO: think about how a single anchor could manage multiple widgets in
# multiple textviews

class RichTextImage (RichTextAnchor):
    """An Image child widget in a RichTextView"""

    def __init__(self):
        RichTextAnchor.__init__(self)
        self._filename = None
        self._download = False
        self._widget = BaseImage()
        self._widget.connect("destroy", self._on_image_destroy)
        self._widget.connect("button-press-event", self._on_clicked)
        self._pixbuf = None
        self._pixbuf_original = None
        self._size = [None, None]
        self._buffer = None
        self._save_needed = False
        

    def is_valid(self):
        """Did the image successfully load an image"""
        return self._pixbuf is not None
    
    def set_filename(self, filename):
        """Sets the filename used for saving image"""
        self._filename = filename
    
    def get_filename(self):
        """Returns the filename used for saving image"""
        return self._filename

    def set_save_needed(self, save):
        """Sets whether image needs to be saved to disk"""
        self._save_needed = save

    def save_needed(self):
        """Returns True if image needs to be saved to disk"""
        return self._save_needed
    
    def set_from_file(self, filename):
        """Sets the image from a file"""
        
        if self._filename is None:
            self._filename = os.path.basename(filename)
        
        try:
            self._pixbuf_original = gdk.pixbuf_new_from_file(filename)
            
        except gobject.GError, e:
            # use missing image instead
            self._widget.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
            self._pixbuf_original = None
            self._pixbuf = None
        else:
            # successful image load, set its size
            self._pixbuf = self._pixbuf_original
            
            if self.is_size_set():
                self.scale(self._size[0], self._size[1], False)
            self._widget.set_from_pixbuf(self._pixbuf)


    def set_from_pixbuf(self, pixbuf, filename=None):
        """Set the image from a pixbuf"""
        
        if filename is not None:
            self._filename = filename
        self._pixbuf = pixbuf
        self._pixbuf_original = pixbuf

        if self.is_size_set():
            self.scale(self._size[0], self._size[1], False)
        self._widget.set_from_pixbuf(self._pixbuf)


    def get_original_pixbuf(self):
        """Returns the pixbuf of the image at its original size (no scaling)"""
        return self._pixbuf_original

                
    def get_size(self, actual_size=False):
        """Returns the size of the image

           actual_size -- if True, None values will be replaced by original size
        """
        
        if actual_size:
            if self._pixbuf_original is not None:
                w, h = self._size
                if w is None:
                    w = self._pixbuf_original.get_width()
                if h is None:
                    h = self._pixbuf_original.get_height()
                return [w, h]
            else:
                return [0, 0]
        else:
            return self._size

    def get_original_size(self):
        return [self._pixbuf_original.get_width(),
                self._pixbuf_original.get_height()]


    def is_size_set(self):
        return self._size[0] is not None or self._size[1] is not None
    

    def scale(self, width, height, set_widget=True):
        """Scale the image to a new width and height"""

        if not self.is_valid:
            return
        
        self._size = [width, height]

        
        if not self.is_size_set():
            # use original image size
            if self._pixbuf != self._pixbuf_original:
                self._pixbuf = self._pixbuf_original
                if self._pixbuf is not None:
                    self._widget.set_from_pixbuf(self._pixbuf)
        
        elif self._pixbuf_original is not None:
            # perform scaling
            
            width2 = self._pixbuf_original.get_width()
            height2 = self._pixbuf_original.get_height()
            
            if width is None:
                factor = height / float(height2)
                width = factor * width2
            if height is None:
                factor = width / float(width2)
                height = factor * height2
            
            self._pixbuf = self._pixbuf_original.scale_simple(
                width, height, gtk.gdk.INTERP_BILINEAR)

            if set_widget:
                self._widget.set_from_pixbuf(self._pixbuf)

        if self._buffer is not None:
            self._buffer.set_modified(True)


    
    def write(self, filename):
        """Write image to file"""
        f, ext = os.path.splitext(filename)
        ext = ext.replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
            
        self._pixbuf_original.save(filename, ext)
        self._save_needed = False
        
        
    def copy(self):
        """Returns a new copy of the image"""
        img = RichTextImage()
        img.set_filename(self._filename)
        img._size = self.get_size()
        
        if self._pixbuf:
            img.get_widget().set_from_pixbuf(self._pixbuf)
        else:
            img.get_widget().set_from_stock(gtk.STOCK_MISSING_IMAGE,
                                            gtk.ICON_SIZE_MENU)
        img._pixbuf = self._pixbuf
        img._pixbuf_original = self._pixbuf_original
        img.get_widget().show()
        return img

    def set_from_url(self, url, filename):
        """Set image by url"""
        
        # make local temp file
        f, imgfile = tempfile.mkstemp("", "takenote")
        os.close(f)
        
        # open url and download image
        infile = urllib2.urlopen(url)
        outfile = open(imgfile, "wb")
        outfile.write(infile.read())
        outfile.close()
        
        # set filename and image
        self.set_from_file(imgfile)
        self.set_filename(filename)

        # remove tempfile
        os.remove(imgfile)

        

    #==========================
    # GUI callbacks
    
    def _on_image_destroy(self, widget):
        self._widget = None
    
    def _on_clicked(self, widget, event):
        """Callback for when image is clicked"""
        
        if event.button == 1:
            # left click selects image
            self._widget.grab_focus()
            self.emit("selected")

            if event.type == gtk.gdk._2BUTTON_PRESS:
                # double left click activates image
                self.emit("activated")
            
            return True
        
        elif event.button == 3:
            # right click presents popup menu
            self.emit("selected")
            self.emit("popup-menu", event.button, event.time)
            return True



    

#=============================================================================
# RichText Fonts and Tags

class RichTextFont (object):
    """Class for representing a font in a simple way"""
    
    def __init__(self, mods, justify, family, size, fg_color, bg_color):
        self.mods = mods
        self.justify = justify
        self.family = family
        self.size = size
        self.fg_color = fg_color
        self.bg_color = bg_color


#=============================================================================
# RichTextBuffer


class RichTextBuffer (gtk.TextBuffer):
    """
    TextBuffer specialize for rich text editing

    - maintains undo/redo stacks
    - manages "current font" behavior
    - manages child widget actions
    - manages editing of indentation levels and bullet point lists
    """
    
    def __init__(self, textview=None):
        gtk.TextBuffer.__init__(self, RichTextTagTable())
        self.textview = textview
        self.undo_stack = UndoStack(MAX_UNDOS)
        
        # action state
        self._insert_mark = None
        self._next_action = None
        self._current_tags = []
        self._user_action = False

        # indentation
        self._indent_update = False
        self._indent_update_start = self.create_mark("indent_update_start",
                                                     self.get_start_iter(),
                                                     True)
        self._indent_update_end = self.create_mark("indent_update_end",
                                                   self.get_end_iter(),
                                                   False)
        self._bullet_mark = self.create_mark("bullet",
                                             self.get_start_iter(),
                                             True)


        # set of all anchors in buffer
        self._anchors = set()

        # anchors that still need to be added,
        # they are defferred because textview was not available at insert-time
        self._anchors_deferred = set() 
        
        # setup signals
        self.signals = [
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
        

    def set_textview(self, textview):
        self.textview = textview
    
    def get_textview(self):
        return self.textview
    
    def get_current_tags(self):
        """Returns the currently active tags"""
        return self._current_tags

    def set_current_tags(self, tags):
        """Sets the currently active tags"""
        self._current_tags = list(tags)            
    
    def block_signals(self):
        """Block all signal handlers"""
        for signal in self.signals:
            self.handler_block(signal)
    
    
    def unblock_signals(self):
        """Unblock all signal handlers"""
        for signal in self.signals:
            self.handler_unblock(signal)


    def clear(self):
        """Clear buffer contents"""
        
        start = self.get_start_iter()
        end = self.get_end_iter()

        self.begin_user_action()
        self.remove_all_tags(start, end)
        self.delete(start, end)
        self.end_user_action()

        self._anchors.clear()
        self._anchors_deferred.clear()


    def insert_contents(self, contents, it=None):
        """Inserts a content stream into the TextBuffer at iter 'it'"""

        if it is None:
            it = self.get_iter_at_mark(self.get_insert())

        self.begin_user_action()
        insert_buffer_contents(self, it,
                               contents,
                               add_child_to_buffer,
                               lookup_tag=lambda name:
                                   self.tag_table.lookup(name))
        self.end_user_action()


    def copy_contents(self, start, end):
        """Return a content stream for copying from iter start and end"""

        contents = iter(iter_buffer_contents(self, start, end, IGNORE_TAGS))

        # remove regions that can't be copied
        for item in contents:
            if item[0] == "begin" and not item[2].can_be_copied():
                end_tag = item[2]
                
                while not (item[0] == "end" and item[2] == end_tag):
                    item = contents.next()

                    if item[0] not in ("text", "anchor") and \
                       item[2] != end_tag:
                        yield item
                    
                continue

            yield item

    #======================================================
    # indentation methods/callbacks

    def indent(self, start=None, end=None):
        """Indent paragraph level"""
        self.change_indent(start, end, 1)


    def unindent(self, start=None, end=None):
        """Unindent paragraph level"""
        self.change_indent(start, end, -1)


    def change_indent(self, start, end, change):
        """Change indentation level"""
        
        # determine region
        if start is None or end is None:
            sel = self.get_selection_bounds()

            if not sel:
                start, end = self.get_paragraph()
            else:
                start, _ = self.get_paragraph(sel[0])
                _, end = self.get_paragraph(sel[1])

        self.begin_user_action()

        end_mark = self.create_mark(None, end, True)
        
        # loop through paragraphs
        pos = start
        while pos.compare(end) == -1:
            par_end = pos.copy()
            par_end.forward_line()
            indent, par_indent = self.get_indent(pos)

            if indent + change > 0:
                self.apply_tag_selected(
                    self.tag_table.lookup_indent(indent + change,
                                                 par_indent),
                    pos, par_end)
            elif indent > 0:
                # remove indent and possible bullets
                self.remove_tag(self.tag_table.lookup_indent(indent,
                                                             par_indent),
                                pos, par_end)                
                pos = self._remove_bullet(pos)
                end = self.get_iter_at_mark(end_mark)

            if not pos.forward_line():
                break

        self.end_user_action()

        self.delete_mark(end_mark)
        


    def toggle_bullet_list(self):
        """Toggle the state of a bullet list"""
        
        self.begin_user_action()

        # start indent if it is not present
        indent, par_type = self.get_indent()
        if indent == 0:
            indent = 1
            #self.indent()
        
        par_start, par_end = self.get_paragraph()

        if par_type != "none":
            par_type = "none"
        else:
            par_type = "bullet"

        # apply indent to whole paragraph
        indent_tag = self.tag_table.lookup_indent(indent, par_type)
        self.apply_tag_selected(indent_tag, par_start, par_end)
            
        self._queue_update_indentation(par_start, par_end)
        
        self.end_user_action()


    def _insert_bullet(self, par_start):
        """Insert a bullet point at the begining of the paragraph"""

        if self._par_has_bullet(par_start):
            return par_start
        
        self.begin_user_action()

        # insert text
        self.move_mark(self._bullet_mark, par_start)
        self.insert(par_start, BULLET_STR)

        # apply tag to just the bullet point
        par_start = self.get_iter_at_mark(self._bullet_mark)
        bullet_end = par_start.copy()
        bullet_end.forward_chars(len(BULLET_STR))
        bullet_tag = self.tag_table.bullet_tag
        self.apply_tag_selected(bullet_tag, par_start, bullet_end)

        self.end_user_action()

        return par_start

    def _remove_bullet(self, par_start):
        """Remove a bullet point from the paragraph"""

        self.begin_user_action()
        
        bullet_end = par_start.copy()
        bullet_end.forward_chars(len(BULLET_STR))
        self.move_mark(self._bullet_mark, par_start)

        if par_start.get_text(bullet_end) == BULLET_STR:            
            bullet_tag = self.tag_table.bullet_tag
            self.remove_tag(bullet_tag, par_start, bullet_end)

            self.delete(par_start, bullet_end)

        self.end_user_action()

        return self.get_iter_at_mark(self._bullet_mark)
 

    def _par_has_bullet(self, par_start):
        """Returns True if paragraph starts with bullet point"""
        bullet_end = par_start.copy()
        bullet_end.forward_chars(len(BULLET_STR))

        return par_start.get_text(bullet_end) == BULLET_STR


    def _on_paragraph_merge(self, start, end):
        """Callback for when paragraphs have merged"""
        self._queue_update_indentation(start, end)


    def _on_paragraph_split(self, start, end):
        """Callback for when paragraphs have split"""
        self._queue_update_indentation(start, end)


    def _queue_update_indentation(self, start, end):
        """Queues an indentation update"""
        
        if not self._indent_update:
            # first update
            self._indent_update = True
            self.move_mark(self._indent_update_start, start)
            self.move_mark(self._indent_update_end, end)
        else:
            # expand update region
            a = self.get_iter_at_mark(self._indent_update_start)
            b = self.get_iter_at_mark(self._indent_update_end)

            if start.compare(a) == -1:                
                self.move_mark(self._indent_update_start, start)

            if end.compare(b) == 1:
                self.move_mark(self._indent_update_end, end)


    def _update_indentation(self):
        """Ensure the indentation tags between start and end are up to date"""

        if self._indent_update:
            self._indent_update = False 

            # perfrom indentation update
            self.begin_user_action()
            #print "start"

            # fixup indentation tags
            # The general rule is that the indentation at the start of
            # each paragraph should determines the indentation of the rest
            # of the paragraph

            pos = self.get_iter_at_mark(self._indent_update_start)
            end = self.get_iter_at_mark(self._indent_update_end)

            end.forward_line()

            # move pos to start of line
            pos = self.move_to_start_of_line(pos)
            assert pos.starts_line(), "pos does not start line before"
            
            while pos.compare(end) == -1:
                assert pos.starts_line(), "pos does not start line"
                par_end = pos.copy()
                par_end.forward_line()
                indent_tag = self.get_indent_tag(pos)

                # remove bullets mid paragraph
                it = pos.copy()
                it.forward_char()
                while True:
                    match = it.forward_search(BULLET_STR, 0, par_end)
                    if not match:
                        it.backward_char()
                        pos, par_end = self.get_paragraph(it)
                        break
                    print "match"
                    self.move_mark(self._indent_update_start, match[0])
                    self.delete(match[0], match[1])
                    it = self.get_iter_at_mark(self._indent_update_start)
                    par_end = it.copy()
                    par_end.forward_line()

                if indent_tag is None:
                    # remove all indent tags
                    self.clear_tag_class(self.tag_table.lookup_indent(1),
                                         pos, par_end)
                    # remove bullets
                    par_type = "none"

                else:
                    self.apply_tag_selected(indent_tag, pos, par_end)

                    # check for bullets
                    par_type = indent_tag.get_par_indent()
                    
                if par_type == "bullet":
                    pass
                    # ensure proper bullet is in place
                    pos = self._insert_bullet(pos)
                    end = self.get_iter_at_mark(self._indent_update_end)
                    
                elif par_type == "none":
                    pass
                    # remove bullets
                    pos = self._remove_bullet(pos)
                    end = self.get_iter_at_mark(self._indent_update_end)
                    
                else:
                    raise Exception("unknown par_type '%s'" % par_type)
                    

                # move forward a line
                if not pos.forward_line():
                    break

            #print "end"
            self.end_user_action()


    #==========================================
    # query and navigate paragraphs/indentation

    def get_indent(self, it=None):
        """Returns the indentation level at iter 'it'"""
        
        tag = self.get_indent_tag(it)
        if tag:
            return tag.get_indent(), tag.get_par_indent()
        else:
            return 0, "none"


    def get_indent_tag(self, it=None):
        """Returns the indentation level at iter 'it'"""
        
        if not it:
            it = self.get_iter_at_mark(self.get_insert())

        it2 = it.copy()
        if not it2.ends_line():
            it2.forward_char()
        
        for tag in it2.get_tags():
            if isinstance(tag, RichTextIndentTag):
                return tag
        
        return None        
        

    def get_paragraph(self, it=None):
        """Returns the start and end of a paragraph containing iter 'it'"""

        if not it:
            par_start = self.get_iter_at_mark(self.get_insert())
        else:
            par_start = it.copy()
        
        par_end = par_start.copy()
        if par_start.get_line() > 0:
            par_start.backward_line()
            par_start.forward_line()
        else:
            par_start = self.get_start_iter()
        par_end.forward_line()

        # NOTE: par_start.starts_line() == True
        #       par_end.starts_line() == True
        
        return par_start, par_end

    def starts_par(self, it):
        """Returns True if iter 'it' starts paragraph"""

        if it.starts_line():
            return True
        else:
            it2 = it.copy()
            it2 = self.move_to_start_of_line(it2)
            
            return self._par_has_bullet(it2) and \
                   it.get_offset() <= it2.get_offset() + len(BULLET_STR)


    def move_to_start_of_line(self, it=None):
        if not it:
            it = self.get_iter_at_mark(self.get_insert())
        if not it.starts_line():
            if it.get_line() > 0:
                it.backward_line()
                it.forward_line()
            else:
                it = self.get_start_iter()
        return it
                

    
    #============================================================
    # child actions
    
    def add_child(self, it, child):

        # preprocess child
        if isinstance(child, RichTextImage):
            self._determine_image_name(child)

        # setup child
        self._anchors.add(child)
        child.set_buffer(self)
        child.connect("activated", self._on_child_activated)
        child.connect("selected", self._on_child_selected)
        child.connect("popup-menu", self._on_child_popup_menu)
        self.insert_child_anchor(it, child)

        # if textview is attaced, let it display child
        if self.textview:
            self.textview.add_child_at_anchor(child.get_widget(), child)
        else:
            # defer display of child
            self._anchors_deferred.add(child)
    
    
    def add_deferred_anchors(self):
        """Add anchors that were deferred"""
        assert self.textview is not None
        
        for child in self._anchors_deferred:
            # only add anchor if it is still present (hasn't been deleted)
            if child in self._anchors:
                self.textview.add_child_at_anchor(child.get_widget(), child)
        
        self._anchors_deferred.clear()
    
    
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer at current position"""

        # set default filename
        if image.get_filename() is None:
            image.set_filename(filename)
        
        # insert image into buffer
        self.begin_user_action()
        it = self.get_iter_at_mark(self.get_insert())
        self.add_child(it, image)
        image.get_widget().show()
        self.end_user_action()


    def insert_hr(self):
        """Insert Horizontal Rule"""
        self.begin_user_action()

        it = self.get_iter_at_mark(self.get_insert())
        hr = RichTextHorizontalRule()
        self.add_child(it, hr)
        
        self.end_user_action()
        

    #===================================
    # Image management

    def get_image_filenames(self):
        filenames = []
        
        for child in self._anchors:
            if isinstance(child, RichTextImage):
                filenames.append(child.get_filename())
        
        return filenames
    

    def _determine_image_name(self, image):
        """Determines image filename"""
        
        if self._is_new_pixbuf(image.get_original_pixbuf()):
            filename, ext = os.path.splitext(image.get_filename())
            filenames = self.get_image_filenames()
            filename2 = takenote.get_unique_filename_list(filenames,
                                                          filename, ext)
            image.set_filename(filename2)
            image.set_save_needed(True)
    

    def _is_new_pixbuf(self, pixbuf):

        # cannot tell if pixbuf is new because it is not loaded
        if pixbuf is None:
            return False
        
        for child in self._anchors:
            if isinstance(child, RichTextImage):
                if pixbuf == child.get_original_pixbuf():
                    return False
        return True
        
    
    #===========================================================
    # Modification callbacks
    
    def _on_mark_set(self, textbuffer, it, mark):
        """Callback for mark movement"""

        if mark.get_name() == "insert":

            # pick up the last tags
            self._current_tags = [x for x in it.get_toggled_tags(False)
                                  if x.can_be_current()]

            self.highlight_children()
            
            # update UI for current fonts
            font = self.get_font()
            self.emit("font-change", font)
    
    
    def _on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""

        # check to make sure insert is not in front of bullet
        if it.starts_line() and self._par_has_bullet(it):
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
                    gtk.TextBuffer.apply_tag(self, tag, it, it2)

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
                par_start, par_end = self.get_paragraph()
        
        
        self.begin_user_action()
        self.undo_stack.do(self._next_action.do, self._next_action.undo, False)
        
        if paragraph_action == "split":
            self._on_paragraph_split(par_start, par_end)
        elif paragraph_action == "merge":
            self._on_paragraph_merge(par_start, par_end)
        
        self._next_action = None            
        self.end_user_action()


    #==============================================
    # Child callbacks

    def _on_child_selected(self, child):
        """Callback for when child object is selected

           Make sure buffer knows the selection
        """
        
        it = self.get_iter_at_child_anchor(child)        
        end = it.copy()        
        end.forward_char()
        self.select_range(it, end)


    def _on_child_activated(self, child):
        """Callback for when child is activated (e.g. double-clicked)"""

        # forward callback to listeners (textview)
        self.emit("child-activated", child)
    

    def _on_child_popup_menu(self, child, button, activate_time):
        """Callback for when child's menu is visible"""

        # forward callback to listeners (textview)
        self.emit("child-menu", child, button, activate_time)
            
    
    def highlight_children(self):
        """Highlight any children that are within selection range"""
        
        sel = self.get_selection_bounds()
        focus = None
        
        if len(sel) > 0:
            
            # selection exists, get range (a, b)
            a = sel[0].get_offset()
            b = sel[1].get_offset()
            for child in self._anchors:
                it = self.get_iter_at_child_anchor(child)
                offset = it.get_offset()
                if a <= offset < b:
                    child.highlight()
                else:
                    child.unhighlight()

                w = child.get_widget()
                if w:
                    top = w.get_toplevel()
                    if top:
                        f = top.get_focus()
                        if f:
                            focus = f
            if focus:
                focus.grab_focus()
        else:
            # no selection, unselect all children
            for child in self._anchors:
                child.unhighlight()
    
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
                gtk.TextBuffer.apply_tag(self, tag, it[0], it[1])
            else:
                self.remove_tag(tag, it[0], it[1])
        
        self.end_user_action()


    def apply_tag(self, tag, start, end):
        """Overriding apply_tag to enable current tags"""
        
        self.begin_user_action()
        self.clear_tag_class(tag, start, end)
        gtk.TextBuffer.apply_tag(self, tag, start, end)
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
            gtk.TextBuffer.apply_tag(self, tag, it[0], it[1])
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
    
    def get_font(self):

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
        font = attr.font

        if font:
            # get font family
            family = font.get_family()

            # get size in points (get_size() returns pango units)
            PIXELS_PER_PANGO_UNIT = 1024
            size = font.get_size() // PIXELS_PER_PANGO_UNIT

            weight = font.get_weight()
            style = font.get_style()
        else:
            # TODO: replace this hardcoding
            family = "Sans"
            size = 10
            weight = pango.WEIGHT_NORMAL
            style = pango.STYLE_NORMAL
        
        
        # get colors
        fg_color = color_to_string(attr.fg_color)
        bg_color = color_to_string(attr.bg_color)
        
        # set modifications (current tags override)
        mods = {"bold":
                self.tag_table.bold_tag in current_tags or
                weight == pango.WEIGHT_BOLD,
                "italic": 
                self.tag_table.italic_tag in current_tags or
                style == pango.STYLE_ITALIC,
                "underline":
                self.tag_table.underline_tag in current_tags or
                attr.underline == pango.UNDERLINE_SINGLE,
                "nowrap":
                self.tag_table.no_wrap_tag in current_tags or
                attr.wrap_mode == gtk.WRAP_NONE}
        
        # set justification
        justify = self.tag_table.justify2name[attr.justification]
        
        # current tags override
        if self.tag_table.center_tag in current_tags:
            justify = "center"
        elif self.tag_table.right_tag in current_tags:
            justify = "right"
        elif self.tag_table.fill_tag in current_tags:
            justify = "fill"
        
        
        # current tags override for family and size
        for tag in self._current_tags:            
            if isinstance(tag, RichTextFamilyTag):
                family = tag.get_family()            
            elif isinstance(tag, RichTextSizeTag):
                size = tag.get_size()
            elif isinstance(tag, RichTextFGColorTag):
                fg_color = tag.get_color()
            elif isinstance(tag, RichTextBGColorTag):
                bg_color = tag.get_color()

        return RichTextFont(mods, justify, family, size, fg_color, bg_color)


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

        # perfrom queued indentation updates
        try:
            self._update_indentation()
        except Exception, e:
            print e
        
        self._user_action = False
        self.undo_stack.end_action()


gobject.type_register(RichTextBuffer)
gobject.signal_new("font-change", RichTextBuffer, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-activated", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-menu", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object, object, object))
#gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
#    gobject.TYPE_NONE, (bool,))

