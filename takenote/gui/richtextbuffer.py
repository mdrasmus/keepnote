


# python imports
import sys, os, tempfile, re
import urllib2
import StringIO
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

from takenote.gui.textbuffer_tools import \
     iter_buffer_contents as iter_buffer_contents2, \
     buffer_contents_iter_to_offset, \
     normalize_tags, \
     insert_buffer_contents, \
     buffer_contents_apply_tags

#from takenote.gui.textbuffer_html import HtmlBuffer, HtmlError

# constants
MIME_TAKENOTE = "application/x-takenote"


# these tags will not be enumerated by iter_buffer_contents
IGNORE_TAGS = set(["gtkspell-misspelled", "hr"])

MAX_UNDOS = 100

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

        
TAG_PATTERN = re.compile("<[^>]*>")
def strip_tags(line):
    return re.sub(TAG_PATTERN, "", line)



def add_child_to_buffer(textbuffer, it, anchor):
    textbuffer.add_child(it, anchor)

def iter_buffer_contents(textbuffer, start=None, end=None,
                         ignore_tags=IGNORE_TAGS):
    return iter_buffer_contents2(textbuffer, start, end, ignore_tags)






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
# RichText actions

class Action (object):
    """A base class for undoable actions in RichTextBuffer"""
    
    def __init__(self):
        pass
    
    def do(self):
        pass
    
    def undo(self):
        pass


class ModifyAction (Action):
    """Represents the act of changing the RichTextBuffer's modified state"""
    
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

        # NOTE: this is probably a bug.  I need to insert and then modify the
        # tags of the insertion.
        # Or, I also change the current font (using current_tags) and then
        # do a normal text insert, mimicking the original text insert more
        # faithfully
        self.textbuffer.insert_with_tags(start, self.text, *self.current_tags)
    
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
        insert_buffer_contents(self.textbuffer, start, self.contents,
                               add_child=add_child_to_buffer)
        cursor = self.textbuffer.get_iter_at_offset(self.cursor_offset)
        self.textbuffer.place_cursor(cursor)
        self.textbuffer.end_user_action()

    
    def record_range(self):
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
        """Set the image from a file"""
        
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
        """Write image to file"""
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

            if event.type == gtk.gdk._2BUTTON_PRESS:
                self.emit("activated")
            
            return True
        elif event.button == 3:
            # popup menu
            self.emit("selected")
            self.emit("popup-menu", event.button, event.time)
            return True



        

#=============================================================================
# RichText classes

