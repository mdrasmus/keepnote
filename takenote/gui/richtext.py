"""
    TakeNote
    Copyright Matt Rasmussen 2008
    
    General rich text editor that saves to HTML
"""



# python imports
import sys, os, tempfile, re
from HTMLParser import HTMLParser

try:
    import gtkspell
except ImportError:
    gtkspell = None


# pygtk imports
import pygtk
pygtk.require('2.0')
import gtk, gobject, pango
from gtk import gdk

# takenote imports
import takenote
from takenote.undo import UndoStack


# constants
MIME_TAKENOTE = "application/x-takespnote"

# these tags will not be enumerated by iter_buffer_contents
IGNORE_TAGS = set(["gtkspell-misspelled", "hr"])

# TextBuffer uses this char for anchors and pixbufs
ANCHOR_CHAR = u'\ufffc'


#=============================================================================
# functions for iterating and inserting into textbuffers

def iter_buffer_contents(textbuffer, start=None, end=None,
                         ignore_tags=IGNORE_TAGS):
    """Iterate over the items of a textbuffer

    textbuffer -- buffer to iterate over
    start      -- starting position (TextIter)
    end        -- ending position (TextIter)
    """

    # initialize iterators
    if start is None:
        it = textbuffer.get_start_iter()
    else:
        it = start.copy()
    last = it.copy()

    if end is None:
        end = textbuffer.get_end_iter()


    # yield opening tags at begining of region
    for tag in it.get_tags():
        if tag.get_property("name") in ignore_tags:
            continue
        yield ("begin", it, tag)
    
    while True:
        it2 = it.copy()    
        it.forward_to_tag_toggle(None)

        # yield child anchors between tags        
        while True:
            if it.get_offset() < end.get_offset():
                stop = it
            else:
                stop = end
            ret = it2.forward_search(ANCHOR_CHAR, (), stop)
            
            if ret is None:
                yield ("text", it2, it2.get_text(stop))
                break
            
            a, b = ret
            anchor = a.get_child_anchor()
            
            # yield text in between tags
            yield ("text", it2, it2.get_text(a))
            if anchor is not None:
                yield ("anchor", a, (anchor, anchor.get_widgets()))
            else:
                yield ("pixbuf", a, a.get_pixbuf())
            it2 = b
        
        # stop iterating if we have pasted end of region
        if it.get_offset() > end.get_offset():
            break
        
        # yield closing tags
        for tag in it.get_toggled_tags(False):
            if tag.get_property("name") in ignore_tags:
                continue
            yield ("end", it, tag)

        # yield opening tags
        for tag in it.get_toggled_tags(True):
            if tag.get_property("name") in ignore_tags:
                continue
            yield ("begin", it, tag)
        
        last = it.copy()
        
        if it.equal(end):
            break
    
    # yield tags that have not been closed yet
    toggled = set(end.get_toggled_tags(False))
    for tag in end.get_tags():
        if tag not in toggled:
            if tag.get_property("name") in ignore_tags:
                continue
            yield ("end", end, tag)


def buffer_contents_iter_to_offset(contents):
    """Converts to iters of a content list to offsets"""
    
    for kind, it, param in contents:
        yield (kind, it.get_offset(), param)
    

def normalize_tags(items):
    """Normalize open and close tags to ensure proper nesting
       This is especially useful for saving to HTML
    """

    open_stack = []

    for item in items:
        kind, it, param = item
        if kind == "begin":
            open_stack.append(param)
            yield item

        elif kind == "end":

            # close any open out of order tags
            reopen_stack = []
            while param != open_stack[-1]:
                reopen_stack.append(open_stack.pop())
                tag2 = reopen_stack[-1]
                yield ("end", it, tag2)

            # close current tag
            open_stack.pop()
            yield item

            # reopen tags
            for tag2 in reversed(reopen_stack):
                open_stack.append(tag2)
                yield ("begin", it, tag2)

        else:
            yield item


def insert_buffer_contents(textbuffer, pos, contents):
    """Insert a content list into a RichTextBuffer"""
    
    textbuffer.place_cursor(pos)
    tags = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for item in contents:
        kind, offset, param = item
        
        if kind == "text":
            # insert text
            textbuffer.insert_at_cursor(param)
            
            if first_insert:
                it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
                it2 = it.copy()
                it2.backward_chars(len(param))
                textbuffer.remove_all_tags(it2, it)
                first_insert = False
            
        elif kind == "anchor":
            # insert widget            
            it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
            anchor = param[0].copy()
            textbuffer.add_child(it, anchor)
            
            if first_insert:
                it = textbuffer.get_iter_at_mark(textbuffer.get_insert())
                it2 = it.copy()
                it2.backward_chars(len(param))
                textbuffer.remove_all_tags(it2, it)
                first_insert = False
            
        elif kind == "begin":
            tags[param] = textbuffer.get_iter_at_mark(textbuffer.get_insert()).get_offset()
            
        elif kind == "end":
            start = textbuffer.get_iter_at_offset(tags[param])
            end = textbuffer.get_iter_at_mark(textbuffer.get_insert())
            textbuffer.apply_tag(param, start, end)


def buffer_contents_apply_tags(textbuffer, contents):
    """Apply tags to a textbuffer"""
    
    tags = {}
    
    # make sure all tags are removed on first text/anchor insert
    first_insert = True
    
    for item in contents:
        kind, offset, param = item
        
        if kind == "begin":
            tags[param] = textbuffer.get_iter_at_offset(offset)
            
        elif kind == "end":
            start = tags[param]
            end = textbuffer.get_iter_at_offset(offset)
            textbuffer.apply_tag(param, start, end)



#=============================================================================
# HTML parser for RichText

class HtmlError (StandardError):
    """Error for HTML parsing"""
    pass


class HtmlBuffer (HTMLParser):
    """Read and write HTML for a RichTextBuffer"""
    
    def __init__(self, out=None):
        HTMLParser.__init__(self)
    
        self.out = out
        self.mod_tags = "biu"
        self.mod_tag2buffer_tag = {
            "b": "Bold",
            "i": "Italic",
            "u": "Underline"}
        self.buffer_tag2mod_tag = {
            "Bold": "b",
            "Italic": "i",
            "Underline": "u"
            }
        self.newline = False
        
        self.tag_stack = []
        self.buffer = None
        self.text_queue = []
        self.within_body = False
        
        self.entity_char_map = [("&", "amp"),
                                (">", "gt"),
                                ("<", "lt"),
                                (" ", "nbsp")]
        self.entity2char = {}
        for ch, name in self.entity_char_map:
            self.entity2char[name] = ch
        
        self.charref2char = {"09": "\t"}
        
        
        
    
    def set_output(self, out):
        """Set the output stream for HTML"""
        self.out = out
    
    
    def read(self, textbuffer, infile):
        """Read from stream infile to populate textbuffer"""
        self.buffer = textbuffer
        self.text_queue = []
        self.within_body = False
        
        for line in infile:
            self.feed(line)
        self.close()
        self.flush_text()
        
        self.buffer.place_cursor(self.buffer.get_start_iter())


    def flush_text(self):
        if len(self.text_queue) > 0:
            self.buffer.insert_at_cursor("".join(self.text_queue))
            self.text_queue[:] = []

    def queue_text(self, text):
        self.text_queue.append(text)
        
    
    def handle_starttag(self, tag, attrs):
        """Callback for parsing a starting HTML tag"""
        self.newline = False
        if tag == "html":
            return
        
        elif tag == "body":
            self.within_body = True
            return

        elif tag in ("hr", "br", "img"):
            mark = None
        else:
            self.flush_text()
            mark = self.buffer.create_mark(None, self.buffer.get_end_iter(),
                                           True)
        self.tag_stack.append((tag, attrs, mark))


    def handle_endtag(self, tag):
        """Callback for parsing a ending HTML tag"""
        
        self.newline = False
        if tag in ("html", "body") or not self.within_body:
            return

        
        # ensure closing tags match opened tags
        if self.tag_stack[-1][0] != tag:
            raise HtmlError("closing tag does not match opening tag")
        htmltag, attrs, mark = self.tag_stack.pop()
        
        
        
        if htmltag in self.mod_tag2buffer_tag:
            # get simple fonts b/i/u
            tag = self.buffer.lookup_mod_tag(self.mod_tag2buffer_tag[htmltag])
            self.flush_text()
            start = self.buffer.get_iter_at_mark(mark)
            self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())

        elif htmltag == "span":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("font-size"):
                        size = int(value.split(":")[1].replace("pt", ""))
                        tag = self.buffer.lookup_size_tag(size)
                        
                    elif value.startswith("font-family"):
                        family = value.split(":")[1].strip()
                        tag = self.buffer.lookup_family_tag(family)
                    
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)

            self.flush_text()
            start = self.buffer.get_iter_at_mark(mark)            
            self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())
        
        elif htmltag == "div":
            # apply style
            
            for key, value in attrs:
                if key == "style":
                    if value.startswith("text-align"):
                        align = value.split(":")[1].strip()
                        if align == "left":
                            tag = self.buffer.left_tag
                        elif align == "center":
                            tag = self.buffer.center_tag
                        elif align == "right":
                            tag = self.buffer.right_tag
                        elif align == "justify":
                            tag = self.buffer.fill_tag
                        else:
                            raise HtmlError("unknown justification '%s'" % align)
                    else:
                        raise HtmlError("unknown style '%s'" % value)
                else:
                    raise HtmlError("unknown attr key '%s'" % key)

            self.flush_text()
            start = self.buffer.get_iter_at_mark(mark)
            self.buffer.apply_tag(tag, start, self.buffer.get_end_iter())    
            
        elif htmltag == "br":
            # insert newline
            self.queue_text("\n")
            self.newline = True

        elif htmltag == "hr":
            # horizontal break
            self.flush_text()
            self.buffer.insert_hr()
        
        elif htmltag == "img":
            # insert image
            img = RichTextImage()
            width, height = None, None
            
            for key, value in attrs:
                if key == "src":
                    img.set_filename(value)
                elif key == "width":
                    try:
                        width = int(value)
                    except ValueError, e:
                        raise HtmlError("expected integer for image width '%s'" % value)
                elif key == "height":
                    try:
                        height = int(value)
                    except ValueError, e:
                        raise HtmlError("expected integer for image height '%s'" % value)
                else:
                    HtmlError("unknown attr key '%s'" % key)

            img.set_size(width, height)
            self.flush_text()
            self.buffer.insert_image(img)
            
        
        else:
            raise HtmlError("WARNING: unhandled tag '%s'" % htmltag)

        
        # delete mark created with start tag
        if mark is not None:
            self.buffer.delete_mark(mark)
        
    
    
    def handle_data(self, data):
        """Callback for character data"""

        if not self.within_body:
            return
        
        if self.newline:
            data = re.sub("\n[\n ]*", "", data)
            self.newline = False
        else:
            data = re.sub("[\n ]+", " ", data)
        self.queue_text(data)

    
    def handle_entityref(self, name):
        if not self.within_body:
            return
        self.queue_text(self.entity2char.get(name, ""))
    
    
    def handle_charref(self, name):
        if not self.within_body:
            return
        self.queue_text(self.charref2char.get(name, ""))
        
    
    def write(self, richtext):
        self.buffer = richtext.textbuffer
        
        #self.out.write("<html><body>")
        self.out.write("""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<body>""")
        
        for kind, it, param in normalize_tags(iter_buffer_contents(self.buffer)):
            if kind == "text":
                text = param

                # TODO: could try to speed this up
                text = text.replace("&", "&amp;")
                text = text.replace(">", "&gt;")
                text = text.replace("<", "&lt;")
                text = text.replace("\n", "<br/>\n")
                text = text.replace("\t", "&#09;")
                text = text.replace("  ", " &nbsp;")
                self.out.write(text)
            
            elif kind == "begin":
                tag = param
                self.write_tag_begin(tag)
                
            elif kind == "end":
                tag = param
                self.write_tag_end(tag)
            
            elif kind == "anchor":
                child = param[0]

                if isinstance(child, RichTextImage):
                    # write image
                    size_str = ""
                    size = child.get_size()
                        
                    if size[0] is not None:
                        size_str += " width=\"%d\"" % size[0]
                    if size[1] is not None:
                        size_str += " height=\"%d\"" % size[1]
                        
                    self.out.write("<img src=\"%s\" %s />" % 
                                   (child.get_filename(), size_str))

                elif isinstance(child, RichTextHorizontalRule):
                    self.out.write("<hr/>")
                    
                else:
                    # warning
                    #TODO:
                    print "unknown child element", child
            
            elif kind == "pixbuf":
                pass
            else:
                raise Exception("unknown kind '%s'" % str(kind))
        
        self.out.write("</body></html>")
        
    
    def write_tag_begin(self, tag):
        if tag in self.buffer.mod_tags:
            self.out.write("<%s>" % self.buffer_tag2mod_tag[tag.get_property("name")])
        else:
            if tag in self.buffer.size_tags:
                self.out.write("<span style='font-size: %dpt'>" % 
                          tag.get_property("size-points"))
            elif tag in self.buffer.family_tags:
                self.out.write("<span style='font-family: %s'>" % 
                          tag.get_property("family"))
            elif tag in self.buffer.justify_tags:
                if tag == self.buffer.left_tag:
                    text = "left"
                elif tag == self.buffer.center_tag:
                    text = "center"
                elif tag == self.buffer.right_tag:
                    text = "right"
                else:
                    text = "justify"
                self.out.write("<div style='text-align: %s'>" % text)
            elif tag.get_property("name") in IGNORE_TAGS:
                pass
            else:
                raise HtmlError("unknown tag '%s'" % tag.get_property("name"))
                
        
    def write_tag_end(self, tag):
        if tag in self.buffer.mod_tags:
            self.out.write("</%s>" % self.buffer_tag2mod_tag[tag.get_property("name")])
        elif tag in self.buffer.justify_tags:
            self.out.write("</div>")
        else:
            self.out.write("</span>")