class RichTextBuffer (gtk.TextBuffer):
    def __init__(self, textview=None):
        gtk.TextBuffer.__init__(self)
        self.clipboard_contents = None
        self.textview = textview
        self.undo_stack = UndoStack(MAX_UNDOS)
        self._html_parser = None
        
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
        self.signals = [
            self.connect("begin_user_action", self.on_begin_user_action),
            self.connect("end_user_action", self.on_end_user_action),
            self.connect("mark-set", self.on_mark_set),
            self.connect("insert-text", self.on_insert_text),
            self.connect("delete-range", self.on_delete_range),
            self.connect("insert-pixbuf", self.on_insert_pixbuf),
            self.connect("insert-child-anchor", self.on_insert_child_anchor),
            self.connect("apply-tag", self.on_apply_tag),
            self.connect("remove-tag", self.on_remove_tag),
            self.connect("changed", self.on_changed)
            ]
                
        self.init_fonts()
        

    def init_fonts(self):
        """Initialize font tags"""

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
            gtk.JUSTIFY_FILL: "fill"
        }
        
        self.justify_tags = set([self.left_tag, self.center_tag,
                                 self.right_tag, self.fill_tag])
        self.family_tags = set()
        self.size_tags = set()

        self.default_attr = gtk.TextAttributes()

    
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

    # TODO: move cut/copy/paste to textview
    # that way I have access to RichTextHtml for html paste
    # and possibly html copy

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
        
        targets = set(clipboard.wait_for_targets())
        
        if targets is None:
            # do nothing
            return
            
        
        if MIME_TAKENOTE in targets:
            clipboard.request_contents(MIME_TAKENOTE, self.do_paste_object)
        elif "text/html" in targets:
            clipboard.request_contents("text/html", self.do_paste_html)
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
        """Paste text into buffer"""
        self.begin_user_action()
        self.delete_selection(False, True)
        self.insert_at_cursor(text)
        self.end_user_action()

    def do_paste_html(self, clipboard, selection_data, data):
        """Paste HTML into buffer"""
        
        html = parse_utf(selection_data.data)        
        self.begin_user_action()
        self.delete_selection(False, True)
        self.insert_html(html)
        self.end_user_action()
        
        
    
    def do_paste_image(self, clipboard, selection_data, data):
        """Paste image into buffer"""
        
        pixbuf = selection_data.get_pixbuf()
        image = RichTextImage()
        image.set_from_pixbuf(pixbuf)
        
        self.insert_image(image)

    
    def do_paste_object(self, clipboard, selection_data, data):
        """Paste a program-specific object into buffer"""
        
        if self.clipboard_contents is None:
            # do nothing
            return
        
        self.begin_user_action()
        it = self.get_iter_at_mark(self.get_insert())
        insert_buffer_contents(self, it, self.clipboard_contents,
                               add_child=add_child_to_buffer)
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
        child.connect("activated", self.on_child_activated)
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
        """Insert Horizontal Rule"""
        self.begin_user_action()

        it = self.get_iter_at_mark(self.get_insert())
        hr = RichTextHorizontalRule()
        self.add_child(it, hr)
        
        self.end_user_action()


    def insert_html(self, html):
        """Insert HTML content into Buffer"""
        
        if self.textview is None:
            return

        contents = list(self.textview._html_buffer.read([html],
                                                        partial=True))
        
        
        for kind, pos, param in contents:
            
            # download and images included in html
            if kind == "anchor" and isinstance(param[0], RichTextImage):
                img = param[0]
                if img.get_filename().startswith("http:"):
                    infile = urllib2.urlopen(img.get_filename())
                    f, imgfile = tempfile.mkstemp("", "takenote")
                    os.close(f)
                    outfile = open(imgfile, "w")
                    outfile.write(infile.read())
                    outfile.close()

                    img.set_filename("image.png")
                    img.set_from_file(imgfile)
                    
        # add to buffer
        self.begin_user_action()
        insert_buffer_contents(self, self.get_iter_at_mark(self.get_insert()),
                               contents,
                               add_child=add_child_to_buffer,
                               lookup_tag=lambda name: self.lookup_tag(name))
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

            self.highlight_children()
            
            # update UI for current fonts
            mods, justify, family, size = self.get_font()
            self.emit("font-change", mods, justify, family, size)
            
            

    
    
    def on_insert_text(self, textbuffer, it, text, length):
        """Callback for text insert"""
        
        # start new action
        self.next_action = InsertAction(self, it.get_offset(), text, length)
        self.insert_mark = self.create_mark(None, it, True)

    def on_delete_range(self, textbuffer, start, end):
        """Callback for delete range"""

        # TODO: deregister children in selection?
        
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
        """Callback for when child object is selected

           Make sure buffer knows the selection
        """
        
        it = self.get_iter_at_child_anchor(child)        
        end = it.copy()        
        end.forward_char()
        self.select_range(it, end)


    def on_child_activated(self, child):
        """Callback for when child is activated (e.g. double-clicked)"""

        self.emit("child-activated", child)
    

    def on_child_popup_menu(self, child, button, activate_time):
        """Callback for when child's menu is visible"""

        # forward callback to textview, if it exists
        self.emit("child-menu", child, button, activate_time)
            
    
    def highlight_children(self):
        """Highlight any children that are within selection range"""
        
        sel = self.get_selection_bounds()
        focus = None
        
        if len(sel) > 0:
            
            # selection exists, get range (a, b)
            a = sel[0].get_offset()
            b = sel[1].get_offset()
            for child in self.anchors:
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

    def lookup_tag(self, name):
        """Lookup any tag, create it if needed"""

        # test to see if name is in table
        tag = self.tag_table.lookup(name)

        if tag:
            return tag

        # test to see if name is a font size
        elif name.startswith("size"):
            return self.lookup_size_tag(int(name.split(" ")[1]))

        else:
            # must be family tag
            return self.lookup_family_tag(name)
        
        
        

    def lookup_mod_tag(self, mod):
        """Lookup Bold, Italic, and Underline"""
        return self.tag_table.lookup(mod)
    
    
    def lookup_family_tag(self, family):
        tag = self.tag_table.lookup(family)
        if tag is None:
            # TODO: do I need to do error handling here?
            tag = self.create_tag(family, family=family)
            self.add_family_tag(tag)
        return tag
    
    def lookup_size_tag(self, size):
        sizename = "size %d" % size
        tag = self.tag_table.lookup(sizename)
        if tag is None:
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
        attr = gtk.TextAttributes()
        self.default_attr.copy_values(attr)
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


gobject.type_register(RichTextBuffer)
gobject.signal_new("font-change", RichTextBuffer, gobject.SIGNAL_RUN_LAST, 
                   gobject.TYPE_NONE, (object, str, str, int))
gobject.signal_new("child-activated", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object,))
gobject.signal_new("child-menu", RichTextBuffer, gobject.SIGNAL_RUN_LAST,
                   gobject.TYPE_NONE, (object, object, object))
#gobject.signal_new("modified", RichTextView, gobject.SIGNAL_RUN_LAST, 
#    gobject.TYPE_NONE, (bool,))