#=============================================================================
# RichText actions

class Action (object):
    def __init__(self):
        pass
    
    def do(self):
        pass
    
    def undo(self):
        pass


class ModifyAction (Action):
    def __init__(self, textbuffer):
        self.textbuffer = textbuffer
        self.was_modified = False
    
    def do(self):
        self.was_modified = self.textbuffer.get_modified()
        self.textbuffer.set_modified(True)
    
    def undo(self):
        if not self.was_modified:
            self.textbuffer.set_modified(False)
        

# XXX: do I need to record current tags to properly redo insert?
class InsertAction (Action):
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
        self.textbuffer.insert_with_tags(start, self.text, *self.current_tags)
    
    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.pos)
        end = self.textbuffer.get_iter_at_offset(self.pos + self.length)
        self.textbuffer.place_cursor(start)
        self.textbuffer.delete(start, end)



class DeleteAction (Action):
    def __init__(self, textbuffer, start_offset, end_offset, text,
                 cursor_offset):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.text = text
        self.cursor_offset = cursor_offset
        self.contents = []        
        self.record_range()
    

    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.textbuffer.place_cursor(start)
        self.record_range()
        self.textbuffer.delete(start, end)


    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        
        self.textbuffer.begin_user_action()
        insert_buffer_contents(self.textbuffer, start, self.contents)
        cursor = self.textbuffer.get_iter_at_offset(self.cursor_offset)
        self.textbuffer.place_cursor(cursor)
        self.textbuffer.end_user_action()

    
    def record_range(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.contents = list(buffer_contents_iter_to_offset(
            iter_buffer_contents(self.textbuffer, start, end)))



class InsertChildAction (Action):
    def __init__(self, textbuffer, pos, child):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.pos = pos
        self.child = child
        
    
    def do(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.child = self.child.copy()
        self.textbuffer.add_child(it, self.child)
        

    
    def undo(self):
        it = self.textbuffer.get_iter_at_offset(self.pos)
        self.child = it.get_child_anchor()
        it2 = it.copy()
        it2.forward_char()
        self.textbuffer.delete(it, it2)
        


class TagAction (Action):
    def __init__(self, textbuffer, tag, start_offset, end_offset, applied):
        Action.__init__(self)
        self.textbuffer = textbuffer
        self.tag = tag
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.applied = applied
        self.contents = []
        self.record_range()
        
    
    def do(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        self.record_range()
        if self.applied:
            self.textbuffer.apply_tag(self.tag, start, end)
        else:
            self.textbuffer.remove_tag(self.tag, start, end)

    
    def undo(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
        if self.applied:
            self.textbuffer.remove_tag(self.tag, start, end)
        else:
            self.textbuffer.apply_tag(self.tag, start, end)
        buffer_contents_apply_tags(self.textbuffer, self.contents)
        
    
    def record_range(self):
        start = self.textbuffer.get_iter_at_offset(self.start_offset)
        end = self.textbuffer.get_iter_at_offset(self.end_offset)
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
        self.img = gtk.Image(*args, **kargs)
        self.add(self.img)

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
        self.img.set_from_pixbuf(pixbuf)
    
    def set_from_stock(self, stock, size):
        self.img.set_from_stock(stock, size)
    
    def show(self):
        gtk.EventBox.show(self)
        self.img.show()


class RichTextImage (RichTextAnchor):
    """An Image child widget in a RichTextView"""

    def __init__(self):
        RichTextAnchor.__init__(self)
        self._filename = None
        self._widget = BaseImage()
        self._widget.connect("destroy", self._on_image_destroy)
        self._widget.connect("button-press-event", self._on_clicked)
        self._pixbuf = None
        self._pixbuf_original = None
        self._size = [None, None]
        self._buffer = None
        self._save_needed = False
        

    def is_valid(self):
        return self._pixbuf is not None
    
    def set_filename(self, filename):
        self._filename = filename
    
    def get_filename(self):
        return self._filename

    def set_save_needed(self, save):
        self._save_needed = save

    def save_needed(self):
        return self._save_needed
    
    def set_from_file(self, filename):
        if self._filename is None:
            self._filename = os.path.basename(filename)
        
        try:
            self._pixbuf_original = gdk.pixbuf_new_from_file(filename)
            
        except gobject.GError, e:            
            self._widget.set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
            self._pixbuf_original = None
            self._pixbuf = None
        else:
            self._pixbuf = self._pixbuf_original
            
            if self.is_size_set():
                self.scale(self._size[0], self._size[1], False)
            self._widget.set_from_pixbuf(self._pixbuf)


    def set_from_pixbuf(self, pixbuf, filename=None):
        if filename is not None:
            self._filename = filename
        self._pixbuf = pixbuf
        self._pixbuf_original = pixbuf

        if self.is_size_set():
            self.scale(self._size[0], self._size[1], False)
        self._widget.set_from_pixbuf(self._pixbuf)


    def get_original_pixbuf(self):
        return self._pixbuf_original

        
    def set_size(self, width, height):
        self._size = [width, height]

        
    def get_size(self, actual_size=False):
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
        
        self._size = [width, height]

        if not self.is_size_set():
            # use original image size
            if self._pixbuf != self._pixbuf_original:
                self._pixbuf = self._pixbuf_original
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
        f, ext = os.path.splitext(filename)
        ext = ext.replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
            
        self._pixbuf_original.save(filename, ext)
        self._save_needed = False
        
        
    def copy(self):
        img = RichTextImage()
        img.set_filename(self._filename)
        img.set_size(*self.get_size())
        
        if self._pixbuf:
            img.get_widget().set_from_pixbuf(self._pixbuf)
        else:
            img.get_widget().set_from_stock(gtk.STOCK_MISSING_IMAGE, gtk.ICON_SIZE_MENU)
        img._pixbuf = self._pixbuf
        img._pixbuf_original = self._pixbuf_original
        img.get_widget().show()
        return img

    #==========================
    # GUI callbacks
    
    def _on_image_destroy(self, widget):
        self._widget = None
    
    def _on_clicked(self, widget, event):
        if event.button == 1:
            self._widget.grab_focus()
            self.emit("selected")
            return True
        elif event.button == 3:
            # popup menu
            self.emit("selected")
            self.emit("popup-menu", event.button, event.time)
            return True



        

#=============================================================================
# RichText classes

class RichTextError (StandardError):
    def __init__(self, msg, error):
        StandardError.__init__(self, msg)
        self.msg = msg
        self.error = error
    
    def __str__(self):
        if self.error:
            return str(self.error) + "\n" + self.msg
        else:
            return self.msg


class RichTextBuffer (gtk.TextBuffer):
    def __init__(self, textview=None):
        gtk.TextBuffer.__init__(self)
        self.clipboard_contents = None
        self.textview = textview
        self.undo_stack = UndoStack()
        
        
        # action state
        self.insert_mark = None
        self.next_action = None
        self.current_tags = []

        # set of all anchors in buffer
        self.anchors = set()

        # anchors that still need to be added,
        # they are defferred because textview was not available at insert-time
        self.anchors_deferred = set() 
        
        # setup signals
        self.signals = []
        self.signals.append(self.connect("begin_user_action", 
                                         self.on_begin_user_action))
        self.signals.append(self.connect("end_user_action", 
                                         self.on_end_user_action))
        self.signals.append(self.connect("mark-set", 
                                         self.on_mark_set))
        self.signals.append(self.connect("insert-text", 
                                         self.on_insert_text))
        self.signals.append(self.connect("delete-range", 
                                         self.on_delete_range))
        self.signals.append(self.connect("insert-pixbuf", 
                                         self.on_insert_pixbuf))
        self.signals.append(self.connect("insert-child-anchor", 
                                         self.on_insert_child_anchor))
        self.signals.append(self.connect("apply-tag", 
                                         self.on_apply_tag))
        self.signals.append(self.connect("remove-tag", 
                                         self.on_remove_tag))
        self.signals.append(self.connect("changed", 
                                         self.on_changed))
             
        
        
        # font tags        
        self.bold_tag = self.create_tag("Bold", weight=pango.WEIGHT_BOLD)
        self.italic_tag = self.create_tag("Italic", style=pango.STYLE_ITALIC)
        self.underline_tag = self.create_tag("Underline", underline=pango.UNDERLINE_SINGLE)
        self.mod_tags = set([self.bold_tag, self.italic_tag,
                             self.underline_tag])
        
        self.left_tag = self.create_tag("Left", justification=gtk.JUSTIFY_LEFT)
        self.center_tag = self.create_tag("Center", justification=gtk.JUSTIFY_CENTER)
        self.right_tag = self.create_tag("Right", justification=gtk.JUSTIFY_RIGHT)
        self.fill_tag = self.create_tag("Fill", justification=gtk.JUSTIFY_FILL)
        
        self.justify2name = {
            gtk.JUSTIFY_LEFT: "left", 
            gtk.JUSTIFY_RIGHT: "right", 
            gtk.JUSTIFY_CENTER: "center", 
            gtk.JUSTIFY_FILL: "fill" # TODO: implement fully
        }
        
        self.justify_tags = set([self.left_tag, self.center_tag, self.right_tag,
                                 self.fill_tag])
        self.family_tags = set()
        self.size_tags = set()
           
    
    def set_textview(self, textview):
        self.textview = textview
    
    def get_textview(self):
        return self.textview
    
    def get_current_tags(self):
        return self.current_tags
    
    def block_signals(self):
        for signal in self.signals:
            self.handler_block(signal)
    
    
    def unblock_signals(self):
        for signal in self.signals:
            self.handler_unblock(signal)


    def clear(self):
        """Clear buffer contents"""
        
        self.anchors.clear()
        self.anchors_deferred.clear()
        start = self.get_start_iter()
        end = self.get_end_iter()
        self.remove_all_tags(start, end)
        self.delete(start, end)

    
    #======================================================
    # copy and paste

    def copy_clipboard(self, clipboard):
        """Callback for copy event"""
                
        targets = [(MIME_TAKENOTE, gtk.TARGET_SAME_APP, -3),
                   ("text/plain", 0, -3),
                   ("text/plain;charset=utf-8", 0, -3),
                   ("text/plain;charset=UTF-8", 0, -3),
                   ("UTF8_STRING", 0, -3),
                   ("STRING", 0, -3),
                   ("COMPOUND_TEXT", 0, -3),
                   ("TEXT", 0, -3)]
        
        sel = self.get_selection_bounds()

        if sel:
            start, end = sel
            contents = list(iter_buffer_contents(self, start, end))
            text = start.get_text(end)
            clipboard.set_with_data(targets, self.get_selection_data, 
                                    self.clear_selection_data,
                                    (contents, text))

    def cut_clipboard(self, clipboard, default_editable):
        """Callback for cut event"""
        
        self.copy_clipboard(clipboard)
        self.delete_selection(False, default_editable)

    
    def paste_clipboard(self, clipboard, override_location, default_editable):
        """Callback for paste event"""
        
        targets = clipboard.wait_for_targets()

        if targets is None:
            # do nothing
            return
            
        
        if MIME_TAKENOTE in targets:
            clipboard.request_contents(MIME_TAKENOTE, self.do_paste)
        elif "image/png" in targets:
            clipboard.request_contents("image/png", self.do_paste_image)        
        elif "image/bmp" in targets:
            clipboard.request_contents("image/bmp", self.do_paste_image)        
        elif "image/jpeg" in targets:
            clipboard.request_contents("image/jpeg", self.do_paste_image)
        elif "image/xpm" in targets:
            clipboard.request_contents("image/xpm", self.do_paste_image)
        else:
            clipboard.request_text(self.do_paste_text)
        
    
    def do_paste_text(self, clipboard, text, data):
        self.begin_user_action()
        self.delete_selection(False, True)
        self.insert_at_cursor(text)
        self.end_user_action()
    
    def do_paste_image(self, clipboard, selection_data, data):
        
        pixbuf = selection_data.get_pixbuf()
        image = RichTextImage()
        image.set_from_pixbuf(pixbuf)
        
        self.insert_image(image)
    
    def do_paste(self, clipboard, selection_data, data):
        if self.clipboard_contents is None:
            # do nothing
            return
        
        self.begin_user_action()
        it = self.get_iter_at_mark(self.get_insert())
        insert_buffer_contents(self, it, self.clipboard_contents)
        self.end_user_action()
    
    
    def get_selection_data(self, clipboard, selection_data, info, data):
        """Callback for when Clipboard needs selection data"""
        
        self.clipboard_contents = data[0]
        
        
        if MIME_TAKENOTE in selection_data.target:
            # set rich text
            selection_data.set(MIME_TAKENOTE, 8, "<takenote>")
        else:
            # set plain text        
            selection_data.set_text(data[1])

    
    def clear_selection_data(self, clipboard, data):
        self.clipboard_contents = None
    
    
    #============================================================
    # child actions
    
    def add_child(self, it, child):

        # preprocess child
        if isinstance(child, RichTextImage):
            self.determine_image_name(child)

        # setup child
        self.anchors.add(child)
        child.set_buffer(self)
        child.connect("selected", self.on_child_selected)
        child.connect("popup-menu", self.on_child_popup_menu)
        self.insert_child_anchor(it, child)

        # if textview is attaced, let it display child
        if self.textview:
            self.textview.add_child_at_anchor(child.get_widget(), child)
        else:
            # defer display of child
            self.anchors_deferred.add(child)
    
    
    def add_deferred_anchors(self):
        """Add anchors that were deferred"""
        assert self.textview is not None
        
        for child in self.anchors_deferred:
            # only add anchor if it is still present (hasn't been deleted)
            if child in self.anchors:
                self.textview.add_child_at_anchor(child.get_widget(), child)
        
        self.anchors_deferred.clear()
    
    
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
        self.begin_user_action()

        it = self.get_iter_at_mark(self.get_insert())
        hr = RichTextHorizontalRule()
        self.add_child(it, hr)
        
        self.end_user_action()


    #===================================
    # Image management

    def determine_image_name(self, image):
        """Determines image filename"""
        
        if self.is_new_pixbuf(image.get_original_pixbuf()):
            filename, ext = os.path.splitext(image.get_filename())
            filenames = self.get_image_filenames()
            filename2 = takenote.get_unique_filename_list(filenames,
                                                          filename, ext)
            image.set_filename(filename2)
            image.set_save_needed(True)
        
    
    def get_image_filenames(self):
        filenames = []
        
        # TODO: could be faster (specialized search_forward)
        #for kind, it, param in iter_buffer_contents(self):
        #    if kind == "anchor":

        for child in self.anchors:
            if isinstance(child, RichTextImage):
                filenames.append(child.get_filename())
        
        return filenames

    def is_new_pixbuf(self, pixbuf):

        # cannot tell if pixbuf is new because it is not loaded
        if pixbuf is None:
            return False
        
        for child in self.anchors:
            if isinstance(child, RichTextImage):
                if pixbuf == child.get_original_pixbuf():
                    return False
        return True
        
    
    #===========================================================
    # Callbacks
    
    def on_mark_set(self, textbuffer, it, mark):
        """Callback for mark movement"""
        
        if mark.get_name() == "insert":
            # pick up the last tags
            self.current_tags = it.get_toggled_tags(False)
            
            # update UI for current fonts
            if self.textview:
                self.textview.on_update_font()
            
            self.highlight_children()

    
    
    def on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""
        
        # start new action
        self.next_action = InsertAction(self, it.get_offset(), text, length)
        self.insert_mark = self.create_mark(None, it, True)

    def on_delete_range(self, textbuffer, start, end):
        """Callback for delete range"""
    
        # start next action
        self.next_action = DeleteAction(self, start.get_offset(), 
                                        end.get_offset(),
                                        start.get_slice(end),
                                        self.get_iter_at_mark(
                                            self.get_insert()).get_offset())
        
    
    def on_insert_pixbuf(self, textbuffer, it, pixbuf):
        """Callback for inserting a pixbuf"""
        pass
    
    
    def on_insert_child_anchor(self, textbuffer, it, anchor):
        """Callback for inserting a child anchor"""
        self.next_action = InsertChildAction(self, it.get_offset(), anchor)
    
    def on_apply_tag(self, textbuffer, tag, start, end):
        """Callback for tag apply"""
        
        self.begin_user_action()
        action = ModifyAction(self)
        self.undo_stack.do(action.do, action.undo)
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), True)
        self.undo_stack.do(action.do, action.undo, False)
        self.end_user_action()
    
    def on_remove_tag(self, textbuffer, tag, start, end):
        """Callback for tag remove"""
    
        self.begin_user_action()
        action = ModifyAction(self)
        self.undo_stack.do(action.do, action.undo)
        action = TagAction(self, tag, start.get_offset(), 
                           end.get_offset(), False)
        self.undo_stack.do(action.do, action.undo, False)
        self.end_user_action()
    
    
    def on_changed(self, textbuffer):
        """Callback for buffer change"""
    
        
        if isinstance(self.next_action, InsertAction):
            # apply current style to inserted text
            
            if len(self.current_tags) > 0:
                it = self.get_iter_at_mark(self.insert_mark)
                it2 = it.copy()
                it2.forward_chars(self.next_action.length)

                for tag in self.current_tags:
                    self.apply_tag(tag, it, it2)

                self.delete_mark(self.insert_mark)
                self.insert_mark = None
                
        elif isinstance(self.next_action, DeleteAction):
            # deregister any deleted anchors
            
            for kind, offset, param in self.next_action.contents:
                if kind == "anchor":
                    self.anchors.remove(param[0])
        
        
        if self.next_action:
            self.begin_user_action()        
            action = ModifyAction(self)
            self.undo_stack.do(action.do, action.undo)
            self.undo_stack.do(self.next_action.do, self.next_action.undo, False)
            self.next_action = None            
            self.end_user_action()


    def on_child_selected(self, child):
        it = self.get_iter_at_child_anchor(child)        
        end = it.copy()        
        end.forward_char() #cursor_position()
        self.select_range(it, end)
        #self.place_cursor(it)
        

    def on_child_popup_menu(self, child, button, activate_time):
        if self.textview:
            self.textview.on_child_popup_menu(child, button, activate_time)
            
    
    def highlight_children(self):
        #return
        sel = self.get_selection_bounds()
        
        if len(sel) > 0:
            a = sel[0].get_offset()
            b = sel[1].get_offset()
            for child in self.anchors:
                it = self.get_iter_at_child_anchor(child)
                offset = it.get_offset()
                if a <= offset < b:
                    child.highlight()
                else:
                    child.unhighlight()

            # make sure textview does not lose focus
            if self.textview:
                self.textview.grab_focus()
        else:
            # unselect all children
            for child in self.anchors:
                child.unhighlight()
    
    #==============================================================
    # Tag manipulation    

    def toggle_tag_selected(self, tag):
        self.begin_user_action()
        it = self.get_selection_bounds()
        
        if len(it) == 0:
            if tag not in self.current_tags:
                self.clear_current_font_tags(tag)
                self.current_tags.append(tag)
            else:
                self.current_tags.remove(tag)
        else:
            self.current_tags = []
            if not it[0].has_tag(tag):
                self.clear_font_tags(tag, it[0], it[1])
                self.apply_tag(tag, it[0], it[1])
            else:
                self.remove_tag(tag, it[0], it[1])
        
        self.end_user_action()
    

    def apply_tag_selected(self, tag):
        self.begin_user_action()    
        it = self.get_selection_bounds()
        
        if len(it) == 0:
            if tag not in self.current_tags:
                self.clear_current_font_tags(tag)
                self.current_tags.append(tag)
        else:
            self.current_tags = []
            self.clear_font_tags(tag, it[0], it[1])
            self.apply_tag(tag, it[0], it[1])
        self.end_user_action()


    def remove_tag_selected(self, tag):
        self.begin_user_action()
        it = self.get_selection_bounds()
        
        if len(it) == 0:
            if tag in self.current_tags:
                self.current_tags.remove(tag)
        else:
            self.current_tags = []
            self.remove_tag(tag, it[0], it[1])
        self.end_user_action()
    
    
    def clear_font_tags(self, tag, start, end):
        
        # remove other justify tags
        if tag in self.justify_tags:
            for tag2 in self.justify_tags:
                self.remove_tag(tag2, start, end)
        
        # remove other family tags        
        elif tag in self.family_tags:
            for tag2 in self.family_tags:
                self.remove_tag(tag2, start, end)
        
        # remove other size tags                    
        elif tag in self.size_tags:
            for tag2 in self.size_tags:
                self.remove_tag(tag2, start, end)

    def clear_current_font_tags(self, tag):
        
        # remove other justify tags
        if tag in self.justify_tags:
            for tag2 in self.justify_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)
        
        # remove other family tags        
        elif tag in self.family_tags:
            for tag2 in self.family_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)
        
        # remove other size tags                    
        elif tag in self.size_tags:
            for tag2 in self.size_tags:
                if tag2 in self.current_tags:
                    self.current_tags.remove(tag2)

    
    #===========================================================
    # Font management


    def lookup_mod_tag(self, mod):
        """Lookup Bold, Italic, and Underline"""
        return self.tag_table.lookup(mod)
    
    
    def lookup_family_tag(self, family):
        tag = self.tag_table.lookup(family)
        if tag == None:
            tag = self.create_tag(family, family=family)
            self.add_family_tag(tag)
        return tag
    
    def lookup_size_tag(self, size):
        sizename = "size %d" % size
        tag = self.tag_table.lookup(sizename)
        if tag == None:
            tag = self.create_tag(sizename, size_points=size)
            self.add_size_tag(tag)
        return tag
    
    def add_family_tag(self, tag):
        self.family_tags.add(tag)        
    
    def add_size_tag(self, tag):
        self.size_tags.add(tag)
    

    def parse_font(self, fontstr):
        tokens = fontstr.split(" ")
        size = int(tokens.pop())
        mods = []
        
        # NOTE: underline is not part of the font string and is handled separately
        while tokens[-1] in ["Bold", "Italic"]:
            mods.append(tokens.pop())

        return " ".join(tokens), mods, size
    
    def get_font(self):
        # get iter for retrieving font
        it2 = self.get_selection_bounds()
        
        if len(it2) == 0:
            it = self.get_iter_at_mark(self.get_insert())
        else:
            it = it2[0]
            it.forward_char()
        
        # create a set that is fast for quering the existance of tags
        current_tags = set(self.current_tags)        
        
        # get the text attributes and font at the iter
        if self.textview:
            attr = self.textview.get_default_attributes()
        else:
            attr = gtk.TextAttributes()
        it.get_attributes(attr)        
        font = attr.font
        
        # set family
        family = font.get_family()
        
        # set modifications (current tags override)
        mods = {"bold":
                self.bold_tag in current_tags or
                font.get_weight() == pango.WEIGHT_BOLD,
                "italic": 
                self.italic_tag in current_tags or
                font.get_style() == pango.STYLE_ITALIC,
                "underline":
                self.underline_tag in current_tags or
                attr.underline == pango.UNDERLINE_SINGLE}
        
        # set justification
        justify = self.justify2name[attr.justification]
        
        # current tags override
        if self.center_tag in current_tags:
            justify = "center"
            
        elif self.right_tag in current_tags:
            justify = "right"
        
        elif self.fill_tag in current_tags:
            justify = "fill"
        
        # get size in points (get_size() returns pango units)
        size = font.get_size() // 1024
        
        for tag in self.current_tags:
            if tag in self.family_tags:
                family = tag.get_property("name")
            
            elif tag in self.size_tags:
                size = int(tag.get_property("size-points"))
        
        return mods, justify, family, size


    #=========================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        self.undo_stack.undo()
        
    def redo(self):
        """Redo the last action in the RichTextView"""    
        self.undo_stack.redo()    
    
    def on_begin_user_action(self, textbuffer):
        """Begin a composite undo/redo action"""
        self.undo_stack.begin_action()

    def on_end_user_action(self, textbuffer):
        """End a composite undo/redo action"""
        self.undo_stack.end_action()


class RichTextMenu (gtk.Menu):
    """A popup menu for child widgets in a RichTextView"""
    def __inti__(self):
        gkt.Menu.__init__(self)
        self._child = None

    def set_child(self, child):
        self._child = child

    def get_child(self):
        return self._child




class RichTextView (gtk.TextView):
    """A RichText editor widget"""

    def __init__(self):
        gtk.TextView.__init__(self, RichTextBuffer(self))
        self.textbuffer = self.get_buffer()
        self.blank_buffer = RichTextBuffer(self)
        
        # spell checker
        self._spell_checker = None
        self.enable_spell_check(True)
        
        # signals
        self.textbuffer.connect("modified-changed", self.on_modified_changed)
        self.block_modified = False
        
        self.set_wrap_mode(gtk.WRAP_WORD)
        self.set_property("right-margin", 5)
        self.set_property("left-margin", 5)
        
        self.ignore_font_upate = False
        self.first_menu = True

        # drag and drop
        self.connect("drag-data-received", self.on_drag_data_received)
        self.connect("drag-motion", self.on_drag_motion)
        self.drag_dest_add_image_targets()

        # clipboard
        self.connect("copy-clipboard", lambda w: self.on_copy())
        self.connect("cut-clipboard", lambda w: self.on_cut())
        self.connect("paste-clipboard", lambda w: self.on_paste())
        self.connect("button-press-event", self.on_button_press)
        
        
        #[('GTK_TEXT_BUFFER_CONTENTS', 1, 0), ('UTF8_STRING', 0, 0), ('COMPOUND_TEXT', 0, 0), ('TEXT', 0, 0), ('STRING', 0, 0), ('text/plain;charset=utf-8', 0, 0), ('text/plain;charset=ANSI_X3.4-1968', 0, 0), ('text/plain', 0, 0)]
        
        #self.connect("populate-popup", self.on_popup)
        
        # initialize HTML buffer
        self.html_buffer = HtmlBuffer()
        
        # popup menus
        self.image_menu = RichTextMenu()
        self.image_menu.attach_to_widget(self, lambda w,m:None)

        item = gtk.ImageMenuItem(gtk.STOCK_CUT)
        item.connect("activate", lambda w: self.emit("cut-clipboard"))
        self.image_menu.append(item)
        item.show()
        
        item = gtk.ImageMenuItem(gtk.STOCK_COPY)
        item.connect("activate", lambda w: self.emit("copy-clipboard"))
        self.image_menu.append(item)
        item.show()

        item = gtk.ImageMenuItem(gtk.STOCK_DELETE)
        item.connect("activate", lambda w: self.textbuffer.delete_selection(True, True))
        self.image_menu.append(item)
        item.show()
        

        
        # requires new pygtk
        #self.textbuffer.register_serialize_format(MIME_TAKENOTE, 
        #                                          self.serialize, None)
        #self.textbuffer.register_deserialize_format(MIME_TAKENOTE, 
        #                                            self.deserialize, None)

    def on_modified_changed(self, textbuffer):
        
        # propogate modified signal to listeners of this textview
        if not self.block_modified:
            self.emit("modified", textbuffer.get_modified())
    
    
    def set_buffer(self, textbuffer):
        # tell current buffer we are detached
        if self.textbuffer:
            self.textbuffer.set_textview(None)
        
        # change buffer
        if textbuffer:
            gtk.TextView.set_buffer(self, textbuffer)
        else:
            gtk.TextView.set_buffer(self, self.blank_buffer)
        self.textbuffer = textbuffer
        
        # tell new buffer we are attached
        if self.textbuffer:
            self.textbuffer.set_textview(self)


    def on_button_press(self, widget, event):
        pass #print "click"

    

    #=======================================================
    # Drag and drop

    def on_drag_motion(self, textview, drag_context, x, y, timestamp):
        
        # check for image targets
        img_target = self.drag_dest_find_target(drag_context, 
            [("image/png", 0, 0) ,
             ("image/bmp", 0, 0) ,
             ("image/jpeg", 0, 0),
             ("image/xpm", 0, 0)])
             
        if img_target is not None and img_target != "NONE":
            textview.drag_dest_set_target_list([(img_target, 0, 0)])
        
        elif "application/pdf" in drag_context.targets:
            textview.drag_dest_set_target_list([("application/pdf", 0, 0)])
        
        else:
            textview.drag_dest_set_target_list([("text/plain", 0, 0)])
            
    
    
    def on_drag_data_received(self, widget, drag_context, x, y,
                              selection_data, info, eventtime):
        
        img_target = self.drag_dest_find_target(drag_context, 
            [("image/png", 0, 0) ,
             ("image/bmp", 0, 0) ,
             ("image/jpeg", 0, 0),
             ("image/xpm", 0, 0)])
             
        if img_target not in (None, "NONE"):
            pixbuf = selection_data.get_pixbuf()
            
            if pixbuf != None:
                image = RichTextImage()
                image.set_from_pixbuf(pixbuf)
        
                self.insert_image(image)
            
                drag_context.finish(True, True, eventtime)
                self.stop_emission("drag-data-received")
                
                
        elif self.drag_dest_find_target(drag_context, 
                   [("application/pdf", 0, 0)]) not in (None, "NONE"):
            
            
            data = selection_data.data
            
            f, imgfile = tempfile.mkstemp(".png", "takenote")
            os.close(f)
            
            out = os.popen("convert - %s" % imgfile, "wb")
            out.write(data)
            out.close()
            
            name, ext = os.path.splitext(imgfile)
            imgfile2 = name + "-0" + ext
            
            if os.path.exists(imgfile2):
                i = 0
                while True:
                    imgfile = name + "-" + str(i) + ext
                    if not os.path.exists(imgfile):
                        break
                    self.insert_pdf_image(imgfile)
                    os.remove(imgfile)
                    i += 1
                    
            elif os.path.exists(imgfile):
                
                self.insert_pdf_image(imgfile)
                os.remove(imgfile)
            
            drag_context.finish(True, True, eventtime)
            self.stop_emission("drag-data-received")
        
        elif self.drag_dest_find_target(drag_context, 
                   [("text/plain", 0, 0)]) not in (None, "NONE"):
            
            self.textbuffer.insert_at_cursor(selection_data.get_text())
                        
            
    def insert_pdf_image(self, imgfile):
        pixbuf = gdk.pixbuf_new_from_file(imgfile)
        img = RichTextImage()
        img.set_from_pixbuf(pixbuf)
        self.insert_image(img, "pdf.png")

        
    """
    def on_popup(self, textview, menu):
        return
        self.first_menu = False
        menu.foreach(lambda item: menu.remove(item))

        # Create the menu item
        copy_item = gtk.MenuItem("Copy")
        copy_item.connect("activate", self.on_copy)
        menu.add(copy_item)
        
        accel_group = menu.get_accel_group()
        print "accel", accel_group
        if accel_group == None:
            accel_group = gtk.AccelGroup()
            menu.set_accel_group(accel_group)
            print "get", menu.get_accel_group()


        # Now add the accelerator to the menu item. Note that since we created
        # the menu item with a label the AccelLabel is automatically setup to 
        # display the accelerators.
        copy_item.add_accelerator("activate", accel_group, ord("C"),
                                  gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
        copy_item.show()                                  
    """
            
           

    

    
    
    #==================================================================
    # Copy and Paste

    def on_copy(self):
        """Callback for copy action"""
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.textbuffer.copy_clipboard(clipboard)
        self.stop_emission('copy-clipboard')
    
    def on_cut(self):
        """Callback for cut action"""    
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.textbuffer.cut_clipboard(clipboard, self.get_editable())
        self.stop_emission('cut-clipboard')
    
    def on_paste(self):
        """Callback for paste action"""    
        clipboard = self.get_clipboard(selection="CLIPBOARD")
        self.textbuffer.paste_clipboard(clipboard, None, self.get_editable())
        self.stop_emission('paste-clipboard')

    
    #==================================================================
    # File I/O
    
    def save(self, filename):
        path = os.path.dirname(filename)
        self.save_images(path)
        
        try:
            out = open(filename, "wb")
            self.html_buffer.set_output(out)
            self.html_buffer.write(self)
            out.close()
        except IOError, e:
            raise RichTextError("Could not save '%s'." % filename, e)
        
        self.textbuffer.set_modified(False)
    
    
    def load(self, filename):
        textbuffer = self.textbuffer
        
        # unhook expensive callbacks
        self.block_modified = True
        textbuffer.undo_stack.suppress()
        textbuffer.block_signals()
        self.set_buffer(None)
        
        # clear buffer        
        textbuffer.clear()
        
        err = None
        try:
            #from rasmus import util
            #util.tic("read")
        
            self.html_buffer.read(textbuffer, open(filename, "r"))
            
            #util.toc()
            
        except (HtmlError, IOError), e:
            err = e
            
            # TODO: turn into function
            textbuffer.clear()
            self.set_buffer(textbuffer)
            
            ret = False
        else:
            self.set_buffer(textbuffer)
            textbuffer.add_deferred_anchors()
        
            path = os.path.dirname(filename)
            self.load_images(path)
            
            ret = True
        
        # rehook up callbacks
        textbuffer.unblock_signals()
        self.textbuffer.undo_stack.resume()
        self.textbuffer.undo_stack.reset()
        self.enable()

        self.block_modified = False        
        self.textbuffer.set_modified(False)

        
        if not ret:
            raise RichTextError("Error loading '%s'." % filename, e)
        
   
        
    
    def load_images(self, path):
        """Load images present in textbuffer"""
        
        for kind, it, param in iter_buffer_contents(self.textbuffer):
            if kind == "anchor":
                child, widgets = param
                    
                if isinstance(child, RichTextImage):
                    filename = os.path.join(path, child.get_filename())
                    child.set_from_file(filename)
                    child.get_widget().show()

    
    def save_images(self, path):
        """Save images present in text buffer"""
        
        for kind, it, param in iter_buffer_contents(self.textbuffer):
            if kind == "anchor":
                child, widgets = param
                    
                if isinstance(child, RichTextImage):
                    filename = os.path.join(path, child.get_filename())
                    if child.save_needed():
                        child.write(filename)
                    

    #=============================================
    # State
    
    def is_modified(self):
        return self.textbuffer.get_modified()
    
        
    def enable(self):
        self.set_sensitive(True)
    
    
    def disable(self):
        
        self.block_modified = True
        self.textbuffer.undo_stack.suppress()
        
        start = self.textbuffer.get_start_iter()
        end = self.textbuffer.get_end_iter()
        self.textbuffer.remove_all_tags(start, end)
        self.textbuffer.delete(start, end)
        self.set_sensitive(False)
        
        self.textbuffer.undo_stack.resume()
        self.textbuffer.undo_stack.reset()
        self.block_modified = False
        self.textbuffer.set_modified(False)
    
    """
    def serialize(self, register_buf, content_buf, start, end, data):
        print "serialize", content_buf
        self.a = u"SERIALIZED"
        return self.a 
    
    
    def deserialize(self, register_buf, content_buf, it, data, create_tags, udata):
        print "deserialize"
    """

    #=====================================================
    # Popup Menus

    def on_child_popup_menu(self, child, button, activate_time):
        self.image_menu.set_child(child)
        
        if isinstance(child, RichTextImage):
            self.image_menu.popup(None, None, None, button, activate_time)
            self.image_menu.show()
            
    def get_image_menu(self):
        return self.image_menu
        
    
    #===========================================================
    # Actions
        
    def insert_image(self, image, filename="image.png"):
        """Inserts an image into the textbuffer"""
                
        self.textbuffer.insert_image(image, filename)    


    def insert_hr(self):
        self.textbuffer.insert_hr()
        
    
    def forward_search(self, it, text, case_sensitive):
        it = it.copy()
        text = unicode(text, "utf8")
        if not case_sensitive:
            text = text.lower()
        
        textlen = len(text)
        
        while True:
            end = it.copy()
            end.forward_chars(textlen)
                        
            text2 = it.get_slice(end)
            if not case_sensitive:
                text2 = text2.lower()
            
            if text2 == text:
                return it, end
            if not it.forward_char():
                return None
    
    
    def backward_search(self, it, text, case_sensitive):
        it = it.copy()
        it.backward_char()
        text = unicode(text, "utf8")
        if not case_sensitive:
            text = text.lower()
        
        textlen = len(text)
        
        while True:
            end = it.copy()
            end.forward_chars(textlen)
                        
            text2 = it.get_slice(end)
            if not case_sensitive:
                text2 = text2.lower()
            
            if text2 == text:
                return it, end
            if not it.backward_char():
                return None

        
    
    def find(self, text, case_sensitive=False, forward=True, next=True):
        # TODO: non-case_sensitive is ignored
        
        if not self.textbuffer:
            return
        
        it = self.textbuffer.get_iter_at_mark(self.textbuffer.get_insert())
        
        
        if forward:
            if next:
                it.forward_char()
            result = self.forward_search(it, text, case_sensitive)
        else:
            result = self.backward_search(it, text, case_sensitive)
        
        if result:
            self.textbuffer.select_range(result[0], result[1])
            self.scroll_mark_onscreen(self.textbuffer.get_insert())
            return result[0].get_offset()
        else:
            return -1
        
        
    def replace(self, text, replace_text, 
                case_sensitive=False, forward=True, next=True):
        
        pos = self.find(text, case_sensitive, forward, next)
        
        if pos != -1:
            self.textbuffer.begin_user_action()
            self.textbuffer.delete_selection(True, self.get_editable())
            self.textbuffer.insert_at_cursor(replace_text)
            self.textbuffer.end_user_action()
            
        return pos
        
            
    def replace_all(self, text, replace_text, 
                    case_sensitive=False, forward=True):
        found = False
        
        self.textbuffer.begin_user_action()
        while self.replace(text, replace_text, case_sensitive, forward, False) != -1:
            found = True
        self.textbuffer.end_user_action()
        
        return found
        
    
    def can_spell_check(self):
        return gtkspell is not None
    
    def enable_spell_check(self, enabled=True):
        if not self.can_spell_check():
            return           
        
        if enabled:
            if self._spell_checker is None:
                self._spell_checker = gtkspell.Spell(self)
        else:
            if self._spell_checker is not None:
                self._spell_checker.detach()
                self._spell_checker = None
        
    #===========================================================
    # Callbacks from UI to change font 

    def on_bold(self):
        self.textbuffer.toggle_tag_selected(self.textbuffer.bold_tag)
        
    def on_italic(self):
        self.textbuffer.toggle_tag_selected(self.textbuffer.italic_tag)
    
    def on_underline(self):
        self.textbuffer.toggle_tag_selected(self.textbuffer.underline_tag)       
    
    def on_font_set(self, widget):
        family, mods, size = self.textbuffer.parse_font(widget.get_font_name())
        
        # apply family tag
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_family_tag(family))
        
        # apply size
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_size_tag(size))
        
        # apply mods
        for mod in mods:
            self.textbuffer.apply_tag_selected(self.textbuffer.tag_table.lookup(mod))
        
        # disable mods not given
        for mod in ["Bold", "Italic", "Underline"]:
            if mod not in mods:
                self.textbuffer.remove_tag_selected(self.textbuffer.tag_table.lookup(mod))
    
    def on_font_family_set(self, family):
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_family_tag(family))
    
    def on_font_family_toggle(self, family):
        self.textbuffer.toggle_tag_selected(self.textbuffer.lookup_family_tag(family))
    
    def on_font_size_set(self, size):
        self.textbuffer.apply_tag_selected(self.textbuffer.lookup_size_tag(size))
    
    def on_left_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.left_tag)
        
    def on_center_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.center_tag)
    
    def on_right_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.right_tag)
    
    def on_fill_justify(self):
        self.textbuffer.apply_tag_selected(self.textbuffer.fill_tag)
    
    #==================================================================
    # UI Updating from chaning font under cursor
    
    def on_update_font(self):
        mods, justify, family, size = self.get_font()
        self.emit("font-change", mods, justify, family, size)
    
    def get_font(self):
        return self.textbuffer.get_font()
    
    
    #=========================================
    # undo/redo methods
    
    def undo(self):
        """Undo the last action in the RichTextView"""
        self.textbuffer.undo()
        
    def redo(self):
        """Redo the last action in the RichTextView"""    
        self.textbuffer.redo()    


gobject.type_register(RichTextView)
gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (bool,))
gobject.signal_new("font-change", RichTextView, gobject.SIGNAL_RUN_LAST, 
    gobject.TYPE_NONE, (object, str, str, int))
#gobject.signal_new("error", RichTextView, gobject.SIGNAL_RUN_LAST, 
#    gobject.TYPE_NONE, (str, object,))

